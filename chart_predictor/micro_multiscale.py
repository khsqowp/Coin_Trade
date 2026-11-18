"""Label-blind 3m/5m frequency screen for frozen micro-candle rules."""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

MINUTE_MS = 60_000
SIZES = (3, 5)
HORIZONS = (10, 20)
RULES = ("body_dominance", "sweep_reclaim")
EXPECTED_BYTES = 1_864_249_344
EXPECTED_SHA256 = "cac23a3d18be66e226bdf8c3dbc0d08f5c6c185d4f18ed2a8687f08d2b6f67b1"
EXPECTED_SYMBOLS = 100
CUTOFF_MS = 1_794_616_140_000
PREREGISTRATION = Path(__file__).resolve().parents[1] / "docs/research/micro-candle-phase7-multiscale-prereg-2026-11-18.md"
FOLDS = (
    (1_784_196_600_000, 1_786_982_400_000),
    (1_786_982_400_000, 1_789_056_000_000),
    (1_789_056_000_000, 1_791_129_600_000),
    (1_791_129_600_000, 1_793_203_200_000),
    (1_793_203_200_000, CUTOFF_MS),
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def aggregate_bars(open_ms, open_, high, low, close, size_minutes: int) -> dict[str, np.ndarray]:
    """Aggregate only exact, complete, valid UTC-epoch minute buckets."""
    width = size_minutes * MINUTE_MS
    if size_minutes not in SIZES:
        raise ValueError("size_minutes must be 3 or 5")
    t = np.asarray(open_ms, dtype=np.int64)
    op, hi, lo, cl = (np.asarray(x, dtype=np.float64) for x in (open_, high, low, close))
    if any(len(x) != len(t) for x in (op, hi, lo, cl)):
        raise ValueError("timestamp and OHLC arrays must have equal lengths")
    if len(t) == 0:
        return {k: np.empty(0, dtype=d) for k, d in (
            ("open_ms", np.int64), ("open", np.float64), ("high", np.float64),
            ("low", np.float64), ("close", np.float64))}
    if np.any(t % MINUTE_MS) or np.any(np.diff(t) <= 0):
        raise ValueError("raw timestamps must be strictly increasing on the minute grid")

    valid = (np.isfinite(op) & np.isfinite(hi) & np.isfinite(lo) & np.isfinite(cl)
             & (lo > 0) & (hi >= np.maximum.reduce([op, cl, lo]))
             & (lo <= np.minimum.reduce([op, cl, hi])))
    bucket = (t // width) * width
    starts = np.r_[0, np.flatnonzero(np.diff(bucket)) + 1]
    ends = np.r_[starts[1:], len(t)]
    counts = ends - starts
    full = (counts == size_minutes)
    full &= t[starts] == bucket[starts]
    full &= t[ends - 1] == bucket[starts] + (size_minutes - 1) * MINUTE_MS
    bad_prefix = np.r_[0, np.cumsum(~valid, dtype=np.int64)]
    full &= (bad_prefix[ends] - bad_prefix[starts]) == 0
    if not np.any(full):
        return {k: np.empty(0, dtype=d) for k, d in (
            ("open_ms", np.int64), ("open", np.float64), ("high", np.float64),
            ("low", np.float64), ("close", np.float64))}
    all_high = np.maximum.reduceat(hi, starts)
    all_low = np.minimum.reduceat(lo, starts)
    return {
        "open_ms": bucket[starts[full]].astype(np.int64),
        "open": op[starts[full]],
        "high": all_high[full],
        "low": all_low[full],
        "close": cl[ends[full] - 1],
    }


def signal_masks(open_ms, open_, high, low, close, interval_ms: int):
    """Return signed body-dominance and sweep/reclaim signals per aggregate bar."""
    t = np.asarray(open_ms, dtype=np.int64)
    op, hi, lo, cl = (np.asarray(x, dtype=np.float64) for x in (open_, high, low, close))
    body = np.zeros(len(t), dtype=np.int8)
    span = hi - lo
    fraction = np.divide(np.abs(cl - op), span, out=np.zeros(len(t)), where=span > 0)
    body[(span > 0) & (fraction >= 0.80) & (cl > op)] = 1
    body[(span > 0) & (fraction >= 0.80) & (cl < op)] = -1

    sweep = np.zeros(len(t), dtype=np.int8)
    if len(t) > 1:
        adjacent = np.diff(t) == interval_ms
        midpoint = (hi[:-1] + lo[:-1]) / 2
        long = (adjacent & (lo[1:] < lo[:-1]) & (hi[1:] <= hi[:-1])
                & (cl[1:] > midpoint) & (cl[1:] < hi[:-1]))
        short = (adjacent & (hi[1:] > hi[:-1]) & (lo[1:] >= lo[:-1])
                 & (cl[1:] < midpoint) & (cl[1:] > lo[:-1]))
        sweep[1:][long] = 1
        sweep[1:][short] = -1
    return body, sweep


def fold_indices(availability_ms, boundaries) -> np.ndarray:
    """Assign timestamps to half-open folds [start,end); -1 is outside."""
    values = np.asarray(availability_ms, dtype=np.int64)
    edges = np.asarray(boundaries, dtype=np.int64)
    result = np.searchsorted(edges, values, side="right") - 1
    valid = (result >= 0) & (result < len(edges) - 1)
    valid &= values < edges[np.clip(result + 1, 0, len(edges) - 1)]
    return np.where(valid, result, -1).astype(np.int8)


def nonoverlap_indices(indexes, availability_ms, horizon: int, interval_ms: int) -> np.ndarray:
    """Greedy earliest-signal selector; exact prior-window end is admissible."""
    candidates = np.asarray(indexes, dtype=np.int64)
    availability = np.asarray(availability_ms, dtype=np.int64)
    selected: list[int] = []
    cursor = 0
    while cursor < len(candidates):
        anchor = int(candidates[cursor])
        selected.append(anchor)
        next_available = availability[anchor] + horizon * interval_ms
        cursor = int(np.searchsorted(availability[candidates], next_available, side="left"))
    return np.asarray(selected, dtype=np.int64)


def _signal_stats(signal, eligible, availability, boundaries, interval_ms):
    fold = fold_indices(availability, boundaries)
    result = []
    for fold_no, (start, end) in enumerate(zip(boundaries[:-1], boundaries[1:]), 1):
        in_fold = (fold == fold_no - 1)
        eligible_n = int(np.sum(eligible & in_fold))
        indexes = np.flatnonzero((signal != 0) & in_fold)
        side_counts = {"long": int(np.sum(signal[indexes] > 0)),
                       "short": int(np.sum(signal[indexes] < 0))}
        cells = {}
        for horizon in HORIZONS:
            chosen = nonoverlap_indices(indexes, availability, horizon, interval_ms)
            cells[str(horizon)] = int(len(chosen))
        result.append({"fold": fold_no, "start_ms": int(start), "end_ms": int(end),
                       "eligible_anchors": eligible_n, "signals": int(len(indexes)),
                       "coverage": len(indexes) / eligible_n if eligible_n else None,
                       **side_counts, "nonoverlap": cells})
    return result


def frequency_scan(database: Path) -> dict:
    """Run outcome-label-blind frequency counts on a pinned read-only snapshot."""
    database = database.resolve()
    if database.stat().st_size != EXPECTED_BYTES:
        raise ValueError("pinned source database size mismatch")
    for suffix in ("-wal", "-shm", "-journal"):
        if Path(f"{database}{suffix}").exists():
            raise ValueError(f"SQLite sidecar exists: {suffix}")
    before_hash = _sha256(database)
    if before_hash != EXPECTED_SHA256:
        raise ValueError("pinned source database SHA-256 mismatch")

    db = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)
    try:
        if db.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal":
            raise ValueError("WAL mode is not accepted for the pinned snapshot")
        db.execute("BEGIN")
        symbols = [row[0] for row in db.execute(
            "SELECT DISTINCT symbol FROM candles WHERE t_open_ms + 60000 <= ? ORDER BY symbol",
            (CUTOFF_MS,))]
        if len(symbols) != EXPECTED_SYMBOLS:
            raise ValueError(f"expected {EXPECTED_SYMBOLS} symbols, got {len(symbols)}")

        bounds = np.array([FOLDS[0][0], *(end for _, end in FOLDS)], dtype=np.int64)
        details = {rule: {str(size): [] for size in SIZES} for rule in RULES}
        totals = {rule: {str(size): {"eligible": 0, "signals": 0,
                                     "long": 0, "short": 0,
                                     "nonoverlap": {str(h): 0 for h in HORIZONS},
                                     "symbols": {str(h): set() for h in HORIZONS}}
                         for size in SIZES} for rule in RULES}
        for symbol_number, symbol in enumerate(symbols, 1):
            raw = pd.read_sql_query(
                "SELECT t_open_ms,o,h,l,c FROM candles WHERE symbol=? AND t_open_ms+60000<=? ORDER BY t_open_ms",
                db, params=(symbol, CUTOFF_MS))
            if db.execute("SELECT COUNT(*) FROM candles WHERE symbol=? AND t_open_ms+60000<=? "
                          "AND typeof(t_open_ms)!='integer'", (symbol, CUTOFF_MS)).fetchone()[0]:
                raise ValueError(f"non-integer timestamps in {symbol}")
            t = raw.t_open_ms.to_numpy(np.int64)
            raw_o, raw_h, raw_l, raw_c = (raw[k].to_numpy(np.float64) for k in ("o", "h", "l", "c"))
            if len(t) and np.any(np.diff(t) <= 0):
                raise ValueError(f"duplicate or unordered minute rows in {symbol}")
            for size in SIZES:
                bars = aggregate_bars(t, raw_o, raw_h, raw_l, raw_c, size)
                interval_ms = size * MINUTE_MS
                availability = bars["open_ms"] + interval_ms
                eligible = bars["high"] > bars["low"]
                body, sweep = signal_masks(
                    bars["open_ms"], bars["open"], bars["high"], bars["low"], bars["close"], interval_ms)
                for rule, signal in (("body_dominance", body), ("sweep_reclaim", sweep)):
                    stats = _signal_stats(signal, eligible, availability, bounds, interval_ms)
                    for horizon in HORIZONS:
                        chosen = [n for n in range(len(stats))
                                  if stats[n]["nonoverlap"][str(horizon)] > 0]
                        for fold_index in chosen:
                            indexes = np.flatnonzero((signal != 0)
                                                     & (fold_indices(availability, bounds) == fold_index))
                            selected = nonoverlap_indices(indexes, availability, horizon, interval_ms)
                            if len(selected):
                                totals[rule][str(size)]["symbols"][str(horizon)].add(symbol)
                        totals[rule][str(size)]["nonoverlap"][str(horizon)] += sum(
                            fold["nonoverlap"][str(horizon)] for fold in stats)
                    totals[rule][str(size)]["eligible"] += sum(x["eligible_anchors"] for x in stats)
                    totals[rule][str(size)]["signals"] += sum(x["signals"] for x in stats)
                    totals[rule][str(size)]["long"] += sum(x["long"] for x in stats)
                    totals[rule][str(size)]["short"] += sum(x["short"] for x in stats)
                    details[rule][str(size)].append({"symbol": symbol, "folds": stats})
            print(f"frequency {symbol_number}/{len(symbols)} {symbol}", flush=True)
    finally:
        db.close()

    after_hash = _sha256(database)
    if before_hash != after_hash or database.stat().st_size != EXPECTED_BYTES:
        raise ValueError("source snapshot changed during frequency scan")
    for rule in RULES:
        for size in SIZES:
            cell = totals[rule][str(size)]
            cell["coverage"] = cell["signals"] / cell["eligible"] if cell["eligible"] else None
            cell["horizons"] = {}
            for horizon in HORIZONS:
                count = cell["nonoverlap"][str(horizon)]
                symbols_n = len(cell["symbols"][str(horizon)])
                cell["horizons"][str(horizon)] = {
                    "nonoverlap_n": count, "nonoverlap_symbols": symbols_n,
                    "frequency_gate_pass": count >= 200 and symbols_n >= 20,
                }
            cell["symbols"] = {h: len(v) for h, v in cell["symbols"].items()}

    source_hash = _sha256(Path(__file__).resolve())
    return {
        "protocol": "micro-candle-phase7-multiscale-frequency",
        "database": str(database), "database_bytes": EXPECTED_BYTES,
        "database_sha256": after_hash, "completed_through_utc": "2026-11-14T00:29:00Z",
        "aggregate_sizes_minutes": list(SIZES), "horizons_aggregate_bars": list(HORIZONS),
        "symbols": symbols, "symbol_count": len(symbols), "folds": [
            {"fold": i + 1, "start_ms": start, "end_ms": end}
            for i, (start, end) in enumerate(FOLDS)],
        "totals": totals, "per_symbol_fold": details,
        "outcome_rows_read": 0, "target_stop_labels_read": 0,
        "source_sha256": source_hash,
        "preregistration_sha256": _sha256(PREREGISTRATION),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = frequency_scan(args.db)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({rule: report["totals"][rule] for rule in RULES}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
