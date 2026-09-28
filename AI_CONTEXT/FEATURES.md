# FEATURES — موجود vs جدید

## موجود (کامل، تست‌شده — Phase 0)
- [x] Import اکسل معاملات (Replace کامل، تشخیص تکراری، نرمال‌سازی)
- [x] Dashboard KPI
- [x] مقایسه با بازه قبل (Comparison)
- [x] تحلیل بازارگردان (بر اساس لیست صریح Settings) — نکته: هنوز «Dynamic hide اگر فعالیت صفر» طبق
      Master Prompt جدید بخش ۲۷ **پیاده‌سازی نشده** — باید بررسی و اضافه شود (فعلاً معلوم نیست جدول خالی
      نشان داده می‌شود یا نه؛ باید در Phase مربوطه چک شود)
- [x] خریداران/فروشندگان برتر، HHI
- [x] رفتار کوتاه‌مدت / نوسان‌گیری هم‌روز
- [x] تشخیص ناهنجاری آماری (با نام طرفین معامله)
- [x] تحلیل بنیادی/کیفی/ارزش‌گذاری (بدون جعل عدد در نبود داده)
- [x] Export همزمان Excel/PDF/PPTX از یک Analytics Result
- [x] صفحه تنظیمات + لوگو
- [x] جستجو در جداول
- [ ] فونت B Titr/B Nazanin — زیرساخت هست، اتصال کامل نیمه‌کاره (بدهی فنی قدیمی، جدا از این Master Prompt)

## جدید — طبق Master Prompt این نشست (هیچ‌کدام هنوز پیاده‌سازی نشده)
- [ ] Shareholder Registry Import (با Column Mapping قابل‌تنظیم)
- [ ] موجودی ابتدای دوره per سهامدار
- [ ] Transaction Ledger واقعی (Opening/Purchase/Sale/Adjustment/Closing per person)
- [ ] کنترل موجودی منفی → «Insufficient Inventory» به‌جای منفی خام (بدون حذف/اصلاح خودکار داده)
- [ ] FIFO Engine مستقل (`fifo_engine.py`) + ۱۳ تست اجباری (بخش ۳۹ Master Prompt)
- [ ] Realized P/L (Profit/Loss/Net) per سهامدار
- [ ] Unrealized P/L (فقط اگر قیمت ارزش‌گذاری موجود باشد؛ وگرنه پیام صریح کمبود داده)
- [ ] Reconciliation (Registry+Transactions vs Calculated vs Official Closing، با گزارش اختلاف)
- [ ] New Shareholders / Exited Shareholders / Active / Inactive (با آستانه‌های قابل‌تنظیم، نه Hard-code)
- [ ] گزارش‌های جدید: Top Shareholders, Top Buyers, Top Sellers, New Shareholders, FIFO P/L,
      Individual Shareholder Detail
- [ ] گزارش مدیریتی PDF Dynamic (بخش‌های بدون داده حذف شوند، نه جدول خالی/صفر)
- [ ] Excel جدید با Sheetهای اضافه: Shareholders, Portfolio, FIFO P&L, New/Exited, Reconciliation
- [ ] Audit Trail کامل برای هر Import (شامل Registry) + Transaction Unique ID برای جلوگیری از دوبار ثبت
- [ ] Anomaly جدید: تغییرات شدید مالکیت (بیشترین افزایش/کاهش، خرید/فروش سنگین) با آستانه قابل‌تنظیم

## فاز‌بندی پیشنهادی (مطابق بخش ۵۶ Master Prompt، تطبیق‌یافته با وضعیت واقعی پروژه)
Phase 0 (این پیام) ✅ Audit + Context → Phase 1 Registry Import + Column Mapping → Phase 2 Ledger/Portfolio
Engine → Phase 3 FIFO Engine + تست‌ها → Phase 4 New/Exited/Active/Inactive → Phase 5 Reconciliation →
Phase 6 گزارش‌های جدید (Excel Sheets) → Phase 7 PDF Dynamic (حذف بخش بی‌داده، شامل قانون Market Maker) →
Phase 8 Dashboard/UI جدید (صفحات Registry/Portfolio/FIFO/Reconciliation) → Phase 9 Regression کامل →
Phase 10 Build Portable

جزئیات فاز جاری همیشه در CURRENT_TASK.md، نه اینجا.
