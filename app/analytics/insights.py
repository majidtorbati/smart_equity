"""
Smart Insight Engine — تولید جملات تحلیلی فارسی صرفاً بر اساس داده واقعی محاسبه‌شده.
هیچ متن عمومی/جعلی تولید نمی‌شود؛ هر جمله مستقیماً از یک Metric واقعی می‌آید.
"""
from __future__ import annotations
import sqlite3
import sys
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from app.analytics import metrics as m
from app.detection import anomaly as an
from app.detection import behavior as bh
from app.analytics import market_maker as mm
from app.core.labels import severity_fa


def executive_summary_narrative(conn: sqlite3.Connection, start=None, end=None) -> list[str]:
    """????? ????? ??????? ?? ???? ???? ????? ??????????."""
    ov = m.overview(conn, start, end)
    conc = m.concentration(conn, "buyer", start, end)
    top_brokers_buy = m.top_brokers(conn, "buyer", start, end, top_n=1)

    alerts = an.run_all_anomaly_detectors(conn, start, end)
    n_critical = sum(
        1 for a in alerts
        if a["severity"] == "Critical"
    )

    st = bh.top_short_term_traders(
        conn, start, end, top_n=1000
    )
    n_high_behavior = sum(
        1 for t in st
        if t["score"] >= 70
    )

    lines = []

    lines.append(
        f"در این بازه {ov['n_transactions']:,} معامله به ارزش "
        f"{ov['total_value']:,.0f} ریال ثبت شده است و میانگین وزنی قیمت "
        f"{ov['weighted_avg_price']:.0f} ریال بوده است."
    )

    if top_brokers_buy:
        b = top_brokers_buy[0]
        share = (
            b["value"] / ov["total_value"] * 100
            if ov["total_value"]
            else 0
        )
        lines.append(
            f"بزرگترین قارگزار خرید از نظر ارزش معاملات "
            f"«{b['broker_name']}» بوده که {share:.1f} درصد "
            f"از ارزش کل خرید را به خود اختصاص داده است."
        )

    level_fa = {
        "Low concentration": "پایین",
        "Medium concentration": "متوسط",
        "High concentration": "بالا",
    }.get(conc["level"], conc["level"])

    lines.append(
        f"{conc['top10_share_pct']:.1f} درصد از ارزش خرید در اختیار "
        f"10 خریدار برتر بوده است "
        f"(سطح تمرکز: {level_fa})."
    )

    if n_critical > 0:
        lines.append(
            f"{n_critical} هشدار با شدت بالا در شاخص‌های تشخیص ناهنجاری "
            f"شناسایی شده است. این هشدارها شاخص‌های آماری برای "
            f"بررسی بیشتر هستند و به تنهایی نشانه تخلف یا دستکاری بازار نیستند."
        )
    else:
        lines.append(
            "هشدار با شدت بالا در خروجی شاخص‌های تشخیص ناهنجاری در این بازه شناسایی نشد."
        )

    if n_high_behavior > 0:
        lines.append(
            f"{n_high_behavior} نفر در این بازه دارای امتیاز رفتار کوتاه‌مدت بالاتر از 70 هستند. "
            f"این امتیاز فقط یک شاخص آماری است و به تنهایی نشاندهنده قصد یا استراتژی معاملاتی نیست."
        )

    mm_summary = mm.market_maker_summary(conn, start, end)

    if mm_summary.get("has_market_maker"):
        net_value = mm_summary.get("net_value", 0)

        if net_value > 0:
            lines.append(
                f"برآیند فعالیت بازارگردان در این بازه خالصاً خرید بوده است "
                f"(خالص خرید {net_value:,.0f} ریال)."
            )
        elif net_value < 0:
            lines.append(
                f"برآیند فعالیت بازارگردان در این بازه خالصاً فروش بوده است "
                f"(خالص فروش {abs(net_value):,.0f} ریال)."
            )
        else:
            lines.append(
                "برآیند ارزش خرید و فروش بازارگردان در این بازه برابر بوده است."
            )

    return lines

if __name__ == "__main__":
    db_path = str(pathlib.Path(__file__).resolve().parents[2] / "data" / "smart_equity.db")
    conn = sqlite3.connect(db_path)
    for line in executive_summary_narrative(conn):
        print("-", line)
