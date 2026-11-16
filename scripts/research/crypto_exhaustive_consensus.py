#!/usr/bin/env python3
"""Development-only exhaustive subset consensus replay for four frozen P8 rules.

Reads a Binance Vision-derived SQLite candle DB read-only. It deliberately uses
the complete historical development archive and makes no validation claim.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import sqlite3
import time
from pathlib import Path

import numpy as np
import pandas as pd

from chart_predictor.indicators import atr, rsi, vwap
from chart_predictor.indicators import candle_patterns
from chart_predictor.resample import resample_frame, TIMEFRAME_MINUTES
from chart_predictor.setups import generate_signals

RULES = ("bb_squeeze_breakout", "orb_funding_session", "vwap_band_fade",
         "volume_climax_exhaustion")
TFS = tuple(TIMEFRAME_MINUTES)
FEE_PER_SIDE = 0.0005
TARGET_R = 2.0
MAX_HOLD_BARS = 12


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


def evaluate_event(frame, raw_times, raw_high, raw_low, signal_i, side, stop):
    entry_i = signal_i + 1
    if entry_i >= len(frame):
        return None
    entry = float(frame.o.iloc[entry_i])
    sign = 1 if side == "long" else -1
    risk = sign * (entry - stop)
    if not math.isfinite(risk) or risk <= 0:
        return None
    target = entry + sign * TARGET_R * risk
    last_i = min(len(frame) - 1, entry_i + MAX_HOLD_BARS - 1)
    begin_ms = int(frame.t_open_ms.iloc[entry_i])
    end_ms = int(frame.t_open_ms.iloc[last_i]) + 60_000 * int(frame.attrs["tf_minutes"])
    lo = int(np.searchsorted(raw_times, begin_ms, side="left"))
    hi = int(np.searchsorted(raw_times, end_ms, side="left"))
    if hi <= lo:
        return None
    reason, exit_price, exit_ms = "timeout", float(frame.c.iloc[last_i]), int(raw_times[hi - 1])
    for j in range(lo, hi):
        hit_stop = raw_low[j] <= stop if side == "long" else raw_high[j] >= stop
        hit_target = raw_high[j] >= target if side == "long" else raw_low[j] <= target
        if hit_stop or hit_target:
            reason = "stop" if hit_stop else "target"
            exit_price = stop if hit_stop else target
            exit_ms = int(raw_times[j])
            break
    gross = sign * (exit_price / entry - 1.0)
    net = gross - 2 * FEE_PER_SIDE
    return {"reason": reason, "net_pct": 100 * net,
            "net_r": net / (risk / entry), "exit_ms": exit_ms}


def summarize(trades):
    n = len(trades)
    if not n:
        return {"n": 0, "target_first_pct": None, "mean_net_pct": None,
                "sum_trade_net_pct": 0.0, "profit_factor": None,
                "timeout_pct": None, "symbols": 0}
    returns = np.asarray([x["net_pct"] for x in trades], dtype=float)
    wins = sum(x["reason"] == "target" for x in trades)
    positive, negative = returns[returns > 0].sum(), -returns[returns < 0].sum()
    return {"n": n, "target_first_pct": 100 * wins / n,
            "mean_net_pct": float(returns.mean()),
            "sum_trade_net_pct": float(returns.sum()),
            "mean_net_r": float(np.mean([x["net_r"] for x in trades])),
            "profit_factor": float(positive / negative) if negative else None,
            "timeout_pct": 100 * sum(x["reason"] == "timeout" for x in trades) / n,
            "symbols": len({x["symbol"] for x in trades})}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    db_path = Path(args.db).resolve()
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    symbols = [r[0] for r in con.execute("SELECT DISTINCT symbol FROM candles ORDER BY symbol")]
    subsets = enumerate_subsets()
    groups = {(subset, tf): [] for subset in subsets for tf in TFS}
    signal_counts = {rule: 0 for rule in RULES}
    data_hash = hashlib.sha256()
    start = time.monotonic()

    for symbol in symbols:
        raw = pd.read_sql_query(
            "SELECT open_ms AS t_open_ms,open AS o,high AS h,low AS l,close AS c,"
            "volume AS v,quote_volume AS quote_v,trade_count AS trades "
            "FROM candles WHERE symbol=? ORDER BY open_ms", con, params=(symbol,))
        if raw.empty:
            continue
        raw = raw.drop_duplicates("t_open_ms", keep=False).reset_index(drop=True)
        raw_times = raw.t_open_ms.to_numpy(np.int64)
        raw_high, raw_low = raw.h.to_numpy(float), raw.l.to_numpy(float)
        data_hash.update(symbol.encode())
        data_hash.update(pd.util.hash_pandas_object(raw, index=False).values.tobytes())
        for tf in TFS:
            minutes = TIMEFRAME_MINUTES[tf]
            frame = raw.copy() if minutes == 1 else resample_frame(raw, tf)
            frame.attrs["tf_minutes"] = minutes
            if len(frame) < 160:
                continue
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
                subset_trades = []
                last_entry = -1
                for i in range(len(frame) - 1):
                    if i < last_entry:
                        continue
                    combined = combine_at_bar(signals, subset, i)
                    if combined is None:
                        continue
                    side, stop = combined
                    trade = evaluate_event(frame, raw_times, raw_high, raw_low, i, side, stop)
                    if trade is None:
                        continue
                    last_entry = i + MAX_HOLD_BARS
                    subset_trades.append({**trade, "symbol": symbol})
                groups[(subset, tf)].extend(subset_trades)
            print(f"processed symbol={symbol} tf={tf} bars={len(frame)} elapsed={time.monotonic()-start:.1f}s", flush=True)
    con.close()

    rows = []
    for (subset, tf), trades in groups.items():
        rows.append({"subset": list(subset), "k": len(subset), "timeframe": tf,
                     **summarize(trades)})
    rows.sort(key=lambda r: (r["mean_net_pct"] is not None,
                             r["mean_net_pct"] if r["mean_net_pct"] is not None else -1e99),
              reverse=True)
    output = {"status": "EXPLORATORY_DEVELOPMENT_ONLY",
              "data_path": str(db_path), "data_sha256": data_hash.hexdigest(),
              "symbols": symbols, "timeframes": list(TFS), "rules": list(RULES),
              "subsets_enumerated": len(subsets), "result_cells": len(rows),
              "subset_sizes": {str(k): sum(len(x) == k for x in subsets)
                               for k in range(1, len(RULES)+1)},
              "combination": "strict majority of all rules in subset at the same closed bar; ties/abstentions are flat",
              "stop": "median structural stop among agreeing votes",
              "entry": "next timeframe open", "target": f"{TARGET_R}R",
              "max_hold_bars": MAX_HOLD_BARS,
              "same_minute_barrier_tie": "stop first",
              "fee_per_side": FEE_PER_SIDE,
              "signal_counts_by_rule": signal_counts,
              "elapsed_seconds": time.monotonic() - start, "results": rows}
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"output": args.output, "subsets": len(subsets),
                      "cells": len(rows), "elapsed_seconds": output["elapsed_seconds"],
                      "best": rows[0] if rows else None}, allow_nan=False))


if __name__ == "__main__":
    main()
