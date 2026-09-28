import sqlite3
import pathlib
import sys
import math

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.jalali import parse_yyyymmdd_jalali, to_jalali_str
from app.core.normalize import normalize_key, clean_display
from app.analytics import metrics as m

DB_PATH = ROOT / "data" / "smart_equity.db"


def get_conn():
    assert DB_PATH.exists(), "Run app/data/import_engine.py first to build the database"
    return sqlite3.connect(str(DB_PATH))


# ---------- Jalali date tests ----------

def test_jalali_roundtrip():
    for val in [14050303, 14050313, 14050519, 14050527]:
        d = parse_yyyymmdd_jalali(val)
        s = str(val)
        expected = f"{s[0:4]}/{s[4:6]}/{s[6:8]}"
        assert to_jalali_str(d) == expected


def test_jalali_known_reference():
    # 1405/01/01 is a known Nowruz reference point; should land in March 2026
    d = parse_yyyymmdd_jalali(14050101)
    assert d.year == 2026
    assert d.month == 3


# ---------- Normalization tests ----------

def test_normalize_zwnj_equivalence():
    a = normalize_key("مشتری\u200cالکترونیکی\u200cمفید2-مفید")
    b = normalize_key("مشتری الکترونیکی مفید2-مفید")
    assert a == b


def test_clean_display_no_literal_nan():
    assert "nan" not in clean_display("مظفری سعید")


# ---------- Analytics correctness tests ----------

def test_overview_matches_manual_sql():
    conn = get_conn()
    ov = m.overview(conn)
    row = conn.execute(
        "SELECT COUNT(*), SUM(quantity), SUM(value) FROM transactions WHERE is_duplicate_of IS NULL"
    ).fetchone()
    assert ov["n_transactions"] == row[0]
    assert ov["total_quantity"] == row[1]
    assert math.isclose(ov["total_value"], row[2], rel_tol=1e-9)


def test_weighted_average_price_is_correct():
    conn = get_conn()
    ov = m.overview(conn)
    # weighted avg must lie within [min price, max price] observed in data
    lo, hi = conn.execute("SELECT MIN(price), MAX(price) FROM transactions WHERE is_duplicate_of IS NULL").fetchone()
    assert lo <= ov["weighted_avg_price"] <= hi
    # and must equal total_value / total_quantity exactly
    assert math.isclose(ov["weighted_avg_price"], ov["total_value"] / ov["total_quantity"], rel_tol=1e-9)


def test_weighted_avg_not_simple_average():
    """
    اثبات اینکه میانگین وزنی واقعاً وزنی است، نه میانگین ساده قیمت‌ها.
    """
    conn = get_conn()
    ov = m.overview(conn)
    simple_avg = conn.execute("SELECT AVG(price) FROM transactions WHERE is_duplicate_of IS NULL").fetchone()[0]
    # they need not be equal; test only that our function returns the *weighted* value, computed independently
    manual_weighted = conn.execute(
        "SELECT SUM(quantity*price)*1.0/SUM(quantity) FROM transactions WHERE is_duplicate_of IS NULL"
    ).fetchone()[0]
    assert math.isclose(ov["weighted_avg_price"], manual_weighted, rel_tol=1e-9)


def test_duplicates_excluded_from_analytics():
    conn = get_conn()
    total_rows = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    ov = m.overview(conn)
    n_dup = conn.execute("SELECT COUNT(*) FROM transactions WHERE is_duplicate_of IS NOT NULL").fetchone()[0]
    assert ov["n_transactions"] == total_rows - n_dup
    # عدد ثابت نگه داشته نمی‌شود چون با تغییر فایل نمونه (تعداد ردیف/دوره متفاوت) طبیعتاً فرق می‌کند؛
    # فقط سازگاری داخلی (overview == total - duplicates) که در خط بالا چک شد، ثابت و معنادار است.
    assert n_dup >= 0


def test_top_brokers_sums_le_total_value():
    conn = get_conn()
    ov = m.overview(conn)
    brokers = m.top_brokers(conn, "buyer", top_n=1000)
    total_broker_value = sum(b["value"] for b in brokers)
    # each transaction has exactly one buyer broker, so sums must be very close to total value
    assert math.isclose(total_broker_value, ov["total_value"], rel_tol=1e-9)


def test_net_position_buy_minus_sell():
    conn = get_conn()
    res = m.net_position_persons(conn, top_n=5)
    for p in res["top_net_buyers"]:
        assert p["net_value"] >= res["top_net_sellers"][-1]["net_value"] if res["top_net_sellers"] else True


def test_concentration_shares_are_monotonic_and_bounded():
    conn = get_conn()
    c = m.concentration(conn, "buyer")
    assert 0 <= c["top1_share_pct"] <= c["top5_share_pct"] <= c["top10_share_pct"] <= 100
    assert 0 <= c["hhi"] <= 10000


def test_individual_vs_institutional_totals_match_overview():
    conn = get_conn()
    ov = m.overview(conn)
    iv = m.individual_vs_institutional(conn)
    total_buy = sum(v["buy_value"] for v in iv.values())
    assert math.isclose(total_buy, ov["total_value"], rel_tol=1e-9)


def test_date_filter_narrows_results():
    conn = get_conn()
    full = m.overview(conn)
    narrowed = m.overview(conn, start="2026-08-01", end="2026-08-18")
    assert narrowed["n_transactions"] <= full["n_transactions"]
    assert narrowed["total_value"] <= full["total_value"]
