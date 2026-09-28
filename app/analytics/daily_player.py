"""
Smart Equity ? Daily Player Event Engine.

Calculates observed transaction positions and daily player events.
Registry information is attached only as historical evidence and
never changes the event classification.
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any


REGISTRY_SNAPSHOT_DATE = "1405/03/03"


def _position_status(position_before: int, position_after: int) -> str:
    if position_before < 0:
        return "INSUFFICIENT_HISTORY"

    if position_after < 0:
        return "DATA_CONFLICT"

    return "OBSERVABLE"


def _event_type(
    position_before: int,
    position_after: int,
    buy_quantity: int,
    sell_quantity: int,
    status: str,
) -> str | None:
    if status != "OBSERVABLE":
        return None

    if position_before == 0 and buy_quantity > 0:
        return "ENTRY_OBSERVED"

    if (
        position_before > 0
        and sell_quantity > 0
        and position_after == 0
    ):
        return "FULL_EXIT_OBSERVED"

    if (
        position_before > 0
        and position_after > 0
        and sell_quantity > 0
        and sell_quantity / position_before >= 0.50
    ):
        return "HEAVY_SELL_OBSERVED"

    return None


def _build_safe_registry_lookup(
    conn: sqlite3.Connection,
) -> dict[int, dict[str, Any]]:
    """
    Build a safe transaction_person_id -> Registry evidence lookup.

    Rules:
    - national_id is safe only when its Registry holding is unique.
    - code_tail/name are safe only when the Registry holding is unique.
    - Any Registry holding matched to multiple transaction persons is
      considered ambiguous and excluded completely.
    """
    rows = conn.execute(
        """
        WITH holding_persons AS (
            SELECT
                registry_holding_id,
                COUNT(DISTINCT transaction_person_id) AS person_count
            FROM identity_matches
            GROUP BY registry_holding_id
        )
        SELECT
            im.transaction_person_id,
            im.registry_holding_id,
            im.match_method,
            im.confidence,
            rh.opening_quantity,
            rh.registry_buy_quantity,
            rh.registry_sell_quantity,
            rh.closing_quantity,
            hp.person_count
        FROM identity_matches im
        JOIN holding_persons hp
          ON hp.registry_holding_id = im.registry_holding_id
        JOIN registry_holdings rh
          ON rh.registry_holding_id = im.registry_holding_id
        WHERE rh.is_total_row = 0
          AND hp.person_count = 1
        ORDER BY
            im.transaction_person_id,
            CASE im.match_method
                WHEN 'national_id' THEN 1
                WHEN 'code_tail' THEN 2
                WHEN 'name' THEN 3
                ELSE 4
            END
        """
    ).fetchall()

    lookup: dict[int, dict[str, Any]] = {}

    for row in rows:
        person_id = int(row["transaction_person_id"])

        # The query should already give one unique Registry holding per
        # transaction person, but keep this guard explicit.
        if person_id in lookup:
            continue

        opening = int(row["opening_quantity"] or 0)
        registry_buy = int(row["registry_buy_quantity"] or 0)
        registry_sell = int(row["registry_sell_quantity"] or 0)
        closing = int(row["closing_quantity"] or 0)

        if opening == 0 and registry_buy > 0:
            registry_status = "REGISTRY_NEW_ON_SNAPSHOT"
        else:
            registry_status = "REGISTRY_HISTORY_PRESENT"

        lookup[person_id] = {
            "registry_snapshot_date": REGISTRY_SNAPSHOT_DATE,
            "registry_status": registry_status,
            "registry_opening_quantity": opening,
            "registry_buy_quantity": registry_buy,
            "registry_sell_quantity": registry_sell,
            "registry_closing_quantity": closing,
            "registry_match_method": row["match_method"],
            "registry_match_confidence": row["confidence"],
        }

    return lookup


def _empty_registry_evidence() -> dict[str, Any]:
    return {
        "registry_snapshot_date": REGISTRY_SNAPSHOT_DATE,
        "registry_status": "NO_REGISTRY_MATCH",
        "registry_opening_quantity": None,
        "registry_buy_quantity": None,
        "registry_sell_quantity": None,
        "registry_closing_quantity": None,
        "registry_match_method": None,
        "registry_match_confidence": None,
    }


def run_daily_player_analysis(
    db_path: str | Path | sqlite3.Connection,
) -> dict[str, Any]:
    """
    Run the read-only daily player analysis.

    The transaction event logic is intentionally independent from Registry.
    Registry fields are historical evidence only.
    """
    owns_connection = False

    if isinstance(db_path, sqlite3.Connection):
        conn = db_path
        conn.row_factory = sqlite3.Row
    else:
        db_path = Path(db_path)
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        owns_connection = True

    try:
        transactions = conn.execute(
            """
            SELECT
                transaction_id,
                trade_date_jalali,
                trade_date_gregorian,
                symbol_id,
                buyer_person_id,
                seller_person_id,
                quantity,
                price,
                value
            FROM transactions
            WHERE quantity > 0
              AND price > 0
              AND value > 0
            ORDER BY
                trade_date_gregorian,
                transaction_id
            """
        ).fetchall()

        registry_lookup = _build_safe_registry_lookup(conn)

    finally:
        if owns_connection:
            conn.close()

    daily: dict[tuple[str, int, int], dict[str, Any]] = {}

    def get_daily(
        trade_date_jalali: str,
        trade_date_gregorian: str,
        symbol_id: int,
        person_id: int,
    ) -> dict[str, Any]:
        key = (trade_date_gregorian, symbol_id, person_id)

        if key not in daily:
            daily[key] = {
                "trade_date_jalali": trade_date_jalali,
                "trade_date_gregorian": trade_date_gregorian,
                "symbol_id": symbol_id,
                "person_id": person_id,
                "buy_quantity": 0,
                "sell_quantity": 0,
                "buy_value": 0,
                "sell_value": 0,
                "buy_value_price_weighted": 0,
                "sell_value_price_weighted": 0,
                "activity_count": 0,
            }

        return daily[key]

    for row in transactions:
        quantity = int(row["quantity"])
        price = int(row["price"])
        value = int(row["value"])

        trade_date_jalali = row["trade_date_jalali"]
        trade_date_gregorian = row["trade_date_gregorian"]
        symbol_id = int(row["symbol_id"])

        buyer_id = row["buyer_person_id"]
        seller_id = row["seller_person_id"]

        if buyer_id is not None:
            item = get_daily(
                trade_date_jalali,
                trade_date_gregorian,
                symbol_id,
                int(buyer_id),
            )
            item["buy_quantity"] += quantity
            item["buy_value"] += value
            item["buy_value_price_weighted"] += quantity * price
            item["activity_count"] += 1

        if seller_id is not None:
            item = get_daily(
                trade_date_jalali,
                trade_date_gregorian,
                symbol_id,
                int(seller_id),
            )
            item["sell_quantity"] += quantity
            item["sell_value"] += value
            item["sell_value_price_weighted"] += quantity * price
            item["activity_count"] += 1

    # Calculate observed transaction positions chronologically.
    position: dict[tuple[int, int], int] = {}

    rows = sorted(
        daily.values(),
        key=lambda x: (
            x["trade_date_gregorian"],
            x["symbol_id"],
            x["person_id"],
        ),
    )

    event_rows: list[dict[str, Any]] = []

    for item in rows:
        person_id = int(item["person_id"])
        symbol_id = int(item["symbol_id"])
        position_key = (person_id, symbol_id)

        position_before = position.get(position_key, 0)

        buy_quantity = int(item["buy_quantity"])
        sell_quantity = int(item["sell_quantity"])

        position_after = (
            position_before
            + buy_quantity
            - sell_quantity
        )

        status = _position_status(
            position_before,
            position_after,
        )

        event_type = _event_type(
            position_before,
            position_after,
            buy_quantity,
            sell_quantity,
            status,
        )

        if position_after >= 0:
            position[position_key] = position_after
        else:
            # Keep the negative calculated position so the next day's
            # status remains a data-quality signal.
            position[position_key] = position_after

        buy_value = int(item["buy_value"])
        sell_value = int(item["sell_value"])
        net_quantity = buy_quantity - sell_quantity
        net_value = buy_value - sell_value
        participation_value = buy_value + sell_value
        participation_quantity = buy_quantity + sell_quantity

        if buy_quantity:
            avg_buy_price = (
                item["buy_value_price_weighted"] / buy_quantity
            )
        else:
            avg_buy_price = None

        if sell_quantity:
            avg_sell_price = (
                item["sell_value_price_weighted"] / sell_quantity
            )
        else:
            avg_sell_price = None

        if sell_value:
            buy_sell_value_ratio = buy_value / sell_value
        else:
            buy_sell_value_ratio = None

        if position_before > 0 and sell_quantity > 0:
            sell_ratio = sell_quantity / position_before
        else:
            sell_ratio = None

        evidence = registry_lookup.get(
            person_id,
            _empty_registry_evidence(),
        )

        result = {
            "trade_date_jalali": item["trade_date_jalali"],
            "trade_date_gregorian": item["trade_date_gregorian"],
            "symbol_id": symbol_id,
            "person_id": person_id,
            "buy_quantity": buy_quantity,
            "sell_quantity": sell_quantity,
            "buy_value": buy_value,
            "sell_value": sell_value,
            "net_quantity": net_quantity,
            "net_value": net_value,
            "avg_buy_price": avg_buy_price,
            "avg_sell_price": avg_sell_price,
            "activity_count": int(item["activity_count"]),
            "buy_sell_value_ratio": buy_sell_value_ratio,
            "participation_value": participation_value,
            "participation_quantity": participation_quantity,
            "position_before": position_before,
            "position_after": position_after,
            "position_status": status,
            "event_type": event_type,
            "sell_ratio": sell_ratio,
            **evidence,
        }

        event_rows.append(result)

    observable_rows = sum(
        1
        for row in event_rows
        if row["position_status"] == "OBSERVABLE"
    )

    insufficient_history_rows = sum(
        1
        for row in event_rows
        if row["position_status"] == "INSUFFICIENT_HISTORY"
    )

    data_conflict_rows = sum(
        1
        for row in event_rows
        if row["position_status"] == "DATA_CONFLICT"
    )

    entry_observed_count = sum(
        1
        for row in event_rows
        if row["event_type"] == "ENTRY_OBSERVED"
    )

    full_exit_observed_count = sum(
        1
        for row in event_rows
        if row["event_type"] == "FULL_EXIT_OBSERVED"
    )

    heavy_sell_observed_count = sum(
        1
        for row in event_rows
        if row["event_type"] == "HEAVY_SELL_OBSERVED"
    )

    days = {
        row["trade_date_gregorian"]
        for row in event_rows
    }

    symbols = {
        row["symbol_id"]
        for row in event_rows
    }

    players = {
        row["person_id"]
        for row in event_rows
    }

    registry_evidence_rows = sum(
        1
        for row in event_rows
        if row["registry_status"] != "NO_REGISTRY_MATCH"
    )

    registry_new_on_snapshot_count = sum(
        1
        for row in event_rows
        if row["registry_status"] == "REGISTRY_NEW_ON_SNAPSHOT"
    )

    return {
        "ready": True,
        "transactions_used": len(transactions),
        "player_days": len(event_rows),
        "days": len(days),
        "symbols": len(symbols),
        "players": len(players),
        "observable_rows": observable_rows,
        "insufficient_history_rows": insufficient_history_rows,
        "data_conflict_rows": data_conflict_rows,
        "entry_observed_count": entry_observed_count,
        "full_exit_observed_count": full_exit_observed_count,
        "heavy_sell_observed_count": heavy_sell_observed_count,
        "event_rows": len(event_rows),
        "registry_evidence_rows": registry_evidence_rows,
        "registry_new_on_snapshot_count": registry_new_on_snapshot_count,
        "rows": event_rows,
    }


def audit_daily_player(
    db_path: str | Path,
) -> dict[str, Any]:
    """
    Run the analysis through SQLite's read-only URI mode.
    """
    db_path = Path(db_path).resolve()

    uri = f"file:{db_path.as_posix()}?mode=ro"

    conn = sqlite3.connect(uri, uri=True)
    conn.close()

    return run_daily_player_analysis(db_path)


def main() -> None:
    import json
    import sys

    db_path = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "data/smart_equity.db"
    )

    result = audit_daily_player(db_path)

    summary = {
        key: value
        for key, value in result.items()
        if key != "rows"
    }

    print(json.dumps(
        summary,
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()
