#!/usr/bin/env python3
"""Development-only exhaustive subset consensus replay for four frozen P8 rules.

Reads a Binance Vision-derived SQLite candle DB read-only. It deliberately uses
the complete historical development archive and makes no validation claim.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import itertools
import json
import math
import sqlite3
import time
from pathlib import Path

import numpy as np
import pandas as pd

from chart_predictor.indicators import atr, rsi, vwap, supertrend_direction
from chart_predictor.indicators import candle_patterns
from chart_predictor.resample import resample_frame, TIMEFRAME_MINUTES
from chart_predictor.setups import generate_signals

RULES = ("bb_squeeze_breakout", "orb_funding_session", "vwap_band_fade",
         "volume_climax_exhaustion")
TFS = tuple(TIMEFRAME_MINUTES)
FEE_PER_SIDE = 0.0005
TARGET_R = 2.0
HORIZON_MULTIPLES = (10, 20)
TARGET_R_MULTIPLES = (0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0)


def enumerate_subsets():
    return [s for k in range(1, len(RULES) + 1)
            for s in itertools.combinations(RULES, k)]


def combine_at_bar(signals_by_rule, subset, bar_index):
    """Strict majority of the frozen subset; ties/abstentions produce no event."""
    votes = []
    for rule in subset:
        vote = signals_by_rule[rule].get(bar_index)
        if vote is not None:
            votes.append(vote)
    longs = sum(side == "long" for side, _ in votes)
    shorts = sum(side == "short" for side, _ in votes)
    if max(longs, shorts) <= len(subset) / 2:
        return None
    side = "long" if longs > shorts else "short"
    agreeing = [stop for vote_side, stop in votes if vote_side == side]
    return side, float(np.median(agreeing))


def wilson_interval(successes, n):
    if not n:
        return [None, None]
    z = 1.959963984540054
    p = successes / n
    den = 1 + z*z/n
    mid = (p + z*z/(2*n))/den
    rad = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))/den
    return [mid-rad, mid+rad]


def evaluate_event_grid(frame, raw_times, raw_open, raw_high, raw_low, raw_trades,
                        signal_i, side, stop, horizon_bars, target_multiples):
    entry_i = signal_i + 1
    if entry_i >= len(frame):
        return None
    entry = float(frame.o.iloc[entry_i])
    sign = 1 if side == "long" else -1
    risk = sign * (entry - stop)
    if not math.isfinite(risk) or risk <= 0:
        return None
    last_i = entry_i + horizon_bars - 1
    begin_ms = int(frame.t_open_ms.iloc[entry_i])
    end_ms = begin_ms + horizon_bars * 60_000 * int(frame.attrs["tf_minutes"])
    lo = int(np.searchsorted(raw_times, begin_ms, side="left"))
    hi = int(np.searchsorted(raw_times, end_ms, side="left"))
    if hi <= lo:
        return None
    if not target_multiples or any(not math.isfinite(float(x)) or x <= 0
                                   for x in target_multiples):
        raise ValueError("target multiples must be finite and positive")
    if tuple(sorted(set(target_multiples))) != tuple(target_multiples):
        raise ValueError("target multiples must be sorted and unique")
    exits = {float(mult): None for mult in target_multiples}
    for j in range(lo, hi):
        if raw_trades[j] <= 0:
            continue
        hit_stop = raw_low[j] <= stop if side == "long" else raw_high[j] >= stop
        if hit_stop:
            stop_price = float(raw_open[j]) if (
                (side == "long" and raw_open[j] < stop)
                or (side == "short" and raw_open[j] > stop)) else stop
            for mult in target_multiples:
                exits[float(mult)] = exits[float(mult)] or (
                    "stop", float(stop_price), int(raw_times[j]))
            break
        for mult in target_multiples:
            key = float(mult)
            if exits[key] is not None:
                continue
            target = entry + sign * key * risk
            hit_target = raw_high[j] >= target if side == "long" else raw_low[j] <= target
            if hit_target:
                exits[key] = ("target", float(target), int(raw_times[j]))
        if all(value is not None for value in exits.values()):
            break
    deadline_direction_correct = sign * (float(frame.c.iloc[last_i]) / entry - 1) > 0
    output = {}
    for mult in target_multiples:
        reason, exit_price, exit_ms = exits[float(mult)] or (
            "timeout", float(frame.c.iloc[last_i]), int(raw_times[hi - 1]))
        gross = sign * (exit_price / entry - 1.0)
        net = gross - 2 * FEE_PER_SIDE
        output[float(mult)] = {"reason": reason, "net_pct": 100 * net,
                               "net_r": net / (risk / entry), "exit_ms": exit_ms,
                               "deadline_direction_correct": deadline_direction_correct}
    return output


def evaluate_event(frame, raw_times, raw_open, raw_high, raw_low, raw_trades,
                   signal_i, side, stop, horizon_bars):
    """Compatibility wrapper for the R033 2R barrier replay tests."""
    grid = evaluate_event_grid(frame, raw_times, raw_open, raw_high, raw_low,
                               raw_trades, signal_i, side, stop, horizon_bars,
                               (TARGET_R,))
    return None if grid is None else grid[TARGET_R]


def parse_settlement_ms(value):
    """Parse an explicit UTC settlement timestamp or millisecond epoch."""
    if isinstance(value, bool):
        raise ValueError("settlement timestamp cannot be boolean")
    if isinstance(value, int):
        return value
    if not isinstance(value, str):
        raise ValueError("settlement timestamp must be UTC ISO text or integer milliseconds")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ValueError("settlement timestamp must include UTC timezone")
    return int(parsed.timestamp() * 1000)


def epoch_window_rejection(frame, raw, signal_i, horizon_bars, settlement_ms=None):
    """Reject events without fresh traded anchors or a complete executable horizon.

    Barriers are evaluated on traded 1m rows. A forecast is anchored only when
    the signal bar's final minute traded; entry is allowed only when the next
    bar's first minute traded. Require a complete, contiguous forecast horizon.
    Near futures settlement, do not open inside the exchange's 30-minute
    restriction window and do not carry a label beyond settlement.
    """
    width_ms = int(frame.attrs["tf_minutes"]) * 60_000
    entry_i = signal_i + 1
    if entry_i >= len(frame):
        return "missing_entry_bar"
    signal_close_ms = int(frame.t_open_ms.iloc[signal_i]) + width_ms
    entry_ms = int(frame.t_open_ms.iloc[entry_i])
    if entry_ms != signal_close_ms:
        return "gap_between_signal_and_entry"
    if int(frame.trades.iloc[signal_i]) <= 0:
        return "signal_bar_no_trades"
    signal_last_minute = int(frame.t_open_ms.iloc[signal_i]) + width_ms - 60_000
    signal_raw_i = int(np.searchsorted(raw.t_open_ms.to_numpy(), signal_last_minute))
    if (signal_raw_i >= len(raw) or int(raw.t_open_ms.iloc[signal_raw_i]) != signal_last_minute
            or int(raw.trades.iloc[signal_raw_i]) <= 0):
        return "signal_close_stale"

    if int(frame.trades.iloc[entry_i]) <= 0:
        return "entry_bar_no_trades"
    entry_raw_i = int(np.searchsorted(raw.t_open_ms.to_numpy(), entry_ms))
    if (entry_raw_i >= len(raw) or int(raw.t_open_ms.iloc[entry_raw_i]) != entry_ms
            or int(raw.trades.iloc[entry_raw_i]) <= 0):
        return "entry_open_not_executable"

    end_i = entry_i + horizon_bars
    if end_i > len(frame):
        return "incomplete_full_horizon"
    bar_times = frame.t_open_ms.iloc[entry_i:end_i].to_numpy(np.int64)
    if len(bar_times) != horizon_bars or np.any(np.diff(bar_times) != width_ms):
        return "gap_in_timeframe_horizon"
    end_ms = entry_ms + horizon_bars * width_ms
    raw_times = raw.t_open_ms.to_numpy(np.int64)
    lo = int(np.searchsorted(raw_times, entry_ms, side="left"))
    hi = int(np.searchsorted(raw_times, end_ms, side="left"))
    expected_minutes = horizon_bars * width_ms // 60_000
    if hi - lo != expected_minutes:
        return "gap_in_1m_execution_path"
    if int(raw.trades.iloc[hi - 1]) <= 0:
        return "timeout_mark_stale"

    if settlement_ms is not None:
        if entry_ms >= settlement_ms - 30 * 60_000:
            return "exchange_no_new_positions_window"
        if end_ms > settlement_ms:
            return "horizon_crosses_settlement"
    return None


def load_settlements(path):
    if path is None:
        return {}
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("settlements JSON must be a symbol-to-UTC-time object")
    return {symbol: parse_settlement_ms(value) for symbol, value in payload.items()}


def latest_closed_directions(htf_open_ms, htf_directions, htf_width_ms,
                             signal_open_ms, signal_width_ms):
    """Map each signal close to the latest HTF bar fully closed by that time."""
    htf_open_ms = np.asarray(htf_open_ms, dtype=np.int64)
    htf_directions = np.asarray(htf_directions, dtype=np.int64)
    signal_open_ms = np.asarray(signal_open_ms, dtype=np.int64)
    if len(htf_open_ms) != len(htf_directions):
        raise ValueError("HTF timestamps and directions must have equal length")
    out = np.zeros(len(signal_open_ms), dtype=np.int64)
    if not len(htf_open_ms):
        return out
    htf_close_ms = htf_open_ms + int(htf_width_ms)
    signal_close_ms = signal_open_ms + int(signal_width_ms)
    indices = np.searchsorted(htf_close_ms, signal_close_ms, side="right") - 1
    valid = indices >= 0
    out[valid] = htf_directions[indices[valid]]
    return out


def resample_daily_frame(frame):
    """Build only complete UTC daily candles; retain trade-count semantics."""
    if frame.empty:
        return frame.assign(bucket=pd.Series(dtype="int64"))
    df = frame.copy()
    timestamps = df.t_open_ms.astype("int64")
    df = df[(timestamps % 60_000) == 0].copy()
    df["bucket"] = (df.t_open_ms.astype("int64") // 86_400_000) * 86_400_000
    grouped = df.groupby("bucket", sort=True)
    daily = grouped.agg(o=("o", "first"), h=("h", "max"), l=("l", "min"),
                        c=("c", "last"), v=("v", "sum"),
                        quote_v=("quote_v", "sum"), trades=("trades", "sum"),
                        count=("t_open_ms", "nunique"))
    daily = daily[daily["count"] == 1440].drop(columns="count")
    daily.index.name = "t_open_ms"
    return daily.reset_index()


def load_symbols(path, connection):
    if path is None:
        return [r[0] for r in connection.execute(
            "SELECT DISTINCT symbol FROM candles ORDER BY symbol")]
    symbols = json.loads(Path(path).read_text(encoding="utf-8"))
    if (not isinstance(symbols, list) or not symbols
            or any(not isinstance(s, str) or not s for s in symbols)
            or symbols != sorted(set(symbols))):
        raise ValueError("symbols JSON must be a nonempty sorted unique list of strings")
    return symbols


def empty_accumulator():
    return {"n": 0, "wins": 0, "direction_hits": 0, "timeouts": 0,
            "sum_net_pct": 0.0, "sum_net_r": 0.0,
            "positive_net_pct": 0.0, "negative_net_pct": 0.0,
            "per_symbol": {}}


def add_to_accumulator(acc, trade, symbol):
    net_pct = float(trade["net_pct"])
    row = acc["per_symbol"].setdefault(symbol, {
        "n": 0, "wins": 0, "direction_hits": 0, "timeouts": 0,
        "sum_net_pct": 0.0, "sum_net_r": 0.0,
        "positive_net_pct": 0.0, "negative_net_pct": 0.0,
    })
    for target in (acc, row):
        target["n"] += 1
        target["wins"] += trade["reason"] == "target"
        target["direction_hits"] += bool(trade["deadline_direction_correct"])
        target["timeouts"] += trade["reason"] == "timeout"
        target["sum_net_pct"] += net_pct
        target["sum_net_r"] += float(trade["net_r"])
        target["positive_net_pct"] += max(0.0, net_pct)
        target["negative_net_pct"] += max(0.0, -net_pct)


def summarize_accumulator(acc):
    n = acc["n"]
    if not n:
        return {"n": 0, "target_first_pct": None,
                "target_first_wilson95_pct": [None, None],
                "deadline_direction_accuracy": None,
                "deadline_direction_wilson95_pct": [None, None],
                "mean_net_pct": None,
                "sum_trade_net_pct": 0.0, "profit_factor": None,
                "timeout_pct": None, "symbols": 0, "per_symbol": {}}
    per_symbol = {}
    for symbol, sample in sorted(acc["per_symbol"].items()):
        sn = sample["n"]
        per_symbol[symbol] = {
            "n": sn,
            "target_first_pct": 100 * sample["wins"] / sn,
            "deadline_direction_accuracy": sample["direction_hits"] / sn,
            "mean_net_pct": sample["sum_net_pct"] / sn,
        }
    return {"n": n, "target_first_pct": 100 * acc["wins"] / n,
            "target_first_wilson95_pct": [100 * x for x in wilson_interval(acc["wins"], n)],
            "deadline_direction_accuracy": acc["direction_hits"] / n,
            "deadline_direction_wilson95_pct": [
                100 * x for x in wilson_interval(acc["direction_hits"], n)],
            "mean_net_pct": acc["sum_net_pct"] / n,
            "sum_trade_net_pct": acc["sum_net_pct"],
            "mean_net_r": acc["sum_net_r"] / n,
            "profit_factor": (acc["positive_net_pct"] / acc["negative_net_pct"]
                              if acc["negative_net_pct"] else None),
            "timeout_pct": 100 * acc["timeouts"] / n,
            "symbols": len(per_symbol), "per_symbol": per_symbol}


def summarize(trades):
    acc = empty_accumulator()
    for trade in trades:
        add_to_accumulator(acc, trade, trade["symbol"])
    return summarize_accumulator(acc)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--settlements-json")
    parser.add_argument("--symbols-json")
    args = parser.parse_args()
    settlements = load_settlements(args.settlements_json)
    db_path = Path(args.db).resolve()
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    symbols = load_symbols(args.symbols_json, con)
    subsets = enumerate_subsets()
    groups = {(subset, tf, regime, horizon, target_r): empty_accumulator()
              for subset in subsets for tf in TFS
              for regime in ("unfiltered", "1d_supertrend")
              for horizon in HORIZON_MULTIPLES
              for target_r in TARGET_R_MULTIPLES}
    signal_counts = {rule: 0 for rule in RULES}
    data_hash = hashlib.sha256()
    skipped_event_windows = {}
    unused_settlements = set(settlements)
    missing_symbols = []
    eligible_anchor_bars = {tf: 0 for tf in TFS}
    consensus_opportunities = {}
    macro_aligned_opportunities = {}
    start = time.monotonic()

    for symbol in symbols:
        raw = pd.read_sql_query(
            "SELECT open_ms AS t_open_ms,open AS o,high AS h,low AS l,close AS c,"
            "volume AS v,quote_volume AS quote_v,trade_count AS trades "
            "FROM candles WHERE symbol=? ORDER BY open_ms", con, params=(symbol,))
        if raw.empty:
            missing_symbols.append(symbol)
            continue
        raw = raw.drop_duplicates("t_open_ms", keep=False).reset_index(drop=True)
        traded_indices = np.flatnonzero(raw.trades.to_numpy(np.int64) > 0)
        if not len(traded_indices):
            missing_symbols.append(symbol)
            continue
        raw = raw.iloc[int(traded_indices[0]):].reset_index(drop=True)
        settlement_ms = settlements.get(symbol)
        unused_settlements.discard(symbol)
        if settlement_ms is not None:
            raw = raw[raw.t_open_ms < settlement_ms].reset_index(drop=True)
        elif len(raw) and int(raw.trades.iloc[-1]) <= 0:
            raise ValueError(f"terminal zero-trade tail needs an official settlement cutoff: {symbol}")
        if raw.empty:
            continue
        raw_times = raw.t_open_ms.to_numpy(np.int64)
        raw_open = raw.o.to_numpy(float)
        raw_high, raw_low = raw.h.to_numpy(float), raw.l.to_numpy(float)
        raw_trades = raw.trades.to_numpy(np.int64)
        data_hash.update(symbol.encode())
        data_hash.update(str(settlement_ms or "").encode())
        data_hash.update(pd.util.hash_pandas_object(raw, index=False).values.tobytes())
        macro_frame = resample_daily_frame(raw)
        macro_atr = atr(macro_frame.h, macro_frame.l, macro_frame.c, 14)
        macro_dirs = supertrend_direction(macro_frame.h, macro_frame.l,
                                          macro_frame.c, macro_atr)
        for tf in TFS:
            minutes = TIMEFRAME_MINUTES[tf]
            frame = raw.copy() if minutes == 1 else resample_frame(raw, tf)
            frame.attrs["tf_minutes"] = minutes
            if len(frame) < 160:
                continue
            eligible_anchor_bars[tf] += len(frame) - 1
            aligned_macro = latest_closed_directions(
                macro_frame.t_open_ms.to_numpy(np.int64), macro_dirs,
                86_400_000, frame.t_open_ms.to_numpy(np.int64),
                minutes * 60_000)
            h, l, c, v = (frame[k].to_numpy(float) for k in ("h", "l", "c", "v"))
            prepared = {"atr": atr(h, l, c, 14), "rsi": rsi(c, 14),
                        "vwap": vwap(h, l, c, v, frame.t_open_ms),
                        "patterns": candle_patterns(frame.o, frame.h, frame.l, frame.c)}
            signals = {}
            for rule in RULES:
                by_index = {}
                for sig in generate_signals(frame, rule, prepared):
                    by_index.setdefault(sig.index, []).append((sig.side, sig.stop))
                signals[rule] = {}
                for index, votes in by_index.items():
                    directions = {side for side, _ in votes}
                    if len(directions) == 1:
                        signals[rule][index] = (votes[0][0], float(np.median([x[1] for x in votes])))
                signal_counts[rule] += len(signals[rule])
            for subset in subsets:
                last_entry = {(regime, horizon): -1
                              for regime in ("unfiltered", "1d_supertrend")
                              for horizon in HORIZON_MULTIPLES}
                for i in range(len(frame) - 1):
                    combined = combine_at_bar(signals, subset, i)
                    if combined is None:
                        continue
                    side, stop = combined
                    count_key = (subset, tf)
                    consensus_opportunities[count_key] = consensus_opportunities.get(count_key, 0) + 1
                    expected_dir = 1 if side == "long" else -1
                    macro_aligned = int(aligned_macro[i]) == expected_dir
                    if macro_aligned:
                        macro_aligned_opportunities[count_key] = (
                            macro_aligned_opportunities.get(count_key, 0) + 1)
                    for regime in ("unfiltered", "1d_supertrend"):
                        if regime == "1d_supertrend":
                            if not macro_aligned:
                                continue
                        for horizon in HORIZON_MULTIPLES:
                            if i < last_entry[(regime, horizon)]:
                                continue
                            rejection = epoch_window_rejection(frame, raw, i, horizon,
                                                               settlement_ms)
                            if rejection:
                                key = f"{regime}:{horizon}:{rejection}"
                                skipped_event_windows[key] = skipped_event_windows.get(key, 0) + 1
                                continue
                            target_trades = evaluate_event_grid(
                                frame, raw_times, raw_open, raw_high, raw_low, raw_trades,
                                i, side, stop, horizon, TARGET_R_MULTIPLES)
                            if target_trades is None:
                                continue
                            last_entry[(regime, horizon)] = i + horizon
                            for target_r, trade in target_trades.items():
                                add_to_accumulator(
                                    groups[(subset, tf, regime, horizon, target_r)],
                                    trade, symbol)
            print(f"processed symbol={symbol} tf={tf} bars={len(frame)} elapsed={time.monotonic()-start:.1f}s", flush=True)
    con.close()
    if missing_symbols:
        raise ValueError(f"frozen universe symbols missing/without trades: {missing_symbols}")

    rows = []
    for (subset, tf, regime, horizon, target_r), accumulator in groups.items():
        n_events = accumulator["n"]
        available_bars = eligible_anchor_bars[tf]
        row = {"subset": list(subset), "k": len(subset), "timeframe": tf,
                     "regime_filter": regime, "horizon_bars": horizon,
                     "horizon_minutes": horizon * TIMEFRAME_MINUTES[tf],
                     "target_r": target_r,
                     "eligible_anchor_bars": available_bars,
                     "consensus_signal_opportunities": consensus_opportunities.get((subset, tf), 0),
                     "macro_aligned_signal_opportunities": macro_aligned_opportunities.get((subset, tf), 0),
                     "entry_coverage_pct": 100 * n_events / available_bars if available_bars else None,
                     **summarize_accumulator(accumulator)}
        denom = (consensus_opportunities.get((subset, tf), 0) if regime == "unfiltered"
                 else macro_aligned_opportunities.get((subset, tf), 0))
        row["nonoverlap_event_rate_pct"] = 100 * n_events / denom if denom else None
        rows.append(row)
    expected_cells = (len(subsets) * len(TFS) * 2 * len(HORIZON_MULTIPLES)
                      * len(TARGET_R_MULTIPLES))
    result_keys = {(tuple(row["subset"]), row["timeframe"], row["regime_filter"],
                    row["horizon_bars"], row["target_r"]) for row in rows}
    if len(rows) != expected_cells or len(result_keys) != expected_cells:
        raise ValueError(f"incomplete or duplicate target matrix: {len(result_keys)}/{expected_cells}")

    anchor_signatures = {}
    for row in rows:
        anchor_key = (tuple(row["subset"]), row["timeframe"],
                      row["regime_filter"], row["horizon_bars"])
        signature = (row["n"], row["deadline_direction_accuracy"],
                     row["deadline_direction_wilson95_pct"])
        if anchor_key in anchor_signatures and anchor_signatures[anchor_key] != signature:
            raise ValueError(f"target variants do not share event anchors: {anchor_key}")
        anchor_signatures[anchor_key] = signature
    # Keep the preregistered matrix in deterministic configuration order.
    # Sorting by observed performance or printing a "best" cell would turn
    # this exploratory grid into an implicit post-hoc selection step.
    output = {"status": "EXPLORATORY_DEVELOPMENT_ONLY",
              "data_path": str(db_path), "data_sha256": data_hash.hexdigest(),
              "symbols": symbols, "timeframes": list(TFS), "rules": list(RULES),
              "horizon_multiples": list(HORIZON_MULTIPLES),
              "target_r_multiples": list(TARGET_R_MULTIPLES),
              "subsets_enumerated": len(subsets), "result_cells": len(rows),
              "subset_sizes": {str(k): sum(len(x) == k for x in subsets)
                               for k in range(1, len(RULES)+1)},
              "combination": "strict majority of all rules in subset at the same closed bar; ties/abstentions are flat",
              "stop": "median structural stop among agreeing votes",
              "entry": "next timeframe open",
              "target": "grid of fixed target distances in R; target barriers evaluated in one minute-path scan",
              "max_hold_bars": list(HORIZON_MULTIPLES),
              "same_minute_barrier_tie": "stop first",
              "fee_per_side": FEE_PER_SIDE,
              "regimes": {"unfiltered": "all valid events", "1d_supertrend": "require latest fully closed UTC daily SuperTrend(14, 3x ATR) direction to align with long/short; 0/unknown direction abstains"},
              "symbols_json": str(Path(args.symbols_json).resolve()) if args.symbols_json else None,
              "settlements_json": str(Path(args.settlements_json).resolve()) if args.settlements_json else None,
              "settlements_used": {symbol: value for symbol, value in settlements.items()
                                   if symbol not in unused_settlements},
              "unused_settlements": sorted(unused_settlements),
              "skipped_event_windows": skipped_event_windows,
              "execution_validity": "fresh traded signal close and entry open; complete contiguous 10- or 20-bar forecast and 1m path; barrier touches only on traded 1m rows; no new entry in final 30 minutes before official futures settlement; skip events whose full horizon crosses settlement or data gaps; stop-first ties; stop-market gaps fill at observed open",
              "signal_counts_by_rule": signal_counts,
              "elapsed_seconds": time.monotonic() - start, "results": rows}
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"output": args.output, "subsets": len(subsets),
                      "cells": len(rows), "elapsed_seconds": output["elapsed_seconds"]},
                     allow_nan=False))


if __name__ == "__main__":
    main()
