# تنظیمات اجرایی ربات — مقدار اولیه از .env، تغییرات از پنل /settings در دیتابیس ذخیره می‌شود
from __future__ import annotations

from . import database as db
from .config import ADMIN_IDS, BUY_DEDUCTION_TOMAN, POST_CHANNEL


def _raw() -> dict:
    return db.get_state().get("settings", {})


def get(key: str):
    """خواندن یک تنظیم با اعمال پیش‌فرض‌های .env"""
    raw = _raw()
    if key == "admins":
        return list(raw.get("admins") or ADMIN_IDS)
    if key == "auto_enabled":
        # انتشار خودکار: هر دقیقه چک، پست فقط با تغییر مقدار قیمت
        return bool(raw.get("auto_enabled", True))
    if key == "channel":
        return raw.get("channel") or POST_CHANNEL
    if key == "reports_enabled":
        return bool(raw.get("reports_enabled", True))
    if key == "buy_deduction":
        # مبلغ کسر از قیمت فروش برای محاسبه‌ی خرید — پیش‌فرض ۱۰۰٬۰۰۰ تومان
        return int(raw.get("buy_deduction", BUY_DEDUCTION_TOMAN))
    if key == "order_button_text":
        return raw.get("order_button_text", "")
    return raw.get(key)


def computed_buy(sell_toman: int | None) -> int | None:
    """قیمت خرید محاسبه‌شده به تومان: خرید = فروش − کسر"""
    if sell_toman is None:
        return None
    return sell_toman - get("buy_deduction")


def get_admins() -> list[int]:
    return get("admins")


def update(key: str, value) -> None:
    """ثبت یک تنظیم در دیتابیس"""
    raw = _raw()
    raw[key] = value
    db.save_state("settings", raw)
