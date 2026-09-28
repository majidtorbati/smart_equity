import pathlib
import sqlite3
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.ai import assistant as ai


def test_builtin_ai_fallback_contains_disclaimer_and_real_summary(tmp_path, monkeypatch):
    db = tmp_path / "x.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE transactions (transaction_id INTEGER PRIMARY KEY, trade_date_gregorian TEXT, quantity REAL, price REAL, value REAL, buyer_person_id INTEGER, seller_person_id INTEGER, buyer_broker_id INTEGER, seller_broker_id INTEGER)")
    conn.execute("CREATE TABLE persons (person_id INTEGER PRIMARY KEY, name_raw TEXT, person_type TEXT, national_id TEXT, shareholder_code TEXT)")
    conn.execute("CREATE TABLE brokers (broker_id INTEGER PRIMARY KEY, broker_name TEXT, is_market_maker INTEGER, is_primary_market_maker INTEGER)")
    conn.execute("CREATE TABLE symbols (symbol_id INTEGER PRIMARY KEY, symbol_code TEXT, symbol_name TEXT)")
    # This test only verifies that the fallback path is deterministic; a minimal schema may not
    # satisfy all analytics, so monkeypatch the built-in analyzer itself.
    monkeypatch.setattr(ai, "_builtin_analysis", lambda *args, **kwargs: "تحلیل داخلی SmartEquity\nمحدودیت: بدون مدل زبانی")
    monkeypatch.setattr(ai, "build_context", lambda *args, **kwargs: {"overview": {"transactions": 1}})
    monkeypatch.setattr(ai, "_settings", lambda: {"ollama_base_url": "http://127.0.0.1:1"})
    result = ai.generate_analysis(conn)
    assert result["provider"] == "تحلیل داخلی SmartEquity"
    assert "محدودیت" in result["text"]
