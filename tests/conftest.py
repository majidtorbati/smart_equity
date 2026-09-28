"""Test bootstrap.

بخشی از تست‌های تحلیلی به دیتابیس واقعی واردشده از Excel نیاز دارند. در build تمیز،
نبود داده نباید باعث شود PyInstaller متوقف شود؛ در صورت وجود DB همه تست‌های داده‌ای اجرا می‌شوند.
"""
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "smart_equity.db"


def pytest_collection_modifyitems(config, items):
    if DB_PATH.exists():
        return
    skip = pytest.mark.skip(reason="تست داده‌محور است؛ برای اجرای کامل، ابتدا فایل‌های Excel را Import کنید.")
    for item in items:
        if "DB_PATH" in getattr(item.module, "__dict__", {}):
            item.add_marker(skip)
