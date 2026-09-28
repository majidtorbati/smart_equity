-- Smart Equity Transaction Intelligence — Database Schema

CREATE TABLE IF NOT EXISTS import_batches (
    batch_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file TEXT NOT NULL,
    imported_at TEXT NOT NULL,
    n_rows_raw INTEGER,
    n_rows_imported INTEGER,
    n_rows_duplicate INTEGER,
    n_rows_rejected INTEGER,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS symbols (
    symbol_id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol_code TEXT UNIQUE NOT NULL,
    symbol_name TEXT
);

CREATE TABLE IF NOT EXISTS brokers (
    broker_id INTEGER PRIMARY KEY AUTOINCREMENT,
    broker_code TEXT,
    broker_name_raw TEXT,
    broker_name_key TEXT UNIQUE NOT NULL,
    is_market_maker INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS persons (
    person_id INTEGER PRIMARY KEY AUTOINCREMENT,
    national_id TEXT UNIQUE,          -- کد/شناسه ملی (primary identifier when present)
    name_raw TEXT,
    name_key TEXT,
    first_name TEXT,                  -- نام
    family_name TEXT,                 -- نام خانوادگی
    person_type TEXT,                 -- حقیقی ایرانی / حقوقی ایرانی
    sejam_code TEXT,                 -- کد خریدار / کد فروشنده
    shareholder_code TEXT,            -- legacy: کدشسا، فقط برای سازگاری با بخش‌های قدیمی
    identifier_confidence TEXT DEFAULT 'high'  -- high (national id) / low (name only)
);
CREATE INDEX IF NOT EXISTS idx_persons_name_key ON persons(name_key);

CREATE TABLE IF NOT EXISTS transactions (
    transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    declaration_no TEXT,              -- شماره اعلامیه
    trade_date_jalali TEXT NOT NULL,  -- '1405/03/13'
    trade_date_gregorian TEXT NOT NULL, -- ISO date, used for all sorting/filtering
    symbol_id INTEGER NOT NULL REFERENCES symbols(symbol_id),
    buyer_person_id INTEGER REFERENCES persons(person_id),
    seller_person_id INTEGER REFERENCES persons(person_id),
    buyer_broker_id INTEGER REFERENCES brokers(broker_id),
    seller_broker_id INTEGER REFERENCES brokers(broker_id),
    quantity INTEGER NOT NULL,
    price REAL NOT NULL,
    value REAL NOT NULL,              -- quantity * price
    is_duplicate_of INTEGER,          -- transaction_id of the original, if this row was a detected exact duplicate
    source_row_index INTEGER,
    import_batch_id INTEGER REFERENCES import_batches(batch_id)
);
CREATE INDEX IF NOT EXISTS idx_tx_date ON transactions(trade_date_gregorian);
CREATE INDEX IF NOT EXISTS idx_tx_symbol ON transactions(symbol_id);
CREATE INDEX IF NOT EXISTS idx_tx_buyer ON transactions(buyer_person_id);
CREATE INDEX IF NOT EXISTS idx_tx_seller ON transactions(seller_person_id);
CREATE INDEX IF NOT EXISTS idx_tx_buyer_broker ON transactions(buyer_broker_id);
CREATE INDEX IF NOT EXISTS idx_tx_seller_broker ON transactions(seller_broker_id);
CREATE INDEX IF NOT EXISTS idx_tx_declaration ON transactions(declaration_no);

CREATE TABLE IF NOT EXISTS data_quality (
    batch_id INTEGER REFERENCES import_batches(batch_id),
    metric_name TEXT,
    metric_value TEXT
);

CREATE TABLE IF NOT EXISTS analysis_cache (
    cache_key TEXT PRIMARY KEY,
    computed_at TEXT,
    payload_json TEXT
);

CREATE TABLE IF NOT EXISTS alerts (
    alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT,
    severity TEXT,        -- Watch / Important / High / Critical
    risk_score REAL,
    alert_type TEXT,
    trade_date_gregorian TEXT,
    symbol_id INTEGER,
    person_id INTEGER,
    broker_id INTEGER,
    value REAL,
    reason TEXT,
    supporting_transaction_ids TEXT   -- JSON list
);


-- Shareholder registry / opening holdings
CREATE TABLE IF NOT EXISTS registry_batches (
    registry_batch_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file TEXT NOT NULL,
    imported_at TEXT NOT NULL,
    n_rows_raw INTEGER,
    n_rows_imported INTEGER,
    n_rows_rejected INTEGER,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS registry_holdings (
    registry_holding_id INTEGER PRIMARY KEY AUTOINCREMENT,
    registry_batch_id INTEGER REFERENCES registry_batches(registry_batch_id),
    shareholder_no TEXT,
    first_name TEXT,
    family_name TEXT,
    father_name TEXT,
    birth_or_registration_no TEXT,
    issue_place TEXT,
    registration_no TEXT,
    exchange_code TEXT,
    national_id TEXT,
    opening_quantity INTEGER NOT NULL DEFAULT 0,
    registry_buy_quantity INTEGER NOT NULL DEFAULT 0,
    registry_sell_quantity INTEGER NOT NULL DEFAULT 0,
    closing_quantity INTEGER NOT NULL DEFAULT 0,
    is_total_row INTEGER NOT NULL DEFAULT 0,
    source_row_index INTEGER
);
CREATE INDEX IF NOT EXISTS idx_registry_nid ON registry_holdings(national_id);
CREATE INDEX IF NOT EXISTS idx_registry_code ON registry_holdings(exchange_code);

CREATE TABLE IF NOT EXISTS identity_matches (
    identity_match_id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_person_id INTEGER REFERENCES persons(person_id),
    registry_holding_id INTEGER REFERENCES registry_holdings(registry_holding_id),
    match_method TEXT,
    confidence TEXT,
    matched_at TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_identity_match_tx_person ON identity_matches(transaction_person_id);

CREATE TABLE IF NOT EXISTS fifo_lots (
    lot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id INTEGER REFERENCES persons(person_id),
    symbol_id INTEGER REFERENCES symbols(symbol_id),
    lot_date_gregorian TEXT NOT NULL,
    lot_date_jalali TEXT NOT NULL,
    source_type TEXT NOT NULL, -- opening / buy
    source_transaction_id INTEGER REFERENCES transactions(transaction_id),
    quantity_original INTEGER NOT NULL,
    quantity_remaining INTEGER NOT NULL,
    unit_cost REAL,
    cost_known INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_fifo_person_symbol ON fifo_lots(person_id, symbol_id);

CREATE TABLE IF NOT EXISTS fifo_realizations (
    realization_id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id INTEGER REFERENCES persons(person_id),
    symbol_id INTEGER REFERENCES symbols(symbol_id),
    sell_transaction_id INTEGER REFERENCES transactions(transaction_id),
    lot_id INTEGER REFERENCES fifo_lots(lot_id),
    quantity INTEGER NOT NULL,
    sell_price REAL NOT NULL,
    unit_cost REAL,
    realized_pnl REAL,
    cost_known INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_fifo_realization_person ON fifo_realizations(person_id);

CREATE TABLE IF NOT EXISTS portfolio_analysis_cache (
    cache_key TEXT PRIMARY KEY,
    computed_at TEXT,
    payload_json TEXT
);
