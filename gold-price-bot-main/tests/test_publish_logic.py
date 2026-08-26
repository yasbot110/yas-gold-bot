# -*- coding: utf-8 -*-
"""تست منطق انتشار — هر دقیقه چک، پست فقط با تغییر «فروش»، فقط در ساعات کاری"""
import asyncio
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot import database as db
from bot.bot import maybe_auto_publish
from bot.config import TEHRAN
from bot.formatting import publish_post

SENT = []


class FakeBot:
    username = "yas110gold_bot"

    async def send_message(self, chat_id, text=None, **kw):
        SENT.append((chat_id, text))
        print(f"  → ارسال به {chat_id}: {text.splitlines()[0]}")


class Ctx:
    bot = FakeBot()
    bot_data = {}


async def main():
    from bot import settings as cfg

    # آماده‌سازی: کانال تنظیم و حالت خودکار روشن؛ کسر پیش‌فرض ۱۰۰٬۰۰۰ تومان
    db.save_state("post_channel", {"value": "@test_channel"})
    cfg.update("channel", "@test_channel")
    cfg.update("auto_enabled", True)
    assert cfg.get("buy_deduction") == 100_000, cfg.get("buy_deduction")
    print(f"✅ کسر خرید پیش‌فرض: {cfg.get('buy_deduction'):,} تومان\n")

    # ساعت داخل بازه‌ی کاری (۱۲:۰۰) و بیرون آن (۲۱:۰۰)
    in_hours = datetime(2026, 8, 26, 12, 0, tzinfo=TEHRAN)
    off_hours = datetime(2026, 8, 26, 21, 0, tzinfo=TEHRAN)

    latest_same = {"sell": {"value": 95_340_000, "msg_id": 10, "time": ""}}

    # ── سناریوی ۱: بدون تغییر → هیچ پستی نمی‌رود (بدون اسپم)
    SENT.clear()
    await maybe_auto_publish(Ctx(), latest_same, in_hours, changed_kinds=set())
    assert len(SENT) == 0, f"بدون تغییر نباید پست می‌رفت؛ رفت: {[s[1][:40] for s in SENT]}"
    print("✅ فروش ثابت → هیچ پستی نمی‌رود\n")

    # ── سناریوی ۲: تغییر فروش → پست فوری؛ خرید = فروش − ۱۰۰٬۰۰۰ محاسبه می‌شود
    latest_changed = {"sell": {"value": 95_500_000, "msg_id": 11, "time": ""}}
    SENT.clear()
    await maybe_auto_publish(Ctx(), latest_changed, in_hours, changed_kinds={"sell"})
    assert len(SENT) == 1, f"پست باید می‌رفت؛ رفت: {[s[1][:60] for s in SENT]}"
    body = SENT[0][1]
    assert "95,500,000 تومان" in body, body          # فروش تازه (اعداد انگلیسی + تومان)
    assert "95,400,000 تومان" in body, body          # خرید = ۹۵٬۵۰۰٬۰۰۰ − ۱۰۰٬۰۰۰
    assert "ریال" not in body, "واحد نباید ریال باشد"
    print("✅ تغییر فروش → پست با خریدِ محاسبه‌شده (تومان، اعداد انگلیسی)\n")
    print(body, "\n")

    # ── سناریوی ۳: پیام تازه با همان مقدار قبلی → پست اضافه نمی‌رود
    SENT.clear()
    await maybe_auto_publish(Ctx(), latest_changed, in_hours, changed_kinds=set())
    assert len(SENT) == 0
    print("✅ پیام مرجع جدید ولی مقدار تکراری → پست اضافه نمی‌رود\n")

    # ── سناریوی ۴: بیرون ساعات کاری → حتی با تغییر هم هیچ
    SENT.clear()
    await maybe_auto_publish(Ctx(), latest_same, off_hours, changed_kinds={"sell"})
    assert len(SENT) == 0
    print("✅ ساعت ۲۱:۰۰ → خارج از ساعات کاری، بدون پست\n")

    # مرزها: ۹:۲۹ نه، ۹:۳۰ بله، ۲۰:۰۰ نه
    assert not __import__("bot.config", fromlist=["x"]).within_working_hours(
        datetime(2026, 8, 26, 9, 29, tzinfo=TEHRAN))
    assert __import__("bot.config", fromlist=["x"]).within_working_hours(
        datetime(2026, 8, 26, 9, 30, tzinfo=TEHRAN))
    assert not __import__("bot.config", fromlist=["x"]).within_working_hours(
        datetime(2026, 8, 26, 20, 0, tzinfo=TEHRAN))
    print("✅ مرزهای ساعت کاری: ۹:۲۹ ✗ · ۹:۳۰ ✓ · ۲۰:۰۰ ✗\n")

    # ── سناریوی ۵: حالت خودکار خاموش → هیچ
    cfg.update("auto_enabled", False)
    SENT.clear()
    await maybe_auto_publish(Ctx(), latest_same, in_hours, changed_kinds={"sell"})
    assert len(SENT) == 0
    print("✅ حالت خودکار خاموش → هیچ پستی نمی‌رود\n")

    cfg.update("auto_enabled", True)

    # ── سناریوی ۶: کانال تنظیم نشده → بدون خطا
    cfg.update("channel", "")
    SENT.clear()
    await maybe_auto_publish(Ctx(), latest_same, in_hours, changed_kinds={"sell"})
    assert len(SENT) == 0
    print("✅ کانال خالی → بدون پست و بدون خطا\n")
    cfg.update("channel", "@test_channel")

    # ── سناریوی ۷: فرمت پست + دکمه‌ها
    txt = publish_post(latest_same, in_hours)
    assert "قیمت لحظه‌ای" in txt and "تومان" in txt and "ریال" not in txt
    from bot.formatting import contact_keyboard
    labels = [b.text for b in contact_keyboard("yas110gold_bot").inline_keyboard[0]]
    assert labels == ["🔴 فروش به ما", "🟢 خرید از ما"], labels
    print("✅ فرمت پست (تومان) + دو دکمه‌ی جدید درست است")

    # ── سناریوی ۸: تغییر کسر دستی → خرید جدید در پست بعدی اعمال می‌شود
    cfg.update("buy_deduction", 250_000)
    SENT.clear()
    await maybe_auto_publish(
        Ctx(), {"sell": {"value": 95_600_000, "msg_id": 12, "time": ""}},
        in_hours, changed_kinds={"sell"},
    )
    assert len(SENT) == 1 and "95,350,000 تومان" in SENT[0][1], \
        f"خرید باید ۹۵٬۳۵۰٬۰۰۰ می‌بود: {SENT[0][1] if SENT else 'هیچ'}"
    cfg.update("buy_deduction", 100_000)   # برگرداندن به پیش‌فرض برای تست‌های بعدی
    print("✅ تغییر دستی کسر (۲۵۰٬۰۰۰) → خرید = ۹۵٬۶۰۰٬۰۰۰ − ۲۵۰٬۰۰۰ = ۹۵٬۳۵۰٬۰۰۰")


if __name__ == "__main__":
    db.init_db()
    asyncio.run(main())
    print("\n🎉 تست منطق انتشار پاس شد")
