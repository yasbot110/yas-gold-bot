# Runtime settings — initial value from .env, changes persisted via /settings panel.
# Dev comments are English; bot-facing texts stay Persian.
from __future__ import annotations

from . import database as db
from .config import ADMIN_IDS, BUY_DEDUCTION_TOMAN, POST_CHANNEL, SELL_MARKUP_TOMAN


def _raw() -> dict:
    return db.get_state().get("settings", {})


def get(key: str):
    """Read a setting, applying .env defaults."""
    raw = _raw()
    if key == "admins":
        return list(raw.get("admins") or ADMIN_IDS)
    if key == "auto_enabled":
        return bool(raw.get("auto_enabled", True))
    if key == "thirty_min_enabled":
        return bool(raw.get("thirty_min_enabled", True))
    if key == "channel":
        return raw.get("channel") or POST_CHANNEL
    if key == "buy_deduction":
        # Amount subtracted from the displayed sell price to derive buy — default 100,000 Toman
        return int(raw.get("buy_deduction", BUY_DEDUCTION_TOMAN))
    if key == "sell_markup":
        # Amount added to the raw sell price to derive the displayed sell — default 0
        return int(raw.get("sell_markup", SELL_MARKUP_TOMAN))
    if key == "order_button_text":
        return raw.get("order_button_text", "")
    return raw.get(key)


def computed_buy(sell_toman: int | None) -> int | None:
    """Computed buy price in Toman: buy = displayed_sell − deduction.
    Where displayed_sell = raw_sell + sell_markup.
    Returns None if sell_toman is None."""
    displayed = displayed_sell(sell_toman)
    if displayed is None:
        return None
    return displayed - get("buy_deduction")


def displayed_sell(sell_toman: int | None) -> int | None:
    """Displayed sell price: raw sell + admin-configured markup (default 0).
    Returns None if sell_toman is None."""
    if sell_toman is None:
        return None
    return sell_toman + get("sell_markup")


def get_admins() -> list[int]:
    return get("admins")


def update(key: str, value) -> None:
    """Persist a setting change."""
    raw = _raw()
    raw[key] = value
    db.save_state("settings", raw)