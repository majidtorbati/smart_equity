"""
PDF Executive Report ، گزارش حرفه‌ای هیئت‌مدیره.
شامل: خلاصه مدیریتی روایی، نمودار قیمت، تحلیل بازارگردان، مقایسه با بازه قبل،
جداول کارگزاران/اشخاص برتر، تمرکز، رفتار کوتاه‌مدت، هشدارها، روش‌شناسی و محدودیت‌های داده.
همه تاریخ‌ها شمسی نمایش داده می‌شوند (ذخیره‌سازی داخلی همچنان میلادی است).
"""
from __future__ import annotations
import re
import sqlite3
import sys
import pathlib
import datetime as dt
import tempfile
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from app.analytics import metrics as m
from app.analytics import market_maker as mm_mod
from app.analytics import comparison as comp
from app.analytics import insights as ins
from app.analytics import extended_analysis as ext
from app.analytics import portfolio as pf
from app.analytics import new_shareholders as ns
from app.detection import anomaly as an
from app.detection import behavior as bh
from app.core.labels import alert_type_fa, severity_fa, concentration_level_fa
from app.core.jalali import jalali_date_display, gregorian_to_jalali
from app.core.normalize import clean_display
from app.core.farsi_text import fa
from app.core.runtime import resource_root
from app.reports import charts as ch
from app.config.settings import (get_company_name, get_report_prepared_by, get_report_audience,
                                  get_report_title, get_logo_path, DEVELOPER_CREDIT_LINE)

ASSETS_DIR = resource_root() / "assets"
FONT_REGULAR = str(ASSETS_DIR / "BNazanin.ttf")
FONT_BOLD = str(ASSETS_DIR / "BTitrBd.ttf")
FONT_LATIN = str(ASSETS_DIR / "Vazirmatn-Regular.ttf")
FONT_LATIN_BOLD = str(ASSETS_DIR / "Vazirmatn-Bold.ttf")

pdfmetrics.registerFont(TTFont("BNazanin", FONT_REGULAR))
pdfmetrics.registerFont(TTFont("BTitr", FONT_BOLD))
pdfmetrics.registerFont(TTFont("Vazirmatn", FONT_LATIN))
pdfmetrics.registerFont(TTFont("VazirmatnBold", FONT_LATIN_BOLD))

COLOR_PRIMARY = colors.HexColor("#1F4E78")
COLOR_MUTED = colors.HexColor("#6B7280")


class RTLReport:
    def __init__(self, path, page_size=A4):
        self.path = path
        self.page_w, self.page_h = page_size
        self.c = canvas.Canvas(path, pagesize=page_size)
        self.margin = 18 * mm
        self.y = self.page_h - self.margin
        self.line_height = 6.5 * mm
        self._cur_font = ("BNazanin", 10)
        self._tmp_files = []

    def _mixed_runs(self, text, primary_font):
        """
        ??? ????? ? ????? ?? ?? ?? bidi/reshape ?? ?? ???? ???? ??? ??????.
        ??? ??? ?? ????? ???? BNazanin/BTitr ?? Vazirmatn ?? ?? ?? ??????? ??????.
        """
        text = str(text).replace(chr(0x200C), '')
        visual = fa(text)

        font_name = "VazirmatnBold" if primary_font == "BTitr" else "Vazirmatn"
        pattern = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/%+\-()]*")

        return [(visual, font_name)]

    def _mixed_width(self, text, size, primary_font):
        return sum(
            self.c.stringWidth(part, font_name, size)
            for part, font_name in self._mixed_runs(text, primary_font)
        )

    def _draw_mixed_right(self, text, right_x, y, size, primary_font, color=None):
        text = str(text)
        visual = fa(text)

        if color is not None:
            self.c.setFillColor(color)

        font_name = "VazirmatnBold" if primary_font == "BTitr" else "Vazirmatn"

        width = self.c.stringWidth(visual, font_name, size)
        self.c.setFont(font_name, size)
        self.c.drawString(right_x - width, y, visual)

        if color is not None:
            self.c.setFillColor(colors.black)

    def _set_font(self, name, size):
        self._cur_font = (name, size)
        self.c.setFont(name, size)

    def _draw_footer(self):
        page_num = self.c.getPageNumber()
        prev_font = self._cur_font
        self.c.setFont("BNazanin", 8)
        self.c.setFillColor(COLOR_MUTED)
        self.c.drawCentredString(self.page_w / 2, 10 * mm, fa(f"صفحه {page_num}"))

        self.c.setFillColor(colors.black)
        self.c.setFont(*prev_font)

    def _new_page(self):
        self._draw_footer()
        self.c.showPage()
        self.y = self.page_h - self.margin
        self.c.setFont(*self._cur_font)
        self.c.setFillColor(colors.black)

    def _check_page_break(self, needed=1):
        if self.y - needed * self.line_height < self.margin + 8 * mm:
            self._new_page()

    def _ensure_space_mm(self, height_mm_val):
        if self.y - height_mm_val * mm < self.margin + 8 * mm:
            self._new_page()

    def title(self, text, size=17):
        self._check_page_break(2)
        self._set_font("BTitr", size)
        self._draw_mixed_right(
            text,
            self.page_w - self.margin,
            self.y,
            size,
            "BTitr",
            COLOR_PRIMARY,
        )
        self.c.setFillColor(colors.black)
        self.y -= size / 2 * mm + 5 * mm

    def heading(self, text, size=13):
        self._check_page_break(3)
        self.y -= 2 * mm
        self._set_font("BTitr", size)
        self._draw_mixed_right(
            text,
            self.page_w - self.margin,
            self.y,
            size,
            "BTitr",
            COLOR_PRIMARY,
        )
        self.c.setLineWidth(0.6)
        self.c.setStrokeColor(COLOR_PRIMARY)
        self.c.line(self.margin, self.y - 2 * mm, self.page_w - self.margin, self.y - 2 * mm)
        self.c.setFillColor(colors.black)
        self.y -= self.line_height + 2 * mm

    def sub_heading(self, text, size=10.5):
        self._check_page_break(2)
        self._set_font("BTitr", size)
        self._draw_mixed_right(
            text,
            self.page_w - self.margin,
            self.y,
            size,
            "BTitr",
            colors.HexColor("#374151"),
        )
        self.c.setFillColor(colors.black)
        self.y -= self.line_height

    def paragraph(self, text, size=10):
        self._check_page_break(1)
        self._draw_mixed_right(
            text,
            self.page_w - self.margin,
            self.y,
            size,
            "BNazanin",
        )
        self.y -= self.line_height

    def wrapped_paragraph(self, text, size=10, bold=False, color=None, bullet=False):
        """پاراگراف روایی چندخطی با شکست خط خودکار و پشتیبانی از فونت لاتین."""
        font_name = "BTitr" if bold else "BNazanin"
        prefix = "- " if bullet else ""
        text = prefix + text
        max_width = self.page_w - 2 * self.margin
        words = text.split(" ")
        lines, line_words = [], []

        for w in words:
            candidate = line_words + [w]
            candidate_text = " ".join(candidate)
            width = self._mixed_width(candidate_text, size, font_name)

            if width <= max_width or not line_words:
                line_words = candidate
            else:
                lines.append(" ".join(line_words))
                line_words = [w]

        if line_words:
            lines.append(" ".join(line_words))

        for line in lines:
            self._check_page_break(1)
            self._draw_mixed_right(
                line,
                self.page_w - self.margin,
                self.y,
                size,
                font_name,
                color,
            )
            self.y -= self.line_height

    def kv_row(self, label, value, size=10):
        self._check_page_break(1)
        self._draw_mixed_right(
            f"{label}: {value}",
            self.page_w - self.margin,
            self.y,
            size,
            "BNazanin",
        )
        self.y -= self.line_height

    def table(self, headers: list[str], rows: list[list], col_widths=None, size=9):
        n_cols = len(headers)
        if col_widths is None:
            usable = self.page_w - 2 * self.margin
            col_widths = [usable / n_cols] * n_cols
        self._check_page_break(2)
        self._set_font("BTitr", size)
        self.c.setFillColor(COLOR_PRIMARY)
        self.c.rect(self.margin, self.y - 2 * mm, self.page_w - 2 * self.margin, self.line_height, fill=1, stroke=0)
        self.c.setFillColor(colors.white)
        cx = self.page_w - self.margin
        for h, w in zip(headers, col_widths):
            self._draw_mixed_right(
                h,
                cx - 2,
                self.y,
                size,
                "BTitr",
            )
            cx -= w
        self.c.setFillColor(colors.black)
        self.y -= self.line_height + 1 * mm
        self._set_font("BNazanin", size)
        for i, row in enumerate(rows):
            self._check_page_break(1)
            if i % 2 == 1:
                self.c.setFillColor(colors.HexColor("#F4F6F8"))
                self.c.rect(self.margin, self.y - 1.5 * mm, self.page_w - 2 * self.margin, self.line_height, fill=1, stroke=0)
                self.c.setFillColor(colors.black)
            cx = self.page_w - self.margin
            for val, w in zip(row, col_widths):
                self._draw_mixed_right(
                    val,
                    cx - 2,
                    self.y,
                    size,
                    "BNazanin",
                )
                cx -= w
            self.y -= self.line_height

    def image(self, path, width_mm=170, height_mm=62):
        self._ensure_space_mm(height_mm + 4)
        x = (self.page_w - width_mm * mm) / 2
        y = self.y - height_mm * mm
        self.c.drawImage(path, x, y, width=width_mm * mm, height=height_mm * mm,
                          preserveAspectRatio=True, anchor="c", mask="auto")
        self.y = y - 4 * mm

    def logo(self, path, max_w_mm=28, max_h_mm=20):
        """
        لوگو را در گوشه بالا-چپ صفحه جاری رسم می‌کند (موقعیت مطلق، مستقل از جریان متن —
        فقط روی صفحه اول/جلد فراخوانی می‌شود، پس نیازی به جابه‌جایی self.y نیست).
        """
        from app.core.image_utils import fit_dimensions
        w_mm, h_mm = fit_dimensions(path, max_w_mm, max_h_mm)
        x = self.margin
        y = self.page_h - self.margin - h_mm * mm
        self.c.drawImage(path, x, y, width=w_mm * mm, height=h_mm * mm, preserveAspectRatio=True, mask="auto")

    def spacer(self, mm_amount=4):
        self.y -= mm_amount * mm

    def save(self):
        self._draw_footer()
        self.c.save()
        for f in self._tmp_files:
            try:
                pathlib.Path(f).unlink()
            except OSError:
                pass


def _fmt_num(x):
    try:
        return f"{x:,.0f}"
    except Exception:
        return str(x)


def _level_fa(level: str) -> str:
    return {"Low concentration": "تمرکز پایین", "Medium concentration": "تمرکز متوسط",
            "High concentration": "تمرکز بالا"}.get(level, level)


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
    return f"{jy:04d}/{jm:02d}/{jd:02d} {now.strftime('%H:%M')}"


def generate_pdf_report(conn: sqlite3.Connection, out_path: str, start=None, end=None, top_n=10) -> str:
    r = RTLReport(out_path)
    tmp_dir = pathlib.Path(tempfile.mkdtemp(prefix="smarteq_charts_"))

    ov = m.overview(conn, start, end)
    period_start_fa = jalali_date_display(start) if start else jalali_date_display(ov["first_date"])
    period_end_fa = jalali_date_display(end) if end else jalali_date_display(ov["last_date"])

    # ---------- 1. Cover ----------
    logo_path = get_logo_path()
    if logo_path:
        r.logo(str(logo_path))

    r.title(get_report_title())

    company_name = get_company_name()
    if company_name:
        r.paragraph(f"شرکت: {company_name}")

    r.paragraph(f"نماد: {_symbol_label(conn)}")
    r.paragraph(f"بازه گزارش: از {period_start_fa} تا {period_end_fa}")
    r.paragraph(
        f"تهیه‌کننده: {get_report_prepared_by()}   ،   ارائه به: {get_report_audience()}"
    )
    r.paragraph(f"تاریخ تهیه گزارش: {_now_jalali_str()}")
    r.spacer(3)
    r.wrapped_paragraph(DEVELOPER_CREDIT_LINE, size=8, color=COLOR_MUTED)
    r.spacer(6)

    # ---------- 2. Executive summary ----------
    r.heading("۱. خلاصه مدیریتی")

    for line in ins.executive_summary_narrative(conn, start, end):
        r.wrapped_paragraph(line, bullet=True)

    r.spacer(3)
    r.kv_row("تعداد معاملات", _fmt_num(ov["n_transactions"]))
    r.kv_row("ارزش کل معاملات (ریال)", _fmt_num(ov["total_value"]))
    r.kv_row("حجم کل معاملات", _fmt_num(ov["total_quantity"]))
    r.kv_row("میانگین وزنی قیمت", f"{ov['weighted_avg_price']:.1f}")
    r.kv_row(
        "تعداد خریداران / فروشندگان منحصر‌به‌فرد",
        f"{ov['n_unique_buyers']} / {ov['n_unique_sellers']}"
    )
    r.spacer(4)

    # ---------- 3. Trading trends ----------
    r.heading("۲. روند معاملات")

    series_data = m.price_series(conn, start, end)

    if len(series_data) >= 2:
        chart_path = str(tmp_dir / "price.png")
        ch.price_trend_chart(series_data, chart_path)
        r._tmp_files.append(chart_path)
        r.image(chart_path)
    else:
        r.paragraph("داده کافی برای رسم روند قیمت در این بازه وجود ندارد.")

    r.spacer(3)

    # ---------- 4. Previous-period comparison ----------
    r.heading("۳. مقایسه با بازه قبل")

    cmp_res = comp.auto_compare_with_previous(
        conn, start, end, top_n=top_n
    )

    r.wrapped_paragraph(
        f"بازه فعلی: از {cmp_res['period_b']['start_fa']} تا "
        f"{cmp_res['period_b']['end_fa']}؛ "
        f"بازه مقایسه‌ای: از {cmp_res['period_a']['start_fa']} تا "
        f"{cmp_res['period_a']['end_fa']}."
    )

    for line in cmp_res["narrative"]:
        r.wrapped_paragraph(line, bullet=True)

    if cmp_res.get("deltas"):
        chart_path = str(tmp_dir / "comparison.png")
        ch.comparison_bar_chart(cmp_res["deltas"], chart_path)
        r._tmp_files.append(chart_path)
        r.image(chart_path, height_mm=55)

    r.spacer(4)

    # ---------- 5. Top brokers ----------
    r.heading("۴. کارگزاران برتر خریدار")

    buyers_b = m.top_brokers(
        conn, "buyer", start, end, top_n=top_n
    )

    r.table(
        ["نام کارگزار", "ارزش (ریال)", "تعداد معاملات"],
        [
            [
                b["broker_name"],
                _fmt_num(b["value"]),
                str(b["n_transactions"])
            ]
            for b in buyers_b
        ],
        col_widths=[95 * mm, 55 * mm, 30 * mm]
    )

    r.spacer(4)

    r.heading("۵. کارگزاران برتر فروشنده")

    sellers_b = m.top_brokers(
        conn, "seller", start, end, top_n=top_n
    )

    r.table(
        ["نام کارگزار", "ارزش (ریال)", "تعداد معاملات"],
        [
            [
                b["broker_name"],
                _fmt_num(b["value"]),
                str(b["n_transactions"])
            ]
            for b in sellers_b
        ],
        col_widths=[95 * mm, 55 * mm, 30 * mm]
    )

    r.spacer(4)

    # ---------- 6. Top buyers / sellers ----------
    r.heading("۶. خریداران برتر")

    top_buy_p = m.top_persons(
        conn, "buyer", start, end, top_n=top_n
    )

    r.table(
        ["نام", "کد سجام", "ارزش (ریال)"],
        [
            [
                p["name"],
                p["sejam_code"],
                _fmt_num(p["value"])
            ]
            for p in top_buy_p
        ],
        col_widths=[80 * mm, 45 * mm, 55 * mm]
    )

    r.spacer(4)

    r.heading("۷. فروشندگان برتر")

    top_sell_p = m.top_persons(
        conn, "seller", start, end, top_n=top_n
    )

    r.table(
        ["نام", "کد سجام", "ارزش (ریال)"],
        [
            [
                p["name"],
                p["sejam_code"],
                _fmt_num(p["value"])
            ]
            for p in top_sell_p
        ],
        col_widths=[80 * mm, 45 * mm, 55 * mm]
    )

    r.spacer(4)

    # ---------- 7. New shareholders ----------
    r.heading("۸. سهامداران جدید")

    new_rows = ns.find_new_shareholders(conn, end)

    r.wrapped_paragraph(
        f"در تاریخ {period_end_fa} تعداد "
        f"{_fmt_num(len(new_rows))} سهامدار جدید واقعی شناسایی شد."
    )

    if new_rows:
        table_rows = []

        for item in new_rows[:top_n]:
            min_price = item["min_buy_price"]
            max_price = item["max_buy_price"]

            if min_price == max_price:
                price_text = _fmt_num(min_price)
            else:
                price_text = (
                    f"{_fmt_num(min_price)} تا {_fmt_num(max_price)}"
                )

            table_rows.append([
                item["name"],
                item["person_type"],
                item["sejam_code"],
                _fmt_num(item["buy_quantity"]),
                _fmt_num(item["buy_value"]),
                price_text,
            ])

        r.table(
            [
                "نام",
                "نوع",
                "کد سجام",
                "حجم خرید",
                "ارزش خرید (ریال)",
                "بازه قیمت خرید"
            ],
            table_rows,
            col_widths=[
                48 * mm,
                25 * mm,
                32 * mm,
                28 * mm,
                38 * mm,
                29 * mm
            ],
            size=7.5
        )
    else:
        r.paragraph(
            "در تاریخ انتخاب‌شده سهامدار جدید واقعی شناسایی نشد."
        )

    r.spacer(4)

    # ---------- 8. Concentration / HHI ----------
    r.heading("۹. تمرکز معاملات (شاخص HHI)")

    hhi = ext.hhi_summary(conn, start, end)

    for line in hhi["narrative"]:
        r.wrapped_paragraph(line, bullet=True)

    r.spacer(4)

    # ---------- 9. Trading behavior ----------
    r.heading("۱۰. رفتار معاملاتی")

    st = bh.top_short_term_traders(
        conn, start, end, top_n=top_n
    )

    if st:
        r.wrapped_paragraph(
            "امتیاز رفتار کوتاه‌مدت یک شاخص آماری است و به‌تنهایی نشان‌دهنده قصد یا استراتژی معاملاتی نیست.",
            size=9,
            color=COLOR_MUTED
        )

        r.table(
            ["نام", "امتیاز", "سطح", "تعداد رفت‌وبرگشت"],
            [
                [
                    t["name"],
                    f"{t['score']:.0f}",
                    t["level"],
                    str(t["n_round_trips"])
                ]
                for t in st
            ],
            col_widths=[65 * mm, 25 * mm, 65 * mm, 25 * mm]
        )
    else:
        r.paragraph(
            "در این بازه الگوی قابل‌توجهی از معاملات کوتاه‌مدت شناسایی نشد."
        )

    r.spacer(3)

    r.sub_heading("خرید و فروش هم‌روز")

    r.wrapped_paragraph(
        bh.DISCLAIMER_SAME_DAY,
        size=9
    )

    same_day = bh.same_day_buy_sell_pairs(
        conn, start, end, top_n=top_n
    )

    if same_day:
        def _fmt_qty_price(qty, price):
            return f"{qty:,.0f} × {price:,.0f}"

        def _verdict_short(item):
            ratio = item["overlap_ratio"]
            if ratio >= 0.8:
                tag = "کامل"
            elif ratio >= 0.3:
                tag = "محتمل"
            else:
                tag = "کم"

            return f"{tag} ({ratio:.0f} درصد)"

        r.table(
            [
                "نام",
                "تاریخ",
                "خرید (تعداد × نرخ)",
                "فروش (تعداد × نرخ)",
                "هم‌پوشانی"
            ],
            [
                [
                    p["name"],
                    jalali_date_display(p["date"]),
                    _fmt_qty_price(
                        p["buy_qty"], p["buy_price"]
                    ),
                    _fmt_qty_price(
                        p["sell_qty"], p["sell_price"]
                    ),
                    _verdict_short(p)
                ]
                for p in same_day
            ],
            col_widths=[
                35 * mm,
                22 * mm,
                40 * mm,
                40 * mm,
                37 * mm
            ],
            size=8.5
        )
    else:
        r.paragraph(
            "در این بازه، شخصی با خرید و فروش همان نماد در یک روز "
            "به‌عنوان الگوی قابل‌توجه شناسایی نشد."
        )

    r.spacer(4)

    # ---------- 10. Market maker - only when present ----------
    mm_summary = mm_mod.market_maker_summary(
        conn, start, end
    )

    if mm_summary.get("has_market_maker"):
        r.heading("۱۱. رفتار بازارگردان")

        for line in mm_summary["narrative"]:
            r.wrapped_paragraph(line, bullet=True)

        chart_path = str(tmp_dir / "market_maker.png")
        ch.market_maker_chart(
            mm_summary["daily"],
            chart_path
        )
        r._tmp_files.append(chart_path)
        r.image(chart_path, height_mm=62)

        r.spacer(4)

    # ---------- 11. Alerts / anomalies ----------
    r.heading("۱۲. هشدارهای معاملاتی")

    r.wrapped_paragraph(
        "امتیاز ریسک یک شاخص آماری برای شناسایی معاملات یا الگوهای "
        "غیرعادی نسبت به سابقه همان بازه است و به‌تنهایی اثبات تخلف "
        "یا دستکاری بازار نیست.",
        size=9
    )

    r.wrapped_paragraph(
        "یک معامله ممکن است توسط بیش از یک آشکارساز علامت‌گذاری شود؛ بنابراین تعداد هشدارها الزاماً معادل تعداد رویدادهای مستقل نیست.",
        size=9,
        color=COLOR_MUTED
    )

    alerts = an.top_alerts_diversified(
        conn, start, end, top_n=top_n
    )

    if alerts:
        for i, alert in enumerate(alerts, 1):
            r._check_page_break(4)

            header = (
                f"{i}. {alert_type_fa(alert['alert_type'])} ، "
                f"شدت: {severity_fa(alert['severity'])} ، "
                f"امتیاز: {alert['risk_score']:.0f} ، "
                f"تاریخ: "
                f"{jalali_date_display(alert.get('trade_date', ''))}"
            )

            if alert.get("value"):
                header += (
                    f" ، ارزش: {alert['value']:,.0f} ریال"
                )

            r.wrapped_paragraph(
                header,
                bold=True,
                size=9.5
            )

            if (
                alert.get("buyer_name")
                or alert.get("seller_name")
            ):
                r.wrapped_paragraph(
                    f"طرف معامله ، خریدار: "
                    f"{alert.get('buyer_name') or '—'} | "
                    f"فروشنده: "
                    f"{alert.get('seller_name') or '—'}",
                    size=9
                )

            r.wrapped_paragraph(
                alert["reason"],
                size=9,
                color=COLOR_MUTED
            )

            r.spacer(1.5)
    else:
        r.paragraph(
            "در این بازه هشدار معاملاتی قابل‌توجهی در فهرست خروجی "
            "شناسایی نشد."
        )

    r.spacer(4)

    # ---------- 12. Management conclusion ----------
    r.heading("۱۳. جمع‌بندی مدیریتی")

    summary_lines = ins.executive_summary_narrative(
        conn, start, end
    )

    for line in summary_lines:
        r.wrapped_paragraph(line, bullet=True)

    r.wrapped_paragraph(
        "این گزارش صرفاً بر مبنای داده‌های معاملات و شاخص‌های "
        "تحلیلی موجود در سامانه تهیه شده است. تصمیم‌گیری مدیریتی "
        "باید در کنار اطلاعات مالی، عملیاتی، افشای اطلاعات و سایر "
        "اطلاعات رسمی شرکت انجام شود.",
        size=9,
        color=COLOR_MUTED
    )

    r.spacer(4)

    # ---------- 13. Methodology and limitations ----------
    r.heading("۱۴. روش‌شناسی و محدودیت‌های داده")

    methodology = [
        "مقایسه با بازه قبل بر اساس بازه‌های تقویمی هم‌طول انجام می‌شود؛ بنابراین تعداد روزهای معاملاتی دو بازه لزوماً یکسان نیست.",
        "میانگین وزنی قیمت بر اساس مجموع حاصل‌ضرب تعداد در قیمت "
        "تقسیم بر مجموع تعداد محاسبه می‌شود.",
        "شاخص تمرکز HHI بر اساس سهم ارزش معاملات اشخاص محاسبه می‌شود.",
        "تشخیص ناهنجاری‌ها بر اساس شاخص‌های آماری و مقایسه با "
        "الگوی معاملات همان بازه انجام می‌شود.",
        "امتیاز رفتار کوتاه‌مدت یک شاخص آماری است و به‌تنهایی "
        "اثبات قصد یا تخلف معاملاتی نیست.",
        "تشخیص سهامداران جدید با استفاده از خرید روز انتخاب‌شده، "
        "سابقه معاملات قبلی و سابقه رجیستری انجام می‌شود؛ "
        "خرید مجدد پس از فروش کامل، سهامدار جدید محسوب نمی‌شود.",
        "تحلیل هویت اشخاص در صورت نبود شناسه کامل می‌تواند محدودیت "
        "داشته باشد و نتایج باید با اطلاعات رسمی تطبیق داده شود.",
        "این گزارش جایگزین بررسی‌های قانونی، نظارتی، مالی یا "
        "حسابرسی شرکت نیست."
    ]

    for line in methodology:
        r.wrapped_paragraph(
            line,
            bullet=True,
            size=9
        )

    r.spacer(2)

    for line in [
        "تشخیص رفتار کوتاه‌مدت بر مبنای روز معاملاتی است، نه ساعت دقیق سفارش.",
        "هم‌بستگی آماری میان فعالیت بازارگردان و تغییر قیمت به‌معنای رابطه علّی نیست.",
        "تحلیل بنیادی و ارزش‌گذاری در این گزارش انجام نشده است، زیرا داده‌های مالی لازم در مجموعه داده معاملات موجود نیست.",
    ]:
        r.wrapped_paragraph(
            line,
            bullet=True,
            size=9,
            color=COLOR_MUTED
        )

    r.save()

    try:
        tmp_dir.rmdir()
    except OSError:
        pass

    return out_path


if __name__ == "__main__":
    db_path = str(pathlib.Path(__file__).resolve().parents[2] / "data" / "smart_equity.db")
    conn = sqlite3.connect(db_path)
    out = generate_pdf_report(conn, str(pathlib.Path(__file__).resolve().parents[2] / "exports" / "gozaresh_hiat_modire.pdf"))
    print("Saved:", out)
