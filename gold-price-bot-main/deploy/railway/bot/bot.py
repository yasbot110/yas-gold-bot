# هسته‌ی ربات: هندلرهای ادمین + حلقه‌ی هر-دقیقه استخراج قیمت
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
from .jalali import format_jalali_datetime
from .persian import fa_digits
from .scraper import fetch_messages, parse_message

log = logging.getLogger("bot")

REPORT_EVERY_MIN = 5   # هر چند دقیقه یک گزارش کامل به ادمین


# ── ابزارها ────────────────────────────────────────────────────────────
def is_admin(update: Update) -> bool:
    user = update.effective_user
    return user is not None and user.id in settings_mod.get_admins()


def extract_latest(messages) -> dict:
    """آخرین buy/sell را از بین پیام‌های صفحه پیدا می‌کند."""
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
    """یک بار کانال را می‌خواند؛ خروجی: آخرین خرید/فروش یا None در خطا"""
    client: httpx.AsyncClient = context.bot_data["http"]
    messages = await fetch_messages(SOURCE_CHANNEL, client)
    if messages is None:
        return None
    latest = extract_latest(messages)
    if not latest:
        log.warning("پیام قیمتی در صفحه‌ی کانال پیدا نشد")
        return None
    return latest


# ── انتشار خودکار در کانال ─────────────────────────────────────────────
async def maybe_auto_publish(
    context: ContextTypes.DEFAULT_TYPE,
    latest: dict,
    now_tehran: datetime,
    changed_kinds: set[str],
) -> None:
    """
    اگر انتشار خودکار فعال و کانال تنظیم شده باشد: هر دقیقه کانال مرجع چک
    می‌شود و هر وقت **مقدار** خرید/فروش نسبت به اسکن قبل عوض شده باشد،
    پست جدید با قیمت تازه فرستاده می‌شود. قیمت ثابت → هیچ پستی نمی‌رود.
    """
    if not settings_mod.get("auto_enabled"):
        return
    target = settings_mod.get("channel")
    if not target:
        return

    # ساعات کاری: فقط ۹:۳۰ تا ۲۰:۰۰ تهران پست می‌رود؛ بیرون از بازه سکوت
    if not within_working_hours(now_tehran):
        return

    if "sell" not in changed_kinds:
        return  # فقط تغییر «فروش» پست جدید می‌سازد (خرید محاسبه‌ای است)

    keyboard = fmt.contact_keyboard(context.bot.username)
    text = fmt.publish_post(latest, now_tehran)
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
    except Exception as exc:  # noqa: BLE001 — خطای کانال نباید poller را بخواباند
        log.error("انتشار خودکار به %s شکست خورد: %s", target, exc)


# ── حلقه‌ی هر دقیقه ────────────────────────────────────────────────────
async def poll_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    latest = await collect_once(context)
    now_tehran = datetime.now(TEHRAN)

    if latest is None:
        context.bot_data["last_error"] = format_jalali_datetime(now_tehran)
        return

    old = db.get_state().get("prices", {})   # مقادیر قبلی زیر کلید «prices» هستند

    # ثبت تاریخچه برای نمودارها و گزارش‌های آینده
    for kind, item in latest.items():
        db.insert_price(kind, item["value"], item["msg_id"])

    # کدام نوع‌ها نسبت به قبل عوض شدند؟
    changed_kinds = {
        kind
        for kind, item in latest.items()
        if old.get(kind) and old[kind].get("value") != item["value"]
    }

    admins = settings_mod.get_admins()

    # اعلان فوری فقط وقتی عدد نسبت به مقدار قبلیِ همان نوع عوض شده باشد
    for kind, item in latest.items():
        if kind not in changed_kinds:
            continue
        prev = old.get(kind)
        for admin_id in admins:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=fmt.change_alert(
                        kind, item["value"], prev["value"], now_tehran
                    ),
                    parse_mode=ParseMode.HTML,
                )
            except Exception as exc:  # noqa: BLE001 — هشدار نباید job را بخواباند
                log.error("ارسال هشدار تغییر به %s شکست خورد: %s", admin_id, exc)

    db.save_state("prices", latest)
    context.bot_data["last_ok"] = format_jalali_datetime(now_tehran)

    # انتشار خودکار در کانال (اگر از تنظیمات فعال باشد)
    await maybe_auto_publish(context, latest, now_tehran, changed_kinds)

    # گزارش کامل دوره‌ای به همه‌ی ادمین‌ها (قابل خاموش‌کردن از پنل)
    if settings_mod.get("reports_enabled") and now_tehran.minute % REPORT_EVERY_MIN == 0:
        for admin_id in admins:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=fmt.admin_report(latest, now_tehran),
                    parse_mode=ParseMode.HTML,
                )
            except Exception as exc:  # noqa: BLE001
                log.error("گزارش به ادمین %s نرفت: %s", admin_id, exc)


# ── دستورهای ربات ──────────────────────────────────────────────────────
async def cmd_start(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(fmt.help_text(), parse_mode=ParseMode.HTML)


async def cmd_now(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        return
    latest = await collect_once(context)
    if not latest:
        await update.effective_message.reply_text("❌ دریافت قیمت ناموفق بود؛ بعداً تلاش کن.")
        return
    merged = {**db.get_state().get("prices", {}), **latest}  # کش + تازه‌ها
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
            f"⏱ بازه‌ی کوئری: هر {fa_digits(POLL_INTERVAL)} ثانیه",
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
            text=fmt.publish_post(latest, datetime.now(TEHRAN)),
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


# ── راه‌اندازی ─────────────────────────────────────────────────────────
async def post_init(app: Application) -> None:
    """بعد از initialize شدن ربات اجرا می‌شود."""
    db.init_db()

    app.bot_data["http"] = httpx.AsyncClient(timeout=20)

    me = await app.bot.get_me()
    app.bot_data["username"] = me.username
    log.info("ربات با نام @%s آنلاین شد", me.username)

    app.job_queue.run_repeating(
        poll_job,
        interval=POLL_INTERVAL,
        first=3,
        name="gold-poller",
    )
    log.info("جاب استخراج قیمت هر %s ثانیه تنظیم شد", POLL_INTERVAL)


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

    # پنل تنظیمات + دکمه‌هایش
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
    """دستور /settings — فقط برای ادمین"""
    from . import settings as cfg
    from .panel import show

    if not is_admin(update):
        await update.effective_message.reply_text("⛔️ فقط ادمین‌ها به تنظیمات دسترسی دارند.")
        return
    await show(update, context)
