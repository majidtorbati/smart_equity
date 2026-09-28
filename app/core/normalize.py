"""
نرمال‌سازی رشته‌های فارسی: حذف نیم‌فاصله اضافی، یکسان‌سازی حروف عربی/فارسی،
حذف کاراکترهای نامرئی، و تمیزکاری برای مقایسه صحیح نام‌ها/کارگزاران.

مهم: نسخه Normalize فقط برای «مقایسه و گروه‌بندی» استفاده می‌شود.
مقدار نمایشی اصلی (raw) همیشه هم نگه داشته می‌شود تا داده اصلی گم نشود.
"""
import re
import unicodedata

ZERO_WIDTH_CHARS = ["\u200c", "\u200b", "\u200d", "\u200e", "\u200f", "\ufeff"]
ARABIC_TO_PERSIAN = {
    "ي": "ی",
    "ك": "ک",
    "ة": "ه",
    "ۀ": "ه",
    "أ": "ا",
    "إ": "ا",
    "ؤ": "و",
}


def clean_display(raw: str) -> str:
    """پاک‌سازی سبک برای نمایش: فقط کاراکترهای نامرئی مشکل‌ساز حذف می‌شوند، خوانایی حفظ می‌شود."""
    if raw is None:
        return ""
    s = str(raw)
    for ch in ["\u200b", "\u200d", "\u200e", "\u200f", "\ufeff"]:
        s = s.replace(ch, "")
    # replace ZWNJ with a normal space only if it's between two words separated originally
    s = s.replace("\u200c", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def normalize_key(raw: str) -> str:
    """
    نسخه‌ی یکسان‌سازی‌شده برای مقایسه/گروه‌بندی (Entity matching).
    حروف عربی -> فارسی، حذف همه فاصله‌ها، حذف اعراب، lower نیست چون فارسی است.
    """
    if raw is None:
        return ""
    s = str(raw)
    s = unicodedata.normalize("NFKC", s)
    for ch in ZERO_WIDTH_CHARS:
        s = s.replace(ch, "")
    for a, p in ARABIC_TO_PERSIAN.items():
        s = s.replace(a, p)
    s = re.sub(r"[\s\u00A0]+", "", s)  # remove all whitespace for key matching
    s = re.sub(r"[\.\-_/]", "", s)
    return s.strip()


if __name__ == "__main__":
    samples = [
        "مشتری‌الکترونیکی‌مفید2-مفید",
        "مشتری الکترونیکی مفید2-مفید",
        "پاشااوغلی‌",
    ]
    for s in samples:
        print(repr(s), "-> display:", repr(clean_display(s)), "| key:", repr(normalize_key(s)))
