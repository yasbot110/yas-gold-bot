# -*- coding: utf-8 -*-
"""تست واحد بدون توکن: پارسر + فرمت پیام + دیتابیس + تاریخ جلالی"""
import asyncio
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx

from bot.database import count_prices, get_state, init_db, insert_price, save_state
from bot.formatting import admin_report, change_alert, contact_keyboard, publish_post
from bot.jalali import format_jalali_datetime, gregorian_to_jalali
from bot.scraper import _to_int, fetch_messages, parse_message


def test_jalali():
    # 2026-08-25 = 3 شهریور 1405 (سه‌شنبه)
    assert gregorian_to_jalali(2026, 8, 25) == (1405, 6, 3)
    dt = datetime(2026, 8, 25, 20, 4, tzinfo=ZoneInfo("Asia/Tehran"))
    s = format_jalali_datetime(dt)
    print("jalali:", s)
    assert "شهریور" in s and "۱۴۰۵" in s and "سه‌شنبه" in s
    print("✅ jalali OK")


def test_to_int():
    assert _to_int("952٬100٬000") == 952100000
    assert _to_int("۹۵۲٬۱۰۰٬۰۰۰") == 952100000
    assert _to_int("952,100,000") == 952100000
    print("✅ to_int OK")


def test_parse_message_sell_only_toman():
    """پارسر فقط فروش می‌گیرد و ریال→تومان می‌کند"""
    buy_text = "🔵 قیمت خرید آبشده نقد فردا: \n\n952٬100٬000 ریال"
    sell_text = "🔴 قیمت فروش آبشده نقد فردا: \n\n9,540٬000٬00 ریال"  # عمداً به‌هم‌ریخته نباشد؛ پایین درستش را داریم
    sell_ok = "🔴 قیمت فروش آبشده نقد فردا: \n\n954٬000٬000 ریال"
    assert parse_message(buy_text) is None            # دیگر خرید نمی‌گیریم
    assert parse_message(sell_ok) == ("sell", 95_400_000)   # ۹۵۴٬۰۰۰٬۰۰۰ ریال = ۹۵٬۴۰۰٬۰۰۰ تومان
    assert parse_message("همکاران گرامی خسته نباشید") is None
    print("✅ parse_message (فقط فروش، خروجی تومان) OK")


async def test_live_channel():
    """دریافت زنده از کانال مرجع + تولید گزارش"""
    async with httpx.AsyncClient(timeout=20) as client:
        msgs = await fetch_messages("MARKIZ_ARG", client)
    assert msgs, "هیچ پیامی از کانال گرفته نشد"
    latest = {}
    for m in sorted(msgs, key=lambda x: x.id):
        p = parse_message(m.text)
        if p:
            kind, value = p
            latest[kind] = {"value": value, "msg_id": m.id, "time": m.time_iso}
    print("latest:", latest)
    assert "sell" in latest, "قیمت فروش در کانال پیدا نشد"

    now = datetime.now(ZoneInfo("Asia/Tehran"))
    report = admin_report(latest, now)
    print("---- گزارش ادمین ----")
    print(report)
    alert = change_alert("sell", latest["sell"]["value"], latest["sell"]["value"] - 500_000, now)
    post = publish_post(latest, now)
    kb = contact_keyboard("yas110gold_bot")
    print("---- هشدار تغییر ----")
    print(alert)
    print("---- پست کانال ----")
    print(post)
    print("---- دکمه‌ها ----")
    labels = [b.text for b in kb.inline_keyboard[0]]
    assert labels == ["🔴 فروش به ما", "🟢 خرید از ما"], labels


def test_database(tmp_path=None):
    init_db()
    save_state("prices", {"sell": {"value": 1}})
    st = get_state()
    assert st["prices"] == {"sell": {"value": 1}}
    n_before = count_prices()
    insert_price("sell", 95400000, 107119)
    assert count_prices() == n_before + 1
    print("✅ database OK — رکوردها:", count_prices())


if __name__ == "__main__":
    test_jalali()
    test_to_int()
    test_parse_message_sell_only_toman()
    test_database()
    asyncio.run(test_live_channel())
    print("\n🎉 همه‌ی تست‌ها پاس شد")
