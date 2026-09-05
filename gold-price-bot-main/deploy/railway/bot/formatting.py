# Message formatting — every text is HTML (Persian-safe) with RTL layout.
# Dev comments are English. Prices: Toman unit + English digits; buy = sell − deduction.
from html import escape

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from .jalali import format_jalali_date, format_jalali_time, format_jalali_datetime
from .persian import fa_digits, money
from . import settings as cfg

ZWNJ = "\u200c"
RLM = "\u202b"   # start right-to-left block
PDF = "\u202c"   # end right-to-left block

SOURCE_LINK = "https://t.me/MARKIZ_ARG"
SUPPORT_LINK = "https://t.me/GoldYas110_Support"   # contact & orders support chat

# Conversion factor: 1 mesghal (مثقال) = 4.3318492 grams (the precise factor used by
# MARKIZ_ARG and Iranian gold traders). Ali confirmed this value as the project standard
# on 1405/06/14 (it yields gram prices that match the channel's published per-gram line).
MESGHAL_TO_GRAM = 4.3318492


def mesghal_to_gram(mesghal_price: int | None) -> int | None:
    """Convert price per mesghal to price per gram (rounded)."""
    if mesghal_price is None:
        return None
    return round(mesghal_price / MESGHAL_TO_GRAM)


def _price_line(label: str, emoji: str, value_toman: int | None) -> str:
    if value_toman is None:
        return f"{emoji} {label}: —"
    # RLM...PDF wrap the number so "95,340,000 تومان" renders correctly in RTL
    return f"{emoji} {label}: {RLM}{money(value_toman)} تومان{PDF}"


def admin_report(state: dict, now_tehran) -> str:
    """On-demand report shown to an admin via /now. state carries only "sell";
    displayed sell = raw + markup; buy = displayed − deduction."""
    sell = state.get("sell")
    sell_raw = sell["value"] if sell else None
    sell_v = cfg.displayed_sell(sell_raw)
    buy_v = cfg.computed_buy(sell_raw)
    lines = [
        "<b>📊 گزارش لحظهای طلا (آبشده ۹۹۹)</b>",
        "",
        _price_line("خرید", "🔵", buy_v),
        _price_line("فروش", "🔴", sell_v),
    ]
    if buy_v and sell_v:
        diff = sell_v - buy_v  # equals the configured deduction
        lines.append(f"⚪️ اختلاف خرید/فروش: {RLM}{money(diff)} تومان{PDF}")
    markup = cfg.get("sell_markup")
    if markup and sell_raw:
        lines.append(
            f"➕ اضافه به فروش: {RLM}{money(markup)} تومان{PDF} "
            f"(خام: {RLM}{money(sell_raw)} تومان{PDF})"
        )
    lines += ["", f"🕒 {escape(format_jalali_datetime(now_tehran))}"]
    if sell and sell.get("msg_id"):
        lines.append(f"🆔 پیام مرجع: {fa_digits(sell['msg_id'])}")
    lines.append(f"📡 منبع: {escape(SOURCE_LINK)}")
    return "\n".join(lines)


def publish_post_1m(state: dict) -> str:
    """1-minute price post with mesghal and gram prices.
    displayed_sell = raw + sell_markup; buy = displayed − buy_deduction."""
    sell = state.get("sell")
    sell_raw = sell["value"] if sell else None
    sell_v = cfg.displayed_sell(sell_raw)
    buy_v = cfg.computed_buy(sell_raw)
    sell_gram = mesghal_to_gram(sell_v)
    buy_gram = mesghal_to_gram(buy_v)
    lines = [
        "نرخ رسمی طلای آبشده نقد فردایی:",
        "",
        _price_line("فروش", "🔴", sell_v),
        _price_line("خرید", "🟢", buy_v),
        "",
        _price_line("فروش گرم", "🟣", sell_gram),
        _price_line("خرید گرم", "🟡", buy_gram),
        "",
        "⌛اعتبار قیمت : 1 دقیقه",
        "",
        "📞تلفن :",
        "<blockquote>"
        "<a href='https://t.me/+989391118448'>09391118448</a>\n\n"
        "<a href='https://t.me/+989151118448'>09151118448</a>\n\n"
        "<a href='https://t.me/+989357990121'>09357990121</a>\n\n"
        "<a href='https://t.me/+989031118448'>09031118448</a>"
        "</blockquote>",
        "@GoldYas110 | گلد یاس ۱۱۰",
    ]
    return "\n".join(lines)


def publish_post_30m(state: dict, now_tehran, gold_usd: float | None = None, silver_usd: float | None = None) -> str:
    """30-minute greeting post with international gold & silver spot prices.
    Format:
      Line 1: سلام
      Line 2: ساعت 15:30 (English digits)
      Line 3: تاریخ 1405/06/03 (English digits)
      Line 4+: 🌍 انس طلا: $4,478.10
              🌙 انس نقره: $67.00
    Either USD price may be None (network failure) — line shows '—' in that case."""
    lines = [
        "سلام",
        f"ساعت {format_jalali_time(now_tehran)}",
        f"تاریخ {format_jalali_date(now_tehran)}",
    ]
    if gold_usd is not None:
        lines.append(f"🌍 انس طلا: {RLM}${gold_usd:,.2f}{PDF}")
    else:
        lines.append("🌍 انس طلا: —")
    if silver_usd is not None:
        lines.append(f"🌙 انس نقره: {RLM}${silver_usd:,.2f}{PDF}")
    else:
        lines.append("🌙 انس نقره: —")
    return "\n".join(lines)


def contact_keyboard(bot_username: str | None = None) -> InlineKeyboardMarkup:
    """Two buttons under channel posts: right "فروش به شما", left "خرید از شما" — both
    deep-link to the support chat (@GoldYas110_Support) where customers place orders.
    (Telegram lays inline buttons right-to-left, so the first button lands on the right.)"""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🔴 فروش به شما", url=SUPPORT_LINK),
                InlineKeyboardButton("🟢 خرید از شما", url=SUPPORT_LINK),
            ]
        ]
    )


def help_text() -> str:
    return "\n".join([
        "🤖 <b>راهنمای ربات قیمت طلا</b>",
        "",
        "/start — شروع و نمایش راهنما",
        "/now — دریافت فوری آخرین  قیمت",
        "/status — وضعیت سرویس و آخرین خطا",
        "/settings —  تنظیمات ",
        "/publish — ارسال دستی پست قیمت به کانال ",
        "/test30m — ارسال تستی پیام نیم ساعته (با قیمت انس طلا/نقره جهانی) به کانال",
        "/testclosing — ارسال تستی پیام پایان روز (همکاران عزیز...) به کانال",
        "/cancel — انصراف ",
    ])


def closing_text() -> str:
    """End-of-day closing message posted at 20:01 Tehran.
    This is the last bot post of the day, sent after the 1-min price posts
    have stopped (work window is 09:30–20:00).

    Phone numbers are clickable — each one deep-links to its own phone contact
    via Telegram t.me/+989... links. Uses the same `<blockquote><a>` pattern
    as publish_post_1m."""
    return "\n".join([
        "همکاران عزیز خسته نباشید.",
        "",
        "جهت معامله با شماره های زیر تماس حاصل فرمایید.",
        "",
        "<blockquote>"
        "<a href='https://t.me/+989391118448'>09391118448</a>\n\n"
        "<a href='https://t.me/+989151118448'>09151118448</a>\n\n"
        "<a href='https://t.me/+989357990121'>09357990121</a>\n\n"
        "<a href='https://t.me/+989031118448'>09031118448</a>"
        "</blockquote>",
        "",
        "@GoldYas110 | گلد یاس ۱۱۰",
    ])