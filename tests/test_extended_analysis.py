import sqlite3
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.analytics import extended_analysis as ext

DB_PATH = ROOT / "data" / "smart_equity.db"


def get_conn():
    assert DB_PATH.exists(), "Run app/data/import_engine.py first"
    return sqlite3.connect(str(DB_PATH))


def test_hhi_summary_matches_concentration_module():
    conn = get_conn()
    from app.analytics import metrics as m
    res = ext.hhi_summary(conn)
    expected = m.concentration(conn, "buyer")
    assert abs(res["buy"]["hhi"] - expected["hhi"]) < 1e-6


def test_fundamental_note_does_not_fabricate_numbers():
    """
    محدودیت داده باید صریح باشد و نباید هیچ عدد مالی جعلی (سود، درآمد، P/E) در آن دیده شود.
    """
    conn = get_conn()
    res = ext.fundamental_analysis_note(conn)
    full_text = " ".join(res["narrative"])
    assert "نیازمند صورت‌های مالی" in full_text or "موجود نیست" in full_text
    # no fabricated financial figures like "سود خالص: ..." with a number should appear
    assert "سود خالص:" not in full_text
    assert len(res["required_data"]) >= 3


def test_qualitative_shares_sum_to_100():
    conn = get_conn()
    res = ext.qualitative_market_behavior(conn)
    assert abs(res["institutional_share_pct"] + res["individual_share_pct"] - 100) < 1e-6


def test_qualitative_distinguishes_from_company_level_analysis():
    conn = get_conn()
    res = ext.qualitative_market_behavior(conn)
    full_text = " ".join(res["narrative"])
    assert "تحلیل کیفی بنیادی شرکت" in full_text  # explicit disclaimer must be present


def test_valuation_overview_distinguishes_price_from_value():
    conn = get_conn()
    res = ext.valuation_methods_overview(conn)
    full_text = " ".join(res["narrative"])
    assert "ارزش ذاتی" in full_text
    assert "قیمت بازار مشاهده‌شده" in full_text
    assert len(res["methods"]) >= 3
    assert res["observed_market_price"] > 0
