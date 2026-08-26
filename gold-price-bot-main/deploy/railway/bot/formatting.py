# قالب‌بندی پیام‌ها — همه‌ی متن‌ها HTML (ایمن برای فارسی) با چیدمان RTL
# قیمت‌ها: واحد تومان + ارقام انگلیسی؛ خرید = فروش − کسر (محاسبه‌ای)
from html import escape

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from .jalali import format_jalali_datetime
from .persian import fa_digits, money
from . import settings as cfg

ZWNJ = "\u200c"
RLM = "\u202b"   # شروع بلاک راست‌به‌چپ
PDF = "\u202c"   # پایان بلاک

SOURCE_LINK = "https://t.me/MARKIZ_ARG"


def _price_line(label: str, emoji: str, value_toman: int | None) -> str:
    if value_toman is None:
        return f"{emoji} {label}: —"
    # RLM…PDF دور عدد می‌گذاریم تا «95,340,000 تومان» درست نمایش داده شود
    return f"{emoji} {label}: {RLM}{money(value_toman)} تومان{PDF}"


def admin_report(state: dict, now_tehran) -> str:
    """گزارش لحظه‌ای که به ادمین می‌رود. state فقط «sell» دارد؛ خرید محاسبه می‌شود."""
    sell = state.get("sell")
    sell_v = sell["value"] if sell else None
    buy_v = cfg.computed_buy(sell_v)
    lines = [
        "<b>📊 گزارش لحظه‌ای طلا (آبشده ۹۹۹)</b>",
        "",
        _price_line("خرید", "🔵", buy_v),
        _price_line("فروش", "🔴", sell_v),
    ]
    if buy_v and sell_v:
        diff = sell_v - buy_v  # همانی است که کسر گذاشتیم
        lines.append(f"⚪️ اختلاف خرید/فروش: {RLM}{money(diff)} تومان{PDF}")
    lines += ["", f"🕒 {escape(format_jalali_datetime(now_tehran))}"]
    if sell and sell.get("msg_id"):
        lines.append(f"🆔 پیام مرجع: {fa_digits(sell['msg_id'])}")
    lines.append(f"📡 منبع: {escape(SOURCE_LINK)}")
    return "\n".join(lines)


def change_alert(kind: str, new_value: int, old_value: int, now_tehran) -> str:
    """اعلان تغییر «فروش» نسبت به آخرین مقدار ثبت‌شده (خرید هم محاسبه می‌شود)."""
    label = "فروش" if kind == "sell" else kind
    emoji = "🔴" if kind == "sell" else "🔵"
    diff = new_value - old_value
    arrow = "⬆️" if diff > 0 else "⬇️"
    sign = "+" if diff > 0 else "−"
    new_buy = cfg.computed_buy(new_value)
    old_buy = cfg.computed_buy(old_value)
    return "\n".join([
        f"{arrow} <b>تغییر قیمت {label} آبشده</b>",
        "",
        _price_line("جدید", emoji, new_value),
        f"▫️ قبلی: {RLM}{money(old_value)} تومان{PDF}",
        f"▫️ تغییر: {RLM}{sign}{money(abs(diff))} تومان{PDF}",
        "",
        _price_line("خرید (محاسبه‌ای)", "🔵", new_buy),
        f"▫️ قبلی: {RLM}{money(old_buy) if old_buy is not None else '—'} تومان{PDF}",
        "",
        f"🕒 {escape(format_jalali_datetime(now_tehran))}",
    ])


def publish_post(state: dict, now_tehran) -> str:
    """پست کانال — دقیقاً همان فرمت قبلی؛ فقط خرید از فروش محاسبه می‌شود."""
    sell = state.get("sell")
    sell_v = sell["value"] if sell else None
    buy_v = cfg.computed_buy(sell_v)
    lines = [
        "💠 <b>قیمت لحظه‌ای طلای آبشده</b> 💠",
        "",
        _price_line("خرید", "🔵", buy_v),
        _price_line("فروش", "🔴", sell_v),
        "",
        f"🕒 {escape(format_jalali_datetime(now_tehran))}",
    ]
    return "\n".join(lines)


def contact_keyboard(bot_username: str | None) -> InlineKeyboardMarkup:
    """دو دکمه زیر پست کانال: راست «فروش به ما»، چپ «خرید از ما» — هر دو deep-link به ربات.
    (تلگرام دکمه‌های inline را راست‌به‌چپ چینش می‌کند؛ اولین دکمه در سمت راست می‌افتد.)"""
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
        "/settings — ⚙️ پنل تنظیمات (تنظیم کانال انتشار، حالت خودکار، کسر خرید، ادمین‌ها)",
        "/publish — ارسال دستی پست قیمت به کانال انتشار",
        "/cancel — انصراف از ورودی فعال پنل تنظیمات",
        "",
        "⚙️ انتشار خودکار: هر دقیقه قیمت چک می‌شود؛ فقط با تغییر «فروش» پست جدید می‌رود.",
        "🕐 ساعات کاری انتشار: ۹:۳۰ تا ۲۰:۰۰",
        "ℹ️ واحد همه‌ی قیمت‌ها تومان است؛ خرید = فروش − کسرِ تنظیم‌شده.",
    ])
