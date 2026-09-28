"""
Smart Equity — Anomaly Detection Engine
سامانه تشخیص ناهنجاری معاملات

Phase 6
Read-only analytical engine.
این ماژول هیچ تغییری در دیتابیس ایجاد نمی‌کند و جدول alerts را نمی‌نویسد.
"""

from __future__ import annotations

import json
import math
import sqlite3
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
        if math.isfinite(result):
            return result
    except (TypeError, ValueError):
        pass
    return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _percentile(values: list[float], percentile: float) -> float:
    """Linear percentile without external dependencies."""
    if not values:
        return 0.0

    ordered = sorted(values)

    if len(ordered) == 1:
        return ordered[0]

    position = (len(ordered) - 1) * percentile
    lower = int(math.floor(position))
    upper = int(math.ceil(position))

    if lower == upper:
        return ordered[lower]

    fraction = position - lower
    return ordered[lower] + (
        ordered[upper] - ordered[lower]
    ) * fraction


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(statistics.median(values))


def _iqr_upper(values: list[float], multiplier: float = 3.0) -> float:
    """
    Conservative upper IQR threshold.

    Q3 + multiplier * IQR
    """
    if len(values) < 4:
        return float("inf")

    q1 = _percentile(values, 0.25)
    q3 = _percentile(values, 0.75)
    iqr = q3 - q1

    if iqr <= 0:
        return q3

    return q3 + multiplier * iqr


def _z_score(value: float, values: list[float]) -> float:
    if len(values) < 2:
        return 0.0

    mean = statistics.mean(values)
    stdev = statistics.pstdev(values)

    if stdev <= 0:
        return 0.0

    return (value - mean) / stdev


# ---------------------------------------------------------------------------
# Main Engine
# ---------------------------------------------------------------------------

def run_anomaly_detection(conn: sqlite3.Connection) -> dict[str, Any]:
    """
    Execute anomaly detection against the current database.

    Read-only:
    - SELECT only
    - does not INSERT/UPDATE/DELETE
    - does not write to alerts
    """

    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """
        SELECT
            transaction_id,
            trade_date_gregorian,
            trade_date_jalali,
            symbol_id,
            buyer_person_id,
            seller_person_id,
            buyer_broker_id,
            seller_broker_id,
            quantity,
            price,
            value
        FROM transactions
        WHERE is_duplicate_of IS NULL
        ORDER BY trade_date_gregorian, transaction_id
        """
    ).fetchall()

    if not rows:
        return {
            "ready": False,
            "reason": "هیچ معامله‌ای برای تحلیل وجود ندارد.",
            "transactions_used": 0,
            "alerts": [],
            "summary": {},
        }

    transactions = [dict(row) for row in rows]

    # -----------------------------------------------------------------------
    # Daily distributions
    # -----------------------------------------------------------------------

    daily_values: dict[str, list[float]] = defaultdict(list)
    daily_quantities: dict[str, list[float]] = defaultdict(list)
    daily_prices: dict[str, list[float]] = defaultdict(list)

    for row in transactions:
        date = row["trade_date_gregorian"]
        daily_values[date].append(_safe_float(row["value"]))
        daily_quantities[date].append(_safe_float(row["quantity"]))
        daily_prices[date].append(_safe_float(row["price"]))

    alerts: list[dict[str, Any]] = []

    # -----------------------------------------------------------------------
    # 1. Transaction value / quantity outliers
    # -----------------------------------------------------------------------

    value_thresholds: dict[str, float] = {}
    quantity_thresholds: dict[str, float] = {}
    threshold_methods: dict[str, str] = {}

    # Global P99 values are used only as a stability guard for
    # low-volume days.
    all_values = [
        _safe_float(row["value"])
        for row in transactions
    ]
    all_quantities = [
        _safe_float(row["quantity"])
        for row in transactions
    ]

    global_value_p99 = _percentile(all_values, 0.99)
    global_quantity_p99 = _percentile(all_quantities, 0.99)

    for date, values in daily_values.items():
        if len(values) >= 100:
            value_thresholds[date] = _percentile(values, 0.99)
            threshold_methods[date] = "daily_p99"
        else:
            value_thresholds[date] = max(
                _percentile(values, 0.95),
                global_value_p99 * 0.50,
            )
            threshold_methods[date] = "small_day_guard"

    for date, quantities in daily_quantities.items():
        if len(quantities) >= 100:
            quantity_thresholds[date] = _percentile(quantities, 0.99)
        else:
            quantity_thresholds[date] = max(
                _percentile(quantities, 0.95),
                global_quantity_p99 * 0.50,
            )

    for row in transactions:
        date = row["trade_date_gregorian"]
        value = _safe_float(row["value"])
        quantity = _safe_float(row["quantity"])

        value_limit = value_thresholds.get(date, float("inf"))
        quantity_limit = quantity_thresholds.get(date, float("inf"))

        if value_limit > 0 and value > value_limit:
            alerts.append(
                {
                    "alert_type": "trade_value_outlier",
                    "trade_date_gregorian": date,
                    "trade_date_jalali": row["trade_date_jalali"],
                    "symbol_id": row["symbol_id"],
                    "person_id": row["buyer_person_id"],
                    "broker_id": row["buyer_broker_id"],
                    "value": value,
                    "reason": (
                        "ارزش این معامله نسبت به توزیع ارزش معاملات "
                        "همان روز به‌صورت غیرعادی بالا است."
                    ),
                    "transaction_id": row["transaction_id"],
                    "metric_value": value,
                    "threshold": value_limit,
                    "threshold_method": threshold_methods.get(
                        date, "daily_p99"
                    ),
                    "threshold_percentile": (
                        0.99
                        if len(daily_values.get(date, [])) >= 100
                        else 0.95
                    ),
                }
            )

        if quantity_limit > 0 and quantity > quantity_limit:
            alerts.append(
                {
                    "alert_type": "trade_quantity_outlier",
                    "trade_date_gregorian": date,
                    "trade_date_jalali": row["trade_date_jalali"],
                    "symbol_id": row["symbol_id"],
                    "person_id": row["buyer_person_id"],
                    "broker_id": row["buyer_broker_id"],
                    "value": value,
                    "reason": (
                        "تعداد سهام این معامله نسبت به توزیع تعداد سهام "
                        "معاملات همان روز به‌صورت غیرعادی بالا است."
                    ),
                    "transaction_id": row["transaction_id"],
                    "metric_value": quantity,
                    "threshold": quantity_limit,
                    "threshold_method": threshold_methods.get(
                        date, "daily_p99"
                    ),
                    "threshold_percentile": (
                        0.99
                        if len(daily_quantities.get(date, [])) >= 100
                        else 0.95
                    ),
                }
            )

    # -----------------------------------------------------------------------
    # 2. Price outliers
    # -----------------------------------------------------------------------

    for row in transactions:
        date = row["trade_date_gregorian"]
        price = _safe_float(row["price"])
        prices = daily_prices.get(date, [])

        if len(prices) < 5:
            continue

        median_price = _median(prices)

        if median_price <= 0:
            continue

        deviation_pct = abs(price - median_price) / median_price * 100.0

        # A transaction price more than 5% away from the daily median
        # is only a statistical flag, not a statement about legitimacy.
        if deviation_pct > 5.0:
            alerts.append(
                {
                    "alert_type": "price_outlier",
                    "trade_date_gregorian": date,
                    "trade_date_jalali": row["trade_date_jalali"],
                    "symbol_id": row["symbol_id"],
                    "person_id": row["buyer_person_id"],
                    "broker_id": row["buyer_broker_id"],
                    "value": _safe_float(row["value"]),
                    "reason": (
                        "قیمت معامله بیش از ۵ درصد با میانه قیمت معاملات "
                        "همان روز فاصله دارد."
                    ),
                    "transaction_id": row["transaction_id"],
                    "metric_value": price,
                    "reference_value": median_price,
                    "deviation_pct": deviation_pct,
                }
            )

    # -----------------------------------------------------------------------
    # 3. Daily player concentration
    # -----------------------------------------------------------------------

    daily_buyer_value: dict[str, Counter] = defaultdict(Counter)
    daily_seller_value: dict[str, Counter] = defaultdict(Counter)
    daily_total_value: Counter = Counter()

    for row in transactions:
        date = row["trade_date_gregorian"]
        value = _safe_float(row["value"])
        buyer = row["buyer_person_id"]
        seller = row["seller_person_id"]

        daily_total_value[date] += value

        if buyer is not None:
            daily_buyer_value[date][buyer] += value

        if seller is not None:
            daily_seller_value[date][seller] += value

    for date in daily_total_value:
        total = daily_total_value[date]

        if total <= 0:
            continue

        buyer_counter = daily_buyer_value[date]
        seller_counter = daily_seller_value[date]

        if buyer_counter:
            buyer_person, buyer_value = buyer_counter.most_common(1)[0]
            buyer_share = buyer_value / total

            if buyer_share >= 0.30:
                alerts.append(
                    {
                        "alert_type": "player_concentration",
                        "trade_date_gregorian": date,
                        "trade_date_jalali": None,
                        "symbol_id": None,
                        "person_id": buyer_person,
                        "broker_id": None,
                        "value": buyer_value,
                        "reason": (
                            "سهم ارزش خرید یک شخص در این روز حداقل ۳۰ درصد "
                            "از کل ارزش معاملات روز بوده است."
                        ),
                        "side": "buyer",
                        "share": buyer_share,
                    }
                )

        if seller_counter:
            seller_person, seller_value = seller_counter.most_common(1)[0]
            seller_share = seller_value / total

            if seller_share >= 0.30:
                alerts.append(
                    {
                        "alert_type": "player_concentration",
                        "trade_date_gregorian": date,
                        "trade_date_jalali": None,
                        "symbol_id": None,
                        "person_id": seller_person,
                        "broker_id": None,
                        "value": seller_value,
                        "reason": (
                            "سهم ارزش فروش یک شخص در این روز حداقل ۳۰ درصد "
                            "از کل ارزش معاملات روز بوده است."
                        ),
                        "side": "seller",
                        "share": seller_share,
                    }
                )

    # -----------------------------------------------------------------------
    # 4. Repeated buyer-seller pairs
    #
    # Important:
    # A high number of trades in one day and repeated activity across
    # multiple days are reported separately.
    # -----------------------------------------------------------------------

    pair_stats: dict[tuple[int, int], dict[str, Any]] = {}

    for row in transactions:
        buyer = row["buyer_person_id"]
        seller = row["seller_person_id"]

        if buyer is None or seller is None:
            continue

        key = (int(buyer), int(seller))

        item = pair_stats.setdefault(
            key,
            {
                "trades": 0,
                "days": set(),
                "quantity": 0,
                "value": 0.0,
                "transactions": [],
            },
        )

        item["trades"] += 1
        item["days"].add(row["trade_date_gregorian"])
        item["quantity"] += _safe_int(row["quantity"])
        item["value"] += _safe_float(row["value"])
        item["transactions"].append(row["transaction_id"])

    for (buyer, seller), item in pair_stats.items():
        trades = item["trades"]
        days = len(item["days"])

        # Formal flag conditions are deliberately transparent:
        # - at least 20 trades in one pair
        # - AND either activity across >= 2 days or >= 20 trades overall.
        if trades < 20:
            continue

        if days >= 2 or trades >= 20:
            alerts.append(
                {
                    "alert_type": "pair_repetition",
                    "trade_date_gregorian": None,
                    "trade_date_jalali": None,
                    "symbol_id": None,
                    "person_id": buyer,
                    "broker_id": None,
                    "value": item["value"],
                    "reason": (
                        "یک جفت خریدار و فروشنده تعداد قابل توجهی معامله "
                        "با یکدیگر داشته‌اند؛ این مورد صرفاً یک الگوی آماری "
                        "برای بررسی بیشتر است و به‌تنهایی نشانه تخلف یا "
                        "دستکاری نیست."
                    ),
                    "buyer_person_id": buyer,
                    "seller_person_id": seller,
                    "trades": trades,
                    "days": days,
                    "quantity": item["quantity"],
                    "supporting_transaction_ids": item["transactions"],
                }
            )

    # -----------------------------------------------------------------------
    # 5. Broker concentration
    # -----------------------------------------------------------------------

    daily_broker_value: dict[str, Counter] = defaultdict(Counter)

    for row in transactions:
        date = row["trade_date_gregorian"]
        value = _safe_float(row["value"])

        buyer_broker = row["buyer_broker_id"]
        seller_broker = row["seller_broker_id"]

        if buyer_broker is not None:
            daily_broker_value[date][buyer_broker] += value

        if seller_broker is not None:
            daily_broker_value[date][seller_broker] += value

    for date, broker_counter in daily_broker_value.items():
        total_broker_value = sum(broker_counter.values())

        if total_broker_value <= 0:
            continue

        broker_id, broker_value = broker_counter.most_common(1)[0]
        share = broker_value / total_broker_value

        if share >= 0.35:
            alerts.append(
                {
                    "alert_type": "broker_concentration",
                    "trade_date_gregorian": date,
                    "trade_date_jalali": None,
                    "symbol_id": None,
                    "person_id": None,
                    "broker_id": broker_id,
                    "value": broker_value,
                    "reason": (
                        "سهم ارزش ثبت‌شده برای یک کارگزار در این روز "
                        "حداقل ۳۵ درصد از ارزش کارگزاری محاسبه‌شده بوده است."
                    ),
                    "share": share,
                }
            )

    # -----------------------------------------------------------------------
    # Sort / summary
    # -----------------------------------------------------------------------

    # -----------------------------------------------------------------------
    # 6. Round-trip pattern
    # -----------------------------------------------------------------------
    #
    # Person-level analytical pattern:
    #   - same-day round trips >= 10
    #   OR
    #   - 0-3 day round trips >= 20 AND share >= 30%
    #
    # This is a statistical pattern only. It is NOT evidence of:
    # market manipulation, illegal activity, player intent,
    # or ownership change.
    # -----------------------------------------------------------------------

    round_trip_stats: dict[int, dict[str, int]] = {}

    fifo_rows = conn.execute(
        """
        SELECT
            fr.person_id,
            fl.lot_date_gregorian AS buy_date,
            t.trade_date_gregorian AS sell_date
        FROM fifo_realizations fr
        JOIN fifo_lots fl
            ON fl.lot_id = fr.lot_id
        JOIN transactions t
            ON t.transaction_id = fr.sell_transaction_id
        WHERE fr.cost_known = 1
          AND fl.source_type = 'buy'
        """
    ).fetchall()

    from datetime import date as _date

    for fifo_row in fifo_rows:
        try:
            buy_date = _date.fromisoformat(
                str(fifo_row["buy_date"])
            )
            sell_date = _date.fromisoformat(
                str(fifo_row["sell_date"])
            )
        except (TypeError, ValueError):
            continue

        holding_days = (sell_date - buy_date).days

        if holding_days < 0:
            continue

        person_id = int(fifo_row["person_id"])

        stats = round_trip_stats.setdefault(
            person_id,
            {
                "total": 0,
                "same_day": 0,
                "fast_0_3": 0,
            },
        )

        stats["total"] += 1

        if holding_days == 0:
            stats["same_day"] += 1

        if holding_days <= 3:
            stats["fast_0_3"] += 1

    round_trip_alert_count = 0

    for person_id, stats in round_trip_stats.items():
        total = stats["total"]
        same_day = stats["same_day"]
        fast_0_3 = stats["fast_0_3"]

        if total <= 0:
            continue

        fast_share = fast_0_3 / total
        same_share = same_day / total

        same_day_trigger = same_day >= 10
        fast_trigger = (
            fast_0_3 >= 20
            and fast_share >= 0.30
        )

        if not (same_day_trigger or fast_trigger):
            continue

        if same_day_trigger and fast_trigger:
            condition = "same_day_and_fast_0_3"
        elif same_day_trigger:
            condition = "same_day"
        else:
            condition = "fast_0_3_share"

        alerts.append(
            {
                "alert_type": "round_trip_pattern",
                "trade_date_gregorian": None,
                "trade_date_jalali": None,
                "symbol_id": None,
                "person_id": person_id,
                "broker_id": None,
                "value": None,
                "reason": (
                    "????? ?????????? ??????? ??????????? ????????? "
                    "?? ???? ???? ??????? FIFO ??????? ??? ???? "
                    "??? ????? ????? ????? ???."
                ),
                "round_trip_count": total,
                "same_day_count": same_day,
                "fast_0_3_day_count": fast_0_3,
                "fast_0_3_day_share": fast_share,
                "same_day_share": same_share,
                "rule_condition": condition,
            }
        )

        round_trip_alert_count += 1

    alert_type_counts = Counter(
        alert["alert_type"] for alert in alerts
    )

    dates = sorted(
        {
            row["trade_date_gregorian"]
            for row in transactions
            if row["trade_date_gregorian"]
        }
    )

    symbols = {
        row["symbol_id"]
        for row in transactions
        if row["symbol_id"] is not None
    }

    persons = {
        person
        for row in transactions
        for person in (
            row["buyer_person_id"],
            row["seller_person_id"],
        )
        if person is not None
    }

    brokers = {
        broker
        for row in transactions
        for broker in (
            row["buyer_broker_id"],
            row["seller_broker_id"],
        )
        if broker is not None
    }

    return {
        "ready": True,
        "methodology": {
            "type": "transparent_statistical_anomaly_detection",
            "read_only": True,
            "description": (
                "ناهنجاری‌ها بر اساس انحراف آماری، تمرکز و تکرار الگوها "
                "شناسایی می‌شوند."
            ),
            "not_proof_of": [
                "market_manipulation",
                "illegal_activity",
                "player_intent",
                "ownership_change",
            ],
            "rules": {
                "trade_value_outlier": (
                    "daily P99 when day transactions >= 100; "
                    "otherwise max(daily P95, 50% of global P99)"
                ),
                "trade_quantity_outlier": (
                    "daily P99 when day transactions >= 100; "
                    "otherwise max(daily P95, 50% of global P99)"
                ),
                "price_outlier": "more than 5% from daily median",
                "player_concentration": ">= 30% of daily transaction value",
                "pair_repetition": ">= 20 trades",
                "broker_concentration": ">= 35% of daily broker value",
                "round_trip_pattern": (
                    "same-day round trips >= 10, or "
                    "0-3 day round trips >= 20 with share >= 30%"
                ),
            },
        },
        "transactions_used": len(transactions),
        "days": len(dates),
        "symbols": len(symbols),
        "persons": len(persons),
        "brokers": len(brokers),
        "alerts_count": len(alerts),
        "alert_type_counts": dict(alert_type_counts),
        "date_range": {
            "first": dates[0] if dates else None,
            "last": dates[-1] if dates else None,
        },
        "alerts": alerts,
    }


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_anomaly_result(result: dict[str, Any]) -> dict[str, Any]:
    """
    Validate the Engine result without modifying the database.
    """

    checks = {
        "ready": bool(result.get("ready")),
        "transactions_positive": result.get("transactions_used", 0) > 0,
        "days_positive": result.get("days", 0) > 0,
        "alert_count_matches": (
            result.get("alerts_count", 0)
            == len(result.get("alerts", []))
        ),
        "alert_types_match": (
            sum(result.get("alert_type_counts", {}).values())
            == result.get("alerts_count", 0)
        ),
        "valid_alert_types": all(
            isinstance(alert.get("alert_type"), str)
            and bool(alert.get("alert_type"))
            for alert in result.get("alerts", [])
        ),
    }

    return {
        "valid": all(checks.values()),
        "checks": checks,
    }


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------

def audit_anomaly(db_path: str | Path) -> dict[str, Any]:
    """
    Run anomaly detection against a database path.
    """

    db_path = Path(db_path)

    if not db_path.exists():
        return {
            "ready": False,
            "reason": f"Database not found: {db_path}",
        }

    conn = sqlite3.connect(str(db_path))

    try:
        result = run_anomaly_detection(conn)
        validation = validate_anomaly_result(result)

        result["validation"] = validation

        return result
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    db_path = Path("data/smart_equity.db")

    result = audit_anomaly(db_path)

    printable = {
        "ready": result.get("ready"),
        "transactions_used": result.get("transactions_used"),
        "days": result.get("days"),
        "symbols": result.get("symbols"),
        "persons": result.get("persons"),
        "brokers": result.get("brokers"),
        "alerts_count": result.get("alerts_count"),
        "alert_type_counts": result.get("alert_type_counts"),
        "date_range": result.get("date_range"),
        "validation": result.get("validation"),
    }

    print(json.dumps(
        printable,
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()
