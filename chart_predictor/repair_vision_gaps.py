"""Fetch the audited historical SOL/XRP gaps into a separate patch database.

The original vision_dev.sqlite is never modified. Pages are retained verbatim
with hashes so repairs can be traced to the public Binance endpoint.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE_URL = "https://fapi.binance.com/fapi/v1/klines"
GAPS = (
    ("SOLUSDT", 1645833600000, 1646092800000),  # 2022-02-26 through 2022-03-01
    ("XRPUSDT", 1645833600000, 1646092800000),
    ("SOLUSDT", 1648771200000, 1648944000000),  # 2022-04-01 through 2022-04-03
    ("XRPUSDT", 1648771200000, 1648944000000),
)
STEP = 60_000
PAGE_LIMIT = 1500
DEFAULT_OUTPUT = Path(__file__).parent / "data" / "vision_gap_repair.sqlite"


def fetch_pages(symbol: str, start_ms: int, end_ms: int, opener=urlopen,
                sleep=time.sleep) -> tuple[list, list[tuple[dict, bytes]]]:
    """Fetch every 1m row in [start_ms, end_ms), retaining source page bytes."""
    rows, cursor, pages = [], start_ms, []
    while cursor < end_ms:
        params = urlencode({"symbol": symbol, "interval": "1m", "startTime": cursor,
                            "endTime": end_ms - 1, "limit": PAGE_LIMIT})
        request = Request(f"{BASE_URL}?{params}", headers={"User-Agent": "Coin_Trade-data-audit/1"})
        with opener(request, timeout=30) as response:
            payload = response.read()
        batch = json.loads(payload)
        if not isinstance(batch, list):
            raise RuntimeError(f"Unexpected Binance response for {symbol}: {payload[:200]!r}")
        if not batch:
            break
        pages.append(({"symbol": symbol, "request_start_ms": cursor,
                       "request_end_ms_exclusive": end_ms,
                       "retrieved_utc": datetime.now(timezone.utc).isoformat(),
                       "sha256": hashlib.sha256(payload).hexdigest(),
                       "row_count": len(batch)}, payload))
        rows.extend(batch)
        next_cursor = int(batch[-1][0]) + STEP
        if next_cursor <= cursor:
            raise RuntimeError(f"Binance pagination stalled for {symbol} at {cursor}")
        cursor = next_cursor
        if len(batch) == PAGE_LIMIT:
            sleep(0.15)
    expected = (end_ms - start_ms) // STEP
    opens = [int(row[0]) for row in rows]
    if opens != list(range(start_ms, end_ms, STEP)):
        raise RuntimeError(
            f"Incomplete/non-contiguous response for {symbol}: expected {expected}, got {len(opens)}"
        )
    for row in rows:
        if (int(row[6]) != int(row[0]) + STEP - 1
                or float(row[1]) <= 0 or float(row[2]) <= 0
                or float(row[3]) <= 0 or float(row[4]) <= 0
                or float(row[2]) < max(float(row[1]), float(row[4]))
                or float(row[3]) > min(float(row[1]), float(row[4]))
                or float(row[5]) < 0 or float(row[7]) < 0 or int(row[8]) < 0):
            raise RuntimeError(f"Invalid OHLCV row returned for {symbol}: {row!r}")
    return rows, pages


def _open_database(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.executescript("""
      CREATE TABLE IF NOT EXISTS candles(
        symbol TEXT NOT NULL, open_ms INTEGER NOT NULL, open REAL NOT NULL,
        high REAL NOT NULL, low REAL NOT NULL, close REAL NOT NULL,
        volume REAL NOT NULL, close_ms INTEGER NOT NULL, quote_volume REAL NOT NULL,
        trade_count INTEGER NOT NULL, taker_buy_base REAL NOT NULL,
        taker_buy_quote REAL NOT NULL, PRIMARY KEY(symbol,open_ms));
      CREATE TABLE IF NOT EXISTS repair_pages(
        sha256 TEXT PRIMARY KEY, symbol TEXT NOT NULL, request_start_ms INTEGER NOT NULL,
        request_end_ms_exclusive INTEGER NOT NULL, retrieved_utc TEXT NOT NULL,
        row_count INTEGER NOT NULL, payload BLOB NOT NULL);
    """)
    return db


def repair(output: str | Path = DEFAULT_OUTPUT, opener=urlopen,
           sleep=time.sleep) -> dict:
    """Idempotently fetch and persist the predefined gaps outside the source DB."""
    path = Path(output)
    db = _open_database(path)
    expected_total = 0
    try:
        for symbol, start_ms, end_ms in GAPS:
            expected = (end_ms - start_ms) // STEP
            expected_total += expected
            existing = db.execute(
                "SELECT COUNT(*) FROM candles WHERE symbol=? AND open_ms>=? AND open_ms<?",
                (symbol, start_ms, end_ms),
            ).fetchone()[0]
            if existing == expected:
                continue
            if existing:
                raise RuntimeError(f"Partial existing patch for {symbol} {start_ms}..{end_ms}")
            all_rows, pages = fetch_pages(symbol, start_ms, end_ms, opener=opener, sleep=sleep)
            for meta, payload in pages:
                db.execute("INSERT OR IGNORE INTO repair_pages VALUES(?,?,?,?,?,?,?)",
                           (meta["sha256"], meta["symbol"], meta["request_start_ms"],
                            meta["request_end_ms_exclusive"], meta["retrieved_utc"],
                            meta["row_count"], payload))
            db.executemany("INSERT INTO candles VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", [
                (symbol, int(row[0]), float(row[1]), float(row[2]), float(row[3]),
                 float(row[4]), float(row[5]), int(row[6]), float(row[7]),
                 int(row[8]), float(row[9]), float(row[10])) for row in all_rows
            ])
            db.commit()
        actual = db.execute("SELECT COUNT(*) FROM candles").fetchone()[0]
        pages = db.execute("SELECT COUNT(*) FROM repair_pages").fetchone()[0]
        if actual != expected_total:
            raise RuntimeError(f"Patch row count mismatch: expected {expected_total}, found {actual}")
        return {"database": str(path.resolve()), "rows": actual,
                "expected_rows": expected_total, "source_page_count": pages,
                "source": BASE_URL, "status": "complete"}
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(repair(args.output), indent=2))


if __name__ == "__main__":
    main()
