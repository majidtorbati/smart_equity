"""
Smart Equity Transaction Intelligence
Accumulation / Distribution Pattern Engine — Phase 4

Methodology:
- Each source transaction is counted exactly once.
- Market-wide buy value and sell value are NOT used as directional pressure,
  because matched transactions make them mathematically equal.
- Direction is inferred from player-level asymmetry:
    * net buyer count vs net seller count
    * concentration of net buyers / sellers
    * price behavior
    * trading-value intensity
- Results are an observational pattern score, not proof of ownership change,
  manipulation, intent, or capital inflow/outflow.
"""

from __future__ import annotations

import json
import sqlite3
import statistics
import sys
from pathlib import Path
from typing import Any


EPSILON = 1e-12
ROLLING_WINDOW = 20


def _safe_ratio(numerator: float, denominator: float) -> float:
    if abs(denominator) <= EPSILON:
        return 0.0
    return numerator / denominator


def _clamp(
    value: float,
    minimum: float = 0.0,
    maximum: float = 1.0,
) -> float:
    return max(minimum, min(maximum, value))


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(statistics.median(values))


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
        ORDER BY trade_date_gregorian, transaction_id
        """
    ).fetchall()

    return [
        {
            "id": row[0],
            "trade_date": row[1],
            "trade_date_jalali": row[2],
            "symbol_id": row[3],
            "buyer_person_id": row[4],
            "seller_person_id": row[5],
            "quantity": float(row[6] or 0),
            "price": float(row[7] or 0),
            "value": float(row[8] or 0),
        }
        for row in rows
    ]


def _build_player_daily(
    transactions: list[dict[str, Any]],
) -> dict[tuple[str, int], dict[int, dict[str, float]]]:
    """
    Build player-level daily activity.

    A player may be both buyer and seller on the same day.
    Net value:
        positive -> net buyer
        negative -> net seller
    """

    result: dict[
        tuple[str, int],
        dict[int, dict[str, float]],
    ] = {}

    for tx in transactions:
        key = (
            tx["trade_date"],
            tx["symbol_id"],
        )

        day_players = result.setdefault(key, {})

        buyer_id = tx["buyer_person_id"]
        seller_id = tx["seller_person_id"]

        buyer = day_players.setdefault(
            buyer_id,
            {
                "buy_value": 0.0,
                "sell_value": 0.0,
                "buy_quantity": 0.0,
                "sell_quantity": 0.0,
            },
        )

        seller = day_players.setdefault(
            seller_id,
            {
                "buy_value": 0.0,
                "sell_value": 0.0,
                "buy_quantity": 0.0,
                "sell_quantity": 0.0,
            },
        )

        buyer["buy_value"] += tx["value"]
        buyer["buy_quantity"] += tx["quantity"]

        seller["sell_value"] += tx["value"]
        seller["sell_quantity"] += tx["quantity"]

    return result


def _build_daily_market(
    transactions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, int], dict[str, Any]] = {}

    for tx in transactions:
        key = (
            tx["trade_date"],
            tx["symbol_id"],
        )

        row = grouped.setdefault(
            key,
            {
                "trade_date": tx["trade_date"],
                "trade_date_jalali": tx["trade_date_jalali"],
                "symbol_id": tx["symbol_id"],
                "transaction_count": 0,
                "quantity": 0.0,
                "value": 0.0,
                "prices": [],
            },
        )

        row["transaction_count"] += 1
        row["quantity"] += tx["quantity"]
        row["value"] += tx["value"]

        if tx["price"] > 0:
            row["prices"].append(tx["price"])

    rows = sorted(
        grouped.values(),
        key=lambda x: (
            x["trade_date"],
            x["symbol_id"],
        ),
    )

    for row in rows:
        row["vwap"] = _safe_ratio(
            row["value"],
            row["quantity"],
        )

        row["min_price"] = (
            min(row["prices"])
            if row["prices"]
            else 0.0
        )

        row["max_price"] = (
            max(row["prices"])
            if row["prices"]
            else 0.0
        )

        row.pop("prices", None)

    return rows


def _calculate_player_asymmetry(
    player_daily: dict[
        tuple[str, int],
        dict[int, dict[str, float]],
    ],
) -> dict[tuple[str, int], dict[str, Any]]:
    result: dict[tuple[str, int], dict[str, Any]] = {}

    for key, players in player_daily.items():
        net_buyers = []
        net_sellers = []
        active_players = 0

        for person_id, values in players.items():
            buy_value = values["buy_value"]
            sell_value = values["sell_value"]

            net_value = buy_value - sell_value
            total_activity = buy_value + sell_value

            if total_activity <= EPSILON:
                continue

            active_players += 1

            values["net_value"] = net_value
            values["activity_value"] = total_activity
            values["net_ratio"] = _safe_ratio(
                net_value,
                total_activity,
            )

            if net_value > EPSILON:
                net_buyers.append(
                    (
                        person_id,
                        net_value,
                        total_activity,
                    )
                )

            elif net_value < -EPSILON:
                net_sellers.append(
                    (
                        person_id,
                        abs(net_value),
                        total_activity,
                    )
                )

        buyer_count = len(net_buyers)
        seller_count = len(net_sellers)

        directional_count = (
            buyer_count + seller_count
        )

        buyer_count_share = _safe_ratio(
            buyer_count,
            directional_count,
        )

        seller_count_share = _safe_ratio(
            seller_count,
            directional_count,
        )

        # Positive => more net buyers
        # Negative => more net sellers
        count_asymmetry = (
            buyer_count_share
            - seller_count_share
        )

        positive_values = [
            item[1]
            for item in net_buyers
        ]

        negative_values = [
            item[1]
            for item in net_sellers
        ]

        gross_positive = sum(positive_values)
        gross_negative = sum(negative_values)

        buyer_concentration = 0.0
        seller_concentration = 0.0

        if gross_positive > EPSILON:
            top5 = sorted(
                positive_values,
                reverse=True,
            )[:5]

            buyer_concentration = _safe_ratio(
                sum(top5),
                gross_positive,
            )

        if gross_negative > EPSILON:
            top5 = sorted(
                negative_values,
                reverse=True,
            )[:5]

            seller_concentration = _safe_ratio(
                sum(top5),
                gross_negative,
            )

        net_ratios = [
            float(values["net_ratio"])
            for values in players.values()
            if values.get(
                "activity_value",
                0.0,
            ) > EPSILON
        ]

        median_net_ratio = _median(
            net_ratios
        )

        result[key] = {
            "net_buyer_count": buyer_count,
            "net_seller_count": seller_count,
            "active_player_count": active_players,
            "buyer_count_share": buyer_count_share,
            "seller_count_share": seller_count_share,
            "count_asymmetry": count_asymmetry,
            "top5_buyer_concentration": buyer_concentration,
            "top5_seller_concentration": seller_concentration,
            "median_player_net_ratio": median_net_ratio,
            "gross_net_buying": gross_positive,
            "gross_net_selling": gross_negative,
        }

    return result


def _add_historical_intensity(
    rows: list[dict[str, Any]],
) -> None:
    history: dict[int, list[float]] = {}

    for row in rows:
        symbol_id = row["symbol_id"]

        values = history.setdefault(
            symbol_id,
            [],
        )

        if values:
            mean_value = (
                sum(values) / len(values)
            )

            median_value = _median(values)

            row["value_vs_mean"] = _safe_ratio(
                row["value"],
                mean_value,
            )

            row["value_vs_median"] = _safe_ratio(
                row["value"],
                median_value,
            )

        else:
            row["value_vs_mean"] = 1.0
            row["value_vs_median"] = 1.0

        values.append(row["value"])

        if len(values) > ROLLING_WINDOW:
            del values[0]


def _add_price_changes(
    rows: list[dict[str, Any]],
) -> None:
    previous_vwap: dict[int, float] = {}

    for row in rows:
        symbol_id = row["symbol_id"]

        current = row["vwap"]
        previous = previous_vwap.get(
            symbol_id
        )

        if (
            previous is None
            or previous <= EPSILON
        ):
            row["price_change"] = 0.0

        else:
            row["price_change"] = _safe_ratio(
                current - previous,
                previous,
            )

        previous_vwap[symbol_id] = current


def _calculate_scores(
    rows: list[dict[str, Any]],
    player_asymmetry: dict[
        tuple[str, int],
        dict[str, Any],
    ],
) -> None:

    for row in rows:
        key = (
            row["trade_date"],
            row["symbol_id"],
        )

        stats = player_asymmetry.get(
            key,
            {},
        )

        count_asymmetry = float(
            stats.get(
                "count_asymmetry",
                0.0,
            )
        )

        buyer_count_share = float(
            stats.get(
                "buyer_count_share",
                0.5,
            )
        )

        seller_count_share = float(
            stats.get(
                "seller_count_share",
                0.5,
            )
        )

        buyer_concentration = float(
            stats.get(
                "top5_buyer_concentration",
                0.0,
            )
        )

        seller_concentration = float(
            stats.get(
                "top5_seller_concentration",
                0.0,
            )
        )

        price_change = float(
            row.get(
                "price_change",
                0.0,
            )
        )

        value_intensity = float(
            row.get(
                "value_vs_median",
                1.0,
            )
        )

        # Price direction:
        # +/- 0.5% is treated as flat.
        if price_change > 0.005:
            price_direction = "up"

        elif price_change < -0.005:
            price_direction = "down"

        else:
            price_direction = "flat"

        row["price_direction"] = (
            price_direction
        )

        price_component = _clamp(
            abs(price_change) / 0.05,
            0.0,
            1.0,
        )

        normalized_price = _clamp(
            price_change / 0.05,
            -1.0,
            1.0,
        )

        intensity_component = _clamp(
            (value_intensity - 0.75) / 1.25,
            0.0,
            1.0,
        )

        positive_count = _clamp(
            max(count_asymmetry, 0.0),
            0.0,
            1.0,
        )

        negative_count = _clamp(
            max(-count_asymmetry, 0.0),
            0.0,
            1.0,
        )

        accumulation_support = (
            positive_count * 0.50
            + buyer_concentration * 0.15
            + max(normalized_price, 0.0) * 0.20
            + intensity_component * 0.15
        )

        distribution_support = (
            negative_count * 0.50
            + seller_concentration * 0.15
            + max(-normalized_price, 0.0) * 0.20
            + intensity_component * 0.15
        )

        if (
            count_asymmetry > 0
            and price_change < 0
        ):
            accumulation_support *= 0.65

        if (
            count_asymmetry < 0
            and price_change > 0
        ):
            distribution_support *= 0.65

        row["buyer_count_share"] = (
            buyer_count_share
        )

        row["seller_count_share"] = (
            seller_count_share
        )

        row["count_asymmetry"] = (
            count_asymmetry
        )

        row["top5_buyer_concentration"] = (
            buyer_concentration
        )

        row["top5_seller_concentration"] = (
            seller_concentration
        )

        row["price_component"] = (
            price_component
        )

        row["value_intensity_component"] = (
            intensity_component
        )

        row["accumulation_score"] = round(
            _clamp(
                accumulation_support
            ) * 100.0,
            2,
        )

        row["distribution_score"] = round(
            _clamp(
                distribution_support
            ) * 100.0,
            2,
        )

        row["net_buyer_count"] = int(
            stats.get(
                "net_buyer_count",
                0,
            )
        )

        row["net_seller_count"] = int(
            stats.get(
                "net_seller_count",
                0,
            )
        )

        row["active_player_count"] = int(
            stats.get(
                "active_player_count",
                0,
            )
        )

        row["gross_net_buying"] = float(
            stats.get(
                "gross_net_buying",
                0.0,
            )
        )

        row["gross_net_selling"] = float(
            stats.get(
                "gross_net_selling",
                0.0,
            )
        )

        # Final pattern classification.
        if (
            row["accumulation_score"] >= 50
            and row["accumulation_score"]
            > row["distribution_score"]
        ):
            pattern = "accumulation"

        elif (
            row["distribution_score"] >= 50
            and row["distribution_score"]
            > row["accumulation_score"]
        ):
            pattern = "distribution"

        else:
            pattern = "neutral"

        row["pattern"] = pattern

        row["pattern_price_context"] = (
            f"{pattern}_{price_direction}"
        )


def _add_persistence(
    rows: list[dict[str, Any]],
) -> None:
    previous_symbol: int | None = None

    accumulation_streak = 0
    distribution_streak = 0

    for row in rows:
        symbol_id = row["symbol_id"]

        if symbol_id != previous_symbol:
            accumulation_streak = 0
            distribution_streak = 0

        accumulation_score = row[
            "accumulation_score"
        ]

        distribution_score = row[
            "distribution_score"
        ]

        if (
            accumulation_score >= 50
            and accumulation_score
            > distribution_score
        ):
            accumulation_streak += 1
        else:
            accumulation_streak = 0

        if (
            distribution_score >= 50
            and distribution_score
            > accumulation_score
        ):
            distribution_streak += 1
        else:
            distribution_streak = 0

        row["accumulation_streak"] = (
            accumulation_streak
        )

        row["distribution_streak"] = (
            distribution_streak
        )

        previous_symbol = symbol_id


def run_accumulation_distribution(
    conn: sqlite3.Connection,
) -> dict[str, Any]:

    transactions = _load_transactions(
        conn
    )

    if not transactions:
        return {
            "ready": False,
            "reason": (
                "هیچ معامله‌ای در پایگاه داده وجود ندارد."
            ),
        }

    player_daily = _build_player_daily(
        transactions
    )

    player_asymmetry = (
        _calculate_player_asymmetry(
            player_daily
        )
    )

    daily_rows = _build_daily_market(
        transactions
    )

    _add_historical_intensity(
        daily_rows
    )

    _add_price_changes(
        daily_rows
    )

    _calculate_scores(
        daily_rows,
        player_asymmetry,
    )

    _add_persistence(
        daily_rows
    )

    accumulation_days = sum(
        1
        for row in daily_rows
        if (
            row["accumulation_score"] >= 50
            and row["accumulation_score"]
            > row["distribution_score"]
        )
    )

    distribution_days = sum(
        1
        for row in daily_rows
        if (
            row["distribution_score"] >= 50
            and row["distribution_score"]
            > row["accumulation_score"]
        )
    )

    neutral_days = (
        len(daily_rows)
        - accumulation_days
        - distribution_days
    )

    average_accumulation = (
        sum(
            row["accumulation_score"]
            for row in daily_rows
        )
        / len(daily_rows)
    )

    average_distribution = (
        sum(
            row["distribution_score"]
            for row in daily_rows
        )
        / len(daily_rows)
    )

    max_accumulation_streak = max(
        (
            row["accumulation_streak"]
            for row in daily_rows
        ),
        default=0,
    )

    max_distribution_streak = max(
        (
            row["distribution_streak"]
            for row in daily_rows
        ),
        default=0,
    )

    strongest_accumulation = max(
        daily_rows,
        key=lambda row:
            row["accumulation_score"],
    )

    strongest_distribution = max(
        daily_rows,
        key=lambda row:
            row["distribution_score"],
    )

    # Correct Player-Day count:
    # one player participating on one date/symbol
    # equals one player-day.
    player_days_count = sum(
        len(players)
        for players in player_daily.values()
    )

    return {
        "ready": True,

        "methodology": {
            "type": "player_pattern_based",
            "description": (
                "الگوی انباشت/توزیع بر اساس "
                "عدم‌تقارن تعداد خریداران و "
                "فروشندگان خالص، تمرکز بازیکنان، "
                "رفتار قیمت و شدت ارزش معاملات "
                "محاسبه شده است."
            ),
            "not_proof_of": [
                "capital_inflow_or_outflow",
                "ownership_change",
                "market_manipulation",
                "player_intent",
            ],
        },

        "transactions_used": len(
            transactions
        ),

        "player_days": player_days_count,

        "days": len(daily_rows),

        "symbols": len(
            {
                row["symbol_id"]
                for row in daily_rows
            }
        ),

        "daily_rows": len(daily_rows),

        "first_trade_date": (
            daily_rows[0]["trade_date"]
        ),

        "last_trade_date": (
            daily_rows[-1]["trade_date"]
        ),

        "accumulation_days": (
            accumulation_days
        ),

        "distribution_days": (
            distribution_days
        ),

        "neutral_days": neutral_days,

        "average_accumulation_score": round(
            average_accumulation,
            2,
        ),

        "average_distribution_score": round(
            average_distribution,
            2,
        ),

        "max_accumulation_streak": (
            max_accumulation_streak
        ),

        "max_distribution_streak": (
            max_distribution_streak
        ),

        "strongest_accumulation": {
            "trade_date": (
                strongest_accumulation[
                    "trade_date"
                ]
            ),

            "trade_date_jalali": (
                strongest_accumulation[
                    "trade_date_jalali"
                ]
            ),

            "symbol_id": (
                strongest_accumulation[
                    "symbol_id"
                ]
            ),

            "score": (
                strongest_accumulation[
                    "accumulation_score"
                ]
            ),

            "price_change": (
                strongest_accumulation[
                    "price_change"
                ]
            ),

            "price_direction": (
                strongest_accumulation[
                    "price_direction"
                ]
            ),

            "pattern": (
                strongest_accumulation[
                    "pattern"
                ]
            ),

            "pattern_price_context": (
                strongest_accumulation[
                    "pattern_price_context"
                ]
            ),

            "value_vs_median": (
                strongest_accumulation[
                    "value_vs_median"
                ]
            ),

            "net_buyer_count": (
                strongest_accumulation[
                    "net_buyer_count"
                ]
            ),

            "net_seller_count": (
                strongest_accumulation[
                    "net_seller_count"
                ]
            ),

            "buyer_count_share": round(
                strongest_accumulation[
                    "buyer_count_share"
                ],
                4,
            ),

            "top5_buyer_concentration": round(
                strongest_accumulation[
                    "top5_buyer_concentration"
                ],
                4,
            ),
        },

        "strongest_distribution": {
            "trade_date": (
                strongest_distribution[
                    "trade_date"
                ]
            ),

            "trade_date_jalali": (
                strongest_distribution[
                    "trade_date_jalali"
                ]
            ),

            "symbol_id": (
                strongest_distribution[
                    "symbol_id"
                ]
            ),

            "score": (
                strongest_distribution[
                    "distribution_score"
                ]
            ),

            "price_change": (
                strongest_distribution[
                    "price_change"
                ]
            ),

            "price_direction": (
                strongest_distribution[
                    "price_direction"
                ]
            ),

            "pattern": (
                strongest_distribution[
                    "pattern"
                ]
            ),

            "pattern_price_context": (
                strongest_distribution[
                    "pattern_price_context"
                ]
            ),

            "value_vs_median": (
                strongest_distribution[
                    "value_vs_median"
                ]
            ),

            "net_buyer_count": (
                strongest_distribution[
                    "net_buyer_count"
                ]
            ),

            "net_seller_count": (
                strongest_distribution[
                    "net_seller_count"
                ]
            ),

            "seller_count_share": round(
                strongest_distribution[
                    "seller_count_share"
                ],
                4,
            ),

            "top5_seller_concentration": round(
                strongest_distribution[
                    "top5_seller_concentration"
                ],
                4,
            ),
        },
    }


def audit_accumulation_distribution(
    db_path: str | Path,
) -> dict[str, Any]:

    conn = sqlite3.connect(
        str(db_path)
    )

    try:
        return run_accumulation_distribution(
            conn
        )

    finally:
        conn.close()


def main() -> None:

    if len(sys.argv) < 2:
        print(
            "Usage: python -m "
            "app.analytics.accumulation_distribution "
            "<db_path>"
        )

        raise SystemExit(1)

    result = (
        audit_accumulation_distribution(
            sys.argv[1]
        )
    )

    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()