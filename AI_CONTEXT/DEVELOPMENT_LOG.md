# DEVELOPMENT_LOG (خلاصه، جدیدترین بالا)

## Phase 0.1 — رفع دو تست شکننده (تصمیمات کاربر به Claude واگذار شد)
- `tests/test_import_replace.py`: مسیر فایل نمونه حالا هم `Book2.xlsx` هم `book2.xlsx` را می‌پذیرد.
- `tests/test_metrics.py`: عدد hardcode شده `1787` حذف و به‌جای آن سازگاری داخلی چک می‌شود.
- Unrealized P/L: تصمیم شد فعلاً «اطلاعات کافی نیست» نمایش داده شود (بدون منبع قیمت پایانی).
- نتیجه تست پس از تغییر: **78 passed, 1 failed** (فقط `test_close_event_clears_database`، پیش از این
  هم fail بود، بی‌ربط به این تغییرات — جزئیات در TEST_STATUS.md).
- DONE: Files changed: `tests/test_import_replace.py`, `tests/test_metrics.py` | Tests: 78/79 |
  Build: تست نشد | Warnings: هیچ | Next Task: Phase 1 — Registry Import

## Phase 0 — Audit + AI_CONTEXT Setup
- محیط جدید (چت جدید) بود؛ پروژه از `SmartEquity_Project__1_.zip` که کاربر آپلود کرد بازیابی شد.
- کاربر دو فایل اکسل جدید هم داد: `book2.xlsx` (معاملات، ۲۹٬۸۹۱ ردیف) و `900000.xlsx` (Shareholder
  Registry — دقیقاً همان چیزی که Master Prompt جدید نیاز دارد).
- DB از `book2.xlsx` ساخته شد (`import_excel`)؛ ۲۹٬۸۹۱ ردیف، ۵٬۳۰۳ خریدار یکتا، ۲۰۳ کارگزار یکتا، صفر رد.
- تست کامل اجرا شد: 75 passed / 4 failed (تحلیل کامل در TEST_STATUS.md — هیچ‌کدام رگرسیون واقعی نیست).
- ساختار AI_CONTEXT/ ایجاد شد (این ۸ فایل).
- **هیچ کد تولیدی (app/) در این Phase تغییر نکرد** — طبق دستور صریح کاربر که فقط Audit انجام شود.

### DONE
Files changed: هیچ فایل تولیدی (فقط AI_CONTEXT/*.md جدید)
Tests: 75 passed, 4 failed (تحلیل‌شده، غیر رگرسیونی)
Build: تست نشد (نیاز به ویندوز)
Warnings: تست‌های #2 نیاز به تصمیم کاربر درباره داده نمونه دارند
Next Task: Phase 1 — Shareholder Registry Import (جزئیات در CURRENT_TASK.md)
