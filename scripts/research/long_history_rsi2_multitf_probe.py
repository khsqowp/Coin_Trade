#!/usr/bin/env python3
"""Exploratory RSI(2) mean-reversion grid on the read-only long-history cache."""
import argparse
import csv
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

DB = Path(__file__).resolve().parents[2] / "chart_predictor/data/vision_dev.sqlite"
CUTOFF_MS = int(pd.Timestamp("2026-10-09T00:00:00Z").timestamp() * 1000)
SYMBOLS = ("BNBUSDT", "BTCUSDT", "DOGEUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT")
TIMEFRAMES = (1, 3, 5, 10, 15, 30, 60, 120, 240, 360, 720, 1440)
HORIZONS = (10, 20)
COSTS = (0.001, 0.003)
BOOTSTRAPS = 1000


def wilson(successes, n):
    if not n:
        return (float("nan"), float("nan"))
    z = 1.95996398454
    p = successes / n
    den = 1 + z * z / n
    mid = (p + z * z / (2 * n)) / den
    radius = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return float(mid - radius), float(mid + radius)


def aggregate(raw, tf):
    if tf == 1:
        return raw[raw.open_ms.mod(60_000) == 0].copy().reset_index(drop=True)
    width = tf * 60_000
    x = raw.copy()
    x["bucket"] = (x.open_ms // width) * width
    groups = x.groupby("bucket", sort=True)
    frame = groups.agg(
        o=("o", "first"), h=("h", "max"), l=("l", "min"), c=("c", "last"),
        n=("open_ms", "nunique"), first=("open_ms", "min"), last=("open_ms", "max"),
    ).reset_index()
    complete = ((frame.n == tf) & (frame["first"] == frame.bucket)
                & (frame["last"] == frame.bucket + (tf - 1) * 60_000))
    return (frame[complete].rename(columns={"bucket": "open_ms"})
            .reset_index(drop=True))


def evaluate_symbol(raw, symbol, signal_family):
    # The exclusive SQL cutoff ensures no later candle is returned by SQLite.
    rt = raw.open_ms.to_numpy(np.int64)
    ro = raw.o.to_numpy(float)
    rh = raw.h.to_numpy(float)
    rl = raw.l.to_numpy(float)
    results = []
    for tf in TIMEFRAMES:
        frame = aggregate(raw, tf)
        frame = frame[frame.open_ms + tf * 60_000 <= CUTOFF_MS].reset_index(drop=True)
        if len(frame) < 100:
            continue
        close = frame.c.to_numpy(float)
        opens = frame.o.to_numpy(float)
        high = frame.h.to_numpy(float)
        low = frame.l.to_numpy(float)
        if signal_family in ("rsi2", "rsi2_ema200_trend"):
            delta = np.diff(np.r_[np.nan, close])
            gain = pd.Series(np.maximum(delta, 0)).ewm(alpha=0.5, adjust=False).mean().to_numpy()
            loss = pd.Series(np.maximum(-delta, 0)).ewm(alpha=0.5, adjust=False).mean().to_numpy()
            rsi2 = np.full(len(frame), np.nan)
            has_loss = loss > 0
            rsi2[has_loss] = 100 - 100 / (1 + gain[has_loss] / loss[has_loss])
            rsi2[(loss == 0) & (gain > 0)] = 100.0
            rsi2[(loss == 0) & (gain == 0)] = 50.0
            if signal_family == "rsi2_ema200_trend":
                ema200 = pd.Series(close).ewm(span=200, adjust=False, min_periods=200).mean().to_numpy()
                long_mask = (rsi2 < 10) & (close > ema200)
                short_mask = (rsi2 > 90) & (close < ema200)
                event_mask = long_mask | short_mask
                side_for = lambda i: 1 if long_mask[i] else -1
            else:
                event_mask = (rsi2 < 10) | (rsi2 > 90)
                side_for = lambda i: 1 if rsi2[i] < 10 else -1
        else:
            mid = pd.Series(close).rolling(20, min_periods=20).mean().to_numpy()
            std = pd.Series(close).rolling(20, min_periods=20).std(ddof=0).to_numpy()
            lower, upper = mid - 2 * std, mid + 2 * std
            previous = np.r_[np.nan, close[:-1]]
            previous_mid = np.r_[np.nan, mid[:-1]]
            previous_std = np.r_[np.nan, std[:-1]]
            was_below = previous < (previous_mid - 2 * previous_std)
            was_above = previous > (previous_mid + 2 * previous_std)
            inside = (close >= lower) & (close <= upper)
            long_reentry = inside & was_below
            short_reentry = inside & was_above
            event_mask = long_reentry | short_reentry
            side_for = lambda i: 1 if long_reentry[i] else -1
        previous_close = np.r_[np.nan, close[:-1]]
        tr = np.maximum(high - low, np.maximum(abs(high - previous_close), abs(low - previous_close)))
        atr = pd.Series(tr).rolling(14, min_periods=14).mean().to_numpy()
        times = frame.open_ms.to_numpy(np.int64)
        adjacent = np.r_[False, np.diff(times) == tf * 60_000]
        contiguous_window = (pd.Series(adjacent.astype(np.int8))
                             .rolling(19, min_periods=19).sum().eq(19).to_numpy())
        events = [(i, side_for(i)) for i in range(19, len(frame) - 21)
                  if contiguous_window[i] and event_mask[i]]

        for horizon in HORIZONS:
            trades = []
            last_exit = -1
            for i, side in events:
                entry_i = i + 1
                if entry_i <= last_exit or entry_i + horizon > len(frame):
                    continue
                if not np.isfinite(atr[i]) or atr[i] <= 0:
                    continue
                entry = opens[entry_i]
                risk = atr[i]
                stop = entry - side * risk
                target = entry + side * risk
                start_ms = int(frame.open_ms.iloc[entry_i])
                end_ms = int(frame.open_ms.iloc[entry_i + horizon - 1]) + tf * 60_000
                lo_ix = np.searchsorted(rt, start_ms)
                hi_ix = np.searchsorted(rt, end_ms)
                if hi_ix - lo_ix != (end_ms - start_ms) // 60_000:
                    continue
                exit_price = close[entry_i + horizon - 1]
                target_first = False
                for j in range(lo_ix, hi_ix):
                    stop_hit = rl[j] <= stop if side > 0 else rh[j] >= stop
                    target_hit = rh[j] >= target if side > 0 else rl[j] <= target
                    if stop_hit or target_hit:
                        # Adverse stop gaps use the worse open; same-bar ties stop first.
                        if stop_hit:
                            exit_price = min(ro[j], stop) if side > 0 else max(ro[j], stop)
                        else:
                            exit_price = target
                            target_first = True
                        break
                gross = side * (exit_price / entry - 1)
                trades.append((float(gross - COSTS[0] > 0), float(gross - COSTS[1] > 0),
                               float(target_first), gross - COSTS[0], gross - COSTS[1],
                               int(frame.open_ms.iloc[i]) // 86_400_000))
                last_exit = entry_i + horizon - 1

            if not trades:
                continue
            values = np.asarray(trades, dtype=float)
            n = len(values)
            day_ids, inverse = np.unique(values[:, 5], return_inverse=True)
            daily_n = np.bincount(inverse)
            daily_sums = np.column_stack([
                np.bincount(inverse, weights=values[:, col]) for col in range(5)
            ])
            rng = np.random.default_rng(444 + tf + horizon)
            boot = np.empty((BOOTSTRAPS, 5))
            for b in range(BOOTSTRAPS):
                draw = rng.integers(0, len(day_ids), len(day_ids))
                boot[b] = daily_sums[draw].sum(axis=0) / daily_n[draw].sum()
            results.append({
                "signal_family": signal_family, "symbol": symbol,
                "timeframe_min": tf, "horizon_bars": horizon, "n": n,
                "accepted_signal_incidence": n / len(frame),
                "net_positive_base": float(values[:, 0].mean()),
                "net_positive_stress": float(values[:, 1].mean()),
                "target_first": float(values[:, 2].mean()),
                "mean_net_base_pct": float(values[:, 3].mean() * 100),
                "mean_net_stress_pct": float(values[:, 4].mean() * 100),
                "net_positive_base_wilson95": wilson(int(values[:, 0].sum()), n),
                "net_positive_base_day_cluster95": tuple(map(float, np.quantile(boot[:, 0], [0.025, 0.975]))),
                "target_first_day_cluster95": tuple(map(float, np.quantile(boot[:, 2], [0.025, 0.975]))),
                "mean_net_base_day_cluster95_pct": tuple(map(float, np.quantile(boot[:, 3], [0.025, 0.975]) * 100)),
                "mean_net_stress_day_cluster95_pct": tuple(map(float, np.quantile(boot[:, 4], [0.025, 0.975]) * 100)),
            })
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv-out", type=Path, help="optional path for the cell-level CSV")
    parser.add_argument("--signal-family", choices=("rsi2", "rsi2_ema200_trend", "bb_reentry"), default="rsi2")
    args = parser.parse_args()
    db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    rows = []
    for symbol in SYMBOLS:
        raw = pd.read_sql_query(
            "SELECT open_ms,open AS o,high AS h,low AS l,close AS c FROM candles "
            "WHERE symbol=? AND open_ms<? ORDER BY open_ms",
            db, params=(symbol, CUTOFF_MS),
        )
        raw = raw[raw.open_ms + 60_000 <= CUTOFF_MS].reset_index(drop=True)
        rows.extend(evaluate_symbol(raw, symbol, args.signal_family))
        print(f"completed {symbol}: bars={len(raw)} cells={sum(r['symbol'] == symbol for r in rows)}", flush=True)
    db.close()
    if args.csv_out:
        args.csv_out.parent.mkdir(parents=True, exist_ok=True)
        fields = list(rows[0])
        with args.csv_out.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
    eligible = [row for row in rows if row["n"] >= 200]
    print(f"signal_family={args.signal_family} cells={len(rows)} eligible_n_ge_200={len(eligible)}")
    if eligible:
        print("best_target_first_n_ge_200", max(eligible, key=lambda row: row["target_first"]))
        print("best_mean_net_n_ge_200", max(eligible, key=lambda row: row["mean_net_base_pct"]))
        print("best_net_positive_n_ge_200", max(eligible, key=lambda row: row["net_positive_base"]))


if __name__ == "__main__":
    main()
