"""
مقایسه دوره‌ای (Period Comparison)
به‌طور پیش‌فرض، بازه انتخابی کاربر («بازه B») با بازه‌ی هم‌طول دقیقاً قبل از آن («بازه A») مقایسه می‌شود،
مگر اینکه دو بازه به‌صورت صریح مشخص شوند.
"""
from __future__ import annotations
import sqlite3
import datetime as dt
import sys
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from app.analytics import metrics as m
from app.core.jalali import jalali_date_display


def previous_equal_period(conn: sqlite3.Connection, start: str, end: str) -> tuple[str, str] | None:
    """
    بازه A را که دقیقاً هم‌طول و بلافاصله قبل از [start, end] است برمی‌گرداند.
    اگر start/end مشخص نباشند (کل بازه انتخاب شده)، از کل محدوده داده استفاده می‌شود
    و بازه به دو نیمه مساوی (قدیمی/جدید) تقسیم می‌گردد.
    """
    if not start or not end:
        row = conn.execute("SELECT MIN(trade_date_gregorian), MAX(trade_date_gregorian) FROM transactions").fetchone()
        if not row or not row[0]:
            return None
        full_start, full_end = dt.date.fromisoformat(row[0]), dt.date.fromisoformat(row[1])
        mid = full_start + (full_end - full_start) / 2
        return full_start.isoformat(), mid.isoformat()  # caller treats this as period A; period B = mid+1..full_end handled by caller
    s = dt.date.fromisoformat(start)
    e = dt.date.fromisoformat(end)
    length = (e - s).days + 1
    prev_end = s - dt.timedelta(days=1)
    prev_start = prev_end - dt.timedelta(days=length - 1)
    return prev_start.isoformat(), prev_end.isoformat()


def _pct_change(old, new) -> float | None:
    if old in (0, None):
        return None
    return (new - old) / old * 100


def compare_periods(conn: sqlite3.Connection, start_a, end_a, start_b, end_b, top_n=10) -> dict:
    ov_a = m.overview(conn, start_a, end_a)
    ov_b = m.overview(conn, start_b, end_b)
    conc_a = m.concentration(conn, "buyer", start_a, end_a)
    conc_b = m.concentration(conn, "buyer", start_b, end_b)

    buyers_a = {p["person_id"] for p in m.top_persons(conn, "buyer", start_a, end_a, top_n=100000)}
    buyers_b = {p["person_id"] for p in m.top_persons(conn, "buyer", start_b, end_b, top_n=100000)}
    names = dict(conn.execute("SELECT person_id, name_raw FROM persons"))
    new_participants = [names.get(pid) for pid in (buyers_b - buyers_a)]
    exited_participants = [names.get(pid) for pid in (buyers_a - buyers_b)]

    deltas = {
        "n_transactions": {"a": ov_a["n_transactions"], "b": ov_b["n_transactions"],
                            "pct": _pct_change(ov_a["n_transactions"], ov_b["n_transactions"])},
        "total_value": {"a": ov_a["total_value"], "b": ov_b["total_value"],
                         "pct": _pct_change(ov_a["total_value"], ov_b["total_value"])},
        "total_quantity": {"a": ov_a["total_quantity"], "b": ov_b["total_quantity"],
                            "pct": _pct_change(ov_a["total_quantity"], ov_b["total_quantity"])},
        "weighted_avg_price": {"a": ov_a["weighted_avg_price"], "b": ov_b["weighted_avg_price"],
                                "pct": _pct_change(ov_a["weighted_avg_price"], ov_b["weighted_avg_price"])},
        "n_unique_buyers": {"a": ov_a["n_unique_buyers"], "b": ov_b["n_unique_buyers"],
                             "pct": _pct_change(ov_a["n_unique_buyers"], ov_b["n_unique_buyers"])},
        "hhi_buyers": {"a": conc_a["hhi"], "b": conc_b["hhi"], "pct": _pct_change(conc_a["hhi"], conc_b["hhi"])},
    }

    narrative = []
    label_fa = {
        "n_transactions": "تعداد معاملات", "total_value": "ارزش کل معاملات", "total_quantity": "حجم کل",
        "weighted_avg_price": "میانگین وزنی قیمت", "n_unique_buyers": "تعداد خریداران", "hhi_buyers": "شاخص تمرکز خریداران",
    }
    for key, d in deltas.items():
        if d["pct"] is None:
            continue
        direction = "افزایش" if d["pct"] >= 0 else "کاهش"
        narrative.append(f"{label_fa[key]} نسبت به بازه قبل {abs(d['pct']):.1f} درصد {direction} یافته است.")

    if new_participants:
        narrative.append(f"{len(new_participants)} خریدار برای اولین‌بار در این بازه ظاهر شده‌اند که در بازه قبل حضور نداشتند.")
    if exited_participants:
        narrative.append(f"{len(exited_participants)} خریدار که در بازه قبل فعال بودند، در این بازه معامله‌ای ثبت نکرده‌اند.")

    return {
        "period_a": {"start": start_a, "end": end_a, "start_fa": jalali_date_display(start_a), "end_fa": jalali_date_display(end_a)},
        "period_b": {"start": start_b, "end": end_b, "start_fa": jalali_date_display(start_b), "end_fa": jalali_date_display(end_b)},
        "deltas": deltas,
        "new_participants": new_participants[:top_n],
        "exited_participants": exited_participants[:top_n],
        "n_new_participants": len(new_participants),
        "n_exited_participants": len(exited_participants),
        "narrative": narrative,
    }


def auto_compare_with_previous(conn: sqlite3.Connection, start=None, end=None, top_n=10) -> dict:
    """نسخه راحت: بازه B را از start/end کاربر می‌گیرد و بازه A را خودکار محاسبه می‌کند."""
    if start and end:
        prev = previous_equal_period(conn, start, end)
        if prev is None:
            return {"narrative": ["داده‌ای برای مقایسه یافت نشد."], "deltas": {}}
        start_a, end_a = prev
        return compare_periods(conn, start_a, end_a, start, end, top_n=top_n)
    else:
        # کل بازه: تقسیم به دو نیمه (قدیمی/جدید) برای مقایسه‌ای معنادار
        prev = previous_equal_period(conn, start, end)
        if prev is None:
            return {"narrative": ["داده‌ای برای مقایسه یافت نشد."], "deltas": {}}
        full_start, mid = prev
        row = conn.execute("SELECT MAX(trade_date_gregorian) FROM transactions").fetchone()
        full_end = row[0]
        next_day = (dt.date.fromisoformat(mid) + dt.timedelta(days=1)).isoformat()
        return compare_periods(conn, full_start, mid, next_day, full_end, top_n=top_n)


if __name__ == "__main__":
    db_path = str(pathlib.Path(__file__).resolve().parents[2] / "data" / "smart_equity.db")
    conn = sqlite3.connect(db_path)

    print("=== Auto comparison (custom period vs previous equal period) ===")
    res = compare_periods(conn, "2026-06-01", "2026-06-15", "2026-06-16", "2026-06-30")
    print("Period A:", res["period_a"])
    print("Period B:", res["period_b"])
    for line in res["narrative"]:
        print(" -", line)
    print("New participants (sample):", res["new_participants"][:5])

    print()
    print("=== Auto comparison (full range split in half) ===")
    res2 = auto_compare_with_previous(conn)
    print("Period A:", res2["period_a"])
    print("Period B:", res2["period_b"])
    for line in res2["narrative"]:
        print(" -", line)
