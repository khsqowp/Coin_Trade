#!/usr/bin/env python3
"""Fixed SuperTrend reversal probe on the read-only long-history candle cache."""
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


def supertrend(frame, width):
    high, low, close = (frame[k].to_numpy(float) for k in ("h", "l", "c"))
    times = frame.open_ms.to_numpy(np.int64)
    previous = np.r_[np.nan, close[:-1]]
    tr = np.maximum(high - low, np.maximum(abs(high - previous), abs(low - previous)))
    atr = pd.Series(tr).ewm(alpha=1 / 14, adjust=False, min_periods=14).mean().to_numpy()
    direction = np.zeros(len(frame), dtype=np.int8)
    adjacent = np.r_[False, np.diff(times) == width]
    starts = np.flatnonzero(~adjacent)
    for start, end in zip(starts, np.r_[starts[1:], len(frame)]):
        upper = np.full(end - start, np.nan)
        lower = np.full(end - start, np.nan)
        for j, i in enumerate(range(start, end)):
            if not np.isfinite(atr[i]):
                continue
            mid = (high[i] + low[i]) / 2
            basic_u, basic_l = mid + 3 * atr[i], mid - 3 * atr[i]
            if j == 0 or not np.isfinite(upper[j - 1]):
                upper[j], lower[j] = basic_u, basic_l
                direction[i] = -1
                continue
            prev_u, prev_l = upper[j - 1], lower[j - 1]
            upper[j] = basic_u if basic_u < prev_u or close[i - 1] > prev_u else prev_u
            lower[j] = basic_l if basic_l > prev_l or close[i - 1] < prev_l else prev_l
            prior_dir = direction[i - 1]
            direction[i] = 1 if close[i] > prev_u else (-1 if close[i] < prev_l else prior_dir)
    return atr, direction


def evaluate(raw, symbol):
    rt = raw.open_ms.to_numpy(np.int64)
    ro, rh, rl = (raw[k].to_numpy(float) for k in ("o", "h", "l"))
    rows = []
    for tf in TIMEFRAMES:
        width = tf * 60_000
        frame = aggregate(raw, tf)
        frame = frame[frame.open_ms + width <= CUTOFF_MS].reset_index(drop=True)
        if len(frame) < 100:
            continue
        times = frame.open_ms.to_numpy(np.int64)
        close, opens, high, low = (frame[k].to_numpy(float) for k in ("c", "o", "h", "l"))
        atr, direction = supertrend(frame, width)
        adjacent = np.r_[False, np.diff(times) == width]
        signals = [i for i in range(15, len(frame) - 21)
                   if adjacent[i] and np.all(adjacent[i - 13:i + 1])
                   and direction[i] != 0 and direction[i - 1] != 0
                   and direction[i] != direction[i - 1] and np.isfinite(atr[i]) and atr[i] > 0]
        for horizon in HORIZONS:
            trades, last_exit = [], -1
            for i in signals:
                side = int(direction[i])
                entry_i = i + 1
                if entry_i <= last_exit or entry_i + horizon > len(frame):
                    continue
                entry, risk = opens[entry_i], 1.5 * atr[i]
                start_ms = int(times[entry_i])
                end_ms = int(times[entry_i + horizon - 1]) + width
                lo_ix, hi_ix = np.searchsorted(rt, start_ms), np.searchsorted(rt, end_ms)
                if hi_ix - lo_ix != (end_ms - start_ms) // 60_000:
                    continue
                def outcome(trade_side):
                    trade_stop = entry - trade_side * risk
                    trade_target = entry + trade_side * 2 * risk
                    exit_price = close[entry_i + horizon - 1]
                    target_first = False
                    for j in range(lo_ix, hi_ix):
                        stop_hit = rl[j] <= trade_stop if trade_side > 0 else rh[j] >= trade_stop
                        target_hit = rh[j] >= trade_target if trade_side > 0 else rl[j] <= trade_target
                        if stop_hit or target_hit:
                            if stop_hit:
                                exit_price = min(ro[j], trade_stop) if trade_side > 0 else max(ro[j], trade_stop)
                            else:
                                exit_price, target_first = trade_target, True
                            break
                    gross = trade_side * (exit_price / entry - 1)
                    return (float(gross - COSTS[0] > 0), float(gross - COSTS[1] > 0),
                            float(target_first), gross - COSTS[0], gross - COSTS[1])
                actual = outcome(side)
                reverse = outcome(-side)
                trades.append((*actual, *reverse, int(times[i]) // 86_400_000))
                last_exit = entry_i + horizon - 1
            if not trades:
                continue
            v = np.asarray(trades)
            day_ids, inverse = np.unique(v[:, 10], return_inverse=True)
            counts = np.bincount(inverse)
            sums = np.column_stack([np.bincount(inverse, weights=v[:, j]) for j in range(10)])
            rng = np.random.default_rng(774 + tf + horizon)
            boot = np.empty((1000, 10))
            for b in range(1000):
                draw = rng.integers(0, len(day_ids), len(day_ids))
                boot[b] = sums[draw].sum(axis=0) / counts[draw].sum()
            rows.append({
                "signal_family": "supertrend_flip_atr14_x3", "symbol": symbol,
                "timeframe_min": tf, "horizon_bars": horizon, "n": len(v),
                "coverage": len(v) / len(frame), "target_first": v[:, 2].mean(),
                "net_positive_base": v[:, 0].mean(), "net_positive_stress": v[:, 1].mean(),
                "mean_net_base_pct": v[:, 3].mean() * 100,
                "mean_net_stress_pct": v[:, 4].mean() * 100,
                "reverse_baseline_target_first": v[:, 7].mean(),
                "reverse_baseline_net_positive_base": v[:, 5].mean(),
                "reverse_baseline_mean_net_base_pct": v[:, 8].mean() * 100,
                "target_first_cluster95": tuple(np.quantile(boot[:, 2], [0.025, 0.975])),
                "mean_base_cluster95_pct": tuple(np.quantile(boot[:, 3], [0.025, 0.975]) * 100),
                "mean_stress_cluster95_pct": tuple(np.quantile(boot[:, 4], [0.025, 0.975]) * 100),
                "reverse_baseline_target_cluster95": tuple(np.quantile(boot[:, 7], [0.025, 0.975])),
                "reverse_baseline_mean_cluster95_pct": tuple(np.quantile(boot[:, 8], [0.025, 0.975]) * 100),
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
        print(f"completed {symbol}: bars={len(raw)} rows={len(rows)}", flush=True)
    db.close()
    args.csv_out.parent.mkdir(parents=True, exist_ok=True)
    with args.csv_out.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    eligible = [r for r in rows if r["n"] >= 200]
    print(f"rows={len(rows)} eligible_n_ge_200={len(eligible)}")
    for key in ("target_first", "net_positive_base", "mean_net_base_pct"):
        print("best", key, max(eligible, key=lambda r: r[key]) if eligible else "none")


if __name__ == "__main__":
    main()
