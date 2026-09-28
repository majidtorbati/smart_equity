"""
مدیریت فونت‌های نصب‌شده Windows برای SmartEquity.
"""

from __future__ import annotations

import os
import pathlib
import winreg

from PySide6.QtGui import QFontDatabase


WINDOWS_FONTS_DIR = pathlib.Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"


def installed_font_families() -> list[str]:
    """فهرست خانواده فونت‌های نصب‌شده در Windows را برمی‌گرداند."""
    try:
        families = QFontDatabase.families()
        return sorted(
            {str(name).strip() for name in families if str(name).strip()},
            key=str.casefold,
        )
    except Exception:
        return []


def find_font_file(font_family: str) -> pathlib.Path | None:
    """
    مسیر فایل فونت نصب‌شده را بر اساس نام خانواده پیدا می‌کند.

    این تابع به فونت‌های خاص پروژه محدود نیست و از رجیستری Windows
    برای پیدا کردن فایل واقعی فونت استفاده می‌کند.
    """
    target = str(font_family).strip().casefold()
    if not target:
        return None

    registry_locations = [
        (winreg.HKEY_LOCAL_MACHINE,
         r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts"),
        (winreg.HKEY_CURRENT_USER,
         r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts"),
    ]

    for root, key_path in registry_locations:
        try:
            with winreg.OpenKey(root, key_path) as key:
                count = winreg.QueryInfoKey(key)[1]

                for index in range(count):
                    try:
                        value_name, value_data, _ = winreg.EnumValue(key, index)
                    except OSError:
                        continue

                    name_without_style = str(value_name)

                    # مثال:
                    # Arial (TrueType)
                    # B Nazanin (TrueType)
                    if "(" in name_without_style:
                        name_without_style = name_without_style.split(
                            "(", 1
                        )[0].strip()

                    # بعضی نام‌ها شامل Style هستند.
                    normalized = name_without_style.casefold()

                    if (
                        normalized == target
                        or target in normalized
                        or normalized in target
                    ):
                        path = pathlib.Path(str(value_data))

                        if not path.is_absolute():
                            path = WINDOWS_FONTS_DIR / path

                        if path.exists():
                            return path

        except (OSError, PermissionError):
            continue

    return _search_font_file_by_filename(font_family)


def _search_font_file_by_filename(font_family: str) -> pathlib.Path | None:
    """Fallback برای زمانی که رجیستری نام فونت را دقیق برنگرداند."""
    if not WINDOWS_FONTS_DIR.exists():
        return None

    target = "".join(
        ch.lower()
        for ch in str(font_family)
        if ch.isalnum()
    )

    if not target:
        return None

    try:
        for path in WINDOWS_FONTS_DIR.iterdir():
            if path.suffix.lower() not in {".ttf", ".otf", ".ttc"}:
                continue

            stem = "".join(
                ch.lower()
                for ch in path.stem
                if ch.isalnum()
            )

            if target in stem or stem in target:
                return path

    except (OSError, PermissionError):
        pass

    return None


def font_is_installed(font_family: str) -> bool:
    """بررسی وجود یک خانواده فونت در Windows."""
    return str(font_family).strip().casefold() in {
        name.casefold() for name in installed_font_families()
    }


def default_heading_font() -> str:
    """فونت پیش‌فرض تیتر."""
    families = installed_font_families()

    for candidate in ("Vazirmatn", "Tahoma", "Arial"):
        if candidate.casefold() in {x.casefold() for x in families}:
            return candidate

    return families[0] if families else "Tahoma"


def default_body_font() -> str:
    """فونت پیش‌فرض متن."""
    families = installed_font_families()

    for candidate in ("Vazirmatn", "Tahoma", "Arial"):
        if candidate.casefold() in {x.casefold() for x in families}:
            return candidate

    return families[0] if families else "Tahoma"