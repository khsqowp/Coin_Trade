#!/usr/bin/env python3
"""Exploratory BTC-relative 1m mean-reversion probe; read-only candle DB."""
import argparse
import csv
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

DB = Path(__file__).resolve().parents[2] / "chart_predictor/data/vision_dev.sqlite"
CUTOFF_MS = int(pd.Timestamp("2026-10-09T00:00:00Z").timestamp() * 1000)
SYMBOLS = ("BNBUSDT", "DOGEUSDT", "ETHUSDT")
HORIZONS = (10, 20)
COSTS = (0.001, 0.003)
BOOTSTRAPS = 1000


def make_signals(frame):
    """Use only completed 1m bars; emit symmetric BTC-relative z-score extremes."""
    times = frame.open_ms.to_numpy(np.int64)
    close = frame.c.to_numpy(float)
    high, low = frame.h.to_numpy(float), frame.l.to_numpy(float)
    alt_ret = np.r_[np.nan, np.diff(np.log(close))]
    btc_ret = np.r_[np.nan, np.diff(np.log(frame.btc_c.to_numpy(float)))]
    relative_20 = pd.Series(alt_ret - btc_ret).rolling(20, min_periods=20).sum()
    past = relative_20.shift(1).rolling(240, min_periods=240)
    mean = past.mean().to_numpy()
    std = past.std(ddof=0).to_numpy()
    z = (relative_20.to_numpy() - mean) / std
    previous_close = np.r_[np.nan, close[:-1]]
    tr = np.maximum(high - low, np.maximum(abs(high - previous_close), abs(low - previous_close)))
    atr20 = pd.Series(tr).rolling(20, min_periods=20).mean().to_numpy()
    adjacent = np.r_[False, np.diff(times) == 60_000]
    continuous = pd.Series(adjacent.astype(np.int8)).rolling(260, min_periods=260).sum().eq(260).to_numpy()
    events = [(i, 1 if z[i] <= -2 else -1) for i in range(260, len(frame) - 21)
              if continuous[i] and np.isfinite(z[i]) and np.isfinite(atr20[i]) and atr20[i] > 0
              and (z[i] <= -2 or z[i] >= 2)]
    return events, atr20, z


def barrier(side, entry, risk, start, horizon, frame):
    """Return first barrier outcome and gross return; stop wins same-candle ties."""
    stop = entry - side * risk
    target = entry + side * 3 * risk
    exit_price = float(frame.c.iloc[start + horizon - 1])
    target_first = False
    for j in range(start, start + horizon):
        o, h, l = (float(frame[k].iloc[j]) for k in ("o", "h", "l"))
        stop_hit = l <= stop if side > 0 else h >= stop
        target_hit = h >= target if side > 0 else l <= target
        if stop_hit or target_hit:
            if stop_hit:
                exit_price = min(o, stop) if side > 0 else max(o, stop)
            else:
                exit_price, target_first = target, True
            break
    return float(target_first), side * (exit_price / entry - 1)


def block_interval(values, days, seed):
    """Moving 7-calendar-day block bootstrap; events retain within-day clustering."""
    if not len(values):
        return (float("nan"), float("nan"))
    unique = np.asarray(sorted(set(days)), dtype=np.int64)
    span = int(unique[-1] - unique[0] + 1)
    blocks = np.zeros(span)
    counts = np.zeros(span)
    for day in unique:
        ix = np.asarray(days) == day
        offset = int(day - unique[0])
        blocks[offset] = np.sum(values[ix])
        counts[offset] = np.sum(ix)
    p_sum = np.r_[0.0, np.cumsum(blocks)]
    p_count = np.r_[0.0, np.cumsum(counts)]
    block_days = min(7, span)
    block_count = int(np.ceil(span / block_days))
    rng = np.random.default_rng(seed)
    samples = np.empty(BOOTSTRAPS)
    for b in range(BOOTSTRAPS):
        starts = rng.integers(0, span - block_days + 1, block_count)
        ends = starts + block_days
        total = (p_sum[ends] - p_sum[starts]).sum()
        n = (p_count[ends] - p_count[starts]).sum()
        samples[b] = total / n if n else np.nan
    return tuple(map(float, np.nanquantile(samples, [0.025, 0.975])))


def evaluate(frame, symbol):
    events, atr20, _ = make_signals(frame)
    rows = []
    for horizon in HORIZONS:
        actual, reverse, last_exit = [], [], -1
        for i, side in events:
            entry_i = i + 1
            if entry_i <= last_exit or entry_i + horizon > len(frame):
                continue
            entry = float(frame.o.iloc[entry_i])
            risk = float(atr20[i])
            if entry <= 0 or risk <= 0 or not np.isfinite(risk):
                continue
            a = barrier(side, entry, risk, entry_i, horizon, frame)
            r = barrier(-side, entry, risk, entry_i, horizon, frame)
            day = int(frame.open_ms.iloc[i]) // 86_400_000
            actual.append((a[0], a[1] - COSTS[0], a[1] - COSTS[1], day))
            reverse.append((r[0], r[1] - COSTS[0], r[1] - COSTS[1], day))
            last_exit = entry_i + horizon - 1
        if not actual:
            continue
        a, r = np.asarray(actual), np.asarray(reverse)
        days = a[:, 3].astype(np.int64)
        rows.append({
            "strategy": "btc_relative_20m_z240_2sigma_atr20_3R",
            "symbol": symbol, "signal_timeframe_min": 1, "horizon_min": horizon,
            "n": len(a), "coverage_per_bar": len(a) / len(frame),
            "target_first": float(a[:, 0].mean()),
            "target_first_7d_block95": block_interval(a[:, 0], days, 8000 + horizon),
            "mean_net_base_pct": float(a[:, 1].mean() * 100),
            "mean_base_7d_block95_pct": tuple(x * 100 for x in block_interval(a[:, 1], days, 8010 + horizon)),
            "mean_net_stress_pct": float(a[:, 2].mean() * 100),
            "mean_stress_7d_block95_pct": tuple(x * 100 for x in block_interval(a[:, 2], days, 8020 + horizon)),
            "reverse_target_first": float(r[:, 0].mean()),
            "reverse_mean_net_base_pct": float(r[:, 1].mean() * 100),
            "reverse_mean_net_stress_pct": float(r[:, 2].mean() * 100),
            "first_signal_day_utc": pd.to_datetime(frame.open_ms.iloc[events[0][0]], unit="ms", utc=True).date().isoformat(),
            "last_signal_day_utc": pd.to_datetime(frame.open_ms.iloc[events[-1][0]], unit="ms", utc=True).date().isoformat(),
            "cost_base_round_trip_pct": COSTS[0] * 100,
            "cost_stress_round_trip_pct": COSTS[1] * 100,
            "block_days": min(7, int(days.max() - days.min() + 1)),
        })
    return rows


def load_pair(db, symbol):
    query = ("SELECT a.open_ms,a.open AS o,a.high AS h,a.low AS l,a.close AS c,b.close AS btc_c "
             "FROM candles a JOIN candles b ON a.open_ms=b.open_ms "
             "WHERE a.symbol=? AND b.symbol='BTCUSDT' AND a.open_ms<? ORDER BY a.open_ms")
    frame = pd.read_sql_query(query, db, params=(symbol, CUTOFF_MS))
    return frame[frame.open_ms + 60_000 <= CUTOFF_MS].reset_index(drop=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv-out", type=Path, required=True)
    args = parser.parse_args()
    db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    rows = []
    for symbol in SYMBOLS:
        frame = load_pair(db, symbol)
        rows.extend(evaluate(frame, symbol))
        print(f"completed {symbol}: aligned_minutes={len(frame)}", flush=True)
    db.close()
    args.csv_out.parent.mkdir(parents=True, exist_ok=True)
    with args.csv_out.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"cells={len(rows)} n_ge_200={sum(int(r['n']) >= 200 for r in rows)}")
    for row in rows:
        print(row)


if __name__ == "__main__":
    main()
