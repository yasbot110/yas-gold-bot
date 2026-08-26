# تنظیمات ربات — مقادیر از فایل .env خوانده می‌شود
import os
from pathlib import Path
from zoneinfo import ZoneInfo

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    """لودر سبک فایل .env — بدون نیاز به کتابخانه‌ی python-dotenv"""
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


_load_dotenv()

# ── اجباری ─────────────────────────────────────────────────────────────
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "").strip()
# چند ادمین؟ با کاما جدا کن:  ADMIN_IDS=111111,222222
ADMIN_IDS: list[int] = [
    int(x) for x in os.getenv("ADMIN_IDS", "").replace(",", " ").split() if x.strip()
]

# ── اختیاری (پیش‌فرض منطقی دارند) ──────────────────────────────────────
SOURCE_CHANNEL: str = os.getenv("SOURCE_CHANNEL", "MARKIZ_ARG")   # کانال مرجع قیمت
POLL_INTERVAL: int = int(os.getenv("POLL_INTERVAL", "60"))        # ثانیه
POST_CHANNEL: str = os.getenv("POST_CHANNEL", "").strip()         # کانال پیش‌فرض برای انتشار

TEHRAN = ZoneInfo("Asia/Tehran")
DB_PATH = BASE_DIR / "data" / "bot.db"
LOG_PATH = BASE_DIR / "data" / "bot.log"

# ── ساعات کاری انتشار (به وقت تهران) ───────────────────────────────────
# ربات فقط در این بازه برای کانال پست می‌فرستد؛ بیرون از بازه سکوت.
WORK_START_MIN = int(os.getenv("WORK_START_MIN", str(9 * 60 + 30)))   # 09:30
WORK_END_MIN = int(os.getenv("WORK_END_MIN", str(20 * 60)))           # 20:00

# ── قیمت خرید محاسبه‌شده ────────────────────────────────────────────────
# فقط «فروش» از کانال مرجع گرفته می‌شود؛ خرید = فروش − BUY_DEDUCTION_TOMAN.
# پیش‌فرض ۱۰۰٬۰۰۰ تومان؛ تغییرش فقط دستی (پنل تنظیمات / KV) انجام می‌شود.
BUY_DEDUCTION_TOMAN: int = int(os.getenv("BUY_DEDUCTION_TOMAN", "100000"))


def within_working_hours(dt) -> bool:
    """True اگر dt داخل ساعات کاری ۹:۳۰ تا ۲۰:۰۰ تهران باشد"""
    m = dt.hour * 60 + dt.minute
    return WORK_START_MIN <= m < WORK_END_MIN

# ── انتشار خودکار در کانال ─────────────────────────────────────────────
# هر دقیقه کانال مرجع چک می‌شود؛ اگر مقدار خرید/فروش نسبت به اسکن قبل عوض
# شده باشد، پست جدید در کانال انتشار فرستاده می‌شود. خاموش/روشن و مقصدش
# از پنل تنظیمات (/settings) کنترل می‌شود.


def validate() -> list[str]:
    """خطاهای پیکربندی را برمی‌گرداند؛ خالی یعنی همه‌چیز اوکی است."""
    errors = []
    if not BOT_TOKEN:
        errors.append("BOT_TOKEN در فایل .env تنظیم نشده است.")
    if not ADMIN_IDS:
        errors.append("ADMIN_IDS در فایل .env تنظیم نشده است (آی‌دی عددی ادمین‌ها).")
    return errors
