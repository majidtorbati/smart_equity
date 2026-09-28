"""تشخیص سهامداران جدید واقعی بر اساس سابقه رجیستری و معاملات."""

from __future__ import annotations

import sqlite3


def find_new_shareholders(conn: sqlite3.Connection, trade_date: str) -> list[dict]:
    """
    سهامداران جدید واقعی در یک روز مشخص را پیدا می‌کند.

    شرط سهامدار جدید:
    1) در روز انتخابی خرید داشته باشد.
    2) قبل از آن روز هیچ خریدی نداشته باشد.
    3) قبل از آن روز هیچ فروشی نداشته باشد.
    4) در رجیستری سابقه‌ای نداشته باشد.

    بنابراین خرید مجدد پس از فروش کامل نیز «سهامدار جدید» محسوب نمی‌شود.
    """

    if not trade_date:
        return []

    rows = conn.execute(
        """
        WITH daily_buys AS (
            SELECT
                t.buyer_person_id AS person_id,
                SUM(t.quantity) AS buy_quantity,
                SUM(t.value) AS buy_value,
                MIN(t.price) AS min_buy_price,
                MAX(t.price) AS max_buy_price
            FROM transactions t
            WHERE t.trade_date_gregorian = ?
              AND t.buyer_person_id IS NOT NULL
              AND t.quantity > 0
              AND t.value > 0
              AND t.is_duplicate_of IS NULL
            GROUP BY t.buyer_person_id
        )
        SELECT
            p.person_id,
            p.first_name,
            p.family_name,
            p.person_type,
            p.sejam_code,
            p.national_id,
            d.buy_quantity,
            d.buy_value,
            d.min_buy_price,
            d.max_buy_price
        FROM daily_buys d
        JOIN persons p
          ON p.person_id = d.person_id

        LEFT JOIN identity_matches im
          ON im.transaction_person_id = p.person_id

        LEFT JOIN registry_holdings rh
          ON rh.registry_holding_id = im.registry_holding_id
         AND rh.is_total_row = 0

        WHERE rh.registry_holding_id IS NULL

          AND NOT EXISTS (
              SELECT 1
              FROM transactions t_prev
              WHERE (t_prev.buyer_person_id = p.person_id
                     OR t_prev.seller_person_id = p.person_id)
                AND t_prev.trade_date_gregorian < ?
                AND t_prev.is_duplicate_of IS NULL
          )

        ORDER BY d.buy_value DESC, p.family_name COLLATE NOCASE, p.first_name COLLATE NOCASE
        """,
        (trade_date, trade_date),
    ).fetchall()

    return [
        {
            "person_id": r[0],
            "name": " ".join(
                part for part in (r[1], r[2])
                if part and str(part).strip()
            ) or "—",
            "person_type": r[3] or "—",
            "sejam_code": r[4] or "—",
            "national_id": r[5] or "—",
            "buy_quantity": int(r[6] or 0),
            "buy_value": float(r[7] or 0),
            "min_buy_price": float(r[8] or 0),
            "max_buy_price": float(r[9] or 0),
            "trade_date": trade_date,
        }
        for r in rows
    ]
