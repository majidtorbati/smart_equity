"""
تشخیص فونت‌های اختیاری B Titr / B Nazanin در پوشه assets.

این دو فونت (برخلاف Vazirmatn که در همین پروژه استفاده و Embed شده) متن‌باز نیستند و مجوز توزیع
آزاد ندارند؛ بنابراین در این پروژه دانلود/جاسازی نمی‌شوند. اما چون روی اغلب ویندوزهای فارسی از قبل
نصب هستند، اگر کاربر خودش فایل .ttf آن‌ها را (که احتمالاً از قبل به‌صورت قانونی در اختیار دارد) در
پوشه assets قرار دهد، برنامه به‌طور خودکار آن‌ها را به‌جای Vazirmatn برای گزارش PDF استفاده می‌کند.
برای PPTX و رابط کاربری نیازی به فایل نیست: کافی است این فونت‌ها روی سیستم اجراکننده نصب باشند
(که در بیشتر موارد همین‌طور است)؛ در غیر این صورت PowerPoint/Qt به‌طور خودکار جایگزین می‌کنند.
"""
from __future__ import annotations
import pathlib

ASSETS_DIR = pathlib.Path(__file__).resolve().parents[2] / "assets"

HEADER_FONT_DISPLAY_NAME = "B Titr"
BODY_FONT_DISPLAY_NAME = "B Nazanin"

_TITR_CANDIDATES = ["BTitr.ttf", "B-Titr.ttf", "B Titr.ttf", "BTITR.TTF", "btitr.ttf", "B_Titr.ttf"]
_NAZANIN_CANDIDATES = ["BNazanin.ttf", "B-Nazanin.ttf", "B Nazanin.ttf", "BNAZANIN.TTF",
                       "bnazanin.ttf", "B_Nazanin.ttf"]
_NAZANIN_BOLD_CANDIDATES = ["BNazaninBold.ttf", "B Nazanin Bold.ttf", "B-Nazanin-Bold.ttf",
                            "BNazanin-Bold.ttf", "BNAZANINBOLD.TTF"]


def _find(candidates: list[str]) -> pathlib.Path | None:
    for name in candidates:
        p = ASSETS_DIR / name
        if p.exists():
            return p
    return None


def find_titr_font() -> pathlib.Path | None:
    return _find(_TITR_CANDIDATES)


def find_nazanin_font() -> pathlib.Path | None:
    return _find(_NAZANIN_CANDIDATES)


def find_nazanin_bold_font() -> pathlib.Path | None:
    return _find(_NAZANIN_BOLD_CANDIDATES)
