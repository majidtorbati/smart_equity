# PROJECT_STATE — SmartEquity

آخرین به‌روزرسانی: 1405 (Phase 0 — Audit) | نویسنده: Claude (Senior Software Architect role)

## هدف پروژه
نرم‌افزار دسکتاپ پرتابل (PySide6، بدون نیاز به نصب Python/اینترنت روی ویندوز) که معاملات خرد یک نماد
بورسی را از اکسل خروجی سامانه معاملاتی وارد می‌کند، تحلیل می‌کند، و گزارش PDF/Excel/PPTX برای هیئت‌مدیره
تولید می‌کند. **در حال گسترش** (این نسخه از master prompt) به یک سیستم کامل:
Shareholder Registry + Opening/Closing Inventory + FIFO Realized/Unrealized P/L + Reconciliation +
New/Exited Shareholders + گزارش مدیریتی حرفه‌ای Dynamic.

## معماری فعلی (خلاصه — جزئیات در ARCHITECTURE.md)
```
Excel خام (Book2.xlsx‑شکل، معاملات) → Import Engine → SQLite (transactions/persons/brokers/symbols)
                                                              → Analytics/Detection → UI + Excel/PDF/PPTX
```
هر Import، دیتابیس قبلی را **کامل جایگزین** می‌کند (نه Append). با بستن برنامه، DB پاک می‌شود.

## مسیر فایل‌های مهم
- Entry point: `app/main.py` → `app/ui/main_window.py:main()`
- Import: `app/data/import_engine.py` (تابع `import_excel(xlsx_path, db_path, column_map=None)`)
- Schema: `app/data/schema.sql`
- Analytics: `app/analytics/{metrics,market_maker,comparison,extended_analysis,insights}.py`
- Detection: `app/detection/{anomaly,behavior}.py`
- Export: `app/export/{excel_report,pdf_report,pptx_report}.py`
- Settings: `app/config/settings.py` + `config/settings.json`
- Build: `build.spec` (PyInstaller) + `build.bat`
- Tests: `tests/*.py` (pytest، ۷۹ تست)

## دیتابیس فعلی (جزئیات کامل در DATABASE_SCHEMA.md)
جداول موجود: `import_batches, symbols, brokers, persons, transactions, data_quality, analysis_cache, alerts`
**هنوز وجود ندارد** (باید در Phase 2+ اضافه شود): `shareholder_registry` (موجودی ابتدای دوره)،
`fifo_lots`, `fifo_matches`, `portfolio_positions`, `reconciliation`.

## قابلیت‌های موجود (کامل و تست‌شده)
- Import اکسل معاملات با نرمال‌سازی نام/تاریخ شمسی، تشخیص رکورد تکراری (نه حذف، فقط پرچم‌گذاری)
- KPI Dashboard، مقایسه با بازه قبل، تحلیل بازارگردان (بر اساس لیست صریح در settings)
- خریداران/فروشندگان برتر، تمرکز HHI، رفتار کوتاه‌مدت (نوسان‌گیری هم‌روز)، تشخیص ناهنجاری آماری
- تحلیل بنیادی/کیفی/ارزش‌گذاری با اعلام صریح کمبود داده (بدون جعل عدد)
- خروجی همزمان Excel/PDF/PPTX از یک Analytics Result مشترک
- صفحه تنظیمات (نام شرکت، بازارگردان، لوگو، تهیه‌کننده گزارش)
- جستجو در جداول UI

## قابلیت‌های جدید مورد نیاز (این نسخه — هنوز پیاده‌سازی نشده)
Registry سهامداران (موجودی اول دوره از فایل مثل `900000.xlsx`) → Ledger واقعی → FIFO Engine →
Realized/Unrealized P/L → New/Exited Shareholders → Reconciliation → گزارش‌های جدید مرتبط
(جزئیات کامل در FEATURES.md، فاز‌بندی در DECISIONS.md/CURRENT_TASK.md)

## داده‌های نمونه موجود در این نشست
- `/mnt/user-data/uploads/book2.xlsx` — معاملات نماد «آباد»، شیت `Deals`، **۲۹٬۸۹۱ ردیف** (توجه: نسخه قبلی
  مستندات از ۱۲٬۸۶۰ ردیف صحبت می‌کرد؛ این فایل جدید/به‌روزتر است یا بازه زمانی متفاوتی دارد — تعداد تکراری‌های
  تشخیص‌داده‌شده هم بر همین اساس فرق می‌کند، نه یک باگ)
- `/mnt/user-data/uploads/900000.xlsx` — دقیقاً همان چیزی که Master Prompt به‌عنوان «Shareholder Registry»
  توصیف کرده: ستون‌های شماره سهامدار، نام، نام‌خانوادگی، کد ملی، **تعداد سهم اول دوره / خریداری‌شده /
  فروخته‌شده / پایان دوره**. این فایل ورودی Phase 2 خواهد بود.

## وضعیت تست / Build
- ۷۹ تست pytest؛ در این نشست با DB ساخته‌شده از `book2.xlsx`: **75 passed, 4 failed**
  (۴ خطا صرفاً به‌دلیل مسیر حروف بزرگ/کوچک فایل نمونه و اعداد hardcode شده مرتبط با فایل قدیمی‌تر است —
  جزئیات در TEST_STATUS.md — **رگرسیون واقعی نیستند**)
- Build (PyInstaller) فقط روی ویندوز قابل اجراست؛ در این محیط لینوکسی تست نشد (طبیعی است)

## مشکلات باز / ریسک‌های شناخته‌شده
جزئیات کامل در بخش «Current Risks» گزارش Audit و در DECISIONS.md
