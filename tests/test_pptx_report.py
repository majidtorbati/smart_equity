import sqlite3
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.export import pptx_report as pr
from app.analytics import metrics as m
from app.config.settings import get_primary_market_maker_names

DB_PATH = ROOT / "data" / "smart_equity.db"


def get_conn():
    assert DB_PATH.exists(), "Run app/data/import_engine.py first"
    return sqlite3.connect(str(DB_PATH))


def test_settings_returns_configured_market_maker():
    names = get_primary_market_maker_names()
    assert "بازارگردان الکترونیکی الگوریتمی صباتامین" in names


def test_top_brokers_flags_only_configured_market_maker():
    conn = get_conn()
    buyers = m.top_brokers(conn, "buyer", top_n=200)
    sellers = m.top_brokers(conn, "seller", top_n=200)
    flagged = [b["broker_name"] for b in buyers + sellers if b["is_primary_market_maker"]]
    assert set(flagged) == {"بازارگردان الکترونیکی الگوریتمی صباتامین"}
    # the general market-making fund broker trades only on the sell side in this dataset;
    # it must NOT be flagged as the primary market maker even though its name contains "بازارگردانی"
    sell_names_non_flagged = [b["broker_name"] for b in sellers if not b["is_primary_market_maker"]]
    assert "شرکت کارگزاری صندوق بازارگردانی توسعه بازار1" in sell_names_non_flagged


def test_generate_pptx_creates_valid_file(tmp_path):
    conn = get_conn()
    out_path = str(tmp_path / "test_report.pptx")
    result = pr.generate_pptx_report(conn, out_path)
    assert pathlib.Path(result).exists()
    assert pathlib.Path(result).stat().st_size > 10_000  # not an empty/broken file


def test_generate_pptx_has_expected_slide_count():
    from pptx import Presentation
    conn = get_conn()
    out_path = str(pathlib.Path(ROOT) / "exports" / "gozaresh_hiat_modire.pptx")
    pr.generate_pptx_report(conn, out_path)
    prs = Presentation(out_path)
    assert len(list(prs.slides)) == 16


def test_truncate_helper_adds_ellipsis_not_raw_cut():
    long_name = "این یک نام بسیار طولانی برای تست کوتاه‌سازی است"
    result = pr._truncate(long_name, 10)
    assert result.endswith("…")
    assert len(result) <= 11


def test_truncate_helper_leaves_short_text_untouched():
    assert pr._truncate("نام کوتاه", 30) == "نام کوتاه"


def test_compact_billion_rial_formatting():
    assert pr._fmt_compact_billion_rial(1_112_482_312_636) == "1,112"
    assert pr._fmt_compact_billion_rial(2_300_000_000) == "2"  # 2.3bn rounds to 2
