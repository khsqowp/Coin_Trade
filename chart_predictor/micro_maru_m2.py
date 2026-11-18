"""Fixed one-minute body-dominance target-first evaluation on a pinned SQLite snapshot."""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

from chart_predictor.micro_candle_m2 import (
    SEED,
    add_agg,
    empty_agg,
    sha_side,
    score_chunk,
    score_signal,
    summarize,
)
from chart_predictor.micro_maru_feasibility import (
    COMPLETED_THROUGH_MS,
    EXPECTED_SYMBOL_COUNT,
    MINUTE_MS,
    SNAPSHOT_BYTES,
    SNAPSHOT_SHA256,
    _assert_no_sqlite_sidecars,
    _file_sha256,
)

ATR_N = 14
CHUNK_SIZE = 25_000
FOLDS = [
    ("2026-07-16T18:10:00Z", "2026-08-10T00:00:00Z"),
    ("2026-08-10T00:00:00Z", "2026-09-03T00:00:00Z"),
    ("2026-09-03T00:00:00Z", "2026-09-27T00:00:00Z"),
    ("2026-09-27T00:00:00Z", "2026-10-21T00:00:00Z"),
    ("2026-10-21T00:00:00Z", "2026-11-14T00:29:00Z"),
]


def _utc_ms(value: str) -> int:
    return int(pd.Timestamp(value).timestamp() * 1000)


def _source_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _signal_from_ohlc(open_: np.ndarray, high: np.ndarray,
                      low: np.ndarray, close: np.ndarray) -> np.ndarray:
    span = high - low
    body = close - open_
    signal = np.zeros(len(close), dtype=np.int8)
    valid = (np.isfinite(open_) & np.isfinite(high) & np.isfinite(low)
             & np.isfinite(close) & (span > 0))
    dominant = valid & (np.abs(body) / np.where(span > 0, span, 1.0) >= 0.80)
    signal[dominant & (body > 0)] = 1
    signal[dominant & (body < 0)] = -1
    return signal


def _load_symbol(db: sqlite3.Connection, symbol: str, cutoff_ms: int):
    frame = pd.read_sql_query(
        "SELECT t_open_ms AS open_ms,o, h,l,c FROM candles "
        "WHERE symbol=? AND t_open_ms < ? ORDER BY t_open_ms",
        db,
        params=(symbol, cutoff_ms - MINUTE_MS + 1),
    )
    non_integer_timestamps = db.execute(
        "SELECT COUNT(*) FROM candles WHERE symbol=? AND CAST(t_open_ms AS REAL) < ? "
        "AND typeof(t_open_ms) != 'integer'",
        (symbol, cutoff_ms - MINUTE_MS + 1),
    ).fetchone()[0]
    if non_integer_timestamps:
        raise ValueError(f"non-integer timestamps in frozen input for {symbol}")
    t = frame.open_ms.to_numpy(np.int64)
    o, h, l, c = (frame[k].to_numpy(np.float64) for k in ("o", "h", "l", "c"))
    if not len(t):
        return t, o, h, l, c, np.empty(0), np.empty(0, dtype=np.int8), np.empty(0, dtype=bool)
    valid = (np.isfinite(o) & np.isfinite(h) & np.isfinite(l) & np.isfinite(c)
             & (l > 0) & (h >= np.maximum.reduce([o, c, l]))
             & (l <= np.minimum.reduce([o, c, h])))
    timestamp_valid = (t % MINUTE_MS) == 0
    contiguous = np.r_[False, (np.diff(t) == MINUTE_MS) & timestamp_valid[1:] & timestamp_valid[:-1]]

    tr = np.maximum(h - l, np.maximum(np.abs(h - np.r_[np.nan, c[:-1]]),
                                      np.abs(l - np.r_[np.nan, c[:-1]])))
    atr = pd.Series(tr).rolling(ATR_N, min_periods=ATR_N).mean().to_numpy(copy=True)
    atr_valid = np.zeros(len(t), dtype=bool)
    for i in range(ATR_N, len(t)):
        atr_valid[i] = (np.all(contiguous[i - ATR_N + 1:i + 1])
                        and np.all(valid[i - ATR_N:i + 1]))
    atr[~atr_valid | ~valid | ~timestamp_valid] = np.nan
    signal = _signal_from_ohlc(o, h, l, c)
    signal[~valid | ~timestamp_valid] = 0
    return t, o, h, l, c, atr, signal, valid & timestamp_valid


def _nonoverlap_indexes(indexes: np.ndarray, horizon: int,
                        timestamps: np.ndarray) -> np.ndarray:
    """Keep signals whose fixed-horizon outcome intervals do not overlap.

    Callers pass either the signal-candle open (entry starts one minute later)
    or signal availability/next-entry time (entry starts at that timestamp).
    Both conventions have the same non-overlap boundary: a new signal exactly
    ``horizon`` minutes after the previous signal is allowed because its entry
    begins after the previous horizon's final bar closes.
    """
    selected = []
    cursor = 0
    while cursor < len(indexes):
        anchor = indexes[cursor]
        selected.append(anchor)
        next_timestamp = timestamps[anchor] + horizon * MINUTE_MS
        cursor = int(np.searchsorted(timestamps[indexes], next_timestamp, side="left"))
    return np.asarray(selected, dtype=np.int64)


def _eligible_signal_indexes(indexes: np.ndarray, atr: np.ndarray,
                             valid: np.ndarray, high: np.ndarray,
                             low: np.ndarray) -> np.ndarray:
    """Signals counted in the ATR-ready coverage numerator, not the M2 denominator."""
    return indexes[valid[indexes] & np.isfinite(atr[indexes])
                   & (high[indexes] > low[indexes])]


def _combine(aggs: list[dict]) -> dict:
    merged = empty_agg()
    for item in aggs:
        for key in ("issued", "resolved", "wins", "timeouts", "directions",
                    "mom_wins", "random_wins", "base_r", "stress_r"):
            merged[key] += item[key]
        merged["symbols"].update(item["symbols"])
    return merged


def _all_issued_metrics(agg: dict) -> dict:
    result = summarize(agg)
    n = agg["issued"]
    result["target_first_all_issued"] = agg["wins"] / n if n else None
    result["matched_momentum_all_issued"] = agg["mom_wins"] / n if n else None
    result["matched_random_all_issued"] = agg["random_wins"] / n if n else None
    return result


def _claim_decision(candidate: dict, independent: dict, coverage: dict,
                    scalar_audit: dict) -> dict:
    candidate_m2 = candidate.get("target_first_all_issued")
    momentum_m2 = candidate.get("matched_momentum_all_issued")
    random_m2 = candidate.get("matched_random_all_issued")
    data_gates = {
        "coverage_ge_10pct": coverage["rate"] is not None and coverage["rate"] >= 0.10,
        "path_resolution_ge_95pct": candidate["path_resolution"] is not None and candidate["path_resolution"] >= 0.95,
        "nonoverlap_n_ge_200": independent["n_issued"] >= 200,
        "nonoverlap_symbols_ge_20": independent["n_symbols"] >= 20,
        "scalar_audit_pass": (scalar_audit["sampled"] > 0
                               and scalar_audit["resolved_samples"] > 0
                               and scalar_audit["label_mismatches"] == 0
                               and scalar_audit["max_abs_net_r_error"] < 1e-12
                               and scalar_audit["max_abs_stress_net_r_error"] < 1e-12),
    }
    performance_gates = {
        "m2_all_issued_ge_80pct": candidate_m2 is not None and candidate_m2 >= 0.80,
        "base_cost_mean_net_r_positive": candidate["mean_net_r_base"] is not None and candidate["mean_net_r_base"] > 0,
        "not_below_matched_momentum": (candidate_m2 is not None and momentum_m2 is not None
                                         and candidate_m2 >= momentum_m2),
        "not_below_matched_random": (candidate_m2 is not None and random_m2 is not None
                                       and candidate_m2 >= random_m2),
    }
    if not all(data_gates.values()):
        decision = "INCONCLUSIVE_DATA_GATES"
    elif all(performance_gates.values()):
        decision = "PRIMARY_SCREEN_SURVIVOR_REVIEW_REQUIRED"
    else:
        decision = "REJECT_PRIMARY_SCREEN"
    return {
        "decision": decision,
        "data_gates": data_gates,
        "performance_gates": performance_gates,
        "statistical_inference_complete": False,
        "independent_oos": False,
    }


def run(database: Path) -> dict:
    database = database.resolve()
    source_paths = {
        "m2_runner": Path(__file__).resolve(),
        "shared_resolver": Path(__file__).with_name("micro_candle_m2.py").resolve(),
    }
    source_hashes = {key: _source_sha256(path) for key, path in source_paths.items()}
    initial_stat = database.stat()
    if initial_stat.st_size != SNAPSHOT_BYTES:
        raise ValueError(f"snapshot size mismatch: {initial_stat.st_size}")
    _assert_no_sqlite_sidecars(database)
    before_sha = _file_sha256(database)
    if before_sha != SNAPSHOT_SHA256:
        raise ValueError(f"snapshot SHA-256 mismatch: {before_sha}")
    db = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)
    try:
        if db.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal":
            raise ValueError("WAL journal mode is not supported")
        db.execute("BEGIN")
        last_completed_open_exclusive = COMPLETED_THROUGH_MS - MINUTE_MS + 1
        symbols = [r[0] for r in db.execute(
            "SELECT DISTINCT symbol FROM candles WHERE t_open_ms < ? ORDER BY symbol",
            (last_completed_open_exclusive,),
        )]
        if len(symbols) != EXPECTED_SYMBOL_COUNT:
            raise ValueError(f"expected {EXPECTED_SYMBOL_COUNT} symbols, found {len(symbols)}")
        claims = {h: [empty_agg() for _ in FOLDS] for h in (10, 20)}
        nonoverlap = {h: [empty_agg() for _ in FOLDS] for h in (10, 20)}
        fold_counts = {h: [{"eligible": 0, "issued": 0, "all_issued": 0,
                            "symbols": set()} for _ in FOLDS]
                       for h in (10, 20)}
        per_symbol = {h: {str(i + 1): [] for i in range(len(FOLDS))} for h in (10, 20)}
        scalar_audit = {h: {"sampled": 0, "resolved_samples": 0,
                           "label_mismatches": 0,
                           "max_abs_net_r_error": 0.0,
                           "max_abs_stress_net_r_error": 0.0} for h in (10, 20)}

        fold_bounds = [(_utc_ms(a), _utc_ms(b)) for a, b in FOLDS]
        for symbol_number, symbol in enumerate(symbols, 1):
            t, o, h, l, c, atr, signal, valid = _load_symbol(db, symbol, COMPLETED_THROUGH_MS)
            eligible = np.flatnonzero(valid & (h > l) & np.isfinite(atr))
            issued = np.flatnonzero(signal != 0)
            for fold_index, (start_ms, end_ms) in enumerate(fold_bounds):
                stop_index = int(np.searchsorted(t, end_ms, side="left"))
                idx = issued[(t[issued] >= start_ms) & (t[issued] < end_ms)]
                for horizon in (10, 20):
                    anchors = eligible[(t[eligible] >= start_ms) & (t[eligible] < end_ms)]
                    eligible_issued = _eligible_signal_indexes(idx, atr, valid, h, l)
                    fold_counts[horizon][fold_index]["eligible"] += len(anchors)
                    fold_counts[horizon][fold_index]["issued"] += len(eligible_issued)
                    fold_counts[horizon][fold_index]["all_issued"] += len(idx)
                    if len(eligible_issued):
                        fold_counts[horizon][fold_index]["symbols"].add(symbol)
                    selected = _nonoverlap_indexes(idx, horizon, t)
                    symbol_result = {"symbol": symbol, "issued": len(idx),
                                     "nonoverlap_n": len(selected)}
                    for indexes, target_agg in ((idx, claims[horizon][fold_index]),
                                                (selected, nonoverlap[horizon][fold_index])):
                        symbol_agg = empty_agg()
                        for offset in range(0, len(indexes), CHUNK_SIZE):
                            batch = indexes[offset:offset + CHUNK_SIZE]
                            scored = score_chunk(t[:stop_index], o[:stop_index], h[:stop_index],
                                                 l[:stop_index], c[:stop_index], atr[:stop_index],
                                                 batch, signal[batch], horizon, symbol)
                            add_agg(target_agg, scored, symbol)
                            add_agg(symbol_agg, scored, symbol)
                        key = "all_issued" if indexes is idx else "nonoverlap"
                        symbol_result[key] = _all_issued_metrics(symbol_agg)
                    per_symbol[horizon][str(fold_index + 1)].append(symbol_result)

                    # Independent scalar check on deterministic first signal(s) per symbol/horizon.
                    audit = scalar_audit[horizon]
                    if len(idx):
                        sample = np.unique(np.asarray([idx[0], idx[len(idx) // 2], idx[-1]], dtype=np.int64))
                        for anchor in sample:
                            fast = score_chunk(t[:stop_index], o[:stop_index], h[:stop_index],
                                               l[:stop_index], c[:stop_index], atr[:stop_index],
                                               np.asarray([anchor]), signal[[anchor]], horizon, symbol)[0]
                            slow = score_signal(t[:stop_index], o[:stop_index], h[:stop_index],
                                                l[:stop_index], c[:stop_index], atr[:stop_index],
                                                int(anchor), int(signal[anchor]), horizon)
                            audit["sampled"] += 1
                            audit["resolved_samples"] += int(bool(fast[0]) and slow is not None)
                            if bool(fast[0]) != (slow is not None):
                                audit["label_mismatches"] += 1
                            if slow is not None:
                                if (bool(fast[1]) != bool(slow[0])
                                        or bool(fast[2]) != bool(slow[1])
                                        or bool(fast[3]) != bool(slow[3])):
                                    audit["label_mismatches"] += 1
                                audit["max_abs_net_r_error"] = max(
                                    audit["max_abs_net_r_error"],
                                    abs(float(fast[4]) - float(slow[2])) if fast[0] else 0.0,
                                )
                                audit["max_abs_stress_net_r_error"] = max(
                                    audit.get("max_abs_stress_net_r_error", 0.0),
                                    abs(float(fast[5]) - float(slow[4])) if fast[0] else 0.0,
                                )
            print(f"done {symbol_number}/{len(symbols)} {symbol} rows={len(t):,} signals={len(issued):,}", flush=True)

        output = {
            "protocol": "micro-candle-phase5-marubozu-m2",
            "database_sha256": before_sha,
            "database_bytes": initial_stat.st_size,
            "implementation_sha256": source_hashes,
            "completed_through_utc": "2026-11-14T00:29:00Z",
            "symbols": len(symbols),
            "signal": "single completed 1m candle body/range >= 0.80; side=body sign",
            "folds": [{"fold": i + 1, "start_utc": FOLDS[i][0], "end_utc": FOLDS[i][1]}
                      for i in range(len(FOLDS))],
            "execution": "next contiguous 1m open; causal 14-bar SMA true range; 1R stop/target; stop-first ties; adverse stop gaps; fold-crossing paths unresolved",
            "costs_round_trip": {"base": 0.0014, "stress": 0.0028},
            "random_control": {"method": "SHA-256 first-byte low bit; key=seed|tag|symbol|anchor_timestamp_ms",
                               "seed": SEED},
            "outcome_access": True,
            "fold_summary": {},
            "nonoverlap_fold_summary": {},
            "coverage": {},
            "per_symbol": per_symbol,
            "scalar_audit": scalar_audit,
        }
        for horizon in (10, 20):
            key = f"{horizon}m"
            output["fold_summary"][key] = {}
            output["nonoverlap_fold_summary"][key] = {}
            for i in range(len(FOLDS)):
                output["fold_summary"][key][f"fold_{i+1}"] = _all_issued_metrics(claims[horizon][i])
                output["nonoverlap_fold_summary"][key][f"fold_{i+1}"] = _all_issued_metrics(nonoverlap[horizon][i])
            output["fold_summary"][key]["pooled"] = _all_issued_metrics(_combine(claims[horizon]))
            output["nonoverlap_fold_summary"][key]["pooled"] = _all_issued_metrics(_combine(nonoverlap[horizon]))
            output["coverage"][key] = [
                {"fold": i + 1,
                 "eligible_anchors": fold_counts[horizon][i]["eligible"],
                 "issued": fold_counts[horizon][i]["issued"],
                 "all_issued": fold_counts[horizon][i]["all_issued"],
                 "rate": (fold_counts[horizon][i]["issued"] / fold_counts[horizon][i]["eligible"]
                          if fold_counts[horizon][i]["eligible"] else None),
                 "symbols": len(fold_counts[horizon][i]["symbols"])}
                for i in range(len(FOLDS))
            ]
            pooled_eligible = sum(x["eligible"] for x in fold_counts[horizon])
            pooled_issued = sum(x["issued"] for x in fold_counts[horizon])
            pooled_all_issued = sum(x["all_issued"] for x in fold_counts[horizon])
            pooled_symbols = set().union(*(x["symbols"] for x in fold_counts[horizon]))
            output["coverage"][key + "_pooled"] = {
                "eligible_anchors": pooled_eligible,
                "issued": pooled_issued,
                "all_issued": pooled_all_issued,
                "rate": pooled_issued / pooled_eligible if pooled_eligible else None,
                "symbols": len(pooled_symbols),
            }

        decisions = {}
        for horizon in (10, 20):
            key = f"{horizon}m"
            candidate = output["fold_summary"][key]["pooled"]
            independent = output["nonoverlap_fold_summary"][key]["pooled"]
            coverage = output["coverage"][key + "_pooled"]
            decisions[key] = _claim_decision(candidate, independent, coverage,
                                             output["scalar_audit"][horizon])
        output["decisions"] = decisions
        statuses = [v["decision"] for v in decisions.values()]
        output["overall_decision"] = (
            "PRIMARY_SCREEN_SURVIVOR_REVIEW_REQUIRED"
            if "PRIMARY_SCREEN_SURVIVOR_REVIEW_REQUIRED" in statuses
            else "INCONCLUSIVE_DATA_GATES"
            if "INCONCLUSIVE_DATA_GATES" in statuses
            else "REJECT_PRIMARY_SCREEN"
        )
        return output
    finally:
        db.close()
        _assert_no_sqlite_sidecars(database)
        after_sha = _file_sha256(database)
        final_stat = database.stat()
        if before_sha != after_sha or (initial_stat.st_size, initial_stat.st_mtime_ns, initial_stat.st_ino) != (final_stat.st_size, final_stat.st_mtime_ns, final_stat.st_ino):
            raise ValueError("database changed while outcome evaluation was running")
        if source_hashes != {key: _source_sha256(path) for key, path in source_paths.items()}:
            raise ValueError("implementation source changed while outcome evaluation was running")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run(args.db)
    encoded = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(encoded, encoding="utf-8")
    print(json.dumps({
        "output": str(args.output),
        "symbols": report["symbols"],
        "10m": report["fold_summary"]["10m"]["pooled"],
        "20m": report["fold_summary"]["20m"]["pooled"],
        "decisions": report["decisions"],
        "scalar_audit": report["scalar_audit"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
