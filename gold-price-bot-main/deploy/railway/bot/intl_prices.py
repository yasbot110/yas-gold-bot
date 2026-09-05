# International gold & silver spot prices via Yahoo Finance (yfinance).
# Dev comments & logs are English; bot-facing texts stay Persian.
# Symbols:
#   GC=F — Gold front-month futures (COMEX)  → $/troy ounce
#   SI=F — Silver front-month futures (COMEX) → $/troy ounce
from __future__ import annotations

import logging
from typing import Tuple

import yfinance as yf

log = logging.getLogger("intl")

GOLD_SYMBOL = "GC=F"
SILVER_SYMBOL = "SI=F"
REQUEST_TIMEOUT = 15  # seconds


def _last_price(symbol: str) -> float | None:
    """Fetch the latest live price for the given ticker; return None on failure.

    Uses intraday 1-minute bars (period=1d, interval=1m) so the value is the
    real-time tick (or the most recent 1-minute close). Falls back to fast_info
    when intraday data is unavailable (e.g. outside market hours, rate-limited)."""
    # ── Primary: 1-minute intraday bars (live tick during market hours) ──
    try:
        hist = yf.Ticker(symbol).history(period="1d", interval="1m", timeout=REQUEST_TIMEOUT)
        if not hist.empty:
            price = float(hist["Close"].iloc[-1])
            if price > 0:
                return price
    except Exception as exc:  # noqa: BLE001
        log.warning("yfinance %s intraday fetch failed: %s", symbol, exc)

    # ── Fallback: fast_info (price from summary detail, not bar history) ──
    try:
        ticker = yf.Ticker(symbol)
        fi = ticker.fast_info
        price = getattr(fi, "last_price", None)
        if price and price > 0:
            return float(price)
    except Exception as exc:  # noqa: BLE001
        log.warning("yfinance %s fast_info fetch failed: %s", symbol, exc)

    log.warning("%s: no live price available", symbol)
    return None


def fetch_gold_silver() -> Tuple[float | None, float | None]:
    """Return (gold_usd_oz, silver_usd_oz). Either may be None on failure."""
    return _last_price(GOLD_SYMBOL), _last_price(SILVER_SYMBOL)
