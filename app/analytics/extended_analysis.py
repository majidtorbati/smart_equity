"""
تحلیل‌های تکمیلی درخواستی هیئت‌مدیره: HHI، بنیادی، کیفی، روش‌های ارزش‌گذاری.

اصل راهنما (طبق همان قانونی که در کل این پروژه رعایت شده):
داده موجود ما فقط «داده معاملات» است (خریدار، فروشنده، تعداد، قیمت، تاریخ).
هیچ داده صورت مالی (درآمد، سود، ترازنامه، جریان نقدی) یا داده کیفی شرکت
(مدیریت، حاکمیت شرکتی، جایگاه رقابتی) در اختیار نداریم.

بنابراین:
- HHI: کاملاً از داده موجود قابل محاسبه است (قبلاً در metrics.concentration پیاده‌سازی شده).
- تحلیل بنیادی واقعی (P/E، EPS، رشد درآمد و ...): از داده معاملات قابل استخراج نیست.
  به‌جای جعل عدد، این محدودیت صریح اعلام و دقیقاً مشخص می‌شود چه داده‌ای لازم است.
- تحلیل کیفی شرکت (مدیریت، صنعت، حاکمیت شرکتی): از داده معاملات قابل استخراج نیست.
  اما یک «تحلیل کیفی رفتار بازار» (ساختار مالکیت، نقش بازارگردان، غلبه حقیقی/حقوقی)
  کاملاً از داده موجود و به‌صورت مستند قابل ارائه است — با عنوان صریح متفاوت تا با
  تحلیل کیفی بنیادی شرکت اشتباه گرفته نشود.
- روش‌های ارزش‌گذاری (DCF، ضرایب P/E، NAV و ...): محاسبه واقعی نیاز به صورت‌های مالی دارد.
  آنچه از داده معاملات واقعاً داریم فقط «قیمت بازار مشاهده‌شده» است، نه «ارزش ذاتی» —
  این دو مفهوم به‌وضوح از هم تفکیک می‌شوند.
"""
from __future__ import annotations
import sqlite3
import sys
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from app.analytics import metrics as m
from app.analytics import market_maker as mm_mod
from app.core.labels import concentration_level_fa


def hhi_summary(conn: sqlite3.Connection, start=None, end=None) -> dict:
    """بسته‌بندی HHI خریداران/فروشندگان با تفسیر متنی، برای اسلاید اختصاصی."""
    c_buy = m.concentration(conn, "buyer", start, end)
    c_sell = m.concentration(conn, "seller", start, end)
    level_fa = {"Low concentration": "پایین", "Medium concentration": "متوسط", "High concentration": "بالا"}
    narrative = [
        f"شاخص HHI خرید {c_buy['hhi']:.0f} است (سطح تمرکز: {level_fa.get(c_buy['level'], c_buy['level'])}؛ "
        f"مقیاس استاندارد HHI از ? تا ??,??? است).",
        f"{c_buy['top10_share_pct']:.1f}٪ از ارزش خرید در اختیار ?? خریدار برتر است.",
        f"شاخص HHI فروش {c_sell['hhi']:.0f} است (سطح تمرکز: {level_fa.get(c_sell['level'], c_sell['level'])}).",
    ]
    return {"buy": c_buy, "sell": c_sell, "narrative": narrative}

def fundamental_analysis_note(conn: sqlite3.Connection) -> dict:
    """
    محدودیت صریح: تحلیل بنیادی واقعی از داده معاملات ساخته نمی‌شود.
    """
    required_data = [
        "صورت سود و زیان (درآمد، سود خالص، حاشیه سود عملیاتی)",
        "ترازنامه (دارایی‌ها، بدهی‌ها، حقوق صاحبان سهام)",
        "صورت جریان وجوه نقد",
        "EPS (سود هر سهم) و P/E (نسبت قیمت به سود)",
        "پیش‌بینی/بودجه سال مالی جاری",
    ]
    narrative = [
        "داده در دسترس این گزارش صرفاً «معاملات ثانویه سهام» است (خریدار، فروشنده، قیمت، حجم، تاریخ).",
        "تحلیل بنیادی واقعی (سودآوری، رشد درآمد، نسبت‌های مالی) نیازمند صورت‌های مالی شرکت است که در این دیتاست موجود نیست.",
        "برای تکمیل این بخش، صورت‌های مالی حسابرسی‌شده و گزارش‌های دوره‌ای شرکت باید در اختیار قرار گیرد.",
    ]
    return {"required_data": required_data, "narrative": narrative}


def qualitative_market_behavior(conn: sqlite3.Connection, start=None, end=None) -> dict:
    """
    تحلیل کیفی «رفتار بازار» (نه تحلیل کیفی بنیادی شرکت) — کاملاً مبتنی بر داده معاملات واقعی.
    عنوان و محتوا عمداً محدود به آنچه از داده قابل استنتاج است نگه داشته شده.
    """
    ov = m.overview(conn, start, end)
    iv = m.individual_vs_institutional(conn, start, end)
    c_buy = m.concentration(conn, "buyer", start, end)
    mm_summary = mm_mod.market_maker_summary(conn, start, end)

    inst_buy = sum(v["buy_value"] for k, v in iv.items() if "حقوقی" in str(k))
    indiv_buy = sum(v["buy_value"] for k, v in iv.items() if "حقیقی" in str(k))
    total_buy = inst_buy + indiv_buy
    inst_share = (inst_buy / total_buy * 100) if total_buy else 0

    narrative = []
    narrative.append(
        f"از نظر ساختار مالکیت معاملاتی، {inst_share:.1f}٪ از ارزش خرید توسط اشخاص حقوقی و "
        f"{100-inst_share:.1f}٪ توسط اشخاص حقیقی انجام شده است."
    )
    narrative.append(
        f"تمرکز خرید در سطح «{concentration_level_fa(c_buy['level'])}» ارزیابی می‌شود؛ این نشان می‌دهد ساختار خریداران "
        f"{'نسبتاً پراکنده و رقابتی است' if c_buy['hhi'] < 1500 else 'در دست عده محدودی متمرکز است'}."
    )
    if mm_summary.get("has_market_maker"):
        narrative.append(
            "الگوی رفتار بازارگردان در این بازه با نقش «تثبیت‌کننده» هم‌خوانی دارد "
            "(عرضه در روزهای رشد قیمت و تقاضا در روزهای افت قیمت) — جزئیات در بخش رفتار بازارگردان."
        )
    narrative.append(
        "توجه: این یک «تحلیل کیفی رفتار بازار» بر مبنای داده معاملات است، نه تحلیل کیفی بنیادی شرکت "
        "(که نیازمند بررسی مدیریت، جایگاه رقابتی، و حاکمیت شرکتی است و در این گزارش انجام نشده)."
    )
    return {"institutional_share_pct": inst_share, "individual_share_pct": 100 - inst_share, "narrative": narrative}


def valuation_methods_overview(conn: sqlite3.Connection, start=None, end=None) -> dict:
    """
    روش‌های متداول ارزش‌گذاری سهام را به‌صورت روش‌شناختی معرفی می‌کند (دانش عمومی مالی، نه محاسبه اختصاصی)
    و آنچه از داده معاملات واقعاً در دسترس است (قیمت بازار مشاهده‌شده) را به‌وضوح از «ارزش ذاتی» تفکیک می‌کند.
    """
    ov = m.overview(conn, start, end)
    methods = [
        {"name": "روش تنزیل جریان نقدی (DCF)", "needs": "پیش‌بینی جریان نقد آزاد، نرخ تنزیل (WACC)، نرخ رشد بلندمدت"},
        {"name": "ضرایب قیمتی (P/E ،P/B ،EV/EBITDA)", "needs": "سود/دفتری/EBITDA شرکت و شرکت‌های مشابه صنعت"},
        {"name": "ارزش خالص دارایی‌ها (NAV)", "needs": "ارزش روز دارایی‌ها و بدهی‌های ترازنامه"},
        {"name": "روش معاملات مشابه (Comparable Transactions)", "needs": "سوابق معاملات M&A شرکت‌های قابل مقایسه"},
    ]
    narrative = [
        "محاسبه واقعی «ارزش ذاتی» سهم با هر یک از روش‌های بالا نیازمند داده‌های مالی شرکت است که در دیتاست معاملاتی این گزارش وجود ندارد.",
        f"آنچه از داده معاملات موجود است، «قیمت بازار مشاهده‌شده» است: میانگین وزنی {ov['weighted_avg_price']:.0f} ریال "
        f"در این بازه (بین کمینه و بیشینه معاملات ثبت‌شده) — این قیمت معامله در بازار است، نه برآورد ارزش ذاتی.",
        "توصیه: در صورت نیاز به مقایسه قیمت بازار با ارزش ذاتی (برای تشخیص کمتر/بیشتر از ارزش بودن سهم)، "
        "صورت‌های مالی و برآوردهای صنعت باید تهیه و در گزارش بعدی لحاظ شود.",
    ]
    return {"methods": methods, "observed_market_price": ov["weighted_avg_price"], "narrative": narrative}


if __name__ == "__main__":
    db_path = str(pathlib.Path(__file__).resolve().parents[2] / "data" / "smart_equity.db")
    conn = sqlite3.connect(db_path)

    print("=== HHI ===")
    for line in hhi_summary(conn)["narrative"]:
        print(" -", line)
    print()
    print("=== Fundamental (limitation) ===")
    for line in fundamental_analysis_note(conn)["narrative"]:
        print(" -", line)
    print()
    print("=== Qualitative market behavior ===")
    for line in qualitative_market_behavior(conn)["narrative"]:
        print(" -", line)
    print()
    print("=== Valuation methods ===")
    for line in valuation_methods_overview(conn)["narrative"]:
        print(" -", line)
