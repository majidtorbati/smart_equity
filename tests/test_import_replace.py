import sqlite3
import pathlib
import sys
import shutil
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.data.import_engine import import_excel

def _find_upload_xlsx() -> pathlib.Path:
    """نام فایل نمونه بین سشن‌ها ممکن است با حروف بزرگ/کوچک متفاوت آپلود شود (Book2.xlsx یا book2.xlsx)."""
    uploads_dir = pathlib.Path("/mnt/user-data/uploads")
    for candidate in ("Book2.xlsx", "book2.xlsx"):
        p = uploads_dir / candidate
        if p.exists():
            return p
    matches = list(uploads_dir.glob("[Bb]ook2.xlsx")) if uploads_dir.exists() else []
    return matches[0] if matches else uploads_dir / "Book2.xlsx"


UPLOAD_XLSX = _find_upload_xlsx()


def test_reimport_replaces_not_appends(tmp_path):
    """
    باگ واقعی گزارش‌شده توسط کاربر: Import یک فایل دوم نباید به داده فایل اول اضافه شود،
    وگرنه معاملات دو شرکت مختلف با هم قاطی و تحلیل نهایی غلط می‌شود.
    """
    if not UPLOAD_XLSX.exists():
        pytest.skip("فایل نمونه Book2.xlsx در محیط تست موجود نیست")
    db_path = str(tmp_path / "test.db")

    result1 = import_excel(str(UPLOAD_XLSX), db_path)
    conn = sqlite3.connect(db_path)
    n_after_first = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    n_batches_after_first = conn.execute("SELECT COUNT(*) FROM import_batches").fetchone()[0]
    conn.close()
    assert n_after_first == result1["n_rows_imported"]
    assert n_batches_after_first == 1

    # وارد کردن دوباره همان فایل (شبیه‌سازی وارد کردن یک فایل دوم) — نتیجه باید دقیقاً
    # همان تعداد سطر باشد، نه دو برابر (که نشانه‌ی append اشتباه به‌جای replace می‌بود).
    result2 = import_excel(str(UPLOAD_XLSX), db_path)
    conn = sqlite3.connect(db_path)
    n_after_second = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    n_batches_after_second = conn.execute("SELECT COUNT(*) FROM import_batches").fetchone()[0]
    conn.close()

    assert n_after_second == result2["n_rows_imported"]
    assert n_after_second == n_after_first  # نه دو برابر
    assert n_batches_after_second == 1  # نه ۲ batch تجمیع‌شده


def test_reimport_with_different_symbol_does_not_mix(tmp_path):
    """
    شبیه‌سازی دقیق‌تر مشکل گزارش‌شده: یک فایل با نماد متفاوت وارد شود، دیتابیس باید
    فقط همان نماد جدید را داشته باشد، نه نماد قبلی به‌علاوه‌ی جدید.
    """
    import pandas as pd
    if not UPLOAD_XLSX.exists():
        pytest.skip("فایل نمونه Book2.xlsx در محیط تست موجود نیست")
    db_path = str(tmp_path / "test.db")

    import_excel(str(UPLOAD_XLSX), db_path)
    conn = sqlite3.connect(db_path)
    symbols_after_first = [r[0] for r in conn.execute("SELECT symbol_code FROM symbols")]
    conn.close()
    assert symbols_after_first == ["آباد"]

    # فایل دومی با نماد متفاوت می‌سازیم (کپی از داده واقعی با نماد جایگزین)
    df = pd.read_excel(str(UPLOAD_XLSX), engine="openpyxl")
    df["نماد"] = "نماد_دوم"
    df["نام نماد"] = "شرکت آزمایشی دوم"
    second_file = tmp_path / "second_company.xlsx"
    df.to_excel(second_file, index=False)

    import_excel(str(second_file), db_path)
    conn = sqlite3.connect(db_path)
    symbols_after_second = [r[0] for r in conn.execute("SELECT symbol_code FROM symbols")]
    conn.close()

    assert symbols_after_second == ["نماد_دوم"]  # نه هر دو نماد با هم
    assert "آباد" not in symbols_after_second
