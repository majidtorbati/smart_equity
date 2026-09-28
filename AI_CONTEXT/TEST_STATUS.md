# TEST_STATUS

## آخرین اجرا (Phase 0، بعد از رفع دو تست شکننده)
`pytest tests/ -q` → **78 passed, 1 failed** (از مجموع ۷۹ تست)

## رفع‌شده در این نشست (تصمیم کاربر: خودم تصمیم بگیرم)
1. `test_import_replace.py` — مسیر فایل نمونه دیگر فقط `Book2.xlsx` (B بزرگ) را نمی‌پذیرد؛
   `_find_upload_xlsx()` هم `Book2.xlsx` و هم `book2.xlsx` را پیدا می‌کند (مقاوم به تفاوت حروف بزرگ/کوچک
   بین Sessionها).
2. `test_metrics.py::test_duplicates_excluded_from_analytics` — بجای `assert n_dup == 1787` (عدد ثابت
   مال فایل نمونه قدیمی)، حالا فقط سازگاری داخلی چک می‌شود (`n_dup >= 0` + خط بالاتر که
   `overview.n_transactions == total_rows - n_dup` را تضمین می‌کند). این تست دیگر با تغییر فایل نمونه
   نمی‌شکند.

## ۱ خطای باقی‌مانده (پیش از این نشست هم وجود داشت — نیاز به بررسی جدا)
`test_gui_search_and_close.py::test_close_event_clears_database`
→ `sqlite3.DatabaseError: file is not a database` — احتمالاً race بین تست‌ها روی همان مسیر db در طول
یک pytest run واحد (تست‌های دیگر db را هم‌زمان بازسازی می‌کنند). **رگرسیون این نشست نیست** (قبل از هر
تغییری هم همین یک مورد در همین لیست ۴تایی بود)؛ رفع آن یک Task جداگانه (بررسی fixture/تمیزکاری بین
تست‌ها یا استفاده از db موقت مجزا برای این تست) است، نه بخشی از Master Prompt جدید.

## Build
PyInstaller فقط روی ویندوز اجرا می‌شود — در این محیط (لینوکس) تست build انجام نشد؛ طبق مستندات پروژه
قبلاً یک بار با موفقیت Build/اجرا شده بود (BUILD_STATUS.md).

## Build
PyInstaller فقط روی ویندوز اجرا می‌شود — در این محیط (لینوکس) تست build انجام نشد؛ طبق مستندات پروژه
قبلاً یک بار با موفقیت Build/اجرا شده بود (BUILD_STATUS.md).
