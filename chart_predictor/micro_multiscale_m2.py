"""Outcome replay for the preregistered 3m/5m micro-candle scale study."""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

from chart_predictor.micro_candle_m2 import score_chunk, sha_side
from chart_predictor.micro_multiscale import (
    CUTOFF_MS, EXPECTED_BYTES, EXPECTED_SHA256, FOLDS, HORIZONS, MINUTE_MS,
    RULES, SIZES, SUPPORTED_SIZES, _sha256, aggregate_bars, fold_indices, nonoverlap_indices,
    signal_masks,
)
from chart_predictor.micro_sweep_m2 import _score_dynamic

BASE_COST = 0.0014
STRESS_COST = 0.0028
PREREGISTRATION = Path(__file__).resolve().parents[1] / "docs/research/micro-candle-phase7-multiscale-prereg-2026-11-18.md"
REPO_ROOT = Path(__file__).resolve().parents[1]


def _prereg_path(value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (REPO_ROOT / path).resolve()


def _empty() -> dict:
    return {"issued": 0, "resolved": 0, "wins": 0, "timeouts": 0,
            "directions": 0, "tradable": 0, "no_trade": 0,
            "base_r": 0.0, "stress_r": 0.0,
            "momentum_wins": 0, "random_wins": 0,
            "momentum_no_trade": 0, "random_no_trade": 0}


def _add(agg: dict, scores: np.ndarray, *, rule: str, side_score: np.ndarray | None = None,
         random_score: np.ndarray | None = None) -> None:
    if not len(scores):
        return
    resolved = scores[:, 0] == 1
    if rule == "sweep_reclaim":
        no_trade = scores[:, 6] == 1
    else:
        no_trade = np.zeros(len(scores), dtype=bool)
    tradable = resolved & ~no_trade
    agg["issued"] += len(scores)
    agg["resolved"] += int(resolved.sum())
    agg["wins"] += int(scores[resolved, 1].sum())
    agg["timeouts"] += int(scores[tradable, 2].sum())
    agg["directions"] += int(scores[tradable, 3].sum())
    agg["tradable"] += int(tradable.sum())
    agg["no_trade"] += int(no_trade.sum())
    agg["base_r"] += float(scores[tradable, 4].sum())
    agg["stress_r"] += float(scores[tradable, 5].sum())
    if side_score is not None:
        agg["momentum_wins"] += int(side_score[side_score[:, 0] == 1, 1].sum())
        if rule == "sweep_reclaim":
            agg["momentum_no_trade"] += int(np.sum(side_score[:, 6] == 1))
    if random_score is not None:
        agg["random_wins"] += int(random_score[random_score[:, 0] == 1, 1].sum())
        if rule == "sweep_reclaim":
            agg["random_no_trade"] += int(np.sum(random_score[:, 6] == 1))


def _metrics(agg: dict) -> dict:
    n = agg["issued"]
    resolved = agg["resolved"]
    tradable = agg["tradable"]
    return {
        "n_issued": n, "n_resolved": resolved, "n_unresolved": n - resolved,
        "n_tradable_resolved": tradable, "n_no_trade": agg["no_trade"],
        "path_resolution": resolved / n if n else None,
        "target_first_all_issued": agg["wins"] / n if n else None,
        "target_first_resolved_trades": agg["wins"] / tradable if tradable else None,
        "n_timeout": agg["timeouts"],
        "direction_at_deadline": agg["directions"] / tradable if tradable else None,
        "mean_net_r_base": agg["base_r"] / tradable if tradable else None,
        "mean_net_r_stress": agg["stress_r"] / tradable if tradable else None,
        "matched_momentum_all_issued": agg["momentum_wins"] / n if n else None,
        "matched_random_all_issued": agg["random_wins"] / n if n else None,
        "matched_momentum_no_trade": agg["momentum_no_trade"],
        "matched_random_no_trade": agg["random_no_trade"],
    }


def _scalar_audit_pass(audit: dict, rule: str, no_trade_total: int) -> bool:
    return (audit["sampled"] > 0 and audit["resolved_samples"] > 0
            and audit["tradable_samples"] > 0
            and audit["label_mismatches"] == 0
            and audit["no_trade_mismatches"] == 0
            and audit["max_abs_net_r_error"] < 1e-12
            and audit["max_abs_stress_net_r_error"] < 1e-12
            and (audit["no_trade_samples"] > 0 or rule == "body_dominance"
                 or (rule == "sweep_reclaim" and no_trade_total == 0)))


def _empty_score(n: int) -> np.ndarray:
    result = np.zeros((n, 8), dtype=np.float64)
    return result


def _score_body(t, o, h, low, c, atr, indexes, sides, horizon, symbol):
    raw = score_chunk(t, o, h, low, c, atr, indexes, sides, horizon, symbol)
    result = _empty_score(len(indexes))
    result[:, :6] = raw[:, :6]
    return result


def _score_sweep(t, o, h, low, c, indexes, sides, stop_prices, horizon, symbol):
    return _score_dynamic(t, o, h, low, c, indexes, sides, stop_prices,
                          horizon, symbol)


def _atr(aggregates: dict[str, np.ndarray], interval_ms: int):
    t = aggregates["open_ms"]
    o, h, low, c = (aggregates[k] for k in ("open", "high", "low", "close"))
    valid = (np.isfinite(o) & np.isfinite(h) & np.isfinite(low) & np.isfinite(c)
             & (low > 0) & (h >= np.maximum.reduce([o, c, low]))
             & (low <= np.minimum.reduce([o, c, h])))
    contiguous = np.r_[False, np.diff(t) == interval_ms]
    prior_close = np.r_[np.nan, c[:-1]]
    tr = np.maximum(h - low, np.maximum(np.abs(h - prior_close), np.abs(low - prior_close)))
    atr = pd.Series(tr).rolling(14, min_periods=14).mean().to_numpy(copy=True)
    atr_valid = np.zeros(len(t), dtype=bool)
    for i in range(14, len(t)):
        atr_valid[i] = (np.all(contiguous[i - 13:i + 1])
                        and np.all(valid[i - 14:i + 1]))
    atr[~atr_valid] = np.nan
    synthetic_t = np.zeros(len(t), dtype=np.int64)
    if len(t) > 1:
        synthetic_t[1:] = np.cumsum(np.where(np.diff(t) == interval_ms,
                                             MINUTE_MS, 2 * MINUTE_MS), dtype=np.int64)
    return synthetic_t, atr


def _random_sides(symbol: str, availability: np.ndarray, tag: str) -> np.ndarray:
    return np.fromiter((sha_side(symbol, int(ts), tag) for ts in availability),
                       dtype=np.int8, count=len(availability))


def _score_one(t, o, h, low, c, atr, index, side, stop_price, horizon, rule):
    """Independent scalar barrier resolver used only for deterministic audits."""
    entry_i = index + 1
    if entry_i >= len(t) or t[entry_i] != t[index] + MINUTE_MS:
        return (False, False, False, False, 0.0, 0.0, False)
    entry = float(o[entry_i])
    if not np.isfinite(entry) or entry <= 0:
        return (False, False, False, False, 0.0, 0.0, False)
    if rule == "body_dominance":
        risk = float(atr[index])
        if not np.isfinite(risk) or risk <= 0:
            return (False, False, False, False, 0.0, 0.0, False)
        stop = entry - side * risk
        target = entry + side * risk
    else:
        stop = float(stop_price)
        risk = side * (entry - stop)
        if not np.isfinite(risk) or risk <= 0:
            return (True, False, False, False, 0.0, 0.0, True)
        target = entry + side * risk
    end = entry_i + horizon
    if end > len(t):
        return (False, False, False, False, 0.0, 0.0, False)
    outcome, exit_price = "TIMEOUT", float(c[end - 1])
    for j in range(entry_i, end):
        if t[j] != t[j - 1] + MINUTE_MS:
            return (False, False, False, False, 0.0, 0.0, False)
        if not (np.isfinite(o[j]) and np.isfinite(h[j]) and np.isfinite(low[j])
                and np.isfinite(c[j]) and low[j] > 0
                and h[j] >= max(o[j], c[j], low[j])
                and low[j] <= min(o[j], c[j], h[j])):
            return (False, False, False, False, 0.0, 0.0, False)
        stop_hit = low[j] <= stop if side > 0 else h[j] >= stop
        target_hit = h[j] >= target if side > 0 else low[j] <= target
        if stop_hit:
            exit_price = min(float(o[j]), stop) if side > 0 else max(float(o[j]), stop)
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


def _validate_frequency(report: dict, sizes: tuple[int, ...], protocol: str) -> None:
    expected_protocol = f"micro-candle-{protocol}-frequency"
    if report.get("protocol") != expected_protocol:
        raise ValueError("wrong frequency-report protocol")
    if report.get("aggregate_sizes_minutes") != list(sizes):
        raise ValueError("frequency report candle sizes differ from requested sizes")
    if report.get("database_sha256") != EXPECTED_SHA256 or report.get("database_bytes") != EXPECTED_BYTES:
        raise ValueError("frequency report is for another database snapshot")
    if report.get("symbol_count") != 100 or len(report.get("symbols", [])) != 100:
        raise ValueError("frequency report symbol count mismatch")
    if report.get("source_sha256") != _sha256(Path(__file__).resolve().with_name("micro_multiscale.py")):
        raise ValueError("frequency screen source changed since screen")
    preregistration = _prereg_path(report.get("preregistration_path", ""))
    if report.get("preregistration_sha256") != _sha256(preregistration):
        raise ValueError("preregistration changed since frequency screen")
    for rule in RULES:
        for size in sizes:
            cell = report.get("totals", {}).get(rule, {}).get(str(size), {})
            for horizon in HORIZONS:
                gate = cell.get("horizons", {}).get(str(horizon), {})
                if (not gate.get("frequency_gate_pass")
                        or gate.get("nonoverlap_n", 0) < 200
                        or gate.get("nonoverlap_symbols", 0) < 20):
                    raise ValueError(f"frequency gate failed for {rule}/{size}m/{horizon}")


def _verify_frequency_counts(report: dict, recomputed: dict, sizes: tuple[int, ...] = SIZES) -> None:
    expected = report["per_symbol_fold"]
    for rule in RULES:
        for size in sizes:
            key = str(size)
            if len(expected[rule][key]) != len(recomputed[rule][key]):
                raise ValueError("frequency per-symbol row count mismatch")
            for old, new in zip(expected[rule][key], recomputed[rule][key]):
                if old["symbol"] != new["symbol"] or old["folds"] != new["folds"]:
                    raise ValueError(f"label-blind frequency counts changed: {rule}/{size}/{old['symbol']}")
            eligible = signals = longs = shorts = 0
            nonoverlap = {str(h): 0 for h in HORIZONS}
            nonoverlap_symbols = {str(h): set() for h in HORIZONS}
            for item in recomputed[rule][key]:
                symbol_has_signal = {str(h): False for h in HORIZONS}
                for fold in item["folds"]:
                    eligible += fold["eligible_anchors"]
                    signals += fold["signals"]
                    longs += fold["long"]
                    shorts += fold["short"]
                    for horizon in HORIZONS:
                        count = fold["nonoverlap"][str(horizon)]
                        nonoverlap[str(horizon)] += count
                        symbol_has_signal[str(horizon)] |= count > 0
                for horizon in HORIZONS:
                    if symbol_has_signal[str(horizon)]:
                        nonoverlap_symbols[str(horizon)].add(item["symbol"])
            actual = report.get("totals", {}).get(rule, {}).get(key, {})
            expected_horizons = {
                str(h): {"nonoverlap_n": nonoverlap[str(h)],
                         "nonoverlap_symbols": len(nonoverlap_symbols[str(h)]),
                         "frequency_gate_pass": (nonoverlap[str(h)] >= 200
                                                  and len(nonoverlap_symbols[str(h)]) >= 20)}
                for h in HORIZONS
            }
            expected_symbols = {str(h): len(nonoverlap_symbols[str(h)]) for h in HORIZONS}
            expected_totals = {"eligible": eligible, "signals": signals,
                               "long": longs, "short": shorts,
                               "coverage": signals / eligible if eligible else None,
                               "nonoverlap": {str(h): nonoverlap[str(h)] for h in HORIZONS},
                               "symbols": expected_symbols, "horizons": expected_horizons}
            for field, value in expected_totals.items():
                if actual.get(field) != value:
                    raise ValueError(f"frequency total reconciliation failed: {rule}/{size}/{field}")


def _recompute_frequency(bars_by_symbol: dict, symbols: list[str], sizes: tuple[int, ...]) -> dict:
    bounds = np.array([FOLDS[0][0], *(end for _, end in FOLDS)], dtype=np.int64)
    result = {rule: {str(size): [] for size in sizes} for rule in RULES}
    for symbol in symbols:
        for size in sizes:
            bars = bars_by_symbol[symbol][size]
            interval = size * MINUTE_MS
            availability = bars["open_ms"] + interval
            eligible = bars["high"] > bars["low"]
            body, sweep = signal_masks(bars["open_ms"], bars["open"], bars["high"], bars["low"], bars["close"], interval)
            folds = fold_indices(availability, bounds)
            for rule, signal in (("body_dominance", body), ("sweep_reclaim", sweep)):
                folds_out = []
                for fold_no, (start, end) in enumerate(FOLDS, 1):
                    in_fold = folds == fold_no - 1
                    eligible_n = int(np.sum(eligible & in_fold))
                    indexes = np.flatnonzero((signal != 0) & in_fold)
                    nonoverlap = {str(h): int(len(nonoverlap_indices(indexes, availability, h, interval)))
                                  for h in HORIZONS}
                    folds_out.append({
                        "fold": fold_no, "start_ms": start, "end_ms": end,
                        "eligible_anchors": eligible_n, "signals": int(len(indexes)),
                        "coverage": len(indexes) / eligible_n if eligible_n else None,
                        "long": int(np.sum(signal[indexes] > 0)),
                        "short": int(np.sum(signal[indexes] < 0)),
                        "nonoverlap": nonoverlap,
                    })
                result[rule][str(size)].append({"symbol": symbol, "folds": folds_out})
    return result


def run(database: Path, frequency_path: Path, sizes: tuple[int, ...] = SIZES,
        protocol: str = "phase7-multiscale") -> dict:
    sizes = tuple(sizes)
    if (not sizes or len(set(sizes)) != len(sizes)
            or any(size not in SUPPORTED_SIZES for size in sizes)):
        raise ValueError(f"sizes must be a unique non-empty subset of {SUPPORTED_SIZES}")
    database = database.resolve()
    frequency_path = frequency_path.resolve()
    if database.stat().st_size != EXPECTED_BYTES or _sha256(database) != EXPECTED_SHA256:
        raise ValueError("pinned source database does not match preregistered snapshot")
    for suffix in ("-wal", "-shm", "-journal"):
        if Path(f"{database}{suffix}").exists():
            raise ValueError(f"SQLite sidecar exists: {suffix}")
    frequency = json.loads(frequency_path.read_text())
    _validate_frequency(frequency, sizes, protocol)
    preregistration = _prereg_path(frequency.get("preregistration_path", ""))
    db = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)
    try:
        if db.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal":
            raise ValueError("WAL mode not accepted")
        db.execute("BEGIN")
        symbols = [r[0] for r in db.execute(
            "SELECT DISTINCT symbol FROM candles WHERE t_open_ms+60000<=? ORDER BY symbol", (CUTOFF_MS,))]
        if symbols != frequency["symbols"]:
            raise ValueError("symbol universe changed after frequency screen")
        bars_by_symbol = {}
        for i, symbol in enumerate(symbols, 1):
            raw = pd.read_sql_query(
                "SELECT t_open_ms,o,h,l,c FROM candles WHERE symbol=? AND t_open_ms+60000<=? ORDER BY t_open_ms",
                db, params=(symbol, CUTOFF_MS))
            if db.execute("SELECT COUNT(*) FROM candles WHERE symbol=? AND t_open_ms+60000<=? "
                          "AND typeof(t_open_ms)!='integer'", (symbol, CUTOFF_MS)).fetchone()[0]:
                raise ValueError(f"non-integer timestamps in {symbol}")
            t = raw.t_open_ms.to_numpy(np.int64)
            arrays = [raw[k].to_numpy(np.float64) for k in ("o", "h", "l", "c")]
            bars_by_symbol[symbol] = {
                size: aggregate_bars(t, *arrays, size) for size in sizes
            }
            print(f"load {i}/{len(symbols)} {symbol}", flush=True)
        recomputed = _recompute_frequency(bars_by_symbol, symbols, sizes)
        _verify_frequency_counts(frequency, recomputed, sizes)

        outcomes = {rule: {str(size): {str(h): {"folds": [], "nonoverlap_folds": [],
                                                "symbols": [], "scalar_audit": {
                                                    "sampled": 0, "resolved_samples": 0,
                                                    "tradable_samples": 0, "no_trade_samples": 0,
                                                    "label_mismatches": 0, "no_trade_mismatches": 0,
                                                    "max_abs_net_r_error": 0.0,
                                                    "max_abs_stress_net_r_error": 0.0},
                                                "_fold_agg": [_empty() for _ in FOLDS],
                                                "_nonoverlap_fold_agg": [_empty() for _ in FOLDS]}
                                           for h in HORIZONS} for size in sizes}
                    for rule in RULES}
        bounds = np.array([FOLDS[0][0], *(end for _, end in FOLDS)], dtype=np.int64)

        for symbol_number, symbol in enumerate(symbols, 1):
            for size in sizes:
                bars = bars_by_symbol[symbol][size]
                interval = size * MINUTE_MS
                t_actual = bars["open_ms"]
                availability = t_actual + interval
                o, hi, low, close = (bars[k] for k in ("open", "high", "low", "close"))
                t_score, atr = _atr(bars, interval)
                body, sweep = signal_masks(t_actual, o, hi, low, close, interval)
                fold_ids = fold_indices(availability, bounds)
                for rule, signals in (("body_dominance", body), ("sweep_reclaim", sweep)):
                    for horizon in HORIZONS:
                        cell = outcomes[rule][str(size)][str(horizon)]
                        pooled = _empty()
                        pooled_nonoverlap = _empty()
                        symbol_scores = []
                        for fold_index, (fold_start, fold_end) in enumerate(FOLDS):
                            in_fold = fold_ids == fold_index
                            indexes = np.flatnonzero((signals != 0) & in_fold)
                            bar_end = int(np.searchsorted(availability, fold_end, side="right"))
                            selected_nonoverlap = nonoverlap_indices(indexes, availability, horizon, interval)
                            nonoverlap_set = set(selected_nonoverlap.tolist())
                            if rule == "body_dominance":
                                sides = signals[indexes]
                                random_sides = _random_sides(symbol, availability[indexes], "random")
                                candidates_parts = []
                                momentum_parts = []
                                random_parts = []
                                for start in range(0, len(indexes), 5_000):
                                    ix = indexes[start:start + 5_000]
                                    side_part = sides[start:start + 5_000]
                                    rand_part = random_sides[start:start + 5_000]
                                    candidates_parts.append(_score_body(t_score[:bar_end], o[:bar_end], hi[:bar_end], low[:bar_end], close[:bar_end], atr[:bar_end], ix, side_part, horizon, symbol))
                                    momentum_parts.append(_score_body(t_score[:bar_end], o[:bar_end], hi[:bar_end], low[:bar_end], close[:bar_end], atr[:bar_end], ix, side_part, horizon, symbol))
                                    random_parts.append(_score_body(t_score[:bar_end], o[:bar_end], hi[:bar_end], low[:bar_end], close[:bar_end], atr[:bar_end], ix, rand_part, horizon, symbol))
                                scores = np.concatenate(candidates_parts) if candidates_parts else _empty_score(0)
                                momentum_scores = np.concatenate(momentum_parts) if momentum_parts else _empty_score(0)
                                random_scores = np.concatenate(random_parts) if random_parts else _empty_score(0)
                            else:
                                sides = signals[indexes]
                                momentum_sides = np.where(close[indexes] > o[indexes], 1,
                                                          np.where(close[indexes] < o[indexes], -1,
                                                                   _random_sides(symbol, availability[indexes], "momentum-zero")))
                                random_sides = _random_sides(symbol, availability[indexes], "random")
                                stops = np.where(sides > 0, low[indexes], hi[indexes])
                                momentum_stops = np.where(momentum_sides > 0, low[indexes], hi[indexes])
                                random_stops = np.where(random_sides > 0, low[indexes], hi[indexes])
                                scores_parts, mom_parts, rand_parts = [], [], []
                                for start in range(0, len(indexes), 5_000):
                                    ix = indexes[start:start + 5_000]
                                    scores_parts.append(_score_sweep(t_score[:bar_end], o[:bar_end], hi[:bar_end], low[:bar_end], close[:bar_end], ix, sides[start:start + 5_000], stops[start:start + 5_000], horizon, symbol))
                                    mom_parts.append(_score_sweep(t_score[:bar_end], o[:bar_end], hi[:bar_end], low[:bar_end], close[:bar_end], ix, momentum_sides[start:start + 5_000], momentum_stops[start:start + 5_000], horizon, symbol))
                                    rand_parts.append(_score_sweep(t_score[:bar_end], o[:bar_end], hi[:bar_end], low[:bar_end], close[:bar_end], ix, random_sides[start:start + 5_000], random_stops[start:start + 5_000], horizon, symbol))
                                scores = np.concatenate(scores_parts) if scores_parts else _empty_score(0)
                                momentum_scores = np.concatenate(mom_parts) if mom_parts else _empty_score(0)
                                random_scores = np.concatenate(rand_parts) if rand_parts else _empty_score(0)

                            fold_agg, nonoverlap_agg = _empty(), _empty()
                            _add(fold_agg, scores, rule=rule, side_score=momentum_scores, random_score=random_scores)
                            if len(selected_nonoverlap):
                                positions = np.fromiter((j for j, ix in enumerate(indexes) if ix in nonoverlap_set), dtype=np.int64)
                                _add(nonoverlap_agg, scores[positions], rule=rule,
                                     side_score=momentum_scores[positions], random_score=random_scores[positions])
                            for key in ("issued", "resolved", "wins", "timeouts", "directions", "tradable", "no_trade", "base_r", "stress_r", "momentum_wins", "random_wins", "momentum_no_trade", "random_no_trade"):
                                pooled[key] += fold_agg[key]
                                pooled_nonoverlap[key] += nonoverlap_agg[key]
                                cell["_fold_agg"][fold_index][key] += fold_agg[key]
                                cell["_nonoverlap_fold_agg"][fold_index][key] += nonoverlap_agg[key]

                            # Deterministic per-fold scalar audit: first/middle/last plus
                            # one no-trade anchor when present, for candidate labels/net R.
                            audit_indexes = set()
                            if len(indexes):
                                audit_indexes.update((int(indexes[0]), int(indexes[len(indexes) // 2]), int(indexes[-1])))
                            if rule == "sweep_reclaim" and len(scores):
                                no_trade_positions = np.flatnonzero(scores[:, 6] == 1)
                                if len(no_trade_positions):
                                    audit_indexes.add(int(indexes[no_trade_positions[0]]))
                            for anchor in sorted(audit_indexes):
                                pos = int(np.searchsorted(indexes, anchor))
                                side = int(signals[anchor])
                                stop_price = float(low[anchor] if side > 0 else hi[anchor])
                                scalar = _score_one(t_score[:bar_end], o[:bar_end], hi[:bar_end], low[:bar_end], close[:bar_end], atr[:bar_end], anchor, side, stop_price, horizon, rule)
                                vector = scores[pos]
                                audit = cell["scalar_audit"]
                                audit["sampled"] += 1
                                audit["resolved_samples"] += int(scalar[0])
                                audit["tradable_samples"] += int(scalar[0] and not scalar[6])
                                audit["no_trade_samples"] += int(scalar[6])
                                audit["label_mismatches"] += int(
                                    bool(vector[0]) != scalar[0] or bool(vector[1]) != scalar[1]
                                    or bool(vector[2]) != scalar[2] or bool(vector[3]) != scalar[3])
                                audit["no_trade_mismatches"] += int(bool(vector[6]) != scalar[6])
                                if scalar[0] and not scalar[6]:
                                    audit["max_abs_net_r_error"] = max(audit["max_abs_net_r_error"], abs(float(vector[4]) - scalar[4]))
                                    audit["max_abs_stress_net_r_error"] = max(audit["max_abs_stress_net_r_error"], abs(float(vector[5]) - scalar[5]))

                        cell["symbols"].append({"symbol": symbol, "pooled": _metrics(pooled),
                                                "nonoverlap": _metrics(pooled_nonoverlap)})
                        cell.setdefault("pooled", _empty())
                        cell.setdefault("pooled_nonoverlap", _empty())
                        for key in ("issued", "resolved", "wins", "timeouts", "directions", "tradable", "no_trade", "base_r", "stress_r", "momentum_wins", "random_wins", "momentum_no_trade", "random_no_trade"):
                            cell["pooled"][key] += pooled[key]
                            cell["pooled_nonoverlap"][key] += pooled_nonoverlap[key]
            print(f"scored {symbol_number}/{len(symbols)} {symbol}", flush=True)

        for rule in RULES:
            for size in sizes:
                for horizon in HORIZONS:
                    cell = outcomes[rule][str(size)][str(horizon)]
                    pooled = cell["pooled"]
                    pooled_nonoverlap = cell["pooled_nonoverlap"]
                    cell["pooled"] = _metrics(pooled)
                    cell["nonoverlap"] = _metrics(pooled_nonoverlap)
                    cell["folds"] = [
                        {"fold": i + 1, "start_ms": FOLDS[i][0], "end_ms": FOLDS[i][1],
                         **_metrics(agg)}
                        for i, agg in enumerate(cell.pop("_fold_agg"))]
                    cell["nonoverlap_folds"] = [
                        {"fold": i + 1, "n_issued": agg["issued"], "metrics": _metrics(agg)}
                        for i, agg in enumerate(cell.pop("_nonoverlap_fold_agg"))]
                    audit = cell["scalar_audit"]
                    audit["pass"] = _scalar_audit_pass(audit, rule, pooled["no_trade"])
                    freq_gate = frequency["totals"][rule][str(size)]["horizons"][str(horizon)]
                    m = cell["pooled"]
                    performance = {
                        "m2_all_issued_ge_80pct": m["target_first_all_issued"] is not None and m["target_first_all_issued"] >= .80,
                        "base_cost_mean_net_r_positive": m["mean_net_r_base"] is not None and m["mean_net_r_base"] > 0,
                        "not_below_matched_momentum": m["matched_momentum_all_issued"] is not None and m["target_first_all_issued"] >= m["matched_momentum_all_issued"],
                        "not_below_matched_random": m["matched_random_all_issued"] is not None and m["target_first_all_issued"] >= m["matched_random_all_issued"],
                    }
                    data_gates = {
                        "frequency_gate_pass": bool(freq_gate["frequency_gate_pass"]),
                        "path_resolution_ge_95pct": m["path_resolution"] is not None and m["path_resolution"] >= .95,
                        "nonoverlap_n_ge_200": freq_gate["nonoverlap_n"] >= 200,
                        "nonoverlap_symbols_ge_20": freq_gate["nonoverlap_symbols"] >= 20,
                        "scalar_audit_pass": bool(audit["pass"]),
                    }
                    cell["decision"] = ("INCONCLUSIVE_DATA_GATES" if not all(data_gates.values())
                                         else "PRIMARY_SCREEN_SURVIVOR_REVIEW_REQUIRED" if all(performance.values())
                                         else "REJECT_PRIMARY_SCREEN")
                    cell["data_gates"] = data_gates
                    cell["performance_gates"] = performance

        final_hash = _sha256(database)
        if final_hash != EXPECTED_SHA256 or database.stat().st_size != EXPECTED_BYTES:
            raise ValueError("pinned source snapshot changed during outcome replay")
        return {
            "protocol": f"micro-candle-{protocol}-m2",
            "aggregate_sizes_minutes": list(sizes),
            "database": str(database), "database_bytes": EXPECTED_BYTES,
            "database_sha256": final_hash,
            "frequency_report_sha256": _sha256(frequency_path),
            "preregistration_path": str(preregistration.relative_to(REPO_ROOT)),
            "preregistration_sha256": _sha256(preregistration),
            "implementation_source_sha256": {
                "runner": _sha256(Path(__file__).resolve()),
                "frequency_screen": _sha256(Path(__file__).resolve().with_name("micro_multiscale.py")),
                "fixed_resolver": _sha256(Path(__file__).resolve().with_name("micro_candle_m2.py")),
                "dynamic_stop_resolver": _sha256(Path(__file__).resolve().with_name("micro_sweep_m2.py")),
            },
            "completed_through_utc": "2026-11-14T00:29:00Z",
            "costs_round_trip": {"base": BASE_COST, "stress": STRESS_COST},
            "outcome_access": True, "frequency_counts_reconciled_before_scoring": True,
            "folds": [{"fold": i + 1, "start_ms": start, "end_ms": end}
                      for i, (start, end) in enumerate(FOLDS)],
            "symbols": symbols, "symbol_count": len(symbols), "outcomes": outcomes,
        }
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--frequency-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sizes", default="3,5", help="comma-separated aggregate candle sizes")
    parser.add_argument("--protocol", default="phase7-multiscale", help="protocol family")
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite result: {args.output}")
    sizes = tuple(int(value) for value in args.sizes.split(","))
    result = run(args.db, args.frequency_report, sizes, args.protocol)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    summary = {rule: {size: {h: cell["decision"] for h, cell in horizons.items()}
                      for size, horizons in sizes.items()}
               for rule, sizes in result["outcomes"].items()}
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
