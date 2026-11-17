"""Full frozen WFA study for RSI/MACD regular divergence on the local 1m archive.

Read-only input; no network access, exchange API calls, or order submission.
The runner writes a new immutable result directory and refuses to overwrite it.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import time

import numpy as np
import pandas as pd

from . import indicators
from .crypto_divergence_engine import (
    MINUTE_MS, Bars, aggregate_complete_minutes, align_closed_4h_regime,
    closed_4h_features, contiguous_slices, evaluate_divergence_event,
    matched_baseline_sides,
)
from .crypto_divergence_robustness import (
    divergence_signals, drawdown_pct, monte_carlo_reorder_mdd, plateau_summary,
    walk_forward_windows,
)

DB_DEFAULT = Path(__file__).resolve().parent / "data/vision_pit_dev_sample.sqlite"
DATA_SHA256 = "bb64efa272bab6c5bed258ec7284f9212165c8912cfcd824f51863ae5d88fafa"
DATA_START_MS = int(pd.Timestamp("2021-01-01T00:00:00Z").timestamp() * 1000)
DATA_END_MS = int(pd.Timestamp("2026-11-01T00:00:00Z").timestamp() * 1000)
TIMEFRAMES = (1, 5, 15, 30, 60)
HORIZONS = (10, 20)
LAGS = (2, 3, 4)
ENTRIES = ("next_open", "stop_entry")
STOP_BUFFERS = (0.0, 0.25)
TARGETS = (1.0, 1.5, 2.0, 3.0)
OSCILLATORS = ("rsi14", "macd_hist_12_26_9")
FEE_PER_SIDE = 0.0005
BASE_SLIPPAGE_PER_SIDE = 0.00025
STRESS_SLIPPAGE_PER_SIDE = 0.00050
MASTER_SEED = 20261117


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, sort_keys=True, allow_nan=False,
                               separators=(",", ":")) + "\n", encoding="utf-8")
    temp.replace(path)


def _jsonl_write(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True, allow_nan=False,
                                    separators=(",", ":")) + "\n")


def _day_ms(day_number: int) -> int:
    return int(pd.Timestamp(date.fromordinal(day_number), tz="UTC").timestamp() * 1000)


def frozen_windows():
    start_day = date(2022, 1, 1).toordinal()
    windows = walk_forward_windows(start_day)
    for row in windows:
        for key in ("train_start", "train_end", "test_start", "test_end"):
            row[key + "_ms"] = _day_ms(row[key])
    return windows


def expected_grid():
    return [
        {"lag": lag, "entry": entry, "stop_buffer_atr": stop_buffer,
         "target_r": target}
        for lag in LAGS for entry in ENTRIES
        for stop_buffer in STOP_BUFFERS for target in TARGETS
    ]


def _empty_cell():
    return {"emitted": 0, "resolved": 0, "wins": 0, "unresolved": 0,
            "invalid": 0, "filled": 0, "net_r_base_sum": 0.0, "net_r_stress_sum": 0.0,
            "m1_n": 0, "m1_correct": 0}


def _connect_readonly(path: Path):
    uri = path.resolve().as_uri() + "?mode=ro"
    db = sqlite3.connect(uri, uri=True)
    db.execute("PRAGMA query_only=ON")
    return db


def _load_symbols(db):
    return [row[0] for row in db.execute(
        "SELECT DISTINCT symbol FROM archive_manifest ORDER BY symbol")]


def _load_symbol(db, symbol):
    frame = pd.read_sql_query(
        "SELECT open_ms,open,high,low,close,volume FROM candles "
        "WHERE symbol=? AND open_ms>=? AND open_ms<? ORDER BY open_ms",
        db, params=(symbol, DATA_START_MS, DATA_END_MS))
    if frame.empty:
        return None
    return tuple(frame[key].to_numpy(np.int64 if key == "open_ms" else np.float64)
                 for key in ("open_ms", "open", "high", "low", "close", "volume"))


def _bars_for_tf(raw, tf):
    ts, op, hi, lo, cl, vol = raw
    return aggregate_complete_minutes(ts, op, hi, lo, cl, vol, tf)


def _events_by_lag(bars: Bars, macro, osc_name, tf):
    """Yield causal signal records; indicator state restarts after every data gap."""
    o, h, l, c = bars.open, bars.high, bars.low, bars.close
    for segment in contiguous_slices(bars.open_ms, tf):
        if segment.stop - segment.start < 20:
            continue
        so, sh, sl, sc = o[segment], h[segment], l[segment], c[segment]
        if osc_name == "rsi14":
            oscillator = indicators.rsi(sc, 14)
        else:
            _, _, oscillator = indicators.macd(sc, 12, 26, 9)
        atr = indicators.atr(sh, sl, sc, 14)
        local_macro = macro[segment]
        for lag in LAGS:
            for signal in divergence_signals(
                    sh, sl, sc, oscillator, lag=lag,
                    macro_direction=local_macro):
                local_i = signal.index
                global_i = segment.start + local_i
                if not np.isfinite(atr[local_i]):
                    continue
                yield {
                    "index": global_i, "segment": segment,
                    "local_index": local_i, "lag": lag,
                    "side": signal.side, "pivot_stop": signal.pivot_price,
                    "atr": float(atr[local_i]),
                    "signal_ms": int(bars.open_ms[global_i] + tf * MINUTE_MS),
                    "signal_close": float(c[global_i]),
                    "oscillator": osc_name,
                }


def _event_bars(bars, segment):
    return Bars(*(np.asarray(getattr(bars, field)[segment]).copy()
                  for field in ("open_ms", "open", "high", "low", "close", "volume")))


def _label(raw, segment_bars, tf, event, *, horizon, params,
           side=None, pivot_stop=None, mode=None, stress=False):
    ts, op, hi, lo, cl, _ = raw
    use_side = side or event["side"]
    use_pivot = event["pivot_stop"] if pivot_stop is None else pivot_stop
    use_mode = mode or params["entry"]
    slip = STRESS_SLIPPAGE_PER_SIDE if stress else BASE_SLIPPAGE_PER_SIDE
    return evaluate_divergence_event(
        minute_open_ms=ts, minute_opens=op, minute_highs=hi,
        minute_lows=lo, minute_closes=cl, native_bars=segment_bars,
        native_tf_minutes=tf, signal_index=event["local_index"],
        side=use_side, pivot_stop=use_pivot, atr_at_signal=event["atr"],
        stop_buffer_atr=params["stop_buffer_atr"], target_r=params["target_r"],
        horizon_bars=horizon, entry_mode=use_mode, fee_per_side=FEE_PER_SIDE,
        slippage_per_side=slip)


def _event_metric(bucket, outcome, *, m1_correct=None):
    bucket["emitted"] += 1
    if outcome["status"] == "invalid":
        bucket["invalid"] += 1
        return
    if outcome["status"] == "unresolved":
        bucket["unresolved"] += 1
        return
    bucket["resolved"] += 1
    bucket["wins"] += int(bool(outcome["target_first"]))
    if outcome["trade_net_r"] is not None:
        bucket["filled"] += 1
        bucket["net_r_base_sum"] += outcome["trade_net_r"]
    if m1_correct is not None:
        bucket["m1_n"] += 1
        bucket["m1_correct"] += int(m1_correct)


def _scheduled_opportunities(symbol_count, start_ms, end_ms, tf):
    """Every UTC-aligned 24/7 slot, including absent/incomplete market bars."""
    width = tf * MINUTE_MS
    if start_ms % width or end_ms % width or end_ms < start_ms:
        raise ValueError("WFA boundaries must align to the native timeframe")
    return symbol_count * ((end_ms - start_ms) // width)


def _claim_decision(gates, *, exact_family_calibrated=False):
    """Separate absent evidence from a measured failure of a binding gate."""
    evidence_gates = ("nonoverlap_n_200", "nonoverlap_symbols_20",
                      "resolved_path_coverage_95pct")
    if not all(gates.get(name, False) for name in evidence_gates):
        return "INCONCLUSIVE"
    if not all(gates.get(name, False) for name in (
            "m2_point_80pct", "issue_coverage_spec_10pct",
            "filled_trade_net_expectancy_positive")):
        return "REJECT"
    return "PASS" if exact_family_calibrated else "INCONCLUSIVE"


def _train_pass(db_path, symbols, windows):
    cells = defaultdict(_empty_cell)
    opportunities = defaultdict(int)
    started = time.monotonic()
    grid = expected_grid()
    db = _connect_readonly(db_path)
    try:
        for symbol_i, symbol in enumerate(symbols, 1):
            raw = _load_symbol(db, symbol)
            if raw is None:
                continue
            ts, op, hi, lo, cl, vol = raw
            htf_end, htf_direction = closed_4h_features(ts, cl)
            for tf in TIMEFRAMES:
                bars = _bars_for_tf(raw, tf)
                macro = align_closed_4h_regime(htf_end, htf_direction, bars.open_ms, tf)
                segment_cache = {}
                for segment in contiguous_slices(bars.open_ms, tf):
                    segment_cache[(segment.start, segment.stop)] = _event_bars(bars, segment)
                for osc in OSCILLATORS:
                    for event in _events_by_lag(bars, macro, osc, tf):
                        eligible_windows = [w for w in windows if
                            w["train_start_ms"] <= event["signal_ms"] <
                            w["train_end_ms"] - 23 * tf * MINUTE_MS]
                        if not eligible_windows:
                            continue
                        for horizon in HORIZONS:
                            for params in grid:
                                if params["lag"] != event["lag"]:
                                    continue
                                outcome = _label(raw, segment_cache[(event["segment"].start,
                                                                      event["segment"].stop)],
                                                 tf, event, horizon=horizon, params=params)
                                for window in eligible_windows:
                                    fold = window["fold"]
                                    key = (fold, osc, tf, horizon,
                                           params["lag"], params["entry"],
                                           params["stop_buffer_atr"], params["target_r"])
                                    _event_metric(cells[key], outcome)
            print(f"train pass {symbol_i}/{len(symbols)} {symbol}: "
                  f"1m_rows={len(ts)} elapsed={time.monotonic()-started:.1f}s", flush=True)
    finally:
        db.close()
    for window in windows:
        for tf in TIMEFRAMES:
            opportunities[(tf, window["fold"])] = _scheduled_opportunities(
                len(symbols), window["train_start_ms"], window["train_end_ms"], tf)
    return cells, opportunities


def _select(cells, opportunities, windows):
    selections, rows = {}, []
    grid = expected_grid()
    for window in windows:
        fold = window["fold"]
        for osc in OSCILLATORS:
            for tf in TIMEFRAMES:
                for horizon in HORIZONS:
                    cell_rows = []
                    for params in grid:
                        key = (fold, osc, tf, horizon, params["lag"], params["entry"],
                               params["stop_buffer_atr"], params["target_r"])
                        raw = cells.get(key, _empty_cell())
                        emitted, resolved = raw["emitted"], raw["resolved"]
                        path_coverage = resolved / emitted if emitted else 0.0
                        m2 = raw["wins"] / resolved if resolved else None
                        net_ev = (raw["net_r_base_sum"] / raw["filled"]
                                  if raw["filled"] else None)
                        row = {
                            "fold": fold, "oscillator": osc, "timeframe_min": tf,
                            "horizon_bars": horizon, "params": params,
                            "emitted": emitted, "resolved_n": resolved,
                        "unresolved": raw["unresolved"], "invalid": raw["invalid"], "m2": m2,
                            "net_expectancy_r_per_resolved_signal": net_ev,
                            "path_coverage": path_coverage,
                            "resolved": bool(emitted and path_coverage >= 0.95),
                            "n": resolved,
                            "net_expectancy": net_ev if net_ev is not None else 0.0,
                            "issue_coverage_train": (emitted / opportunities[(tf, fold)]
                                                     if opportunities[(tf, fold)] else 0.0),
                        }
                        cell_rows.append(row)
                    plateau = plateau_summary(cell_rows, expected_params=grid)
                    plateau_by_params = {tuple(sorted(p["params"].items())): p for p in plateau}
                    for row in cell_rows:
                        row.update(plateau_by_params[tuple(sorted(row["params"].items()))])
                        rows.append(row)
                    eligible = [r for r in cell_rows if r["plateau_robust"]
                                and r["m2"] is not None and r["m2"] >= 0.80
                                and r["resolved_n"] >= 30
                                and r["net_expectancy_r_per_resolved_signal"] is not None
                                and r["net_expectancy_r_per_resolved_signal"] > 0]
                    eligible.sort(key=lambda r: (
                        -r["m2"], -r["net_expectancy_r_per_resolved_signal"],
                        r["params"]["lag"], ENTRIES.index(r["params"]["entry"]),
                        r["params"]["stop_buffer_atr"], r["params"]["target_r"]))
                    key = (fold, osc, tf, horizon)
                    selections[key] = eligible[0]["params"] if eligible else None
    return selections, rows


def _m1_correct(bars, event, side, horizon):
    end_i = event["local_index"] + horizon
    if end_i >= len(bars.close):
        return None
    close = float(bars.close[end_i])
    return close > event["signal_close"] if side == "long" else close < event["signal_close"]


def _previous_completed_close(bars, event):
    i = event["local_index"]
    return float(bars.close[i - 1]) if i > 0 else float(event["signal_close"])


def _oos_pass(db_path, symbols, windows, selections):
    summary = defaultdict(lambda: {"emitted": 0, "resolved": 0, "wins": 0,
            "unresolved": 0, "invalid": 0, "censored": 0, "filled": 0,
                                   "baseline_momentum_wins": 0,
                                   "baseline_random_wins": 0,
                                   "baseline_momentum_resolved": 0,
                                   "baseline_random_resolved": 0,
                                   "paired_momentum_n": 0, "paired_momentum_delta_sum": 0,
                                   "paired_random_n": 0, "paired_random_delta_sum": 0,
                                   "m1_n": 0,
                                   "m1_correct": 0, "net_r_base_sum": 0.0,
                                   "net_r_stress_sum": 0.0,
                                   "trades": [], "signals": [],
                                   "nonoverlap": [], "folds": {}})
    all_events = []
    opportunities_test = defaultdict(int)
    db = _connect_readonly(db_path)
    started = time.monotonic()
    try:
        for symbol_i, symbol in enumerate(symbols, 1):
            raw = _load_symbol(db, symbol)
            if raw is None:
                continue
            ts, op, hi, lo, cl, vol = raw
            htf_end, htf_direction = closed_4h_features(ts, cl)
            for tf in TIMEFRAMES:
                bars = _bars_for_tf(raw, tf)
                macro = align_closed_4h_regime(htf_end, htf_direction, bars.open_ms, tf)
                segment_cache = {}
                for segment in contiguous_slices(bars.open_ms, tf):
                    segment_cache[(segment.start, segment.stop)] = _event_bars(bars, segment)
                for window in windows:
                    fold = window["fold"]
                for osc in OSCILLATORS:
                    for event in _events_by_lag(bars, macro, osc, tf):
                        segment_bars = segment_cache[(event["segment"].start,
                                                      event["segment"].stop)]
                        for horizon in HORIZONS:
                            for window in windows:
                                fold = window["fold"]
                                params = selections[(fold, osc, tf, horizon)]
                                if params is None or event["lag"] != params["lag"]:
                                    continue
                                complete_end = event["signal_ms"] + (3 + horizon) * tf * MINUTE_MS
                                if not (window["test_start_ms"] <= event["signal_ms"]
                                        < window["test_end_ms"]):
                                    continue
                                censored = complete_end > window["test_end_ms"]
                                if censored:
                                    unresolved = {"status": "unresolved", "target_first": None,
                                                  "entry_ms": None, "entry_price": None,
                                                  "exit_price": None, "trade_net_r": None}
                                    candidate = candidate_stress = unresolved.copy()
                                else:
                                    candidate = _label(raw, segment_bars, tf, event,
                                                       horizon=horizon, params=params)
                                    candidate_stress = _label(raw, segment_bars, tf, event,
                                                              horizon=horizon, params=params,
                                                              stress=True)
                                sides = matched_baseline_sides(
                                    _previous_completed_close(segment_bars, event),
                                    event["signal_close"], symbol=symbol,
                                    timeframe_minutes=tf, anchor_ms=event["signal_ms"],
                                    seed=MASTER_SEED)
                                baseline_outcomes = {}
                                entry_i = event["local_index"] + 1
                                common_entry = (float(segment_bars.open[entry_i])
                                                if entry_i < len(segment_bars.open) else None)
                                candidate_stop = (event["pivot_stop"] - params["stop_buffer_atr"] * event["atr"]
                                                  if event["side"] == "long" else
                                                  event["pivot_stop"] + params["stop_buffer_atr"] * event["atr"])
                                ex_ante_distance = abs(event["signal_close"] - candidate_stop)
                                for baseline_name, baseline_side in sides.items():
                                    if censored or common_entry is None:
                                        baseline_outcomes[baseline_name] = unresolved.copy()
                                        continue
                                    baseline_stop = (common_entry - ex_ante_distance
                                                     if baseline_side == "long" else
                                                     common_entry + ex_ante_distance)
                                    baseline_params = {"entry": "next_open",
                                                       "stop_buffer_atr": 0.0,
                                                       "target_r": params["target_r"]}
                                    baseline_outcomes[baseline_name] = _label(
                                        raw, segment_bars, tf, event, horizon=horizon,
                                        params=baseline_params, side=baseline_side,
                                        pivot_stop=baseline_stop, mode="next_open")
                                m1 = (None if censored else
                                      _m1_correct(segment_bars, event, event["side"], horizon))
                                rec = {
                                    "symbol": symbol, "fold": fold, "oscillator": osc,
                                    "timeframe_min": tf, "horizon_bars": horizon,
                                    "params": params, "signal_ms": event["signal_ms"],
                                    "anchor_ms": int(bars.open_ms[event["index"] - event["lag"]]),
                                    "side": event["side"], "candidate": candidate,
                                    "candidate_stress": candidate_stress,
                                    "baselines": baseline_outcomes,
                                    "m1_correct": m1,
                                    "censored": censored,
                                }
                                all_events.append(rec)
            print(f"OOS pass {symbol_i}/{len(symbols)} {symbol}: "
                  f"rows={len(ts)} events={len(all_events)} elapsed={time.monotonic()-started:.1f}s",
                  flush=True)
    finally:
        db.close()

    for window in windows:
        for tf in TIMEFRAMES:
            opportunities_test[(tf, window["fold"])] = _scheduled_opportunities(
                len(symbols), window["test_start_ms"], window["test_end_ms"], tf)

    # Stable order for chronological metrics and outcome-blind non-overlap selection.
    all_events.sort(key=lambda x: (x["oscillator"], x["timeframe_min"],
                                   x["horizon_bars"], x["fold"], x["symbol"], x["signal_ms"]))
    last_allowed = {}
    for event in all_events:
        claim = (event["oscillator"], event["timeframe_min"], event["horizon_bars"])
        out = summary[claim]
        fold_out = out["folds"].setdefault(event["fold"], {
            "emitted": 0, "resolved": 0, "wins": 0, "unresolved": 0,
            "invalid": 0, "censored": 0, "filled": 0, "m1_n": 0, "m1_correct": 0,
            "baseline_momentum_wins": 0, "baseline_random_wins": 0,
            "baseline_momentum_resolved": 0,
            "baseline_random_resolved": 0,
            "paired_momentum_n": 0, "paired_momentum_delta_sum": 0,
            "paired_random_n": 0, "paired_random_delta_sum": 0,
            "trades": [], "params": event["params"],
        })
        candidate = event["candidate"]
        out["emitted"] += 1; fold_out["emitted"] += 1
        if event["censored"]:
            out["censored"] += 1; fold_out["censored"] += 1
        if candidate["status"] == "invalid":
            out["invalid"] += 1; fold_out["invalid"] += 1
        elif candidate["status"] == "unresolved":
            out["unresolved"] += 1; fold_out["unresolved"] += 1
        else:
            out["resolved"] += 1; fold_out["resolved"] += 1
            win = int(bool(candidate["target_first"]))
            out["wins"] += win; fold_out["wins"] += win
        for baseline_name, baseline in event["baselines"].items():
            if baseline["status"] != "unresolved":
                baseline_win = int(bool(baseline["target_first"]))
                out[f"baseline_{baseline_name}_wins"] += baseline_win
                fold_out[f"baseline_{baseline_name}_wins"] += baseline_win
                out[f"baseline_{baseline_name}_resolved"] += 1
                fold_out[f"baseline_{baseline_name}_resolved"] += 1
                if candidate["status"] != "unresolved":
                    paired_name = f"paired_{baseline_name}"
                    out[f"{paired_name}_n"] += 1
                    fold_out[f"{paired_name}_n"] += 1
                    delta = int(bool(candidate["target_first"])) - baseline_win
                    out[f"{paired_name}_delta_sum"] += delta
                    fold_out[f"{paired_name}_delta_sum"] += delta
        if event["m1_correct"] is not None:
            out["m1_n"] += 1; out["m1_correct"] += int(event["m1_correct"])
            fold_out["m1_n"] += 1; fold_out["m1_correct"] += int(event["m1_correct"])
        if candidate["trade_net_r"] is not None:
            out["filled"] += 1; fold_out["filled"] += 1
            out["net_r_base_sum"] += candidate["trade_net_r"]
            out["net_r_stress_sum"] += event["candidate_stress"]["trade_net_r"]
            trade = {"entry_ms": candidate["entry_ms"], "symbol": event["symbol"],
                     "net_r_base": candidate["trade_net_r"],
                     "net_r_stress": event["candidate_stress"]["trade_net_r"]}
            out["trades"].append(trade); fold_out["trades"].append(trade)
        nkey = (claim, event["symbol"])
        permitted = last_allowed.get(nkey, -1)
        selected_nonoverlap = event["signal_ms"] >= permitted
        out["signals"].append(event)
        if selected_nonoverlap:
            out["nonoverlap"].append(event)
            last_allowed[nkey] = event["signal_ms"] + (3 + event["horizon_bars"]) * event["timeframe_min"] * MINUTE_MS

    return all_events, summary, opportunities_test


def _final_report(out_dir, symbols, windows, selections, train_rows,
                  oos_events, oos_summary, opportunities_test):
    claims = []
    for osc in OSCILLATORS:
        for tf in TIMEFRAMES:
            for horizon in HORIZONS:
                key = (osc, tf, horizon)
                raw = oos_summary[key]
                emitted = raw["emitted"]
                resolved = raw["resolved"]
                m2 = raw["wins"] / resolved if resolved else None
                m2_all_failure = raw["wins"] / emitted if emitted else None
                coverage = resolved / emitted if emitted else 0.0
                mom_denom = raw["baseline_momentum_resolved"]
                random_denom = raw["baseline_random_resolved"]
                mom_m2 = raw["baseline_momentum_wins"] / mom_denom if mom_denom else None
                random_m2 = raw["baseline_random_wins"] / random_denom if random_denom else None
                nonoverlap = raw["nonoverlap"]
                nonoverlap_symbols = len({event["symbol"] for event in nonoverlap})
                issue_coverage_n = len(raw["signals"])
                opps = sum(opportunities_test[(tf, fold)] for fold in range(1, 6))
                issue_coverage = issue_coverage_n / opps if opps else 0.0
                ordered_trades = sorted(raw["trades"], key=lambda x: (x["entry_ms"], x["symbol"]))
                base_mc = (monte_carlo_reorder_mdd(
                    [t["net_r_base"] for t in ordered_trades],
                    seed=MASTER_SEED + OSCILLATORS.index(osc) * 10_000 + tf * 100 + horizon)
                    if ordered_trades else None)
                stress_mc = (monte_carlo_reorder_mdd(
                    [t["net_r_stress"] for t in ordered_trades],
                    seed=MASTER_SEED + 1_000_000 + OSCILLATORS.index(osc) * 10_000 + tf * 100 + horizon)
                    if ordered_trades else None)
                folds = []
                for fold in range(1, 6):
                    selected = selections[(fold, osc, tf, horizon)]
                    f = raw["folds"].get(fold, {})
                    train_match = next((r for r in train_rows
                                        if r["fold"] == fold and r["oscillator"] == osc
                                        and r["timeframe_min"] == tf
                                        and r["horizon_bars"] == horizon
                                        and r["params"] == selected), None) if selected else None
                    fold_trades = sorted(f.get("trades", []),
                                         key=lambda x: (x["entry_ms"], x["symbol"]))
                    fold_base_mdd = (drawdown_pct(np.asarray(
                        [t["net_r_base"] for t in fold_trades]) * 0.01)
                                     if fold_trades else None)
                    fold_stress_mdd = (drawdown_pct(np.asarray(
                        [t["net_r_stress"] for t in fold_trades]) * 0.01)
                                       if fold_trades else None)
                    folds.append({"fold": fold, "selected_params": selected,
                                  "emitted": f.get("emitted", 0),
                                  "resolved": f.get("resolved", 0),
                                  "unresolved": f.get("unresolved", 0),
                                  "invalid": f.get("invalid", 0),
                                  "censored": f.get("censored", 0),
                                  "path_coverage": (f.get("resolved", 0) / f["emitted"]
                                                    if f.get("emitted", 0) else 0.0),
                                  "target_first": f.get("wins", 0),
                                  "oos_m2": (f.get("wins", 0) / f["resolved"]
                                             if f.get("resolved", 0) else None),
                                  "train_m2_selected": (train_match["m2"]
                                                        if train_match else None),
                                  "train_to_test_m2_change_pp": (
                                      100 * (f.get("wins", 0) / f["resolved"] - train_match["m2"])
                                      if train_match and f.get("resolved", 0)
                                      and train_match["m2"] is not None else None),
                                  "filled_trades": f.get("filled", 0),
                                  "mean_net_r_per_filled_trade_base": (
                                      sum(t["net_r_base"] for t in fold_trades) / len(fold_trades)
                                      if fold_trades else None),
                                  "historical_mdd_base_pct": fold_base_mdd,
                                  "historical_mdd_stress_pct": fold_stress_mdd,
                                  "m1_n": f.get("m1_n", 0),
                                  "m1_accuracy": (f.get("m1_correct", 0) / f["m1_n"]
                                                  if f.get("m1_n", 0) else None)})
                gates = {
                    "m2_point_80pct": m2 is not None and m2 >= 0.80,
                    "nonoverlap_n_200": len(nonoverlap) >= 200,
                    "nonoverlap_symbols_20": nonoverlap_symbols >= 20,
                    "resolved_path_coverage_95pct": coverage >= 0.95,
                    "issue_coverage_spec_10pct": issue_coverage >= 0.10,
                    "filled_trade_net_expectancy_positive": (
                        raw["net_r_base_sum"] / raw["filled"] > 0 if raw["filled"] else False),
                    "exact_family_baseline_inference_calibrated": False,
                }
                decision = _claim_decision(
                    gates, exact_family_calibrated=
                    gates["exact_family_baseline_inference_calibrated"])
                claims.append({
                    "oscillator": osc, "timeframe_min": tf, "horizon_bars": horizon,
                    "signals": emitted, "resolved": resolved,
                    "unresolved": raw["unresolved"],
                    "invalid": raw["invalid"], "censored": raw["censored"],
                    "m2_target_first_resolved": m2,
                    "m2_unresolved_as_loss": m2_all_failure,
                    "path_coverage": coverage,
                    "direction_accuracy_at_deadline": (raw["m1_correct"] / raw["m1_n"]
                                                        if raw["m1_n"] else None),
                    "direction_n": raw["m1_n"], "baseline_momentum_m2": mom_m2,
                    "baseline_random_m2": random_m2,
                    "paired_momentum_n": raw["paired_momentum_n"],
                    "paired_momentum_delta": (
                        raw["paired_momentum_delta_sum"] / raw["paired_momentum_n"]
                        if raw["paired_momentum_n"] else None),
                    "paired_random_n": raw["paired_random_n"],
                    "paired_random_delta": (
                        raw["paired_random_delta_sum"] / raw["paired_random_n"]
                        if raw["paired_random_n"] else None),
                    "coverage_issue_rate": issue_coverage,
                    "scheduled_symbol_bar_opportunities": opps,
                    "nonoverlap_n": len(nonoverlap),
                    "nonoverlap_symbols": nonoverlap_symbols,
                    "filled_trades": raw["filled"],
                    "mean_net_r_per_filled_trade_base": (raw["net_r_base_sum"] / raw["filled"]
                                                          if raw["filled"] else None),
                    "mean_net_r_per_filled_trade_stress": (raw["net_r_stress_sum"] / raw["filled"]
                                                            if raw["filled"] else None),
                    "mean_net_r_per_resolved_signal_base": (raw["net_r_base_sum"] / resolved
                                                             if resolved else None),
                    "monte_carlo_1000_base": base_mc,
                    "monte_carlo_1000_stress": stress_mc,
                    "folds": folds, "gates": gates,
                    "decision": decision,
                })
    _jsonl_write(out_dir / "train_cells.jsonl", train_rows)
    _jsonl_write(out_dir / "oos_events.jsonl", oos_events)
    _atomic_json(out_dir / "summary.json", {"claims": claims})
    lines = ["# Crypto divergence walk-forward backtest", "",
             "Status: historical OOS study completed; no live-trading authorization.",
             "Baseline-superiority promotion remains INCONCLUSIVE until exact 20-claim/40-contrast synthetic calibration passes.",
             "Universe is the archive_manifest cohort, not proven point-in-time exchange membership.", "",
             "| Oscillator | TF | H | OOS signals | M2 | unresolved | path coverage | issue coverage | nonoverlap N/symbols | filled | mean net R | MC P95 MDD | decision |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    for c in claims:
        mc = c["monte_carlo_1000_base"]
        p95 = mc["permuted_mdd_p95_pct"] if mc else None
        fmt = lambda x: "—" if x is None else f"{x:.2%}"
        lines.append(f"| {c['oscillator']} | {c['timeframe_min']}m | {c['horizon_bars']} | {c['signals']} | {fmt(c['m2_target_first_resolved'])} | {c['unresolved']} | {fmt(c['path_coverage'])} | {fmt(c['coverage_issue_rate'])} | {c['nonoverlap_n']}/{c['nonoverlap_symbols']} | {c['filled_trades']} | {c['mean_net_r_per_filled_trade_base'] if c['mean_net_r_per_filled_trade_base'] is not None else '—'} | {fmt(p95 / 100 if p95 is not None else None)} | {c['decision']} |")
    (out_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return claims


def run(db_path: Path, out_dir: Path, *, verify_hash=True):
    db_path = db_path.resolve()
    if not db_path.is_file():
        raise FileNotFoundError(db_path)
    if out_dir.exists():
        raise FileExistsError(f"refusing to overwrite existing run directory: {out_dir}")
    windows = frozen_windows()
    data_sha = _sha256(db_path) if verify_hash else None
    if verify_hash and data_sha != DATA_SHA256:
        raise ValueError(f"data SHA mismatch: {data_sha}")
    db = _connect_readonly(db_path)
    try:
        symbols = _load_symbols(db)
    finally:
        db.close()
    if len(symbols) != 86:
        raise ValueError(f"frozen archive universe expected 86 symbols, found {len(symbols)}")
    out_dir.mkdir(parents=True)
    manifest = {
        "study_id": "crypto-divergence-wfa-v1",
        "market_data_read": "metadata-only so far; full run reads OHLC outcomes",
        "db_path": str(db_path), "data_sha256": data_sha,
        "symbols_sha256": hashlib.sha256("\n".join(symbols).encode()).hexdigest(),
        "symbols": symbols, "windows": windows,
        "timeframes_min": list(TIMEFRAMES), "horizons_bars": list(HORIZONS),
        "oscillators": list(OSCILLATORS), "expected_cell_count": 4800,
        "entry_modes": list(ENTRIES), "pivot_lags": list(LAGS),
        "stop_buffer_atr": list(STOP_BUFFERS), "target_r": list(TARGETS),
        "fees_per_side": FEE_PER_SIDE,
        "base_slippage_per_side": BASE_SLIPPAGE_PER_SIDE,
        "stress_slippage_per_side": STRESS_SLIPPAGE_PER_SIDE,
        "monte_carlo_sims": 1000, "risk_fraction": 0.01,
        "path_coverage_gate": 0.95, "issue_coverage_gate": 0.10,
        "purge_native_bars": 23,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }
    _atomic_json(out_dir / "manifest.json", manifest)
    train_cells, opportunities_train = _train_pass(db_path, symbols, windows)
    selections, train_rows = _select(train_cells, opportunities_train, windows)
    _atomic_json(out_dir / "selections.json", {
        "selections": [{"fold": f, "oscillator": o, "timeframe_min": tf,
                        "horizon_bars": h, "params": p}
                       for (f, o, tf, h), p in selections.items()]})
    oos_events, oos_summary, opportunities_test = _oos_pass(
        db_path, symbols, windows, selections)
    claims = _final_report(out_dir, symbols, windows, selections,
                           train_rows, oos_events, oos_summary, opportunities_test)
    manifest["market_data_read"] = True
    manifest["completed_claims"] = len(claims)
    manifest["completed_train_cells"] = len(train_rows)
    manifest["oos_event_rows"] = len(oos_events)
    manifest["source_sha256"] = _sha256(Path(__file__).resolve())
    _atomic_json(out_dir / "manifest.json", manifest)
    return {"claims": len(claims), "train_cells": len(train_rows),
            "oos_events": len(oos_events), "out_dir": str(out_dir)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DB_DEFAULT)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--skip-data-hash", action="store_true",
                        help="development only; result is not promotion-eligible")
    args = parser.parse_args()
    result = run(args.db, args.out, verify_hash=not args.skip_data_hash)
    print(json.dumps(result, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
