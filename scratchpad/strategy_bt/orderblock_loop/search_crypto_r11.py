"""R11 single-config TRAIN diagnostic: prior-range false-break reclaim long.

This module never reads TEST data and never writes the shared trial ledger.
"""

from __future__ import annotations

import hashlib
import json
from math import isfinite
from pathlib import Path
from statistics import mean
from typing import Mapping, Sequence

import search_crypto as common
from crypto import (Bar, FundingEvent, Setup, Trade, Zone, _atr,
                    simulate_trade, trade_daily_pnl)
from metrics import curve_metrics, trade_metrics, wilson_lower

HERE = Path(__file__).resolve().parent
BAR_MS = 14_400_000
LOOKBACK = 20
ATR_PERIOD = 14
MINIMUM_SYMBOLS = 30
MAX_HOLDING_BARS = 48
STOP_BUFFER_ATR = 0.10
REWARD_R = 2.0
ROUND_TRIP_COST_BPS = 12.0
FUNDING_ORDER_POLICY = "adverse_only"
CONFIG = {
    "round": "R11-coin", "name": "prior_range_false_break_reclaim_long",
    "timeframe": "4h", "lookback_bars": LOOKBACK,
    "signal": "low_below_prior_20_low_close_above_prior_low_bullish",
    "entry": "next_4h_open", "stop_buffer_atr": STOP_BUFFER_ATR,
    "target_r": REWARD_R, "max_holding_bars": MAX_HOLDING_BARS,
    "round_trip_cost_bps": ROUND_TRIP_COST_BPS,
    "funding_order_policy": FUNDING_ORDER_POLICY,
}


def _segments(bars: Sequence[Bar]) -> list[tuple[int, int]]:
    if any(not bar.complete for bar in bars):
        raise ValueError("R11 accepts completed bars only")
    if any(bar.timestamp % BAR_MS for bar in bars):
        raise ValueError("R11 bars must align to UTC 4h boundaries")
    if any(a.timestamp >= b.timestamp for a, b in zip(bars, bars[1:])):
        raise ValueError("R11 timestamps must be strictly increasing")
    if not bars:
        return []
    result = []
    start = 0
    for index in range(1, len(bars)):
        if bars[index].timestamp - bars[index - 1].timestamp != BAR_MS:
            result.append((start, index))
            start = index
    result.append((start, len(bars)))
    return result


def signal_at(bars: Sequence[Bar], index: int) -> dict | None:
    """Return the fixed false-break signal using only the current prefix."""
    if index < LOOKBACK or index >= len(bars):
        return None
    bar = bars[index]
    previous_low = min(item.low for item in bars[index - LOOKBACK:index])
    atr = _atr(bars, index, ATR_PERIOD)
    if atr is None or not isfinite(atr) or atr <= 0:
        return None
    if bar.low < previous_low and bar.close > previous_low and bar.close > bar.open:
        return {"previous_low": previous_low, "atr": atr}
    return None


def make_setup(bars: Sequence[Bar], signal_index: int) -> Setup | None:
    """Create a next-open long setup; return None for missing or invalid fills."""
    signal = signal_at(bars, signal_index)
    entry_index = signal_index + 1
    if signal is None or entry_index >= len(bars) or not bars[entry_index].complete:
        return None
    entry = bars[entry_index].open
    stop = bars[signal_index].low - STOP_BUFFER_ATR * signal["atr"]
    risk = entry - stop
    if not isfinite(entry) or entry <= 0 or risk <= 0:
        return None
    zone = Zone(signal_index, signal_index, "long", stop, entry, signal["atr"])
    return Setup(zone, entry_index, entry, stop, entry + REWARD_R * risk)


def _event_id(symbol: str, signal_ts: int) -> str:
    raw = f"R11|{symbol}|{signal_ts}".encode()
    return hashlib.sha256(raw).hexdigest()


def _funding_slice(bars: Sequence[Bar], funding: Mapping[int, FundingEvent]) -> dict[int, FundingEvent]:
    return common._funding_by_timestamp(bars, funding, BAR_MS)


def _simulate_segment(symbol: str, bars: Sequence[Bar], funding: Mapping[int, FundingEvent],
                      *, is_last_segment: bool) -> dict:
    events: list[dict] = []
    daily: dict[int, float] = {}
    strict_daily: dict[int, float] = {}
    counts = {key: 0 for key in (
        "signals", "entered", "entry_gap_skipped", "entry_censored",
        "gap_exit_censored", "cutoff_exit_censored", "funding_unscorable",
    )}
    if not bars:
        return {"events": events, "daily": daily, "strict_daily": strict_daily,
                "counts": counts}
    scoped_funding = _funding_slice(bars, funding)
    index = LOOKBACK
    while index < len(bars):
        signal = signal_at(bars, index)
        if signal is None:
            index += 1
            continue
        counts["signals"] += 1
        signal_ts = bars[index].timestamp
        setup = make_setup(bars, index)
        if setup is None:
            counts["entry_censored"] += 1
            break
        if setup.entry_price <= setup.stop:
            counts["entry_gap_skipped"] += 1
            index += 1
            continue
        trade = simulate_trade(
            bars, setup, funding=scoped_funding,
            max_holding_bars=MAX_HOLDING_BARS,
            fee_bps_per_side=4.0, slippage_bps_per_side=2.0,
            bar_duration_ms=BAR_MS, funding_order_policy=FUNDING_ORDER_POLICY,
        )
        if trade is None:
            counts["cutoff_exit_censored" if is_last_segment else "gap_exit_censored"] += 1
            break
        counts["entered"] += 1
        daily_pnl = trade_daily_pnl(
            bars, trade, funding=scoped_funding, bar_duration_ms=BAR_MS,
        )
        if trade.net_return is None or daily_pnl is None:
            counts["funding_unscorable"] += 1
        else:
            for day, value in daily_pnl.items():
                daily[day] = daily.get(day, 0.0) + value
            if trade.ambiguous_funding_events == 0:
                for day, value in daily_pnl.items():
                    strict_daily[day] = strict_daily.get(day, 0.0) + value
        exit_ts = bars[trade.exit_index].timestamp
        event_funding = [
            {"timestamp_ms": ts, "rate": item.rate, "mark_price": item.mark_price,
             "coverage_gap": item.coverage_gap,
             "used_candle_close_fallback": item.used_candle_close_fallback}
            for ts, item in sorted(scoped_funding.items())
            if bars[setup.entry_index].timestamp <= ts <= exit_ts + BAR_MS + 1_000
        ]
        events.append({
            "signal_id": _event_id(symbol, signal_ts), "symbol": symbol,
            "signal_timestamp_ms": signal_ts,
            "entry_timestamp_ms": bars[setup.entry_index].timestamp,
            "entry_price": setup.entry_price, "stop": setup.stop,
            "target": setup.target,
            "exit_timestamp_ms": exit_ts, "exit_end_timestamp_ms": exit_ts + BAR_MS,
            "exit_price": trade.exit_price, "exit_reason": trade.exit_reason,
            "target_first": trade.exit_reason == "target",
            "net_return": trade.net_return,
            "ambiguous_funding_events": trade.ambiguous_funding_events,
            "funding_events": event_funding,
            "m2_included": True,
        })
        # Signals confirmed at the exit-bar close are available after that exit.
        index = trade.exit_index
    return {"events": events, "daily": daily, "strict_daily": strict_daily,
            "counts": counts}


def _nonoverlap(events: Sequence[dict]) -> list[dict]:
    selected = []
    by_symbol: dict[str, list[dict]] = {}
    for event in events:
        by_symbol.setdefault(event["symbol"], []).append(event)
    for rows in by_symbol.values():
        last_end = -1
        for event in sorted(rows, key=lambda item: (
                item["exit_end_timestamp_ms"], item["entry_timestamp_ms"], item["signal_id"])):
            if event["entry_timestamp_ms"] >= last_end:
                selected.append(event)
                last_end = event["exit_end_timestamp_ms"]
    return selected


def _metrics(events: list[dict], daily_by_symbol: dict[str, dict[int, float]],
             strict_by_symbol: dict[str, dict[int, float]], symbols: Sequence[str],
             first_day: int | None, last_day: int | None) -> dict:
    scoreable = [event for event in events if event["net_return"] is not None]
    strict = [event for event in scoreable if event["ambiguous_funding_events"] == 0]
    scored_stats = trade_metrics([event["net_return"] for event in scoreable])
    strict_stats = trade_metrics([event["net_return"] for event in strict])
    days = range(first_day, last_day + 1) if first_day is not None and last_day is not None else ()
    daily_returns = [sum(daily_by_symbol[s].get(day, 0.0) for s in symbols) / len(symbols)
                     for day in days] if symbols else []
    strict_daily_returns = [sum(strict_by_symbol[s].get(day, 0.0) for s in symbols) / len(symbols)
                            for day in days] if symbols else []
    curve = curve_metrics(daily_returns, 365)
    strict_curve = curve_metrics(strict_daily_returns, 365)
    nonoverlap = _nonoverlap(events)
    hits = sum(event["target_first"] for event in events)
    nonoverlap_hits = sum(event["target_first"] for event in nonoverlap)
    return {
        "entered_trades": len(events), "scoreable_trades": scored_stats.count,
        "funding_unscorable_trades": len(events) - scored_stats.count,
        "win_rate": scored_stats.win_rate, "profit_factor": scored_stats.profit_factor,
        "expectancy_bps": scored_stats.expectancy_bps,
        "cumulative_return": curve.cumulative_return, "max_drawdown": curve.max_drawdown,
        "annualized_sharpe": curve.annualized_sharpe, "solvent": curve.solvent,
        "strict_scoreable_trades": strict_stats.count,
        "strict_win_rate": strict_stats.win_rate,
        "strict_profit_factor": strict_stats.profit_factor,
        "strict_expectancy_bps": strict_stats.expectancy_bps,
        "strict_cumulative_return": strict_curve.cumulative_return,
        "strict_max_drawdown": strict_curve.max_drawdown,
        "strict_annualized_sharpe": strict_curve.annualized_sharpe,
        "m2_signal_count": len(events), "m2_target_hits": hits,
        "m2_target_first_rate": hits / len(events) if events else None,
        "m2_wilson_lower_95": wilson_lower(hits, len(events)),
        "m2_nonoverlap_count": len(nonoverlap),
        "m2_nonoverlap_target_hits": nonoverlap_hits,
        "m2_nonoverlap_target_first_rate": nonoverlap_hits / len(nonoverlap) if nonoverlap else None,
        "m2_nonoverlap_wilson_lower_95": wilson_lower(nonoverlap_hits, len(nonoverlap)),
    }


def evaluate(barsets: Sequence[tuple[str, Sequence[Bar], Mapping[int, FundingEvent], int]]) -> dict:
    """Evaluate in-memory TRAIN barsets; useful for synthetic tests and TRAIN runner."""
    symbols = [symbol for symbol, bars, _funding, _excluded in barsets if bars]
    daily_by_symbol = {symbol: {} for symbol in symbols}
    strict_by_symbol = {symbol: {} for symbol in symbols}
    all_events: list[dict] = []
    totals: dict[str, int] = {}
    first_day = last_day = None
    for symbol, raw_bars, funding, _excluded in barsets:
        bars = [bar for bar in raw_bars if bar.complete]
        segments = _segments(bars)
        if not bars:
            continue
        first_day = min(first_day, bars[0].timestamp // 86_400_000) if first_day is not None else bars[0].timestamp // 86_400_000
        last_day = max(last_day, bars[-1].timestamp // 86_400_000) if last_day is not None else bars[-1].timestamp // 86_400_000
        for pos, (start, end) in enumerate(segments):
            part = bars[start:end]
            result = _simulate_segment(symbol, part, funding, is_last_segment=pos == len(segments) - 1)
            all_events.extend(result["events"])
            for key, value in result["counts"].items():
                totals[key] = totals.get(key, 0) + value
            for day, value in result["daily"].items():
                daily_by_symbol[symbol][day] = daily_by_symbol[symbol].get(day, 0.0) + value
            for day, value in result["strict_daily"].items():
                strict_by_symbol[symbol][day] = strict_by_symbol[symbol].get(day, 0.0) + value
    summary = _metrics(all_events, daily_by_symbol, strict_by_symbol, symbols, first_day, last_day)
    status = "unscorable" if len(symbols) < MINIMUM_SYMBOLS or summary["funding_unscorable_trades"] else "completed"
    return {"status": status, "eligible_symbols": len(symbols), **totals, **summary,
            "events": all_events, "config": CONFIG.copy()}


def _expected_symbols(path: Path | None = None) -> frozenset[str]:
    import csv
    path = path or HERE / "universe" / "CRYPTO_35.csv"
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != ["symbol"]:
            raise ValueError("frozen crypto universe must have one symbol column")
        symbols = [row["symbol"].strip() for row in reader]
    if not symbols or any(not symbol for symbol in symbols) or len(symbols) != len(set(symbols)):
        raise ValueError("frozen crypto universe contains empty or duplicate symbols")
    return frozenset(symbols)


def load_train(*, loader=None, data_dir=None) -> list[tuple]:
    if loader is None:
        import data_access as loader
    rows = []
    for symbol, bars, funding in loader.iter_train_bars(timeframe="4h", data_dir=data_dir):
        rows.append((symbol, [bar for bar in bars if bar.complete], funding,
                     sum(not bar.complete for bar in bars)))
        common._check_memory()
    actual = [row[0] for row in rows]
    expected = _expected_symbols()
    if len(actual) != len(set(actual)) or set(actual) != set(expected):
        raise ValueError("R11 TRAIN symbols differ from the exact frozen 35-symbol list")
    return rows


def _hash_inputs() -> dict[str, str]:
    paths = [HERE / name for name in ("crypto.py", "data_access.py", "metrics.py", "search_crypto.py", Path(__file__).name)]
    paths += [HERE / "PREREG_R11_R12.md", HERE / "universe" / "CRYPTO_35.csv"]
    return {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def run_train(*, loader=None, data_dir=None) -> dict:
    barsets = load_train(loader=loader, data_dir=data_dir)
    summary = evaluate(barsets)
    summary["train_input_fingerprint"] = common._train_input_fingerprint("4h", barsets)
    summary["input_hashes"] = _hash_inputs()
    summary["train_period"] = "4h bars closing <= 2023-11-06T16:00:00Z"
    summary["test_opened"] = False
    return summary


if __name__ == "__main__":
    print(json.dumps(run_train(), sort_keys=True, separators=(",", ":")))
