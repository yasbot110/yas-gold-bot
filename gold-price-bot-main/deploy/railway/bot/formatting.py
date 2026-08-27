# Message formatting — every text is HTML (Persian-safe) with RTL layout.
# Dev comments are English. Prices: Toman unit + English digits; buy = sell − deduction.
from html import escape

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from .jalali import format_jalali_datetime
from .persian import fa_digits, money
from . import settings as cfg

ZWNJ = "\u200c"
RLM = "\u202b"   # start right-to-left block
PDF = "\u202c"   # end right-to-left block

SOURCE_LINK = "https://t.me/MARKIZ_ARG"


def _price_line(label: str, emoji: str, value_toman: int | None) -> str:
    if value_toman is None:
        return f"{emoji} {label}: —"
    # RLM...PDF wrap the number so "95,340,000 تومان" renders correctly in RTL
    return f"{emoji} {label}: {RLM}{money(value_toman)} تومان{PDF}"


def admin_report(state: dict, now_tehran) -> str:
    """On-demand report shown to an admin via /now. state carries only "sell";
    buy is computed."""
    sell = state.get("sell")
    sell_v = sell["value"] if sell else None
    buy_v = cfg.computed_buy(sell_v)
    lines = [
        "<b>📊 گزارش لحظهای طلا (آبشده ۹۹۹)</b>",
        "",
        _price_line("خرید", "🔵", buy_v),
        _price_line("فروش", "🔴", sell_v),
    ]
    if buy_v and sell_v:
        diff = sell_v - buy_v  # equals the configured deduction
        lines.append(f"⚪️ اختلاف خرید/فروش: {RLM}{money(diff)} تومان{PDF}")
    lines += ["", f"🕒 {escape(format_jalali_datetime(now_tehran))}"]
    if sell and sell.get("msg_id"):
        lines.append(f"🆔 پیام مرجع: {fa_digits(sell['msg_id'])}")
    lines.append(f"📡 منبع: {escape(SOURCE_LINK)}")
    return "\n".join(lines)


def publish_post(state: dict, now_tehran) -> str:
    """Channel post — exactly the previous layout; only buy is derived from sell."""
    sell = state.get("sell")
    sell_v = sell["value"] if sell else None
    buy_v = cfg.computed_buy(sell_v)
    sell_gram = round(sell_v / 4.3318492) if sell_v else 0
    buy_gram = round(buy_v / 4.3318492) if buy_v else 0
    lines = [
        "نرخ رسمی طلای آبشده نقد فردایی:",
        "",
        _price_line("فروش", "🔴", sell_v),
        _price_line("خرید", "🟢", buy_v),
        "",
        _price_line("فروش گرم", "🟣", sell_gram ),
        _price_line("خرید گرم", "🟡", buy_gram ),
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


def contact_keyboard(bot_username: str | None) -> InlineKeyboardMarkup:
    """Two buttons under channel posts: right "فروش به ما", left "خرید از ما" — both
    deep-link to the bot. (Telegram lays inline buttons right-to-left, so the first
    button lands on the right.)"""
    url = f"https://t.me/{bot_username}" if bot_username else SOURCE_LINK
    return InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("🔴 فروش به ما", url=url),
            InlineKeyboardButton("🟢 خرید از ما", url=url),
        ]]
    )


def help_text() -> str:
    return "\n".join([
        "🤖 <b>راهنمای ربات قیمت طلا</b>",
        "",
        "/start — شروع و نمایش راهنما",
        "/now — دریافت فوری آخرین گزارش قیمت",
        "/status — وضعیت سرویس و آخرین خطا",
        "/settings — ⚙️ پنل تنظیمات (تنظیم کانال انتشار، حالت خودکار، کسر خرید، ادمینها)",
        "/publish — ارسال دستی پست قیمت به کانال انتشار",
        "/cancel — انصراف از ورودی فعال پنل تنظیمات",
        "",
        "⚙️ انتشار خودکار: هر دقیقه قیمت چک میشود؛ فقط با تغییر «فروش» پست جدید میرود.",
        "🕐 ساعات کاری انتشار: ۹:۳۰ تا ۲۰:۰۰",
        "i️ واحد همهی قیمتها تومان است؛ خرید = فروش − کسرِ تنظیمشده.",
    ])
