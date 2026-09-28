"""
تولید نمودارهای تصویری (PNG) برای جاسازی در گزارش PDF.
از matplotlib با فونت Vazirmatn و reshape فارسی استفاده می‌شود (چون matplotlib خودش RTL/شکل‌دهی حروف عربی-فارسی را انجام نمی‌دهد).
"""
from __future__ import annotations
import pathlib
import sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

from app.core.farsi_text import fa
from app.core.jalali import jalali_date_display
import datetime as dt

ASSETS_DIR = pathlib.Path(__file__).resolve().parents[2] / "assets"
_FONT_PATH = str(ASSETS_DIR / "Vazirmatn-Regular.ttf")
fm.fontManager.addfont(_FONT_PATH)
_FONT_NAME = fm.FontProperties(fname=_FONT_PATH).get_name()
plt.rcParams["font.family"] = _FONT_NAME
plt.rcParams["axes.unicode_minus"] = False

COLOR_PRIMARY = "#1F4E78"
COLOR_BUY = "#2E86AB"
COLOR_SELL = "#B02A2A"
COLOR_PRICE = "#F2A104"


def _sample_labels(labels: list[str], max_labels: int = 10) -> list[str]:
    step = max(1, len(labels) // max_labels)
    return [lab if i % step == 0 else "" for i, lab in enumerate(labels)]


def price_trend_chart(series_data: list[dict], out_path: str, title: str = "روند قیمت وزنی روزانه"):
    dates = [jalali_date_display(d["date"])[5:] for d in series_data]  # MM/DD
    prices = [d["weighted_avg_price"] for d in series_data]

    fig, ax = plt.subplots(figsize=(7.2, 3.0), dpi=150)
    ax.plot(range(len(prices)), prices, color=COLOR_PRIMARY, linewidth=2)
    ax.fill_between(range(len(prices)), prices, min(prices) * 0.98, color=COLOR_PRIMARY, alpha=0.08)
    ax.set_xticks(range(len(dates)))
    ax.set_xticklabels(_sample_labels(dates), fontsize=8)
    ax.set_title(fa(title), fontsize=12)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", linestyle="--", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, transparent=True)
    plt.close(fig)
    return out_path


def market_maker_chart(daily: list[dict], out_path: str, title: str = "فعالیت بازارگردان و روند قیمت"):
    dates = [jalali_date_display(d["date"])[5:] for d in daily]
    net_values = [d["mm_net_value"] for d in daily]
    prices = [d["price"] for d in daily]

    fig, ax1 = plt.subplots(figsize=(7.2, 3.2), dpi=150)
    colors_bar = [COLOR_BUY if v >= 0 else COLOR_SELL for v in net_values]
    ax1.bar(range(len(net_values)), net_values, color=colors_bar, alpha=0.75, width=0.6)
    ax1.axhline(0, color="#888888", linewidth=0.8)
    ax1.set_ylabel(fa("خالص خرید/فروش بازارگردان (ریال)"), fontsize=8)
    ax1.set_xticks(range(len(dates)))
    ax1.set_xticklabels(_sample_labels(dates), fontsize=8)
    ax1.spines["top"].set_visible(False)

    ax2 = ax1.twinx()
    ax2.plot(range(len(prices)), prices, color=COLOR_PRICE, linewidth=2, marker="o", markersize=2)
    ax2.set_ylabel(fa("قیمت وزنی"), fontsize=8)
    ax2.spines["top"].set_visible(False)

    ax1.set_title(fa(title), fontsize=12)
    fig.tight_layout()
    fig.savefig(out_path, transparent=True)
    plt.close(fig)
    return out_path


def comparison_bar_chart(deltas: dict, out_path: str, title: str = "مقایسه با بازه قبل"):
    label_fa = {
        "n_transactions": "تعداد معاملات", "total_value": "ارزش کل", "total_quantity": "حجم کل",
        "weighted_avg_price": "میانگین قیمت", "n_unique_buyers": "تعداد خریداران",
    }
    keys = [k for k in label_fa if k in deltas and deltas[k]["pct"] is not None]
    labels = [fa(label_fa[k]) for k in keys]
    pcts = [deltas[k]["pct"] for k in keys]
    colors_bar = [COLOR_BUY if p >= 0 else COLOR_SELL for p in pcts]

    fig, ax = plt.subplots(figsize=(7.2, 2.8), dpi=150)
    bars = ax.barh(labels, pcts, color=colors_bar, alpha=0.85)
    ax.axvline(0, color="#888888", linewidth=0.8)
    ax.margins(x=0.22)  # فضای کافی برای برچسب اعداد، به‌خصوص وقتی یک میله خیلی کوچک کنار میله‌های بزرگ باشد
    x_range = max(pcts) - min(pcts) if len(pcts) > 1 else max(abs(p) for p in pcts) or 1
    offset = max(x_range * 0.02, 0.8)
    for bar, pct in zip(bars, pcts):
        ax.text(bar.get_width() + (offset if pct >= 0 else -offset), bar.get_y() + bar.get_height() / 2,
                f"{pct:+.1f}%", va="center", ha="left" if pct >= 0 else "right", fontsize=8)
    ax.set_title(fa(title), fontsize=12)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    fig.savefig(out_path, transparent=True)
    plt.close(fig)
    return out_path


if __name__ == "__main__":
    import sqlite3
    from app.analytics import metrics as m
    from app.analytics import market_maker as mm
    from app.analytics import comparison as comp

    db_path = str(pathlib.Path(__file__).resolve().parents[2] / "data" / "smart_equity.db")
    conn = sqlite3.connect(db_path)

    out_dir = pathlib.Path("/tmp/chart_test")
    out_dir.mkdir(exist_ok=True)

    series = m.price_series(conn)
    price_trend_chart(series, str(out_dir / "price.png"))
    print("price chart saved")

    mm_summary = mm.market_maker_summary(conn)
    market_maker_chart(mm_summary["daily"], str(out_dir / "mm.png"))
    print("mm chart saved")

    cmp_res = comp.auto_compare_with_previous(conn)
    comparison_bar_chart(cmp_res["deltas"], str(out_dir / "cmp.png"))
    print("comparison chart saved")
