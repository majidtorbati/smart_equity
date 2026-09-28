"""
Combined project import:
1) reset SQLite
2) import daily transactions
3) import shareholder registry
4) reconcile identities
5) run FIFO portfolio analysis
"""
from __future__ import annotations
import pathlib
import sqlite3
from app.data.import_engine import import_excel, init_db
from app.data.registry_engine import import_registry, reconcile_identities
from app.analytics.portfolio import run_fifo

def import_project(transaction_xlsx: str, registry_xlsx: str, db_path: str) -> dict:
    db=pathlib.Path(db_path)
    if db.exists():
        db.unlink()
    db.parent.mkdir(parents=True,exist_ok=True)

    tx_result=import_excel(transaction_xlsx, str(db), reset_db=True)
    reg_result=import_registry(registry_xlsx, str(db), reset_registry=True)

    conn=sqlite3.connect(str(db))
    identity=reconcile_identities(conn)
    fifo=run_fifo(conn)
    conn.close()
    return {"transactions":tx_result,"registry":reg_result,"identity":identity,"fifo":fifo["summary"]}
