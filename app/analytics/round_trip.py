"""
Smart Equity Transaction Intelligence
Round Trip Analysis Engine

تحلیل رفت‌وبرگشت معاملات بر اساس اتصال دقیق Buy -> Sell
از طریق FIFO.

نکته:
- فقط realizationهایی که به lot با source_type='buy' متصل هستند بررسی می‌شوند.
- lotهای opening موجودی اولیه هستند و از Round Trip حذف می‌شوند.
- این تحلیل به‌تنهایی اثبات‌کننده دستکاری بازار، نیت معامله‌گر،
  فعالیت غیرقانونی یا تغییر مالکیت نیست.
"""

from __future__ import annotations

import math
import sqlite3
from datetime import date
from pathlib import Path
from statistics import mean
from typing import Any


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        if math.isfinite(number):
            return number
    except (TypeError, ValueError):
        pass
    return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _return_pct(buy_price: float, sell_price: float) -> float:
    if buy_price <= 0:
        return 0.0
    return ((sell_price - buy_price) / buy_price) * 100.0


def _holding_bucket(holding_days: int) -> str:
    if holding_days == 0:
        return "same_day"
    if 1 <= holding_days <= 3:
        return "1_3_days"
    if 4 <= holding_days <= 7:
        return "4_7_days"
    if 8 <= holding_days <= 30:
        return "8_30_days"
    return "31_plus_days"


def _load_round_trip_realizations(
    conn: sqlite3.Connection,
) -> list[dict[str, Any]]:
    """
    بارگذاری اتصال‌های معتبر Buy -> Sell از ساختار FIFO.
    """

    query = """
        SELECT
            r.realization_id,
            r.person_id,
            r.symbol_id,
            r.sell_transaction_id,
            r.lot_id,
            r.quantity,
            r.sell_price,
            r.unit_cost AS realization_unit_cost,
            r.realized_pnl,
            r.cost_known AS realization_cost_known,

            l.lot_date_gregorian AS buy_date,
            l.lot_date_jalali AS buy_date_jalali,
            l.source_type,
            l.source_transaction_id,
            l.unit_cost AS lot_unit_cost,
            l.cost_known AS lot_cost_known,

            bt.trade_date_gregorian AS buy_trade_date,
            bt.trade_date_jalali AS buy_trade_date_jalali,
            bt.buyer_broker_id AS buy_broker_id,
            bt.price AS buy_transaction_price,

            st.trade_date_gregorian AS sell_trade_date,
            st.trade_date_jalali AS sell_trade_date_jalali,
            st.seller_broker_id AS sell_broker_id,
            st.price AS sell_transaction_price

        FROM fifo_realizations r

        INNER JOIN fifo_lots l
            ON l.lot_id = r.lot_id

        LEFT JOIN transactions bt
            ON bt.transaction_id = l.source_transaction_id

        LEFT JOIN transactions st
            ON st.transaction_id = r.sell_transaction_id

        WHERE
            l.source_type = 'buy'
            AND l.source_transaction_id IS NOT NULL
            AND r.sell_transaction_id IS NOT NULL
            AND r.quantity > 0
            AND r.sell_price > 0
            AND l.unit_cost > 0
            AND l.cost_known = 1
            AND r.cost_known = 1

        ORDER BY
            st.trade_date_gregorian,
            r.realization_id
    """

    rows = conn.execute(query).fetchall()

    columns = [
        "realization_id",
        "person_id",
        "symbol_id",
        "sell_transaction_id",
        "lot_id",
        "quantity",
        "sell_price",
        "realization_unit_cost",
        "realized_pnl",
        "realization_cost_known",
        "buy_date",
        "buy_date_jalali",
        "source_type",
        "source_transaction_id",
        "lot_unit_cost",
        "lot_cost_known",
        "buy_trade_date",
        "buy_trade_date_jalali",
        "buy_broker_id",
        "buy_transaction_price",
        "sell_trade_date",
        "sell_trade_date_jalali",
        "sell_broker_id",
        "sell_transaction_price",
    ]

    return [dict(zip(columns, row)) for row in rows]


def _build_round_trip_rows(
    raw_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    تبدیل realizationهای FIFO به رکوردهای تحلیلی Round Trip.
    """

    result: list[dict[str, Any]] = []

    for raw in raw_rows:
        buy_date = raw.get("buy_trade_date") or raw.get("buy_date")
        sell_date = raw.get("sell_trade_date")

        if not buy_date or not sell_date:
            continue

        try:
            buy_dt = date.fromisoformat(str(buy_date))
            sell_dt = date.fromisoformat(str(sell_date))
        except (TypeError, ValueError):
            continue

        holding_days = (sell_dt - buy_dt).days

        if holding_days < 0:
            continue

        quantity = _safe_int(raw.get("quantity"))
        buy_price = _safe_float(
            raw.get("lot_unit_cost")
            or raw.get("realization_unit_cost")
        )
        sell_price = _safe_float(raw.get("sell_price"))

        if quantity <= 0 or buy_price <= 0 or sell_price <= 0:
            continue

        buy_value = quantity * buy_price
        sell_value = quantity * sell_price

        stored_pnl = raw.get("realized_pnl")
        if stored_pnl is None:
            realized_pnl = sell_value - buy_value
        else:
            realized_pnl = _safe_float(
                stored_pnl,
                sell_value - buy_value,
            )

        return_pct = _return_pct(buy_price, sell_price)

        result.append(
            {
                "realization_id": _safe_int(raw.get("realization_id")),
                "person_id": _safe_int(raw.get("person_id")),
                "symbol_id": _safe_int(raw.get("symbol_id")),
                "sell_transaction_id": _safe_int(
                    raw.get("sell_transaction_id")
                ),
                "lot_id": _safe_int(raw.get("lot_id")),
                "buy_transaction_id": _safe_int(
                    raw.get("source_transaction_id")
                ),
                "quantity": quantity,
                "buy_date": str(buy_date),
                "buy_date_jalali": raw.get("buy_trade_date_jalali")
                or raw.get("buy_date_jalali"),
                "sell_date": str(sell_date),
                "sell_date_jalali": raw.get("sell_trade_date_jalali"),
                "holding_days": holding_days,
                "holding_bucket": _holding_bucket(holding_days),
                "buy_price": buy_price,
                "sell_price": sell_price,
                "buy_value": buy_value,
                "sell_value": sell_value,
                "realized_pnl": realized_pnl,
                "return_pct": return_pct,
                "buy_broker_id": raw.get("buy_broker_id"),
                "sell_broker_id": raw.get("sell_broker_id"),
            }
        )

    return result


def _build_summary(
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    if not rows:
        return {
            "realizations_used": 0,
            "persons": 0,
            "symbols": 0,
            "first_buy_date": None,
            "last_sell_date": None,
            "total_quantity": 0,
            "total_buy_value": 0.0,
            "total_sell_value": 0.0,
            "total_realized_pnl": 0.0,
            "average_holding_days": 0.0,
            "median_holding_days": 0.0,
            "average_return_pct": 0.0,
            "profitable_realizations": 0,
            "loss_making_realizations": 0,
            "breakeven_realizations": 0,
            "holding_buckets": {},
        }

    holding_days = [r["holding_days"] for r in rows]
    returns = [r["return_pct"] for r in rows]

    profitable = sum(1 for r in rows if r["realized_pnl"] > 0)
    loss_making = sum(1 for r in rows if r["realized_pnl"] < 0)
    breakeven = sum(1 for r in rows if r["realized_pnl"] == 0)

    buckets: dict[str, dict[str, Any]] = {}

    for row in rows:
        bucket = row["holding_bucket"]

        if bucket not in buckets:
            buckets[bucket] = {
                "realizations": 0,
                "quantity": 0,
                "buy_value": 0.0,
                "sell_value": 0.0,
                "realized_pnl": 0.0,
            }

        item = buckets[bucket]
        item["realizations"] += 1
        item["quantity"] += row["quantity"]
        item["buy_value"] += row["buy_value"]
        item["sell_value"] += row["sell_value"]
        item["realized_pnl"] += row["realized_pnl"]

    return {
        "realizations_used": len(rows),
        "persons": len({r["person_id"] for r in rows}),
        "symbols": len({r["symbol_id"] for r in rows}),
        "first_buy_date": min(r["buy_date"] for r in rows),
        "last_sell_date": max(r["sell_date"] for r in rows),
        "total_quantity": sum(r["quantity"] for r in rows),
        "total_buy_value": sum(r["buy_value"] for r in rows),
        "total_sell_value": sum(r["sell_value"] for r in rows),
        "total_realized_pnl": sum(r["realized_pnl"] for r in rows),
        "average_holding_days": mean(holding_days),
        "median_holding_days": sorted(holding_days)[
            len(holding_days) // 2
        ]
        if len(holding_days) % 2 == 1
        else (
            sorted(holding_days)[len(holding_days) // 2 - 1]
            + sorted(holding_days)[len(holding_days) // 2]
        )
        / 2,
        "average_return_pct": mean(returns),
        "profitable_realizations": profitable,
        "loss_making_realizations": loss_making,
        "breakeven_realizations": breakeven,
        "holding_buckets": buckets,
    }


def _build_person_summary(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[int, list[dict[str, Any]]] = {}

    for row in rows:
        grouped.setdefault(row["person_id"], []).append(row)

    result = []

    for person_id, items in grouped.items():
        pnl = sum(r["realized_pnl"] for r in items)
        buy_value = sum(r["buy_value"] for r in items)
        sell_value = sum(r["sell_value"] for r in items)

        result.append(
            {
                "person_id": person_id,
                "realizations": len(items),
                "quantity": sum(r["quantity"] for r in items),
                "buy_value": buy_value,
                "sell_value": sell_value,
                "realized_pnl": pnl,
                "average_holding_days": mean(
                    r["holding_days"] for r in items
                ),
                "average_return_pct": mean(
                    r["return_pct"] for r in items
                ),
                "profitable_realizations": sum(
                    1 for r in items if r["realized_pnl"] > 0
                ),
                "loss_making_realizations": sum(
                    1 for r in items if r["realized_pnl"] < 0
                ),
            }
        )

    result.sort(
        key=lambda x: (
            x["realized_pnl"],
            x["sell_value"],
        ),
        reverse=True,
    )

    return result


def _build_symbol_summary(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[int, list[dict[str, Any]]] = {}

    for row in rows:
        grouped.setdefault(row["symbol_id"], []).append(row)

    result = []

    for symbol_id, items in grouped.items():
        result.append(
            {
                "symbol_id": symbol_id,
                "realizations": len(items),
                "quantity": sum(r["quantity"] for r in items),
                "buy_value": sum(r["buy_value"] for r in items),
                "sell_value": sum(r["sell_value"] for r in items),
                "realized_pnl": sum(
                    r["realized_pnl"] for r in items
                ),
                "average_holding_days": mean(
                    r["holding_days"] for r in items
                ),
                "average_return_pct": mean(
                    r["return_pct"] for r in items
                ),
            }
        )

    result.sort(
        key=lambda x: x["realized_pnl"],
        reverse=True,
    )

    return result


def _validate_rows(
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    total = len(rows)

    sell_before_buy = sum(
        1 for r in rows if r["holding_days"] < 0
    )

    nonpositive_quantity = sum(
        1 for r in rows if r["quantity"] <= 0
    )

    nonpositive_buy_price = sum(
        1 for r in rows if r["buy_price"] <= 0
    )

    nonpositive_sell_price = sum(
        1 for r in rows if r["sell_price"] <= 0
    )

    invalid_return = sum(
        1
        for r in rows
        if not math.isfinite(r["return_pct"])
    )

    invalid_pnl = sum(
        1
        for r in rows
        if not math.isfinite(r["realized_pnl"])
    )

    valid = all(
        value == 0
        for value in (
            sell_before_buy,
            nonpositive_quantity,
            nonpositive_buy_price,
            nonpositive_sell_price,
            invalid_return,
            invalid_pnl,
        )
    )

    return {
        "total": total,
        "sell_before_buy": sell_before_buy,
        "nonpositive_quantity": nonpositive_quantity,
        "nonpositive_buy_price": nonpositive_buy_price,
        "nonpositive_sell_price": nonpositive_sell_price,
        "invalid_return": invalid_return,
        "invalid_pnl": invalid_pnl,
        "valid": valid,
    }


def run_round_trip(
    conn: sqlite3.Connection,
) -> dict[str, Any]:
    """
    اجرای کامل تحلیل Round Trip.
    """

    raw_rows = _load_round_trip_realizations(conn)
    rows = _build_round_trip_rows(raw_rows)

    validation = _validate_rows(rows)
    summary = _build_summary(rows)

    person_summary = _build_person_summary(rows)
    symbol_summary = _build_symbol_summary(rows)

    return {
        "ready": bool(rows) and validation["valid"],
        "methodology": {
            "type": "fifo_transaction_round_trip",
            "description": (
                "اتصال دقیق خرید به فروش بر اساس FIFO و محاسبه "
                "مدت نگهداری، ارزش خرید، ارزش فروش و سود/زیان تحقق‌یافته."
            ),
            "included_source_type": "buy",
            "excluded_source_type": "opening",
            "not_proof_of": [
                "market_manipulation",
                "player_intent",
                "illegal_activity",
                "ownership_change",
            ],
        },
        **summary,
        "validation": validation,
        "person_summary": person_summary,
        "symbol_summary": symbol_summary,
        "rows": rows,
    }


def audit_round_trip(
    db_path: str | Path,
) -> dict[str, Any]:
    """
    اجرای مستقل Engine برای Audit.
    """

    path = Path(db_path)

    if not path.exists():
        return {
            "ready": False,
            "error": f"Database not found: {path}",
        }

    conn = sqlite3.connect(str(path))

    try:
        return run_round_trip(conn)
    finally:
        conn.close()


def main() -> None:
    """
    اجرای مستقیم برای تست Engine.
    """

    db_path = Path("data") / "smart_equity.db"

    result = audit_round_trip(db_path)

    print(result)


if __name__ == "__main__":
    main()