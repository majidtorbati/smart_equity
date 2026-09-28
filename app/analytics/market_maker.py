"""
Market Maker Behavior Analysis (رفتار بازارگردان)
سؤال اصلی: آیا فعالیت بازارگردان با افزایش قیمت (تغذیه رشد) هم‌زمان بوده،
یا با کاهش قیمت (ایجاد حمایت) / افزایش قیمت (ایجاد مقاومت با فروش) هم‌زمانی داشته؟

اصل مهم: این ماژول هرگز رابطه علّی ادعا نمی‌کند (Correlation ≠ Causation).
فقط «هم‌زمانی مشاهده‌شده» را با آمار واقعی گزارش می‌کند.
"""
from __future__ import annotations
import sqlite3
import sys
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from app.analytics.metrics import _date_filter, price_series
from app.core.jalali import jalali_date_display
from app.core.normalize import normalize_key
from app.config.settings import get_primary_market_maker_names


def get_market_maker_broker_ids(conn: sqlite3.Connection) -> list[dict]:
    """
    بازارگردان(های) «اصلی» و رسمی این نماد را برمی‌گرداند — بر اساس فهرست صریح در تنظیمات
    (app/config/settings.py)، نه صرفاً پرچم خودکار is_market_maker در دیتابیس.
    دلیل: پرچم خودکار فقط بر مبنای وجود کلمه «بازارگردان» در نام کارگزار تشخیص داده می‌شود و
    ممکن است شامل صندوق‌های بازارگردانی عمومی هم بشود که بازارگردان رسمی این شرکت خاص نیستند؛
    آن‌ها برای این تحلیل باید مثل بقیه خریداران/فروشندگان معمولی در نظر گرفته شوند.
    """
    configured_names = get_primary_market_maker_names()
    configured_keys = {normalize_key(n) for n in configured_names}
    if not configured_keys:
        return []
    rows = conn.execute("SELECT broker_id, broker_name_raw, broker_name_key FROM brokers").fetchall()
    return [{"broker_id": r[0], "broker_name": r[1]} for r in rows if r[2] in configured_keys]


def market_maker_daily_activity(conn, start=None, end=None) -> list[dict]:
    """
    برای هر روز معاملاتی در بازه: ارزش خرید/فروش بازارگردان (مجموع همه بازارگردان‌ها) + قیمت وزنی آن روز.
    اگر هیچ بازارگردانی در آن روز فعالیت نداشته، buy_value/sell_value صفر است (نه حذف از لیست).
    """
    mm_ids = [r["broker_id"] for r in get_market_maker_broker_ids(conn)]
    price_by_day = {p["date"]: p["weighted_avg_price"] for p in price_series(conn, start, end)}

    where, params = _date_filter(start, end)

    # آخرین قیمت واقعی هر روز = قیمت آخرین معامله بر اساس transaction_id
    last_price_rows = conn.execute(f"""
        SELECT t.trade_date_gregorian, t.price
        FROM transactions t
        JOIN (
            SELECT trade_date_gregorian,
                   MAX(transaction_id) AS last_transaction_id
            FROM transactions t
            WHERE {where}
            GROUP BY trade_date_gregorian
        ) x
          ON x.trade_date_gregorian = t.trade_date_gregorian
         AND x.last_transaction_id = t.transaction_id
    """, params).fetchall()

    last_price_by_day = dict(last_price_rows)

    if not mm_ids:
        return [
            {
                "date": d,
                "mm_buy_value": 0,
                "mm_sell_value": 0,
                "mm_net_value": 0,
                "price": p,
                "last_price": last_price_by_day.get(d, 0),
            }
            for d, p in sorted(price_by_day.items())
        ]

    placeholders = ",".join("?" * len(mm_ids))
    where, params = _date_filter(start, end)
    buy_rows = conn.execute(f"""
        SELECT trade_date_gregorian, SUM(value) FROM transactions t
        WHERE {where} AND buyer_broker_id IN ({placeholders})
        GROUP BY trade_date_gregorian
    """, params + mm_ids).fetchall()
    sell_rows = conn.execute(f"""
        SELECT trade_date_gregorian, SUM(value) FROM transactions t
        WHERE {where} AND seller_broker_id IN ({placeholders})
        GROUP BY trade_date_gregorian
    """, params + mm_ids).fetchall()
    buy_by_day = dict(buy_rows)
    sell_by_day = dict(sell_rows)

    out = []
    for d in sorted(price_by_day.keys()):
        bv = buy_by_day.get(d, 0) or 0
        sv = sell_by_day.get(d, 0) or 0
        out.append({
            "date": d,
            "mm_buy_value": bv,
            "mm_sell_value": sv,
            "mm_net_value": bv - sv,
            "price": price_by_day[d],
            "last_price": last_price_by_day.get(d, 0),
        })
    return out


def market_maker_summary(conn, start=None, end=None) -> dict:
    mm_brokers = get_market_maker_broker_ids(conn)
    daily = market_maker_daily_activity(conn, start, end)

    n_days = len(daily)
    n_active = sum(
        1 for d in daily
        if d["mm_buy_value"] > 0 or d["mm_sell_value"] > 0
    )

    # ???? ?????????? ?? ??????? ????????? ?? ???? ??????
    # ?? ???? ????? ????? ??? ?????? ????? ???? ???.
    if not mm_brokers or n_active == 0:
        return {
            "has_market_maker": False,
            "mm_broker_names": [b["broker_name"] for b in mm_brokers],
            "n_trading_days": n_days,
            "n_active_days": 0,
            "narrative": [],
            "daily": daily,
        }

    n_net_buyer_days = sum(1 for d in daily if d["mm_net_value"] > 0)
    n_net_seller_days = sum(1 for d in daily if d["mm_net_value"] < 0)
    total_buy = sum(d["mm_buy_value"] for d in daily)
    total_sell = sum(d["mm_sell_value"] for d in daily)
    net_total = total_buy - total_sell

    price_start = daily[0]["price"]
    price_end = daily[-1]["price"]
    price_change_pct = (
        ((price_end - price_start) / price_start * 100)
        if price_start else 0
    )

    # day-over-day price change, to test same-day statistical alignment
    up_days_mm_net = []
    down_days_mm_net = []

    for i in range(1, n_days):
        prev_p = daily[i - 1]["price"]
        cur_p = daily[i]["price"]

        if cur_p > prev_p:
            up_days_mm_net.append(daily[i]["mm_net_value"])
        elif cur_p < prev_p:
            down_days_mm_net.append(daily[i]["mm_net_value"])

    n_up = len(up_days_mm_net)
    n_down = len(down_days_mm_net)

    n_up_with_mm_seller = sum(
        1 for v in up_days_mm_net if v < 0
    )
    n_up_with_mm_buyer = sum(
        1 for v in up_days_mm_net if v > 0
    )
    n_down_with_mm_buyer = sum(
        1 for v in down_days_mm_net if v > 0
    )
    n_down_with_mm_seller = sum(
        1 for v in down_days_mm_net if v < 0
    )

    pct_up_seller = (
        n_up_with_mm_seller / n_up * 100
        if n_up else None
    )
    pct_up_buyer = (
        n_up_with_mm_buyer / n_up * 100
        if n_up else None
    )
    pct_down_buyer = (
        n_down_with_mm_buyer / n_down * 100
        if n_down else None
    )
    pct_down_seller = (
        n_down_with_mm_seller / n_down * 100
        if n_down else None
    )

    mm_turnover = total_buy + total_sell

    names = "? ".join(b["broker_name"] for b in mm_brokers)
    narrative = []

    narrative.append(
        f"?? ??? ????? {len(mm_brokers)} ?????????? ??????? ?? "
        f"({names}) ?? ?? {n_active} ?? {n_days} ??? ???????? "
        f"?????? ?????????."
    )

    if net_total > 0:
        narrative.append(
            f"?????????? ?? ????? ??? ???? ??????? ????? ???? ??? "
            f"(???? ???? ???? ???? {net_total:,.0f} ????)."
        )
    elif net_total < 0:
        narrative.append(
            f"?????????? ?? ????? ??? ???? ???????? ????? ???? ??? "
            f"(???? ???? ???? ???? {abs(net_total):,.0f} ????)."
        )
    else:
        narrative.append(
            "?????????? ?? ????? ??? ????? ???? ? ???? ??????? ??????? ????? ???."
        )

    if n_days >= 2:
        narrative.append(
            f"???? ?? ??? ???? ?? {price_start:.0f} ?? {price_end:.0f} ???? "
            f"????? ??? (????? {price_change_pct:+.1f}?)."
        )

    if n_up >= 3 and pct_up_seller is not None:
        narrative.append(
            f"?? {n_up} ???? ?? ???? ???? ?? ??? ??? ?????? ?????? "
            f"?????????? ?? {pct_up_seller:.0f}? ?? ?? ????? ??????? ???? "
            f"? ?? {pct_up_buyer:.0f}? ?????? ???? ???? ???."
        )

    if n_down >= 3 and pct_down_buyer is not None:
        narrative.append(
            f"?? {n_down} ???? ?? ???? ???? ?? ??? ??? ???? ?????? "
            f"?????????? ?? {pct_down_buyer:.0f}? ?? ?? ????? ?????? ???? "
            f"? ?? {pct_down_seller:.0f}? ??????? ???? ???? ???."
        )

    narrative.append(
        "????: ??? ????? ????? ???????? ????? ?? ???? ???????? "
        "?? ????? ????? ???????? ????? ???? ?????????? ???? ????? ???? ??? ???."
    )

    return {
        "has_market_maker": True,
        "mm_broker_names": [b["broker_name"] for b in mm_brokers],
        "n_trading_days": n_days,
        "n_active_days": n_active,
        "n_net_buyer_days": n_net_buyer_days,
        "n_net_seller_days": n_net_seller_days,
        "total_buy_value": total_buy,
        "total_sell_value": total_sell,
        "net_value": net_total,
        "mm_turnover": mm_turnover,
        "price_start": price_start,
        "price_end": price_end,
        "price_change_pct": price_change_pct,
        "n_up_days": n_up,
        "n_down_days": n_down,
        "pct_up_days_mm_seller": pct_up_seller,
        "pct_up_days_mm_buyer": pct_up_buyer,
        "pct_down_days_mm_buyer": pct_down_buyer,
        "pct_down_days_mm_seller": pct_down_seller,
        "narrative": narrative,
        "daily": daily,
    }

if __name__ == "__main__":
    db_path = str(pathlib.Path(__file__).resolve().parents[2] / "data" / "smart_equity.db")
    conn = sqlite3.connect(db_path)
    summary = market_maker_summary(conn)
    for k, v in summary.items():
        if k not in ("narrative", "daily"):
            print(f"{k}: {v}")
    print()
    print("Narrative:")
    for line in summary["narrative"]:
        print(" -", line)
    print()
    print(f"Daily records: {len(summary['daily'])}, sample:")
    for d in summary["daily"][:5]:
        print(" ", jalali_date_display(d["date"]), d)
