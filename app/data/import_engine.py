"""
Import Engine: Excel -> Validation -> Normalization -> Cleaning -> SQLite
فایل Excel اصلی هرگز تغییر نمی‌کند (فقط خوانده می‌شود).
"""
from __future__ import annotations
import sqlite3
import datetime as dt
import json
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

import pandas as pd
from app.core.jalali import parse_yyyymmdd_jalali
from app.core.normalize import clean_display, normalize_key

SCHEMA_PATH = pathlib.Path(__file__).parent / "schema.sql"

# mapping from expected Persian column names -> internal roles.
# اگر ساختار فایل جدید فرق کند، این dict باید در UI به کاربر برای Column Mapping نمایش داده شود.
DEFAULT_COLUMN_MAP = {
    "declaration_no": "شماره اعلامیه",
    "trade_date": "تاریخ معامله",
    "symbol_code": "نماد",
    "symbol_name": "نام نماد",
    "buyer_national_id": "کد/شناسه ملی خریدار",
    "buyer_name": "نام خریدار",
    "buyer_family": "نام خانوادگی خریدار",
    "buyer_type": "نوع خریدار",
    "buyer_sejam_code": "کد خریدار",
    "buyer_broker_code": "کد کارگزار خریدار",
    "buyer_broker_name": "نام کارگزار خریدار",
    "seller_national_id": "کد/شناسه ملی فروشنده",
    "seller_name": "نام فروشنده",
    "seller_family": "نام خانوادگی فروشنده",
    "seller_type": "نوع فروشنده",
    "seller_sejam_code": "کد فروشنده",
    "seller_broker_code": "کد کارگزار فروشنده",
    "seller_broker_name": "نام کارگزار فروشنده",
    "quantity": "تعداد سهم",
    "price": "قیمت هر سهم",
}


def init_db(db_path: str):
    conn = sqlite3.connect(db_path)
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()
    return conn


def _get_or_create_symbol(conn, code, name):
    cur = conn.execute("SELECT symbol_id FROM symbols WHERE symbol_code=?", (code,))
    row = cur.fetchone()
    if row:
        return row[0]
    cur = conn.execute("INSERT INTO symbols(symbol_code, symbol_name) VALUES (?,?)", (code, name))
    return cur.lastrowid


def _get_or_create_broker(conn, code, name_raw, broker_cache: dict):
    name_disp = clean_display(name_raw)
    key = normalize_key(name_raw)
    if key in broker_cache:
        return broker_cache[key]
    cur = conn.execute("SELECT broker_id FROM brokers WHERE broker_name_key=?", (key,))
    row = cur.fetchone()
    if row:
        broker_cache[key] = row[0]
        return row[0]
    is_mm = 1 if "بازارگردان" in name_disp else 0
    cur = conn.execute(
        "INSERT INTO brokers(broker_code, broker_name_raw, broker_name_key, is_market_maker) VALUES (?,?,?,?)",
        (code, name_disp, key, is_mm),
    )
    broker_cache[key] = cur.lastrowid
    return cur.lastrowid


def _get_or_create_person(conn, national_id, name_raw, family_raw, ptype, sejam_code, person_cache: dict):
    nid = str(national_id) if national_id not in (None, "") else None
    family_clean = "" if pd.isna(family_raw) else str(family_raw).strip()
    name_clean = "" if pd.isna(name_raw) else str(name_raw).strip()

    name_disp = clean_display(f"{family_clean} {name_clean}".strip())
    name_key = normalize_key(name_disp)

    sej_code = (
        str(sejam_code).strip()
        if sejam_code is not None and not pd.isna(sejam_code)
        else None
    )

    cache_key = nid if nid else (
        f"SEJAM::{sej_code}" if sej_code
        else f"NAME::{name_key}"
    )

    if cache_key in person_cache:
        person_id = person_cache[cache_key]

        conn.execute(
            """
            UPDATE persons
            SET first_name=?,
                family_name=?,
                person_type=?,
                sejam_code=?,
                name_raw=?,
                name_key=?
            WHERE person_id=?
            """,
            (
                name_clean,
                family_clean,
                ptype,
                sej_code,
                name_disp,
                name_key,
                person_id,
            ),
        )

        return person_id

    if nid:
        cur = conn.execute(
            "SELECT person_id FROM persons WHERE national_id=?",
            (nid,),
        )
        row = cur.fetchone()

        if row:
            person_id = row[0]

            conn.execute(
                """
                UPDATE persons
                SET first_name=?,
                    family_name=?,
                    person_type=?,
                    sejam_code=?,
                    name_raw=?,
                    name_key=?,
                    identifier_confidence=?
                WHERE person_id=?
                """,
                (
                    name_clean,
                    family_clean,
                    ptype,
                    sej_code,
                    name_disp,
                    name_key,
                    "high",
                    person_id,
                ),
            )

            person_cache[cache_key] = person_id
            return person_id

    if sej_code:
        cur = conn.execute(
            """
            SELECT person_id
            FROM persons
            WHERE sejam_code=?
            LIMIT 1
            """,
            (sej_code,),
        )
        row = cur.fetchone()

        if row:
            person_id = row[0]

            conn.execute(
                """
                UPDATE persons
                SET national_id=?,
                    first_name=?,
                    family_name=?,
                    person_type=?,
                    name_raw=?,
                    name_key=?,
                    identifier_confidence=?
                WHERE person_id=?
                """,
                (
                    nid,
                    name_clean,
                    family_clean,
                    ptype,
                    name_disp,
                    name_key,
                    "high" if nid else "low",
                    person_id,
                ),
            )

            person_cache[cache_key] = person_id
            return person_id

    confidence = "high" if nid else "low"

    cur = conn.execute(
        """
        INSERT INTO persons(
            national_id,
            name_raw,
            name_key,
            first_name,
            family_name,
            person_type,
            sejam_code,
            shareholder_code,
            identifier_confidence
        )
        VALUES (?,?,?,?,?,?,?,?,?)
        """,
        (
            nid,
            name_disp,
            name_key,
            name_clean,
            family_clean,
            ptype,
            sej_code,
            None,
            confidence,
        ),
    )

    person_cache[cache_key] = cur.lastrowid
    return cur.lastrowid
def import_excel(xlsx_path: str, db_path: str, column_map: dict = None, reset_db: bool = True) -> dict:
    """
    Returns a data-quality / import summary dict. Never mutates the source file.

    مهم: هر Import، دیتابیس قبلی را کاملاً جایگزین می‌کند، نه اینکه به آن اضافه کند.
    قبلاً چون init_db() از CREATE TABLE IF NOT EXISTS استفاده می‌کرد، وارد کردن یک فایل دوم
    (مثلاً معاملات یک شرکت دیگر) صرفاً به داده‌ی شرکت قبلی اضافه می‌شد و همه معاملات با هم
    قاطی می‌شدند — تحلیل نهایی هر دو شرکت را با هم مخلوط نشان می‌داد. برای اینکه هر Import
    دقیقاً و فقط همان یک فایل را تحلیل کند، دیتابیس قبل از Import جدید حذف و از صفر ساخته می‌شود.
    """
    db_file = pathlib.Path(db_path)

    # reset_db=True:
    # ????? ?????? ????? ?? ??????? ???? ??? ? Schema ?? ?? ????? ??????.
    #
    # reset_db=False:
    # ??? ???????? ???????? ???? ??????? ??????? ? ??????? ????????? ??? ??????.
    if reset_db and db_file.exists():
        db_file.unlink()

    cm = column_map or DEFAULT_COLUMN_MAP
    df_raw = pd.read_excel(xlsx_path, engine="openpyxl")
    n_rows_raw = len(df_raw)

    conn = init_db(db_path)

    if not reset_db:
        # Import ????? ???????:
        # ??????? ????????? ??? ?????? ? ??? ???????? ????????
        # ? ??????? ?????? ?? ???? ??????? ???????.
        conn.execute("DELETE FROM fifo_realizations")
        conn.execute("DELETE FROM fifo_lots")
        conn.execute("DELETE FROM identity_matches")
        conn.execute("DELETE FROM transactions")
        conn.execute("DELETE FROM persons")
        conn.execute("DELETE FROM brokers")
        conn.execute("DELETE FROM symbols")
        conn.execute("DELETE FROM import_batches")
        conn.execute("DELETE FROM data_quality")
        conn.execute("DELETE FROM alerts")
        conn.execute("DELETE FROM analysis_cache")
        conn.execute("DELETE FROM portfolio_analysis_cache")
        conn.commit()

    batch_cur = conn.execute(
        "INSERT INTO import_batches(source_file, imported_at, n_rows_raw) VALUES (?,?,?)",
        (str(xlsx_path), dt.datetime.now().isoformat(timespec="seconds"), n_rows_raw),
    )
    batch_id = batch_cur.lastrowid

    broker_cache: dict = {}
    person_cache: dict = {}

    n_rejected = 0
    n_duplicate = 0
    n_imported = 0
    reject_reasons = []
    seen_declaration_hash = {}  # declaration_no+qty+price+date -> transaction_id (first occurrence)

    for idx, row in df_raw.iterrows():
        try:
            trade_date_j_raw = row[cm["trade_date"]]
            g_date = parse_yyyymmdd_jalali(trade_date_j_raw)
            j_str = str(int(trade_date_j_raw))
            j_str_fmt = f"{j_str[0:4]}/{j_str[4:6]}/{j_str[6:8]}"

            qty = row[cm["quantity"]]
            price = row[cm["price"]]
            if pd.isna(qty) or pd.isna(price):
                n_rejected += 1
                reject_reasons.append((idx, "missing quantity/price"))
                continue
            qty = int(qty)
            price = float(price)
            if qty <= 0 or price <= 0:
                n_rejected += 1
                reject_reasons.append((idx, "non-positive quantity/price"))
                continue
            value = qty * price

            declaration_no = row.get(cm["declaration_no"])
            symbol_id = _get_or_create_symbol(conn, row[cm["symbol_code"]], row.get(cm["symbol_name"]))

            buyer_broker_id = _get_or_create_broker(conn, row.get(cm["buyer_broker_code"]), row.get(cm["buyer_broker_name"]), broker_cache)
            seller_broker_id = _get_or_create_broker(conn, row.get(cm["seller_broker_code"]), row.get(cm["seller_broker_name"]), broker_cache)

            buyer_person_id = _get_or_create_person(
                conn, row.get(cm["buyer_national_id"]), row.get(cm["buyer_name"]), row.get(cm["buyer_family"]),
                row.get(cm["buyer_type"]), row.get(cm["buyer_sejam_code"]), person_cache,
            )
            seller_person_id = _get_or_create_person(
                conn, row.get(cm["seller_national_id"]), row.get(cm["seller_name"]), row.get(cm["seller_family"]),
                row.get(cm["seller_type"]), row.get(cm["seller_sejam_code"]), person_cache,
            )

            dup_key = (declaration_no, qty, price, j_str_fmt, buyer_person_id, seller_person_id)
            is_dup_of = seen_declaration_hash.get(dup_key)
            if is_dup_of is not None:
                n_duplicate += 1

            cur = conn.execute(
                """INSERT INTO transactions
                (declaration_no, trade_date_jalali, trade_date_gregorian, symbol_id,
                 buyer_person_id, seller_person_id, buyer_broker_id, seller_broker_id,
                 quantity, price, value, is_duplicate_of, source_row_index, import_batch_id)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (str(declaration_no), j_str_fmt, g_date.isoformat(), symbol_id,
                 buyer_person_id, seller_person_id, buyer_broker_id, seller_broker_id,
                 qty, price, value, is_dup_of, int(idx), batch_id),
            )
            if is_dup_of is None:
                seen_declaration_hash[dup_key] = cur.lastrowid
            n_imported += 1
        except Exception as e:
            n_rejected += 1
            reject_reasons.append((idx, str(e)))
            continue

    conn.execute(
        "UPDATE import_batches SET n_rows_imported=?, n_rows_duplicate=?, n_rows_rejected=? WHERE batch_id=?",
        (n_imported, n_duplicate, n_rejected, batch_id),
    )

    dq_metrics = {
        "n_rows_raw": n_rows_raw,
        "n_rows_imported": n_imported,
        "n_rows_rejected": n_rejected,
        "n_rows_duplicate_flagged": n_duplicate,
        "n_unique_buyers": len(set(v for k, v in person_cache.items())),
        "n_unique_brokers": len(broker_cache),
        "reject_samples": reject_reasons[:20],
    }
    for k, v in dq_metrics.items():
        if k == "reject_samples":
            v = json.dumps(v, ensure_ascii=False)
        conn.execute("INSERT INTO data_quality(batch_id, metric_name, metric_value) VALUES (?,?,?)", (batch_id, k, str(v)))

    conn.commit()
    conn.close()
    return dq_metrics


if __name__ == "__main__":
    import time
    db_path = str(pathlib.Path(__file__).resolve().parents[2] / "data" / "smart_equity.db")
    pathlib.Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    # حذف صریح دیگر لازم نیست؛ خودِ import_excel() اکنون همیشه دیتابیس قبلی را جایگزین می‌کند.
    t0 = time.time()
    result = import_excel(str(pathlib.Path(sys.argv[1]).resolve()) if len(sys.argv) > 1 else str(pathlib.Path(__file__).resolve().parents[2] / "Book2.xlsx"), db_path)
    t1 = time.time()
    print(f"Import finished in {t1-t0:.2f}s")
    print(json.dumps(result, ensure_ascii=False, indent=2))
