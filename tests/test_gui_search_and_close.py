import pathlib
import sys
import sqlite3
import shutil
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication
from app.ui.main_window import make_table, fill_table, apply_table_filter, MainWindow, SettingsPage

UPLOAD_XLSX = pathlib.Path("/mnt/user-data/uploads/Book2.xlsx")


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_apply_table_filter_hides_non_matching_rows(qapp):
    t = make_table(["نام", "ارزش"])
    fill_table(t, [["علی رضایی", 100], ["محمد کریمی", 200], ["علی احمدی", 300]])
    apply_table_filter(t, "علی", column=0)
    hidden = [t.isRowHidden(r) for r in range(t.rowCount())]
    # دو ردیف "علی رضایی" و "علی احمدی" باید نمایان بمانند، "محمد کریمی" پنهان شود
    visible_names = [t.item(r, 0).text() for r in range(t.rowCount()) if not t.isRowHidden(r)]
    assert set(visible_names) == {"علی رضایی", "علی احمدی"}


def test_apply_table_filter_empty_query_shows_all(qapp):
    t = make_table(["نام", "ارزش"])
    fill_table(t, [["علی", 1], ["رضا", 2]])
    apply_table_filter(t, "رضا", column=0)
    apply_table_filter(t, "", column=0)  # پاک‌کردن جستجو باید همه را دوباره نشان دهد
    hidden = [t.isRowHidden(r) for r in range(t.rowCount())]
    assert not any(hidden)


def test_apply_table_filter_all_columns_mode(qapp):
    t = make_table(["نوع", "توضیح"])
    fill_table(t, [["قیمت غیرعادی", "کارگزار الف در این معامله فعال بود"],
                   ["معامله بزرگ", "بدون نام کارگزار خاصی"]])
    apply_table_filter(t, "کارگزار الف", column=None)
    visible = [t.item(r, 0).text() for r in range(t.rowCount()) if not t.isRowHidden(r)]
    assert visible == ["قیمت غیرعادی"]


def test_apply_table_filter_case_insensitive(qapp):
    t = make_table(["نام", "کد"])
    fill_table(t, [["BFM صندوق", 1], ["دیگری", 2]])
    apply_table_filter(t, "bfm", column=0)
    visible = [t.item(r, 0).text() for r in range(t.rowCount()) if not t.isRowHidden(r)]
    assert visible == ["BFM صندوق"]


def test_close_event_preserves_database(qapp, tmp_path, monkeypatch):
    """دیتابیس پروژه پرتابل با بستن برنامه حذف نمی‌شود و در اجرای بعدی قابل ادامه است."""
    import app.ui.main_window as mw_module

    fake_db = tmp_path / "smart_equity.db"
    sqlite3.connect(str(fake_db)).close()

    monkeypatch.setattr(mw_module, "DB_PATH", fake_db)
    win = MainWindow()
    assert fake_db.exists()

    class FakeEvent:
        def accept(self):
            self.accepted = True

    event = FakeEvent()
    win.closeEvent(event)

    assert fake_db.exists()
    assert getattr(event, "accepted", False)


def test_settings_page_loads_current_values(qapp, tmp_path, monkeypatch):
    import app.config.settings as cfg
    fake_settings = tmp_path / "settings.json"
    monkeypatch.setattr(cfg, "SETTINGS_PATH", fake_settings)
    cfg.save_settings({"company_name": "شرکت تست", "report_prepared_by": "شخص تست"})

    page = SettingsPage()
    assert page.company_name_edit.text() == "شرکت تست"
    assert page.prepared_by_edit.text() == "شخص تست"
    assert page.market_maker_edit.text() == "بازارگردان الکترونیکی الگوریتمی صباتامین"


def test_settings_page_save_round_trip(qapp, tmp_path, monkeypatch):
    import app.config.settings as cfg
    fake_settings = tmp_path / "settings.json"
    monkeypatch.setattr(cfg, "SETTINGS_PATH", fake_settings)

    page = SettingsPage()
    page.company_name_edit.setText("شرکت جدید")
    page.prepared_by_edit.setText("مدیر جدید")
    page.market_maker_edit.setText("بازارگردان الف، بازارگردان ب")
    page.on_save()

    assert cfg.get_company_name() == "شرکت جدید"
    assert cfg.get_report_prepared_by() == "مدیر جدید"
    assert cfg.get_primary_market_maker_names() == ["بازارگردان الف", "بازارگردان ب"]
    assert "ذخیره شد" in page.status_label.text()


def test_settings_page_logo_upload_and_remove(qapp, tmp_path, monkeypatch):
    import app.config.settings as cfg
    from PIL import Image
    fake_settings = tmp_path / "settings.json"
    fake_assets = tmp_path / "assets"
    monkeypatch.setattr(cfg, "SETTINGS_PATH", fake_settings)
    monkeypatch.setattr(cfg, "ASSETS_DIR", fake_assets)

    page = SettingsPage()
    assert not page.btn_remove_logo.isEnabled()

    src = tmp_path / "logo.jpg"
    Image.new("RGB", (300, 100), color=(1, 2, 3)).save(src, format="JPEG")
    cfg.set_logo(str(src))
    page._load_logo_preview()
    assert page.btn_remove_logo.isEnabled()
    assert not page.logo_preview.pixmap().isNull()

    page.on_remove_logo()
    assert not page.btn_remove_logo.isEnabled()
    assert cfg.get_logo_path() is None
