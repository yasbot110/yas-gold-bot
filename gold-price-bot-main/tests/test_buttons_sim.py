# -*- coding: utf-8 -*-
"""شبیه‌سازی کلیک تک‌تک دکمه‌های پنل — تشخیص اینکه آیا هندلر به همه جواب می‌دهد"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from telegram import InlineKeyboardButton, Update  # noqa: E402
from telegram.ext import ContextTypes  # noqa: E402

from bot.panel import admins_menu, main_menu  # noqa: E402


class FakeQuery:
    """جایگزین CallbackQuery برای تست بدون تلگرام واقعی"""

    def __init__(self, data: str, user_id: int):
        self.data = data
        self.answered = False
        self.edited = False
        self.alert = None
        self.from_user = type("U", (), {"id": user_id})()

        async def _reply(*a, **kw):
            return None

        self._message = type("M", (), {"reply_text": staticmethod(_reply)})()

    async def answer(self, text=None, show_alert=False):
        self.answered = True
        self.alert = text

    async def edit_message_text(self, *a, **kw):
        self.edited = True

    @property
    def effective_message(self):
        return None

    @property
    def message(self):
        return self._message


def make_update(data: str, user_id: int) -> tuple[Update, FakeQuery]:
    q = FakeQuery(data, user_id)
    upd = Update(update_id=1, callback_query=q)
    return upd, q


ALL_DATA = [b.callback_data for row in main_menu().inline_keyboard for b in row]
ALL_DATA += [b.callback_data for row in admins_menu().inline_keyboard for b in row]

ADMIN_ID = 306652923  # همان .env


async def main() -> None:
    from bot.panel import handle_callback  # noqa: E402

    results = []
    for data in ALL_DATA:
        upd, q = make_update(data, ADMIN_ID)
        ctx = type("C", (), {
            "user_data": {},
            "application": None,
            "bot": type("B", (), {"send_message": lambda self, **kw: None})(),
            "effective_chat": None,
        })()  # context ساختگی
        try:
            await handle_callback(upd, ctx)
        except Exception as exc:  # noqa: BLE001
            results.append((data, f"EXCEPTION: {exc!r}"))
            continue
        if q.answered or q.edited:
            results.append((data, "OK"))
        else:
            results.append((data, "SILENT — هیچ شاخه‌ای نگرفتش!"))

    print(f"{'callback_data':22} | نتیجه")
    print("-" * 55)
    bad = 0
    for data, status in results:
        flag = "" if status == "OK" else "  ← مشکل"
        if status != "OK":
            bad += 1
        print(f"{data:22} | {status}{flag}")
    print("-" * 55)
    print(f"جمع: {len(results)} دکمه، {bad} مورد بی‌پاسخ")
    sys.exit(1 if bad else 0)


asyncio.run(main())
