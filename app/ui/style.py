"""تنظیمات ظاهری مشترک اپلیکیشن SmartEquity."""

from app.core.runtime import resource_root


ASSETS_DIR = resource_root() / "assets"
FONT_PATH = str(ASSETS_DIR / "Vazirmatn-Regular.ttf")


# ---------------------------------------------------------
# Corporate financial dashboard palette
# ---------------------------------------------------------

COLOR_PRIMARY = "#1F4E78"
COLOR_PRIMARY_DARK = "#163A57"
COLOR_PRIMARY_LIGHT = "#EAF2F8"

COLOR_BG = "#F3F6F9"
COLOR_CARD = "#FFFFFF"

COLOR_TEXT = "#17202A"
COLOR_MUTED = "#667085"
COLOR_BORDER = "#D9E2EC"
COLOR_BORDER_LIGHT = "#E7EDF3"

COLOR_GOOD = "#1E7E34"
COLOR_GOOD_BG = "#EAF6EE"

COLOR_BAD = "#B02A2A"
COLOR_BAD_BG = "#FCECEC"

COLOR_WARN = "#9A6700"
COLOR_WARN_BG = "#FFF7DF"


# ---------------------------------------------------------
# Global application style
# ---------------------------------------------------------

APP_STYLESHEET = f"""
/* ========================================================
   GLOBAL
   ======================================================== */

* {{
    font-family: "Vazirmatn";
    font-size: 13px;
    color: {COLOR_TEXT};
}}

QMainWindow,
QWidget#centralWidget {{
    background-color: {COLOR_BG};
}}


/* ========================================================
   SIDEBAR
   ======================================================== */

QListWidget#sidebar {{
    background-color: {COLOR_PRIMARY_DARK};
    color: white;
    border: none;
    padding-top: 14px;
    padding-bottom: 14px;
    outline: 0;
}}

QListWidget#sidebar::item {{
    padding: 13px 18px;
    margin: 2px 8px;
    color: #E8EEF3;
    border-radius: 6px;
}}

QListWidget#sidebar::item:hover {{
    background-color: #214D70;
    color: white;
}}

QListWidget#sidebar::item:selected {{
    background-color: {COLOR_PRIMARY};
    color: white;
    border-right: 4px solid #63B3ED;
    padding-right: 14px;
}}


/* ========================================================
   PAGE HEADER
   ======================================================== */

QLabel#dashboardPageTitle {{
    font-size: 22px;
    font-weight: bold;
    color: #FFFFFF;
    padding: 8px 0px 2px 0px;
}}

QLabel#dashboardPageSubtitle {{
    color: #D7E2EA;
    font-size: 12px;
    padding: 0px 0px 10px 0px;
}}

QLabel#dashboardSectionTitle {{
    color: #FFFFFF;
    font-size: 17px;
    font-weight: bold;
    padding: 4px 2px 3px 2px;
}}


/* ========================================================
   KPI CARDS
   ======================================================== */

QFrame#kpiCard {{
    background-color: {COLOR_CARD};
    border: 1px solid {COLOR_BORDER_LIGHT};
    border-radius: 12px;
}}

QFrame#kpiCard:hover {{
    border: 1px solid #B8C9D8;
    background-color: #FCFDFE;
}}

QLabel#kpiLabel {{
    color: {COLOR_MUTED};
    font-size: 14px;
    font-weight: bold;
}}

QLabel#kpiValue {{
    font-size: 21px;
    font-weight: bold;
    color: {COLOR_PRIMARY_DARK};
    padding-top: 2px;
}}


/* ========================================================
   GROUP BOXES / MANAGEMENT SECTIONS
   ======================================================== */

QGroupBox {{
    background-color: {COLOR_CARD};
    border: 1px solid {COLOR_BORDER};
    border-radius: 10px;
    margin-top: 10px;
    padding: 9px 8px 8px 8px;
    font-size: 13px;
    font-weight: bold;
    color: {COLOR_PRIMARY_DARK};
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0px 8px;
    background-color: {COLOR_CARD};
    color: {COLOR_PRIMARY_DARK};
    font-weight: bold;
    text-align: right;
}}

QGroupBox#dashboardChartBox {{
    border: 1px solid #C9D7E4;
    border-radius: 12px;
    margin-top: 10px;
    padding: 10px 8px 8px 8px;
}}

QGroupBox#dashboardChartBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top right;
    right: 12px;
    padding: 0px 8px;
    color: {COLOR_PRIMARY_DARK};
    font-size: 14px;
    font-weight: bold;
}}

QGroupBox#dashboardAnalysisBox {{
    border: 1px solid {COLOR_BORDER_LIGHT};
    border-radius: 10px;
}}

QGroupBox#dashboardPhaseBox {{
    border: 1px solid #C9D7E4;
    border-radius: 12px;
}}

QGroupBox#dashboardMethodologyBox {{
    background-color: #F8FAFC;
    border: 1px solid {COLOR_BORDER_LIGHT};
}}


/* ========================================================
   DASHBOARD PHASE CARDS
   ======================================================== */

QLabel#dashboardPhaseValue {{
    font-size: 17px;
    font-weight: bold;
    color: {COLOR_PRIMARY};
    padding: 8px;
}}

QLabel#dashboardChartTitle {{
    color: {COLOR_PRIMARY_DARK};
    font-size: 14px;
    font-weight: bold;
    padding: 2px 4px 4px 4px;
}}
/* ========================================================
   TABLES
   ======================================================== */

QTableWidget {{
    background-color: {COLOR_CARD};
    alternate-background-color: #F8FAFC;
    gridline-color: #E5EAF0;
    border: 1px solid {COLOR_BORDER};
    border-radius: 8px;
    selection-background-color: {COLOR_PRIMARY_LIGHT};
    selection-color: {COLOR_TEXT};
}}

QTableWidget::item {{
    padding: 7px;
}}

QTableWidget::item:selected {{
    background-color: {COLOR_PRIMARY_LIGHT};
    color: {COLOR_TEXT};
}}

QHeaderView {{
    background-color: transparent;
}}

QHeaderView::section {{
    background-color: {COLOR_PRIMARY};
    color: white;
    padding: 8px 7px;
    border: none;
    font-weight: bold;
}}

QHeaderView::section:hover {{
    background-color: {COLOR_PRIMARY_DARK};
}}


/* ========================================================
   BUTTONS
   ======================================================== */

QPushButton {{
    background-color: {COLOR_PRIMARY};
    color: white;
    padding: 8px 18px;
    border-radius: 7px;
    border: none;
    font-weight: bold;
}}

QPushButton:hover {{
    background-color: {COLOR_PRIMARY_DARK};
}}

QPushButton:pressed {{
    background-color: #102C43;
}}

QPushButton:disabled {{
    background-color: #CBD5E0;
    color: #718096;
}}

QPushButton#secondary {{
    background-color: #E8EDF2;
    color: {COLOR_TEXT};
    border: 1px solid #D5DEE7;
}}

QPushButton#secondary:hover {{
    background-color: #DCE5ED;
}}


/* ========================================================
   INPUTS
   ======================================================== */

QLineEdit,
QComboBox {{
    padding: 7px 9px;
    border: 1px solid #CBD5E0;
    border-radius: 7px;
    background-color: white;
    selection-background-color: {COLOR_PRIMARY};
}}

QLineEdit:focus,
QComboBox:focus {{
    border: 1px solid #63B3ED;
}}

QComboBox QAbstractItemView {{
    background-color: white;
    border: 1px solid {COLOR_BORDER};
    selection-background-color: {COLOR_PRIMARY_LIGHT};
    selection-color: {COLOR_TEXT};
}}


/* ========================================================
   TEXT AREAS
   ======================================================== */

QPlainTextEdit {{
    background-color: white;
    border: 1px solid {COLOR_BORDER};
    border-radius: 7px;
    padding: 7px;
}}

QPlainTextEdit:focus {{
    border: 1px solid #63B3ED;
}}


/* ========================================================
   SCROLL AREAS
   ======================================================== */

QScrollArea {{
    background-color: transparent;
    border: none;
}}

QScrollBar:vertical {{
    background: #E9EEF3;
    width: 9px;
    margin: 2px;
    border-radius: 4px;
}}

QScrollBar::handle:vertical {{
    background: #B8C5D1;
    min-height: 35px;
    border-radius: 4px;
}}

QScrollBar::handle:vertical:hover {{
    background: #91A4B5;
}}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QScrollBar:horizontal {{
    background: #E9EEF3;
    height: 9px;
    margin: 2px;
    border-radius: 4px;
}}

QScrollBar::handle:horizontal {{
    background: #B8C5D1;
    min-width: 35px;
    border-radius: 4px;
}}

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {{
    width: 0px;
}}


/* ========================================================
   TABS
   ======================================================== */

QTabWidget::pane {{
    border: 1px solid {COLOR_BORDER};
    background-color: {COLOR_CARD};
    border-radius: 8px;
}}

QTabBar::tab {{
    background-color: #E8EDF2;
    color: {COLOR_MUTED};
    padding: 8px 16px;
    margin-left: 2px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}}

QTabBar::tab:selected {{
    background-color: {COLOR_PRIMARY};
    color: white;
}}

QTabBar::tab:hover {{
    background-color: #DCE5ED;
}}


/* ========================================================
   MESSAGE / STATUS ELEMENTS
   ======================================================== */

QLabel#statusGood {{
    color: {COLOR_GOOD};
    background-color: {COLOR_GOOD_BG};
    border-radius: 6px;
    padding: 6px 10px;
}}

QLabel#statusBad {{
    color: {COLOR_BAD};
    background-color: {COLOR_BAD_BG};
    border-radius: 6px;
    padding: 6px 10px;
}}

QLabel#statusWarn {{
    color: {COLOR_WARN};
    background-color: {COLOR_WARN_BG};
    border-radius: 6px;
    padding: 6px 10px;
}}

/* ========================================================
   CHART TOOLTIP
   ======================================================== */

QToolTip {{
    background-color: white;
    color: #111111;
    border: 1px solid #888888;
    padding: 6px 10px;
    font-size: 12px;
}}
"""

