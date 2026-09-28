import pathlib
import sys
import shutil

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core import custom_fonts as cf


def test_returns_none_when_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(cf, "ASSETS_DIR", tmp_path)
    assert cf.find_titr_font() is None
    assert cf.find_nazanin_font() is None
    assert cf.find_nazanin_bold_font() is None


def test_finds_file_when_present_with_exact_name(tmp_path, monkeypatch):
    monkeypatch.setattr(cf, "ASSETS_DIR", tmp_path)
    (tmp_path / "BTitr.ttf").write_bytes(b"fake ttf content")
    found = cf.find_titr_font()
    assert found is not None
    assert found.name == "BTitr.ttf"


def test_finds_file_with_alternate_naming_variant(tmp_path, monkeypatch):
    monkeypatch.setattr(cf, "ASSETS_DIR", tmp_path)
    (tmp_path / "B-Nazanin.ttf").write_bytes(b"fake ttf content")
    found = cf.find_nazanin_font()
    assert found is not None
    assert found.name == "B-Nazanin.ttf"


def test_does_not_confuse_titr_and_nazanin(tmp_path, monkeypatch):
    monkeypatch.setattr(cf, "ASSETS_DIR", tmp_path)
    (tmp_path / "BTitr.ttf").write_bytes(b"x")
    assert cf.find_nazanin_font() is None
    assert cf.find_titr_font() is not None
