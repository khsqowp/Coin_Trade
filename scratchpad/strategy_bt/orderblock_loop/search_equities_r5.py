"""R5 train-only equity search with point-in-time membership gating.

The runner implements the ten fixed E3 rules. TEST access is absent by design.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from statistics import mean, pstdev, stdev
from typing import Iterable

import pandas as pd

from data_access import EQUITY_COMMON_SPLIT_MS
from equities import Bar, Trade, preregistered_costs
from data_quality import SymbolQualityError, filter_equity_bars
from resource_guard import heavy_task

ROOT = Path(__file__).resolve().parent
MEMBERSHIP_FIELDS = {"market", "symbol", "alive_from", "alive_through", "source", "source_asof"}
MARKETS = {"US", "KR"}
NEW_CANDIDATES = tuple(f"E3-{letter}" for letter in "ABCDEFGHIJ")
TRIAL_FIELDS = ["trial_id", "round", "market_group", "utc_timestamp", "definition",
                "parameter_grid_hash", "code_sha256", "train_period", "metric", "rank", "notes"]


@dataclass(frozen=True)
class Membership:
    market: str
    symbol: str
    alive_from: date
    alive_through: date
    source: str
    source_asof: date

    def alive(self, when: date) -> bool:
        return self.alive_from <= when <= self.alive_through


def load_membership(path: Path) -> dict[tuple[str, str], Membership]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not MEMBERSHIP_FIELDS.issubset(reader.fieldnames):
            raise ValueError(f"membership CSV requires {sorted(MEMBERSHIP_FIELDS)}")
        records = {}
        for row in reader:
            raw_market, symbol = row["market"].strip(), row["symbol"].strip()
            market = "KR" if raw_market in {"KOSPI", "KOSDAQ", "KONEX", "KOSDAQ GLOBAL"} else raw_market
            if market not in MARKETS or not symbol:
                raise ValueError(f"invalid membership key: {market!r}/{symbol!r}")
            key = (market, symbol)
            if key in records:
                raise ValueError(f"duplicate membership record: {market}/{symbol}")
            record = Membership(market, symbol, date.fromisoformat(row["alive_from"]),
                                date.fromisoformat(row["alive_through"]), row["source"].strip(),
                                date.fromisoformat(row["source_asof"]))
            if record.alive_from > record.alive_through or not record.source:
                raise ValueError(f"invalid membership interval/source: {market}/{symbol}")
            records[key] = record
    if not records:
        raise ValueError("membership CSV is empty")
    return records


def survivorship_safe_trades(trades: Iterable[Trade], daily_bars: list[Bar],
                             membership: Membership) -> tuple[list[Trade], int]:
    kept, gaps = [], 0
    for trade in trades:
        signal_day = _day(daily_bars[trade.signal_index])
        exit_day = _day(daily_bars[trade.exit_index])
        if not membership.alive(signal_day):
            continue
        if not membership.alive(exit_day):
            gaps += 1
            continue
        kept.append(trade)
    return kept, gaps


def _day(bar: Bar) -> date:
    return pd.Timestamp(bar.timestamp, unit="ms", tz="UTC").date()


def _daily_bars(frame: pd.DataFrame, membership: Membership,
                quality_stats: dict[str, int] | None = None) -> list[Bar]:
    required = {"open_time", "open", "high", "low", "close"}
    if not required.issubset(frame.columns):
        raise ValueError(f"daily columns missing: {sorted(required - set(frame.columns))}")
    frame, stats = filter_equity_bars(frame, membership.symbol)
    if quality_stats is not None:
        quality_stats.update(stats)
    if "complete" in frame and not pd.api.types.is_bool_dtype(frame["complete"].dtype):
        raise ValueError("complete column must be boolean")
    output = []
    for row in frame.itertuples(index=False):
        stamp = int(row.open_time)
        day = pd.Timestamp(stamp, unit="ms", tz="UTC").date()
        if day < membership.alive_from or day > membership.alive_through:
            continue
        bar = Bar(stamp, float(row.open), float(row.high), float(row.low), float(row.close),
                  bool(getattr(row, "complete", True)))
        if not bar.complete:
            raise ValueError(f"incomplete bar for {membership.symbol} at {day}")
        if output and stamp <= output[-1].timestamp:
            raise ValueError(f"non-increasing timestamp for {membership.symbol}")
        output.append(bar)
    return output


def _daily_volumes(frame: pd.DataFrame, membership: Membership) -> list[float] | None:
    if "volume" not in frame.columns:
        return None
    output = []
    for row in frame.itertuples(index=False):
        day = pd.Timestamp(int(row.open_time), unit="ms", tz="UTC").date()
        if membership.alive_from <= day <= membership.alive_through:
            value = float(row.volume)
            if not pd.notna(value) or value < 0:
                raise ValueError(f"invalid volume for {membership.symbol} at {day}")
            output.append(value)
    return output


def _atr(bars: list[Bar], i: int, period: int) -> float | None:
    if i + 1 < period:
        return None
    values = []
    for j in range(i - period + 1, i + 1):
        previous = bars[j - 1].close if j else bars[j].open
        values.append(max(bars[j].high - bars[j].low,
                          abs(bars[j].high - previous), abs(bars[j].low - previous)))
    return mean(values)


def _sma(values: list[float], end: int, period: int) -> float | None:
    if end + 1 < period:
        return None
    return mean(values[end - period + 1:end + 1])


def _ema(values: list[float], period: int) -> list[float | None]:
    output: list[float | None] = [None] * len(values)
    if len(values) < period:
        return output
    value = mean(values[:period])
    output[period - 1] = value
    alpha = 2 / (period + 1)
    for i in range(period, len(values)):
        value = alpha * values[i] + (1 - alpha) * value
        output[i] = value
    return output


def _rsi(values: list[float], period: int) -> list[float | None]:
    output: list[float | None] = [None] * len(values)
    if len(values) <= period:
        return output
    changes = [values[i] - values[i - 1] for i in range(1, len(values))]
    gain = mean(max(x, 0) for x in changes[:period])
    loss = mean(max(-x, 0) for x in changes[:period])
    output[period] = 100.0 if loss == 0 else 100 - 100 / (1 + gain / loss)
    for i in range(period + 1, len(values)):
        change = changes[i - 1]
        gain = (gain * (period - 1) + max(change, 0)) / period
        loss = (loss * (period - 1) + max(-change, 0)) / period
        output[i] = 100.0 if loss == 0 else 100 - 100 / (1 + gain / loss)
    return output


def _indicators(bars: list[Bar], volumes: list[float] | None = None) -> dict[str, list[float | None]]:
    close = [b.close for b in bars]
    high, low = [b.high for b in bars], [b.low for b in bars]
    ema20, ema100 = _ema(close, 20), _ema(close, 100)
    rsi4, rsi14 = _rsi(close, 4), _rsi(close, 14)
    atr10 = [_atr(bars, i, 10) for i in range(len(bars))]
    atr14 = [_atr(bars, i, 14) for i in range(len(bars))]
    upper_st, lower_st, st = [None] * len(bars), [None] * len(bars), [None] * len(bars)
    for i in range(len(bars)):
        value = atr10[i]
        if value is None:
            continue
        midpoint = (high[i] + low[i]) / 2
        basic_upper, basic_lower = midpoint + 3 * value, midpoint - 3 * value
        upper_st[i] = basic_upper if i == 0 or upper_st[i - 1] is None or basic_upper < upper_st[i - 1] or close[i - 1] > upper_st[i - 1] else upper_st[i - 1]
        lower_st[i] = basic_lower if i == 0 or lower_st[i - 1] is None or basic_lower > lower_st[i - 1] or close[i - 1] < lower_st[i - 1] else lower_st[i - 1]
        if i == 0 or st[i - 1] is None:
            st[i] = upper_st[i]
        elif st[i - 1] == upper_st[i - 1]:
            st[i] = upper_st[i] if close[i] <= upper_st[i] else lower_st[i]
        else:
            st[i] = lower_st[i] if close[i] >= lower_st[i] else upper_st[i]
    cloud_a, cloud_b, cci, mfi, williams, adx = ([None] * len(bars) for _ in range(6))
    typical = [(high[i] + low[i] + close[i]) / 3 for i in range(len(bars))]
    true_ranges, plus_moves, minus_moves = [], [], []
    for i, bar in enumerate(bars):
        up = high[i] - high[i-1] if i else 0.0
        down = low[i-1] - low[i] if i else 0.0
        previous = close[i-1] if i else bar.open
        true_ranges.append(max(high[i]-low[i], abs(high[i]-previous), abs(low[i]-previous)))
        plus_moves.append(up if up > down and up > 0 else 0.0)
        minus_moves.append(down if down > up and down > 0 else 0.0)
    dx = [None] * len(bars)
    if len(bars) >= 14:
        tr_sum = sum(true_ranges[:14])
        plus_sum, minus_sum = sum(plus_moves[:14]), sum(minus_moves[:14])
        for i in range(13, len(bars)):
            if i > 13:
                tr_sum = tr_sum - tr_sum / 14 + true_ranges[i]
                plus_sum = plus_sum - plus_sum / 14 + plus_moves[i]
                minus_sum = minus_sum - minus_sum / 14 + minus_moves[i]
            pdi, mdi = ((100 * plus_sum / tr_sum, 100 * minus_sum / tr_sum)
                        if tr_sum else (0.0, 0.0))
            dx[i] = 100 * abs(pdi - mdi) / (pdi + mdi) if pdi + mdi else 0.0
    if len(bars) >= 27:
        adx[26] = mean(value for value in dx[13:27] if value is not None)
        for i in range(27, len(bars)):
            adx[i] = (adx[i-1] * 13 + dx[i]) / 14
    for i in range(len(bars)):
        if i >= 77:
            known = i - 26
            tenkan = (max(high[known-8:known+1]) + min(low[known-8:known+1])) / 2
            kijun = (max(high[known-25:known+1]) + min(low[known-25:known+1])) / 2
            cloud_a[i] = (tenkan + kijun) / 2
            cloud_b[i] = (max(high[known-51:known+1]) + min(low[known-51:known+1])) / 2
        if i >= 19:
            window = typical[i-19:i+1]
            deviation = mean(abs(x - mean(window)) for x in window)
            cci[i] = (typical[i] - mean(window)) / (0.015 * deviation) if deviation else 0.0
        if i >= 13:
            highest, lowest = max(high[i-13:i+1]), min(low[i-13:i+1])
            williams[i] = -100 * (highest - close[i]) / (highest - lowest) if highest != lowest else -50.0
            if volumes is not None:
                flows = [typical[j] * volumes[j] for j in range(i-13, i+1)]
                positive = sum(flows[k] for k, j in enumerate(range(i-13, i+1)) if j == 0 or typical[j] > typical[j-1])
                negative = sum(flows[k] for k, j in enumerate(range(i-13, i+1)) if j > 0 and typical[j] < typical[j-1])
                mfi[i] = 100.0 if negative == 0 else 100 - 100 / (1 + positive / negative)
    return {"close": close, "high": high, "low": low, "ema20": ema20, "ema100": ema100,
            "rsi4": rsi4, "rsi14": rsi14, "atr10": atr10, "atr14": atr14,
            "supertrend": st, "cloud_a": cloud_a, "cloud_b": cloud_b,
            "cci": cci, "mfi": mfi, "williams": williams, "adx": adx}


def _signal(candidate: str, bars: list[Bar], ind: dict[str, list[float | None]], i: int):
    b, close = bars[i], ind["close"]
    if candidate == "E3-A" and i and ind["supertrend"][i-1] is not None and ind["supertrend"][i] is not None:
        return ("signal", 60, None, None) if close[i-1] <= ind["supertrend"][i-1] and close[i] > ind["supertrend"][i] else None
    if candidate == "E3-B" and ind["cloud_a"][i] is not None and ind["cloud_b"][i] is not None:
        tenkan = (max(ind["high"][i-8:i+1]) + min(ind["low"][i-8:i+1])) / 2
        kijun = (max(ind["high"][i-25:i+1]) + min(ind["low"][i-25:i+1])) / 2
        if close[i] > min(ind["cloud_a"][i], ind["cloud_b"][i]) and tenkan > kijun:
            return ("signal", 60, None, None)
    if candidate == "E3-C" and i >= 20 and ind["atr10"][i] is not None and ind["ema20"][i] is not None:
        bb_width = 4 * pstdev(close[i-20:i])
        kc_width = 4 * ind["atr10"][i-1] if ind["atr10"][i-1] is not None else None
        upper = ind["ema20"][i] + 2 * ind["atr10"][i]
        if kc_width is not None and bb_width < kc_width and b.close > upper:
            return ("signal", 30, b.close - 2 * ind["atr10"][i], None)
    if candidate == "E3-D" and i and ind["ema100"][i] is not None and ind["rsi4"][i-1] is not None and ind["rsi4"][i] is not None:
        if close[i] > ind["ema100"][i] and ind["rsi4"][i-1] < 15 <= ind["rsi4"][i]:
            return ("signal", 15, None, 85)
    if candidate == "E3-E" and i and ind["cci"][i-1] is not None and ind["mfi"][i-1] is not None and ind["cci"][i] is not None and ind["mfi"][i] is not None:
        if ind["cci"][i-1] < -100 and ind["mfi"][i-1] < 20 and ind["cci"][i] > -100 and ind["mfi"][i] > 20:
            return ("signal", 10, None, 100)
    if candidate == "E3-F" and i >= 200 and ind["williams"][i-1] is not None and ind["williams"][i] is not None:
        if close[i] > _sma(close, i, 200) and ind["williams"][i-1] <= -80 and ind["williams"][i] > -60:
            return ("signal", 20, None, -20)
    if candidate == "E3-G" and i >= 20 and ind["atr14"][i] is not None:
        prior_rsi_values, recent_rsi_values = ind["rsi14"][i-20:i-10], ind["rsi14"][i-10:i]
        if any(value is None for value in prior_rsi_values + recent_rsi_values):
            return None
        prior_low, recent_low = min(ind["low"][i-20:i-10]), min(ind["low"][i-10:i])
        prior_rsi, recent_rsi = min(prior_rsi_values), min(recent_rsi_values)
        if recent_low < prior_low and recent_rsi > prior_rsi and b.close > max(ind["high"][i-20:i]):
            return ("signal", 15, b.close - 1.5 * ind["atr14"][i], None)
    if candidate == "E3-H" and i >= 28 and ind["adx"][i] is not None and ind["ema20"][i] is not None:
        if ind["adx"][i] > 30 and b.close > ind["ema20"][i] and b.low <= ind["ema20"][i] <= b.close:
            return ("breakout", 10, b.high, None)
    if candidate == "E3-I" and i >= 3 and _day(b).weekday() == 0:
        if close[i-1] < close[i-2] and close[i-2] < close[i-3]:
            return ("signal", 5, None, None)
    if candidate == "E3-J" and _day(b).month == 11:
        day = _day(b)
        if i == 0 or _day(bars[i-1]).month != 11:
            return ("season_entry", 0, None, None)
    return None


def _cost_bps(market: str) -> float:
    costs = preregistered_costs(market)
    return 2 * (costs.commission_bps_per_side + costs.slippage_bps_per_side) + costs.sell_tax_bps


def simulate_e3(candidate: str, bars: list[Bar], market: str,
                volumes: list[float] | None = None) -> tuple[list[Trade], int]:
    if candidate not in NEW_CANDIDATES:
        raise ValueError(f"unknown E3 candidate: {candidate}")
    if market not in MARKETS:
        raise ValueError(f"unsupported market: {market}")
    if len(bars) < 2:
        return [], 0
    if volumes is not None and len(volumes) != len(bars):
        raise ValueError("volume count must match daily bars")
    if candidate == "E3-E" and volumes is None:
        raise ValueError("E3-E requires actual daily volume for MFI")
    ind, trades, i, busy_until, gaps = _indicators(bars, volumes), [], 0, -1, 0
    cost = _cost_bps(market)
    while i < len(bars) - 1:
        if i <= busy_until:
            i += 1
            continue
        setup = _signal(candidate, bars, ind, i)
        if setup is None:
            i += 1
            continue
        kind, horizon, stop, exit_level = setup
        if kind == "breakout":
            if i + 2 >= len(bars) or bars[i+1].high <= stop:
                i += 1
                continue
            signal_i, entry_i = i + 1, i + 2
            risk_at_signal = ind["atr14"][signal_i]
            if risk_at_signal is None:
                i += 1
                continue
            stop = bars[entry_i].open - 1.5 * risk_at_signal
        else:
            signal_i, entry_i = i, i + 1
        entry = bars[entry_i].open
        if not pd.notna(entry) or entry <= 0:
            i += 1
            continue
        if stop is not None and kind != "breakout":
            stop = entry - (bars[signal_i].close - stop)
        if candidate == "E3-J":
            year = _day(bars[signal_i]).year
            exit_signal = next((j for j in range(entry_i, len(bars))
                                if _day(bars[j]).year == year + 1 and _day(bars[j]).month == 5
                                and _day(bars[j]).day <= 7), None)
            if exit_signal is None or exit_signal + 1 >= len(bars):
                gaps += 1
                i += 1
                continue
            exit_i, exit_price, reason = exit_signal + 1, bars[exit_signal + 1].open, "season"
        else:
            limit = min(len(bars) - 1, entry_i + horizon - 1)
            exit_i, exit_price, reason = None, None, "time"
            censored = False
            for j in range(entry_i, limit + 1):
                b = bars[j]
                if stop is not None and b.low <= stop:
                    exit_i, exit_price, reason = j, min(b.open, stop), "stop"
                    break
                if candidate == "E3-I" and j > entry_i and b.close > bars[j-1].high:
                    if j + 1 < len(bars):
                        exit_i, exit_price, reason = j + 1, bars[j+1].open, "signal"
                    else:
                        censored = True
                    break
                if exit_level is not None:
                    value = ind["rsi4"][j] if candidate == "E3-D" else ind["cci"][j] if candidate == "E3-E" else ind["williams"][j]
                    if value is not None and ((candidate == "E3-D" and value > exit_level) or
                       (candidate == "E3-E" and value > exit_level) or
                       (candidate == "E3-F" and value > exit_level)):
                        if j + 1 < len(bars):
                            exit_i, exit_price, reason = j + 1, bars[j+1].open, "signal"
                        else:
                            censored = True
                        break
                if candidate in ("E3-A", "E3-B"):
                    below = (ind["supertrend"][j] is not None and b.close < ind["supertrend"][j]) if candidate == "E3-A" else (ind["cloud_a"][j] is not None and b.close < min(ind["cloud_a"][j], ind["cloud_b"][j]))
                    if below and j + 1 < len(bars):
                        exit_i, exit_price, reason = j + 1, bars[j+1].open, "signal"
                        break
                    if below:
                        censored = True
                        break
            if exit_i is None:
                time_exit = entry_i + horizon
                if censored or time_exit >= len(bars):
                    gaps += 1
                    i += 1
                    continue
                exit_i, exit_price = time_exit, bars[time_exit].open
            if exit_i >= len(bars) or exit_price is None:
                gaps += 1
                i += 1
                continue
        gross = exit_price / entry - 1
        net = gross - cost / 10_000
        trades.append(Trade(candidate, signal_i, entry_i, exit_i, entry, exit_price,
                            reason, gross, cost, net))
        busy_until, i = exit_i, exit_i + 1
    return trades, gaps


def _metrics(trades: list[Trade]) -> dict[str, object]:
    values = [t.net_return for t in trades]
    wins = sum(x > 0 for x in values)
    profit, loss = sum(x for x in values if x > 0), -sum(x for x in values if x < 0)
    return {"trades": len(values), "win_rate_pct": 100 * wins / len(values) if values else None,
            "profit_factor": profit / loss if loss else None,
            "expectancy_net_bps": 10_000 * sum(values) / len(values) if values else None}


def _e3j_portfolio_metrics(symbol_bars: dict[str, list[Bar]],
                           memberships: dict[str, Membership]) -> dict[str, object]:
    """Build equal-weight daily close marks for PIT-safe November cohorts."""
    dated_bars = {symbol: {_day(bar): bar for bar in bars}
                  for symbol, bars in symbol_bars.items()}
    market_days = sorted({day for bars in dated_bars.values() for day in bars})
    if not market_days:
        return {"symbols": 0, "trades": 0, "max_drawdown": None, "sharpe": None,
                "delisting_gap": 0}

    returns, included_symbols, trades, gaps = [], set(), 0, 0
    seasons = [(day, i) for i, day in enumerate(market_days)
               if day.month == 11 and (i == 0 or market_days[i - 1].month != 11)]
    for signal_day, signal_pos in seasons:
        entry_pos = signal_pos + 1
        may_pos = next((i for i in range(signal_pos + 1, len(market_days))
                        if market_days[i].year == signal_day.year + 1
                        and market_days[i].month == 5), None)
        exit_pos = may_pos + 1 if may_pos is not None else None
        if entry_pos >= len(market_days) or exit_pos is None or exit_pos >= len(market_days):
            continue
        entry_day, exit_day = market_days[entry_pos], market_days[exit_pos]
        cohort = {}
        for symbol, bars in dated_bars.items():
            member = memberships.get(symbol)
            if member is None or not member.alive(signal_day):
                continue
            entry_bar, exit_bar = bars.get(entry_day), bars.get(exit_day)
            if entry_bar is None:
                continue
            if not member.alive(exit_day) or exit_bar is None:
                gaps += 1
                continue
            cohort[symbol] = (entry_bar.open, entry_bar.close)
        if not cohort:
            continue
        included_symbols.update(cohort)
        trades += len(cohort)
        marks = {symbol: close for symbol, (_, close) in cohort.items()}
        previous_value = 1.0
        for day in market_days[entry_pos:may_pos + 1]:
            for symbol in cohort:
                bar = dated_bars[symbol].get(day)
                if bar is not None:
                    marks[symbol] = bar.close
            value = mean(marks[symbol] / cohort[symbol][0] for symbol in cohort)
            daily_return = value / previous_value - 1
            returns.append(daily_return)
            previous_value = value

    if not returns:
        return {"symbols": len(included_symbols), "trades": trades,
                "max_drawdown": None, "sharpe": None, "delisting_gap": gaps}
    curve = []
    current = 1.0
    for daily_return in returns:
        current *= 1 + daily_return
        curve.append(current)
    peak = 1.0
    drawdowns = []
    for value in curve:
        peak = max(peak, value)
        drawdowns.append(value / peak - 1)
    deviation = stdev(returns) if len(returns) >= 2 else 0.0
    sharpe = math.sqrt(252) * mean(returns) / deviation if deviation else None
    return {"symbols": len(included_symbols), "trades": trades,
            "max_drawdown": min(drawdowns), "sharpe": sharpe,
            "delisting_gap": gaps}


def _append_trials(rows: list[dict[str, object]], trials_path: Path) -> None:
    if trials_path.exists() and trials_path.stat().st_size:
        with trials_path.open(newline="", encoding="utf-8") as handle:
            if next(csv.reader(handle)) != TRIAL_FIELDS:
                raise ValueError("TRAIN_TRIALS.csv schema mismatch")
    digest = hashlib.sha256()
    for name in ("search_equities_r5.py", "search_equities_r4.py", "search_equities_r3.py",
                 "data_access.py", "equities.py", "resource_guard.py"):
        digest.update(name.encode() + b"\0" + (ROOT / name).read_bytes())
    code_sha, prereg_sha = digest.hexdigest(), hashlib.sha256((ROOT / "PREREG.md").read_bytes()).hexdigest()
    now = datetime.now(timezone.utc).isoformat()
    with trials_path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=TRIAL_FIELDS)
        if handle.tell() == 0:
            writer.writeheader()
        for rank, row in enumerate(rows, 1):
            writer.writerow({"trial_id": f"R5-{row['market']}-{row['strategy']}", "round": "R5",
                "market_group": row["market"], "utc_timestamp": now,
                "definition": json.dumps(row["parameters"], sort_keys=True, separators=(",", ":")),
                "parameter_grid_hash": prereg_sha, "code_sha256": code_sha,
                "train_period": "<=2018-10-26T23:59:00Z",
                "metric": json.dumps(row, sort_keys=True, separators=(",", ":")), "rank": rank,
                "notes": "TRAIN only; not G; PIT gated; no TEST access"})


def run(universe_path: Path, membership_path: Path, split_file: Path,
        survivors_only: bool = False, trials_path: Path | None = None) -> list[dict[str, object]]:
    from search_equities_r3 import _load_train
    memberships = load_membership(membership_path)
    with universe_path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    if not rows or not {"market", "symbol", "daily_path"}.issubset(rows[0]):
        raise ValueError("universe CSV requires market,symbol,daily_path")
    if any((r["market"], r["symbol"]) not in memberships for r in rows):
        raise ValueError("universe contains symbol without PIT membership record")
    if any(r["market"] not in MARKETS for r in rows):
        raise ValueError("universe market must be US or KR")
    per_market: dict[tuple[str, str], list[Trade]] = {}
    e3j_bars: dict[str, dict[str, list[Bar]]] = {}
    all_results, survivor_trades = [], {}
    symbol_accounting: dict[str, dict[str, dict[str, object]]] = {}
    for row in rows:
        market, symbol = row["market"], row["symbol"]
        member = memberships[(market, symbol)]
        quality_stats: dict[str, int] = {"invalid_ohlc": 0, "halt_bars": 0}
        try:
            frame = _load_train(Path(row["daily_path"]).expanduser(), symbol, market, split_file)
            bars = _daily_bars(frame, member, quality_stats)
            symbol_accounting.setdefault(market, {})[symbol] = {"status": "valid", **quality_stats}
            e3j_bars.setdefault(market, {})[symbol] = bars
            filtered_frame, _ = filter_equity_bars(frame, symbol)
            volumes = _daily_volumes(filtered_frame, member)
            for candidate in NEW_CANDIDATES:
                trades, gaps = simulate_e3(candidate, bars, market, volumes if candidate == "E3-E" else None)
                accepted, pit_gaps = survivorship_safe_trades(trades, bars, member)
                per_market.setdefault((market, candidate), []).extend(accepted)
                all_results.append({"market": market, "symbol": symbol, "strategy": candidate,
                                    "parameters": {"candidate": candidate}, **_metrics(accepted),
                                    "delisting_gap": pit_gaps, "uncompleted": gaps,
                                    "survivorship_biased": False,
                                    "status": "TRAIN_ONLY_NOT_G"})
                if survivors_only and bars and member.alive(_day(bars[-1])):
                    survivor_trades.setdefault((market, candidate), []).extend(trades)
        except MemoryError:
            raise
        except SymbolQualityError as exc:
            symbol_accounting.setdefault(market, {})[symbol] = {
                "status": "quality_excluded", **quality_stats, "detail": str(exc)}
            continue
        except Exception as exc:
            print(f"{market},{symbol}: {type(exc).__name__}: {exc}", file=sys.stderr)
            symbol_accounting.setdefault(market, {})[symbol] = {
                "status": "data_error", **quality_stats,
                "detail": f"{type(exc).__name__}: {exc}"}
            continue

    trial_rows = []
    for market, candidate in sorted(per_market):
        subset = per_market[(market, candidate)]
        trial_rows.append({"market": market, "strategy": candidate,
                           "parameters": {"candidate": candidate}, "symbols": len([r for r in rows if r["market"] == market]),
                           "invalid_ohlc_rows_filtered": sum(int(a["invalid_ohlc"]) for a in symbol_accounting.get(market, {}).values()),
                           "halt_bars_filtered": sum(int(a["halt_bars"]) for a in symbol_accounting.get(market, {}).values()),
                           "symbols_quality_excluded": sum(a["status"] == "quality_excluded" for a in symbol_accounting.get(market, {}).values()),
                           "symbols_data_error": sum(a["status"] == "data_error" for a in symbol_accounting.get(market, {}).values()),
                           "symbol_accounting": symbol_accounting.get(market, {}),
                           **_metrics(subset), "survivorship_biased": False, "status": "TRAIN_ONLY_NOT_G"})
    for market in MARKETS:
        if any(row["market"] == market for row in rows):
            all_results.append({"market": market, "strategy": "E3-J-portfolio",
                                "parameters": {"candidate": "E3-J", "weighting": "equal"},
                                **_e3j_portfolio_metrics(
                                    e3j_bars.get(market, {}),
                                    {symbol: memberships[(market, symbol)]
                                     for mkt, symbol in memberships if mkt == market}),
                                "survivorship_biased": False,
                                "status": "TRAIN_ONLY_NOT_G"})
    if trials_path is not None and trial_rows:
        _append_trials(trial_rows, trials_path)
    if survivors_only:
        for (market, candidate), trades in survivor_trades.items():
            all_results.append({"market": market, "strategy": candidate,
                "parameters": {"candidate": candidate, "view": "survivors_only"}, **_metrics(trades),
                "survivorship_biased": True, "status": "TRAIN_ONLY_NOT_G"})
    return all_results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--universe", type=Path, required=True)
    parser.add_argument("--membership", type=Path, required=True)
    parser.add_argument("--split-file", type=Path, required=True)
    parser.add_argument("--trials", type=Path, default=ROOT / "TRAIN_TRIALS.csv")
    parser.add_argument("--survivors-only", action="store_true",
                        help="also report end-date survivors-only figures, explicitly biased")
    args = parser.parse_args()
    if os.getpriority(os.PRIO_PROCESS, 0) < 10:
        raise RuntimeError("R5 requires an effective nice value of at least 10")
    if args.membership.resolve() == args.universe.resolve():
        raise ValueError("membership must be a separate PIT source file")
    with heavy_task("R5"):
        results = run(args.universe, args.membership, args.split_file, args.survivors_only, args.trials)
    print(json.dumps({"rows": len(results), "train_cutoff_ms": EQUITY_COMMON_SPLIT_MS,
                      "new_candidates_registered": list(NEW_CANDIDATES),
                      "result_scope": "E3 A-J; train only", "results": results},
                     sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
