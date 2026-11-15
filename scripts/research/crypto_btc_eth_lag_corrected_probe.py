#!/usr/bin/env python3
"""Corrected symmetric BTC-impulse/ETH-lag probe over local 1m candles."""
import argparse
import hashlib
import json
import math
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

MINUTE_MS = 60_000
FIVE_MIN_MS = 300_000
HORIZON_MINUTES = 50
CUTOFF_MS = int(pd.Timestamp("2026-11-14T00:00:00Z").timestamp() * 1000)
COSTS = (0.001, 0.003, 0.0015)
SEED = 20261115


def load_minutes(db_path, symbol):
    connection = sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)
    try:
        frame = pd.read_sql_query(
            "SELECT t_open_ms,o,h,l,c FROM candles "
            "WHERE symbol=? AND t_open_ms<? ORDER BY t_open_ms",
            connection, params=(symbol, CUTOFF_MS),
        )
    finally:
        connection.close()
    return frame[frame.t_open_ms % MINUTE_MS == 0].reset_index(drop=True)


def aggregate_complete_5m(frame):
    """Aggregate only UTC 5m buckets containing all five exact minute opens."""
    rows = []
    if frame.empty:
        return pd.DataFrame(columns=("t", "o", "h", "l", "c"))
    buckets = frame.groupby(frame.t_open_ms // FIVE_MIN_MS, sort=True)
    for bucket, group in buckets:
        start = int(bucket) * FIVE_MIN_MS
        times = group.t_open_ms.to_numpy(dtype=np.int64)
        if len(times) != 5 or not np.array_equal(
            times, start + np.arange(5, dtype=np.int64) * MINUTE_MS
        ):
            continue
        rows.append((start, group.o.iloc[0], group.h.max(), group.l.min(), group.c.iloc[-1]))
    return pd.DataFrame(rows, columns=("t", "o", "h", "l", "c"))


def add_zscore(frame, column, window=20):
    returns = np.log(frame[column] / frame[column].shift(1))
    returns = returns.where(frame.t.diff().eq(FIVE_MIN_MS))
    mean = returns.shift(1).rolling(window, min_periods=window).mean()
    std = returns.shift(1).rolling(window, min_periods=window).std(ddof=0)
    return returns, (returns - mean) / std.replace(0, np.nan)


def make_signals(btc, eth):
    aligned = btc.merge(eth, on="t", suffixes=("_btc", "_eth"), validate="one_to_one")
    aligned = aligned.rename(columns={f"{name}_eth": name for name in ("o", "h", "l", "c")})
    # Do not let a shared timestamp bridge missing 5m buckets in either asset.
    contiguous = aligned.t.diff().eq(FIVE_MIN_MS)
    btc_ret, btc_z = add_zscore(aligned, "c_btc")
    eth_ret, eth_z = add_zscore(aligned, "c")
    side = np.sign(btc_ret).astype(float)
    lag = (side * eth_ret >= 0) & (side * eth_ret < side * btc_ret)
    aligned["btc_ret"], aligned["btc_z"] = btc_ret, btc_z
    aligned["eth_ret"], aligned["eth_z"] = eth_ret, eth_z
    aligned["continuous"] = contiguous
    aligned["lag_side"] = np.where((side * btc_z >= 2) & lag & contiguous, side, 0)
    aligned["btc_only_side"] = np.where((side * btc_z >= 2) & contiguous, side, 0)
    eth_side = np.sign(eth_ret)
    aligned["eth_only_side"] = np.where((eth_side * eth_z >= 2) & contiguous, eth_side, 0)
    return aligned


def resolve(signal_pos, side, bars, minutes, previous_range):
    entry_pos = signal_pos + 1
    if entry_pos >= len(bars):
        return None
    entry_time = int(bars.t.iloc[entry_pos])
    entry = float(bars.o.iloc[entry_pos])
    risk = previous_range / entry
    if not math.isfinite(risk) or risk <= 0:
        return None
    path = minutes[(minutes.t_open_ms >= entry_time) &
                   (minutes.t_open_ms < entry_time + HORIZON_MINUTES * MINUTE_MS)]
    expected = entry_time + np.arange(HORIZON_MINUTES, dtype=np.int64) * MINUTE_MS
    if len(path) != HORIZON_MINUTES or not np.array_equal(path.t_open_ms.to_numpy(), expected):
        return None
    stop = entry * (1 - side * risk)
    target = entry * (1 + side * 2 * risk)
    exit_px, reason, exit_time = float(path.c.iloc[-1]), "expiry", int(path.t_open_ms.iloc[-1])
    for row in path.itertuples(index=False):
        if side == 1:
            if row.o <= stop:
                exit_px, reason = float(row.o), "stop_gap"
            elif row.o >= target:
                exit_px, reason = target, "target_gap"
            elif row.l <= stop:
                exit_px, reason = stop, "stop"
            elif row.h >= target:
                exit_px, reason = target, "target"
        else:
            if row.o >= stop:
                exit_px, reason = float(row.o), "stop_gap"
            elif row.o <= target:
                exit_px, reason = target, "target_gap"
            elif row.h >= stop:
                exit_px, reason = stop, "stop"
            elif row.l <= target:
                exit_px, reason = target, "target"
        if reason != "expiry":
            exit_time = int(row.t_open_ms)
            break
    gross = side * (exit_px / entry - 1)
    expiry_direction = side * (float(path.c.iloc[-1]) / entry - 1) > 0
    return {"signal_time": int(bars.t.iloc[signal_pos]), "entry_time": entry_time,
            "exit_time": exit_time, "side": int(side), "target_first": reason.startswith("target"),
            "expiry_direction": expiry_direction, "gross_return": gross,
            "reason": reason, "day": int(entry_time // 86_400_000)}


def collect_trades(bars, minutes, signal_col):
    trades, last_exit = [], -1
    for pos in np.flatnonzero(bars[signal_col].to_numpy()):
        if pos <= last_exit or pos == 0:
            continue
        risk_range = float(bars.h.iloc[pos - 1] - bars.l.iloc[pos - 1])
        trade = resolve(pos, int(bars[signal_col].iloc[pos]), bars, minutes, risk_range)
        if trade is not None:
            trades.append(trade)
            last_exit = pos + 1
    return trades


def wilson_lower(successes, n):
    if not n:
        return None
    z = 1.959963984540054
    p = successes / n
    return (p + z*z/(2*n) - z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))) / (1+z*z/n)


def moving_block_ci(values, block_days=7, draws=10_000):
    by_day = {}
    for item in values:
        by_day.setdefault(item["day"], []).append(item)
    if not by_day:
        return [None, None]
    first, last = min(by_day), max(by_day)
    days = [by_day.get(day, []) for day in range(first, last + 1)]
    counts = np.array([len(day) for day in days], dtype=float)
    rng = np.random.default_rng(SEED)
    n, block_count = len(days), int(np.ceil(len(days) / block_days))
    offsets = np.arange(block_days)
    stats = np.empty(draws)
    for draw in range(draws):
        starts = rng.integers(0, n, size=block_count)
        indexes = np.concatenate([(start + offsets) % n for start in starts])[:n]
        selected = [trade for ix in indexes for trade in days[ix]]
        stats[draw] = np.mean([trade["gross_return"] for trade in selected]) if selected else np.nan
    return [float(value * 100) for value in np.nanquantile(stats, [0.025, 0.975])]


def summarize(trades):
    if not trades:
        return {"n": 0}
    gross = np.array([t["gross_return"] for t in trades])
    targets = sum(t["target_first"] for t in trades)
    result = {"n": len(trades), "long_n": sum(t["side"] == 1 for t in trades),
              "short_n": sum(t["side"] == -1 for t in trades),
              "target_first_pct": targets / len(trades) * 100,
              "target_first_wilson95_lower_pct": wilson_lower(targets, len(trades)) * 100,
              "expiry_direction_pct": np.mean([t["expiry_direction"] for t in trades]) * 100,
              "avg_gross_pct": np.mean(gross) * 100,
              "block95_avg_gross_pct": moving_block_ci(trades),
              "cost_scenarios": []}
    for cost in COSTS:
        net = gross - cost
        result["cost_scenarios"].append({"round_trip_cost_pct": cost * 100,
            "net_positive_pct": np.mean(net > 0) * 100, "avg_net_pct": np.mean(net) * 100})
    return result


def fingerprint(frames):
    digest = hashlib.sha256()
    for symbol in sorted(frames):
        digest.update(symbol.encode())
        for col in ("t_open_ms", "o", "h", "l", "c"):
            values = frames[symbol][col].to_numpy()
            digest.update(values.astype("<i8" if col == "t_open_ms" else "<f8").tobytes())
    return digest.hexdigest()


def run(db_path):
    minutes = {symbol: load_minutes(db_path, symbol) for symbol in ("BTCUSDT", "ETHUSDT")}
    btc = aggregate_complete_5m(minutes["BTCUSDT"])
    eth = aggregate_complete_5m(minutes["ETHUSDT"])
    aligned = make_signals(btc, eth)
    eth_minutes = minutes["ETHUSDT"]
    strategies = {}
    for name, column in (("btc_eth_lag_corrected", "lag_side"),
                         ("btc_impulse_only", "btc_only_side"),
                         ("eth_impulse_only", "eth_only_side")):
        trades = collect_trades(aligned, eth_minutes, column)
        strategies[name] = summarize(trades)
    return {"data_sha256": fingerprint(minutes), "symbols": list(minutes),
            "source_rows_1m": {k: len(v) for k, v in minutes.items()},
            "complete_5m_rows": {"BTCUSDT": len(btc), "ETHUSDT": len(eth)},
            "aligned_5m_rows": len(aligned), "cutoff_exclusive_utc": "2026-11-14T00:00:00+00:00",
            "signal": "BTC signed prior-20-return z-score >=2 and ETH same-direction 5m return in [0, BTC directional return)",
            "entry": "next ETH 5m open", "risk": "prior completed ETH 5m high-low / entry",
            "barriers": "stop 1R, target 2R, 50 consecutive 1m bars; stop-first; adverse stop gap; expiry at final close",
            "cost_scenarios_pct": [cost * 100 for cost in COSTS],
            "block_bootstrap": "7 UTC calendar days, 10000 draws, seed 20261115",
            "strategies": strategies, "oos": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=Path(__file__).resolve().parents[2] / "chart_predictor/data/candles.sqlite")
    args = parser.parse_args()
    print(json.dumps(run(args.db), indent=2))


if __name__ == "__main__":
    main()
