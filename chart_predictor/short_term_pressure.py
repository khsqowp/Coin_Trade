"""Development-only 3-minute quote-volume weighted candle-pressure trial.

The score is an OHLCV proxy, not observed aggressor-side order flow. The input
database is opened read-only, and the runner never reads the validation window.
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
FEE_PER_SIDE = 0.0005
BASE_SLIPPAGE = 0.0004
STRESS_SLIPPAGE = 0.0008
TARGET_PCT = 0.0045
STOP_PCT = 0.0020
HORIZON_BARS = 8
SIDE_SLOTS = 2
MAX_POSITIONS = 8
RANDOM_SEED = 20261120


@dataclass(frozen=True)
class Signal:
    time_ms: int
    symbol: str
    side: int
    pressure: float


def pressure_scores(frame: pd.DataFrame) -> np.ndarray:
    """Return rolling three-bar quote-volume-weighted close-location scores."""
    high = frame.h.to_numpy(dtype=float)
    low = frame.l.to_numpy(dtype=float)
    close = frame.c.to_numpy(dtype=float)
    quote_volume = frame.quote_v.to_numpy(dtype=float)
    ranges = high - low
    location = np.divide(
        2.0 * close - high - low,
        ranges,
        out=np.zeros_like(ranges),
        where=ranges > 0,
    )
    weighted = location * quote_volume
    weighted_sum = pd.Series(weighted).rolling(3, min_periods=3).sum().to_numpy()
    volume_sum = pd.Series(quote_volume).rolling(3, min_periods=3).sum().to_numpy()
    return np.divide(
        weighted_sum,
        volume_sum,
        out=np.full_like(weighted_sum, np.nan, dtype=float),
        where=volume_sum > 0,
    )


def pressure_score(frame: pd.DataFrame) -> float:
    """Return a score for one 3-bar window; zero-range candles contribute zero."""
    if len(frame) != 3:
        raise ValueError("pressure score requires exactly three completed bars")
    return float(pressure_scores(frame)[-1])


def select_cross_sectional_sides(scores: dict[str, float]) -> list[tuple[str, int]]:
    """Select top-two longs and bottom-two shorts with deterministic tie breaks."""
    if len(scores) != 20 or any(not math.isfinite(value) for value in scores.values()):
        raise ValueError("exactly 20 finite symbol scores are required")
    ranked = sorted(scores.items(), key=lambda item: (item[1], item[0]))
    return ([(symbol, 1) for symbol, _ in ranked[-SIDE_SLOTS:][::-1]]
            + [(symbol, -1) for symbol, _ in ranked[:SIDE_SLOTS]])


def load_universe(path: Path) -> list[str]:
    symbols = json.loads(path.read_text())[:20]
    if len(symbols) != 20 or len(set(symbols)) != 20:
        raise ValueError("universe must contain at least 20 unique symbols")
    return symbols


def load_market(db_path: Path, symbols: list[str]) -> tuple[dict[str, pd.DataFrame], str]:
    """Read fixed-universe minute bars before the development cutoff only."""
    uri = f"file:{db_path.resolve()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    minutes: dict[str, pd.DataFrame] = {}
    digest = hashlib.sha256()
    common_times: np.ndarray | None = None
    try:
        for symbol in symbols:
            frame = pd.read_sql_query(
                "SELECT t_open_ms,o,h,l,c,quote_v FROM candles "
                "WHERE symbol=? AND t_open_ms<? ORDER BY t_open_ms",
                connection,
                params=(symbol, DEV_CUTOFF_MS),
            )
            if frame.empty:
                raise ValueError(f"no candle data for {symbol}")
            values = frame[["o", "h", "l", "c", "quote_v"]]
            if (values.isna().any().any() or (values[["o", "h", "l", "c"]] <= 0).any().any()
                    or (values.quote_v < 0).any() or (frame.h < frame.l).any()):
                raise ValueError(f"invalid OHLCV data for {symbol}")
            times = frame.t_open_ms.to_numpy(dtype=np.int64)
            if len(times) > 1 and not np.all(np.diff(times) == MINUTE_MS):
                raise ValueError(f"minute data has a gap or off-grid row for {symbol}")
            if common_times is None:
                common_times = times
            elif not np.array_equal(common_times, times):
                raise ValueError(f"minute series are not synchronized for {symbol}")
            minutes[symbol] = frame
            digest.update(symbol.encode("utf-8") + b"\0")
            for row in frame.itertuples(index=False, name=None):
                digest.update(struct.pack("<q5d", int(row[0]), *map(float, row[1:])))
    finally:
        connection.close()
    return minutes, digest.hexdigest()


def build_signals(minutes: dict[str, pd.DataFrame], strategy: str) -> list[Signal]:
    """Generate one fixed 2-long/2-short cross-section per completed minute."""
    if len(minutes) != 20:
        raise ValueError("the preregistered universe has exactly 20 symbols")
    symbols = sorted(minutes)
    times = minutes[symbols[0]].t_open_ms.to_numpy(dtype=np.int64)
    score_arrays = {symbol: pressure_scores(minutes[symbol]) for symbol in symbols}
    signal_start = int(np.searchsorted(times + MINUTE_MS, START_MS, side="left"))
    signal_stop_ms = DEV_CUTOFF_MS - HORIZON_BARS * MINUTE_MS
    signal_stop = int(np.searchsorted(times + MINUTE_MS, signal_stop_ms, side="left"))
    signals: list[Signal] = []
    random = np.random.default_rng(RANDOM_SEED)

    for index in range(max(signal_start, 2), signal_stop):
        scores = {symbol: float(score_arrays[symbol][index]) for symbol in symbols}
        if not all(math.isfinite(value) for value in scores.values()):
            continue
        if strategy == "pressure_momentum":
            selected = select_cross_sectional_sides(scores)
        elif strategy == "reverse_pressure":
            selected = [(symbol, -side) for symbol, side in select_cross_sectional_sides(scores)]
        elif strategy == "random":
            shuffled = list(symbols)
            random.shuffle(shuffled)
            selected = ([(symbol, 1) for symbol in shuffled[:SIDE_SLOTS]]
                        + [(symbol, -1) for symbol in shuffled[SIDE_SLOTS:2 * SIDE_SLOTS]])
        else:
            raise ValueError(f"unknown strategy: {strategy}")
        signal_time = int(times[index] + MINUTE_MS)
        signals.extend(Signal(signal_time, symbol, side, scores[symbol])
                       for symbol, side in selected)
    return sorted(signals, key=lambda item: (item.time_ms, item.symbol, -item.side))


def _entry_fill(price: float, side: int, slippage: float) -> float:
    return price * (1 + side * slippage)


def _exit_fill(price: float, side: int, slippage: float) -> float:
    return price * (1 - side * slippage)


def _resolve_arrays(
    signal: Signal,
    times: np.ndarray,
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    fee_per_side: float,
    slippage_per_side: float,
    target_pct: float = TARGET_PCT,
    stop_pct: float = STOP_PCT,
    horizon_bars: int = HORIZON_BARS,
) -> dict[str, Any]:
    """Resolve first-touch barriers with stop-first ties and strict bar timing."""
    start = int(np.searchsorted(times, signal.time_ms))
    if start >= len(times) or times[start] != signal.time_ms:
        return {"status": "unscorable", "reason": "missing_entry_minute"}
    stop_index = start + horizon_bars
    expected = signal.time_ms + np.arange(horizon_bars, dtype=np.int64) * MINUTE_MS
    if stop_index > len(times) or not np.array_equal(times[start:stop_index], expected):
        return {"status": "unscorable", "reason": "incomplete_execution_path"}

    entry = _entry_fill(float(opens[start]), signal.side, slippage_per_side)
    horizon_close_return = signal.side * (float(closes[stop_index - 1]) / entry - 1)
    target = entry * (1 + signal.side * target_pct)
    stop = entry * (1 - signal.side * stop_pct)
    reason = "timeout"
    exit_reference = float(closes[stop_index - 1])
    exit_time = int(times[stop_index - 1] + MINUTE_MS)

    for index in range(start, stop_index):
        open_price, high, low = map(float, (opens[index], highs[index], lows[index]))
        stop_gap = open_price <= stop if signal.side == 1 else open_price >= stop
        target_gap = open_price >= target if signal.side == 1 else open_price <= target
        stop_hit = stop_gap or (low <= stop if signal.side == 1 else high >= stop)
        target_hit = target_gap or (high >= target if signal.side == 1 else low <= target)
        if stop_hit or target_hit:
            reason = "stop" if stop_hit else "target"
            exit_reference = open_price if stop_gap else (stop if stop_hit else target)
            exit_time = int(times[index])
            break

    exit_price = _exit_fill(exit_reference, signal.side, slippage_per_side)
    gross_after_slippage = signal.side * (exit_price / entry - 1)
    net_return = gross_after_slippage - fee_per_side * (1 + exit_price / entry)
    return {
        "status": "scorable", "reason": reason, "entry_ms": signal.time_ms,
        "exit_ms": exit_time, "entry": entry, "exit": exit_price,
        "gross_after_slippage": gross_after_slippage, "net_return": net_return,
        "horizon_close_return": horizon_close_return,
        "target_first": reason == "target", "side": signal.side,
        "symbol": signal.symbol,
    }


def resolve_signal(
    signal: Signal,
    frame: pd.DataFrame,
    fee_per_side: float,
    slippage_per_side: float,
    target_pct: float = TARGET_PCT,
    stop_pct: float = STOP_PCT,
    horizon_bars: int = HORIZON_BARS,
) -> dict[str, Any]:
    """DataFrame adapter for one-signal tests and diagnostics."""
    return _resolve_arrays(
        signal,
        frame.t_open_ms.to_numpy(dtype=np.int64),
        frame.o.to_numpy(dtype=float),
        frame.h.to_numpy(dtype=float),
        frame.l.to_numpy(dtype=float),
        frame.c.to_numpy(dtype=float),
        fee_per_side,
        slippage_per_side,
        target_pct,
        stop_pct,
        horizon_bars,
    )


def _wilson(wins: int, total: int) -> list[float | None]:
    if not total:
        return [None, None]
    z = 1.959963984540054
    p = wins / total
    divisor = 1 + z * z / total
    center = (p + z * z / (2 * total)) / divisor
    radius = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / divisor
    return [center - radius, center + radius]


def score_signals(
    signals: list[Signal], minutes: dict[str, pd.DataFrame], slippage: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    arrays = {
        symbol: (
            frame.t_open_ms.to_numpy(dtype=np.int64), frame.o.to_numpy(dtype=float),
            frame.h.to_numpy(dtype=float), frame.l.to_numpy(dtype=float),
            frame.c.to_numpy(dtype=float),
        )
        for symbol, frame in minutes.items()
    }
    outcomes = [
        _resolve_arrays(signal, *arrays[signal.symbol], FEE_PER_SIDE, slippage)
        for signal in signals
    ]
    scorable = [item for item in outcomes if item["status"] == "scorable"]
    nonoverlap: list[dict[str, Any]] = []
    next_allowed: dict[str, int] = {}
    for signal, outcome in zip(signals, outcomes):
        if outcome["status"] != "scorable":
            continue
        if signal.time_ms >= next_allowed.get(signal.symbol, -1):
            nonoverlap.append(outcome)
            next_allowed[signal.symbol] = signal.time_ms + HORIZON_BARS * MINUTE_MS
    wins = sum(item["target_first"] for item in scorable)
    nonoverlap_wins = sum(item["target_first"] for item in nonoverlap)
    base_times = next(iter(arrays.values()))[0]
    eligible_start = int(np.searchsorted(base_times + MINUTE_MS, START_MS, side="left"))
    signal_stop_ms = DEV_CUTOFF_MS - HORIZON_BARS * MINUTE_MS
    eligible_stop = int(np.searchsorted(base_times + MINUTE_MS, signal_stop_ms, side="left"))
    eligible_symbol_minutes = max(eligible_stop - eligible_start, 0)
    report = {
        "issued": len(signals), "scorable": len(scorable),
        "unscorable": len(signals) - len(scorable),
        "eligible_symbol_minutes": eligible_symbol_minutes * 20,
        "actionable_coverage": len(signals) / (eligible_symbol_minutes * 20)
        if eligible_symbol_minutes else 0,
        "m2_all": wins / len(scorable) if scorable else None,
        "wilson95_all": _wilson(wins, len(scorable)),
        "m2_nonoverlap": nonoverlap_wins / len(nonoverlap) if nonoverlap else None,
        "wilson95_nonoverlap": _wilson(nonoverlap_wins, len(nonoverlap)),
        "n_nonoverlap": len(nonoverlap),
        "m1_direction_at_8m": sum(item["horizon_close_return"] > 0 for item in scorable)
        / len(scorable) if scorable else None,
        "m1_direction_at_8m_nonoverlap": sum(
            item["horizon_close_return"] > 0 for item in nonoverlap
        ) / len(nonoverlap) if nonoverlap else None,
        "mean_net_signal_return": float(np.mean([item["net_return"] for item in scorable]))
        if scorable else None,
        "per_symbol": {},
        "per_side": {},
    }
    for symbol in sorted({item["symbol"] for item in scorable}):
        records = [item for item in scorable if item["symbol"] == symbol]
        report["per_symbol"][symbol] = {
            "n": len(records),
            "m2": sum(item["target_first"] for item in records) / len(records),
            "mean_net_return": float(np.mean([item["net_return"] for item in records])),
        }
    for side, name in ((1, "long"), (-1, "short")):
        records = [item for item in scorable if item["side"] == side]
        report["per_side"][name] = {
            "n": len(records),
            "m2": sum(item["target_first"] for item in records) / len(records) if records else None,
            "mean_net_return": float(np.mean([item["net_return"] for item in records]))
            if records else None,
        }
    return outcomes, report


def _close_position(
    positions: dict[str, dict[str, Any]], cash: float, symbol: str,
    exit_price: float, now: int, reason: str, fee: float, completed: list[dict[str, Any]],
) -> float:
    position = positions.pop(symbol)
    pnl_gross = position["side"] * position["notional"] * (exit_price / position["entry"] - 1)
    exit_fee = fee * position["notional"] * exit_price / position["entry"]
    net_pnl = pnl_gross - exit_fee - position["entry_fee"]
    cash += pnl_gross - exit_fee
    completed.append({
        "symbol": symbol, "side": position["side"], "entry_ms": position["entry_ms"],
        "exit_ms": now, "reason": reason, "target_first": reason == "target",
        "net_pnl": net_pnl, "net_return_on_notional": net_pnl / position["notional"],
    })
    return cash


def simulate_portfolio(
    signals: list[Signal], minutes: dict[str, pd.DataFrame], slippage: float,
) -> dict[str, Any]:
    """Replay at most 1x gross exposure with eight 1/8-NAV notional slots."""
    schedules: dict[int, list[Signal]] = {}
    for signal in signals:
        schedules.setdefault(signal.time_ms, []).append(signal)
    arrays = {
        symbol: {column: frame[column].to_numpy(dtype=np.int64 if column == "t_open_ms" else float)
                 for column in ("t_open_ms", "o", "h", "l", "c")}
        for symbol, frame in minutes.items()
    }
    base_times = arrays[sorted(arrays)[0]]["t_open_ms"]
    start = int(np.searchsorted(base_times, START_MS))
    end = int(np.searchsorted(base_times, DEV_CUTOFF_MS))
    cash, peak, max_drawdown, max_gross_to_nav = 1.0, 1.0, 0.0, 0.0
    positions: dict[str, dict[str, Any]] = {}
    completed: list[dict[str, Any]] = []
    nav_samples: list[float] = []
    sample_times: list[int] = []

    def unrealized(position: dict[str, Any], price: float) -> float:
        return position["side"] * position["notional"] * (price / position["entry"] - 1)

    for index in range(start, end):
        now = int(base_times[index])
        bars = {symbol: (float(data["o"][index]), float(data["h"][index]),
                         float(data["l"][index]), float(data["c"][index]))
                for symbol, data in arrays.items()}

        for symbol in list(positions):
            position = positions[symbol]
            open_price = bars[symbol][0]
            stop_gap = open_price <= position["stop"] if position["side"] == 1 else open_price >= position["stop"]
            target_gap = open_price >= position["target"] if position["side"] == 1 else open_price <= position["target"]
            if stop_gap or target_gap:
                reference = open_price if stop_gap else position["target"]
                exit_price = _exit_fill(reference, position["side"], slippage)
                cash = _close_position(positions, cash, symbol, exit_price, now,
                                       "stop" if stop_gap else "target", FEE_PER_SIDE, completed)

        nav_open = cash + sum(unrealized(position, bars[symbol][0])
                              for symbol, position in positions.items())
        gross_open = sum(position["notional"] * bars[symbol][0] / position["entry"]
                         for symbol, position in positions.items())
        for signal in schedules.get(now, []):
            same_side = sum(position["side"] == signal.side for position in positions.values())
            if signal.symbol in positions or len(positions) >= MAX_POSITIONS or same_side >= 4:
                continue
            notional = min(max(nav_open, 0.0) / MAX_POSITIONS, max(nav_open - gross_open, 0.0))
            notional /= 1 + FEE_PER_SIDE
            if notional <= 0:
                continue
            entry = _entry_fill(bars[signal.symbol][0], signal.side, slippage)
            target = entry * (1 + signal.side * TARGET_PCT)
            stop = entry * (1 - signal.side * STOP_PCT)
            entry_fee = FEE_PER_SIDE * notional
            cash -= entry_fee
            positions[signal.symbol] = {
                "symbol": signal.symbol, "side": signal.side, "entry": entry,
                "notional": notional, "target": target, "stop": stop,
                "entry_ms": now, "entry_fee": entry_fee, "bars_held": 0,
            }
            gross_open += notional

        for symbol in list(positions):
            position = positions[symbol]
            _, high, low, close = bars[symbol]
            stop_hit = low <= position["stop"] if position["side"] == 1 else high >= position["stop"]
            target_hit = high >= position["target"] if position["side"] == 1 else low <= position["target"]
            position["bars_held"] += 1
            if stop_hit or target_hit:
                reason = "stop" if stop_hit else "target"
                reference = position["stop"] if stop_hit else position["target"]
                exit_price = _exit_fill(reference, position["side"], slippage)
                cash = _close_position(positions, cash, symbol, exit_price, now,
                                       reason, FEE_PER_SIDE, completed)
            elif position["bars_held"] >= HORIZON_BARS:
                exit_price = _exit_fill(close, position["side"], slippage)
                cash = _close_position(positions, cash, symbol, exit_price,
                                       now + MINUTE_MS, "timeout", FEE_PER_SIDE, completed)

        nav = cash + sum(unrealized(position, bars[symbol][3])
                         for symbol, position in positions.items())
        peak = max(peak, nav)
        max_drawdown = max(max_drawdown, 1 - nav / peak if peak else 0.0)
        gross_close = sum(position["notional"] * bars[symbol][3] / position["entry"]
                          for symbol, position in positions.items())
        max_gross_to_nav = max(max_gross_to_nav, gross_close / nav if nav > 0 else math.inf)
        if now % (60 * MINUTE_MS) == 0:
            sample_times.append(now)
            nav_samples.append(nav)

    if positions:
        raise AssertionError("positions remain open at the purged development boundary")
    final = cash
    elapsed_days = (DEV_CUTOFF_MS - START_MS) / (24 * 60 * MINUTE_MS)
    cagr = final ** (365.25 / elapsed_days) - 1 if final > 0 else -1.0
    hourly_returns = np.diff(nav_samples) / np.asarray(nav_samples[:-1]) if len(nav_samples) > 1 else np.array([])
    std = float(np.std(hourly_returns, ddof=1)) if len(hourly_returns) > 1 else 0.0
    wins = sum(item["target_first"] for item in completed)
    wins_net = sum(item["net_return_on_notional"] > 0 for item in completed)
    gains = sum(item["net_return_on_notional"] for item in completed
                if item["net_return_on_notional"] > 0)
    losses = abs(sum(item["net_return_on_notional"] for item in completed
                     if item["net_return_on_notional"] < 0))
    return {
        "initial_equity": 1.0, "final_equity": final, "total_compounded_return": final - 1,
        "cagr_dev_only": cagr, "max_drawdown": max_drawdown,
        "hourly_sharpe_dev_only": float(np.mean(hourly_returns) / std * math.sqrt(24 * 365))
        if std > 0 else None,
        "completed_positions": len(completed), "open_at_end": len(positions),
        "portfolio_m2": wins / len(completed) if completed else None,
        "portfolio_trade_positive_net_rate": wins_net / len(completed) if completed else None,
        "mean_net_return_on_notional": float(np.mean([item["net_return_on_notional"] for item in completed]))
        if completed else None,
        "profit_factor": gains / losses if losses else None,
        "max_gross_to_nav": max_gross_to_nav,
        "monthly_nav_samples": {
            pd.to_datetime(time, unit="ms", utc=True).strftime("%Y-%m"): nav
            for time, nav in zip(sample_times, nav_samples)
        },
    }


def _btc_buy_hold(minutes: dict[str, pd.DataFrame], slippage: float) -> dict[str, float]:
    frame = minutes["BTCUSDT"]
    times = frame.t_open_ms.to_numpy(dtype=np.int64)
    start = int(np.searchsorted(times, START_MS))
    end = int(np.searchsorted(times, DEV_CUTOFF_MS)) - 1
    if start >= len(times) or end <= start or times[start] != START_MS:
        raise ValueError("BTC baseline misses the development endpoints")
    entry = _entry_fill(float(frame.o.iloc[start]), 1, slippage)
    exit_price = _exit_fill(float(frame.c.iloc[end]), 1, slippage)
    equity = exit_price / entry - FEE_PER_SIDE * (1 + exit_price / entry)
    return {"final_equity": equity, "total_compounded_return": equity - 1}


def run(db_path: Path, universe_path: Path) -> dict[str, Any]:
    symbols = load_universe(universe_path)
    minutes, data_hash = load_market(db_path, symbols)
    strategy_results: dict[str, Any] = {}
    for name in ("pressure_momentum", "reverse_pressure", "random"):
        signals = build_signals(minutes, name)
        _, report = score_signals(signals, minutes, BASE_SLIPPAGE)
        portfolio = simulate_portfolio(signals, minutes, BASE_SLIPPAGE)
        _, stress_report = score_signals(signals, minutes, STRESS_SLIPPAGE)
        stress_portfolio = simulate_portfolio(signals, minutes, STRESS_SLIPPAGE)
        delayed = [Signal(item.time_ms + MINUTE_MS, item.symbol, item.side, item.pressure)
                   for item in signals
                   if item.time_ms + (HORIZON_BARS + 1) * MINUTE_MS < DEV_CUTOFF_MS]
        _, delayed_report = score_signals(delayed, minutes, BASE_SLIPPAGE)
        strategy_results[name] = {
            "signals": report,
            "portfolio_base_cost": portfolio,
            "signals_stress_slippage": stress_report,
            "portfolio_stress_slippage": stress_portfolio,
        }
        if name == "pressure_momentum":
            strategy_results[name]["signals_one_minute_extra_delay"] = delayed_report
    return {
        "study": "three_minute_quote_volume_weighted_close_location_cross_sectional_momentum",
        "trial_id": "crypto_pressure_20261120_01", "trial_count_in_this_hypothesis": 1,
        "split": "development_only", "start_ms": START_MS, "cutoff_exclusive_ms": DEV_CUTOFF_MS,
        "signal_cutoff_exclusive_ms": DEV_CUTOFF_MS - HORIZON_BARS * MINUTE_MS,
        "validation_opened": False, "universe": symbols,
        "input_db": str(db_path.resolve()), "universe_file": str(universe_path.resolve()),
        "input_db_size_bytes": db_path.stat().st_size, "input_db_mtime_ns": db_path.stat().st_mtime_ns,
        "data_sha256_selected_rows": data_hash,
        "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "fee_per_side": FEE_PER_SIDE, "base_slippage_per_side": BASE_SLIPPAGE,
        "stress_slippage_per_side": STRESS_SLIPPAGE,
        "target_pct": TARGET_PCT, "stop_pct": STOP_PCT, "horizon_bars": HORIZON_BARS,
        "btc_buy_and_hold_base_cost": _btc_buy_hold(minutes, BASE_SLIPPAGE),
        "btc_buy_and_hold_stress_slippage": _btc_buy_hold(minutes, STRESS_SLIPPAGE),
        "strategies": strategy_results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--universe", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.db, args.universe)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "trial_id": result["trial_id"], "data_sha256_selected_rows": result["data_sha256_selected_rows"],
        "strategies": {
            name: {
                "signals": value["signals"],
                "final_equity": value["portfolio_base_cost"]["final_equity"],
                "mdd": value["portfolio_base_cost"]["max_drawdown"],
            }
            for name, value in result["strategies"].items()
        },
        "output": str(args.output),
    }, indent=2))


if __name__ == "__main__":
    main()
