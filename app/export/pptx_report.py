"""
PowerPoint Export — گزارش قابل ارائه در جلسه هیئت‌مدیره.

چرا python-pptx (نه pptxgenjs/Node)؟
این ماژول بخشی از خودِ نرم‌افزار پرتابل است (دکمه Export داخل برنامه) و باید روی هر
کامپیوتر ویندوزی بدون Node.js/npm/اینترنت اجرا شود. python-pptx یک کتابخانه خالص
Python است که با PyInstaller باندل می‌شود؛ pptxgenjs به Node.js نیاز دارد که در
build نهایی موجود نیست.

فونت: Tahoma (نه Vazirmatn) — چون روی PPTX نمی‌توان مثل PDF فونت را Embed کرد و
مطمئن شد همه‌جا هست؛ Tahoma از ویندوز XP به بعد روی هر سیستم ویندوزی نصب است و
پشتیبانی رسمی و کامل از حروف فارسی/عربی دارد (طراحی خود مایکروسافت برای همین منظور).
"""
from __future__ import annotations
import sqlite3
import sys
import pathlib
import tempfile
import datetime as dt
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn
from pptx.oxml.xmlchemy import OxmlElement

from app.analytics import metrics as m
from app.analytics import market_maker as mm_mod
from app.analytics import comparison as comp
from app.analytics import insights as ins
from app.analytics import extended_analysis as ext
from app.analytics import portfolio as pf
from app.detection import anomaly as an
from app.detection import behavior as bh
from app.core.labels import alert_type_fa, severity_fa, concentration_level_fa
from app.core.jalali import jalali_date_display, gregorian_to_jalali
from app.core.normalize import clean_display
from app.core.runtime import resource_root
from app.reports import charts as ch
from app.config.settings import (get_company_name, get_report_prepared_by, get_report_audience,
                                  get_report_title, get_logo_path, DEVELOPER_CREDIT_LINE)

# ---------------------------------------------------------------------------
# Palette: "Midnight Executive" — مناسب گزارش مالی/هیئت‌مدیره
# ---------------------------------------------------------------------------
NAVY = RGBColor(0x1E, 0x27, 0x61)
NAVY_DARK = RGBColor(0x14, 0x1B, 0x47)
ICE_BLUE = RGBColor(0xCA, 0xDC, 0xFC)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
TEXT_DARK = RGBColor(0x1A, 0x1A, 0x2E)
TEXT_MUTED = RGBColor(0x6B, 0x72, 0x80)
ROW_ALT = RGBColor(0xF4, 0xF6, 0xFB)
GOOD_GREEN = RGBColor(0x1E, 0x7E, 0x34)
BAD_RED = RGBColor(0xB0, 0x2A, 0x2A)

FONT = "Tahoma"
SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)
MARGIN = Inches(0.6)

_RTL_ATTEMPTED_WARNING = False


def _set_rtl(paragraph):
    """تلاش برای تنظیم rtl=1 در XML پاراگراف (برای رفتار صحیح ویرایش در PowerPoint)."""
    try:
        pPr = paragraph._p.get_or_add_pPr()
        pPr.set("rtl", "1")
    except Exception:
        pass  # صرفاً یک بهبود جانبی است؛ عدم موفقیت نباید تولید فایل را متوقف کند


def _fmt_num(x):
    try:
        return f"{x:,.0f}"
    except Exception:
        return str(x)


def _fmt_compact_billion_rial(x):
    """برای Stat Card ها: عدد بزرگ ریالی را به میلیارد ریال (قرارداد رایج گزارش‌های مالی ایران) خلاصه می‌کند."""
    try:
        return f"{x/1e9:,.0f}"
    except Exception:
        return str(x)


def _truncate(text, n):
    """کوتاه‌سازی برای ستون‌های جدول با فضای محدود؛ در صورت بریدن، با «…» علامت‌گذاری می‌شود (نه یک برش خام وسط کلمه)."""
    text = str(text)
    if len(text) <= n:
        return text
    return text[:n].rstrip(" -–—.،") + "…"


def _set_run_font(run, font_name=FONT, lang="fa-IR"):
    """فونت را برای Latin/East-Asia/Complex-Script هم‌زمان ثبت می‌کند.

    python-pptx معمولاً فقط a:latin را می‌نویسد؛ در PowerPoint ویندوز این موضوع می‌تواند
    باعث شود حروف فارسی از فونت دیگری گرفته شوند. این تابع هر سه family را صریحاً ثبت می‌کند.
    """
    run.font.name = font_name
    rPr = run._r.get_or_add_rPr()
    rPr.set("lang", lang)
    # حذف cs/ea قبلی و ثبت صریح هر سه family
    for tag in ("{http://schemas.openxmlformats.org/drawingml/2006/main}cs",
                "{http://schemas.openxmlformats.org/drawingml/2006/main}ea",
                "{http://schemas.openxmlformats.org/drawingml/2006/main}latin"):
        for child in list(rPr):
            if child.tag == tag:
                rPr.remove(child)
    for tag in ("latin", "ea", "cs"):
        el = OxmlElement(f"a:{tag}")
        el.set("typeface", font_name)
        rPr.append(el)


def _add_textbox(slide, x, y, w, h, text, size=14, bold=False, color=TEXT_DARK,
                  align=PP_ALIGN.RIGHT, font=FONT, line_spacing=1.15):
    box = slide.shapes.add_textbox(x, y, w, h)
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.TOP
    lines = text if isinstance(text, list) else [text]
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = line_spacing
        _set_rtl(p)
        run = p.add_run()
        run.text = line
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.color.rgb = color
        _set_run_font(run, font)
    return box


def _add_bullets(slide, x, y, w, h, bullets, size=13, color=TEXT_DARK, space_after=8):
    box = slide.shapes.add_textbox(x, y, w, h)
    tf = box.text_frame
    tf.word_wrap = True
    for i, b in enumerate(bullets):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = PP_ALIGN.RIGHT
        p.space_after = Pt(space_after)
        _set_rtl(p)
        run = p.add_run()
        run.text = f"• {b}"
        run.font.size = Pt(size)
        run.font.color.rgb = color
        _set_run_font(run, FONT)
    return box


def _add_rect(slide, x, y, w, h, fill_color, line=False):
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h)
    shape.adjustments[0] = 0.06
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill_color
    if line:
        shape.line.color.rgb = fill_color
    else:
        shape.line.fill.background()
    shape.shadow.inherit = False
    return shape


def _slide_bg(slide, color):
    bg = slide.background
    bg.fill.solid()
    bg.fill.fore_color.rgb = color


def _add_slide(prs, bg=WHITE):
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank layout
    _slide_bg(slide, bg)
    return slide


def _add_page_title(slide, title, dark_bg=False):
    color = WHITE if dark_bg else NAVY
    _add_textbox(slide, MARGIN, Inches(0.35), SLIDE_W - 2 * MARGIN, Inches(0.7),
                 title, size=26, bold=True, color=color, align=PP_ALIGN.RIGHT)
    line = slide.shapes.add_connector(1, MARGIN, Inches(1.05), SLIDE_W - MARGIN, Inches(1.05))
    line.line.color.rgb = ICE_BLUE if dark_bg else NAVY
    line.line.width = Pt(1.25)


def _add_stat_card(slide, x, y, w, h, value_text, label_text, accent=NAVY):
    _add_rect(slide, x, y, w, h, RGBColor(0xF7, 0xF9, 0xFC))
    # اعداد طولانی‌تر باید کوچک‌تر رسم شوند وگرنه در یک Card باریک به خط دوم می‌شکنند و روی برچسب زیرش می‌افتند
    value_size = 26 if len(str(value_text)) <= 8 else (20 if len(str(value_text)) <= 13 else 16)
    _add_textbox(slide, x + Inches(0.08), y + Inches(0.12), w - Inches(0.16), h - Inches(0.55),
                 value_text, size=value_size, bold=True, color=accent, align=PP_ALIGN.CENTER)
    _add_textbox(slide, x + Inches(0.08), y + h - Inches(0.42), w - Inches(0.16), Inches(0.35),
                 label_text, size=11, bold=False, color=TEXT_MUTED, align=PP_ALIGN.CENTER)


def _add_rtl_table(slide, x, y, w, h, headers, rows, col_widths_ratio=None, font_size=11):
    """
    جدول با ترتیب راست‌به‌چپ: ستون منطقی اول (headers[0]) در سمت راست فیزیکی جدول قرار می‌گیرد،
    چون python-pptx مفهوم 'RTL کل جدول' ندارد و ستون ۰ همیشه فیزیکاً چپ‌ترین است.
    """
    n_cols = len(headers)
    n_rows = len(rows) + 1
    shape = slide.shapes.add_table(n_rows, n_cols, x, y, w, h)
    table = shape.table
    if col_widths_ratio:
        for i, ratio in enumerate(col_widths_ratio):
            table.columns[i].width = Emu(int(w * ratio))
    else:
        for i in range(n_cols):
            table.columns[i].width = Emu(int(w / n_cols))

    def set_cell(r, c_logical, text, header=False, alt=False):
        c_physical = n_cols - 1 - c_logical
        cell = table.cell(r, c_physical)
        cell.text = ""
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        cell.margin_left = Pt(4)
        cell.margin_right = Pt(4)
        tf = cell.text_frame
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.RIGHT
        _set_rtl(p)
        run = p.add_run()
        run.text = str(text)
        run.font.size = Pt(font_size if not header else font_size)
        _set_run_font(run, FONT)
        run.font.bold = header
        run.font.color.rgb = WHITE if header else TEXT_DARK
        cell.fill.solid()
        cell.fill.fore_color.rgb = NAVY if header else (ROW_ALT if alt else WHITE)

    for c, h_text in enumerate(headers):
        set_cell(0, c, h_text, header=True)
    for r, row in enumerate(rows, start=1):
        for c, val in enumerate(row):
            set_cell(r, c, val, alt=(r % 2 == 0))
    return shape


def _add_picture_fit(slide, path, x, y, max_w, max_h):
    from PIL import Image
    with Image.open(path) as im:
        iw, ih = im.size
    ratio = min(max_w / iw, max_h / ih)
    w, h = int(iw * ratio), int(ih * ratio)
    px = x + (max_w - w) // 2
    py = y + (max_h - h) // 2
    slide.shapes.add_picture(path, px, py, width=w, height=h)


def _symbol_label(conn) -> str:
    rows = conn.execute("SELECT symbol_code, symbol_name FROM symbols").fetchall()
    if len(rows) == 1:
        code, name = rows[0]
        name_clean = clean_display(name) if name and str(name) != "nan" else ""
        return f"{code} ({name_clean})" if name_clean else str(code)
    return f"{len(rows)} نماد"


def _now_jalali_str() -> str:
    now = dt.datetime.now()
    jy, jm, jd = gregorian_to_jalali(now.year, now.month, now.day)
    return f"{jy:04d}/{jm:02d}/{jd:02d}"


# ---------------------------------------------------------------------------
# Main builder
# ---------------------------------------------------------------------------

def generate_pptx_report(conn: sqlite3.Connection, out_path: str, start=None, end=None,
                          top_n=8, prepared_by=None) -> str:
    tmp_dir = pathlib.Path(tempfile.mkdtemp(prefix="smarteq_pptx_"))
    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H

    ov = m.overview(conn, start, end)
    period_start_fa = jalali_date_display(start) if start else jalali_date_display(ov["first_date"])
    period_end_fa = jalali_date_display(end) if end else jalali_date_display(ov["last_date"])
    symbol_label = _symbol_label(conn)
    prepared_by = prepared_by or get_report_prepared_by()
    company_name = get_company_name()
    audience = get_report_audience()

    # ---------- Slide 1: Title (dark) ----------
    s = _add_slide(prs, bg=NAVY)
    logo_path = get_logo_path()
    if logo_path:
        _add_picture_fit(s, str(logo_path), Inches(5.67), Inches(0.5), Inches(2), Inches(1.1))
    _add_textbox(s, Inches(1), Inches(2.3), SLIDE_W - Inches(2), Inches(1.3),
                 get_report_title(), size=40, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    _add_textbox(s, Inches(1), Inches(3.3), SLIDE_W - Inches(2), Inches(0.6),
                 f"ارائه به {audience}", size=20, bold=False, color=ICE_BLUE, align=PP_ALIGN.CENTER)
    info_lines = []
    if company_name:
        info_lines.append(f"شرکت: {company_name}")
    info_lines += [
        f"نماد: {symbol_label}",
        f"بازه: از {period_start_fa} تا {period_end_fa}",
        f"تهیه‌کننده: {prepared_by}   |   تاریخ تهیه: {_now_jalali_str()}",
    ]
    _add_textbox(s, Inches(1), Inches(4.2), SLIDE_W - Inches(2), Inches(1.6),
                 info_lines, size=14, bold=False, color=WHITE, align=PP_ALIGN.CENTER)
    _add_textbox(s, Inches(1), Inches(6.9), SLIDE_W - Inches(2), Inches(0.4),
                 DEVELOPER_CREDIT_LINE, size=10, bold=False, color=ICE_BLUE, align=PP_ALIGN.CENTER)

    # ---------- Slide 2: Executive summary ----------
    s = _add_slide(prs)
    _add_page_title(s, "خلاصه مدیریتی")
    narrative = ins.executive_summary_narrative(conn, start, end)
    _add_bullets(s, MARGIN, Inches(1.3), SLIDE_W - 2 * MARGIN, Inches(2.3), narrative, size=14)

    kpis = [
        (_fmt_num(ov["n_transactions"]), "تعداد معاملات"),
        (_fmt_compact_billion_rial(ov["total_value"]), "ارزش کل (میلیارد ریال)"),
        (f"{ov['weighted_avg_price']:.0f}", "میانگین وزنی قیمت"),
        (f"{ov['n_unique_buyers']} / {ov['n_unique_sellers']}", "خریداران / فروشندگان"),
    ]
    card_w = (SLIDE_W - 2 * MARGIN - Inches(0.3) * 3) // 4
    for i, (val, label) in enumerate(kpis):
        x = SLIDE_W - MARGIN - card_w - i * (card_w + Inches(0.3))
        _add_stat_card(s, x, Inches(3.9), card_w, Inches(1.3), val, label)

    # ---------- Slide 3: Price trend ----------
    s = _add_slide(prs)
    _add_page_title(s, "روند قیمت")
    series_data = m.price_series(conn, start, end)
    if len(series_data) >= 2:
        chart_path = str(tmp_dir / "price.png")
        ch.price_trend_chart(series_data, chart_path)
        _add_picture_fit(s, chart_path, MARGIN, Inches(1.3), SLIDE_W - 2 * MARGIN, Inches(5.6))
    price_chg = ((series_data[-1]["weighted_avg_price"] - series_data[0]["weighted_avg_price"])
                 / series_data[0]["weighted_avg_price"] * 100) if len(series_data) >= 2 else 0
    _add_textbox(s, MARGIN, Inches(6.9), SLIDE_W - 2 * MARGIN, Inches(0.4),
                 f"تغییر قیمت در کل بازه: {price_chg:+.1f}٪", size=13, bold=True,
                 color=GOOD_GREEN if price_chg >= 0 else BAD_RED, align=PP_ALIGN.RIGHT)

    # ---------- Slide 4: Period comparison ----------
    s = _add_slide(prs)
    _add_page_title(s, "مقایسه با بازه قبل")
    cmp_res = comp.auto_compare_with_previous(conn, start, end, top_n=top_n)
    if cmp_res.get("deltas"):
        chart_path2 = str(tmp_dir / "cmp.png")
        ch.comparison_bar_chart(cmp_res["deltas"], chart_path2)
        _add_picture_fit(s, chart_path2, MARGIN, Inches(1.25), Inches(7.3), Inches(4.6))
        info_x = MARGIN + Inches(7.6)
        info_w = SLIDE_W - MARGIN - info_x
        _add_bullets(s, info_x, Inches(1.3), info_w, Inches(4.6), cmp_res["narrative"][:5], size=12)
        _add_textbox(s, MARGIN, Inches(6.15),
                     SLIDE_W - 2 * MARGIN, Inches(1.1),
                     f"خریداران تازه‌وارد: {cmp_res['n_new_participants']} نفر   |   "
                     f"خریداران خارج‌شده: {cmp_res['n_exited_participants']} نفر",
                     size=13, bold=True, color=NAVY, align=PP_ALIGN.RIGHT)

    # ---------- Slide 5: Market maker ----------
    s = _add_slide(prs)
    _add_page_title(s, "رفتار بازارگردان")
    mm_summary = mm_mod.market_maker_summary(conn, start, end)
    if mm_summary.get("has_market_maker"):
        chart_path3 = str(tmp_dir / "mm.png")
        ch.market_maker_chart(mm_summary["daily"], chart_path3)
        _add_picture_fit(s, chart_path3, MARGIN, Inches(3.05), SLIDE_W - 2 * MARGIN, Inches(4.1))
        _add_bullets(s, MARGIN, Inches(1.25), SLIDE_W - 2 * MARGIN, Inches(1.75),
                     mm_summary["narrative"][:4], size=12.5)
    else:
        _add_textbox(s, MARGIN, Inches(1.4), SLIDE_W - 2 * MARGIN, Inches(0.6),
                     "بازارگردانی برای این نماد در این بازه شناسایی نشد.", size=14)

    # ---------- Slide 6: Top brokers ----------
    s = _add_slide(prs)
    _add_page_title(s, "کارگزاران برتر خریدار و فروشنده")
    buyers_b = m.top_brokers(conn, "buyer", start, end, top_n=6)
    sellers_b = m.top_brokers(conn, "seller", start, end, top_n=6)
    half_w = (SLIDE_W - 2 * MARGIN - Inches(0.3)) // 2
    _add_textbox(s, SLIDE_W - MARGIN - half_w, Inches(1.25), half_w, Inches(0.35),
                 "خریداران", size=14, bold=True, color=NAVY, align=PP_ALIGN.RIGHT)
    _add_rtl_table(s, SLIDE_W - MARGIN - half_w, Inches(1.65), half_w, Inches(4.8),
                   ["نام کارگزار", "ارزش (ریال)"],
                   [[_truncate(b["broker_name"], 24), _fmt_num(b["value"])] for b in buyers_b],
                   col_widths_ratio=[0.62, 0.38], font_size=11)
    _add_textbox(s, MARGIN, Inches(1.25), half_w, Inches(0.35),
                 "فروشندگان", size=14, bold=True, color=NAVY, align=PP_ALIGN.RIGHT)
    _add_rtl_table(s, MARGIN, Inches(1.65), half_w, Inches(4.8),
                   ["نام کارگزار", "ارزش (ریال)"],
                   [[_truncate(b["broker_name"], 24), _fmt_num(b["value"])] for b in sellers_b],
                   col_widths_ratio=[0.62, 0.38], font_size=11)

    # ---------- Slide 7: Top persons ----------
    s = _add_slide(prs)
    _add_page_title(s, "خریداران و فروشندگان برتر (اشخاص)")
    top_buy_p = m.top_persons(conn, "buyer", start, end, top_n=6)
    top_sell_p = m.top_persons(conn, "seller", start, end, top_n=6)
    _add_textbox(s, SLIDE_W - MARGIN - half_w, Inches(1.25), half_w, Inches(0.35),
                 "خریداران برتر", size=14, bold=True, color=NAVY, align=PP_ALIGN.RIGHT)
    _add_rtl_table(s, SLIDE_W - MARGIN - half_w, Inches(1.65), half_w, Inches(4.8),
                   ["نام", "ارزش (ریال)"],
                   [[_truncate(p["name"], 22), _fmt_num(p["value"])] for p in top_buy_p],
                   col_widths_ratio=[0.62, 0.38], font_size=11)
    _add_textbox(s, MARGIN, Inches(1.25), half_w, Inches(0.35),
                 "فروشندگان برتر", size=14, bold=True, color=NAVY, align=PP_ALIGN.RIGHT)
    _add_rtl_table(s, MARGIN, Inches(1.65), half_w, Inches(4.8),
                   ["نام", "ارزش (ریال)"],
                   [[_truncate(p["name"], 22), _fmt_num(p["value"])] for p in top_sell_p],
                   col_widths_ratio=[0.62, 0.38], font_size=11)

    # ---------- Slide 8: HHI / Concentration ----------
    s = _add_slide(prs)
    _add_page_title(s, "تمرکز معاملات (شاخص HHI)")
    hhi = ext.hhi_summary(conn, start, end)
    _add_bullets(s, MARGIN, Inches(1.3), SLIDE_W - 2 * MARGIN, Inches(1.6), hhi["narrative"], size=14)
    stat_w = (SLIDE_W - 2 * MARGIN - Inches(0.3) * 2) // 3
    stats = [
        (f"{hhi['buy']['hhi']:.0f}", "HHI خریداران"),
        (f"{hhi['buy']['top10_share_pct']:.1f}٪", "سهم ۱۰ خریدار برتر"),
        (concentration_level_fa(hhi['buy']['level']), "سطح تمرکز خرید"),
    ]
    for i, (val, label) in enumerate(stats):
        x = SLIDE_W - MARGIN - stat_w - i * (stat_w + Inches(0.3))
        _add_stat_card(s, x, Inches(3.4), stat_w, Inches(1.5), val, label)

    # ---------- Slide 9: Short-term behavior ----------
    s = _add_slide(prs)
    _add_page_title(s, "الگوهای رفتاری کوتاه‌مدت")
    st = bh.top_short_term_traders(conn, start, end, top_n=8)
    _add_rtl_table(s, MARGIN, Inches(1.3), SLIDE_W - 2 * MARGIN, Inches(4.3),
                   ["نام", "امتیاز", "سطح", "تعداد رفت‌وبرگشت"],
                   [[_truncate(t["name"], 24), f"{t['score']:.0f}", t["level"], str(t["n_round_trips"])] for t in st],
                   col_widths_ratio=[0.42, 0.13, 0.32, 0.13], font_size=12)
    _add_textbox(s, MARGIN, Inches(5.85), SLIDE_W - 2 * MARGIN, Inches(0.5),
                 "این امتیاز شاخصی آماری از الگوی معاملات مشاهده‌شده است، نه اثبات قصد یا استراتژی واقعی شخص.",
                 size=10.5, color=TEXT_MUTED, align=PP_ALIGN.RIGHT)

    # ---------- Slide 10: Anomalies ----------
    s = _add_slide(prs)
    _add_page_title(s, "هشدارهای معاملاتی")
    alerts = an.top_alerts_diversified(conn, start, end, top_n=8)
    _add_rtl_table(s, MARGIN, Inches(1.3), SLIDE_W - 2 * MARGIN, Inches(4.5),
                   ["نوع", "شدت", "امتیاز ریسک", "تاریخ"],
                   [[alert_type_fa(a["alert_type"]), severity_fa(a["severity"]), f"{a['risk_score']:.0f}",
                     jalali_date_display(a.get("trade_date", ""))] for a in alerts],
                   col_widths_ratio=[0.32, 0.22, 0.2, 0.26], font_size=12)

    # ---------- Slide 11: Fundamental analysis (honest limitation) ----------
    s = _add_slide(prs)
    _add_page_title(s, "تحلیل بنیادی")
    fund = ext.fundamental_analysis_note(conn)
    _add_bullets(s, MARGIN, Inches(1.3), SLIDE_W - 2 * MARGIN, Inches(1.9), fund["narrative"], size=14)
    _add_textbox(s, MARGIN, Inches(3.3), SLIDE_W - 2 * MARGIN, Inches(0.4),
                 "داده‌های مالی لازم برای تکمیل این بخش:", size=14, bold=True, color=NAVY, align=PP_ALIGN.RIGHT)
    _add_bullets(s, MARGIN, Inches(3.8), SLIDE_W - 2 * MARGIN, Inches(2.8), fund["required_data"], size=13)

    # ---------- Slide 12: Qualitative analysis ----------
    s = _add_slide(prs)
    _add_page_title(s, "تحلیل کیفی (رفتار بازار)")
    qual = ext.qualitative_market_behavior(conn, start, end)
    _add_bullets(s, MARGIN, Inches(1.3), SLIDE_W - 2 * MARGIN, Inches(2.6), qual["narrative"], size=14)
    stat_w2 = (SLIDE_W - 2 * MARGIN - Inches(0.3)) // 2
    _add_stat_card(s, SLIDE_W - MARGIN - stat_w2, Inches(4.2), stat_w2, Inches(1.4),
                   f"{qual['institutional_share_pct']:.1f}٪", "سهم خرید حقوقی")
    _add_stat_card(s, MARGIN, Inches(4.2), stat_w2, Inches(1.4),
                   f"{qual['individual_share_pct']:.1f}٪", "سهم خرید حقیقی")

    # ---------- Slide 13: Valuation methods ----------
    s = _add_slide(prs)
    _add_page_title(s, "روش‌های ارزش‌گذاری")
    val = ext.valuation_methods_overview(conn, start, end)
    _add_rtl_table(s, MARGIN, Inches(1.3), SLIDE_W - 2 * MARGIN, Inches(2.6),
                   ["روش", "داده مورد نیاز"],
                   [[me["name"], me["needs"]] for me in val["methods"]],
                   col_widths_ratio=[0.38, 0.62], font_size=12)
    _add_bullets(s, MARGIN, Inches(4.15), SLIDE_W - 2 * MARGIN, Inches(2.4), val["narrative"], size=12.5)

    # ---------- Slide 14: Registry / FIFO + methodology ----------
    s = _add_slide(prs)
    _add_page_title(s, "رجیستری، مالکیت و FIFO")
    fifo = pf.run_fifo(conn)
    fs = fifo["summary"]
    _add_bullets(s, MARGIN, Inches(1.25), SLIDE_W - 2 * MARGIN, Inches(2.6), [
        f"افراد تحلیل‌شده: {fs['people']:,} نفر؛ منطبق با رجیستری: {fs['registry_matched']:,} نفر.",
        f"موارد بالقوه تازه‌وارد: {fs['potential_new_entrants']:,} نفر؛ این عدد ورود قطعی را اثبات نمی‌کند.",
        f"تطبیق کامل پایان دوره: {fs['reconciled']:,} نفر؛ دارای اختلاف: {fs['mismatched']:,} نفر.",
        f"سود تحقق‌یافته با بهای معلوم: {fs['known_realized_pnl']:,.0f} ریال.",
        f"فروش از موجودی با بهای نامعلوم: {fs['unknown_cost_sold_qty']:,} سهم.",
    ], size=12.5)
    _add_textbox(s, MARGIN, Inches(4.1), SLIDE_W - 2 * MARGIN, Inches(1.2),
                 "موجودی اول دوره به‌عنوان Lot با بهای تمام‌شده نامعلوم وارد شده است؛ بنابراین سود/زیان این بخش عددسازی نمی‌شود.",
                 size=12, color=TEXT_MUTED, align=PP_ALIGN.RIGHT)
    _add_textbox(s, MARGIN, Inches(5.7), SLIDE_W - 2 * MARGIN, Inches(0.5),
                 "تطبیق پایان دوره فقط در صورت هم‌زمان و هم‌دامنه بودن رجیستری و فایل معاملات قابل تفسیر است.",
                 size=10.5, color=TEXT_MUTED, align=PP_ALIGN.RIGHT)

    # ---------- Slide 15: Methodology & limitations ----------
    s = _add_slide(prs)
    _add_page_title(s, "روش‌شناسی و محدودیت‌های داده")
    method_lines = [
        "میانگین وزنی قیمت: مجموع (تعداد × قیمت) تقسیم بر مجموع تعداد.",
        "شاخص HHI: مجموع مجذور سهم هر شخص از ارزش خرید (مقیاس ۰ تا ۱۰,۰۰۰).",
        "تشخیص ناهنجاری: بر پایه Z-score و IQR نسبت به میانگین/میانه.",
        "تحلیل بازارگردان: هم‌زمانی آماری با تغییر قیمت را می‌سنجد؛ رابطه علّی را اثبات نمی‌کند.",
        "هویت اشخاص بدون کد ملی صرفاً بر اساس نام (با اطمینان پایین) شناسایی شده است.",
        "این گزارش شاخص‌های آماری از داده معاملات ارائه می‌دهد و جایگزین تحلیل مالی/حقوقی کامل نیست.",
    ]
    _add_bullets(s, MARGIN, Inches(1.3), SLIDE_W - 2 * MARGIN, Inches(4.8), method_lines, size=14, space_after=14)

    # ---------- Slide 16: Closing (dark) ----------
    s = _add_slide(prs, bg=NAVY)
    _add_textbox(s, Inches(1), Inches(3.1), SLIDE_W - Inches(2), Inches(1),
                 "پرسش و پاسخ", size=34, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    _add_textbox(s, Inches(1), Inches(4.0), SLIDE_W - Inches(2), Inches(0.6),
                 "Smart Equity Transaction Intelligence", size=13, color=ICE_BLUE, align=PP_ALIGN.CENTER)

    out_dir = pathlib.Path(out_path).parent
    out_dir.mkdir(parents=True, exist_ok=True)
    prs.save(out_path)
    for f in tmp_dir.glob("*"):
        try:
            f.unlink()
        except OSError:
            pass
    try:
        tmp_dir.rmdir()
    except OSError:
        pass
    return out_path


if __name__ == "__main__":
    db_path = str(pathlib.Path(__file__).resolve().parents[2] / "data" / "smart_equity.db")
    conn = sqlite3.connect(db_path)
    out = generate_pptx_report(conn, str(pathlib.Path(__file__).resolve().parents[2] / "exports" / "gozaresh_hiat_modire.pptx"))
    print("Saved:", out)
