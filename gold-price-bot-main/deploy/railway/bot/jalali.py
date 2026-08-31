# Gregorian ↔ Jalali date conversion, no external library.
# Standard algorithm (jdf.scr.ir) — tested on known dates.
# Dev comments are English.

G_MONTH_DAYS = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]

J_MONTHS = [
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
]

# weekday(): Monday=0 ... Sunday=6
J_WEEKDAYS = ["دوشنبه", "سهشنبه", "چهارشنبه", "پنجشنبه", "جمعه", "شنبه", "یکشنبه"]


def gregorian_to_jalali(gy: int, gm: int, gd: int) -> tuple[int, int, int]:
    if gm > 2:
        gy2 = gy + 1
    else:
        gy2 = gy
    days = (
        355666 + 365 * gy
        + (gy2 + 3) // 4 - (gy2 + 99) // 100 + (gy2 + 399) // 400
        + gd + G_MONTH_DAYS[gm - 1]
    )
    jy = -1595 + 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm = 1 + days // 31
        jd = 1 + days % 31
    else:
        jm = 7 + (days - 186) // 30
        jd = 1 + (days - 186) % 30
    return jy, jm, jd


def format_jalali_date(dt) -> str:
    """datetime (preferably Tehran time) → date string with English digits: '1405/06/03'"""
    from .persian import money  # money() formats with English digits + comma
    jy, jm, jd = gregorian_to_jalali(dt.year, dt.month, dt.day)
    # Use money() for zero-padded English digits: 3 → "3", but we need "03" etc.
    # Simpler: just format with f-strings (English digits natively)
    return f"{jy}/{jm:02d}/{jd:02d}"


def format_jalali_time(dt) -> str:
    """datetime (preferably Tehran time) → time string with English digits: '15:30'"""
    return f"{dt.hour:02d}:{dt.minute:02d}"


def format_jalali_datetime(dt, with_weekday: bool = True) -> str:
    """datetime (preferably Tehran time) → «سهشنبه ۳ شهریور ۱۴۰۵ • ۲۰:۰۴» (Persian digits)
    Kept for backward compatibility with admin_report / status messages."""
    from .persian import fa_digits  # inner import to avoid a circular import

    jy, jm, jd = gregorian_to_jalali(dt.year, dt.month, dt.day)
    wd = J_WEEKDAYS[dt.weekday()] if with_weekday else ""
    date_part = f"{fa_digits(jd)} {J_MONTHS[jm - 1]} {fa_digits(jy)}"
    time_part = fa_digits(f"{dt.hour:02d}:{dt.minute:02d}")
    prefix = f"{wd} " if wd else ""
    return f"{prefix}{date_part} • {time_part}"