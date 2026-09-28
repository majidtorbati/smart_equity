"""آماده‌سازی متن فارسی برای رسم صحیح (reshape + bidi) در reportlab و matplotlib."""
import arabic_reshaper
from bidi.algorithm import get_display


def fa(text) -> str:
    if text is None:
        return ""
    reshaped = arabic_reshaper.reshape(str(text))
    return get_display(reshaped)
