# Bot core: admin command handlers + the every-minute price-scrape loop.
# Dev comments & logs are English; bot-facing message texts stay Persian.
import html as html_mod
import logging
from datetime import datetime

import httpx
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from . import database as db
from . import formatting as fmt
from . import settings as settings_mod
from .config import (
    ADMIN_IDS,
    POLL_INTERVAL,
    SOURCE_CHANNEL,
    TEHRAN,
    within_working_hours,
)
from .jalali import format_jalali_date, format_jalali_time, format_jalali_datetime
from .persian import fa_digits
from .scraper import fetch_messages, parse_message

log = logging.getLogger("bot")


# ── Helpers ─────────────────────────────────────────────────────────────
def is_admin(update: Update) -> bool:
    user = update.effective_user
    return user is not None and user.id in settings_mod.get_admins()


def extract_latest(messages) -> dict:
    """Pick the newest sell across the page's messages."""
    result: dict = {}
    for msg in messages:
        parsed = parse_message(msg.text)
        if not parsed:
            continue
        kind, value = parsed
        prev = result.get(kind)
        if prev is None or msg.id >= prev["msg_id"]:
            result[kind] = {"value": value, "msg_id": msg.id, "time": msg.time_iso}
    return result


async def collect_once(context: ContextTypes.DEFAULT_TYPE) -> dict | None:
    """Read the channel once; return the latest sell or None on error."""
    client: httpx.AsyncClient = context.bot_data["http"]
    messages = await fetch_messages(SOURCE_CHANNEL, client)
    if messages is None:
        return None
    latest = extract_latest(messages)
    if not latest:
        log.warning("no price message found on the channel page")
        return None
    return latest


# ── Auto-publish to the target channel (1-min price post) ───────────────
async def maybe_auto_publish(
    context: ContextTypes.DEFAULT_TYPE,
    latest: dict,
    now_tehran: datetime,
    changed_kinds: set[str],
) -> None:
    """If auto-publish is on and a channel is set: check every minute and send a
    new post whenever the SELL value changed since the last scan. A steady price
    sends nothing. (Buy is derived from sell, so it never triggers a post by
    itself.)"""
    if not settings_mod.get("auto_enabled"):
        return
    target = settings_mod.get("channel")
    if not target:
        return

    # Business hours only: 09:30–20:00 Tehran; silent outside that window
    if not within_working_hours(now_tehran):
        return

    if "sell" not in changed_kinds:
        return  # only a SELL change creates a new post (buy is computed)

    keyboard = fmt.contact_keyboard(context.bot.username)
    text = fmt.publish_post_1m(latest)
    try:
        await context.bot.send_message(
            chat_id=target,
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
        )
        db.save_state(
            "last_post",
            {
                "jalali": format_jalali_datetime(now_tehran),
                "buy": settings_mod.computed_buy(latest.get("sell", {}).get("value")),
                "sell": latest.get("sell", {}).get("value"),
            },
        )
    except Exception as exc:  # noqa: BLE001 — a channel failure must not stall the poller
        log.error("auto-publish to %s failed: %s", target, exc)


# ── 30-minute greeting post ─────────────────────────────────────────────
async def publish_30m_greeting(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send the 30-minute greeting post at exact 30-min slots: 09:30, 10:00, 10:30...
    Runs every minute; only sends when minute in {0, 30} and within work hours.
    Uses 'last_30m_slot' in DB to avoid duplicate sends."""
    if not settings_mod.get("auto_enabled"):
        return
    if not settings_mod.get("thirty_min_enabled"):
        return
    target = settings_mod.get("channel")
    if not target:
        return

    now_tehran = datetime.now(TEHRAN)
    # Only during work hours 09:30–20:00
    if not within_working_hours(now_tehran):
        return

    # Only fire at :00 or :30 minutes
    if now_tehran.minute not in (0, 30):
        return

    # Build a slot key like "2026-08-26-09-30" to deduplicate
    slot_key = now_tehran.strftime("%Y-%m-%d-%H-%M")
    state = db.get_state()
    last_slot = state.get("last_30m_slot")
    if last_slot == slot_key:
        return  # already sent for this slot

    # Fetch international spot prices (gold & silver) via Yahoo Finance
    from .intl_prices import fetch_gold_silver
    gold_usd, silver_usd = fetch_gold_silver()

    text = fmt.publish_post_30m({}, now_tehran, gold_usd=gold_usd, silver_usd=silver_usd)
    try:
        await context.bot.send_message(
            chat_id=target,
            text=text,
            parse_mode=ParseMode.HTML,
        )
        db.save_state("last_30m_slot", slot_key)
    except Exception as exc:  # noqa: BLE001
        log.error("30-min greeting post to %s failed: %s", target, exc)


# ── Every-minute loop ───────────────────────────────────────────────────
async def poll_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    latest = await collect_once(context)
    now_tehran = datetime.now(TEHRAN)

    if latest is None:
        context.bot_data["last_error"] = format_jalali_datetime(now_tehran)
        return

    old = db.get_state().get("prices", {})   # previous values live under key "prices"

    # Record the history for future charts/reports
    for kind, item in latest.items():
        db.insert_price(kind, item["value"], item["msg_id"])

    # NEW LOGIC: Check if we have a NEW message (new msg_id) with sell price.
    # If the message is new, post it regardless of whether the value changed.
    # This ensures every fresh message from the reference channel is relayed.
    new_msg = False
    if "sell" in latest:
        old_sell = old.get("sell")
        if old_sell is None or latest["sell"]["msg_id"] != old_sell.get("msg_id"):
            new_msg = True

    db.save_state("prices", latest)
    context.bot_data["last_ok"] = format_jalali_datetime(now_tehran)

    # 5-second debounce: don't post more often than once every 5 seconds
    last_post_ts = db.get_state().get("last_post_ts")
    now_ts = now_tehran.timestamp()
    can_post = not last_post_ts or (now_ts - last_post_ts) >= 5

    # Auto-publish to the channel (if enabled in settings).
    # Send on every NEW message from reference channel, not just value changes,
    # but respect the 5-second debounce to prevent flooding.
    if new_msg and can_post:
        await maybe_auto_publish(context, latest, now_tehran, {"sell"})
        db.save_state("last_post_ts", now_ts)
    elif new_msg and not can_post:
        # Message is new but we're in debounce — still update OK time so we
        # don't lose the "we got a new message" awareness
        pass  # last_ok already set above
    else:
        context.bot_data["last_ok"] = format_jalali_datetime(now_tehran)


# ── Bot commands ────────────────────────────────────────────────────────
async def cmd_start(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(fmt.help_text(), parse_mode=ParseMode.HTML)


async def cmd_now(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        return
    latest = await collect_once(context)
    if not latest:
        await update.effective_message.reply_text("❌ دریافت قیمت ناموفق بود؛ بعداً تلاش کن.")
        return
    merged = {**db.get_state().get("prices", {}), **latest}  # cache + fresh
    await update.effective_message.reply_text(
        fmt.admin_report(merged, datetime.now(TEHRAN)), parse_mode=ParseMode.HTML
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        return
    bd = context.bot_data
    last_ok = bd.get("last_ok", "—")
    last_err = bd.get("last_error", "—")
    count = db.count_prices()
    await update.effective_message.reply_text(
        "\n".join([
            "<b>🩺 وضعیت سرویس</b>",
            "",
            f"📡 منبع: @{SOURCE_CHANNEL}",
            f"⏱ بازهی کوئری: هر {fa_digits(POLL_INTERVAL)} ثانیه",
            f"✅ آخرین دریافت موفق: {last_ok}",
            f"⚠️ آخرین خطا: {last_err}",
            f"💾 رکوردهای تاریخچه: {fa_digits(count)}",
        ]),
        parse_mode=ParseMode.HTML,
    )


async def cmd_publish(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        return
    target = settings_mod.get("channel")
    if not target:
        await update.effective_message.reply_text(
            "هنوز کانال انتشار تنظیم نشده.\n"
            "اول ربات را ادمین کانال کن، بعد از ⚙️ /settings بخش «📡 نام کانال» "
            "نامش را ثبت کن."
        )
        return

    latest = await collect_once(context)
    if not latest:
        await update.effective_message.reply_text("❌ قیمت تازه نگرفتم؛ پست ارسال نشد.")
        return
    db.save_state("prices", {**db.get_state().get("prices", {}), **latest})

    keyboard = fmt.contact_keyboard(context.bot.username)
    try:
        await context.bot.send_message(
            chat_id=target,
            text=fmt.publish_post_1m(latest),
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
        )
        await update.effective_message.reply_text(f"✅ به {html_mod.escape(target)} ارسال شد.")
    except Exception as exc:  # noqa: BLE001
        await update.effective_message.reply_text(
            f"❌ ارسال نشد: <code>{html_mod.escape(str(exc))}</code>\n"
            "چک کن که ربات ادمین آن کانال باشد.",
            parse_mode=ParseMode.HTML,
        )


async def cmd_test30m(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Test the 30-minute greeting post manually."""
    if not is_admin(update):
        return
    target = settings_mod.get("channel")
    if not target:
        await update.effective_message.reply_text("کانال انتشار تنظیم نشده.")
        return

    now_tehran = datetime.now(TEHRAN)
    from .intl_prices import fetch_gold_silver
    gold_usd, silver_usd = fetch_gold_silver()
    text = fmt.publish_post_30m({}, now_tehran, gold_usd=gold_usd, silver_usd=silver_usd)
    try:
        await context.bot.send_message(
            chat_id=target,
            text=text,
            parse_mode=ParseMode.HTML,
        )
        await update.effective_message.reply_text("✅ پیام ۳۰ دقیقه‌ای تستی ارسال شد.")
    except Exception as exc:  # noqa: BLE001
        await update.effective_message.reply_text(
            f"❌ ارسال نشد: <code>{html_mod.escape(str(exc))}</code>",
            parse_mode=ParseMode.HTML,
        )


# ── Setup ───────────────────────────────────────────────────────────────
async def post_init(app: Application) -> None:
    """Runs once the bot is initialized."""
    db.init_db()

    app.bot_data["http"] = httpx.AsyncClient(timeout=20)

    me = await app.bot.get_me()
    app.bot_data["username"] = me.username
    log.info("bot online as @%s", me.username)

    # Every-minute price poll job
    app.job_queue.run_repeating(
        poll_job,
        interval=POLL_INTERVAL,
        first=3,
        name="gold-poller",
    )
    log.info("price poll job scheduled every %s seconds", POLL_INTERVAL)

    # 30-minute greeting post job — runs every minute, but only sends at :00/:30
    app.job_queue.run_repeating(
        publish_30m_greeting,
        interval=60,  # every minute; the handler filters to :00/:30
        first=10,
        name="greeting-30m",
    )
    log.info("30-min greeting job scheduled (runs every minute, sends at :00/:30)")


async def post_shutdown(app: Application) -> None:
    client: httpx.AsyncClient | None = app.bot_data.get("http")
    if client:
        await client.aclose()


def build_app(token: str) -> Application:
    app = (
        ApplicationBuilder()
        .token(token)
        .concurrent_updates(False)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    app.add_handler(CommandHandler(["start", "help"], cmd_start))
    app.add_handler(CommandHandler("now", cmd_now))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("publish", cmd_publish))
    app.add_handler(CommandHandler("test30m", cmd_test30m))

    # Settings panel + its buttons
    from .panel import cmd_cancel, handle_callback, handle_wait_input

    app.add_handler(CommandHandler("settings", panel_cmd_settings))
    app.add_handler(CommandHandler("cancel", cmd_cancel))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
                       handle_wait_input)
    )
    return app


async def panel_cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/settings — admins only"""
    from . import settings as cfg
    from .panel import show

    if not is_admin(update):
        await update.effective_message.reply_text("⛔️ فقط ادمینها به تنظیمات دسترسی دارند.")
        return
    await show(update, context)