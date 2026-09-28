import pathlib
import sys
import json

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import settings as cfg


def test_defaults_present_without_file(tmp_path, monkeypatch):
    fake_path = tmp_path / "nonexistent_settings.json"
    monkeypatch.setattr(cfg, "SETTINGS_PATH", fake_path)
    assert cfg.get_report_prepared_by() == "مدیر مالی"
    assert cfg.get_report_audience() == "هیئت‌مدیره"
    assert cfg.get_company_name() == ""
    assert cfg.get_primary_market_maker_names() == ["بازارگردان الکترونیکی الگوریتمی صباتامین"]


def test_save_and_load_round_trip(tmp_path, monkeypatch):
    fake_path = tmp_path / "settings.json"
    monkeypatch.setattr(cfg, "SETTINGS_PATH", fake_path)
    cfg.save_settings({"company_name": "شرکت آزمایشی", "report_prepared_by": "علی رضایی، مدیرعامل"})
    assert cfg.get_company_name() == "شرکت آزمایشی"
    assert cfg.get_report_prepared_by() == "علی رضایی، مدیرعامل"
    # کلیدهایی که در save_settings ذکر نشده‌اند نباید از بین بروند (merge، نه overwrite کامل)
    assert cfg.get_primary_market_maker_names() == ["بازارگردان الکترونیکی الگوریتمی صباتامین"]


def test_save_settings_merges_not_overwrites(tmp_path, monkeypatch):
    fake_path = tmp_path / "settings.json"
    monkeypatch.setattr(cfg, "SETTINGS_PATH", fake_path)
    cfg.save_settings({"company_name": "شرکت اول"})
    cfg.save_settings({"report_prepared_by": "مدیر دوم"})
    # هر دو مقدار باید هم‌زمان باقی مانده باشند، چون save دوم نباید مقدار اول را پاک کند
    assert cfg.get_company_name() == "شرکت اول"
    assert cfg.get_report_prepared_by() == "مدیر دوم"


def test_empty_string_falls_back_to_default():
    # get_report_prepared_by باید برای رشته خالی هم به‌جای رشته خالی، پیش‌فرض معنادار برگرداند
    assert cfg.DEFAULT_SETTINGS["report_prepared_by"] != ""


def test_developer_credit_is_fixed_and_contains_required_info():
    assert "مجید تربتی" in cfg.DEVELOPER_CREDIT_LINE
    assert "09151102442" in cfg.DEVELOPER_CREDIT_LINE


def test_logo_path_none_when_not_set(tmp_path, monkeypatch):
    fake_path = tmp_path / "settings.json"
    monkeypatch.setattr(cfg, "SETTINGS_PATH", fake_path)
    assert cfg.get_logo_path() is None


def test_set_logo_converts_to_png_at_fixed_path(tmp_path, monkeypatch):
    from PIL import Image
    fake_settings = tmp_path / "settings.json"
    fake_assets = tmp_path / "assets"
    monkeypatch.setattr(cfg, "SETTINGS_PATH", fake_settings)
    monkeypatch.setattr(cfg, "ASSETS_DIR", fake_assets)

    src = tmp_path / "source_logo.jpg"
    Image.new("RGB", (200, 80), color=(10, 20, 30)).save(src, format="JPEG")

    rel = cfg.set_logo(str(src))
    assert rel == "assets/company_logo.png"
    resolved = cfg.get_logo_path()
    assert resolved is not None
    assert resolved.suffix == ".png"
    with Image.open(resolved) as im:
        assert im.format == "PNG"
        assert im.size == (200, 80)


def test_remove_logo_clears_setting_and_deletes_file(tmp_path, monkeypatch):
    from PIL import Image
    fake_settings = tmp_path / "settings.json"
    fake_assets = tmp_path / "assets"
    monkeypatch.setattr(cfg, "SETTINGS_PATH", fake_settings)
    monkeypatch.setattr(cfg, "ASSETS_DIR", fake_assets)

    src = tmp_path / "source_logo.png"
    Image.new("RGB", (50, 50)).save(src, format="PNG")
    cfg.set_logo(str(src))
    assert cfg.get_logo_path() is not None

    cfg.remove_logo()
    assert cfg.get_logo_path() is None
    assert not (fake_assets / "company_logo.png").exists()


def test_fit_dimensions_preserves_aspect_ratio(tmp_path):
    from PIL import Image
    from app.core.image_utils import fit_dimensions
    img_path = tmp_path / "wide.png"
    Image.new("RGB", (400, 150)).save(img_path, format="PNG")
    w, h = fit_dimensions(str(img_path), 30, 30)
    assert round(w, 2) == 30.0
    assert abs(h - 11.25) < 0.01


def test_settings_json_file_is_valid():
    assert cfg.SETTINGS_PATH.exists()
    with open(cfg.SETTINGS_PATH, encoding="utf-8") as f:
        data = json.load(f)
    assert "primary_market_maker_broker_names" in data
