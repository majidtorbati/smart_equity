"""
Shareholder registry importer and identity reconciliation.
رجیستری «اول دوره/پایان دوره» را به‌عنوان موجودی افتتاحیه ثبت می‌کند.
فایل منبع هرگز تغییر نمی‌کند.
"""
from __future__ import annotations
import datetime as dt
import pathlib
import re
import sqlite3
import pandas as pd

from app.core.normalize import normalize_key

REGISTRY_COLUMNS = {
    "shareholder_no": "شماره سهامدار",
    "first_name": "نام",
    "family_name": "نام خانوادگي",
    "father_name": "نام پدر",
    "birth_or_registration_no": "شماره شناسنامه _ثبت",
    "issue_place": "محل صدور_ ثبت",
    "exchange_code": "كدبورس",
    "national_id": "كد ملي",
    "opening_quantity": "تعداد سهم اول دوره",
    "registry_buy_quantity": "تعداد سهم خريداري شده",
    "registry_sell_quantity": "تعداد سهم فروخته شده",
    "closing_quantity": "تعداد سهم پايان دوره",
}

def _clean_id(v):
    if pd.isna(v) or v in ("", None):
        return None
    s = str(v).strip()
    if re.fullmatch(r"\d+\.0", s):
        s = s[:-2]
    digits = re.sub(r"\D", "", s)
    return digits or None

def _clean_int(v):
    if pd.isna(v) or v in ("", None):
        return 0
    try:
        return int(float(v))
    except Exception:
        return 0

def _clean_text(v):
    if pd.isna(v) or v is None:
        return ""
    return str(v).strip()

def _name_key(family, first):
    return normalize_key(f"{_clean_text(family)} {_clean_text(first)}")

def import_registry(xlsx_path: str, db_path: str, reset_registry: bool = True) -> dict:
    df = pd.read_excel(xlsx_path, engine="openpyxl")
    conn = sqlite3.connect(db_path)
    if reset_registry:
        conn.execute("DELETE FROM identity_matches")
        conn.execute("DELETE FROM fifo_realizations")
        conn.execute("DELETE FROM fifo_lots")
        conn.execute("DELETE FROM registry_holdings")
        conn.execute("DELETE FROM registry_batches")

    cur = conn.execute(
        "INSERT INTO registry_batches(source_file, imported_at, n_rows_raw) VALUES (?,?,?)",
        (str(pathlib.Path(xlsx_path).resolve()), dt.datetime.now().isoformat(timespec="seconds"), len(df))
    )
    batch_id = cur.lastrowid
    imported = rejected = 0

    for idx, row in df.iterrows():
        # The supplied file contains a final total row with no shareholder number.
        is_total = pd.isna(row.get(REGISTRY_COLUMNS["shareholder_no"]))
        if is_total:
            continue
        try:
            vals = {k: row.get(v) for k, v in REGISTRY_COLUMNS.items()}
            conn.execute(
                """INSERT INTO registry_holdings
                (registry_batch_id, shareholder_no, first_name, family_name, father_name,
                 birth_or_registration_no, issue_place, registration_no, exchange_code, national_id,
                 opening_quantity, registry_buy_quantity, registry_sell_quantity, closing_quantity,
                 is_total_row, source_row_index)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (batch_id, _clean_text(vals["shareholder_no"]), _clean_text(vals["first_name"]),
                 _clean_text(vals["family_name"]), _clean_text(vals["father_name"]),
                 _clean_text(vals["birth_or_registration_no"]), _clean_text(vals["issue_place"]),
                 "", _clean_text(vals["exchange_code"]), _clean_id(vals["national_id"]),
                 _clean_int(vals["opening_quantity"]), _clean_int(vals["registry_buy_quantity"]),
                 _clean_int(vals["registry_sell_quantity"]), _clean_int(vals["closing_quantity"]),
                 0, int(idx))
            )
            imported += 1
        except Exception:
            rejected += 1

    conn.execute("UPDATE registry_batches SET n_rows_imported=?, n_rows_rejected=? WHERE registry_batch_id=?",
                 (imported, rejected, batch_id))
    conn.commit()
    conn.close()
    return {
        "registry_batch_id": batch_id,
        "n_rows_raw": len(df),
        "n_rows_imported": imported,
        "n_rows_rejected": rejected,
        "total_opening_quantity": int(df.loc[df[REGISTRY_COLUMNS["shareholder_no"]].notna(), REGISTRY_COLUMNS["opening_quantity"]].fillna(0).sum()),
        "total_closing_quantity": int(df.loc[df[REGISTRY_COLUMNS["shareholder_no"]].notna(), REGISTRY_COLUMNS["closing_quantity"]].fillna(0).sum()),
    }

def reconcile_identities(conn: sqlite3.Connection) -> dict:
    registry = conn.execute("""
        SELECT registry_holding_id, exchange_code, national_id,
               first_name, family_name
        FROM registry_holdings
        WHERE is_total_row=0
    """).fetchall()

    by_exchange_code = {}
    by_nid = {}
    by_name = {}

    for rid, exchange_code, nid, first, family in registry:
        code = str(exchange_code).strip() if exchange_code is not None else ""
        if code:
            by_exchange_code.setdefault(code, []).append(rid)

        nid_key = str(nid).strip() if nid is not None else ""
        if nid_key:
            by_nid.setdefault(nid_key, []).append(rid)

        nk = _name_key(family, first)
        if nk:
            by_name.setdefault(nk, []).append(rid)

    conn.execute("DELETE FROM identity_matches")

    people = conn.execute("""
        SELECT person_id, national_id, sejam_code,
               first_name, family_name, name_raw
        FROM persons
    """).fetchall()

    stats = {
        "sejam_code": 0,
        "national_id": 0,
        "name": 0,
        "unmatched": 0,
        "ambiguous": 0,
    }

    for pid, nid, sejam_code, first_name, family_name, name_raw in people:
        rid = None
        method = None
        confidence = None

        code = str(sejam_code).strip() if sejam_code is not None else ""
        candidates = by_exchange_code.get(code, []) if code else []

        if len(candidates) == 1:
            rid, method, confidence = candidates[0], "sejam_code", "high"
        elif len(candidates) > 1:
            stats["ambiguous"] += 1
        else:
            nid_key = str(nid).strip() if nid is not None else ""
            candidates = by_nid.get(nid_key, []) if nid_key else []

            if len(candidates) == 1:
                rid, method, confidence = candidates[0], "national_id", "high"
            elif len(candidates) > 1:
                stats["ambiguous"] += 1
            else:
                nk = _name_key(family_name, first_name)

                if not nk:
                    nk = normalize_key(name_raw or "")

                candidates = by_name.get(nk, []) if nk else []

                if len(candidates) == 1:
                    rid, method, confidence = candidates[0], "name", "medium-low"
                elif len(candidates) > 1:
                    stats["ambiguous"] += 1

        if rid:
            conn.execute("""
                INSERT OR REPLACE INTO identity_matches
                    (transaction_person_id, registry_holding_id,
                     match_method, confidence, matched_at)
                VALUES (?,?,?,?,?)
            """, (
                pid,
                rid,
                method,
                confidence,
                dt.datetime.now().isoformat(timespec="seconds"),
            ))
            stats[method] += 1
        else:
            stats["unmatched"] += 1

    conn.commit()

    stats["matched"] = (
        stats["sejam_code"]
        + stats["national_id"]
        + stats["name"]
    )
    stats["total_people"] = len(people)

    return stats