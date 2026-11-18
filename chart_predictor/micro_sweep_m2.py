"""Fixed 1-minute two-candle sweep/reclaim target-first evaluation."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sqlite3
from pathlib import Path

import numpy as np

from chart_predictor.micro_candle_m2 import score_chunk, sha_side
from chart_predictor.micro_maru_feasibility import (
    COMPLETED_THROUGH_MS,
    EXPECTED_SYMBOL_COUNT,
    MINUTE_MS,
    SNAPSHOT_BYTES,
    SNAPSHOT_SHA256,
    _assert_no_sqlite_sidecars,
    _file_sha256,
)
from chart_predictor.micro_maru_m2 import (
    FOLDS,
    _load_symbol,
    _nonoverlap_indexes,
    _utc_ms,
)

CHUNK_SIZE = 25_000
BASE_COST = 0.0014
STRESS_COST = 0.0028
SEED = 20261118


def _signal_array(o, h, low, c, valid, contiguous):
    signal = np.zeros(len(c), dtype=np.int8)
    if len(c) < 2:
        return signal
    h1, l1, c1 = h[:-1], low[:-1], c[:-1]
    h2, l2, c2 = h[1:], low[1:], c[1:]
    midpoint = (h1 + l1) / 2.0
    pair_valid = valid[:-1] & valid[1:] & contiguous[1:]
    long = (pair_valid & (l2 < l1) & (h2 <= h1)
            & (c2 > midpoint) & (c2 < h1))
    short = (pair_valid & (h2 > h1) & (l2 >= l1)
             & (c2 < midpoint) & (c2 > l1))
    signal[1:][long] = 1
    signal[1:][short] = -1
    return signal


def _new_agg():
    return {"issued": 0, "resolved": 0, "wins": 0, "timeouts": 0,
            "directions": 0, "tradable_resolved": 0, "no_trade": 0,
            "base_r": 0.0, "stress_r": 0.0, "symbols": set()}


def _score_dynamic(t, o, h, low, c, indexes, sides, stop_prices,
                   horizon, symbol):
    """Vector resolver using each signal side's frozen bar2-extreme stop."""
    n = len(indexes)
    result = np.zeros((n, 8), dtype=np.float64)
    result[:, 7] = indexes
    if not n:
        return result
    entry_i = indexes + 1
    has_entry = entry_i < len(t)
    rows = np.flatnonzero(has_entry)
    if not len(rows):
        return result
    ii, ee = indexes[rows], entry_i[rows]
    side = sides[rows].astype(np.int8)
    stop = stop_prices[rows].astype(np.float64)
    entry_valid = ((t[ee] == t[ii] + MINUTE_MS)
                   & np.isfinite(o[ee]) & (o[ee] > 0)
                   & np.isfinite(h[ee]) & np.isfinite(low[ee]) & np.isfinite(c[ee])
                   & (low[ee] > 0)
                   & (h[ee] >= np.maximum.reduce([o[ee], c[ee], low[ee]]))
                   & (low[ee] <= np.minimum.reduce([o[ee], c[ee], h[ee]])))
    risk = side * (o[ee] - stop)
    no_trade_rows = rows[entry_valid & (risk <= 0)]
    result[no_trade_rows, 0] = 1  # resolved no-trade failure at the next open
    result[no_trade_rows, 6] = 1

    tradable_rows = rows[entry_valid & (risk > 0)]
    if len(tradable_rows):
        tradable_indexes = indexes[tradable_rows]
        tradable_sides = sides[tradable_rows]
        risk_by_anchor = np.full(len(t), np.nan, dtype=np.float64)
        risk_by_anchor[tradable_indexes] = risk[entry_valid & (risk > 0)]
        scored = score_chunk(t, o, h, low, c, risk_by_anchor,
                             tradable_indexes, tradable_sides, horizon, symbol)
        result[tradable_rows, :6] = scored[:, :6]
    return result


def _score_scalar(t, o, h, low, c, index, side, horizon):
    """Independent scalar resolver for deterministic audit samples."""
    entry_i = index + 1
    if entry_i >= len(t) or t[entry_i] != t[index] + MINUTE_MS:
        return (False, False, False, False, 0.0, 0.0, False)
    entry_bar = (float(o[entry_i]), float(h[entry_i]),
                 float(low[entry_i]), float(c[entry_i]))
    if not _valid_ohlc(*entry_bar):
        return (False, False, False, False, 0.0, 0.0, False)
    stop = float(low[index] if side > 0 else h[index])
    entry = float(o[entry_i])
    risk = side * (entry - stop)
    if risk <= 0:
        return (True, False, False, False, 0.0, 0.0, True)
    end = entry_i + horizon
    if end > len(t):
        return (False, False, False, False, 0.0, 0.0, False)
    path = range(entry_i, end)
    if any(t[j] != t[entry_i] + (j - entry_i) * MINUTE_MS
           or not _valid_ohlc(float(o[j]), float(h[j]), float(low[j]), float(c[j]))
           for j in path):
        return (False, False, False, False, 0.0, 0.0, False)
    stop_price = entry - side * risk
    target = entry + side * risk
    outcome, exit_price = "TIMEOUT", float(c[end - 1])
    for j in path:
        stop_hit = low[j] <= stop_price if side > 0 else h[j] >= stop_price
        target_hit = h[j] >= target if side > 0 else low[j] <= target
        if stop_hit:
            exit_price = min(float(o[j]), stop_price) if side > 0 else max(float(o[j]), stop_price)
            outcome = "STOP"
            break
        if target_hit:
            exit_price, outcome = target, "TARGET"
            break
    gross = side * (exit_price / entry - 1.0)
    risk_fraction = risk / entry
    direction = side * (float(c[end - 1]) / entry - 1.0) > 0
    return (True, outcome == "TARGET", outcome == "TIMEOUT", bool(direction),
            (gross - BASE_COST) / risk_fraction,
            (gross - STRESS_COST) / risk_fraction, False)


def _valid_ohlc(op, high, low, close):
    return (np.isfinite(op) and np.isfinite(high) and np.isfinite(low)
            and np.isfinite(close) and low > 0 and high >= max(op, close, low)
            and low <= min(op, close, high))


def _no_trade_candidates(t, o, h, low, c, indexes, sides):
    entry_i = indexes + 1
    available = entry_i < len(t)
    positions = np.flatnonzero(available)
    if not len(positions):
        return np.empty(0, dtype=np.int64)
    anchors = indexes[positions]
    entries = entry_i[positions]
    directions = sides[positions]
    entry_ok = ((t[entries] == t[anchors] + MINUTE_MS)
                & np.isfinite(o[entries]) & (o[entries] > 0)
                & np.isfinite(h[entries]) & np.isfinite(low[entries])
                & np.isfinite(c[entries]) & (low[entries] > 0)
                & (h[entries] >= np.maximum.reduce([o[entries], c[entries], low[entries]]))
                & (low[entries] <= np.minimum.reduce([o[entries], c[entries], h[entries]])))
    stops = np.where(directions > 0, low[anchors], h[anchors])
    risk = directions * (o[entries] - stops)
    return anchors[entry_ok & (risk <= 0)]


def _add(agg, scores, symbol):
    if not len(scores):
        return
    resolved = scores[:, 0] == 1
    traded = resolved & (scores[:, 6] == 0)
    agg["issued"] += len(scores)
    agg["resolved"] += int(resolved.sum())
    agg["wins"] += int(scores[resolved, 1].sum())
    agg["timeouts"] += int(scores[traded, 2].sum())
    agg["directions"] += int(scores[traded, 3].sum())
    agg["tradable_resolved"] += int(traded.sum())
    agg["no_trade"] += int((scores[:, 6] == 1).sum())
    agg["base_r"] += float(scores[traded, 4].sum())
    agg["stress_r"] += float(scores[traded, 5].sum())
    agg["symbols"].add(symbol)


def _combine(aggs):
    result = _new_agg()
    for agg in aggs:
        for key in ("issued", "resolved", "wins", "timeouts", "directions",
                    "tradable_resolved", "no_trade", "base_r", "stress_r"):
            result[key] += agg[key]
        result["symbols"].update(agg["symbols"])
    return result


def _metrics(agg, momentum_wins=None, random_wins=None):
    issued, resolved, tradable = agg["issued"], agg["resolved"], agg["tradable_resolved"]
    return {
        "n_issued": issued, "n_resolved": resolved,
        "n_unresolved": issued - resolved,
        "path_resolution": resolved / issued if issued else None,
        "n_no_trade": agg["no_trade"], "n_tradable_resolved": tradable,
        "target_first": agg["wins"] / tradable if tradable else None,
        "target_first_resolved_trades": agg["wins"] / tradable if tradable else None,
        "target_first_all_issued": agg["wins"] / issued if issued else None,
        "matched_momentum_all_issued": (momentum_wins / issued
                                         if issued and momentum_wins is not None else None),
        "matched_random_all_issued": (random_wins / issued
                                       if issued and random_wins is not None else None),
        "n_timeout": agg["timeouts"],
        "direction_at_deadline": agg["directions"] / tradable if tradable else None,
        "mean_net_r_base": agg["base_r"] / tradable if tradable else None,
        "mean_net_r_stress": agg["stress_r"] / tradable if tradable else None,
        "n_symbols": len(agg["symbols"]),
    }


def _claim(candidate, independent, coverage, audit):
    m2 = candidate["target_first_all_issued"]
    data = {
        "coverage_reported": coverage is not None,
        "path_resolution_ge_95pct": candidate["path_resolution"] is not None and candidate["path_resolution"] >= 0.95,
        "nonoverlap_n_ge_200": independent["n_issued"] >= 200,
        "nonoverlap_symbols_ge_20": independent["n_symbols"] >= 20,
        "scalar_audit_pass": (audit["resolved_samples"] > 0 and audit["tradable_samples"] > 0
                              and audit["label_mismatches"] == 0
                              and audit["max_abs_net_r_error"] < 1e-12
                              and audit["max_abs_stress_net_r_error"] < 1e-12),
        "no_trade_scalar_audit_pass": (candidate["n_no_trade"] == 0
                                       or (audit["no_trade_samples"] > 0
                                           and audit["no_trade_mismatches"] == 0)),
    }
    performance = {
        "m2_all_issued_ge_80pct": m2 is not None and m2 >= 0.80,
        "base_cost_mean_net_r_positive": candidate["mean_net_r_base"] is not None and candidate["mean_net_r_base"] > 0,
        "not_below_matched_momentum": (m2 is not None
                                       and candidate["matched_momentum_all_issued"] is not None
                                       and m2 >= candidate["matched_momentum_all_issued"]),
        "not_below_matched_random": (m2 is not None
                                     and candidate["matched_random_all_issued"] is not None
                                     and m2 >= candidate["matched_random_all_issued"]),
    }
    if not all(data.values()):
        decision = "INCONCLUSIVE_DATA_GATES"
    elif all(performance.values()):
        decision = "PRIMARY_SCREEN_SURVIVOR_REVIEW_REQUIRED"
    else:
        decision = "REJECT_PRIMARY_SCREEN"
    return {"decision": decision, "data_gates": data,
            "performance_gates": performance,
            "statistical_inference_complete": False, "independent_oos": False}


def _validate_frequency_report(report, database_sha256, database_bytes,
                               expected_screen_sha256, expected_helper_sha256):
    if report.get("protocol") != "micro-candle-phase6-sweep-reclaim-frequency-only":
        raise ValueError("frequency report protocol mismatch")
    if (report.get("database_sha256") != database_sha256
            or report.get("database_bytes") != database_bytes
            or report.get("completed_through_utc") != "2026-11-14T00:29:00Z"
            or report.get("symbols") != EXPECTED_SYMBOL_COUNT):
        raise ValueError("frequency report snapshot identity mismatch")
    expected_rule = ("bar2 sweeps exactly one bar1 extreme, then closes inside bar1 range "
                     "and beyond its midpoint; entry and outcomes not evaluated")
    if report.get("candidate") != expected_rule:
        raise ValueError("frequency report candidate rule mismatch")
    if report.get("outcome_rows_read") != 0 or report.get("target_stop_labels_read") != 0:
        raise ValueError("frequency report is not label-blind")
    source_hashes = report.get("implementation_source_sha256", {})
    if (source_hashes.get("frequency_screen") != expected_screen_sha256
            or source_hashes.get("timestamp_and_nonoverlap_helper") != expected_helper_sha256):
        raise ValueError("frequency report implementation fingerprint mismatch")
    per_symbol = report.get("per_symbol", [])
    symbol_names = [row.get("symbol") for row in per_symbol]
    if len(per_symbol) != EXPECTED_SYMBOL_COUNT or len(set(symbol_names)) != EXPECTED_SYMBOL_COUNT:
        raise ValueError("frequency report per-symbol inventory is incomplete or duplicated")
    horizons = report.get("horizons", {})
    for horizon in ("10m", "20m"):
        item = horizons.get(horizon)
        if not item or item.get("frequency_gate_pass") is not True:
            raise ValueError(f"frequency gate failed or missing for {horizon}")
        if item.get("decision") != "READY_FOR_OUTCOME_PREREG":
            raise ValueError(f"frequency decision mismatch for {horizon}")
        if item.get("nonoverlap_n", 0) < 200 or item.get("nonoverlap_symbols", 0) < 20:
            raise ValueError(f"frequency sample gate failed for {horizon}")
        folds = item.get("folds", [])
        if len(folds) != len(FOLDS) or any(
                row.get("start_utc") != FOLDS[i][0] or row.get("end_utc") != FOLDS[i][1]
                for i, row in enumerate(folds)):
            raise ValueError(f"frequency fold definitions mismatch for {horizon}")
        if item.get("signals", -1) != sum(x.get("signals", 0) for x in folds):
            raise ValueError(f"frequency fold signal totals do not reconcile for {horizon}")
        if any(x.get("signals", -1) != x.get("long", 0) + x.get("short", 0)
               for x in folds):
            raise ValueError(f"frequency side counts do not reconcile for {horizon}")
        nonoverlap_key = f"nonoverlap_{horizon}"
        aggregates = [{"eligible_pairs": 0, "signals": 0, "long": 0,
                       "short": 0, "nonoverlap": 0, "symbols": set()}
                      for _ in FOLDS]
        for symbol_row in per_symbol:
            symbol_folds = symbol_row.get("folds", {})
            if set(symbol_folds) != {str(i + 1) for i in range(len(FOLDS))}:
                raise ValueError(f"frequency per-symbol fold inventory invalid for {horizon}")
            for fi, agg in enumerate(aggregates):
                row = symbol_folds[str(fi + 1)]
                keys = ("eligible_pairs", "signals", "long", "short", nonoverlap_key)
                if any(not isinstance(row.get(key), int) or row[key] < 0 for key in keys):
                    raise ValueError(f"invalid per-symbol counts for {horizon}")
                if row["signals"] != row["long"] + row["short"]:
                    raise ValueError(f"per-symbol side counts do not reconcile for {horizon}")
                for key in keys[:-1]:
                    agg[key] += row[key]
                agg["nonoverlap"] += row[nonoverlap_key]
                if row[nonoverlap_key]:
                    agg["symbols"].add(symbol_row["symbol"])
        for fi, (fold, agg) in enumerate(zip(folds, aggregates)):
            expected = (agg["eligible_pairs"], agg["signals"], agg["long"], agg["short"],
                        agg["nonoverlap"], len(agg["symbols"]))
            actual = (fold.get("eligible_pairs"), fold.get("signals"), fold.get("long"),
                      fold.get("short"), fold.get("nonoverlap_n"), fold.get("nonoverlap_symbols"))
            if actual != expected:
                raise ValueError(f"frequency per-symbol/fold totals do not reconcile for {horizon}")
            expected_rate = agg["signals"] / agg["eligible_pairs"] if agg["eligible_pairs"] else None
            if expected_rate is None or not math.isclose(
                    fold.get("coverage", -1), expected_rate, rel_tol=0.0, abs_tol=1e-12):
                raise ValueError(f"frequency fold coverage does not reconcile for {horizon}")
        total_signals = sum(x["signals"] for x in folds)
        total_pairs = sum(x["eligible_pairs"] for x in folds)
        total_nonoverlap = sum(x["nonoverlap"] for x in aggregates)
        total_symbols = len(set().union(*(x["symbols"] for x in aggregates)))
        expected_gate = total_nonoverlap >= 200 and total_symbols >= 20
        if (item["signals"] != total_signals or item["eligible_pairs"] != total_pairs
                or item["nonoverlap_n"] != total_nonoverlap
                or item["nonoverlap_symbols"] != total_symbols
                or item["frequency_gate_pass"] is not expected_gate):
            raise ValueError(f"frequency pooled totals/gate do not reconcile for {horizon}")
        if not math.isclose(item.get("coverage", -1), total_signals / total_pairs,
                            rel_tol=0.0, abs_tol=1e-12):
            raise ValueError(f"frequency pooled coverage does not reconcile for {horizon}")
    return {
        horizon: {"signals": horizons[horizon]["signals"],
                  "nonoverlap_n": horizons[horizon]["nonoverlap_n"],
                  "nonoverlap_symbols": horizons[horizon]["nonoverlap_symbols"]}
        for horizon in ("10m", "20m")
    }


def run(database: Path, frequency_report_path: Path) -> dict:
    database = database.resolve()
    initial_stat = database.stat()
    if initial_stat.st_size != SNAPSHOT_BYTES:
        raise ValueError(f"snapshot size mismatch: {initial_stat.st_size}")
    _assert_no_sqlite_sidecars(database)
    before_sha = _file_sha256(database)
    if before_sha != SNAPSHOT_SHA256:
        raise ValueError(f"snapshot SHA-256 mismatch: {before_sha}")
    frequency_report_path = frequency_report_path.resolve()
    frequency_report_sha256 = hashlib.sha256(frequency_report_path.read_bytes()).hexdigest()
    frequency_report = json.loads(frequency_report_path.read_text(encoding="utf-8"))
    frequency_screen_path = Path(__file__).with_name("micro_sweep_feasibility.py").resolve()
    nonoverlap_helper_path = Path(__file__).with_name("micro_maru_m2.py").resolve()
    frequency_gate = _validate_frequency_report(
        frequency_report, before_sha, initial_stat.st_size,
        hashlib.sha256(frequency_screen_path.read_bytes()).hexdigest(),
        hashlib.sha256(nonoverlap_helper_path.read_bytes()).hexdigest())
    source_paths = {
        "m2_runner": Path(__file__).resolve(),
        "frequency_screen": Path(__file__).with_name("micro_sweep_feasibility.py").resolve(),
        "shared_resolver": Path(__file__).with_name("micro_candle_m2.py").resolve(),
        "shared_snapshot_loader_and_nonoverlap": Path(__file__).with_name("micro_maru_m2.py").resolve(),
        "snapshot_guard": Path(__file__).with_name("micro_maru_feasibility.py").resolve(),
    }
    source_hashes = {key: hashlib.sha256(path.read_bytes()).hexdigest()
                     for key, path in source_paths.items()}
    db = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)
    try:
        if db.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal":
            raise ValueError("WAL journal mode is not supported")
        db.execute("BEGIN")
        cutoff_exclusive = COMPLETED_THROUGH_MS - MINUTE_MS + 1
        symbols = [row[0] for row in db.execute(
            "SELECT DISTINCT symbol FROM candles WHERE t_open_ms < ? ORDER BY symbol",
            (cutoff_exclusive,),
        )]
        if len(symbols) != EXPECTED_SYMBOL_COUNT:
            raise ValueError(f"expected {EXPECTED_SYMBOL_COUNT} symbols, found {len(symbols)}")
        folds = [(_utc_ms(a), _utc_ms(b)) for a, b in FOLDS]
        all_agg = {h: [_new_agg() for _ in FOLDS] for h in (10, 20)}
        independent = {h: [_new_agg() for _ in FOLDS] for h in (10, 20)}
        momentum = {h: [_new_agg() for _ in FOLDS] for h in (10, 20)}
        random = {h: [_new_agg() for _ in FOLDS] for h in (10, 20)}
        counts = {h: [{"eligible_pairs": 0, "issued": 0, "long": 0,
                       "short": 0, "symbols": set()} for _ in FOLDS]
                  for h in (10, 20)}
        scalar_audit = {h: {"sampled": 0, "resolved_samples": 0, "tradable_samples": 0,
                            "no_trade_samples": 0, "no_trade_mismatches": 0,
                            "label_mismatches": 0, "max_abs_net_r_error": 0.0,
                            "max_abs_stress_net_r_error": 0.0} for h in (10, 20)}
        per_symbol = {h: {str(i + 1): [] for i in range(len(FOLDS))} for h in (10, 20)}

        for symbol_number, symbol in enumerate(symbols, 1):
            t, o, h, low, c, _, _, valid = _load_symbol(db, symbol, COMPLETED_THROUGH_MS)
            contiguous = np.r_[False, (np.diff(t) == MINUTE_MS)]
            signal = _signal_array(o, h, low, c, valid, contiguous)
            issued_indexes = np.flatnonzero(signal != 0)
            signal_times = t + MINUTE_MS
            for fi, (start_ms, end_ms) in enumerate(folds):
                stop_index = int(np.searchsorted(t, end_ms, side="left"))
                idx = issued_indexes[(signal_times[issued_indexes] >= start_ms)
                                     & (signal_times[issued_indexes] < end_ms)]
                eligible = np.flatnonzero(valid[1:] & valid[:-1] & contiguous[1:]) + 1
                eligible = eligible[(signal_times[eligible] >= start_ms)
                                    & (signal_times[eligible] < end_ms)]
                mom_sides = np.where(c[idx] > o[idx], 1,
                                     np.where(c[idx] < o[idx], -1,
                                              np.fromiter((sha_side(symbol, int(signal_times[x]), "momentum-zero")
                                                           for x in idx), dtype=np.int8, count=len(idx))))
                rand_sides = np.fromiter((sha_side(symbol, int(signal_times[x]), "random")
                                          for x in idx), dtype=np.int8, count=len(idx))
                momentum_by_anchor = np.zeros(len(t), dtype=np.int8)
                random_by_anchor = np.zeros(len(t), dtype=np.int8)
                momentum_by_anchor[idx] = mom_sides
                random_by_anchor[idx] = rand_sides
                selected = {hor: _nonoverlap_indexes(idx.astype(np.int64), hor, signal_times)
                            for hor in (10, 20)}
                symbol_row = {"symbol": symbol, "issued": len(idx),
                              "long": int((signal[idx] == 1).sum()),
                              "short": int((signal[idx] == -1).sum()),
                              "nonoverlap_10m": len(selected[10]),
                              "nonoverlap_20m": len(selected[20])}
                for horizon in (10, 20):
                    counts[horizon][fi]["eligible_pairs"] += len(eligible)
                    counts[horizon][fi]["issued"] += len(idx)
                    counts[horizon][fi]["long"] += int((signal[idx] == 1).sum())
                    counts[horizon][fi]["short"] += int((signal[idx] == -1).sum())
                    if len(idx):
                        counts[horizon][fi]["symbols"].add(symbol)
                    for indexes, target, side_source in (
                        (idx, all_agg[horizon][fi], signal),
                        (selected[horizon], independent[horizon][fi], signal),
                        (idx, momentum[horizon][fi], momentum_by_anchor),
                        (idx, random[horizon][fi], random_by_anchor),
                    ):
                        for offset in range(0, len(indexes), CHUNK_SIZE):
                            batch = indexes[offset:offset + CHUNK_SIZE]
                            batch_sides = side_source[batch]
                            batch_stops = np.where(batch_sides > 0, low[batch], h[batch])
                            scored = _score_dynamic(t[:stop_index], o[:stop_index], h[:stop_index],
                                                    low[:stop_index], c[:stop_index], batch,
                                                    batch_sides, batch_stops, horizon, symbol)
                            _add(target, scored, symbol)
                    per_symbol[horizon][str(fi + 1)].append(symbol_row)

                    audit = scalar_audit[horizon]
                    if len(idx):
                        sample = np.unique(np.asarray([idx[0], idx[len(idx) // 2], idx[-1]], dtype=np.int64))
                        no_trade_sample = _no_trade_candidates(
                            t[:stop_index], o[:stop_index], h[:stop_index], low[:stop_index],
                            c[:stop_index], idx, signal[idx])
                        if len(no_trade_sample):
                            sample = np.unique(np.r_[sample, no_trade_sample[:1]])
                        for anchor in sample:
                            fast = _score_dynamic(t[:stop_index], o[:stop_index], h[:stop_index],
                                                  low[:stop_index], c[:stop_index],
                                                  np.asarray([anchor]), signal[[anchor]],
                                                  np.asarray([low[anchor] if signal[anchor] > 0 else h[anchor]]),
                                                  horizon, symbol)[0]
                            slow = _score_scalar(t[:stop_index], o[:stop_index], h[:stop_index],
                                                 low[:stop_index], c[:stop_index], int(anchor),
                                                 int(signal[anchor]), horizon)
                            audit["sampled"] += 1
                            if bool(fast[0]) != bool(slow[0]):
                                audit["label_mismatches"] += 1
                            if bool(fast[6]) or bool(slow[6]):
                                audit["no_trade_samples"] += 1
                                if bool(fast[6]) != bool(slow[6]):
                                    audit["no_trade_mismatches"] += 1
                            if slow[0]:
                                audit["resolved_samples"] += 1
                                if (bool(fast[1]) != bool(slow[1])
                                        or bool(fast[2]) != bool(slow[2])
                                        or bool(fast[3]) != bool(slow[3])
                                        or bool(fast[6]) != bool(slow[6])):
                                    audit["label_mismatches"] += 1
                                if not slow[6]:
                                    audit["tradable_samples"] += 1
                                    audit["max_abs_net_r_error"] = max(
                                        audit["max_abs_net_r_error"], abs(float(fast[4]) - float(slow[4])))
                                    audit["max_abs_stress_net_r_error"] = max(
                                        audit["max_abs_stress_net_r_error"], abs(float(fast[5]) - float(slow[5])))
            print(f"done {symbol_number}/{len(symbols)} {symbol} signals={len(issued_indexes):,}", flush=True)

        output = {
            "protocol": "micro-candle-phase6-sweep-reclaim-m2",
            "database_sha256": before_sha, "database_bytes": initial_stat.st_size,
            "frequency_report_sha256": frequency_report_sha256,
            "frequency_gate_preflight": frequency_gate,
            "implementation_source_sha256": source_hashes,
            "completed_through_utc": "2026-11-14T00:29:00Z", "symbols": len(symbols),
            "signal": "bar2 sweeps one bar1 extreme, closes inside bar1 range beyond midpoint; enter next contiguous open",
            "stops_targets": "bar2 extreme stop, 1R target; entry beyond stop is resolved no-trade failure",
            "costs_round_trip": {"base": BASE_COST, "stress": STRESS_COST},
            "random_control": {"seed": SEED, "key": "seed|tag|symbol|signal_close_ms"},
            "folds": [{"fold": i + 1, "start_utc": FOLDS[i][0], "end_utc": FOLDS[i][1]}
                      for i in range(len(FOLDS))],
            "outcome_access": True, "fold_summary": {}, "nonoverlap_fold_summary": {},
            "coverage": {}, "decisions": {}, "scalar_audit": scalar_audit,
            "per_symbol": per_symbol,
        }
        for horizon in (10, 20):
            key = f"{horizon}m"
            output["fold_summary"][key] = {}
            output["nonoverlap_fold_summary"][key] = {}
            for fi in range(len(FOLDS)):
                output["fold_summary"][key][f"fold_{fi+1}"] = _metrics(
                    all_agg[horizon][fi], momentum[horizon][fi]["wins"], random[horizon][fi]["wins"])
                output["nonoverlap_fold_summary"][key][f"fold_{fi+1}"] = _metrics(
                    independent[horizon][fi])
            output["fold_summary"][key]["pooled"] = _metrics(
                _combine(all_agg[horizon]), _combine(momentum[horizon])["wins"],
                _combine(random[horizon])["wins"])
            output["nonoverlap_fold_summary"][key]["pooled"] = _metrics(_combine(independent[horizon]))
            fold_coverage = []
            for fi, item in enumerate(counts[horizon]):
                fold_coverage.append({
                    "fold": fi + 1, "eligible_pairs": item["eligible_pairs"],
                    "issued": item["issued"], "long": item["long"],
                    "short": item["short"],
                    "rate": item["issued"] / item["eligible_pairs"] if item["eligible_pairs"] else None,
                    "symbols": len(item["symbols"]),
                })
            output["coverage"][key] = fold_coverage
            eligible_n = sum(x["eligible_pairs"] for x in counts[horizon])
            issued_n = sum(x["issued"] for x in counts[horizon])
            output["coverage"][key + "_pooled"] = {
                "eligible_pairs": eligible_n, "issued": issued_n,
                "long": sum(x["long"] for x in counts[horizon]),
                "short": sum(x["short"] for x in counts[horizon]),
                "rate": issued_n / eligible_n if eligible_n else None,
                "symbols": len(set().union(*(x["symbols"] for x in counts[horizon]))),
            }
            output["decisions"][key] = _claim(
                output["fold_summary"][key]["pooled"],
                output["nonoverlap_fold_summary"][key]["pooled"],
                output["coverage"][key + "_pooled"], scalar_audit[horizon])
        statuses = [v["decision"] for v in output["decisions"].values()]
        output["overall_decision"] = (
            "PRIMARY_SCREEN_SURVIVOR_REVIEW_REQUIRED"
            if "PRIMARY_SCREEN_SURVIVOR_REVIEW_REQUIRED" in statuses
            else "INCONCLUSIVE_DATA_GATES"
            if "INCONCLUSIVE_DATA_GATES" in statuses else "REJECT_PRIMARY_SCREEN")
        return output
    finally:
        db.close()
        _assert_no_sqlite_sidecars(database)
        after_sha = _file_sha256(database)
        final_stat = database.stat()
        if before_sha != after_sha or (initial_stat.st_size, initial_stat.st_mtime_ns, initial_stat.st_ino) != (final_stat.st_size, final_stat.st_mtime_ns, final_stat.st_ino):
            raise ValueError("database changed during M2 evaluation")
        if source_hashes != {key: hashlib.sha256(path.read_bytes()).hexdigest()
                             for key, path in source_paths.items()}:
            raise ValueError("source files changed during M2 evaluation")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, required=True)
    ap.add_argument("--frequency-report", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    report = run(args.db, args.frequency_report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
                           encoding="utf-8")
    print(json.dumps({"output": str(args.output), "decisions": report["decisions"],
                      "pooled": {h: report["fold_summary"][h]["pooled"] for h in ("10m", "20m")},
                      "scalar_audit": report["scalar_audit"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
