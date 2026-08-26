# استخراج قیمت از کانال مرجع از طریق پیش‌نمایش وب t.me/s/<channel>
# نیازی به API_ID تلگرام ندارد؛ کانال MARKIZ_ARG پیش‌نمایشش فعال است (تست زنده: ۱۴۰۵/۰۶/۰۲)
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


# ── پارس متن پیام‌های کانال مارکیز ─────────────────────────────────────
# نمونه:  «🔴 قیمت فروش آبشده نقد فردا: \n\n954٬000٬000 ریال»
# طبق تصمیم علی فقط «فروش» از کانال گرفته می‌شود؛ «خرید» در ربات محاسبه می‌شود
# (خرید = فروش − کسر). کانال به «ریال» می‌گوید ولی همه‌جا با «تومان» کار می‌کنیم
# → همان لحظه ÷۱۰ می‌شود.
RE_SELL = re.compile(r"قیمت\s+فروش\s+آبشده[^\n:]*:\s*\n?\s*([\d۰-۹.,٬\s]+?)\s*ریال")


def _to_int(raw: str) -> int | None:
    """«۹۵۲٬۱۰۰٬۰۰۰» یا «952,100,000» → 952100000"""
    s = raw.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))
    s = re.sub(r"[.,\s٬]", "", s)
    return int(s) if s.isdigit() else None


def parse_message(text: str) -> tuple[str, int] | None:
    """اگر پیام حامل «قیمت فروش» بود → ('sell', مقدار به تومان) وگرنه None.
    قیمت خرید دیگر از کانال خوانده نمی‌شود؛ در ربات محاسبه می‌شود."""
    m = RE_SELL.search(text)
    if m:
        value_rial = _to_int(m.group(1))
        if value_rial:
            return "sell", value_rial // 10   # ریال → تومان
    return None


def _clean_html(fragment: str) -> str:
    t = re.sub(r"<br\s*/?>", "\n", fragment)
    t = re.sub(r"<[^>]+>", "", t)
    return html_mod.unescape(t).strip()


async def fetch_messages(channel: str, client: httpx.AsyncClient) -> list[Message] | None:
    """پیام‌های صفحه‌ی پیش‌نمایش کانال را برمی‌گرداند؛ خطای شبکه → None"""
    url = f"https://t.me/s/{channel}"
    try:
        resp = await client.get(url, headers=HEADERS, timeout=20, follow_redirects=True)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        log.warning("خطای دریافت %s : %s", url, exc)
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
