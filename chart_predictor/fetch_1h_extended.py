"""Fetch native 1h/4h klines for P7-D; separate from the 1m-resampled P5/P6 DB.

These native bars support strategy-level comparison only, not bar-for-bar
comparison to 60m bars resampled from the project's 1m candle store.
"""
import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from .collector import BASE_URL, _request

ROOT = Path(__file__).parent
DB_PATH = ROOT / "data" / "candles_1h_extended.sqlite"
OUT = ROOT / "data" / "p7d"
DAY = 86_400_000
SCHEMA = """CREATE TABLE IF NOT EXISTS {table}(
 symbol TEXT NOT NULL,t_open_ms INTEGER NOT NULL,o REAL NOT NULL,h REAL NOT NULL,
 l REAL NOT NULL,c REAL NOT NULL,v REAL NOT NULL,quote_v REAL NOT NULL,trades INTEGER NOT NULL,
 PRIMARY KEY(symbol,t_open_ms))"""


def fetch_interval(db, symbol, interval, table, width, start_ms, end_ms, now_ms, session=requests):
    """Page backward by native bar; store only closed bars, idempotently."""
    db.execute(SCHEMA.format(table=table))
    cursor = end_ms - 1
    while cursor >= start_ms:
        rows = _request(session, {"symbol": symbol, "interval": interval,
                                  "endTime": cursor, "limit": 1500})
        if not rows:
            break
        completed = [(symbol, int(r[0]), float(r[1]), float(r[2]), float(r[3]),
                      float(r[4]), float(r[5]), float(r[7]), int(r[8]))
                     for r in rows if start_ms <= int(r[0]) < end_ms and int(r[6]) < now_ms]
        db.executemany(f"INSERT OR IGNORE INTO {table} VALUES(?,?,?,?,?,?,?,?,?)", completed)
        db.commit()
        earliest = min(int(r[0]) for r in rows)
        if earliest <= start_ms or len(rows) < 1500:
            break
        cursor = earliest - 1
        time.sleep(0.08)


def coverage(db, symbols):
    result = {}
    for table in ("candles_60m", "candles_240m"):
        rows = []
        for symbol in symbols:
            first, last, count = db.execute(
                f"SELECT MIN(t_open_ms),MAX(t_open_ms),COUNT(*) FROM {table} WHERE symbol=?",
                (symbol,)).fetchone()
            days = ((last - first) / DAY if first is not None and last is not None else 0.0)
            rows.append({"symbol": symbol, "first_t_open_ms": first,
                         "last_t_open_ms": last, "row_count": count,
                         "actual_days_covered": round(days, 4)})
        result[table] = rows
    return result


def run(days=450):
    symbols = json.loads((ROOT / "data" / "universe_collect.json").read_text())[:50]
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    end_ms = now_ms
    start_ms = end_ms - days * DAY
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    try:
        for table in ("candles_60m", "candles_240m"):
            db.execute(SCHEMA.format(table=table))
        db.commit()
        for i, symbol in enumerate(symbols, 1):
            print(f"[{i}/50] {symbol}", flush=True)
            fetch_interval(db, symbol, "1h", "candles_60m", 3_600_000,
                           start_ms, end_ms, now_ms)
            fetch_interval(db, symbol, "4h", "candles_240m", 14_400_000,
                           start_ms, end_ms, now_ms)
            time.sleep(0.12)
        report = {"requested_start_ms": start_ms, "requested_end_exclusive_ms": end_ms,
                  "requested_days": days, "fetch_time_utc": datetime.now(timezone.utc).isoformat(),
                  "resolution_note": "Native Binance 1h/4h bars; not bar-for-bar comparable to P5/P6 1m-resampled 60m bars.",
                  "coverage": coverage(db, symbols)}
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "coverage.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        return report
    finally:
        db.close()


if __name__ == "__main__":
    run()
