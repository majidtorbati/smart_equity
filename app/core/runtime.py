"""مسیرهای امن برای اجرای توسعه‌ای و نسخه EXE پرتابل."""
from __future__ import annotations
import pathlib
import sys


def runtime_root() -> pathlib.Path:
    """پوشه‌ای که دیتابیس، تنظیمات، خروجی‌ها و فایل‌های کاربر باید در آن ذخیره شوند."""
    if getattr(sys, "frozen", False):
        return pathlib.Path(sys.executable).resolve().parent
    return pathlib.Path(__file__).resolve().parents[2]


def resource_root() -> pathlib.Path:
    """ریشه منابع read-only بسته‌شده توسط PyInstaller."""
    if getattr(sys, "_MEIPASS", None):
        return pathlib.Path(sys._MEIPASS).resolve()
    return runtime_root()
