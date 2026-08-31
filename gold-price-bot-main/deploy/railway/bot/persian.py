# Persian display helpers: dates and ids stay Persian.
# Prices use ENGLISH digits per Ali's decision → money().
FA_DIGITS = str.maketrans("0123456789,.%", "۰۱۲۳۴۵۶۷۸۹٬٫٪")


def fa_digits(value) -> str:
    """Return a number/string with Persian digits — for dates, ids and counters."""
    return str(value).translate(FA_DIGITS)


def money(amount: int) -> str:
    """Integer → thousands separator with English digits (unit added separately):
    95340000 → 95,340,000"""
    return f"{int(amount):,}"