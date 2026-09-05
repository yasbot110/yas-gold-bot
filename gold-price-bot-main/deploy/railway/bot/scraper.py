# Scrape prices from the reference channel via its web preview t.me/s/<channel>.
# No Telegram API_ID needed; MARKIZ_ARG preview is public (live-tested 1405/06/02).
# Dev comments are English.
from __future__ import annotations

import asyncio
import html as html_mod
import logging
import re
from dataclasses import dataclass

import httpx

log = logging.getLogger("scraper")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    )
}

RE_MSG_TEXT = re.compile(r"tgme_widget_message_text[^>]*>([\s\S]*?)</div>")
RE_TIME = re.compile(r'<time datetime="([^"]+)"')
RE_ID = re.compile(r'data-post="[^/]*/(\d+)"')


@dataclass
class Message:
    id: int
    time_iso: str
    text: str


# ── Parse the Markiz channel message text ───────────────────────────────
# Sample (current format, 1405/06/14):
#   «🔴 قیمت فروش آبشده نقد فردا: \n\n102360\n\n☎️ تلفن:...»
#   – number is now raw Toman (no «ریال» suffix, 3 trailing zeros dropped),
#     digits are English.
# Sample (legacy format):
#   «🔴 قیمت فروش آبشده نقد فردا: \n\n954٬000٬000 ریال»
# Requirements (Ali):
#   1. MUST contain «فروش» AND «آبشده» — so a «خرید» line never matches.
#   2. Either order of the two keywords is OK: «قیمت فروش آبشده» or
#      «قیمت آبشده فروش» — only the channel uses the first today but the
#      pattern is loose on purpose.
#   3. Window is bounded by the next «☎» / «تلفن» line (or end-of-text), so
#      phone numbers or «اعتبار قیمت: 1 دقیقه» can never be mistaken for the
#      price even if the length-bounded match would otherwise over-greedy.
#   4. Digits may be Persian (۰-۹) or English (0-9); separators may be
#      Persian «٬», ASCII «,», dot «.» or whitespace.
#   5. Returned value is Toman (raw). Legacy «ریال» suffix is detected and
#     ÷10 applied to stay backward-compatible with old messages.
RE_SELL = re.compile(
    r"قیمت\s+"                              # «قیمت »
    r"(?=.*?فروش)(?=.*?آبشده)"               # lookaheads: must contain BOTH words later
    r"(?:[^.\n]*?)"                          # any non-dot, non-newline filler (lets the two words reorder)
    r":"                                     # the colon that ends the label line
    r"\s*\n?\s*"                             # newline / spaces after the colon
    r"([\d۰-۹.,٬\s]+?)"                      # CAPTURE 1 — the price (digits, Persian/English, separators)
    r"(?=\s*(?:☎|تلفن|⏰|اعتبار|ریال|$))"     # stop before phone / validity / ریال / end — non-greedy boundary
)


def _to_int(raw: str) -> int | None:
    """«۹۵۲٬۱۰۰٬۰۰۰» or «952,100,000» or «102360» → 952100000 / 102360.
    Accepts Persian/English digits and any of «, . ٬ whitespace» as separators."""
    s = raw.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))
    s = re.sub(r"[.,\s٬]", "", s)
    return int(s) if s.isdigit() else None


def parse_message(text: str) -> tuple[str, int] | None:
    """If the message carries a SELL price → ('sell', value in Toman per mesghal) else None.
    Buy is no longer read from the channel; it is computed in the bot.

    Scale history (channel drift):
      • Old format  : «قیمت فروش آبشده ... ریال» → value is in Rial → ÷10 → Toman per mesghal.
      • Current     : English digits, no «ریال», 3 trailing zeros dropped (raw Toman, but
                      presented in a 6-digit shorthand that the channel chose to save
                      space) → multiply by 1000 to recover the full 9-digit market figure.
    Every downstream consumer (compute_buy, displayed_sell, mesghal_to_gram) expects the
    full 9-digit Toman-per-mesghal value, so the scale must be normalised HERE — single
    source of truth, every caller fixed at once."""
    m = RE_SELL.search(text)
    if not m:
        return None
    raw = m.group(1)
    # Look ahead from the match end to detect the legacy «ریال» suffix.
    rest = text[m.end():m.end() + 12]  # tiny window, enough for «\nریال» / « ریال»
    value = _to_int(raw)
    if value is None:
        return None
    if "ریال" in rest:
        value //= 10              # legacy: Rial → Toman (drop one zero)
    else:
        value *= 1000             # current: 6-digit shorthand → 9-digit market price
    return "sell", value


def _clean_html(fragment: str) -> str:
    t = re.sub(r"<br\s*/?>", "\n", fragment)
    t = re.sub(r"<[^>]+>", "", t)
    return html_mod.unescape(t).strip()


async def fetch_messages(channel: str, client: httpx.AsyncClient) -> list[Message] | None:
    """Return the channel preview page messages; network error → None."""
    url = f"https://t.me/s/{channel}"
    try:
        resp = await client.get(url, headers=HEADERS, timeout=20, follow_redirects=True)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        log.warning("error fetching %s : %s", url, exc)
        return None

    raw = resp.text
    texts = [_clean_html(x) for x in RE_MSG_TEXT.findall(raw)]
    times = RE_TIME.findall(raw)
    ids = RE_ID.findall(raw)

    out: list[Message] = []
    for i, txt in enumerate(texts):
        mid = int(ids[i]) if i < len(ids) and ids[i].isdigit() else 0
        tm = times[i] if i < len(times) else ""
        out.append(Message(id=mid, time_iso=tm, text=txt))
    out.sort(key=lambda m: m.id)
    return out