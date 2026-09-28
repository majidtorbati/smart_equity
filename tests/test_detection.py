import sqlite3
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.detection import anomaly as an
from app.detection import behavior as bh

DB_PATH = ROOT / "data" / "smart_equity.db"


def get_conn():
    assert DB_PATH.exists(), "Run app/data/import_engine.py first"
    return sqlite3.connect(str(DB_PATH))


def test_large_trade_alerts_reference_real_transactions():
    conn = get_conn()
    alerts = an.detect_large_trades(conn)
    assert len(alerts) > 0
    for a in alerts[:5]:
        tx_id = a["supporting_transaction_ids"][0]
        row = conn.execute("SELECT value FROM transactions WHERE transaction_id=?", (tx_id,)).fetchone()
        assert row is not None
        assert abs(row[0] - a["value"]) < 1e-6


def test_large_trade_z_scores_above_threshold():
    conn = get_conn()
    alerts = an.detect_large_trades(conn, z_threshold=3.0)
    for a in alerts:
        assert a["z_score"] >= 3.0


def test_broker_spike_reason_uses_jalali_date_not_gregorian():
    """
    باگ واقعی: متن 'reason' این هشدار قبلاً تاریخ میلادی خام (مثل 2026-08-18) را مستقیم در جمله
    جاسازی می‌کرد چون در لحظه تشخیص ساخته می‌شود، نه در لایه نمایش. باید همیشه شمسی باشد.
    """
    conn = get_conn()
    alerts = an.detect_broker_activity_spike(conn)
    assert len(alerts) > 0
    for a in alerts:
        assert "202" not in a["reason"]  # هیچ سال میلادی (۲۰XX) نباید در متن ظاهر شود
        assert "/" in a["reason"]  # فرمت شمسی YYYY/MM/DD همیشه شامل "/" است


def test_large_trade_and_price_outlier_include_person_names():
    """معامله‌گر (خریدار/فروشنده) هر هشدار باید قابل مشاهده باشد، نه فقط شناسه عددی پنهان."""
    conn = get_conn()
    for alerts in [an.detect_large_trades(conn), an.detect_price_outliers(conn)]:
        assert len(alerts) > 0
        for a in alerts[:20]:
            assert a["buyer_name"] is not None
            assert a["seller_name"] is not None
            # نام باید با کد ملی/شخص واقعی طرف معامله همان تراکنش پشتیبان مطابقت داشته باشد
            tx_id = a["supporting_transaction_ids"][0]
            row = conn.execute(
                "SELECT p1.name_raw, p2.name_raw FROM transactions t "
                "JOIN persons p1 ON t.buyer_person_id=p1.person_id "
                "JOIN persons p2 ON t.seller_person_id=p2.person_id "
                "WHERE t.transaction_id=?", (tx_id,)).fetchone()
            assert row == (a["buyer_name"], a["seller_name"])


def test_broker_activity_spike_has_no_person_name():
    """این نوع هشدار به یک تراکنش/شخص خاص اشاره ندارد (میانگین فعالیت روزانه کارگزار است)."""
    conn = get_conn()
    alerts = an.detect_broker_activity_spike(conn)
    assert len(alerts) > 0
    for a in alerts:
        assert "buyer_name" not in a
        assert "seller_name" not in a


def test_severity_mapping_monotonic():
    assert an._severity_from_score(10) == "Normal"
    assert an._severity_from_score(35) == "Watch"
    assert an._severity_from_score(55) == "Important"
    assert an._severity_from_score(75) == "High"
    assert an._severity_from_score(90) == "Critical"


def test_price_outliers_within_day_bounds():
    conn = get_conn()
    alerts = an.detect_price_outliers(conn)
    # every alert must reference a real date that exists in transactions
    dates_in_db = set(r[0] for r in conn.execute("SELECT DISTINCT trade_date_gregorian FROM transactions"))
    for a in alerts[:20]:
        assert a["trade_date"] in dates_in_db


def test_behavior_score_bounded_0_100():
    conn = get_conn()
    top = bh.top_short_term_traders(conn, top_n=30)
    assert len(top) > 0
    for t in top:
        assert 0 <= t["score"] <= 100


def test_behavior_score_requires_both_sides():
    """کسی که فقط خرید یا فقط فروش داشته نباید در Round-Trip candidates ظاهر شود."""
    conn = get_conn()
    top = bh.top_short_term_traders(conn, top_n=50)
    for t in top:
        pid = t["person_id"]
        has_buy = conn.execute("SELECT 1 FROM transactions WHERE buyer_person_id=? LIMIT 1", (pid,)).fetchone()
        has_sell = conn.execute("SELECT 1 FROM transactions WHERE seller_person_id=? LIMIT 1", (pid,)).fetchone()
        assert has_buy and has_sell


def test_round_trip_detection_produces_valid_prices():
    conn = get_conn()
    top = bh.top_short_term_traders(conn, top_n=5)
    assert len(top) > 0
    pid = top[0]["person_id"]
    trips = bh.detect_round_trips(conn, pid)
    assert len(trips) > 0
    for rt in trips:
        assert rt["entry_price"] > 0
        assert rt["exit_price"] > 0
        assert rt["entry_side"] != rt["exit_side"]


def test_disclaimer_present_in_score_output():
    conn = get_conn()
    top = bh.top_short_term_traders(conn, top_n=1)
    detail = bh.short_term_behavior_score(conn, top[0]["person_id"])
    assert "شاخص آماری" in detail["disclaimer"]
    assert "اثبات‌کننده" in detail["disclaimer"]


def test_same_day_pairs_are_real_overlaps():
    """هر ردیف باید واقعاً هم خرید و هم فروش همان شخص در همان روز باشد."""
    conn = get_conn()
    pairs = bh.same_day_buy_sell_pairs(conn, top_n=50)
    assert len(pairs) > 0
    for p in pairs:
        assert p["buy_qty"] > 0
        assert p["sell_qty"] > 0
        assert p["overlap_qty"] == min(p["buy_qty"], p["sell_qty"])
        row = conn.execute(
            "SELECT COUNT(*) FROM transactions WHERE buyer_person_id=? AND trade_date_gregorian=?",
            (p["person_id"], p["date"])).fetchone()
        assert row[0] > 0
        row2 = conn.execute(
            "SELECT COUNT(*) FROM transactions WHERE seller_person_id=? AND trade_date_gregorian=?",
            (p["person_id"], p["date"])).fetchone()
        assert row2[0] > 0


def test_same_day_pairs_verdict_matches_overlap_ratio():
    conn = get_conn()
    pairs = bh.same_day_buy_sell_pairs(conn, top_n=200)
    for p in pairs:
        if p["overlap_ratio"] >= 0.8:
            assert "کامل" in p["verdict"]
        elif p["overlap_ratio"] >= 0.3:
            assert "محتمل" in p["verdict"]
        else:
            assert "کم" in p["verdict"]


def test_same_day_pairs_pnl_direction_matches_price_diff():
    conn = get_conn()
    pairs = bh.same_day_buy_sell_pairs(conn, top_n=200)
    for p in pairs:
        if p["sell_price"] > p["buy_price"]:
            assert p["approx_pnl"] >= 0
        elif p["sell_price"] < p["buy_price"]:
            assert p["approx_pnl"] <= 0


def test_same_day_pairs_respects_date_filter():
    conn = get_conn()
    full = bh.same_day_buy_sell_pairs(conn, top_n=100000)
    narrowed = bh.same_day_buy_sell_pairs(conn, start="2026-08-01", end="2026-08-18", top_n=100000)
    assert len(narrowed) <= len(full)
    for p in narrowed:
        assert "2026-08-01" <= p["date"] <= "2026-08-18"
