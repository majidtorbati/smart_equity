"""
Portfolio / FIFO engine for shareholder registry + daily trades.

قواعد:
- موجودی اول دوره از رجیستری به‌صورت Lot با بهای تمام‌شده «نامشخص» وارد می‌شود.
- خریدهای روزانه Lot با بهای خرید معلوم می‌سازند.
- فروش با FIFO به ترتیب تاریخ و شماره معامله مصرف می‌شود.
- سود تحقق‌یافته فقط برای بخشی که بهای تمام‌شده معلوم دارد عددی است؛
  فروش از موجودی اول دوره به‌عنوان سود/زیان «نامشخص» گزارش می‌شود.
- معاملات تکراری علامت‌گذاری‌شده از محاسبات کنار گذاشته می‌شوند.
"""
from __future__ import annotations
import collections
import datetime as dt
import json
import sqlite3
from dataclasses import dataclass

@dataclass
class Lot:
    lot_id: int
    person_id: int
    symbol_id: int
    date: str
    jalali: str
    source_type: str
    source_tx: int | None
    qty_original: int
    qty_remaining: int
    unit_cost: float | None
    cost_known: bool

def _latest_price(conn, symbol_id, end=None):
    if end:
        row=conn.execute("""SELECT price FROM transactions
                            WHERE symbol_id=? AND trade_date_gregorian<=? AND is_duplicate_of IS NULL
                            ORDER BY trade_date_gregorian DESC, transaction_id DESC LIMIT 1""",(symbol_id,end)).fetchone()
    else:
        row=conn.execute("""SELECT price FROM transactions
                            WHERE symbol_id=? AND is_duplicate_of IS NULL
                            ORDER BY trade_date_gregorian DESC, transaction_id DESC LIMIT 1""",(symbol_id,)).fetchone()
    return float(row[0]) if row else None

def run_fifo(conn: sqlite3.Connection, start=None, end=None) -> dict:
    # Clear prior calculated rows.
    conn.execute("DELETE FROM fifo_realizations")
    conn.execute("DELETE FROM fifo_lots")

    # Registry opening lots are the state immediately before the analysis window.
    reg_rows = conn.execute("""SELECT ih.registry_holding_id, ih.opening_quantity,
                                      ih.closing_quantity, im.transaction_person_id,
                                      p.name_raw, s.symbol_id
                               FROM registry_holdings ih
                               JOIN identity_matches im ON im.registry_holding_id=ih.registry_holding_id
                               JOIN persons p ON p.person_id=im.transaction_person_id
                               JOIN symbols s ON 1=1
                               WHERE ih.is_total_row=0""").fetchall()
    lots_by_person = collections.defaultdict(collections.deque)
    opening_by_person = collections.Counter()
    registry_closing = {}
    for rid, opening, closing, pid, name, sid in reg_rows:
        cur=conn.execute("""INSERT INTO fifo_lots
            (person_id,symbol_id,lot_date_gregorian,lot_date_jalali,source_type,
             source_transaction_id,quantity_original,quantity_remaining,unit_cost,cost_known)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (pid,sid,"1900-01-01","اول دوره","opening",None,int(opening),int(opening),None,0))
        lot=Lot(cur.lastrowid,pid,sid,"1900-01-01","اول دوره","opening",None,int(opening),int(opening),None,False)
        lots_by_person[(pid,sid)].append(lot)
        opening_by_person[(pid,sid)] += int(opening)
        registry_closing[(pid,sid)] = int(closing)

    where=["t.is_duplicate_of IS NULL"]; params=[]
    if start: where.append("t.trade_date_gregorian>=?"); params.append(start)
    if end: where.append("t.trade_date_gregorian<=?"); params.append(end)
    txs=conn.execute(f"""SELECT t.transaction_id,t.trade_date_gregorian,t.trade_date_jalali,
                                t.symbol_id,t.buyer_person_id,t.seller_person_id,t.quantity,t.price
                         FROM transactions t WHERE {' AND '.join(where)}
                         ORDER BY t.trade_date_gregorian,t.transaction_id""",params).fetchall()

    # Ensure persons with transactions but no opening registry still get FIFO queues.
    stats=collections.defaultdict(lambda: {
        "buy_qty":0,"sell_qty":0,"buy_value":0.0,"sell_value":0.0,
        "known_realized_pnl":0.0,"known_realized_qty":0,"unknown_cost_qty":0,
        "unresolved_sell_qty":0,"new_entrant":False
    })
    person_names=dict(conn.execute("SELECT person_id,name_raw FROM persons"))
    symbol_names=dict(conn.execute("SELECT symbol_id,symbol_code FROM symbols"))

    for txid,date,jdate,sid,bpid,spid,qty,price in txs:
        qty=int(qty); price=float(price)
        # Buy side
        if bpid is not None:
            k=(bpid,sid)
            stats[k]["buy_qty"] += qty
            stats[k]["buy_value"] += qty*price
            cur=conn.execute("""INSERT INTO fifo_lots
                (person_id,symbol_id,lot_date_gregorian,lot_date_jalali,source_type,
                 source_transaction_id,quantity_original,quantity_remaining,unit_cost,cost_known)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (bpid,sid,date,jdate,"buy",txid,qty,qty,price,1))
            lot=Lot(cur.lastrowid,bpid,sid,date,jdate,"buy",txid,qty,qty,price,True)
            lots_by_person[k].append(lot)
        # Sell side: consume FIFO
        if spid is not None:
            k=(spid,sid)
            stats[k]["sell_qty"] += qty
            stats[k]["sell_value"] += qty*price
            remaining=qty
            while remaining>0 and lots_by_person[k]:
                lot=lots_by_person[k][0]
                take=min(remaining,lot.qty_remaining)
                if lot.cost_known:
                    pnl=(price-lot.unit_cost)*take
                    stats[k]["known_realized_pnl"] += pnl
                    stats[k]["known_realized_qty"] += take
                    conn.execute("""INSERT INTO fifo_realizations
                        (person_id,symbol_id,sell_transaction_id,lot_id,quantity,sell_price,unit_cost,realized_pnl,cost_known)
                        VALUES (?,?,?,?,?,?,?,?,1)""",
                        (spid,sid,txid,lot.lot_id,take,price,lot.unit_cost,pnl))
                else:
                    stats[k]["unknown_cost_qty"] += take
                    conn.execute("""INSERT INTO fifo_realizations
                        (person_id,symbol_id,sell_transaction_id,lot_id,quantity,sell_price,unit_cost,realized_pnl,cost_known)
                        VALUES (?,?,?,?,?,?,?,?,0)""",
                        (spid,sid,txid,lot.lot_id,take,price,None,None))
                lot.qty_remaining-=take
                conn.execute("UPDATE fifo_lots SET quantity_remaining=? WHERE lot_id=?",(lot.qty_remaining,lot.lot_id))
                remaining-=take
                if lot.qty_remaining==0:
                    lots_by_person[k].popleft()
            if remaining:
                stats[k]["unresolved_sell_qty"] += remaining

    latest={sid:_latest_price(conn,sid,end) for sid in symbol_names}
    results=[]
    keys=set(stats)|set(opening_by_person)|set(registry_closing)
    # Include people with only registry holdings.
    for k in keys:
        pid,sid=k
        st=stats[k]
        opening=int(opening_by_person.get(k,0))
        expected=opening+st["buy_qty"]-st["sell_qty"]
        reg_close=registry_closing.get(k)
        remaining_known=remaining_unknown=0
        for lot in lots_by_person.get(k,[]):
            if lot.qty_remaining:
                if lot.cost_known: remaining_known += lot.qty_remaining
                else: remaining_unknown += lot.qty_remaining
        lp=latest.get(sid)
        mkt_value=(remaining_known+remaining_unknown)*lp if lp is not None else None
        st["new_entrant"]=opening==0 and st["buy_qty"]>0 and k not in registry_closing
        results.append({
            "person_id":pid,"symbol_id":sid,"name":person_names.get(pid),
            "symbol":symbol_names.get(sid),
            "opening_qty":opening,"daily_buy_qty":st["buy_qty"],"daily_sell_qty":st["sell_qty"],
            "expected_closing_qty":expected,"registry_closing_qty":reg_close,
            "reconciliation_diff":(expected-reg_close) if reg_close is not None else None,
            "buy_value":st["buy_value"],"sell_value":st["sell_value"],
            "known_realized_pnl":st["known_realized_pnl"],
            "known_realized_qty":st["known_realized_qty"],
            "unknown_cost_sold_qty":st["unknown_cost_qty"],
            "unresolved_sell_qty":st["unresolved_sell_qty"],
            "remaining_known_qty":remaining_known,
            "remaining_unknown_cost_qty":remaining_unknown,
            "latest_price":lp,"market_value":mkt_value,
            "is_potential_new_entrant":bool(st["new_entrant"]),
            "is_registry_matched":k in registry_closing,
        })
    # cache JSON summary
    summary={
        "people":len(results),
        "registry_matched":sum(r["is_registry_matched"] for r in results),
        "potential_new_entrants":sum(r["is_potential_new_entrant"] for r in results),
        "reconciled":sum(r["reconciliation_diff"]==0 for r in results if r["reconciliation_diff"] is not None),
        "mismatched":sum(r["reconciliation_diff"]!=0 for r in results if r["reconciliation_diff"] is not None),
        "unmatched_registry":sum(not r["is_registry_matched"] for r in results),
        "known_realized_pnl":sum(r["known_realized_pnl"] for r in results),
        "unknown_cost_sold_qty":sum(r["unknown_cost_sold_qty"] for r in results),
        "unresolved_sell_qty":sum(r["unresolved_sell_qty"] for r in results),
    }
    conn.execute("INSERT OR REPLACE INTO portfolio_analysis_cache(cache_key,computed_at,payload_json) VALUES (?,?,?)",
                 ("fifo_summary",dt.datetime.now().isoformat(timespec="seconds"),json.dumps(summary,ensure_ascii=False)))
    conn.commit()
    return {"summary":summary,"results":results}

def portfolio_summary(conn,start=None,end=None):
    """اگر محاسبه هنوز انجام نشده باشد، محاسبه می‌کند."""
    return run_fifo(conn,start,end)

def top_portfolio(conn,start=None,end=None,top_n=200):
    res=run_fifo(conn,start,end)["results"]
    return sorted(res,key=lambda x: abs(x["known_realized_pnl"]),reverse=True)[:top_n]
