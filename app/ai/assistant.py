"""AI provider router for SmartEquity.

اولویت سرویس‌ها:
1) Ollama محلی
2) هر سرویس OpenAI-compatible محلی که کاربر در تنظیمات/متغیر محیطی معرفی کند
3) OpenAI از طریق اینترنت، فقط در صورت وجود API Key
4) تحلیل داخلی قطعی (بدون شبکه و بدون مدل)

هیچ کلید API در فایل پروژه ذخیره نمی‌شود؛ کلید از Environment یا تنظیمات محلی خوانده می‌شود.
برای حفظ حریم داده، متن ارسالی پیش‌فرض فقط شامل شاخص‌های تجمیعی است و شناسه ملی/نام سهامداران
ارسال نمی‌شود.
"""
from __future__ import annotations
import json
import os
import sqlite3
import urllib.request
import urllib.error
from typing import Any

from app.analytics import metrics as m
from app.analytics import portfolio as pf
from app.analytics import market_maker as mm
from app.analytics import insights as ins
from app.analytics import extended_analysis as ext
from app.detection import anomaly as an


def _settings() -> dict:
    try:
        from app.config.settings import load_settings
        return load_settings()
    except Exception:
        return {}


def _http_json(url: str, payload: dict | None = None, headers: dict | None = None, timeout: int = 20):
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers or {}, method="POST" if payload is not None else "GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _ollama_generate(base_url: str, model: str, prompt: str) -> str:
    url = base_url.rstrip("/") + "/api/generate"
    data = _http_json(url, {"model": model, "prompt": prompt, "stream": False, "options": {"temperature": 0.2}}, timeout=60)
    text = data.get("response")
    if not text:
        raise RuntimeError("Ollama پاسخ متنی برنگرداند.")
    return text.strip()


def _openai_compatible(base_url: str, api_key: str, model: str, prompt: str) -> str:
    url = base_url.rstrip("/") + "/chat/completions"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "شما دستیار تحلیل مالی SmartEquity هستید. فقط بر اساس داده ارائه‌شده تحلیل کنید و عددی را حدس نزنید."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }
    data = _http_json(url, payload, headers=headers, timeout=90)
    try:
        return data["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        raise RuntimeError(f"پاسخ OpenAI-compatible قابل خواندن نیست: {exc}")


def _openai_responses(api_key: str, model: str, prompt: str) -> str:
    url = "https://api.openai.com/v1/responses"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    payload = {"model": model, "input": prompt}
    data = _http_json(url, payload, headers=headers, timeout=90)
    if isinstance(data.get("output_text"), str) and data["output_text"].strip():
        return data["output_text"].strip()
    # fallback برای شکل‌های مختلف پاسخ Responses API
    parts = []
    for item in data.get("output", []) or []:
        for content in item.get("content", []) or []:
            txt = content.get("text")
            if isinstance(txt, str):
                parts.append(txt)
    if parts:
        return "\n".join(parts).strip()
    raise RuntimeError("OpenAI پاسخ متنی برنگرداند.")


def build_context(conn: sqlite3.Connection, start=None, end=None) -> dict[str, Any]:
    ov = m.overview(conn, start, end)
    fifo = pf.run_fifo(conn)["summary"]
    hhi = ext.hhi_summary(conn, start, end)
    mm_summary = mm.market_maker_summary(conn, start, end)
    alerts = an.run_all_anomaly_detectors(conn, start, end)
    brokers = m.top_brokers(conn, "buyer", start, end, top_n=5)
    return {
        "overview": {
            "transactions": ov["n_transactions"], "total_quantity": ov["total_quantity"],
            "total_value_rial": ov["total_value"], "weighted_avg_price": ov["weighted_avg_price"],
            "unique_buyers": ov["n_unique_buyers"], "unique_sellers": ov["n_unique_sellers"],
            "first_date": ov["first_date"], "last_date": ov["last_date"],
        },
        "fifo": fifo,
        "hhi": {"buy": hhi["buy"]["hhi"], "sell": hhi["sell"]["hhi"]},
        "alerts": {"count": len(alerts), "critical": sum(1 for a in alerts if a.get("severity") == "Critical")},
        "top_buyer_brokers": [
            {"name": b["broker_name"], "value_rial": b["value"], "transactions": b["n_transactions"]}
            for b in brokers
        ],
        "market_maker": {
            "has_market_maker": bool(mm_summary.get("has_market_maker")),
            "net_value_rial": mm_summary.get("net_value"),
        },
    }


def _prompt_from_context(ctx: dict) -> str:
    return """در نقش دستیار تحلیل مالی SmartEquity، یک تحلیل مدیریتی کوتاه و حرفه‌ای به فارسی ارائه کن.
قواعد:
- فقط از داده زیر استفاده کن.
- هیچ عدد، نام، علت یا نتیجه‌ای که در داده نیست اضافه نکن.
- بین «واقعیت داده»، «تفسیر» و «محدودیت» تفاوت بگذار.
- ورود احتمالی، هشدار آماری و بازارگردانی را به‌عنوان اثبات تخلف/علت قطعی بیان نکن.
- در پایان ۳ اقدام پیشنهادی برای بررسی مدیریتی بنویس، بدون اینکه تصمیم را به‌جای مدیر بگیری.

داده تجمیعی:
""" + json.dumps(ctx, ensure_ascii=False, indent=2)


def _builtin_analysis(conn: sqlite3.Connection, start=None, end=None) -> str:
    lines = ins.executive_summary_narrative(conn, start, end)
    fifo = pf.run_fifo(conn)["summary"]
    return "تحلیل داخلی SmartEquity (بدون مدل زبانی و بدون اینترنت)\n\n" + "\n".join(f"• {x}" for x in lines) + (
        f"\n\n• رجیستری/FIFO: {fifo['registry_matched']:,} تطبیق، {fifo['mismatched']:,} اختلاف، "
        f"{fifo['potential_new_entrants']:,} ورود احتمالی."
    ) + "\n\nمحدودیت: این خروجی بر پایه قواعد و شاخص‌های داخلی نرم‌افزار است و مدل زبانی خارجی در آن استفاده نشده است."


def generate_analysis(conn: sqlite3.Connection, start=None, end=None) -> dict[str, str]:
    settings = _settings()
    ctx = build_context(conn, start, end)
    prompt = _prompt_from_context(ctx)
    errors = []

    # 1) Local Ollama
    ollama_url = os.getenv("OLLAMA_HOST") or settings.get("ollama_base_url") or "http://127.0.0.1:11434"
    ollama_model = os.getenv("SMART_EQUITY_OLLAMA_MODEL") or settings.get("ollama_model") or "qwen2.5-coder:7b"
    try:
        # /api/tags is a cheap availability check and avoids a long timeout if Ollama is absent.
        tags = _http_json(ollama_url.rstrip("/") + "/api/tags", timeout=4)
        models = [x.get("name", "") for x in tags.get("models", []) if x.get("name")]
        selected_model = next((x for x in models if ollama_model == x or ollama_model in x), None)
        if selected_model is None:
            # اگر مدل پیش‌فرض حذف شده ولی مدل زبانی دیگری محلی وجود دارد، همان را امتحان کن.
            candidates = [x for x in models if "embed" not in x.lower() and "embedding" not in x.lower()]
            selected_model = candidates[0] if candidates else None
        if selected_model:
            return {"provider": f"Ollama محلی — {selected_model}", "text": _ollama_generate(ollama_url, selected_model, prompt)}
        errors.append("هیچ مدل زبانی مناسب در Ollama محلی پیدا نشد")
    except Exception as exc:
        errors.append(f"Ollama: {exc}")

    # 2) Custom local OpenAI-compatible endpoint (OmniRoute / LM Studio / etc.)
    local_base = os.getenv("SMART_EQUITY_LOCAL_AI_BASE_URL") or settings.get("local_ai_base_url", "")
    local_model = os.getenv("SMART_EQUITY_LOCAL_AI_MODEL") or settings.get("local_ai_model", "")
    local_key = os.getenv("SMART_EQUITY_LOCAL_AI_API_KEY") or settings.get("local_ai_api_key", "")
    if local_base and local_model:
        try:
            return {"provider": f"Local OpenAI-compatible — {local_model}", "text": _openai_compatible(local_base, local_key, local_model, prompt)}
        except Exception as exc:
            errors.append(f"Local OpenAI-compatible: {exc}")

    # 3) OpenAI over internet. Key is intentionally not bundled in the EXE.
    api_key = os.getenv("OPENAI_API_KEY") or settings.get("openai_api_key", "")
    if api_key:
        model = os.getenv("SMART_EQUITY_OPENAI_MODEL") or settings.get("openai_model") or "gpt-5.6-luna"
        try:
            return {"provider": f"OpenAI اینترنتی — {model}", "text": _openai_responses(api_key, model, prompt)}
        except Exception as exc:
            errors.append(f"OpenAI: {exc}")

    # 4) Built-in fallback
    text = _builtin_analysis(conn, start, end)
    if errors:
        text += "\n\nوضعیت اتصال: " + " | ".join(errors[:3])
    return {"provider": "تحلیل داخلی SmartEquity", "text": text}
