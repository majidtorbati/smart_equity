"""محاسبه ابعاد متناسب (حفظ نسبت تصویر) برای جاسازی لوگو/تصویر در گزارش‌ها."""
from __future__ import annotations
import pathlib


def fit_dimensions(image_path, max_w: float, max_h: float) -> tuple[float, float]:
    """
    ابعاد نهایی (w, h) را طوری محاسبه می‌کند که تصویر داخل کادر max_w × max_h جا شود
    بدون کش‌آمدگی (نسبت تصویر اصلی حفظ می‌شود). واحد ورودی/خروجی یکسان و دلخواه است
    (mm برای PDF، EMU برای PPTX، پیکسل برای Excel — فقط باید max_w/max_h با همان واحد داده شوند).
    """
    from PIL import Image
    with Image.open(image_path) as im:
        iw, ih = im.size
    ratio = min(max_w / iw, max_h / ih)
    return iw * ratio, ih * ratio
