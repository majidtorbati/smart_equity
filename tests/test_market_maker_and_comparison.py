import sqlite3
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.analytics import market_maker as mm
from app.analytics import comparison as comp
from app.analytics import insights as ins

DB_PATH = ROOT / "data" / "smart_equity.db"


def get_conn():
    assert DB_PATH.exists(), "Run app/data/import_engine.py first"
    return sqlite3.connect(str(DB_PATH))


# ---------- Market maker ----------

def test_market_maker_detected_in_real_data():
    conn = get_conn()
    brokers = mm.get_market_maker_broker_ids(conn)
    assert len(brokers) >= 1
    assert all("broker_id" in b and "broker_name" in b for b in brokers)


def test_market_maker_only_designated_broker_included():
    """
    طبق تأیید کاربر، فقط «بازارگردان الکترونیکی الگوریتمی صباتامین» بازارگردان اصلی این نماد است.
    کارگزار دوم که به‌طور خودکار (به‌خاطر داشتن کلمه «بازارگردان» در نام) پرچم گرفته بود
    («شرکت کارگزاری صندوق بازارگردانی توسعه بازار1») نباید در این تحلیل به‌عنوان بازارگردان لحاظ شود.
    """
    conn = get_conn()
    brokers = mm.get_market_maker_broker_ids(conn)
    names = [b["broker_name"] for b in brokers]
    assert "بازارگردان الکترونیکی الگوریتمی صباتامین" in names
    assert "شرکت کارگزاری صندوق بازارگردانی توسعه بازار1" not in names
    assert len(brokers) == 1


def test_market_maker_daily_activity_matches_total():
    conn = get_conn()
    summary = mm.market_maker_summary(conn)
    assert summary["has_market_maker"] is True
    daily_buy_sum = sum(d["mm_buy_value"] for d in summary["daily"])
    daily_sell_sum = sum(d["mm_sell_value"] for d in summary["daily"])
    assert abs(daily_buy_sum - summary["total_buy_value"]) < 1e-6
    assert abs(daily_sell_sum - summary["total_sell_value"]) < 1e-6


def test_market_maker_up_down_percentages_bounded():
    conn = get_conn()
    summary = mm.market_maker_summary(conn)
    for key in ["pct_up_days_mm_seller", "pct_up_days_mm_buyer", "pct_down_days_mm_buyer", "pct_down_days_mm_seller"]:
        val = summary.get(key)
        if val is not None:
            assert 0 <= val <= 100


def test_market_maker_narrative_avoids_causal_language():
    conn = get_conn()
    summary = mm.market_maker_summary(conn)
    full_text = " ".join(summary["narrative"])
    assert "باعث" not in full_text or "نمی‌توان نتیجه گرفت" in full_text
    assert "هم‌زمانی" in full_text or "هم‌خوان" in full_text


def test_market_maker_net_value_equals_buy_minus_sell():
    conn = get_conn()
    summary = mm.market_maker_summary(conn)
    assert abs(summary["net_value"] - (summary["total_buy_value"] - summary["total_sell_value"])) < 1e-6


# ---------- Period comparison ----------

def test_previous_equal_period_length_matches():
    conn = get_conn()
    prev = comp.previous_equal_period(conn, "2026-06-10", "2026-06-19")  # 10-day period
    assert prev is not None
    import datetime as dt
    start_a, end_a = [dt.date.fromisoformat(x) for x in prev]
    assert (end_a - start_a).days + 1 == 10
    assert end_a == dt.date(2026, 6, 9)  # immediately before 2026-06-10


def test_compare_periods_new_and_exited_are_disjoint_from_common():
    conn = get_conn()
    res = comp.compare_periods(conn, "2026-05-24", "2026-07-06", "2026-07-07", "2026-08-18")
    new_set = set(res["new_participants"])
    exited_set = set(res["exited_participants"])
    assert new_set.isdisjoint(exited_set)


def test_compare_periods_pct_change_matches_manual_calc():
    conn = get_conn()
    res = comp.compare_periods(conn, "2026-05-24", "2026-07-06", "2026-07-07", "2026-08-18")
    d = res["deltas"]["total_value"]
    if d["a"]:
        expected_pct = (d["b"] - d["a"]) / d["a"] * 100
        assert abs(d["pct"] - expected_pct) < 1e-6


def test_auto_compare_with_full_range_produces_two_periods():
    conn = get_conn()
    res = comp.auto_compare_with_previous(conn, None, None)
    assert res["period_a"]["start"] is not None
    assert res["period_b"]["start"] is not None
    assert res["period_a"]["end"] < res["period_b"]["start"]


# ---------- Insights ----------

def test_executive_summary_narrative_nonempty_and_grounded():
    conn = get_conn()
    lines = ins.executive_summary_narrative(conn)
    assert len(lines) >= 3
    # first line should mention the real transaction count
    from app.analytics import metrics as m
    ov = m.overview(conn)
    assert f"{ov['n_transactions']:,}" in lines[0]
