"""Outcome-blind, read-only frequency screen for the frozen 1m body-dominance rule."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sqlite3
from pathlib import Path

MINUTE_MS = 60_000
BODY_FRACTION = 0.80
SNAPSHOT_SHA256 = "cac23a3d18be66e226bdf8c3dbc0d08f5c6c185d4f18ed2a8687f08d2b6f67b1"
SNAPSHOT_BYTES = 1_864_249_344
EXPECTED_SYMBOL_COUNT = 100
COMPLETED_THROUGH_MS = 1_794_616_140_000  # 2026-11-14T00:29:00Z


def _file_sha256(database: Path) -> str:
    digest = hashlib.sha256()
    with database.open("rb") as source:
        for block in iter(lambda: source.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _assert_no_sqlite_sidecars(database: Path) -> None:
    for suffix in ("-wal", "-shm", "-journal"):
        sidecar = Path(str(database) + suffix)
        if sidecar.exists():
            raise ValueError(f"SQLite sidecar present; snapshot is not pinned: {sidecar.name}")


def screen(database: Path) -> dict:
    return _screen(database, SNAPSHOT_SHA256, COMPLETED_THROUGH_MS)


def _screen(database: Path, expected_sha256: str | None,
            completed_through_ms: int) -> dict:
    database = database.resolve()
    initial_stat = database.stat()
    if expected_sha256 is not None and initial_stat.st_size != SNAPSHOT_BYTES:
        raise ValueError(f"snapshot size mismatch: {initial_stat.st_size}")
    _assert_no_sqlite_sidecars(database)
    before_sha = _file_sha256(database)
    if expected_sha256 is not None and before_sha != expected_sha256:
        raise ValueError(f"snapshot SHA-256 mismatch: {before_sha}")
    db = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)
    try:
        journal_mode = db.execute("PRAGMA journal_mode").fetchone()[0].lower()
        if journal_mode == "wal":
            raise ValueError("WAL journal mode is not supported for this pinned file snapshot")
        db.execute("BEGIN")
        last_completed_open_exclusive = completed_through_ms - MINUTE_MS + 1
        symbols = [r[0] for r in db.execute(
            "SELECT DISTINCT symbol FROM candles WHERE t_open_ms < ? ORDER BY symbol",
            (last_completed_open_exclusive,),
        )]
        if expected_sha256 is not None and len(symbols) != EXPECTED_SYMBOL_COUNT:
            raise ValueError(f"expected {EXPECTED_SYMBOL_COUNT} symbols, found {len(symbols)}")
        per_symbol = []
        for symbol in symbols:
            rows = db.execute(
                "SELECT t_open_ms,o,h,l,c FROM candles "
                "WHERE symbol=? AND t_open_ms < ? ORDER BY t_open_ms",
                (symbol, last_completed_open_exclusive),
            )
            scheduled = raw = longs = shorts = 0
            cooldown_counts = {10: 0, 20: 0}
            last_signal = {10: -10, 20: -20}
            last_ts = None
            row_count = 0
            for raw_ts, op, high, low, close in rows:
                if type(raw_ts) is not int:
                    raise ValueError(f"non-integer timestamp for {symbol}: {raw_ts!r}")
                ts = raw_ts
                op, high, low, close = map(float, (op, high, low, close))
                if ts % MINUTE_MS:
                    raise ValueError(f"off-grid timestamp for {symbol}: {ts}")
                if last_ts is not None and ts - last_ts != MINUTE_MS:
                    raise ValueError(f"non-contiguous timestamps for {symbol}: {last_ts} -> {ts}")
                if not all(map(math.isfinite, (op, high, low, close))):
                    raise ValueError(f"non-finite OHLC for {symbol} at {ts}")
                if low <= 0 or high < max(op, close, low) or low > min(op, close, high):
                    raise ValueError(f"invalid OHLC for {symbol} at {ts}")

                span = high - low
                if span == 0:
                    last_ts = ts
                    row_count += 1
                    continue
                scheduled += 1
                body = abs(close - op)
                signal = body / span >= BODY_FRACTION and close != op
                if signal:
                    raw += 1
                    longs += int(close > op)
                    shorts += int(close < op)
                    for horizon in (10, 20):
                        if row_count - last_signal[horizon] >= horizon:
                            cooldown_counts[horizon] += 1
                            last_signal[horizon] = row_count
                last_ts = ts
                row_count += 1

            per_symbol.append({
                "symbol": symbol,
                "scheduled_anchors": scheduled,
                "long_events": longs,
                "short_events": shorts,
                "raw_events": raw,
                "raw_coverage": raw / scheduled if scheduled else 0.0,
                "cooldown_events_10m": cooldown_counts[10],
                "cooldown_events_20m": cooldown_counts[20],
            })

        scheduled = sum(x["scheduled_anchors"] for x in per_symbol)
        raw = sum(x["raw_events"] for x in per_symbol)
        cooled10 = sum(x["cooldown_events_10m"] for x in per_symbol)
        cooled20 = sum(x["cooldown_events_20m"] for x in per_symbol)
        active = sum(x["raw_events"] > 0 for x in per_symbol)
        coverage = raw / scheduled if scheduled else 0.0
        return {
            "trial": "micro-candle-phase5-marubozu",
            "database": str(database),
            "database_bytes": database.stat().st_size,
            "database_sha256": before_sha,
            "completed_through_utc": "2026-11-14T00:29:00Z",
            "completed_through_ms": completed_through_ms,
            "rule": "single completed 1m candle; abs(close-open)/(high-low)>=0.80; side=body sign",
            "symbols": len(symbols),
            "active_symbols": active,
            "scheduled_anchors": scheduled,
            "raw_events": raw,
            "raw_coverage": coverage,
            "long_events": sum(x["long_events"] for x in per_symbol),
            "short_events": sum(x["short_events"] for x in per_symbol),
            "cooldown_events_10m": cooled10,
            "cooldown_events_20m": cooled20,
            "gates": {
                "coverage_ge_10pct": coverage >= 0.10,
                "active_symbols_ge_20": active >= 20,
                "nonoverlap_10m_n_ge_200": cooled10 >= 200,
                "nonoverlap_20m_n_ge_200": cooled20 >= 200,
            },
            "decision": "OPEN_REVIEW_BEFORE_OUTCOMES" if coverage >= 0.10 and active >= 20 and cooled10 >= 200 and cooled20 >= 200 else "REJECT_BEFORE_OUTCOMES",
            "outcome_rows_read": 0,
            "target_stop_labels_read": 0,
            "per_symbol": per_symbol,
        }
    finally:
        db.close()
        _assert_no_sqlite_sidecars(database)
        after_sha = _file_sha256(database)
        final_stat = database.stat()
        if before_sha != after_sha or (initial_stat.st_size, initial_stat.st_mtime_ns, initial_stat.st_ino) != (final_stat.st_size, final_stat.st_mtime_ns, final_stat.st_ino):
            raise ValueError("database changed while the read-only screen was running")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("database", type=Path)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    result = screen(args.database)
    output = json.dumps(result, indent=2, sort_keys=True)
    if args.json:
        args.json.write_text(output + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
