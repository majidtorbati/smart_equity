"""
SmartEquity - Phase 1 Data Integrity Engine.

Read-only analytical validation of the SQLite database.
This module never modifies the database.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any
import sqlite3


@dataclass(frozen=True)
class Finding:
    code: str
    severity: str
    category: str
    message: str
    value: Any = None


def _scalar(conn: sqlite3.Connection, sql: str, params=()):
    return conn.execute(sql, params).fetchone()[0]


def _rows(conn: sqlite3.Connection, sql: str, params=()):
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return bool(
        _scalar(
            conn,
            "SELECT COUNT(*) FROM sqlite_master "
            "WHERE type='table' AND name=?",
            (table,),
        )
    )


def _index_exists(conn: sqlite3.Connection, index: str) -> bool:
    return bool(
        _scalar(
            conn,
            "SELECT COUNT(*) FROM sqlite_master "
            "WHERE type='index' AND name=?",
            (index,),
        )
    )


def _add(
    findings: list[Finding],
    code: str,
    severity: str,
    category: str,
    message: str,
    value: Any = None,
) -> None:
    findings.append(
        Finding(
            code=code,
            severity=severity,
            category=category,
            message=message,
            value=value,
        )
    )


def run_data_integrity(conn: sqlite3.Connection) -> dict:
    """
    Run the complete Phase 1 read-only integrity audit.

    The supplied connection is never committed, updated, inserted into,
    deleted from, or otherwise modified.
    """
    conn.row_factory = sqlite3.Row
    findings: list[Finding] = []

    required_tables = [
        "import_batches",
        "symbols",
        "brokers",
        "persons",
        "transactions",
        "data_quality",
        "alerts",
        "registry_batches",
        "registry_holdings",
        "identity_matches",
        "fifo_lots",
        "fifo_realizations",
    ]

    missing_tables = [
        t for t in required_tables if not _table_exists(conn, t)
    ]

    if missing_tables:
        _add(
            findings,
            "DQ-TABLE-001",
            "ERROR",
            "schema",
            "Required database tables are missing.",
            missing_tables,
        )
        return {
            "ready": False,
            "findings": [asdict(x) for x in findings],
            "metrics": {},
        }

    metrics: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # 1. Transaction coverage
    # ------------------------------------------------------------------
    metrics["transactions"] = _scalar(
        conn, "SELECT COUNT(*) FROM transactions"
    )
    metrics["transaction_days"] = _scalar(
        conn,
        "SELECT COUNT(DISTINCT trade_date_gregorian) FROM transactions",
    )
    metrics["distinct_symbols"] = _scalar(
        conn, "SELECT COUNT(DISTINCT symbol_id) FROM transactions"
    )

    dates = conn.execute(
        """
        SELECT
            MIN(trade_date_gregorian),
            MAX(trade_date_gregorian),
            MIN(trade_date_jalali),
            MAX(trade_date_jalali)
        FROM transactions
        """
    ).fetchone()

    metrics["min_gregorian_date"] = dates[0]
    metrics["max_gregorian_date"] = dates[1]
    metrics["min_jalali_date"] = dates[2]
    metrics["max_jalali_date"] = dates[3]

    if metrics["transactions"] == 0:
        _add(
            findings,
            "DQ-TX-001",
            "ERROR",
            "transactions",
            "No transaction records exist.",
            0,
        )
    else:
        _add(
            findings,
            "DQ-TX-001",
            "INFO",
            "transactions",
            "Transaction records exist.",
            metrics["transactions"],
        )

    if metrics["transaction_days"] < 2 and metrics["transactions"] > 0:
        _add(
            findings,
            "DQ-TX-002",
            "WARNING",
            "transactions",
            "Less than two distinct transaction dates are available.",
            metrics["transaction_days"],
        )

    # ------------------------------------------------------------------
    # 2. Transaction numeric integrity
    # ------------------------------------------------------------------
    numeric_checks = {
        "quantity_nonpositive": """
            SELECT COUNT(*) FROM transactions
            WHERE quantity IS NULL OR quantity <= 0
        """,
        "price_nonpositive": """
            SELECT COUNT(*) FROM transactions
            WHERE price IS NULL OR price <= 0
        """,
        "value_nonpositive": """
            SELECT COUNT(*) FROM transactions
            WHERE value IS NULL OR value <= 0
        """,
        "value_mismatch": """
            SELECT COUNT(*) FROM transactions
            WHERE ABS(value - (quantity * price)) > 0.0001
        """,
    }

    for key, sql in numeric_checks.items():
        metrics[key] = _scalar(conn, sql)
        if metrics[key]:
            _add(
                findings,
                f"DQ-NUM-{key.upper()}",
                "ERROR",
                "numeric",
                f"Numeric integrity violation: {key}.",
                metrics[key],
            )

    # ------------------------------------------------------------------
    # 3. Referential integrity
    # ------------------------------------------------------------------
    ref_checks = {
        "missing_symbol": """
            SELECT COUNT(*)
            FROM transactions t
            LEFT JOIN symbols s ON s.symbol_id = t.symbol_id
            WHERE s.symbol_id IS NULL
        """,
        "missing_buyer": """
            SELECT COUNT(*)
            FROM transactions t
            LEFT JOIN persons p ON p.person_id = t.buyer_person_id
            WHERE p.person_id IS NULL
        """,
        "missing_seller": """
            SELECT COUNT(*)
            FROM transactions t
            LEFT JOIN persons p ON p.person_id = t.seller_person_id
            WHERE p.person_id IS NULL
        """,
        "missing_buyer_broker": """
            SELECT COUNT(*)
            FROM transactions t
            LEFT JOIN brokers b ON b.broker_id = t.buyer_broker_id
            WHERE b.broker_id IS NULL
        """,
        "missing_seller_broker": """
            SELECT COUNT(*)
            FROM transactions t
            LEFT JOIN brokers b ON b.broker_id = t.seller_broker_id
            WHERE b.broker_id IS NULL
        """,
    }

    for key, sql in ref_checks.items():
        metrics[key] = _scalar(conn, sql)

        if metrics[key]:
            _add(
                findings,
                f"DQ-REF-{key.upper()}",
                "ERROR",
                "referential",
                f"Broken transaction reference: {key}.",
                metrics[key],
            )

    # ------------------------------------------------------------------
    # 4. Identity quality
    # ------------------------------------------------------------------
    metrics["persons"] = _scalar(conn, "SELECT COUNT(*) FROM persons")
    metrics["persons_with_national_id"] = _scalar(
        conn,
        "SELECT COUNT(*) FROM persons "
        "WHERE national_id IS NOT NULL AND TRIM(national_id) <> ''",
    )
    metrics["persons_with_shareholder_code"] = _scalar(
        conn,
        "SELECT COUNT(*) FROM persons "
        "WHERE shareholder_code IS NOT NULL "
        "AND TRIM(shareholder_code) <> ''",
    )

    confidence_rows = _rows(
        conn,
        """
        SELECT identifier_confidence, COUNT(*) AS n
        FROM persons
        GROUP BY identifier_confidence
        ORDER BY identifier_confidence
        """,
    )
    metrics["identity_confidence"] = confidence_rows

    metrics["identity_unmatched_to_registry"] = _scalar(
        conn,
        """
        SELECT COUNT(*)
        FROM persons p
        LEFT JOIN identity_matches im
            ON im.transaction_person_id = p.person_id
        WHERE im.transaction_person_id IS NULL
        """,
    )

    metrics["identity_matches"] = _scalar(
        conn, "SELECT COUNT(*) FROM identity_matches"
    )

    method_rows = _rows(
        conn,
        """
        SELECT match_method, confidence, COUNT(*) AS n
        FROM identity_matches
        GROUP BY match_method, confidence
        ORDER BY match_method, confidence
        """,
    )
    metrics["identity_match_methods"] = method_rows

    if metrics["identity_unmatched_to_registry"]:
        _add(
            findings,
            "DQ-ID-001",
            "WARNING",
            "identity",
            "Some transaction persons have no registry identity match.",
            metrics["identity_unmatched_to_registry"],
        )

    low_conf = _scalar(
        conn,
        """
        SELECT COUNT(*)
        FROM identity_matches
        WHERE LOWER(COALESCE(confidence, '')) IN
              ('medium-low', 'low')
        """,
    )

    metrics["low_confidence_matches"] = low_conf

    if low_conf:
        _add(
            findings,
            "DQ-ID-002",
            "INFO",
            "identity",
            "Some identity matches have lower confidence.",
            low_conf,
        )

    # ------------------------------------------------------------------
    # 5. Registry quality
    # ------------------------------------------------------------------
    metrics["registry_batches"] = _scalar(
        conn, "SELECT COUNT(*) FROM registry_batches"
    )
    metrics["registry_holdings"] = _scalar(
        conn, "SELECT COUNT(*) FROM registry_holdings"
    )
    metrics["registry_total_rows"] = _scalar(
        conn,
        "SELECT COUNT(*) FROM registry_holdings WHERE is_total_row = 1",
    )
    metrics["registry_non_total_rows"] = _scalar(
        conn,
        "SELECT COUNT(*) FROM registry_holdings WHERE is_total_row = 0",
    )
    metrics["registry_with_national_id"] = _scalar(
        conn,
        """
        SELECT COUNT(*)
        FROM registry_holdings
        WHERE national_id IS NOT NULL AND TRIM(national_id) <> ''
        """,
    )
    metrics["registry_with_exchange_code"] = _scalar(
        conn,
        """
        SELECT COUNT(*)
        FROM registry_holdings
        WHERE exchange_code IS NOT NULL AND TRIM(exchange_code) <> ''
        """,
    )

    if metrics["registry_holdings"] and metrics["registry_total_rows"] == 0:
        _add(
            findings,
            "DQ-REG-001",
            "INFO",
            "registry",
            "Registry contains no explicit total row.",
            0,
        )

    # ------------------------------------------------------------------
    # 6. Broker quality
    # ------------------------------------------------------------------
    metrics["brokers"] = _scalar(
        conn, "SELECT COUNT(*) FROM brokers"
    )
    metrics["market_maker_brokers"] = _scalar(
        conn,
        "SELECT COUNT(*) FROM brokers WHERE is_market_maker = 1",
    )

    # ------------------------------------------------------------------
    # 7. Duplicate/import quality
    # ------------------------------------------------------------------
    metrics["duplicate_rows"] = _scalar(
        conn,
        """
        SELECT COUNT(*)
        FROM transactions
        WHERE is_duplicate_of IS NOT NULL
        """,
    )

    metrics["import_batches"] = _scalar(
        conn, "SELECT COUNT(*) FROM import_batches"
    )

    if metrics["duplicate_rows"]:
        _add(
            findings,
            "DQ-DUP-001",
            "WARNING",
            "duplicates",
            "Transactions are marked as duplicates.",
            metrics["duplicate_rows"],
        )

    # ------------------------------------------------------------------
    # 8. Temporal integrity
    # ------------------------------------------------------------------
    metrics["invalid_gregorian_dates"] = _scalar(
        conn,
        """
        SELECT COUNT(*)
        FROM transactions
        WHERE trade_date_gregorian IS NULL
           OR TRIM(trade_date_gregorian) = ''
        """,
    )

    metrics["invalid_jalali_dates"] = _scalar(
        conn,
        """
        SELECT COUNT(*)
        FROM transactions
        WHERE trade_date_jalali IS NULL
           OR TRIM(trade_date_jalali) = ''
        """,
    )

    if metrics["invalid_gregorian_dates"]:
        _add(
            findings,
            "DQ-DATE-001",
            "ERROR",
            "temporal",
            "Transactions contain missing Gregorian dates.",
            metrics["invalid_gregorian_dates"],
        )

    if metrics["invalid_jalali_dates"]:
        _add(
            findings,
            "DQ-DATE-002",
            "ERROR",
            "temporal",
            "Transactions contain missing Jalali dates.",
            metrics["invalid_jalali_dates"],
        )

    # ------------------------------------------------------------------
    # 9. FIFO
    # ------------------------------------------------------------------
    metrics["fifo_lots"] = _scalar(
        conn, "SELECT COUNT(*) FROM fifo_lots"
    )
    metrics["fifo_remaining_lots"] = _scalar(
        conn,
        "SELECT COUNT(*) FROM fifo_lots WHERE quantity_remaining > 0",
    )
    metrics["fifo_known_cost_lots"] = _scalar(
        conn,
        "SELECT COUNT(*) FROM fifo_lots WHERE cost_known = 1",
    )
    metrics["fifo_realizations"] = _scalar(
        conn, "SELECT COUNT(*) FROM fifo_realizations"
    )
    metrics["fifo_known_cost_realizations"] = _scalar(
        conn,
        "SELECT COUNT(*) FROM fifo_realizations WHERE cost_known = 1",
    )
    metrics["fifo_realized_pnl"] = _scalar(
        conn,
        """
        SELECT COUNT(*)
        FROM fifo_realizations
        WHERE realized_pnl IS NOT NULL
        """,
    )

    # ------------------------------------------------------------------
    # 10. Analytical readiness
    # ------------------------------------------------------------------
    hard_errors = sum(
        1 for f in findings if f.severity == "ERROR"
    )

    ready = (
        metrics["transactions"] > 0
        and metrics["transaction_days"] >= 2
        and metrics["distinct_symbols"] > 0
        and metrics["persons"] > 0
        and hard_errors == 0
    )

    if ready:
        _add(
            findings,
            "DQ-READY-001",
            "INFO",
            "readiness",
            "Database is analytically ready for downstream engines.",
            True,
        )
    else:
        _add(
            findings,
            "DQ-READY-001",
            "ERROR",
            "readiness",
            "Database is not analytically ready.",
            False,
        )

    return {
        "ready": ready,
        "metrics": metrics,
        "findings": [asdict(x) for x in findings],
        "summary": {
            "errors": sum(
                1 for f in findings if f.severity == "ERROR"
            ),
            "warnings": sum(
                1 for f in findings if f.severity == "WARNING"
            ),
            "info": sum(
                1 for f in findings if f.severity == "INFO"
            ),
        },
    }


def audit_database(db_path: str) -> dict:
    """
    Open a SQLite database read-only and execute Phase 1.
    """
    from pathlib import Path

    path = Path(db_path).resolve()
    uri = f"file:{path.as_posix()}?mode=ro"

    conn = sqlite3.connect(uri, uri=True)
    try:
        return run_data_integrity(conn)
    finally:
        conn.close()


def main() -> int:
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description="SmartEquity Phase 1 read-only data integrity audit"
    )
    parser.add_argument("database", help="Path to smart_equity.db")
    args = parser.parse_args()

    result = audit_database(args.database)
    print(json.dumps(result, ensure_ascii=False, indent=2))

    return 0 if result["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
