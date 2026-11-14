"""Resumable SQLite collector for completed Binance USDT-M 1m candles."""
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
import requests

BASE_URL = "https://fapi.binance.com"
DB_PATH = Path(__file__).parent / "data" / "candles.sqlite"
SCHEMA = """CREATE TABLE IF NOT EXISTS candles(
 symbol TEXT NOT NULL,t_open_ms INTEGER NOT NULL,o REAL NOT NULL,h REAL NOT NULL,
 l REAL NOT NULL,c REAL NOT NULL,v REAL NOT NULL,quote_v REAL NOT NULL,trades INTEGER NOT NULL,
 PRIMARY KEY(symbol,t_open_ms))"""


def connect(path=DB_PATH):
    """Open/create the candle database."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.execute(SCHEMA)
    return db


def _request(session, params, sleep=time.sleep, retries=8):
    """Request one page, respecting used weight and server retry instructions."""
    for attempt in range(retries):
        response = session.get(f"{BASE_URL}/fapi/v1/klines", params=params, timeout=30)
        if response.status_code in (418, 429):
            delay = float(response.headers.get("Retry-After", min(2 ** attempt, 60)))
            sleep(max(delay, 1.0))
            continue
        response.raise_for_status()
        used = int(response.headers.get("X-MBX-USED-WEIGHT-1M", "0"))
        if used >= 1050:
            sleep(60)
        elif used >= 900:
            sleep(10)
        return response.json()
    raise RuntimeError("Binance rate limit retries exhausted")


def _existing_bounds(db, symbol):
    row = db.execute("SELECT MIN(t_open_ms),MAX(t_open_ms) FROM candles WHERE symbol=?", (symbol,)).fetchone()
    return row


def _missing_ranges(db, symbol, start_ms, end_ms):
    """Return absent 1m-open intervals in the half-open requested window."""
    opens = [row[0] for row in db.execute(
        "SELECT t_open_ms FROM candles WHERE symbol=? AND t_open_ms>=? AND t_open_ms<? ORDER BY t_open_ms",
        (symbol, start_ms, end_ms))]
    gaps, cursor = [], start_ms
    for stamp in opens:
        if stamp > cursor:
            gaps.append((cursor, stamp))
        cursor = max(cursor, stamp + 60_000)
    if cursor < end_ms:
        gaps.append((cursor, end_ms))
    return gaps


def _store(db, symbol, rows, now_ms, start_ms=None, end_ms=None):
    """Insert completed rows from one requested range; return actual inserts."""
    completed = [(symbol, int(r[0]), float(r[1]), float(r[2]), float(r[3]),
                  float(r[4]), float(r[5]), float(r[7]), int(r[8]))
                 for r in rows if int(r[6]) < now_ms
                 and (start_ms is None or int(r[0]) >= start_ms)
                 and (end_ms is None or int(r[0]) < end_ms)]
    before = db.total_changes
    db.executemany("INSERT OR IGNORE INTO candles VALUES(?,?,?,?,?,?,?,?,?)", completed)
    db.commit()
    return db.total_changes - before


def _fetch_range(db, symbol, start_ms, end_ms, now_ms, session, sleep):
    """Fetch one missing half-open interval page by page."""
    cursor, inserted = start_ms, 0
    while cursor < end_ms:
        page = _request(session, {"symbol": symbol, "interval": "1m", "startTime": cursor,
                                 "endTime": end_ms - 1, "limit": 1500}, sleep)
        if not page:
            break
        inserted += _store(db, symbol, page, now_ms, start_ms, end_ms)
        next_cursor = int(page[-1][0]) + 60_000
        if next_cursor <= cursor:
            break
        cursor = next_cursor
        if len(page) < 1500:
            break
    return inserted


def collect_symbol(symbol, start_ms, end_ms, db=None, session=requests, sleep=time.sleep):
    """Fill every missing leading, internal, or trailing range idempotently."""
    owned = db is None
    db = db or connect()
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    start_ms, end_ms = _minute_ceiling(int(start_ms)), min(_minute_ceiling(int(end_ms)), now_ms // 60_000 * 60_000)
    try:
        ranges = _missing_ranges(db, symbol, start_ms, end_ms)
        return sum(_fetch_range(db, symbol, left, right, now_ms, session, sleep)
                   for left, right in ranges)
    finally:
        if owned:
            db.close()


def _minute_ceiling(timestamp_ms):
    """Round an inclusive time boundary up to the next 1m candle open."""
    return (timestamp_ms + 59_999) // 60_000 * 60_000


def verify_symbol(db, symbol, start_ms, end_ms, now_ms=None):
    """Summarize requested-window coverage and duplicate rows for one symbol."""
    now_ms = now_ms or int(datetime.now(timezone.utc).timestamp() * 1000)
    start_ms = _minute_ceiling(int(start_ms))
    end_ms = min(_minute_ceiling(int(end_ms)), now_ms // 60_000 * 60_000)
    rows = [row[0] for row in db.execute(
        "SELECT t_open_ms FROM candles WHERE symbol=? AND t_open_ms>=? AND t_open_ms<? ORDER BY t_open_ms",
        (symbol, start_ms, end_ms))]
    gaps = _missing_ranges(db, symbol, start_ms, end_ms)
    duplicates = db.execute("SELECT COUNT(*)-COUNT(DISTINCT t_open_ms) FROM candles "
                             "WHERE symbol=? AND t_open_ms>=? AND t_open_ms<?",
                             (symbol, start_ms, end_ms)).fetchone()[0]
    inner = sum(1 for a, b in zip(rows, rows[1:]) if b - a > 60_000)
    missing = sum((right - left) // 60_000 for left, right in gaps)
    return {"symbol": symbol, "row_count": len(rows), "first_t_open_ms": rows[0] if rows else None,
            "last_t_open_ms": rows[-1] if rows else None, "internal_gaps": inner,
            "missing_minutes": missing, "duplicates": int(duplicates)}


def collect_symbols(symbols, days=30, **kwargs):
    """Collect all symbols for the requested trailing duration."""
    end = int(datetime.now(timezone.utc).timestamp() * 1000)
    start = end - int(days * 86_400_000)
    return {symbol: collect_symbol(symbol, start, end, **kwargs) for symbol in symbols}
