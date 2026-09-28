import sqlite3
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.export import pdf_report, pptx_report, excel_report
from app.config import settings as cfg

DB_PATH = ROOT / "data" / "smart_equity.db"


def get_conn():
    assert DB_PATH.exists(), "Run app/data/import_engine.py first"
    return sqlite3.connect(str(DB_PATH))


def test_reports_generate_with_logo_configured(tmp_path, monkeypatch):
    from PIL import Image
    fake_settings = tmp_path / "settings.json"
    fake_assets = tmp_path / "assets"
    monkeypatch.setattr(cfg, "SETTINGS_PATH", fake_settings)
    monkeypatch.setattr(cfg, "ASSETS_DIR", fake_assets)

    src = tmp_path / "logo.png"
    Image.new("RGB", (300, 120), color=(20, 40, 60)).save(src, format="PNG")
    cfg.set_logo(str(src))
    assert cfg.get_logo_path() is not None

    conn = get_conn()
    pdf_out = pdf_report.generate_pdf_report(conn, str(tmp_path / "r.pdf"))
    pptx_out = pptx_report.generate_pptx_report(conn, str(tmp_path / "r.pptx"))
    xlsx_out = excel_report.generate_excel_report(conn, str(tmp_path / "r.xlsx"))

    assert pathlib.Path(pdf_out).stat().st_size > 10_000
    assert pathlib.Path(pptx_out).stat().st_size > 10_000
    assert pathlib.Path(xlsx_out).stat().st_size > 10_000


def test_excel_logo_embedded_in_summary_sheet(tmp_path, monkeypatch):
    from PIL import Image
    fake_settings = tmp_path / "settings.json"
    fake_assets = tmp_path / "assets"
    monkeypatch.setattr(cfg, "SETTINGS_PATH", fake_settings)
    monkeypatch.setattr(cfg, "ASSETS_DIR", fake_assets)
    src = tmp_path / "logo.png"
    Image.new("RGB", (300, 120)).save(src, format="PNG")
    cfg.set_logo(str(src))

    conn = get_conn()
    out = excel_report.generate_excel_report(conn, str(tmp_path / "r.xlsx"))
    import openpyxl
    wb = openpyxl.load_workbook(out)
    ws = wb["خلاصه"]
    assert len(ws._images) == 1


def test_reports_generate_without_logo_gracefully(tmp_path, monkeypatch):
    """نبود لوگو نباید هیچ‌کدام از سه تولیدکننده گزارش را کرش بدهد."""
    fake_settings = tmp_path / "settings.json"
    monkeypatch.setattr(cfg, "SETTINGS_PATH", fake_settings)
    assert cfg.get_logo_path() is None

    conn = get_conn()
    pdf_out = pdf_report.generate_pdf_report(conn, str(tmp_path / "r2.pdf"))
    pptx_out = pptx_report.generate_pptx_report(conn, str(tmp_path / "r2.pptx"))
    xlsx_out = excel_report.generate_excel_report(conn, str(tmp_path / "r2.xlsx"))
    assert pathlib.Path(pdf_out).exists()
    assert pathlib.Path(pptx_out).exists()
    assert pathlib.Path(xlsx_out).exists()


def test_excel_no_image_when_no_logo(tmp_path, monkeypatch):
    fake_settings = tmp_path / "settings.json"
    monkeypatch.setattr(cfg, "SETTINGS_PATH", fake_settings)
    conn = get_conn()
    out = excel_report.generate_excel_report(conn, str(tmp_path / "r3.xlsx"))
    import openpyxl
    wb = openpyxl.load_workbook(out)
    ws = wb["خلاصه"]
    assert len(ws._images) == 0
