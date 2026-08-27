# Bot configuration — values read from the .env file (Railway edition).
# Dev comments are English; bot-facing texts stay Persian.
import os
from pathlib import Path
from zoneinfo import ZoneInfo

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    """Lightweight .env loader — no python-dotenv dependency."""
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

# ── Required ────────────────────────────────────────────────────────────
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "").strip()
# Multiple admins? Separate with commas:  ADMIN_IDS=111111,222222
ADMIN_IDS: list[int] = [
    int(x) for x in os.getenv("ADMIN_IDS", "").replace(",", " ").split() if x.strip()
]

# ── Optional (sensible defaults) ────────────────────────────────────────
SOURCE_CHANNEL: str = os.getenv("SOURCE_CHANNEL", "MARKIZ_ARG")   # reference price channel
POLL_INTERVAL: int = int(os.getenv("POLL_INTERVAL", "60"))        # seconds
POST_CHANNEL: str = os.getenv("POST_CHANNEL", "").strip()         # default channel to publish to

TEHRAN = ZoneInfo("Asia/Tehran")
# Railway: point DATA_DIR at a Volume so the DB survives redeploys
DATA_DIR = Path(os.getenv("DATA_DIR", str(BASE_DIR / "data")))
DB_PATH = DATA_DIR / "bot.db"
LOG_PATH = DATA_DIR / "bot.log"

# ── Publishing business hours (Tehran time) ─────────────────────────────
# The bot posts to the channel only inside this window; silent outside it.
WORK_START_MIN = int(os.getenv("WORK_START_MIN", str(9 * 60 + 30)))   # 09:30
WORK_END_MIN = int(os.getenv("WORK_END_MIN", str(20 * 60)))           # 20:00

# ── Computed buy price ──────────────────────────────────────────────────
# Only the SELL price is taken from the reference channel; buy = sell − deduction.
# Default is 100,000 Toman; changed ONLY manually (settings panel / KV).
BUY_DEDUCTION_TOMAN: int = int(os.getenv("BUY_DEDUCTION_TOMAN", "100000"))


def within_working_hours(dt) -> bool:
    """True if dt is inside the 09:30–20:00 Tehran business window."""
    m = dt.hour * 60 + dt.minute
    return WORK_START_MIN <= m < WORK_END_MIN


# ── Auto-publish to the channel ─────────────────────────────────────────
# The reference channel is checked every minute; if the value changed vs the
# previous scan a new post is sent to the publish channel. Enabled/disabled and
# its destination are controlled from the /settings panel.


def validate() -> list[str]:
    """Return configuration errors; empty means everything is fine."""
    errors = []
    if not BOT_TOKEN:
        errors.append("BOT_TOKEN در فایل .env تنظیم نشده است.")
    if not ADMIN_IDS:
        errors.append("ADMIN_IDS در فایل .env تنظیم نشده است (آیدی عددی ادمینها).")
    return errors