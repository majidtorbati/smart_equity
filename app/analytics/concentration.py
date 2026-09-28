"""
Smart Equity Transaction Intelligence
Phase 8 — Concentration Analysis

Read-only analytics engine.
No database mutation.
"""

from __future__ import annotations

import math
import sqlite3
from collections import defaultdict
from pathlib import Path
from statistics import median
from typing import Any


DB_PATH = Path(__file__).resolve().parents[2] / "data" / "smart_equity.db"


def _safe_float(value: Any) -> float:
    try:
        number = float(value)
        return number if math.isfinite(number) else 0.0
    except Exception:
        return 0.0


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def _hhi(shares: list[float]) -> float:
    """
    HHI using decimal shares.

    Example:
        50% -> 0.50
        30% -> 0.30
        20% -> 0.20

    HHI is returned on the 0..10,000 scale.
    """
    if not shares:
        return 0.0

    return round(
        sum((max(0.0, share) * 100.0) ** 2 for share in shares),
        4,
    )


def _concentration_summary(
    rows: list[dict[str, Any]],
    key: str,
    value_key: str,
    top_n: tuple[int, ...] = (1, 5, 10),
) -> dict[str, Any]:
    """
    Aggregate a value by entity and calculate concentration metrics.
    """

    totals: dict[Any, float] = defaultdict(float)

    for row in rows:
        entity = row.get(key)
        value = _safe_float(row.get(value_key))

        if entity is None or value <= 0:
            continue

        totals[entity] += value

    ranked = sorted(
        totals.items(),
        key=lambda item: item[1],
        reverse=True,
    )

    total_value = sum(value for _, value in ranked)

    if total_value <= 0:
        return {
            "entities": 0,
            "total_value": 0.0,
            "hhi": 0.0,
            "top1_share": 0.0,
            "top5_share": 0.0,
            "top10_share": 0.0,
            "rows": [],
        }

    shares = [
        value / total_value
        for _, value in ranked
    ]

    result_rows = []

    for rank, (entity, value) in enumerate(ranked, start=1):
        result_rows.append(
            {
                "rank": rank,
                "entity_id": entity,
                "value": value,
                "share": value / total_value,
            }
        )

    result = {
        "entities": len(ranked),
        "total_value": total_value,
        "hhi": _hhi(shares),
        "top1_share": sum(shares[:1]),
        "top5_share": sum(shares[:5]),
        "top10_share": sum(shares[:10]),
        "rows": result_rows,
    }

    return result


def _load_transactions(
    conn: sqlite3.Connection,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
            transaction_id,
            trade_date_gregorian,
            trade_date_jalali,
            symbol_id,
            buyer_person_id,
            seller_person_id,
            quantity,
            price,
            value
        FROM transactions
        WHERE is_duplicate_of IS NULL
        """
    ).fetchall()

    result = []

    for row in rows:
        result.append(
            {
                "transaction_id": row[0],
                "trade_date_gregorian": row[1],
                "trade_date_jalali": row[2],
                "symbol_id": row[3],
                "buyer_person_id": row[4],
                "seller_person_id": row[5],
                "quantity": _safe_int(row[6]),
                "price": _safe_float(row[7]),
                "value": _safe_float(row[8]),
            }
        )

    return result


def _load_person_info(
    conn: sqlite3.Connection,
) -> dict[int, dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
            person_id,
            name_raw,
            person_type,
            national_id,
            shareholder_code
        FROM persons
        """
    ).fetchall()

    return {
        int(row[0]): {
            "person_id": int(row[0]),
            "name": row[1],
            "person_type": row[2],
            "national_id": row[3],
            "shareholder_code": row[4],
        }
        for row in rows
    }


def _build_daily_concentration(
    transactions: list[dict[str, Any]],
    person_info: dict[int, dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for tx in transactions:
        grouped[tx["trade_date_gregorian"]].append(tx)

    result = []

    for trade_date in sorted(grouped):
        day_rows = grouped[trade_date]

        buyers = [
            {
                "person_id": tx["buyer_person_id"],
                "value": tx["value"],
            }
            for tx in day_rows
            if tx["buyer_person_id"] is not None
            and tx["value"] > 0
        ]

        sellers = [
            {
                "person_id": tx["seller_person_id"],
                "value": tx["value"],
            }
            for tx in day_rows
            if tx["seller_person_id"] is not None
            and tx["value"] > 0
        ]

        buyer_summary = _concentration_summary(
            buyers,
            "person_id",
            "value",
        )

        seller_summary = _concentration_summary(
            sellers,
            "person_id",
            "value",
        )

        daily_total = sum(
            tx["value"]
            for tx in day_rows
            if tx["value"] > 0
        )

        jalali = day_rows[0]["trade_date_jalali"]

        result.append(
            {
                "trade_date": trade_date,
                "trade_date_jalali": jalali,
                "transactions": len(day_rows),
                "total_value": daily_total,
                "buyer": buyer_summary,
                "seller": seller_summary,
            }
        )

    return result


def _build_period_concentration(
    transactions: list[dict[str, Any]],
) -> dict[str, Any]:
    buyers = [
        {
            "person_id": tx["buyer_person_id"],
            "value": tx["value"],
        }
        for tx in transactions
        if tx["buyer_person_id"] is not None
        and tx["value"] > 0
    ]

    sellers = [
        {
            "person_id": tx["seller_person_id"],
            "value": tx["value"],
        }
        for tx in transactions
        if tx["seller_person_id"] is not None
        and tx["value"] > 0
    ]

    return {
        "buyers": _concentration_summary(
            buyers,
            "person_id",
            "value",
        ),
        "sellers": _concentration_summary(
            sellers,
            "person_id",
            "value",
        ),
    }


def _load_registry(
    conn: sqlite3.Connection,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
            registry_holding_id,
            registry_batch_id,
            shareholder_no,
            first_name,
            family_name,
            national_id,
            exchange_code,
            opening_quantity,
            registry_buy_quantity,
            registry_sell_quantity,
            closing_quantity
        FROM registry_holdings
        WHERE is_total_row = 0
        """
    ).fetchall()

    result = []

    for row in rows:
        result.append(
            {
                "registry_holding_id": row[0],
                "registry_batch_id": row[1],
                "shareholder_no": row[2],
                "first_name": row[3],
                "family_name": row[4],
                "national_id": row[5],
                "exchange_code": row[6],
                "opening_quantity": _safe_int(row[7]),
                "registry_buy_quantity": _safe_int(row[8]),
                "registry_sell_quantity": _safe_int(row[9]),
                "closing_quantity": _safe_int(row[10]),
            }
        )

    return result


def _build_ownership_concentration(
    registry_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    positive = [
        row
        for row in registry_rows
        if row["closing_quantity"] > 0
    ]

    totals = sorted(
        positive,
        key=lambda row: row["closing_quantity"],
        reverse=True,
    )

    total_quantity = sum(
        row["closing_quantity"]
        for row in positive
    )

    if total_quantity <= 0:
        return {
            "holders": 0,
            "total_closing_quantity": 0,
            "hhi": 0.0,
            "top1_share": 0.0,
            "top5_share": 0.0,
            "top10_share": 0.0,
            "rows": [],
        }

    shares = [
        row["closing_quantity"] / total_quantity
        for row in totals
    ]

    result_rows = []

    for rank, row in enumerate(totals, start=1):
        result_rows.append(
            {
                "rank": rank,
                "registry_holding_id": row[
                    "registry_holding_id"
                ],
                "shareholder_no": row["shareholder_no"],
                "first_name": row["first_name"],
                "family_name": row["family_name"],
                "national_id": row["national_id"],
                "exchange_code": row["exchange_code"],
                "closing_quantity": row[
                    "closing_quantity"
                ],
                "share": (
                    row["closing_quantity"]
                    / total_quantity
                ),
            }
        )

    return {
        "holders": len(totals),
        "total_closing_quantity": total_quantity,
        "hhi": _hhi(shares),
        "top1_share": sum(shares[:1]),
        "top5_share": sum(shares[:5]),
        "top10_share": sum(shares[:10]),
        "rows": result_rows,
    }


def validate_concentration_result(
    result: dict[str, Any],
) -> dict[str, Any]:
    checks = {
        "ready": bool(result.get("ready")),
        "transactions_positive": (
            _safe_int(result.get("transactions_used")) > 0
        ),
        "days_positive": (
            _safe_int(result.get("days")) > 0
        ),
        "period_concentration_present": (
            "period" in result
        ),
        "daily_concentration_present": (
            "daily" in result
        ),
        "ownership_present": (
            "ownership" in result
        ),
    }

    finite_errors = 0

    def check_summary(summary: dict[str, Any]) -> None:
        nonlocal finite_errors

        for key in (
            "hhi",
            "top1_share",
            "top5_share",
            "top10_share",
        ):
            value = _safe_float(summary.get(key))
            if not math.isfinite(value):
                finite_errors += 1

        for key in (
            "top1_share",
            "top5_share",
            "top10_share",
        ):
            value = _safe_float(summary.get(key))
            if value < 0 or value > 1:
                finite_errors += 1

        hhi = _safe_float(summary.get("hhi"))
        if hhi < 0 or hhi > 10000:
            finite_errors += 1

    period = result.get("period", {})

    for side in ("buyers", "sellers"):
        summary = period.get(side)
        if isinstance(summary, dict):
            check_summary(summary)

    ownership = result.get("ownership")
    if isinstance(ownership, dict):
        check_summary(ownership)

    checks["finite_metric_errors"] = finite_errors

    valid = all(
        value
        for key, value in checks.items()
        if key != "finite_metric_errors"
    ) and finite_errors == 0

    return {
        "valid": valid,
        "checks": checks,
    }


def run_concentration_analysis(
    conn: sqlite3.Connection,
) -> dict[str, Any]:
    transactions = _load_transactions(conn)
    person_info = _load_person_info(conn)

    if not transactions:
        return {
            "ready": False,
            "reason": "No valid transactions found.",
            "transactions_used": 0,
            "days": 0,
            "period": {},
            "daily": [],
            "ownership": {},
            "person_info_count": len(person_info),
        }

    period = _build_period_concentration(
        transactions
    )

    daily = _build_daily_concentration(
        transactions,
        person_info,
    )

    registry = _load_registry(conn)

    ownership = _build_ownership_concentration(
        registry
    )

    first_date = min(
        tx["trade_date_gregorian"]
        for tx in transactions
    )

    last_date = max(
        tx["trade_date_gregorian"]
        for tx in transactions
    )

    result = {
        "ready": True,
        "methodology": {
            "type": "transaction_and_ownership_concentration",
            "transaction_basis": (
                "non-duplicate transaction value"
            ),
            "ownership_basis": (
                "registry closing quantity"
            ),
            "hhi_scale": "0_to_10000",
            "top_groups": [1, 5, 10],
            "ownership_total_rows_excluded": True,
            "read_only": True,
            "interpretation_limits": [
                "Concentration does not prove intent.",
                "Concentration does not prove manipulation.",
                "Transaction concentration is not ownership concentration.",
                "Registry closing quantity represents the supplied registry snapshot.",
            ],
        },
        "transactions_used": len(transactions),
        "days": len(
            {
                tx["trade_date_gregorian"]
                for tx in transactions
            }
        ),
        "symbols": len(
            {
                tx["symbol_id"]
                for tx in transactions
            }
        ),
        "first_trade_date": first_date,
        "last_trade_date": last_date,
        "period": period,
        "daily": daily,
        "ownership": ownership,
        "person_info_count": len(person_info),
    }

    validation = validate_concentration_result(
        result
    )

    result["validation"] = validation

    return result


def audit_concentration(
    db_path: str | Path = DB_PATH,
) -> dict[str, Any]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    try:
        return run_concentration_analysis(conn)
    finally:
        conn.close()


def main() -> None:
    result = audit_concentration()

    print(
        {
            "ready": result.get("ready"),
            "transactions_used": result.get(
                "transactions_used"
            ),
            "days": result.get("days"),
            "symbols": result.get("symbols"),
            "period_buyers": result.get(
                "period", {}
            ).get("buyers", {}).get("entities"),
            "period_sellers": result.get(
                "period", {}
            ).get("sellers", {}).get("entities"),
            "ownership_holders": result.get(
                "ownership", {}
            ).get("holders"),
            "validation": result.get("validation"),
        }
    )


if __name__ == "__main__":
    main()
