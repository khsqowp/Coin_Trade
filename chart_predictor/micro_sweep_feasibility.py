"""Label-blind frequency screen for the frozen 2-candle sweep/reclaim rule."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sqlite3
from pathlib import Path

import numpy as np

from chart_predictor.micro_maru_feasibility import (
    COMPLETED_THROUGH_MS,
    EXPECTED_SYMBOL_COUNT,
    MINUTE_MS,
    SNAPSHOT_BYTES,
    SNAPSHOT_SHA256,
    _assert_no_sqlite_sidecars,
    _file_sha256,
)
from chart_predictor.micro_maru_m2 import FOLDS, _nonoverlap_indexes, _utc_ms


def _valid(op: float, high: float, low: float, close: float) -> bool:
    return (all(map(math.isfinite, (op, high, low, close))) and low > 0
            and high >= max(op, close, low) and low <= min(op, close, high))


def candidate_side(first: tuple[float, ...], second: tuple[float, ...]) -> int:
    """Return LONG=1, SHORT=-1, or 0 for a frozen adjacent-bar pattern."""
    o1, h1, l1, c1 = first
    o2, h2, l2, c2 = second
    if not (_valid(o1, h1, l1, c1) and _valid(o2, h2, l2, c2)):
        return 0
    midpoint = (h1 + l1) / 2.0
    if l2 < l1 and h2 <= h1 and midpoint < c2 < h1:
        return 1
    if h2 > h1 and l2 >= l1 and l1 < c2 < midpoint:
        return -1
    return 0


def run(database: Path) -> dict:
    database = database.resolve()
    source_paths = {
        "frequency_screen": Path(__file__).resolve(),
        "timestamp_and_nonoverlap_helper": Path(__file__).with_name("micro_maru_m2.py").resolve(),
    }
    source_hashes = {key: hashlib.sha256(path.read_bytes()).hexdigest()
                     for key, path in source_paths.items()}
    initial_stat = database.stat()
    if initial_stat.st_size != SNAPSHOT_BYTES:
        raise ValueError(f"snapshot size mismatch: {initial_stat.st_size}")
    _assert_no_sqlite_sidecars(database)
    before_sha = _file_sha256(database)
    if before_sha != SNAPSHOT_SHA256:
        raise ValueError(f"snapshot SHA-256 mismatch: {before_sha}")
    db = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)
    fold_bounds = [(_utc_ms(start), _utc_ms(end)) for start, end in FOLDS]
    per_horizon = {h: {i: {"eligible_pairs": 0, "signals": 0, "long": 0,
                           "short": 0, "nonoverlap_n": 0,
                           "symbols": set()} for i in range(len(FOLDS))}
                   for h in (10, 20)}
    per_symbol = []
    try:
        if db.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal":
            raise ValueError("WAL journal mode is not supported")
        db.execute("BEGIN")
        cutoff_exclusive = COMPLETED_THROUGH_MS - MINUTE_MS + 1
        symbols = [r[0] for r in db.execute(
            "SELECT DISTINCT symbol FROM candles WHERE t_open_ms < ? ORDER BY symbol",
            (cutoff_exclusive,),
        )]
        if len(symbols) != EXPECTED_SYMBOL_COUNT:
            raise ValueError(f"expected {EXPECTED_SYMBOL_COUNT} symbols, found {len(symbols)}")
        for symbol in symbols:
            malformed_timestamps = db.execute(
                "SELECT COUNT(*) FROM candles WHERE symbol=? "
                "AND (CAST(t_open_ms AS REAL) IS NULL OR CAST(t_open_ms AS REAL) < ?) "
                "AND typeof(t_open_ms) != 'integer'",
                (symbol, cutoff_exclusive),
            ).fetchone()[0]
            if malformed_timestamps:
                raise ValueError(f"non-integer timestamps for {symbol}")
            rows = db.execute(
                "SELECT t_open_ms,o,h,l,c FROM candles WHERE symbol=? AND t_open_ms < ? ORDER BY t_open_ms",
                (symbol, cutoff_exclusive),
            )
            previous = None
            timestamps = []
            sides = []
            pair_validity = []
            for raw_ts, o, h, low, c in rows:
                if type(raw_ts) is not int:
                    raise ValueError(f"non-integer timestamp for {symbol}: {raw_ts!r}")
                ts = raw_ts
                if ts % MINUTE_MS:
                    previous = None
                    continue
                try:
                    current = (float(o), float(h), float(low), float(c))
                except (TypeError, ValueError):
                    previous = None
                    continue
                if previous is not None and ts - previous[0] == MINUTE_MS:
                    pair_is_valid = (_valid(*previous[1]) and _valid(*current))
                    side = candidate_side(previous[1], current) if pair_is_valid else 0
                    timestamps.append(ts)
                    sides.append(side)
                    pair_validity.append(pair_is_valid)
                elif previous is not None and ts <= previous[0]:
                    previous = None
                    continue
                previous = (ts, current)

            ts_array = np.asarray(timestamps, dtype="int64")
            signal_times = ts_array + MINUTE_MS  # bar2 close: exact time the signal becomes observable
            side_array = np.asarray(sides, dtype="int8")
            pair_valid = np.asarray(pair_validity, dtype=bool)
            symbol_result = {"symbol": symbol,
                             "snapshot_signals": int((side_array != 0).sum()),
                             "snapshot_long": int((side_array == 1).sum()),
                             "snapshot_short": int((side_array == -1).sum()), "folds": {}}
            for fi, (start_ms, end_ms) in enumerate(fold_bounds):
                indexes = np.flatnonzero(
                    (side_array != 0) & (signal_times >= start_ms) & (signal_times < end_ms))
                anchors = np.flatnonzero(pair_valid & (signal_times >= start_ms) & (signal_times < end_ms))
                symbol_fold = {
                    "eligible_pairs": len(anchors), "signals": len(indexes),
                    "long": int((side_array[indexes] == 1).sum()),
                    "short": int((side_array[indexes] == -1).sum()),
                }
                for horizon in (10, 20):
                    counts = per_horizon[horizon][fi]
                    counts["eligible_pairs"] += len(anchors)
                    if len(indexes):
                        counts["signals"] += len(indexes)
                        counts["long"] += int((side_array[indexes] == 1).sum())
                        counts["short"] += int((side_array[indexes] == -1).sum())
                        selected = _nonoverlap_indexes(indexes.astype("int64"), horizon, signal_times)
                        counts["nonoverlap_n"] += len(selected)
                        counts["symbols"].add(symbol)
                        symbol_fold[f"nonoverlap_{horizon}m"] = len(selected)
                    else:
                        symbol_fold[f"nonoverlap_{horizon}m"] = 0
                symbol_result["folds"][str(fi + 1)] = symbol_fold
            per_symbol.append(symbol_result)

        summaries = {}
        for horizon in (10, 20):
            fold_rows = []
            for fi, (start, end) in enumerate(FOLDS):
                counts = per_horizon[horizon][fi]
                summary = {
                    "fold": fi + 1, "start_utc": start, "end_utc": end,
                    "eligible_pairs": counts["eligible_pairs"],
                    "signals": counts["signals"], "long": counts["long"], "short": counts["short"],
                    "coverage": counts["signals"] / counts["eligible_pairs"] if counts["eligible_pairs"] else None,
                    "nonoverlap_n": counts["nonoverlap_n"],
                    "nonoverlap_symbols": len(counts["symbols"]),
                }
                fold_rows.append(summary)
            total_signals = sum(x["signals"] for x in fold_rows)
            total_eligible = sum(x["eligible_pairs"] for x in fold_rows)
            total_nonoverlap = sum(x["nonoverlap_n"] for x in fold_rows)
            symbols_with_events = len(set().union(*(x["symbols"] for x in per_horizon[horizon].values())))
            passed = total_nonoverlap >= 200 and symbols_with_events >= 20
            summaries[f"{horizon}m"] = {
                "folds": fold_rows, "eligible_pairs": total_eligible,
                "signals": total_signals,
                "coverage": total_signals / total_eligible if total_eligible else None,
                "nonoverlap_n": total_nonoverlap,
                "nonoverlap_symbols": symbols_with_events,
                "frequency_gate_pass": passed,
                "decision": "READY_FOR_OUTCOME_PREREG" if passed else "REJECT_INSUFFICIENT_FREQUENCY",
            }
        return {
            "protocol": "micro-candle-phase6-sweep-reclaim-frequency-only",
            "database_sha256": before_sha, "database_bytes": initial_stat.st_size,
            "implementation_source_sha256": source_hashes,
            "completed_through_utc": "2026-11-14T00:29:00Z", "symbols": len(symbols),
            "outcome_rows_read": 0, "target_stop_labels_read": 0,
            "candidate": "bar2 sweeps exactly one bar1 extreme, then closes inside bar1 range and beyond its midpoint; entry and outcomes not evaluated",
            "horizons": summaries, "per_symbol": per_symbol,
        }
    finally:
        db.close()
        _assert_no_sqlite_sidecars(database)
        after_sha = _file_sha256(database)
        final_stat = database.stat()
        if before_sha != after_sha or (initial_stat.st_size, initial_stat.st_mtime_ns, initial_stat.st_ino) != (final_stat.st_size, final_stat.st_mtime_ns, final_stat.st_ino):
            raise ValueError("database changed during label-blind frequency screen")
        if source_hashes != {key: hashlib.sha256(path.read_bytes()).hexdigest()
                             for key, path in source_paths.items()}:
            raise ValueError("frequency screen source changed during execution")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    report = run(args.db)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({h: {k: v for k, v in item.items() if k != "folds"}
                      for h, item in report["horizons"].items()}, indent=2))


if __name__ == "__main__":
    main()
