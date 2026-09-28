"""
تنظیمات قابل‌تغییر برنامه (به‌جای hard-code کردن مقادیر تجاری در کد) — از طریق صفحه «تنظیمات»
در برنامه یا مستقیماً از فایل config/settings.json قابل ویرایش است.

نکته مهم درباره بازارگردان: تشخیص خودکار «بازارگردان» صرفاً بر مبنای وجود کلمه «بازارگردان» در نام
کارگزار است (در app/data/import_engine.py، ستون brokers.is_market_maker) و ممکن است چند کارگزار را
شامل شود که همگی واقعاً بازارگردان رسمی و قراردادی همین نماد نیستند (مثلاً صندوق‌های بازارگردانی عمومی
که در چند نماد فعالیت می‌کنند). بنابراین برای تحلیل اختصاصی «رفتار بازارگردان»، به‌جای تکیه بر آن پرچم
خودکار، از فهرست صریح زیر (قابل‌ویرایش از صفحه تنظیمات) استفاده می‌شود.
"""
import json
import pathlib
import sys


def _runtime_root() -> pathlib.Path:
    """ریشه قابل‌نوشتن پروژه؛ در EXE یک‌فایلی/پرتابل از کنار executable استفاده می‌شود."""
    if getattr(sys, "frozen", False):
        return pathlib.Path(sys.executable).resolve().parent
    return pathlib.Path(__file__).resolve().parents[2]


RUNTIME_ROOT = _runtime_root()
SETTINGS_PATH = RUNTIME_ROOT / "config" / "settings.json"

DEFAULT_SETTINGS = {
    "company_name": "",  # اگر خالی باشد، نام نماد از خودِ فایل اکسل به‌عنوان جایگزین نمایش داده می‌شود
    "primary_market_maker_broker_names": [
        "بازارگردان الکترونیکی الگوریتمی صباتامین"
    ],
    "report_prepared_by": "مدیر مالی",
    "report_audience": "هیئت‌مدیره",
    "report_title": "گزارش تحلیل معاملات سهام",
    "logo_path": "",  # مسیر نسبی به assets/company_logo.png (بعد از آپلود از صفحه تنظیمات پر می‌شود)
    # AI: کلیدها را داخل پروژه یا EXE ذخیره نکنید؛ متغیرهای محیطی اولویت دارند.
    "ollama_base_url": "http://127.0.0.1:11434",
    "ollama_model": "qwen2.5-coder:7b",
    "local_ai_base_url": "",
    "local_ai_model": "",
    "local_ai_api_key": "",
    "openai_model": "gpt-5.6-luna",
    "openai_api_key": "",
}

ASSETS_DIR = RUNTIME_ROOT / "assets"
LOGO_FILENAME = "company_logo.png"

# --- اطلاعات ثابت برنامه (عمداً در فایل تنظیماتِ قابل‌ویرایش نیست؛ طبق درخواست کاربر باید ثابت بماند) ---
DEVELOPER_NAME = "مجید تربتی"
DEVELOPER_CREDIT = f"برنامه‌نویس: {DEVELOPER_NAME} (به کمک هوش مصنوعی)"
SUPPORT_PHONE = "09151102442"
DEVELOPER_CREDIT_LINE = f"{DEVELOPER_CREDIT}   ،   تلفن: {SUPPORT_PHONE}"


def load_settings() -> dict:
    if SETTINGS_PATH.exists():
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            merged = dict(DEFAULT_SETTINGS)
            merged.update(data)
            return merged
        except (json.JSONDecodeError, OSError):
            return dict(DEFAULT_SETTINGS)
    return dict(DEFAULT_SETTINGS)


def save_settings(settings: dict):
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    merged = load_settings()
    merged.update(settings)
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)


def get_primary_market_maker_names() -> list[str]:
    return load_settings().get("primary_market_maker_broker_names", [])


def get_company_name() -> str:
    return load_settings().get("company_name", "") or ""


def get_report_prepared_by() -> str:
    return load_settings().get("report_prepared_by") or DEFAULT_SETTINGS["report_prepared_by"]


def get_report_audience() -> str:
    return load_settings().get("report_audience") or DEFAULT_SETTINGS["report_audience"]


def get_report_title() -> str:
    return load_settings().get("report_title") or DEFAULT_SETTINGS["report_title"]


def get_logo_path() -> pathlib.Path | None:
    """
    مسیر مطلق فایل لوگو را برمی‌گرداند، فقط اگر فایل واقعاً روی دیسک موجود باشد؛
    در غیر این صورت None (مثلاً اگر کاربر فایل را دستی حذف کرده باشد، برنامه نباید کرش کند).
    """
    rel = load_settings().get("logo_path", "")
    if not rel:
        return None
    p = ASSETS_DIR / LOGO_FILENAME
    return p if p.exists() else None


def set_logo(source_path) -> str:
    """
    فایل تصویر انتخاب‌شده را (با هر فرمتی: png/jpg/jpeg/bmp) به یک PNG استاندارد در پوشه assets
    تبدیل و کپی می‌کند، تا مسیر ذخیره‌شده همیشه ثابت و مستقل از فایل اصلی کاربر باشد (مهم برای
    قابلیت حمل روی فلش — اگر مسیر اصلی فایل کاربر بعداً در دسترس نباشد، نباید گزارش‌ها خراب شوند).
    """
    from PIL import Image
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    dest = ASSETS_DIR / LOGO_FILENAME
    with Image.open(source_path) as im:
        if im.mode not in ("RGB", "RGBA"):
            im = im.convert("RGBA")
        im.save(dest, format="PNG")
    rel_path = f"assets/{LOGO_FILENAME}"
    save_settings({"logo_path": rel_path})
    return rel_path


def remove_logo():
    logo = get_logo_path()
    if logo is not None:
        try:
            logo.unlink()
        except OSError:
            pass
    save_settings({"logo_path": ""})
