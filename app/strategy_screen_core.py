"""Reusable event-study harness for first-pass strategy screening.

The contract is intentionally simple: a signal function returns a direction series
indexed like the OHLCV frame, where 1 means long, -1 means short, and 0 means no
event. The harness enters at the next bar open, exits after N bars at close, and
compares the result with same-symbol unconditional entries.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd

SPOT_FEE_ONE_WAY_PCT = 0.1
FUTURES_FEE_ONE_WAY_PCT = 0.05

HORIZONS_DEFAULT = (5, 10, 20)

SignalFunc = Callable[[pd.DataFrame], pd.Series]


@dataclass(frozen=True)
class HorizonStats:
    signal_n: int
    avg_return_pct: float
    baseline_avg_return_pct: float
    edge_pctp: float
    win_rate_pct: float


@dataclass(frozen=True)
class StrategyStats:
    signal_count: int
    per_horizon: dict[int, HorizonStats]


def clean_direction(signal: pd.Series, index: pd.Index) -> pd.Series:
    out = signal.reindex(index).fillna(0)
    out = out.astype(float).clip(-1, 1)
    out = out.where(out.abs() >= 1, 0)
    return out.astype(int)


def evaluate_direction_series(
    frame: pd.DataFrame,
    direction: pd.Series,
    horizons: tuple[int, ...] = HORIZONS_DEFAULT,
    fee_one_way_pct: float = FUTURES_FEE_ONE_WAY_PCT,
) -> StrategyStats | None:
    max_h = max(horizons)
    if len(frame) < max_h + 2:
        return None

    df = frame.copy()
    direction = clean_direction(direction, df.index)
    opens = df["Open"].to_numpy(dtype=float)
    closes = df["Close"].to_numpy(dtype=float)
    dirs = direction.to_numpy(dtype=int)
    n = len(df)
    round_trip_fee_pct = fee_one_way_pct * 2
    event_idx = [i for i in range(n - 1 - max_h) if dirs[i] != 0]

    per_horizon: dict[int, HorizonStats] = {}
    for h in horizons:
        signal_rets: list[float] = []
        long_events = 0
        short_events = 0
        for i in event_idx:
            entry_i = i + 1
            exit_i = entry_i + h
            if exit_i >= n or opens[entry_i] <= 0:
                continue
            raw = (closes[exit_i] / opens[entry_i] - 1) * 100
            signal_rets.append(float(raw * dirs[i] - round_trip_fee_pct))
            if dirs[i] > 0:
                long_events += 1
            else:
                short_events += 1

        baseline_rets: list[float] = []
        for i in range(n - 1 - h):
            entry_i = i + 1
            exit_i = entry_i + h
            if exit_i >= n or opens[entry_i] <= 0:
                continue
            raw = (closes[exit_i] / opens[entry_i] - 1) * 100
            if long_events:
                baseline_rets.append(float(raw - round_trip_fee_pct))
            if short_events:
                baseline_rets.append(float(-raw - round_trip_fee_pct))

        avg = float(np.mean(signal_rets)) if signal_rets else float("nan")
        base = float(np.mean(baseline_rets)) if baseline_rets else float("nan")
        win = float(np.mean([r > 0 for r in signal_rets]) * 100) if signal_rets else float("nan")
        per_horizon[h] = HorizonStats(
            signal_n=len(signal_rets),
            avg_return_pct=avg,
            baseline_avg_return_pct=base,
            edge_pctp=avg - base if np.isfinite(avg) and np.isfinite(base) else float("nan"),
            win_rate_pct=win,
        )

    return StrategyStats(signal_count=len(event_idx), per_horizon=per_horizon)


def evaluate_signal_func(
    frame: pd.DataFrame,
    signal_func: SignalFunc,
    horizons: tuple[int, ...] = HORIZONS_DEFAULT,
    fee_one_way_pct: float = FUTURES_FEE_ONE_WAY_PCT,
) -> StrategyStats | None:
    return evaluate_direction_series(frame, signal_func(frame), horizons, fee_one_way_pct)


def aggregate_symbol_stats(results: dict[str, StrategyStats], horizons: tuple[int, ...] = HORIZONS_DEFAULT) -> StrategyStats:
    total_signals = sum(r.signal_count for r in results.values())
    per_horizon: dict[int, HorizonStats] = {}
    for h in horizons:
        n = sum(r.per_horizon[h].signal_n for r in results.values())
        if n == 0:
            per_horizon[h] = HorizonStats(0, float("nan"), float("nan"), float("nan"), float("nan"))
            continue
        avg = sum(r.per_horizon[h].avg_return_pct * r.per_horizon[h].signal_n for r in results.values() if r.per_horizon[h].signal_n) / n
        base = sum(r.per_horizon[h].baseline_avg_return_pct * r.per_horizon[h].signal_n for r in results.values() if r.per_horizon[h].signal_n) / n
        win = sum(r.per_horizon[h].win_rate_pct * r.per_horizon[h].signal_n for r in results.values() if r.per_horizon[h].signal_n) / n
        per_horizon[h] = HorizonStats(n, avg, base, avg - base, win)
    return StrategyStats(total_signals, per_horizon)


def atr(frame: pd.DataFrame, period: int = 14) -> pd.Series:
    high = frame["High"]
    low = frame["Low"]
    close = frame["Close"]
    tr = pd.concat([(high - low), (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return (100 - (100 / (1 + rs))).fillna(50)


def adx(frame: pd.DataFrame, period: int = 14) -> pd.Series:
    high = frame["High"]
    low = frame["Low"]
    close = frame["Close"]
    plus_dm = (high.diff()).where((high.diff() > -low.diff()) & (high.diff() > 0), 0.0)
    minus_dm = (-low.diff()).where((-low.diff() > high.diff()) & (-low.diff() > 0), 0.0)
    tr = pd.concat([(high - low), (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
    atr_v = tr.ewm(alpha=1 / period, adjust=False).mean()
    plus_di = 100 * plus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr_v
    minus_di = 100 * minus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr_v
    dx = ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)) * 100
    return dx.ewm(alpha=1 / period, adjust=False).mean()


def rolling_vwap(frame: pd.DataFrame, period: int = 20) -> pd.Series:
    typical = (frame["High"] + frame["Low"] + frame["Close"]) / 3
    pv = typical * frame["Volume"]
    return pv.rolling(period).sum() / frame["Volume"].rolling(period).sum()


def zscore(series: pd.Series, period: int = 20) -> pd.Series:
    mean = series.rolling(period).mean()
    std = series.rolling(period).std()
    return (series - mean) / std.replace(0, np.nan)


def percentile_rank_last(values: pd.Series) -> float:
    if values.isna().any():
        return np.nan
    return float(values.rank(pct=True).iloc[-1] * 100)


def connors_rsi(close: pd.Series, rsi_period: int = 3, streak_period: int = 2, rank_period: int = 100) -> pd.Series:
    base_rsi = rsi(close, rsi_period)
    diff = close.diff()
    streak_vals: list[int] = []
    current = 0
    for v in diff:
        if pd.isna(v) or v == 0:
            current = 0
        elif v > 0:
            current = current + 1 if current > 0 else 1
        else:
            current = current - 1 if current < 0 else -1
        streak_vals.append(current)
    streak = pd.Series(streak_vals, index=close.index, dtype=float)
    streak_rsi = rsi(streak, streak_period)
    one_day = close.pct_change()
    pr = one_day.rolling(rank_period).apply(percentile_rank_last, raw=False)
    return (base_rsi + streak_rsi + pr) / 3
