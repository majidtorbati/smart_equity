"""
Smart Equity — Phase 3: New / Exited Shareholders

Read-only engine for detecting first-observed and last-observed
transaction activity within the available transaction history.

Important:
Transaction activity is not treated as definitive ownership.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


def run_new_exited_shareholders(
    conn: sqlite3.Connection,
) -> dict[str, Any]:
    """Analyze first and last observed transaction activity per person."""
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """
        SELECT
            t.trade_date_gregorian AS trade_date,
            t.trade_date_jalali AS trade_date_jalali,
            t.symbol_id,
            t.buyer_person_id,
            t.seller_person_id,
            t.quantity,
            t.price,
            t.value,
            pb.person_type AS buyer_person_type,
            ps.person_type AS seller_person_type
        FROM transactions t
        LEFT JOIN persons pb
            ON pb.person_id = t.buyer_person_id
        LEFT JOIN persons ps
            ON ps.person_id = t.seller_person_id
        WHERE t.quantity > 0
          AND t.price > 0
          AND t.value > 0
        ORDER BY t.trade_date_gregorian, t.source_row_index
        """
    ).fetchall()

    if not rows:
        return {
            "ready": False,
            "transactions_used": 0,
            "players": 0,
            "new_shareholders": [],
            "exited_shareholders": [],
        }

    first_date = rows[0]["trade_date"]
    last_date = rows[-1]["trade_date"]

    # Registry identity / opening-position information.
    #
    # A person can have more than one Registry holding row, so opening
    # quantity and Registry movements are aggregated per person.
    registry_rows = conn.execute(
        """
        SELECT
            im.transaction_person_id AS person_id,
            SUM(COALESCE(r.opening_quantity, 0)) AS registry_opening_quantity,
            SUM(COALESCE(r.registry_buy_quantity, 0)) AS registry_buy_quantity,
            SUM(COALESCE(r.registry_sell_quantity, 0)) AS registry_sell_quantity,
            SUM(COALESCE(r.closing_quantity, 0)) AS registry_closing_quantity,
            COUNT(*) AS registry_match_count,
            MIN(im.match_method) AS registry_match_method,
            MIN(im.confidence) AS registry_match_confidence
        FROM identity_matches im
        JOIN registry_holdings r
          ON r.registry_holding_id = im.registry_holding_id
        WHERE r.is_total_row = 0
        GROUP BY im.transaction_person_id
        """
    ).fetchall()

    registry_by_person = {
        int(row["person_id"]): {
            "registry_opening_quantity": int(
                row["registry_opening_quantity"] or 0
            ),
            "registry_buy_quantity": int(
                row["registry_buy_quantity"] or 0
            ),
            "registry_sell_quantity": int(
                row["registry_sell_quantity"] or 0
            ),
            "registry_closing_quantity": int(
                row["registry_closing_quantity"] or 0
            ),
            "registry_match_count": int(
                row["registry_match_count"] or 0
            ),
            "registry_match_method": row["registry_match_method"],
            "registry_match_confidence": row["registry_match_confidence"],
        }
        for row in registry_rows
    }

    players: dict[int, dict[str, Any]] = {}

    def get_player(
        person_id: int,
        person_type: str | None,
    ) -> dict[str, Any]:
        if person_id not in players:
            players[person_id] = {
                "person_id": person_id,
                "person_type": person_type,
                "first_seen_date": None,
                "first_seen_date_jalali": None,
                "last_seen_date": None,
                "last_seen_date_jalali": None,
                "buy_count": 0,
                "sell_count": 0,
                "buy_quantity": 0,
                "sell_quantity": 0,
                "buy_value": 0,
                "sell_value": 0,
                "first_buy_date": None,
                "first_buy_date_jalali": None,
                "first_buy_quantity": 0,
                "first_buy_price": None,
                "first_sell_date": None,
                "first_sell_date_jalali": None,
                "first_sell_quantity": 0,
                "first_sell_price": None,

                # Registry reconciliation fields.
                "registry_matched": False,
                "registry_opening_quantity": None,
                "registry_buy_quantity": None,
                "registry_sell_quantity": None,
                "registry_closing_quantity": None,
                "registry_match_count": 0,
                "registry_match_method": None,
                "registry_match_confidence": None,
                "newcomer_class": None,
            }
        return players[person_id]

    for row in rows:
        trade_date = row["trade_date"]
        trade_date_jalali = row["trade_date_jalali"]

        # Buyer activity
        buyer_id = row["buyer_person_id"]
        if buyer_id is not None:
            p = get_player(buyer_id, row["buyer_person_type"])

            if p["first_seen_date"] is None:
                p["first_seen_date"] = trade_date
                p["first_seen_date_jalali"] = trade_date_jalali

            p["last_seen_date"] = trade_date
            p["last_seen_date_jalali"] = trade_date_jalali

            p["buy_count"] += 1
            p["buy_quantity"] += row["quantity"]
            p["buy_value"] += row["value"]

            if p["first_buy_date"] is None:
                p["first_buy_date"] = trade_date
                p["first_buy_date_jalali"] = trade_date_jalali
                p["first_buy_quantity"] = row["quantity"]
                p["first_buy_price"] = row["price"]

        # Seller activity
        seller_id = row["seller_person_id"]
        if seller_id is not None:
            p = get_player(seller_id, row["seller_person_type"])

            if p["first_seen_date"] is None:
                p["first_seen_date"] = trade_date
                p["first_seen_date_jalali"] = trade_date_jalali

            p["last_seen_date"] = trade_date
            p["last_seen_date_jalali"] = trade_date_jalali

            p["sell_count"] += 1
            p["sell_quantity"] += row["quantity"]
            p["sell_value"] += row["value"]

            if p["first_sell_date"] is None:
                p["first_sell_date"] = trade_date
                p["first_sell_date_jalali"] = trade_date_jalali
                p["first_sell_quantity"] = row["quantity"]
                p["first_sell_price"] = row["price"]

    new_shareholders = []
    exited_shareholders = []

    for p in players.values():
        p["avg_buy_price"] = (
            p["buy_value"] / p["buy_quantity"]
            if p["buy_quantity"]
            else None
        )

        p["avg_sell_price"] = (
            p["sell_value"] / p["sell_quantity"]
            if p["sell_quantity"]
            else None
        )

        p["net_quantity"] = p["buy_quantity"] - p["sell_quantity"]
        p["net_value"] = p["buy_value"] - p["sell_value"]

        # ------------------------------------------------------------
        # New shareholder definition
        # ------------------------------------------------------------
        #
        # The previous implementation used:
        #
        #   first_seen_date == first_date
        #
        # That only identifies people first observed on the first
        # transaction day. It is NOT a reliable definition of a
        # newcomer.
        #
        # New definition:
        #
        # 1) No valid Registry identity match + at least one buy
        #    -> UNMATCHED_REGISTRY
        #
        # 2) Valid Registry match + zero opening quantity + at least
        #    one buy
        #    -> REGISTRY_NEW
        #
        # Net quantity is deliberately NOT used as a requirement.
        # A newcomer may buy and later sell all of those shares.
        registry = registry_by_person.get(p["person_id"])

        if registry is None:
            p["registry_matched"] = False
            p["registry_opening_quantity"] = None
            p["registry_buy_quantity"] = None
            p["registry_sell_quantity"] = None
            p["registry_closing_quantity"] = None
            p["registry_match_count"] = 0
            p["registry_match_method"] = None
            p["registry_match_confidence"] = None

            p["is_new"] = p["buy_quantity"] > 0

            if p["is_new"]:
                p["newcomer_class"] = "UNMATCHED_REGISTRY"

        else:
            p["registry_matched"] = True
            p["registry_opening_quantity"] = registry[
                "registry_opening_quantity"
            ]
            p["registry_buy_quantity"] = registry[
                "registry_buy_quantity"
            ]
            p["registry_sell_quantity"] = registry[
                "registry_sell_quantity"
            ]
            p["registry_closing_quantity"] = registry[
                "registry_closing_quantity"
            ]
            p["registry_match_count"] = registry[
                "registry_match_count"
            ]
            p["registry_match_method"] = registry[
                "registry_match_method"
            ]
            p["registry_match_confidence"] = registry[
                "registry_match_confidence"
            ]

            p["is_new"] = (
                p["buy_quantity"] > 0
                and p["registry_opening_quantity"] == 0
            )

            if p["is_new"]:
                p["newcomer_class"] = "REGISTRY_NEW"

        # Exited = last observed activity occurs on the final
        # transaction date of the available dataset.
        #
        # This definition is intentionally left unchanged for the
        # separate Exit Audit stage.
        p["is_exited"] = p["last_seen_date"] == last_date

        if p["is_new"]:
            new_shareholders.append(dict(p))

        if p["is_exited"]:
            exited_shareholders.append(dict(p))

    new_shareholders.sort(
        key=lambda x: (x["first_seen_date"], x["person_id"])
    )
    exited_shareholders.sort(
        key=lambda x: (x["last_seen_date"], x["person_id"])
    )

    return {
        "ready": True,
        "transactions_used": len(rows),
        "players": len(players),
        "first_transaction_date": first_date,
        "first_transaction_date_jalali": rows[0]["trade_date_jalali"],
        "last_transaction_date": last_date,
        "last_transaction_date_jalali": rows[-1]["trade_date_jalali"],
        "new_shareholders_count": len(new_shareholders),
        "exited_shareholders_count": len(exited_shareholders),
        "new_shareholders": new_shareholders,
        "exited_shareholders": exited_shareholders,
    }


def audit_new_exited_shareholders(
    db_path: str | Path,
) -> dict[str, Any]:
    """Run Phase 3 against SQLite in read-only mode."""
    db_path = Path(db_path).resolve()

    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    uri = f"file:{db_path.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)

    try:
        return run_new_exited_shareholders(conn)
    finally:
        conn.close()


def main() -> int:
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description="Smart Equity Phase 3 — New / Exited Shareholders"
    )
    parser.add_argument(
        "db_path",
        nargs="?",
        default="data/smart_equity.db",
    )

    args = parser.parse_args()

    result = audit_new_exited_shareholders(args.db_path)

    print(
        json.dumps(
            {
                "ready": result["ready"],
                "transactions_used": result["transactions_used"],
                "players": result["players"],
                "first_transaction_date": result.get(
                    "first_transaction_date"
                ),
                "first_transaction_date_jalali": result.get(
                    "first_transaction_date_jalali"
                ),
                "last_transaction_date": result.get(
                    "last_transaction_date"
                ),
                "last_transaction_date_jalali": result.get(
                    "last_transaction_date_jalali"
                ),
                "new_shareholders_count": result.get(
                    "new_shareholders_count", 0
                ),
                "exited_shareholders_count": result.get(
                    "exited_shareholders_count", 0
                ),
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
