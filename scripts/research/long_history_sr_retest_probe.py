#!/usr/bin/env python3
"""Fixed support/resistance breakout-retest probe; read-only candle input."""
import argparse
import csv
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

DB = Path(__file__).resolve().parents[2] / "chart_predictor/data/vision_dev.sqlite"
CUTOFF_MS = int(pd.Timestamp("2026-10-09T00:00:00Z").timestamp() * 1000)
SYMBOLS = ("BNBUSDT", "BTCUSDT", "DOGEUSDT", "ETHUSDT")
TIMEFRAMES = (1, 3, 5, 10, 15, 30, 60, 120, 240, 360, 720, 1440)
HORIZONS = (10, 20)
COSTS = (0.001, 0.003)


def aggregate(raw, tf):
    if tf == 1:
        return raw[raw.open_ms.mod(60_000) == 0].copy().reset_index(drop=True)
    width = tf * 60_000
    x = raw.copy()
    x["bucket"] = (x.open_ms // width) * width
    frame = x.groupby("bucket", sort=True).agg(
        o=("o", "first"), h=("h", "max"), l=("l", "min"), c=("c", "last"),
        n=("open_ms", "nunique"), first=("open_ms", "min"), last=("open_ms", "max"),
    ).reset_index()
    complete = ((frame.n == tf) & (frame["first"] == frame.bucket)
                & (frame["last"] == frame.bucket + (tf - 1) * 60_000))
    return frame[complete].rename(columns={"bucket": "open_ms"}).reset_index(drop=True)


def make_signals(frame, width):
    """Return (bar index, side, stop price) after causal 20-bar breakout/retest."""
    times = frame.open_ms.to_numpy(np.int64)
    high, low, close, opens = (frame[k].to_numpy(float) for k in ("h", "l", "c", "o"))
    prior_resistance = pd.Series(high).shift(1).rolling(20, min_periods=20).max().to_numpy()
    prior_support = pd.Series(low).shift(1).rolling(20, min_periods=20).min().to_numpy()
    previous_close = np.r_[np.nan, close[:-1]]
    tr = np.maximum(high - low, np.maximum(abs(high - previous_close), abs(low - previous_close)))
    atr = pd.Series(tr).rolling(14, min_periods=14).mean().to_numpy()
    adjacent = np.r_[False, np.diff(times) == width]
    signals, pending = [], None
    for i in range(20, len(frame)):
        if not adjacent[i]:
            pending = None
            continue
        if not np.all(adjacent[i - 19:i + 1]):
            pending = None
            continue
        if not np.isfinite(atr[i]) or atr[i] <= 0:
            pending = None
            continue
        emitted = False
        if pending is not None:
            side, level, breakout_i = pending
            age = i - breakout_i
            if age > 10:
                pending = None
            elif side > 0:
                if close[i] <= level or low[i] < level - 0.5 * atr[i]:
                    pending = None
                elif low[i] <= level + 0.25 * atr[i] and close[i] > level and close[i] > opens[i]:
                    signals.append((i, 1, float(low[i])))
                    pending, emitted = None, True
            else:
                if close[i] >= level or high[i] > level + 0.5 * atr[i]:
                    pending = None
                elif high[i] >= level - 0.25 * atr[i] and close[i] < level and close[i] < opens[i]:
                    signals.append((i, -1, float(high[i])))
                    pending, emitted = None, True
        if emitted or pending is not None:
            continue
        resistance, support = prior_resistance[i], prior_support[i]
        if not np.isfinite(resistance) or not np.isfinite(support):
            continue
        if close[i] > resistance and previous_close[i] <= resistance:
            pending = (1, float(resistance), i)
        elif close[i] < support and previous_close[i] >= support:
            pending = (-1, float(support), i)
    return signals, atr


def score_path(side, entry, risk, lo_ix, hi_ix, raw_arrays, fallback):
    ro, rh, rl = raw_arrays
    stop, target = entry - side * risk, entry + side * 2 * risk
    exit_price, target_first = fallback, False
    for j in range(lo_ix, hi_ix):
        stop_hit = rl[j] <= stop if side > 0 else rh[j] >= stop
        target_hit = rh[j] >= target if side > 0 else rl[j] <= target
        if stop_hit or target_hit:
            if stop_hit:
                exit_price = min(ro[j], stop) if side > 0 else max(ro[j], stop)
            else:
                exit_price, target_first = target, True
            break
    gross = side * (exit_price / entry - 1)
    return (float(target_first), float(gross - COSTS[0] > 0),
            float(gross - COSTS[1] > 0), gross - COSTS[0], gross - COSTS[1])


def evaluate(raw, symbol):
    raw_times = raw.open_ms.to_numpy(np.int64)
    raw_arrays = tuple(raw[k].to_numpy(float) for k in ("o", "h", "l"))
    rows = []
    for tf in TIMEFRAMES:
        width = tf * 60_000
        frame = aggregate(raw, tf)
        frame = frame[frame.open_ms + width <= CUTOFF_MS].reset_index(drop=True)
        if len(frame) < 100:
            continue
        times = frame.open_ms.to_numpy(np.int64)
        close, opens = frame.c.to_numpy(float), frame.o.to_numpy(float)
        signals, atr = make_signals(frame, width)
        for horizon in HORIZONS:
            trades, last_exit = [], -1
            for i, side, signal_stop in signals:
                entry_i = i + 1
                if entry_i <= last_exit or entry_i + horizon > len(frame):
                    continue
                entry = opens[entry_i]
                risk = side * (entry - signal_stop)
                if not np.isfinite(risk) or risk <= 0:
                    continue
                start_ms, end_ms = int(times[entry_i]), int(times[entry_i + horizon - 1]) + width
                lo_ix, hi_ix = np.searchsorted(raw_times, start_ms), np.searchsorted(raw_times, end_ms)
                if hi_ix - lo_ix != (end_ms - start_ms) // 60_000:
                    continue
                fallback = close[entry_i + horizon - 1]
                actual = score_path(side, entry, risk, lo_ix, hi_ix, raw_arrays, fallback)
                reverse = score_path(-side, entry, risk, lo_ix, hi_ix, raw_arrays, fallback)
                trades.append((*actual, *reverse, int(times[i]) // 86_400_000))
                last_exit = entry_i + horizon - 1
            if not trades:
                continue
            values = np.asarray(trades, dtype=float)
            days, inverse = np.unique(values[:, 10].astype(np.int64), return_inverse=True)
            daily_n = np.bincount(inverse)
            daily_sums = np.column_stack([np.bincount(inverse, weights=values[:, j]) for j in range(10)])
            rng = np.random.default_rng(842 + tf + horizon)
            boot = np.empty((1000, 10))
            block_days = max(1, int(np.ceil(horizon * tf / 1440)))
            block_days = min(block_days, int(days[-1] - days[0] + 1))
            span_days = int(days[-1] - days[0] + 1)
            block_count = int(np.ceil(span_days / block_days))
            calendar_sums = np.zeros((span_days, 10))
            calendar_n = np.zeros(span_days)
            day_offsets = days - days[0]
            calendar_sums[day_offsets] = daily_sums
            calendar_n[day_offsets] = daily_n
            prefix_sums = np.vstack((np.zeros(10), np.cumsum(calendar_sums, axis=0)))
            prefix_n = np.r_[0.0, np.cumsum(calendar_n)]
            start_count = span_days - block_days + 1
            for chunk_start in range(0, 1000, 100):
                chunk_end = min(chunk_start + 100, 1000)
                starts = rng.integers(0, start_count, (chunk_end - chunk_start, block_count))
                ends = starts + block_days
                sample_sums = (prefix_sums[ends] - prefix_sums[starts]).sum(axis=1)
                sample_n = (prefix_n[ends] - prefix_n[starts]).sum(axis=1)
                boot[chunk_start:chunk_end] = np.divide(
                    sample_sums, sample_n[:, None],
                    out=np.full_like(sample_sums, np.nan), where=sample_n[:, None] > 0,
                )
            rows.append({
                "signal_family": "sr_20bar_breakout_retest", "symbol": symbol,
                "timeframe_min": tf, "horizon_bars": horizon, "n": len(values),
                "coverage": len(values) / len(frame), "target_first": values[:, 0].mean(),
                "time_block_days": block_days,
                "net_positive_base": values[:, 1].mean(), "net_positive_stress": values[:, 2].mean(),
                "mean_net_base_pct": values[:, 3].mean() * 100,
                "mean_net_stress_pct": values[:, 4].mean() * 100,
                "reverse_target_first": values[:, 7].mean(),
                "reverse_net_positive_base": values[:, 6].mean(),
                "reverse_mean_net_base_pct": values[:, 8].mean() * 100,
                "target_first_time_block95": tuple(np.nanquantile(boot[:, 0], [0.025, 0.975])),
                "mean_base_time_block95_pct": tuple(np.nanquantile(boot[:, 3], [0.025, 0.975]) * 100),
                "mean_stress_time_block95_pct": tuple(np.nanquantile(boot[:, 4], [0.025, 0.975]) * 100),
                "reverse_target_time_block95": tuple(np.nanquantile(boot[:, 7], [0.025, 0.975])),
                "reverse_mean_time_block95_pct": tuple(np.nanquantile(boot[:, 8], [0.025, 0.975]) * 100),
            })
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv-out", type=Path, required=True)
    args = parser.parse_args()
    db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    rows = []
    for symbol in SYMBOLS:
        raw = pd.read_sql_query(
            "SELECT open_ms,open AS o,high AS h,low AS l,close AS c FROM candles "
            "WHERE symbol=? AND open_ms<? ORDER BY open_ms", db, params=(symbol, CUTOFF_MS))
        raw = raw[raw.open_ms + 60_000 <= CUTOFF_MS].reset_index(drop=True)
        rows.extend(evaluate(raw, symbol))
        print(f"completed {symbol}: minute_rows={len(raw)} cells={len(rows)}", flush=True)
    db.close()
    args.csv_out.parent.mkdir(parents=True, exist_ok=True)
    with args.csv_out.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    eligible = [row for row in rows if row["n"] >= 200]
    print(f"cells={len(rows)} eligible_n_ge_200={len(eligible)}")
    for field in ("target_first", "net_positive_base", "mean_net_base_pct"):
        print("best", field, max(eligible, key=lambda row: row[field]) if eligible else "none")


if __name__ == "__main__":
    main()
