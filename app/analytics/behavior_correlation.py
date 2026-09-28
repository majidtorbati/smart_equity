"""
Smart Equity — Phase 7
Behavior Correlation Engine

Read-only behavioral analysis at person level.

This engine:
- does not modify the database
- does not create alerts
- does not rank persons by suspiciousness
- reports statistical relationships only
- correlation does not imply causation, manipulation, illegal activity,
  player intent, or ownership change.
"""

from __future__ import annotations

import math
import sqlite3
import statistics
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


def _pearson(x: list[float], y: list[float]) -> float:
    if len(x) != len(y) or len(x) < 2:
        return 0.0

    pairs = [
        (float(a), float(b))
        for a, b in zip(x, y)
        if math.isfinite(float(a)) and math.isfinite(float(b))
    ]

    if len(pairs) < 2:
        return 0.0

    xs = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]

    mean_x = statistics.mean(xs)
    mean_y = statistics.mean(ys)

    numerator = sum(
        (a - mean_x) * (b - mean_y)
        for a, b in zip(xs, ys)
    )

    denom_x = math.sqrt(
        sum((a - mean_x) ** 2 for a in xs)
    )
    denom_y = math.sqrt(
        sum((b - mean_y) ** 2 for b in ys)
    )

    if denom_x <= 0 or denom_y <= 0:
        return 0.0

    return numerator / (denom_x * denom_y)


def _rank(values: list[float]) -> list[float]:
    """
    Average ranks for ties.
    """
    indexed = sorted(
        enumerate(values),
        key=lambda item: item[1],
    )

    ranks = [0.0] * len(values)
    i = 0

    while i < len(indexed):
        j = i

        while (
            j + 1 < len(indexed)
            and indexed[j + 1][1] == indexed[i][1]
        ):
            j += 1

        average_rank = (i + j + 2) / 2.0

        for k in range(i, j + 1):
            original_index = indexed[k][0]
            ranks[original_index] = average_rank

        i = j + 1

    return ranks


def _spearman(x: list[float], y: list[float]) -> float:
    if len(x) != len(y) or len(x) < 2:
        return 0.0

    pairs = [
        (float(a), float(b))
        for a, b in zip(x, y)
        if math.isfinite(float(a)) and math.isfinite(float(b))
    ]

    if len(pairs) < 2:
        return 0.0

    xs = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]

    return _pearson(_rank(xs), _rank(ys))


def _correlation(
    rows: list[dict[str, Any]],
    x_key: str,
    y_key: str,
) -> dict[str, Any]:
    x = [
        _safe_float(row.get(x_key))
        for row in rows
    ]
    y = [
        _safe_float(row.get(y_key))
        for row in rows
    ]

    return {
        "x": x_key,
        "y": y_key,
        "n": len(x),
        "pearson": _pearson(x, y),
        "spearman": _spearman(x, y),
    }


# ---------------------------------------------------------------------------
# Person behavioral metrics
# ---------------------------------------------------------------------------

def _load_person_behavior(
    conn: sqlite3.Connection,
) -> list[dict[str, Any]]:
    """
    Build person-level behavioral metrics from transactions.

    Each transaction contributes once to:
    - buyer activity
    - seller activity

    The transaction itself is not duplicated inside either side.
    """

    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """
        SELECT
            transaction_id,
            trade_date_gregorian,
            symbol_id,
            buyer_person_id,
            seller_person_id,
            quantity,
            price,
            value
        FROM transactions
        WHERE is_duplicate_of IS NULL
        ORDER BY transaction_id
        """
    ).fetchall()

    people: dict[int, dict[str, Any]] = {}

    for row in rows:
        value = _safe_float(row["value"])
        quantity = _safe_int(row["quantity"])
        person_sides = (
            (
                _safe_int(row["buyer_person_id"], -1),
                "buy",
            ),
            (
                _safe_int(row["seller_person_id"], -1),
                "sell",
            ),
        )

        for person_id, side in person_sides:
            if person_id < 0:
                continue

            item = people.setdefault(
                person_id,
                {
                    "person_id": person_id,
                    "transaction_count": 0,
                    "active_days": set(),
                    "buy_count": 0,
                    "sell_count": 0,
                    "buy_quantity": 0,
                    "sell_quantity": 0,
                    "buy_value": 0.0,
                    "sell_value": 0.0,
                    "total_value": 0.0,
                    "max_daily_value_share": 0.0,
                    "daily_value": {},
                },
            )

            item["transaction_count"] += 1
            item["active_days"].add(
                str(row["trade_date_gregorian"])
            )

            item["total_value"] += value

            day = str(row["trade_date_gregorian"])
            daily = item["daily_value"]
            daily[day] = daily.get(day, 0.0) + value

            if side == "buy":
                item["buy_count"] += 1
                item["buy_quantity"] += quantity
                item["buy_value"] += value
            else:
                item["sell_count"] += 1
                item["sell_quantity"] += quantity
                item["sell_value"] += value

    # Daily total market values for concentration.
    daily_totals = {
        str(row["trade_date_gregorian"]): _safe_float(row["day_value"])
        for row in conn.execute(
            """
            SELECT
                trade_date_gregorian,
                SUM(value) AS day_value
            FROM transactions
            WHERE is_duplicate_of IS NULL
            GROUP BY trade_date_gregorian
            """
        ).fetchall()
    }

    result: list[dict[str, Any]] = []

    for item in people.values():
        daily_value = item.pop("daily_value")

        shares = []
        for day, value in daily_value.items():
            day_total = daily_totals.get(day, 0.0)
            if day_total > 0:
                shares.append(value / day_total)

        max_share = max(shares) if shares else 0.0
        avg_share = (
            statistics.mean(shares)
            if shares
            else 0.0
        )

        buy_value = _safe_float(item["buy_value"])
        sell_value = _safe_float(item["sell_value"])
        total_value = _safe_float(item["total_value"])

        net_value = buy_value - sell_value

        result.append(
            {
                "person_id": item["person_id"],
                "transaction_count": item["transaction_count"],
                "active_days": len(item["active_days"]),
                "buy_count": item["buy_count"],
                "sell_count": item["sell_count"],
                "buy_quantity": item["buy_quantity"],
                "sell_quantity": item["sell_quantity"],
                "buy_value": buy_value,
                "sell_value": sell_value,
                "total_value": total_value,
                "net_value": net_value,
                "buy_value_share": (
                    buy_value / total_value
                    if total_value > 0
                    else 0.0
                ),
                "sell_value_share": (
                    sell_value / total_value
                    if total_value > 0
                    else 0.0
                ),
                "max_daily_value_share": max_share,
                "avg_daily_value_share": avg_share,
            }
        )

    return result


# ---------------------------------------------------------------------------
# Round Trip metrics
# ---------------------------------------------------------------------------

def _load_round_trip_metrics(
    conn: sqlite3.Connection,
) -> dict[int, dict[str, Any]]:
    """
    Load FIFO transaction round trips.

    Only source_type='buy' is included.
    Opening inventory is excluded, matching Phase 5.
    """

    rows = conn.execute(
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

    result: dict[int, dict[str, Any]] = {}

    from datetime import date

    for row in rows:
        try:
            buy_date = date.fromisoformat(
                str(row["buy_date"])
            )
            sell_date = date.fromisoformat(
                str(row["sell_date"])
            )
        except (TypeError, ValueError):
            continue

        holding_days = (sell_date - buy_date).days

        if holding_days < 0:
            continue

        person_id = _safe_int(row["person_id"], -1)

        if person_id < 0:
            continue

        item = result.setdefault(
            person_id,
            {
                "round_trip_count": 0,
                "same_day_count": 0,
                "fast_0_3_day_count": 0,
                "holding_days_total": 0,
            },
        )

        item["round_trip_count"] += 1
        item["holding_days_total"] += holding_days

        if holding_days == 0:
            item["same_day_count"] += 1

        if holding_days <= 3:
            item["fast_0_3_day_count"] += 1

    for item in result.values():
        total = item["round_trip_count"]

        item["avg_holding_days"] = (
            item["holding_days_total"] / total
            if total > 0
            else 0.0
        )

        item["fast_0_3_day_share"] = (
            item["fast_0_3_day_count"] / total
            if total > 0
            else 0.0
        )

        item["same_day_share"] = (
            item["same_day_count"] / total
            if total > 0
            else 0.0
        )

        item.pop("holding_days_total", None)

    return result


# ---------------------------------------------------------------------------
# Anomaly metrics
# ---------------------------------------------------------------------------

def _load_anomaly_metrics(
    conn: sqlite3.Connection,
) -> dict[int, dict[str, Any]]:
    """
    Reconstruct person-level anomaly counts using the same seven
    analytical rules established in Phase 6.

    This is intentionally independent of the anomaly Engine so Phase 7
    remains auditable and does not modify Phase 6.
    """

    conn.row_factory = sqlite3.Row

    transactions = conn.execute(
        """
        SELECT
            transaction_id,
            trade_date_gregorian,
            buyer_person_id,
            seller_person_id,
            buyer_broker_id,
            seller_broker_id,
            quantity,
            price,
            value
        FROM transactions
        WHERE is_duplicate_of IS NULL
        ORDER BY transaction_id
        """
    ).fetchall()

    if not transactions:
        return {}

    from collections import Counter, defaultdict

    daily_rows: dict[str, list[sqlite3.Row]] = defaultdict(list)

    for row in transactions:
        daily_rows[str(row["trade_date_gregorian"])].append(row)

    flagged: dict[int, set[str]] = defaultdict(set)

    # Rules 1-3
    for day, rows in daily_rows.items():
        values = [_safe_float(r["value"]) for r in rows]
        quantities = [_safe_float(r["quantity"]) for r in rows]
        prices = [_safe_float(r["price"]) for r in rows]

        n = len(rows)

        # Match Phase 6 small-day guard.
        global_value_values = [
            _safe_float(r["value"])
            for r in transactions
        ]
        global_quantity_values = [
            _safe_float(r["quantity"])
            for r in transactions
        ]

        def percentile(
            vals: list[float],
            p: float,
        ) -> float:
            if not vals:
                return 0.0
            ordered = sorted(vals)
            if len(ordered) == 1:
                return ordered[0]
            position = (len(ordered) - 1) * p
            lower = int(math.floor(position))
            upper = int(math.ceil(position))
            if lower == upper:
                return ordered[lower]
            weight = position - lower
            return (
                ordered[lower] * (1.0 - weight)
                + ordered[upper] * weight
            )

        global_value_p99 = percentile(
            global_value_values, 0.99
        )
        global_quantity_p99 = percentile(
            global_quantity_values, 0.99
        )

        if n >= 100:
            value_threshold = percentile(values, 0.99)
            quantity_threshold = percentile(
                quantities, 0.99
            )
        else:
            value_threshold = max(
                percentile(values, 0.95),
                0.50 * global_value_p99,
            )
            quantity_threshold = max(
                percentile(quantities, 0.95),
                0.50 * global_quantity_p99,
            )

        daily_median_price = (
            statistics.median(prices)
            if prices
            else 0.0
        )

        for row in rows:
            tid = _safe_int(row["transaction_id"])

            if _safe_float(row["value"]) > value_threshold:
                flagged[tid].add("trade_value_outlier")

            if _safe_float(row["quantity"]) > quantity_threshold:
                flagged[tid].add("trade_quantity_outlier")

            price = _safe_float(row["price"])
            if (
                daily_median_price > 0
                and abs(price - daily_median_price)
                / daily_median_price > 0.05
            ):
                flagged[tid].add("price_outlier")

    # Rule 4 — player concentration
    for day, rows in daily_rows.items():
        buyer_values = Counter()
        seller_values = Counter()
        total_value = sum(
            _safe_float(r["value"])
            for r in rows
        )

        if total_value <= 0:
            continue

        for row in rows:
            value = _safe_float(row["value"])
            buyer_values[
                _safe_int(row["buyer_person_id"], -1)
            ] += value
            seller_values[
                _safe_int(row["seller_person_id"], -1)
            ] += value

        concentrated_buyers = {
            person
            for person, value in buyer_values.items()
            if person >= 0
            and value / total_value >= 0.30
        }

        concentrated_sellers = {
            person
            for person, value in seller_values.items()
            if person >= 0
            and value / total_value >= 0.30
        }

        for row in rows:
            buyer = _safe_int(
                row["buyer_person_id"], -1
            )
            seller = _safe_int(
                row["seller_person_id"], -1
            )

            tid = _safe_int(row["transaction_id"])

            if buyer in concentrated_buyers:
                flagged[tid].add("player_concentration")

            if seller in concentrated_sellers:
                flagged[tid].add("player_concentration")

    # Rule 5 — pair repetition
    for day, rows in daily_rows.items():
        pair_counts = Counter(
            (
                _safe_int(r["buyer_person_id"], -1),
                _safe_int(r["seller_person_id"], -1),
            )
            for r in rows
        )

        for row in rows:
            pair = (
                _safe_int(row["buyer_person_id"], -1),
                _safe_int(row["seller_person_id"], -1),
            )

            if pair_counts[pair] >= 20:
                flagged[
                    _safe_int(row["transaction_id"])
                ].add("pair_repetition")

    # Rule 6 — broker concentration
    for day, rows in daily_rows.items():
        broker_values = Counter()
        total_value = sum(
            _safe_float(r["value"])
            for r in rows
        )

        if total_value <= 0:
            continue

        for row in rows:
            value = _safe_float(row["value"])

            broker_values[
                _safe_int(row["buyer_broker_id"], -1)
            ] += value

            broker_values[
                _safe_int(row["seller_broker_id"], -1)
            ] += value

        concentrated_brokers = {
            broker
            for broker, value in broker_values.items()
            if broker >= 0
            and value / total_value >= 0.35
        }

        for row in rows:
            buyer_broker = _safe_int(
                row["buyer_broker_id"], -1
            )
            seller_broker = _safe_int(
                row["seller_broker_id"], -1
            )

            tid = _safe_int(row["transaction_id"])

            if (
                buyer_broker in concentrated_brokers
                or seller_broker in concentrated_brokers
            ):
                flagged[tid].add(
                    "broker_concentration"
                )

    # Convert transaction-level flags to person-level counts.
    result: dict[int, dict[str, Any]] = {}

    transaction_lookup = {
        _safe_int(row["transaction_id"]): row
        for row in transactions
    }

    for tid, alert_types in flagged.items():
        row = transaction_lookup.get(tid)
        if row is None:
            continue

        persons = {
            _safe_int(row["buyer_person_id"], -1),
            _safe_int(row["seller_person_id"], -1),
        }

        persons.discard(-1)

        for person_id in persons:
            item = result.setdefault(
                person_id,
                {
                    "anomaly_flagged_transactions": 0,
                    "anomaly_alert_count": 0,
                    "anomaly_type_count": 0,
                    "anomaly_types": set(),
                },
            )

            item["anomaly_flagged_transactions"] += 1
            item["anomaly_alert_count"] += len(alert_types)
            item["anomaly_types"].update(alert_types)

    for item in result.values():
        item["anomaly_type_count"] = len(
            item["anomaly_types"]
        )
        item["anomaly_types"] = sorted(
            item["anomaly_types"]
        )

    return result


# ---------------------------------------------------------------------------
# Correlation
# ---------------------------------------------------------------------------

def _build_correlations(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    pairs = [
        ("transaction_count", "round_trip_count"),
        ("transaction_count", "anomaly_alert_count"),
        ("active_days", "round_trip_count"),
        ("active_days", "anomaly_alert_count"),
        ("total_value", "round_trip_count"),
        ("total_value", "anomaly_alert_count"),
        ("max_daily_value_share", "anomaly_alert_count"),
        ("buy_value_share", "round_trip_count"),
        ("fast_0_3_day_share", "anomaly_alert_count"),
        ("same_day_share", "anomaly_alert_count"),
    ]

    return [
        _correlation(rows, x, y)
        for x, y in pairs
    ]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_behavior_result(
    result: dict[str, Any],
) -> dict[str, Any]:
    rows = result.get("rows", [])
    correlations = result.get("correlations", [])

    checks = {
        "ready": bool(result.get("ready")),
        "persons_positive": result.get(
            "persons_used", 0
        ) > 0,
        "rows_count_matches": (
            result.get("persons_used", 0)
            == len(rows)
        ),
        "correlations_present": len(correlations) > 0,
        "correlations_finite": all(
            math.isfinite(
                _safe_float(c.get("pearson"))
            )
            and math.isfinite(
                _safe_float(c.get("spearman"))
            )
            for c in correlations
        ),
    }

    return {
        "valid": all(checks.values()),
        "checks": checks,
    }


# ---------------------------------------------------------------------------
# Main Engine
# ---------------------------------------------------------------------------

def run_behavior_correlation(
    conn: sqlite3.Connection,
) -> dict[str, Any]:
    """
    Execute Phase 7.

    Read-only behavioral correlation analysis.
    """

    conn.row_factory = sqlite3.Row

    behavior_rows = _load_person_behavior(conn)

    if not behavior_rows:
        return {
            "ready": False,
            "reason": "هیچ داده معاملاتی برای تحلیل وجود ندارد.",
            "persons_used": 0,
            "rows": [],
            "correlations": [],
        }

    round_trip = _load_round_trip_metrics(conn)
    anomaly = _load_anomaly_metrics(conn)

    rows: list[dict[str, Any]] = []

    for row in behavior_rows:
        person_id = row["person_id"]

        rt = round_trip.get(
            person_id,
            {
                "round_trip_count": 0,
                "same_day_count": 0,
                "fast_0_3_day_count": 0,
                "avg_holding_days": 0.0,
                "fast_0_3_day_share": 0.0,
                "same_day_share": 0.0,
            },
        )

        an = anomaly.get(
            person_id,
            {
                "anomaly_flagged_transactions": 0,
                "anomaly_alert_count": 0,
                "anomaly_type_count": 0,
                "anomaly_types": [],
            },
        )

        merged = dict(row)
        merged.update(rt)
        merged.update(an)

        rows.append(merged)

    correlations = _build_correlations(rows)

    summary = {
        "persons": len(rows),
        "persons_with_round_trips": sum(
            1
            for row in rows
            if row["round_trip_count"] > 0
        ),
        "persons_with_anomaly_alerts": sum(
            1
            for row in rows
            if row["anomaly_alert_count"] > 0
        ),
        "total_round_trips": sum(
            row["round_trip_count"]
            for row in rows
        ),
        "total_anomaly_alerts": sum(
            row["anomaly_alert_count"]
            for row in rows
        ),
    }

    result = {
        "ready": True,
        "methodology": {
            "type": "person_level_behavior_correlation",
            "read_only": True,
            "description": (
                "محاسبه شاخص‌های رفتاری در سطح شخص و "
                "اندازه‌گیری روابط آماری بین فعالیت، "
                "معاملات کوتاه‌مدت، تمرکز و هشدارهای آماری."
            ),
            "correlation_methods": [
                "pearson",
                "spearman",
            ],
            "interpretation_note": (
                "همبستگی آماری به‌تنهایی به معنی رابطه علّی، "
                "دستکاری بازار، تخلف، قصد معاملاتی یا تغییر مالکیت نیست."
            ),
        },
        "persons_used": len(rows),
        "rows": rows,
        "summary": summary,
        "correlations": correlations,
    }

    result["validation"] = validate_behavior_result(
        result
    )

    return result


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------

def audit_behavior_correlation(
    db_path: str | Path,
) -> dict[str, Any]:
    path = Path(db_path)

    if not path.exists():
        return {
            "ready": False,
            "reason": f"Database not found: {path}",
        }

    conn = sqlite3.connect(str(path))

    try:
        return run_behavior_correlation(conn)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    db_path = Path("data") / "smart_equity.db"

    result = audit_behavior_correlation(db_path)

    printable = {
        "ready": result.get("ready"),
        "persons_used": result.get("persons_used"),
        "summary": result.get("summary"),
        "correlations": result.get("correlations"),
        "validation": result.get("validation"),
    }

    print(printable)


if __name__ == "__main__":
    main()
