#!/usr/bin/env python3
"""Fixed 1m sweep-rejection/taker-flow probe; candle DB is read-only."""
import argparse
import csv
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

DB = Path(__file__).resolve().parents[2] / "chart_predictor/data/vision_dev.sqlite"
CUTOFF_MS = int(pd.Timestamp("2026-10-09T00:00:00Z").timestamp() * 1000)
SYMBOLS = ("BNBUSDT", "BTCUSDT", "DOGEUSDT", "ETHUSDT")
HORIZONS = (10, 20)
COSTS = (0.001, 0.003)
BOOTSTRAPS = 1000


def make_signals(frame):
    """Detect completed-bar range sweeps with wick-close and taker-flow agreement."""
    times = frame.open_ms.to_numpy(np.int64)
    op = frame.o.to_numpy(float)
    high, low, close = (frame[k].to_numpy(float) for k in ("h", "l", "c"))
    quote = frame.quote_volume.to_numpy(float)
    taker = frame.taker_buy_quote.to_numpy(float)
    share = np.divide(taker, quote, out=np.full_like(taker, np.nan), where=quote > 0)
    resistance = pd.Series(high).shift(1).rolling(20, min_periods=20).max().to_numpy()
    support = pd.Series(low).shift(1).rolling(20, min_periods=20).min().to_numpy()
    prior_close = np.r_[np.nan, close[:-1]]
    tr = np.maximum(high - low, np.maximum(abs(high - prior_close), abs(low - prior_close)))
    atr = pd.Series(tr).rolling(14, min_periods=14).mean().to_numpy()
    adjacent = np.r_[False, np.diff(times) == 60_000]
    continuous = pd.Series(adjacent.astype(np.int8)).rolling(20, min_periods=20).sum().eq(20).to_numpy()
    width = high - low
    close_location = np.divide(close - low, width, out=np.full_like(close, np.nan), where=width > 0)
    lower_wick = np.minimum(op, close) - low
    upper_wick = high - np.maximum(op, close)
    long_mask = ((low < support) & (close > support) & (lower_wick >= 0.5 * atr)
                 & (close_location >= 0.60) & (share >= 0.65))
    short_mask = ((high > resistance) & (close < resistance) & (upper_wick >= 0.5 * atr)
                  & (close_location <= 0.40) & (share <= 0.35))
    events = [(i, 1 if long_mask[i] else -1) for i in range(20, len(frame) - 21)
              if continuous[i] and np.isfinite(atr[i]) and atr[i] > 0
              and (long_mask[i] or short_mask[i])]
    return events, atr


def score_path(side, entry, risk, start, horizon, arrays):
    """Resolve 1m barriers; stop-first ties and adverse stop gaps."""
    op, high, low, close = arrays
    stop = entry - side * risk
    target = entry + side * 2 * risk
    exit_price, target_first = close[start + horizon - 1], False
    for j in range(start, start + horizon):
        stop_hit = low[j] <= stop if side > 0 else high[j] >= stop
        target_hit = high[j] >= target if side > 0 else low[j] <= target
        if stop_hit or target_hit:
            if stop_hit:
                exit_price = min(op[j], stop) if side > 0 else max(op[j], stop)
            else:
                exit_price, target_first = target, True
            break
    gross = side * (exit_price / entry - 1)
    return float(target_first), gross


def moving_block_ci(values_by_trade, days, seed):
    """Seven-calendar-day moving-block bootstrap with empty days retained."""
    day_values = np.asarray(days, dtype=np.int64)
    unique, inverse = np.unique(day_values, return_inverse=True)
    sums = np.column_stack([np.bincount(inverse, weights=values_by_trade[:, i]) for i in range(values_by_trade.shape[1])])
    counts = np.bincount(inverse)
    span = int(unique[-1] - unique[0] + 1)
    calendar_sums = np.zeros((span, values_by_trade.shape[1]))
    calendar_counts = np.zeros(span)
    offsets = unique - unique[0]
    calendar_sums[offsets], calendar_counts[offsets] = sums, counts
    prefix_sums = np.vstack((np.zeros(values_by_trade.shape[1]), np.cumsum(calendar_sums, axis=0)))
    prefix_counts = np.r_[0.0, np.cumsum(calendar_counts)]
    block_days = min(7, span)
    n_blocks = int(np.ceil(span / block_days))
    start_count = span - block_days + 1
    rng = np.random.default_rng(seed)
    boot = np.empty((BOOTSTRAPS, values_by_trade.shape[1]))
    for begin in range(0, BOOTSTRAPS, 100):
        end = min(begin + 100, BOOTSTRAPS)
        starts = rng.integers(0, start_count, size=(end - begin, n_blocks))
        ends = starts + block_days
        sampled_sums = (prefix_sums[ends] - prefix_sums[starts]).sum(axis=1)
        sampled_counts = (prefix_counts[ends] - prefix_counts[starts]).sum(axis=1)
        boot[begin:end] = sampled_sums / sampled_counts[:, None]
    return [tuple(map(float, np.quantile(boot[:, i], [0.025, 0.975]))) for i in range(boot.shape[1])]


def evaluate(frame, symbol):
    events, atr = make_signals(frame)
    times = frame.open_ms.to_numpy(np.int64)
    opens = frame.o.to_numpy(float)
    arrays = tuple(frame[k].to_numpy(float) for k in ("o", "h", "l", "c"))
    rows = []
    for horizon in HORIZONS:
        trades, last_exit = [], -1
        for signal_i, side in events:
            entry_i = signal_i + 1
            if entry_i <= last_exit or entry_i + horizon > len(frame):
                continue
            start_ms = int(times[entry_i])
            end_ms = int(times[entry_i + horizon - 1]) + 60_000
            lo, hi = np.searchsorted(times, start_ms), np.searchsorted(times, end_ms)
            if hi - lo != horizon:
                continue
            entry, stop_price = opens[entry_i], float(frame.l.iloc[signal_i] if side > 0 else frame.h.iloc[signal_i])
            risk = side * (entry - stop_price)
            if not np.isfinite(risk) or risk <= 0 or entry <= 0:
                continue
            actual = score_path(side, entry, risk, lo, horizon, arrays)
            reverse = score_path(-side, entry, risk, lo, horizon, arrays)
            actual_net = [actual[1] - cost for cost in COSTS]
            reverse_net = [reverse[1] - cost for cost in COSTS]
            trades.append((actual[0], float(actual_net[0] > 0), float(actual_net[1] > 0),
                           actual_net[0], actual_net[1], reverse[0],
                           float(reverse_net[0] > 0), float(reverse_net[1] > 0),
                           reverse_net[0], reverse_net[1], times[signal_i] // 86_400_000))
            last_exit = entry_i + horizon - 1
        if not trades:
            continue
        values = np.asarray(trades, dtype=float)
        ci = moving_block_ci(values[:, :10], values[:, 10].astype(np.int64), 9100 + horizon)
        rows.append({
            "strategy": "1m_20bar_sweep_wick_takerflow_2R",
            "symbol": symbol, "signal_timeframe_min": 1, "horizon_min": horizon,
            "n": len(values), "coverage_per_minute": len(values) / len(frame),
            "target_first": float(values[:, 0].mean()), "target_first_7d_block95": ci[0],
            "net_positive_base": float(values[:, 1].mean()), "net_positive_stress": float(values[:, 2].mean()),
            "mean_net_base_pct": float(values[:, 3].mean() * 100), "mean_base_7d_block95_pct": tuple(x * 100 for x in ci[3]),
            "mean_net_stress_pct": float(values[:, 4].mean() * 100), "mean_stress_7d_block95_pct": tuple(x * 100 for x in ci[4]),
            "reverse_target_first": float(values[:, 5].mean()), "reverse_mean_net_base_pct": float(values[:, 8].mean() * 100),
            "reverse_mean_net_stress_pct": float(values[:, 9].mean() * 100),
            "first_signal_day_utc": pd.to_datetime(times[events[0][0]], unit="ms", utc=True).date().isoformat(),
            "last_signal_day_utc": pd.to_datetime(times[events[-1][0]], unit="ms", utc=True).date().isoformat(),
            "cost_base_round_trip_pct": COSTS[0] * 100, "cost_stress_round_trip_pct": COSTS[1] * 100,
        })
    return rows


def synthetic_checks():
    rng = np.random.default_rng(20261115)
    n = 1000
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.001, n)))
    quote = np.full(n, 100_000.0)
    frame = pd.DataFrame({"open_ms": np.arange(n, dtype=np.int64) * 60_000,
                          "o": close, "h": close * 1.002, "l": close * 0.998, "c": close,
                          "quote_volume": quote, "taker_buy_quote": quote * 0.5})
    events1, _ = make_signals(frame)
    changed = frame.copy()
    changed.loc[800:, ["o", "h", "l", "c", "taker_buy_quote"]] *= 1.1
    events2, _ = make_signals(changed)
    assert [(i, s) for i, s in events1 if i < 800] == [(i, s) for i, s in events2 if i < 800]
    assert all(np.all(np.diff(frame.open_ms.iloc[i - 20:i + 1]) == 60_000) for i, _ in events1)
    # Deliberately future-dependent feature must change at the mutation boundary.
    bad1 = frame.c.shift(-1).rolling(2, min_periods=2).mean().to_numpy()
    bad2 = changed.c.shift(-1).rolling(2, min_periods=2).mean().to_numpy()
    assert not np.allclose(bad1[799], bad2[799], equal_nan=True)
    both = pd.DataFrame({"o": [100.0], "h": [105.0], "l": [95.0], "c": [100.0]})
    target_first, gross = score_path(1, 100, 1, 0, 1, tuple(both[k].to_numpy(float) for k in ("o", "h", "l", "c")))
    assert target_first == 0 and np.isclose(gross, -0.01)
    gap = frame.drop(index=500).reset_index(drop=True)
    gap_events, _ = make_signals(gap)
    assert all(np.all(np.diff(gap.open_ms.iloc[i - 20:i + 1]) == 60_000) for i, _ in gap_events)
    print("prefix/future-peek/gap/stop-first synthetic checks PASS")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv-out", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        synthetic_checks()
        return
    if not args.csv_out:
        parser.error("--csv-out is required unless --self-test is set")
    db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    rows = []
    for symbol in SYMBOLS:
        frame = pd.read_sql_query(
            "SELECT open_ms,open AS o,high AS h,low AS l,close AS c,quote_volume,taker_buy_quote "
            "FROM candles WHERE symbol=? AND open_ms<? ORDER BY open_ms",
            db, params=(symbol, CUTOFF_MS))
        frame = frame[frame.open_ms + 60_000 <= CUTOFF_MS].reset_index(drop=True)
        rows.extend(evaluate(frame, symbol))
        print(f"completed {symbol}: minute_rows={len(frame)}", flush=True)
    db.close()
    args.csv_out.parent.mkdir(parents=True, exist_ok=True)
    with args.csv_out.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"cells={len(rows)} n_ge_200={sum(int(x['n']) >= 200 for x in rows)}")
    for row in rows:
        print(row)


if __name__ == "__main__":
    main()
