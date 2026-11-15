#!/usr/bin/env python3
"""One fixed BTC 1m three-close streak continuation probe; read-only SQLite."""
import argparse
import hashlib
import json
import math
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

CUTOFF_MS = int(pd.Timestamp("2026-10-09T00:00:00Z").timestamp() * 1000)
HORIZON = 15
ROUND_TRIP_COST = 0.0010
ROUND_TRIP_SLIPPAGE = 0.0004
MIN_N = 200
BOOTSTRAP_DRAWS = 10_000
SEED = 20261115
DAY_MS = 86_400_000
MINUTE_MS = 60_000


def wilson_lower(successes, count):
    if count == 0:
        return float("nan")
    z = 1.959963984540054
    p = successes / count
    denominator = 1 + z * z / count
    midpoint = p + z * z / (2 * count)
    radius = z * math.sqrt(
        p * (1 - p) / count + z * z / (4 * count * count)
    )
    return (midpoint - radius) / denominator


def streak_signals(open_, close, timestamps):
    direction = np.sign(close - open_)
    continuous = np.r_[False, np.diff(timestamps) == MINUTE_MS]
    signals = np.zeros(len(close), dtype=np.int8)
    for index in range(2, len(close)):
        if not continuous[index - 1:index + 1].all():
            continue
        last_three = direction[index - 2:index + 1]
        if (last_three == 1).all():
            signals[index] = 1
        elif (last_three == -1).all():
            signals[index] = -1
    return signals


def true_range_atr(high, low, close, timestamps, period=14):
    previous = np.r_[np.nan, close[:-1]]
    tr = np.maximum(high - low, np.maximum(np.abs(high - previous), np.abs(low - previous)))
    continuous = np.r_[False, np.diff(timestamps) == MINUTE_MS]
    atr = pd.Series(tr).rolling(period, min_periods=period).mean().to_numpy()
    valid = np.zeros(len(close), dtype=bool)
    for index in range(period, len(close)):
        valid[index] = continuous[index - period + 1:index + 1].all()
    atr[~valid] = np.nan
    return atr


def resolve_trade(signal_index, side, timestamps, open_, high, low, close, atr):
    entry_index = signal_index + 1
    end_index = entry_index + HORIZON - 1
    if end_index >= len(timestamps) or not np.isfinite(atr[signal_index]) or atr[signal_index] <= 0:
        return None
    if not np.all(np.diff(timestamps[entry_index:end_index + 1]) == MINUTE_MS):
        return None
    entry = open_[entry_index]
    stop = entry - side * atr[signal_index]
    target = entry + side * atr[signal_index]
    exit_price = close[end_index]
    target_first = False
    for index in range(entry_index, end_index + 1):
        stop_hit = low[index] <= stop if side == 1 else high[index] >= stop
        target_hit = high[index] >= target if side == 1 else low[index] <= target
        if stop_hit:
            exit_price = min(open_[index], stop) if side == 1 else max(open_[index], stop)
            break
        if target_hit:
            exit_price = target
            target_first = True
            break
    expiry_direction = side * (close[end_index] / entry - 1) > 0
    gross_return = side * (exit_price / entry - 1)
    return {
        "signal_index": signal_index, "entry_index": entry_index,
        "end_index": end_index, "side": side, "target_first": target_first,
        "expiry_direction_correct": expiry_direction, "gross_return": gross_return,
        "signal_day": int(timestamps[signal_index] // DAY_MS),
    }


def moving_block_ci(values_by_day, count_by_day, seed=SEED,
                    draws=BOOTSTRAP_DRAWS, block_days=7):
    values_by_day = np.asarray(values_by_day, dtype=float)
    count_by_day = np.asarray(count_by_day, dtype=float)
    n_days = len(count_by_day)
    if n_days < block_days or count_by_day.sum() == 0:
        return [float("nan"), float("nan")]
    rng = np.random.default_rng(seed)
    blocks = int(np.ceil(n_days / block_days))
    offsets = np.arange(block_days)
    values = np.empty(draws)
    for draw in range(draws):
        starts = rng.integers(0, n_days, size=blocks)
        indexes = np.concatenate([(start + offsets) % n_days for start in starts])[:n_days]
        total = count_by_day[indexes].sum()
        values[draw] = values_by_day[indexes].sum() / total if total else np.nan
    return list(map(float, np.nanquantile(values, [0.025, 0.975])))


def summarize(trades, baseline_trades, timestamps, symbol, rows):
    n = len(trades)
    if not n:
        return {"symbol": symbol, "rows": rows, "trades": 0, "decision": "REJECT"}
    successes = int(sum(trade["target_first"] for trade in trades))
    first_day = min(trade["signal_day"] for trade in trades)
    last_day = max(trade["signal_day"] for trade in trades)
    day_count = last_day - first_day + 1
    daily_success = np.zeros(day_count)
    daily_net = np.zeros(day_count)
    daily_count = np.zeros(day_count)
    for trade in trades:
        offset = trade["signal_day"] - first_day
        daily_success[offset] += trade["target_first"]
        daily_net[offset] += trade["gross_return"] - ROUND_TRIP_COST - ROUND_TRIP_SLIPPAGE
        daily_count[offset] += 1
    target_rate = successes / n
    lower = wilson_lower(successes, n)
    block_ci = moving_block_ci(daily_success, daily_count)
    net_ci = moving_block_ci(daily_net, daily_count)
    net = np.asarray(
        [trade["gross_return"] - ROUND_TRIP_COST - ROUND_TRIP_SLIPPAGE for trade in trades]
    )
    expiry_correct = np.mean([trade["expiry_direction_correct"] for trade in trades])
    decision = "PASS" if n >= MIN_N and lower >= 0.80 else "FAIL"
    return {
        "symbol": symbol, "rows": rows, "trades": n,
        "first_signal_utc": pd.Timestamp(timestamps[min(t["signal_index"] for t in trades)],
                                         unit="ms", tz="UTC").isoformat(),
        "last_signal_utc": pd.Timestamp(timestamps[max(t["signal_index"] for t in trades)],
                                        unit="ms", tz="UTC").isoformat(),
        "utc_calendar_days": day_count, "target_first_rate_pct": target_rate * 100,
        "target_first_wilson95_lower_pct": lower * 100,
        "target_first_7day_moving_block95_pct": [v * 100 for v in block_ci],
        "mean_net_7day_moving_block95_pct": [v * 100 for v in net_ci],
        "expiry_direction_accuracy_pct": expiry_correct * 100,
        "net_positive_rate_pct": float(np.mean(net > 0) * 100),
        "mean_net_return_pct": float(np.mean(net) * 100),
        "baseline_same_anchor_always_long": {
            "trades": len(baseline_trades),
            "target_first_rate_pct": float(np.mean([t["target_first"] for t in baseline_trades]) * 100),
            "net_positive_rate_pct": float(np.mean([
                t["gross_return"] - ROUND_TRIP_COST - ROUND_TRIP_SLIPPAGE > 0
                for t in baseline_trades
            ]) * 100),
            "mean_net_return_pct": float(np.mean([
                t["gross_return"] - ROUND_TRIP_COST - ROUND_TRIP_SLIPPAGE
                for t in baseline_trades
            ]) * 100),
        },
        "gate_min_200_and_wilson_lower_80pct": decision,
    }


def load_data(db_path, symbol):
    connection = sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)
    frame = pd.read_sql_query(
        "SELECT open_ms,open AS o,high AS h,low AS l,close AS c FROM candles "
        "WHERE symbol=? AND open_ms<? ORDER BY open_ms",
        connection, params=(symbol, CUTOFF_MS),
    )
    connection.close()
    frame = frame[
        (frame.open_ms % MINUTE_MS == 0)
        & (frame.open_ms + MINUTE_MS <= CUTOFF_MS)
    ].reset_index(drop=True)
    return frame


def run(db_path, symbol):
    frame = load_data(db_path, symbol)
    timestamps = frame.open_ms.to_numpy(np.int64)
    open_, high, low, close = (
        frame[name].to_numpy(float) for name in ("o", "h", "l", "c")
    )
    atr = true_range_atr(high, low, close, timestamps)
    signals = streak_signals(open_, close, timestamps)
    digest = hashlib.sha256()
    for column in (timestamps.astype("<i8"), open_.astype("<f8"),
                   high.astype("<f8"), low.astype("<f8"), close.astype("<f8")):
        digest.update(column.tobytes())
    trades, baseline_trades, last_exit = [], [], -1
    for index in np.flatnonzero(signals):
        entry_index = index + 1
        if entry_index <= last_exit:
            continue
        trade = resolve_trade(
            index, int(signals[index]), timestamps, open_, high, low, close, atr
        )
        if trade is None:
            continue
        trades.append(trade)
        baseline_trade = resolve_trade(
            index, 1, timestamps, open_, high, low, close, atr
        )
        if baseline_trade is not None:
            baseline_trades.append(baseline_trade)
        last_exit = trade["end_index"]
    summary = summarize(trades, baseline_trades, timestamps, symbol, len(frame))
    summary.update({
        "timeframe": "1m", "horizon_bars": HORIZON,
        "cutoff_exclusive_utc": pd.Timestamp(CUTOFF_MS, unit="ms", tz="UTC").isoformat(),
        "entry": "signal next 1m open", "stop": "1x signal ATR14",
        "target": "1x signal ATR14", "same_minute_tie": "stop first",
        "stop_gap_fill": "adverse open", "round_trip_cost_pct": ROUND_TRIP_COST * 100,
        "round_trip_slippage_pct": ROUND_TRIP_SLIPPAGE * 100,
        "baseline": "always-long same selected anchors and ATR barriers",
        "data_sha256": digest.hexdigest(),
        "data_fingerprint": {
            "first_open_ms": int(timestamps[0]), "last_open_ms": int(timestamps[-1]),
            "rows": len(timestamps),
        } if len(timestamps) else {},
        "oos": False,
    })
    return summary, trades


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--db", type=Path,
        default=Path(__file__).resolve().parents[2] / "chart_predictor/data/vision_dev.sqlite",
    )
    parser.add_argument("--symbol", default="BTCUSDT")
    args = parser.parse_args()
    result, _ = run(args.db, args.symbol)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
