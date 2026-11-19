"""Pre-registered, development-only cross-sectional mean-reversion study.

Reads candle data in SQLite read-only mode. It never places orders and never
opens the preregistered validation window.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sqlite3
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

START_MS = 1784246400000  # 2026-07-17T00:00:00Z
DEV_CUTOFF_MS = 1791504000000  # 2026-10-09T00:00:00Z, exclusive
MINUTE_MS = 60_000
HOUR_MS = 60 * MINUTE_MS
HORIZON_MINUTES = 12 * 60
FEE_PER_SIDE = 0.0005
BASE_SLIPPAGE = 0.0004
STRESS_SLIPPAGE = 0.0008
TOP_BOTTOM_N = 4
MAX_POSITIONS = 8
SIGNAL_CUTOFF_MS = DEV_CUTOFF_MS - HORIZON_MINUTES * MINUTE_MS


@dataclass(frozen=True)
class Signal:
    time_ms: int
    symbol: str
    side: int  # +1 long, -1 short
    relative_return: float
    atr: float
    strategy: str


def load_universe(path: Path) -> list[str]:
    symbols = json.loads(path.read_text())[:20]
    if len(symbols) != 20 or len(set(symbols)) != 20:
        raise ValueError("universe must contain at least 20 unique symbols")
    return symbols


def load_market(db_path: Path, symbols: list[str]) -> tuple[dict[str, pd.DataFrame], dict[str, pd.DataFrame], str]:
    """Load the fixed universe and build only complete UTC 60-minute bars."""
    uri = f"file:{db_path.resolve()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    minutes: dict[str, pd.DataFrame] = {}
    hours: dict[str, pd.DataFrame] = {}
    digest = hashlib.sha256()
    common_start: int | None = None
    try:
        for symbol in symbols:
            frame = pd.read_sql_query(
                "SELECT t_open_ms,o,h,l,c,quote_v FROM candles WHERE symbol=? AND t_open_ms<? "
                "ORDER BY t_open_ms",
                connection,
                params=(symbol, DEV_CUTOFF_MS),
            )
            if frame.empty:
                raise ValueError(f"no candle data for {symbol}")
            times = frame.t_open_ms.to_numpy(dtype=np.int64)
            if len(times) > 1 and not np.all(np.diff(times) == MINUTE_MS):
                raise ValueError(f"minute data has a gap or off-grid row for {symbol}")
            if (frame[["o", "h", "l", "c", "quote_v"]].isna().any().any()
                    or (frame[["o", "h", "l", "c"]] <= 0).any().any()
                    or (frame.quote_v < 0).any()):
                raise ValueError(f"invalid price or volume for {symbol}")
            if common_start is None:
                common_start = int(times[0])
            elif int(times[0]) != common_start:
                raise ValueError(f"minute series do not share a common start for {symbol}")
            minutes[symbol] = frame
            digest.update(symbol.encode("utf-8") + b"\0")
            for row in frame.itertuples(index=False, name=None):
                digest.update(struct.pack("<q5d", int(row[0]), *map(float, row[1:])))

            frame = frame.copy()
            frame["bucket"] = (frame.t_open_ms // HOUR_MS) * HOUR_MS
            grouped = frame.groupby("bucket", sort=True).agg(
                o=("o", "first"), h=("h", "max"), l=("l", "min"),
                c=("c", "last"), quote_v=("quote_v", "sum"),
                count=("t_open_ms", "count"),
                first_ms=("t_open_ms", "first"), last_ms=("t_open_ms", "last"),
            )
            grouped = grouped[(grouped["count"] == 60)
                              & (grouped["first_ms"] == grouped.index)
                              & (grouped["last_ms"] == grouped.index + 59 * MINUTE_MS)]
            grouped = grouped.drop(columns=["count", "first_ms", "last_ms"])
            previous_close = grouped.c.shift(1)
            tr = pd.concat(
                [grouped.h - grouped.l, (grouped.h - previous_close).abs(),
                 (grouped.l - previous_close).abs()], axis=1,
            ).max(axis=1)
            grouped["atr14"] = tr.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
            grouped["ret24"] = np.log(grouped.c / grouped.c.shift(24))
            grouped["close_ms"] = grouped.index + HOUR_MS
            hours[symbol] = grouped
    finally:
        connection.close()
    return minutes, hours, digest.hexdigest()


def build_signals(hours: dict[str, pd.DataFrame], strategy: str) -> list[Signal]:
    """Build fixed-rule signals using only complete bars at or before each anchor."""
    returns = pd.concat({s: f.ret24 for s, f in hours.items()}, axis=1).sort_index()
    atrs = pd.concat({s: f.atr14 for s, f in hours.items()}, axis=1).reindex(returns.index)
    close_ms = returns.index + HOUR_MS
    eligible = (close_ms >= START_MS) & (close_ms < SIGNAL_CUTOFF_MS)
    signals: list[Signal] = []
    rng = np.random.default_rng(20261120)
    for i, anchor in enumerate(returns.index[eligible]):
        row = returns.loc[anchor]
        atr_row = atrs.loc[anchor]
        if row.isna().any() or atr_row.isna().any() or not np.isfinite(row.to_numpy()).all():
            continue
        median = float(row.median())
        residual = row - median
        ranked = sorted(residual.items(), key=lambda item: (float(item[1]), item[0]))
        if strategy == "mean_reversion":
            long_names = [name for name, _ in ranked[:TOP_BOTTOM_N]]
            short_names = [name for name, _ in ranked[-TOP_BOTTOM_N:]]
        elif strategy == "cross_sectional_momentum":
            long_names = [name for name, _ in ranked[-TOP_BOTTOM_N:]]
            short_names = [name for name, _ in ranked[:TOP_BOTTOM_N]]
        elif strategy == "random":
            shuffled = list(returns.columns)
            rng.shuffle(shuffled)
            long_names, short_names = shuffled[:TOP_BOTTOM_N], shuffled[TOP_BOTTOM_N:2 * TOP_BOTTOM_N]
        else:
            raise ValueError(f"unknown strategy: {strategy}")
        time_ms = int(anchor + HOUR_MS)
        for name in long_names:
            signals.append(Signal(time_ms, name, 1, float(residual[name]), float(atr_row[name]), strategy))
        for name in short_names:
            signals.append(Signal(time_ms, name, -1, float(residual[name]), float(atr_row[name]), strategy))
    return sorted(signals, key=lambda signal: (signal.time_ms, signal.symbol, -signal.side))


def _entry_fill(open_price: float, side: int, slippage: float) -> float:
    return open_price * (1 + side * slippage)


def _exit_fill(price: float, side: int, slippage: float) -> float:
    return price * (1 - side * slippage)


def resolve_signal(signal: Signal, frame: pd.DataFrame, fee: float, slippage: float) -> dict[str, Any]:
    """Resolve a single signal on contiguous 1m bars, with conservative ties."""
    times = frame.t_open_ms.to_numpy(dtype=np.int64)
    start = int(np.searchsorted(times, signal.time_ms))
    if start >= len(times) or times[start] != signal.time_ms:
        return {"status": "unscorable", "reason": "missing_entry_minute"}
    stop_index = start + HORIZON_MINUTES
    if stop_index > len(times) or not np.array_equal(
        times[start:stop_index], signal.time_ms + np.arange(HORIZON_MINUTES) * MINUTE_MS
    ):
        return {"status": "unscorable", "reason": "incomplete_execution_path"}
    opens = frame.o.to_numpy(dtype=float)
    highs = frame.h.to_numpy(dtype=float)
    lows = frame.l.to_numpy(dtype=float)
    closes = frame.c.to_numpy(dtype=float)
    entry = _entry_fill(float(opens[start]), signal.side, slippage)
    target = entry + signal.side * 0.5 * signal.atr
    stop = entry - signal.side * 2.0 * signal.atr
    reason = "timeout"
    exit_reference = float(closes[stop_index - 1])
    exit_time = int(times[stop_index - 1] + MINUTE_MS)
    for i in range(start, stop_index):
        o, h, l = float(opens[i]), float(highs[i]), float(lows[i])
        stop_gap = o <= stop if signal.side == 1 else o >= stop
        stop_hit = stop_gap or (l <= stop if signal.side == 1 else h >= stop)
        target_hit = h >= target if signal.side == 1 else l <= target
        if stop_hit or target_hit:
            reason = "stop" if stop_hit else "target"
            exit_reference = o if stop_gap else (stop if stop_hit else target)
            exit_time = int(times[i])
            break
    exit_price = _exit_fill(exit_reference, signal.side, slippage)
    price_return = signal.side * (exit_price / entry - 1)
    net_return = price_return - fee * (1 + exit_price / entry)
    return {
        "status": "scorable", "reason": reason, "entry_ms": signal.time_ms,
        "exit_ms": exit_time, "entry": entry, "exit": exit_price,
        "gross_after_slippage": price_return, "net_return": net_return,
        "target_first": reason == "target", "side": signal.side,
        "symbol": signal.symbol,
    }


def score_signals(
    signals: list[Signal], minutes: dict[str, pd.DataFrame], slippage: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    resolved = [resolve_signal(signal, minutes[signal.symbol], FEE_PER_SIDE, slippage) for signal in signals]
    scorable = [trade for trade in resolved if trade["status"] == "scorable"]
    nonoverlap: list[dict[str, Any]] = []
    next_allowed: dict[str, int] = {}
    for signal, trade in zip(signals, resolved):
        if trade["status"] != "scorable":
            continue
        if signal.time_ms >= next_allowed.get(signal.symbol, -1):
            nonoverlap.append(trade)
            next_allowed[signal.symbol] = signal.time_ms + HORIZON_MINUTES * MINUTE_MS
    wins = sum(t["target_first"] for t in scorable)
    nwins = sum(t["target_first"] for t in nonoverlap)
    anchor_count = len({signal.time_ms for signal in signals})
    eligible_symbol_hours = anchor_count * 20
    by_symbol: dict[str, dict[str, int]] = {}
    by_side: dict[str, dict[str, float]] = {}
    for trade in scorable:
        stats = by_symbol.setdefault(trade["symbol"], {"n": 0, "target_first": 0})
        stats["n"] += 1
        stats["target_first"] += int(trade["target_first"])
        side_name = "long" if trade["side"] == 1 else "short"
        side_stats = by_side.setdefault(side_name, {"n": 0, "target_first": 0, "net_sum": 0.0})
        side_stats["n"] += 1
        side_stats["target_first"] += int(trade["target_first"])
        side_stats["net_sum"] += float(trade["net_return"])
    report = {
        "issued": len(signals), "scorable": len(scorable),
        "unscorable": len(signals) - len(scorable),
        "actionable_signal_coverage": len(signals) / eligible_symbol_hours if eligible_symbol_hours else 0.0,
        "scorable_fraction": len(scorable) / len(signals) if signals else 0.0,
        "eligible_symbol_hours": eligible_symbol_hours,
        "m2_all": wins / len(scorable) if scorable else None,
        "wilson95_all": _wilson(wins, len(scorable)),
        "m2_nonoverlap": nwins / len(nonoverlap) if nonoverlap else None,
        "wilson95_nonoverlap": _wilson(nwins, len(nonoverlap)),
        "n_nonoverlap": len(nonoverlap),
        "mean_net_trade_return": float(np.mean([t["net_return"] for t in scorable])) if scorable else None,
        "per_symbol": {
            symbol: {"n": stats["n"], "m2": stats["target_first"] / stats["n"]}
            for symbol, stats in sorted(by_symbol.items())
        },
        "per_side": {
            side: {"n": stats["n"], "m2": stats["target_first"] / stats["n"],
                   "mean_net_trade_return": stats["net_sum"] / stats["n"]}
            for side, stats in sorted(by_side.items())
        },
    }
    return resolved, report


def simulate_portfolio(
    signals: list[Signal], minutes: dict[str, pd.DataFrame], fee: float, slippage: float,
) -> dict[str, Any]:
    """Chronological 1m NAV replay, max eight equal-risk-notional slots, no leverage."""
    schedules: dict[int, list[Signal]] = {}
    for signal in signals:
        schedules.setdefault(signal.time_ms, []).append(signal)
    for batch in schedules.values():
        batch.sort(key=lambda item: (-abs(item.relative_return), item.symbol))
    minute_arrays = {
        symbol: tuple(frame[column].to_numpy(dtype=np.int64 if column == "t_open_ms" else float)
                      for column in ("t_open_ms", "o", "h", "l", "c"))
        for symbol, frame in minutes.items()
    }
    base_times = next(iter(minute_arrays.values()))[0]
    start = int(np.searchsorted(base_times, START_MS))
    end_ms = DEV_CUTOFF_MS
    end = int(np.searchsorted(base_times, end_ms))
    cash = 1.0
    positions: dict[str, dict[str, Any]] = {}
    peak = 1.0
    max_drawdown = 0.0
    max_gross_ratio = 0.0
    nav_hourly: list[float] = []
    hourly_times: list[int] = []
    completed: list[dict[str, Any]] = []

    def mark_position(position: dict[str, Any], price: float) -> float:
        return position["side"] * position["notional"] * (price / position["entry"] - 1)

    for minute_index in range(start, end):
        now = int(base_times[minute_index])
        bars: dict[str, tuple[float, float, float, float]] = {}
        for symbol, arrays in minute_arrays.items():
            times, opens, highs, lows, closes = arrays
            if minute_index < len(times) and int(times[minute_index]) == now:
                bars[symbol] = (
                    float(opens[minute_index]), float(highs[minute_index]),
                    float(lows[minute_index]), float(closes[minute_index]),
                )

        # Close positions that gap through barriers at this minute's open first.
        for symbol in list(positions):
            bar = bars.get(symbol)
            if bar is None:
                continue
            position = positions[symbol]
            o, h, l, _ = bar
            stop_gap = o <= position["stop"] if position["side"] == 1 else o >= position["stop"]
            target_gap = o >= position["target"] if position["side"] == 1 else o <= position["target"]
            if stop_gap or target_gap:
                reference = o if stop_gap else position["target"]
                exit_at = _exit_fill(reference, position["side"], slippage)
                cash_holder = {"cash": cash}
                reason = "stop" if stop_gap else "target"
                _close_position(positions, cash_holder, symbol, exit_at, now, fee, completed, reason)
                cash = cash_holder["cash"]

        # New entries are based on the opening NAV and cannot exceed 1x gross exposure.
        nav_open = cash + sum(
            mark_position(pos, bars[pos["symbol"]][0])
            for pos in positions.values() if pos["symbol"] in bars
        )
        gross = sum(
            pos["notional"] * bars[pos["symbol"]][0] / pos["entry"]
            for pos in positions.values() if pos["symbol"] in bars
        )
        for signal in schedules.get(now, []):
            same_side_count = sum(pos["side"] == signal.side for pos in positions.values())
            if (signal.symbol in positions or signal.symbol not in bars
                    or len(positions) >= MAX_POSITIONS or same_side_count >= TOP_BOTTOM_N):
                continue
            allocation = max(nav_open, 0.0) / MAX_POSITIONS
            available_after_entry_fee = max(nav_open - gross, 0.0) / (1 + fee)
            notional = min(allocation / (1 + fee), available_after_entry_fee)
            if notional <= 0:
                continue
            open_price = bars[signal.symbol][0]
            entry = _entry_fill(open_price, signal.side, slippage)
            stop = entry - signal.side * 2.0 * signal.atr
            target = entry + signal.side * 0.5 * signal.atr
            cash -= fee * notional
            positions[signal.symbol] = {
                "symbol": signal.symbol, "side": signal.side, "entry": entry,
                "notional": notional, "stop": stop, "target": target,
                "entry_ms": now, "timeout_ms": now + HORIZON_MINUTES * MINUTE_MS,
                "entry_fee": fee * notional,
            }
            gross += notional

        # Resolve intraminute touches conservatively, then time exits at the 12h close.
        for symbol in list(positions):
            bar = bars.get(symbol)
            if bar is None:
                continue
            position = positions[symbol]
            o, h, l, close = bar
            stop_gap = o <= position["stop"] if position["side"] == 1 else o >= position["stop"]
            stop_hit = stop_gap or (l <= position["stop"] if position["side"] == 1 else h >= position["stop"])
            target_hit = h >= position["target"] if position["side"] == 1 else l <= position["target"]
            if stop_hit or target_hit:
                reference = o if stop_gap else (position["stop"] if stop_hit else position["target"])
                exit_at = _exit_fill(reference, position["side"], slippage)
                cash_holder = {"cash": cash}
                reason = "stop" if stop_hit else "target"
                _close_position(positions, cash_holder, symbol, exit_at, now, fee, completed, reason)
                cash = cash_holder["cash"]
            elif now + MINUTE_MS >= position["timeout_ms"]:
                exit_at = _exit_fill(close, position["side"], slippage)
                cash_holder = {"cash": cash}
                _close_position(positions, cash_holder, symbol, exit_at, now + MINUTE_MS, fee, completed, "timeout")
                cash = cash_holder["cash"]

        nav = cash + sum(
            mark_position(pos, bars[pos["symbol"]][3])
            for pos in positions.values() if pos["symbol"] in bars
        )
        if nav <= 0:
            nav = 0.0
        peak = max(peak, nav)
        max_drawdown = max(max_drawdown, 1 - nav / peak if peak else 0.0)
        gross_now = sum(
            pos["notional"] * bars[pos["symbol"]][3] / pos["entry"]
            for pos in positions.values() if pos["symbol"] in bars
        )
        max_gross_ratio = max(max_gross_ratio, gross_now / nav if nav else math.inf)
        if now % HOUR_MS == 0:
            nav_hourly.append(nav)
            hourly_times.append(now)

    if positions:
        raise AssertionError("purged development boundary left open portfolio positions")
    final_nav = cash
    elapsed_days = max((DEV_CUTOFF_MS - START_MS) / (24 * HOUR_MS), 1e-9)
    cagr = final_nav ** (365.25 / elapsed_days) - 1 if final_nav > 0 else -1.0
    hourly_returns = np.diff(nav_hourly) / np.asarray(nav_hourly[:-1]) if len(nav_hourly) > 1 else np.array([])
    sharpe = (
        float(np.mean(hourly_returns) / np.std(hourly_returns, ddof=1) * math.sqrt(24 * 365))
        if len(hourly_returns) > 1 and np.std(hourly_returns, ddof=1) > 0 else None
    )
    completed_returns = [trade["net_return_on_notional"] for trade in completed]
    portfolio_wins = sum(trade["target_first"] for trade in completed)
    return {
        "initial_equity": 1.0, "final_equity": final_nav,
        "total_compounded_return": final_nav - 1.0, "cagr_dev_only": cagr,
        "max_drawdown": max_drawdown, "hourly_sharpe_dev_only": sharpe,
        "completed_positions": len(completed), "open_at_end": len(positions),
        "portfolio_m2": portfolio_wins / len(completed) if completed else None,
        "portfolio_m2_wilson95": _wilson(portfolio_wins, len(completed)),
        "portfolio_trade_win_rate": (
            sum(value > 0 for value in completed_returns) / len(completed_returns)
            if completed_returns else None
        ),
        "mean_net_return_on_notional": float(np.mean(completed_returns)) if completed_returns else None,
        "profit_factor_on_notional": (
            sum(value for value in completed_returns if value > 0)
            / abs(sum(value for value in completed_returns if value < 0))
            if any(value < 0 for value in completed_returns) else None
        ),
        "max_gross_to_nav": max_gross_ratio,
        "monthly_nav_samples": _monthly_samples(hourly_times, nav_hourly),
        "completed_trade_records": completed,
    }


def _close_position(
    positions: dict[str, dict[str, Any]], cash_holder: dict[str, float], symbol: str,
    exit_price: float, exit_ms: int, fee: float, completed: list[dict[str, Any]], reason: str,
) -> None:
    position = positions.pop(symbol)
    gross_pnl = position["side"] * position["notional"] * (exit_price / position["entry"] - 1)
    exit_fee = fee * position["notional"] * exit_price / position["entry"]
    net_pnl = gross_pnl - exit_fee
    cash_holder["cash"] += net_pnl
    completed.append({
        "symbol": symbol, "side": position["side"], "entry_ms": position["entry_ms"],
        "exit_ms": exit_ms, "net_pnl": net_pnl - position["entry_fee"],
        "net_return_on_notional": (net_pnl - position["entry_fee"]) / position["notional"],
        "reason": reason, "target_first": reason == "target",
    })


def _monthly_samples(times: list[int], navs: list[float]) -> dict[str, float]:
    result: dict[str, float] = {}
    for timestamp, nav in zip(times, navs):
        month = pd.to_datetime(timestamp, unit="ms", utc=True).strftime("%Y-%m")
        result[month] = float(nav)
    return result


def _btc_buy_hold(minutes: dict[str, pd.DataFrame], fee: float, slippage: float) -> dict[str, float]:
    frame = minutes["BTCUSDT"]
    times = frame.t_open_ms.to_numpy(dtype=np.int64)
    start = int(np.searchsorted(times, START_MS))
    end = int(np.searchsorted(times, DEV_CUTOFF_MS)) - 1
    if start >= len(times) or end <= start or times[start] != START_MS:
        raise ValueError("BTC buy-and-hold baseline is missing its development endpoints")
    entry = _entry_fill(float(frame.o.iloc[start]), 1, slippage)
    exit_price = _exit_fill(float(frame.c.iloc[end]), 1, slippage)
    final_equity = (exit_price / entry) - fee * (1 + exit_price / entry)
    return {"final_equity": final_equity, "total_compounded_return": final_equity - 1.0}


def _wilson(wins: int, total: int) -> list[float | None]:
    if total == 0:
        return [None, None]
    z = 1.959963984540054
    p = wins / total
    divisor = 1 + z * z / total
    center = (p + z * z / (2 * total)) / divisor
    radius = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / divisor
    return [center - radius, center + radius]


def run(db_path: Path, universe_path: Path) -> dict[str, Any]:
    symbols = load_universe(universe_path)
    minutes, hours, data_hash = load_market(db_path, symbols)
    strategies: dict[str, Any] = {}
    for name in ("mean_reversion", "cross_sectional_momentum", "random"):
        signals = build_signals(hours, name)
        trades, m2 = score_signals(signals, minutes, BASE_SLIPPAGE)
        portfolio = simulate_portfolio(signals, minutes, FEE_PER_SIDE, BASE_SLIPPAGE)
        _, stress_m2 = score_signals(signals, minutes, STRESS_SLIPPAGE)
        stress_portfolio = simulate_portfolio(signals, minutes, FEE_PER_SIDE, STRESS_SLIPPAGE)
        delayed_signals = [Signal(s.time_ms + HOUR_MS, s.symbol, s.side, s.relative_return, s.atr, s.strategy)
                           for s in signals if s.time_ms + HOUR_MS < SIGNAL_CUTOFF_MS]
        _, delayed_m2 = score_signals(delayed_signals, minutes, BASE_SLIPPAGE)
        delayed_portfolio = simulate_portfolio(delayed_signals, minutes, FEE_PER_SIDE, BASE_SLIPPAGE)
        strategies[name] = {
            "m2_base_cost": m2,
            "portfolio_base_cost": portfolio,
            "m2_stress_slippage": stress_m2,
            "portfolio_stress_slippage": stress_portfolio,
            "m2_one_hour_extra_delay": delayed_m2,
            "portfolio_one_hour_extra_delay": delayed_portfolio,
            "signal_outcomes_base_cost": [
                {
                    **outcome,
                    "time_ms": signal.time_ms,
                    "symbol": signal.symbol,
                    "side": "long" if signal.side == 1 else "short",
                    "relative_return": signal.relative_return,
                    "atr14": signal.atr,
                }
                for signal, outcome in zip(signals, trades)
            ],
        }
    return {
        "study": "preregistered_60m_cross_sectional_relative_return_mr",
        "trial_id": "cs_mr_20261120_01",
        "trial_count_in_this_preregistered_round": 1,
        "split": "development_only",
        "start_ms": START_MS,
        "cutoff_exclusive_ms": DEV_CUTOFF_MS,
        "signal_cutoff_exclusive_ms": SIGNAL_CUTOFF_MS,
        "validation_opened": False,
        "universe": symbols,
        "input_db": str(db_path.resolve()),
        "universe_file": str(universe_path.resolve()),
        "input_db_size_bytes": db_path.stat().st_size,
        "input_db_mtime_ns": db_path.stat().st_mtime_ns,
        "data_sha256_selected_rows": data_hash,
        "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "fee_per_side": FEE_PER_SIDE,
        "base_slippage_per_side": BASE_SLIPPAGE,
        "stress_slippage_per_side": STRESS_SLIPPAGE,
        "btc_buy_and_hold_base_cost": _btc_buy_hold(minutes, FEE_PER_SIDE, BASE_SLIPPAGE),
        "btc_buy_and_hold_stress_slippage": _btc_buy_hold(minutes, FEE_PER_SIDE, STRESS_SLIPPAGE),
        "strategies": strategies,
        "interpretation": "Exploratory only: short survivor-biased sample; not an approval or future-performance claim.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--universe", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    report = run(args.db, args.universe)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"output": str(args.out), "split": report["split"], "strategies": report["strategies"]}, indent=2))


if __name__ == "__main__":
    main()
