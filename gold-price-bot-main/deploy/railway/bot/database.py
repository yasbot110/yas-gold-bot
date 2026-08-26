# ذخیره‌سازی ساده روی SQLite — آخرین وضعیت قیمت‌ها + تاریخچه برای نمودارهای آینده
import json
import sqlite3
from datetime import datetime, timezone

from .config import DB_PATH

# عملیات‌ها سبک‌اند (چند میلی‌ثانیه)؛ فراخوانی مستقیم داخل event-loop اشکالی ندارد.


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _conn() as c:
        c.execute(
            "CREATE TABLE IF NOT EXISTS state ("
            " key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        c.execute(
            "CREATE TABLE IF NOT EXISTS prices ("
            " id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " kind TEXT NOT NULL,"           # buy | sell
            " value_rial INTEGER NOT NULL,"
            " msg_id INTEGER,"
            " created_at TEXT NOT NULL)"      # UTC iso
        )


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ── state (کلید/مقدار JSON) ────────────────────────────────────────────
def get_state() -> dict:
    with _conn() as c:
        rows = c.execute("SELECT key, value FROM state").fetchall()
    return {r["key"]: json.loads(r["value"]) for r in rows}


def save_state(key: str, value) -> None:
    with _conn() as c:
        c.execute(
            "INSERT INTO state(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, json.dumps(value, ensure_ascii=False)),
        )


# ── تاریخچه‌ی قیمت ─────────────────────────────────────────────────────
def insert_price(kind: str, value_rial: int, msg_id: int) -> None:
    with _conn() as c:
        c.execute(
            "INSERT INTO prices(kind, value_rial, msg_id, created_at) VALUES(?,?,?,?)",
            (kind, value_rial, msg_id, utc_now_iso()),
        )


def count_prices() -> int:
    with _conn() as c:
        return c.execute("SELECT COUNT(*) AS n FROM prices").fetchone()["n"]
