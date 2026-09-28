"""
Anomaly Detection Engine.
روش‌های آماری ساده و قابل توضیح (Z-score, IQR, Rolling stats) — بدون مدل جعبه‌سیاه غیرضروری.
هر Alert شامل دلیل، شواهد (تراکنش‌های پشتیبان)، و شدت است.
"""
from __future__ import annotations
import sqlite3
import statistics
import json
import math
import sys
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from app.analytics.metrics import BASE_FILTER, _date_filter
from app.core.jalali import jalali_date_display


def _smooth_score(base: float, excess: float, scale: float) -> float:
    """
    نگاشت پیوسته و بدون اشباع: هرچه excess بزرگ‌تر، امتیاز به ۱۰۰ نزدیک‌تر می‌شود
    اما هیچ‌وقت با فرمول خطی ساده به یک عدد ثابت (مثلاً ۱۰۰) قفل نمی‌شود.
    این باعث می‌شود چند هشدار شدید هم امتیازهای متفاوت و قابل رتبه‌بندی داشته باشند.
    """
    if excess <= 0:
        return base
    score = 100 - (100 - base) * math.exp(-excess / scale)
    return round(min(99.9, score), 1)


def _severity_from_score(score: float) -> str:
    if score < 30:
        return "Normal"
    elif score < 50:
        return "Watch"
    elif score < 70:
        return "Important"
    elif score < 85:
        return "High"
    else:
        return "Critical"


def detect_large_trades(conn: sqlite3.Connection, start=None, end=None,
                         z_threshold: float = 3.0) -> list[dict]:
    """
    معاملات با حجم/ارزش بسیار بالاتر از میانگین (Z-score روی value).
    """
    where, params = _date_filter(start, end)
    rows = conn.execute(f"""
        SELECT transaction_id, trade_date_gregorian, quantity, price, value,
               buyer_person_id, seller_person_id, buyer_broker_id, seller_broker_id
        FROM transactions t WHERE {where}
    """, params).fetchall()
    if len(rows) < 5:
        return []
    values = [r[4] for r in rows]
    mean_v = statistics.mean(values)
    stdev_v = statistics.pstdev(values) or 1.0
    person_names = {
        r[0]: " ".join(part for part in (r[1], r[2]) if part and str(part).strip()) or "?"
        for r in conn.execute(
            "SELECT person_id, first_name, family_name FROM persons"
        ).fetchall()
    }

    alerts = []
    for r in rows:
        tx_id, date, qty, price, value, buyer_id, seller_id, buyer_broker, seller_broker = r
        z = (value - mean_v) / stdev_v
        if z >= z_threshold:
            # map z-score (3..8+ typical range) onto 0-100 risk scale
            risk_score = _smooth_score(base=40, excess=z - z_threshold, scale=5)
            alerts.append({
                "alert_type": "Large Trade",
                "trade_date": date,
                "value": value,
                "quantity": qty,
                "price": price,
                "z_score": round(z, 2),
                "risk_score": round(risk_score, 1),
                "severity": _severity_from_score(risk_score),
                "reason": f"ارزش این معامله ({value:,.0f}) حدود {z:.1f} انحراف معیار بالاتر از میانگین معاملات این بازه است.",
                "supporting_transaction_ids": [tx_id],
                "buyer_person_id": buyer_id,
                "seller_person_id": seller_id,
                "buyer_broker_id": buyer_broker,
                "seller_broker_id": seller_broker,
                "buyer_name": person_names.get(buyer_id),
                "seller_name": person_names.get(seller_id),
            })
    return sorted(alerts, key=lambda a: a["risk_score"], reverse=True)


def detect_price_outliers(conn, start=None, end=None, iqr_k: float = 3.0) -> list[dict]:
    """معاملاتی با قیمتی که در همان روز به‌شدت از سایر معاملات فاصله دارد (IQR روی قیمتِ هر روز)."""
    where, params = _date_filter(start, end)
    rows = conn.execute(f"""
        SELECT transaction_id, trade_date_gregorian, price, value, quantity, buyer_person_id, seller_person_id
        FROM transactions t WHERE {where} ORDER BY trade_date_gregorian
    """, params).fetchall()
    by_day: dict[str, list] = {}
    for tx_id, date, price, value, qty, buyer_id, seller_id in rows:
        by_day.setdefault(date, []).append((tx_id, price, value, qty, buyer_id, seller_id))
    person_names = {
        r[0]: " ".join(part for part in (r[1], r[2]) if part and str(part).strip()) or "?"
        for r in conn.execute(
            "SELECT person_id, first_name, family_name FROM persons"
        ).fetchall()
    }

    alerts = []
    for date, items in by_day.items():
        if len(items) < 5:
            continue
        prices = sorted(p for _, p, _, _, _, _ in items)
        n = len(prices)
        q1 = prices[n // 4]
        q3 = prices[(3 * n) // 4]
        iqr = q3 - q1
        if iqr == 0:
            continue
        lower = q1 - iqr_k * iqr
        upper = q3 + iqr_k * iqr
        for tx_id, price, value, qty, buyer_id, seller_id in items:
            if price < lower or price > upper:
                dist = max(price - upper, lower - price)
                risk_score = _smooth_score(base=40, excess=(dist / iqr) - 0, scale=4)
                alerts.append({
                    "alert_type": "Price Outlier",
                    "trade_date": date,
                    "price": price,
                    "value": value,
                    "quantity": qty,
                    "risk_score": round(risk_score, 1),
                    "severity": _severity_from_score(risk_score),
                    "reason": f"قیمت این معامله ({price}) در مقایسه با دامنه معمول قیمت همان روز ({q1}-{q3}) غیرعادی است.",
                    "supporting_transaction_ids": [tx_id],
                    "buyer_person_id": buyer_id,
                    "seller_person_id": seller_id,
                    "buyer_name": person_names.get(buyer_id),
                    "seller_name": person_names.get(seller_id),
                })
    return sorted(alerts, key=lambda a: a["risk_score"], reverse=True)


def detect_broker_activity_spike(conn, start=None, end=None, z_threshold: float = 2.5) -> list[dict]:
    """
    روزهایی که فعالیت یک کارگزار (ارزش معاملات آن روز) به‌شدت بالاتر از میانگین فعالیت روزانه‌ی خودش است.
    """
    where, params = _date_filter(start, end)
    rows = conn.execute(f"""
        SELECT buyer_broker_id, trade_date_gregorian, SUM(value)
        FROM transactions t WHERE {where}
        GROUP BY buyer_broker_id, trade_date_gregorian
    """, params).fetchall()
    by_broker: dict[int, list] = {}
    for broker_id, date, val in rows:
        by_broker.setdefault(broker_id, []).append((date, val))

    names = dict(conn.execute("SELECT broker_id, broker_name_raw FROM brokers"))
    alerts = []
    for broker_id, daily in by_broker.items():
        if len(daily) < 5:
            continue
        vals = [v for _, v in daily]
        mean_v = statistics.mean(vals)
        stdev_v = statistics.pstdev(vals) or 1.0
        for date, val in daily:
            z = (val - mean_v) / stdev_v
            if z >= z_threshold:
                risk_score = _smooth_score(base=35, excess=z - z_threshold, scale=4)
                alerts.append({
                    "alert_type": "Broker Activity Spike",
                    "trade_date": date,
                    "broker_id": broker_id,
                    "broker_name": names.get(broker_id),
                    "value": val,
                    "z_score": round(z, 2),
                    "risk_score": round(risk_score, 1),
                    "severity": _severity_from_score(risk_score),
                    "reason": f"فعالیت خرید کارگزار «{names.get(broker_id)}» در تاریخ {jalali_date_display(date)} حدود {z:.1f} انحراف معیار بالاتر از میانگین فعالیت روزانه‌ی خودِ این کارگزار است.",
                    "supporting_transaction_ids": [],
                })
    return sorted(alerts, key=lambda a: a["risk_score"], reverse=True)


def run_all_anomaly_detectors(conn, start=None, end=None) -> list[dict]:
    alerts = []
    alerts += detect_large_trades(conn, start, end)
    alerts += detect_price_outliers(conn, start, end)
    alerts += detect_broker_activity_spike(conn, start, end)
    return sorted(alerts, key=lambda a: a["risk_score"], reverse=True)


def top_alerts_diversified(conn, start=None, end=None, top_n: int = 10) -> list[dict]:
    """
    برای گزارش هیئت‌مدیره: به‌جای اینکه Top N صرفاً از پرتکرارترین نوع هشدار پر شود
    (مثلاً وقتی همه‌ی امتیازهای بالا مربوط به یک روز/یک نوع خاص هستند)،
    سهمی متناسب از هر نوع هشدار نمایش داده می‌شود تا تصویر کامل‌تری به هیئت‌مدیره بدهد.
    """
    all_alerts = run_all_anomaly_detectors(conn, start, end)
    by_type: dict[str, list] = {}
    for a in all_alerts:
        by_type.setdefault(a["alert_type"], []).append(a)
    types = list(by_type.keys())
    if not types:
        return []
    per_type = max(1, top_n // len(types))
    picked = []
    for t in types:
        picked += by_type[t][:per_type]
    picked = sorted(picked, key=lambda a: a["risk_score"], reverse=True)
    # fill remaining slots (if any type had fewer alerts than its quota) from the global ranking
    if len(picked) < top_n:
        picked_ids = {id(a) for a in picked}
        for a in all_alerts:
            if id(a) not in picked_ids:
                picked.append(a)
                picked_ids.add(id(a))
            if len(picked) >= top_n:
                break
    return sorted(picked[:top_n], key=lambda a: a["risk_score"], reverse=True)


if __name__ == "__main__":
    import pathlib
    db_path = str(pathlib.Path(__file__).resolve().parents[2] / "data" / "smart_equity.db")
    conn = sqlite3.connect(db_path)
    all_alerts = run_all_anomaly_detectors(conn)
    print(f"Total alerts: {len(all_alerts)}")
    by_type = {}
    for a in all_alerts:
        by_type[a["alert_type"]] = by_type.get(a["alert_type"], 0) + 1
    print("By type:", by_type)
    print()
    print("Top 5 highest-risk alerts:")
    for a in all_alerts[:5]:
        print(f"  [{a['severity']:9s}] {a['alert_type']:22s} score={a['risk_score']:5.1f}  {a['reason'][:80]}")
