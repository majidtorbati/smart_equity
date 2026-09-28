"""
تبدیل تاریخ شمسی (جلالی) به میلادی و بالعکس.
پیاده‌سازی مستقل بدون نیاز به کتابخانه خارجی (برای سازگاری با build پرتابل).
الگوریتم استاندارد تبدیل جلالی <-> گرگوری.
"""
from __future__ import annotations
import datetime as _dt


def _div(a, b):
    return a // b


def jalali_to_gregorian(jy: int, jm: int, jd: int) -> _dt.date:
    jy += 1595
    days = -355668 + (365 * jy) + (_div(jy, 33) * 8) + _div(((jy % 33) + 3), 4) + jd
    if jm < 7:
        days += (jm - 1) * 31
    else:
        days += ((jm - 7) * 30) + 186
    gy = 400 * _div(days, 146097)
    days %= 146097
    if days > 36524:
        gy += 100 * _div(days - 1, 36524)
        days = (days - 1) % 36524
        if days >= 365:
            days += 1
    gy += 4 * _div(days, 1461)
    days %= 1461
    if days > 365:
        gy += _div(days - 1, 365)
        days = (days - 1) % 365
    gd = days + 1
    sal_a = [0, 31, 59 + (1 if (gy % 4 == 0 and (gy % 100 != 0 or gy % 400 == 0)) else 0),
             90 + (1 if (gy % 4 == 0 and (gy % 100 != 0 or gy % 400 == 0)) else 0),
             120 + (1 if (gy % 4 == 0 and (gy % 100 != 0 or gy % 400 == 0)) else 0),
             151 + (1 if (gy % 4 == 0 and (gy % 100 != 0 or gy % 400 == 0)) else 0),
             181 + (1 if (gy % 4 == 0 and (gy % 100 != 0 or gy % 400 == 0)) else 0),
             212, 243, 273, 304, 334, 365]
    gm = 0
    for i in range(1, 13):
        if gd <= sal_a[i]:
            gm = i
            break
    gd = gd - sal_a[gm - 1]
    return _dt.date(int(gy), int(gm), int(gd))


def gregorian_to_jalali(gy: int, gm: int, gd: int):
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    if gm > 2 and (gy % 4 == 0 and (gy % 100 != 0 or gy % 400 == 0)):
        gy2 = gy + 1
    else:
        gy2 = gy
    days = 355666 + (365 * gy) + _div((gy2 + 3), 4) - _div((gy2 + 99), 100) + _div((gy2 + 399), 400) + gd + g_d_m[gm - 1]
    jy = -1595 + (33 * _div(days, 12053))
    days %= 12053
    jy += 4 * _div(days, 1461)
    days %= 1461
    if days > 365:
        jy += _div(days - 1, 365)
        days = (days - 1) % 365
    if days < 186:
        jm = 1 + _div(days, 31)
        jd = 1 + (days % 31)
    else:
        jm = 7 + _div((days - 186), 30)
        jd = 1 + ((days - 186) % 30)
    return int(jy), int(jm), int(jd)


def parse_yyyymmdd_jalali(value) -> _dt.date:
    """
    ورودی نمونه: 14050313  ->  1405/03/13 (شمسی)  ->  تاریخ میلادی معادل
    مقادیر فایل به‌صورت عدد صحیح 8 رقمی هستند.
    """
    s = str(int(value))
    if len(s) != 8:
        raise ValueError(f"Unexpected Jalali date format: {value}")
    jy = int(s[0:4])
    jm = int(s[4:6])
    jd = int(s[6:8])
    return jalali_to_gregorian(jy, jm, jd)


def to_jalali_str(g_date: _dt.date) -> str:
    jy, jm, jd = gregorian_to_jalali(g_date.year, g_date.month, g_date.day)
    return f"{jy:04d}/{jm:02d}/{jd:02d}"


def jalali_date_display(iso_date_str) -> str:
    """
    ورودی: '2026-06-03' یا None  ->  خروجی: '1405/03/13' یا '' (برای نمایش در UI/گزارش‌ها).
    این تابع تنها لایه نمایش را تبدیل می‌کند؛ ذخیره‌سازی داخلی همچنان میلادی/ISO باقی می‌ماند.
    """
    if not iso_date_str:
        return ""
    try:
        g = _dt.date.fromisoformat(str(iso_date_str)[:10])
        return to_jalali_str(g)
    except (ValueError, TypeError):
        return str(iso_date_str)


def jalali_datetime_display(iso_datetime_str) -> str:
    """ورودی: '2026-08-29T10:53:25'  ->  خروجی: '1405/06/07 10:53'."""
    if not iso_datetime_str:
        return ""
    try:
        s = str(iso_datetime_str)
        dt_part, _, time_part = s.partition("T")
        g = _dt.date.fromisoformat(dt_part)
        jstr = to_jalali_str(g)
        hm = time_part[:5] if time_part else ""
        return f"{jstr} {hm}".strip()
    except (ValueError, TypeError):
        return str(iso_datetime_str)


if __name__ == "__main__":
    # self-test using known reference points
    d = parse_yyyymmdd_jalali(14050313)
    print("14050313 ->", d, "-> back to jalali:", to_jalali_str(d))
    assert to_jalali_str(d) == "1405/03/13"
    print("OK")
