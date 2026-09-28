import sqlite3
from pathlib import Path

db = Path("data/smart_equity.db")

print("=" * 80)
print("SMART EQUITY - DATA INTEGRITY READ-ONLY AUDIT")
print("=" * 80)
print(f"Database: {db.resolve()}")
print(f"Size: {db.stat().st_size:,} bytes")

conn = sqlite3.connect(f"file:{db.resolve()}?mode=ro", uri=True)
conn.row_factory = sqlite3.Row

def scalar(sql):
    return conn.execute(sql).fetchone()[0]

def section(title):
    print()
    print("-" * 80)
    print(title)
    print("-" * 80)

# 1. TABLE COUNTS
section("1. TABLE COUNTS")

tables = [
    "import_batches",
    "symbols",
    "brokers",
    "persons",
    "transactions",
    "data_quality",
    "analysis_cache",
    "alerts",
    "registry_batches",
    "registry_holdings",
    "identity_matches",
    "fifo_lots",
    "fifo_realizations",
    "portfolio_analysis_cache",
]

for table in tables:
    try:
        print(f"{table:28} {scalar(f'SELECT COUNT(*) FROM {table}'):,.0f}")
    except Exception as e:
        print(f"{table:28} ERROR: {e}")

# 2. TRANSACTION COVERAGE
section("2. TRANSACTION COVERAGE")

print("Transaction rows:",
      f"{scalar('SELECT COUNT(*) FROM transactions'):,}")

print("Distinct transaction dates:",
      f"{scalar('SELECT COUNT(DISTINCT trade_date_gregorian) FROM transactions'):,}")

print("Min Gregorian date:",
      scalar("SELECT MIN(trade_date_gregorian) FROM transactions"))

print("Max Gregorian date:",
      scalar("SELECT MAX(trade_date_gregorian) FROM transactions"))

print("Min Jalali date:",
      scalar("SELECT MIN(trade_date_jalali) FROM transactions"))

print("Max Jalali date:",
      scalar("SELECT MAX(trade_date_jalali) FROM transactions"))

print("Distinct symbols:",
      f"{scalar('SELECT COUNT(DISTINCT symbol_id) FROM transactions'):,}")

# 3. PLAYER COVERAGE
section("3. PLAYER COVERAGE")

print("Distinct buyers:",
      f"{scalar('SELECT COUNT(DISTINCT buyer_person_id) FROM transactions WHERE buyer_person_id IS NOT NULL'):,}")

print("Distinct sellers:",
      f"{scalar('SELECT COUNT(DISTINCT seller_person_id) FROM transactions WHERE seller_person_id IS NOT NULL'):,}")

print("Transactions without buyer:",
      f"{scalar('SELECT COUNT(*) FROM transactions WHERE buyer_person_id IS NULL'):,}")

print("Transactions without seller:",
      f"{scalar('SELECT COUNT(*) FROM transactions WHERE seller_person_id IS NULL'):,}")

# 4. PERSON IDENTITY QUALITY
section("4. PERSON IDENTITY QUALITY")

print("Total persons:",
      f"{scalar('SELECT COUNT(*) FROM persons'):,}")

print("With national_id:",
      f"{scalar('SELECT COUNT(*) FROM persons WHERE national_id IS NOT NULL AND TRIM(national_id) <> \"\"'):,}")

print("Without national_id:",
      f"{scalar('SELECT COUNT(*) FROM persons WHERE national_id IS NULL OR TRIM(national_id) = \"\"'):,}")

print("With shareholder_code:",
      f"{scalar('SELECT COUNT(*) FROM persons WHERE shareholder_code IS NOT NULL AND TRIM(shareholder_code) <> \"\"'):,}")

print("Without shareholder_code:",
      f"{scalar('SELECT COUNT(*) FROM persons WHERE shareholder_code IS NULL OR TRIM(shareholder_code) = \"\"'):,}")

print()
print("identifier_confidence:")

for r in conn.execute("""
    SELECT
        COALESCE(NULLIF(TRIM(identifier_confidence), ''), '[NULL/EMPTY]') AS confidence,
        COUNT(*) AS n
    FROM persons
    GROUP BY COALESCE(NULLIF(TRIM(identifier_confidence), ''), '[NULL/EMPTY]')
    ORDER BY n DESC
"""):
    print(f"  {r['confidence']:20} {r['n']:,}")

print()
print("person_type:")

for r in conn.execute("""
    SELECT
        COALESCE(NULLIF(TRIM(person_type), ''), '[NULL/EMPTY]') AS person_type,
        COUNT(*) AS n
    FROM persons
    GROUP BY COALESCE(NULLIF(TRIM(person_type), ''), '[NULL/EMPTY]')
    ORDER BY n DESC
"""):
    print(f"  {r['person_type']:30} {r['n']:,}")

# 5. TRANSACTION INTEGRITY
section("5. TRANSACTION NUMERIC INTEGRITY")

print("quantity <= 0:",
      f"{scalar('SELECT COUNT(*) FROM transactions WHERE quantity <= 0'):,}")

print("price <= 0:",
      f"{scalar('SELECT COUNT(*) FROM transactions WHERE price <= 0'):,}")

print("value <= 0:",
      f"{scalar('SELECT COUNT(*) FROM transactions WHERE value <= 0'):,}")

print("quantity IS NULL:",
      f"{scalar('SELECT COUNT(*) FROM transactions WHERE quantity IS NULL'):,}")

print("price IS NULL:",
      f"{scalar('SELECT COUNT(*) FROM transactions WHERE price IS NULL'):,}")

print("value IS NULL:",
      f"{scalar('SELECT COUNT(*) FROM transactions WHERE value IS NULL'):,}")

print("value != quantity * price:",
      f"""{scalar('SELECT COUNT(*) FROM transactions WHERE ABS(value - (quantity * price)) > 0.01'):,}""")

# 6. DUPLICATES / IMPORT
section("6. DUPLICATE / IMPORT QUALITY")

print("Rows marked duplicate:",
      f"{scalar('SELECT COUNT(*) FROM transactions WHERE is_duplicate_of IS NOT NULL'):,}")

print("Import batches:",
      f"{scalar('SELECT COUNT(*) FROM import_batches'):,}")

for r in conn.execute("""
    SELECT
        batch_id,
        source_file,
        imported_at,
        n_rows_raw,
        n_rows_imported,
        n_rows_duplicate,
        n_rows_rejected
    FROM import_batches
    ORDER BY batch_id
"""):
    print(
        f"  batch={r['batch_id']} | "
        f"raw={r['n_rows_raw']} | "
        f"imported={r['n_rows_imported']} | "
        f"duplicate={r['n_rows_duplicate']} | "
        f"rejected={r['n_rows_rejected']} | "
        f"file={r['source_file']}"
    )

# 7. REGISTRY
section("7. REGISTRY COVERAGE")

print("Registry batches:",
      f"{scalar('SELECT COUNT(*) FROM registry_batches'):,}")

print("Registry holdings:",
      f"{scalar('SELECT COUNT(*) FROM registry_holdings'):,}")

print("Registry total rows:",
      f"{scalar('SELECT COUNT(*) FROM registry_holdings WHERE is_total_row = 1'):,}")

print("Registry non-total rows:",
      f"{scalar('SELECT COUNT(*) FROM registry_holdings WHERE is_total_row = 0'):,}")

print("Registry with national_id:",
      f"{scalar('SELECT COUNT(*) FROM registry_holdings WHERE national_id IS NOT NULL AND TRIM(national_id) <> \"\"'):,}")

print("Registry with exchange_code:",
      f"{scalar('SELECT COUNT(*) FROM registry_holdings WHERE exchange_code IS NOT NULL AND TRIM(exchange_code) <> \"\"'):,}")

# 8. IDENTITY MATCHING
section("8. IDENTITY MATCHING")

print("Identity matches:",
      f"{scalar('SELECT COUNT(*) FROM identity_matches'):,}")

print("Persons matched:",
      f"{scalar('SELECT COUNT(DISTINCT transaction_person_id) FROM identity_matches WHERE transaction_person_id IS NOT NULL'):,}")

for r in conn.execute("""
    SELECT
        COALESCE(NULLIF(TRIM(match_method), ''), '[NULL/EMPTY]') AS method,
        COUNT(*) AS n
    FROM identity_matches
    GROUP BY COALESCE(NULLIF(TRIM(match_method), ''), '[NULL/EMPTY]')
    ORDER BY n DESC
"""):
    print(f"  method={r['method']:30} {r['n']:,}")

print()
print("confidence:")

for r in conn.execute("""
    SELECT
        COALESCE(NULLIF(TRIM(confidence), ''), '[NULL/EMPTY]') AS confidence,
        COUNT(*) AS n
    FROM identity_matches
    GROUP BY COALESCE(NULLIF(TRIM(confidence), ''), '[NULL/EMPTY]')
    ORDER BY n DESC
"""):
    print(f"  {r['confidence']:20} {r['n']:,}")

# 9. FIFO
section("9. FIFO COVERAGE")

print("FIFO lots:",
      f"{scalar('SELECT COUNT(*) FROM fifo_lots'):,}")

print("FIFO lots with remaining quantity:",
      f"{scalar('SELECT COUNT(*) FROM fifo_lots WHERE quantity_remaining > 0'):,}")

print("FIFO lots with known cost:",
      f"{scalar('SELECT COUNT(*) FROM fifo_lots WHERE cost_known = 1'):,}")

print("FIFO realizations:",
      f"{scalar('SELECT COUNT(*) FROM fifo_realizations'):,}")

print("Realizations with known cost:",
      f"{scalar('SELECT COUNT(*) FROM fifo_realizations WHERE cost_known = 1'):,}")

print("Realizations with realized P&L:",
      f"{scalar('SELECT COUNT(*) FROM fifo_realizations WHERE realized_pnl IS NOT NULL'):,}")

# 10. BROKERS
section("10. BROKER COVERAGE")

print("Brokers:",
      f"{scalar('SELECT COUNT(*) FROM brokers'):,}")

print("Transactions with buyer broker:",
      f"{scalar('SELECT COUNT(*) FROM transactions WHERE buyer_broker_id IS NOT NULL'):,}")

print("Transactions with seller broker:",
      f"{scalar('SELECT COUNT(*) FROM transactions WHERE seller_broker_id IS NOT NULL'):,}")

print("Market-maker brokers:",
      f"{scalar('SELECT COUNT(*) FROM brokers WHERE is_market_maker = 1'):,}")

# 11. SYMBOLS
section("11. SYMBOL COVERAGE")

print("Symbols table:",
      f"{scalar('SELECT COUNT(*) FROM symbols'):,}")

print()
print("Top 20 symbols by transaction count:")

for r in conn.execute("""
    SELECT
        s.symbol_code,
        s.symbol_name,
        COUNT(t.transaction_id) AS tx_count
    FROM symbols s
    LEFT JOIN transactions t ON t.symbol_id = s.symbol_id
    GROUP BY s.symbol_id
    ORDER BY tx_count DESC
    LIMIT 20
"""):
    print(
        f"  {str(r['symbol_code']):15} "
        f"{str(r['symbol_name'] or '')[:35]:35} "
        f"{r['tx_count']:,}"
    )

# 12. DAILY COVERAGE
section("12. DAILY COVERAGE")

r = conn.execute("""
    SELECT
        COUNT(*) AS days,
        MIN(n) AS min_tx_day,
        MAX(n) AS max_tx_day,
        AVG(n) AS avg_tx_day
    FROM (
        SELECT trade_date_gregorian, COUNT(*) AS n
        FROM transactions
        GROUP BY trade_date_gregorian
    )
""").fetchone()

print("Trading/data days:", f"{r['days']:,}")
print("Minimum transactions/day:", r["min_tx_day"])
print("Maximum transactions/day:", r["max_tx_day"])
print("Average transactions/day:", r["avg_tx_day"])

# 13. ALERTS
section("13. EXISTING ALERTS")

print("Alerts:",
      f"{scalar('SELECT COUNT(*) FROM alerts'):,}")

for r in conn.execute("""
    SELECT
        COALESCE(NULLIF(TRIM(severity), ''), '[NULL/EMPTY]') AS severity,
        COUNT(*) AS n
    FROM alerts
    GROUP BY COALESCE(NULLIF(TRIM(severity), ''), '[NULL/EMPTY]')
    ORDER BY n DESC
"""):
    print(f"  {r['severity']:20} {r['n']:,}")

# 14. READINESS
section("14. ANALYTICAL READINESS")

checks = [
    ("Transactions exist",
     scalar("SELECT COUNT(*) FROM transactions") > 0),

    ("Multiple dates exist",
     scalar("SELECT COUNT(DISTINCT trade_date_gregorian) FROM transactions") > 1),

    ("Symbols exist",
     scalar("SELECT COUNT(*) FROM symbols") > 0),

    ("Players exist",
     scalar("SELECT COUNT(*) FROM persons") > 0),

    ("Prices are positive",
     scalar("SELECT COUNT(*) FROM transactions WHERE price <= 0") == 0),

    ("Quantities are positive",
     scalar("SELECT COUNT(*) FROM transactions WHERE quantity <= 0") == 0),

    ("Values are positive",
     scalar("SELECT COUNT(*) FROM transactions WHERE value <= 0") == 0),
]

for name, ok in checks:
    print(f"{'PASS' if ok else 'CHECK'}  {name}")

conn.close()

print()
print("=" * 80)
print("READ-ONLY AUDIT FINISHED")
print("No database modification was performed.")
print("=" * 80)
