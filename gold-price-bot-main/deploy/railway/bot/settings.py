# Runtime settings — initial value from .env, changes persisted via /settings panel.
# Dev comments are English; bot-facing texts stay Persian.
from __future__ import annotations

from . import database as db
from .config import ADMIN_IDS, BUY_DEDUCTION_TOMAN, POST_CHANNEL


def _raw() -> dict:
    return db.get_state().get("settings", {})


def get(key: str):
    """Read a setting, applying .env defaults."""
    raw = _raw()
    if key == "admins":
        return list(raw.get("admins") or ADMIN_IDS)
    if key == "auto_enabled":
        return bool(raw.get("auto_enabled", True))
    if key == "channel":
        return raw.get("channel") or POST_CHANNEL
    if key == "buy_deduction":
        # Amount subtracted from the sell price to derive buy — default 100000 Toman
        return int(raw.get("buy_deduction", BUY_DEDUCTION_TOMAN))
    if key == "order_button_text":
        return raw.get("order_button_text", "")
    return raw.get(key)


def computed_buy(sell_toman: int | None) -> int | None:
    """Computed buy price in Toman: buy = sell − deduction."""
    if sell_toman is None:
        return None
    return sell_toman - get("buy_deduction")


def get_admins() -> list[int]:
    return get("admins")


def update(key: str, value) -> None:
    """Persist a setting change."""
    raw = _raw()
    raw[key] = value
    db.save_state("settings", raw)