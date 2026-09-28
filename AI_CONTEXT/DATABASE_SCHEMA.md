# DATABASE_SCHEMA — SmartEquity

منبع حقیقت: `app/data/schema.sql` (همیشه همان فایل را چک کن، این سند فقط خلاصه است)

## جداول موجود (Phase 0)
- **import_batches** — batch_id, source_file, imported_at, n_rows_raw/imported/duplicate/rejected, notes
- **symbols** — symbol_id, symbol_code(UNIQUE), symbol_name
- **brokers** — broker_id, broker_code, broker_name_raw, broker_name_key(UNIQUE), is_market_maker
- **persons** — person_id, national_id(UNIQUE), name_raw, name_key, person_type, shareholder_code,
  identifier_confidence (high=کد ملی موجود / low=فقط نام)
- **transactions** — transaction_id, declaration_no, trade_date_jalali, trade_date_gregorian,
  symbol_id, buyer_person_id, seller_person_id, buyer_broker_id, seller_broker_id, quantity, price,
  value, is_duplicate_of (نه حذف، فقط پرچم روی رکورد تکراری اصلی), source_row_index, import_batch_id
  (ایندکس روی date/symbol/buyer/seller/brokers/declaration)
- **data_quality** — batch_id, metric_name, metric_value
- **analysis_cache** — cache_key(PK), computed_at, payload_json
- **alerts** — alert_id, created_at, severity, risk_score, alert_type, trade_date_gregorian, symbol_id,
  person_id, broker_id, value, reason, supporting_transaction_ids(JSON)

## جداول موردنیاز برای Master Prompt جدید (هنوز ایجاد نشده — Phase 2+)
```sql
-- موجودی اول دوره، از فایلی مثل 900000.xlsx — هر Import این جدول را Replace می‌کند (مثل transactions)
CREATE TABLE shareholder_registry (
    registry_id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id INTEGER REFERENCES persons(person_id),
    shareholder_code TEXT,          -- «شماره سهامدار» ستون فایل 900000.xlsx
    national_id TEXT,
    opening_quantity INTEGER NOT NULL,
    opening_date_jalali TEXT,
    -- مقادیر خود فایل (خریداری‌شده/فروخته‌شده/پایان‌دوره طبق منبع رسمی) برای Reconciliation:
    official_purchased_qty INTEGER,
    official_sold_qty INTEGER,
    official_closing_qty INTEGER,
    import_batch_id INTEGER REFERENCES import_batches(batch_id)
);

-- Lotهای خرید FIFO (هم Opening به‌صورت Lot مصنوعی، هم هر خرید واقعی)
CREATE TABLE fifo_lots (
    lot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id INTEGER REFERENCES persons(person_id),
    source_type TEXT,               -- 'opening' | 'purchase'
    source_transaction_id INTEGER REFERENCES transactions(transaction_id),  -- NULL اگر opening
    trade_date_gregorian TEXT,
    original_quantity INTEGER NOT NULL,
    remaining_quantity INTEGER NOT NULL,
    unit_cost REAL NOT NULL
);

-- نتیجه match هر فروش با یک یا چند Lot
CREATE TABLE fifo_matches (
    match_id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_transaction_id INTEGER REFERENCES transactions(transaction_id),
    lot_id INTEGER REFERENCES fifo_lots(lot_id),
    matched_quantity INTEGER NOT NULL,
    sale_price REAL NOT NULL,
    cost_basis REAL NOT NULL,        -- matched_quantity * unit_cost آن Lot
    realized_pnl REAL NOT NULL
);

-- Snapshot محاسبه‌شده نهایی هر سهامدار (cache نتیجه، قابل بازسازی از ledger — منبع حقیقت نیست)
CREATE TABLE portfolio_positions (
    person_id INTEGER PRIMARY KEY REFERENCES persons(person_id),
    opening_quantity INTEGER,
    purchased_quantity INTEGER,
    sold_quantity INTEGER,
    closing_quantity INTEGER,
    fifo_remaining_cost REAL,
    realized_pnl REAL,
    unrealized_pnl REAL,             -- NULL اگر قیمت ارزش‌گذاری موجود نباشد
    insufficient_inventory_flag INTEGER DEFAULT 0
);

CREATE TABLE reconciliation_results (
    person_id INTEGER REFERENCES persons(person_id),
    registry_opening INTEGER,
    calculated_closing INTEGER,
    official_closing INTEGER,        -- از فایل Registry، اگر موجود
    difference INTEGER,
    status TEXT                      -- 'ok' | 'mismatch' | 'insufficient_data'
);
```

⚠️ قبل از اجرای هر Migration، این فایل را با `app/data/schema.sql` واقعی مقایسه کن — اگر Task قبلی این
جداول را اضافه کرده، این بخش را به‌روزرسانی کن تا کپی تکراری ساخته نشود (طبق قانون ۳۶ Master Prompt).
