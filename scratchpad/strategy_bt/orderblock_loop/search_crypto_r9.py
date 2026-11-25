"""Preregistered R9 crypto OB sweep/reclaim strategy; TRAIN only."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import os

import search_crypto as common
from crypto import (
    Bar, FundingEvent, Setup, Trade, Zone, _atr, r4_zones,
    simulate_trade, trade_daily_pnl,
)
from metrics import curve_metrics, trade_metrics, wilson_lower

HERE = Path(__file__).resolve().parent
TIMEFRAME = "4h"
BAR_MS = 14_400_000
DEFINITION = "bos_origin"
DEADLINE = 48
REWARD_R = 2.0
MINIMUM_SYMBOLS = 30
FUNDING_ORDER_POLICY = "adverse_only"
UNIVERSE_PATH = HERE / "universe" / "CRYPTO_35.csv"
PREREG_PATH = HERE / "PREREG.md"
CONFIG = {
    "round": "R9-coin", "name": "bos_distal_sweep_full_reclaim",
    "timeframe": TIMEFRAME, "definition": DEFINITION,
    "direction": "both", "deadline": DEADLINE, "reward_r": REWARD_R,
    "minimum_symbols": MINIMUM_SYMBOLS,
    "funding_order_policy": FUNDING_ORDER_POLICY,
}


@dataclass(frozen=True)
class SweepDecision:
    status: str
    sweep_index: int | None = None
    confirmation_index: int | None = None
    consumed_index: int | None = None


def _contact(bar: Bar, zone: Zone) -> bool:
    return bar.low <= zone.high and bar.high >= zone.low


def first_sweep_recovery(bars: list[Bar], zone: Zone) -> SweepDecision:
    """Find only the first retest and require distal sweep plus full-zone close."""
    if not bars or not (0 <= zone.signal_index < len(bars)):
        return SweepDecision("invalid_zone")
    end = min(len(bars) - 1, zone.signal_index + DEADLINE)
    for index in range(zone.signal_index + 1, end + 1):
        bar = bars[index]
        long = zone.direction == "long"
        gap_failed = (bar.open < zone.low and bar.high < zone.low if long
                      else bar.open > zone.high and bar.low > zone.high)
        if gap_failed:
            return SweepDecision("distal_gap_failed", index, None, index)
        if not _contact(bar, zone):
            continue
        swept = bar.low < zone.low if long else bar.high > zone.high
        if not swept:
            return SweepDecision("ordinary_retest_consumed", consumed_index=index)
        distal_close_failed = bar.close <= zone.low if long else bar.close >= zone.high
        if distal_close_failed:
            return SweepDecision("distal_close_failed", index, None, index)
        fully_reclaimed = bar.close > zone.high if long else bar.close < zone.low
        if fully_reclaimed:
            return SweepDecision("reclaimed_same_bar", index, index, index)
        confirm_index = index + 1
        if confirm_index > end:
            if confirm_index > zone.signal_index + DEADLINE:
                return SweepDecision("expired_confirmation_outside_deadline", index,
                                     None, index)
        if confirm_index >= len(bars):
            return SweepDecision("confirmation_right_censored", index, None, index)
        confirm = bars[confirm_index]
        confirm_distal_close_failed = (
            confirm.close <= zone.low if long else confirm.close >= zone.high
        )
        if confirm_distal_close_failed:
            return SweepDecision("confirmation_distal_close_failed", index,
                                 confirm_index, confirm_index)
        reclaimed = confirm.close > zone.high if long else confirm.close < zone.low
        if reclaimed:
            return SweepDecision("reclaimed_next_bar", index, confirm_index,
                                 confirm_index)
        return SweepDecision("confirmation_failed", index, confirm_index,
                             confirm_index)
    if len(bars) - 1 < zone.signal_index + DEADLINE:
        return SweepDecision("segment_right_censored", consumed_index=len(bars) - 1)
    return SweepDecision("expired_no_contact", consumed_index=end)


def _segments(bars: list[Bar]) -> list[tuple[int, int]]:
    """Validate UTC 4h bars and return half-open contiguous index ranges."""
    if any(not bar.complete for bar in bars):
        raise ValueError("R9 accepts completed bars only")
    if any(bar.timestamp % BAR_MS for bar in bars):
        raise ValueError("4h open timestamps must align to UTC boundaries")
    if any(a.timestamp >= b.timestamp for a, b in zip(bars, bars[1:])):
        raise ValueError("timestamps must be strictly increasing")
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


def _event_id(symbol: str, signal_ts: int, origin_ts: int, direction: str) -> str:
    value = f"{symbol}|{signal_ts}|{origin_ts}|{direction}"
    return hashlib.sha256(value.encode()).hexdigest()


def _write_zone_event(writer, symbol: str, bars: list[Bar], zone: Zone,
                      status: str) -> None:
    if writer is None:
        return
    signal_ts = bars[zone.signal_index].timestamp
    writer.write(json.dumps({
        "signal_id": _event_id(
            symbol, signal_ts, bars[zone.origin_index].timestamp, zone.direction,
        ),
        "symbol": symbol, "direction": zone.direction,
        "signal_timestamp": signal_ts,
        "origin_timestamp": bars[zone.origin_index].timestamp,
        "zone_low": zone.low, "zone_high": zone.high,
        "status": status,
    }, sort_keys=True) + "\n")


def _record_ignored_zones(audit: dict[str, int], writer, symbol: str,
                          bars: list[Bar], by_index: dict[int, Zone],
                          lower_exclusive: int, upper_inclusive: int,
                          status: str) -> None:
    for index in sorted(i for i in by_index
                        if lower_exclusive < i <= upper_inclusive):
        audit["ignored_zones"] += 1
        _write_zone_event(writer, symbol, bars, by_index[index], status)


def simulate_symbol(symbol: str, bars: list[Bar], funding: dict[int, FundingEvent],
                    *, event_writer=None) -> tuple[list[Trade], list[Trade], list[Trade], dict[str, int], list[tuple], dict[int, float], dict[int, float]]:
    """Run one symbol; each zone's first contact is terminal and zones never overlap."""
    audit = {key: 0 for key in (
        "zones", "ordinary_retest_consumed", "sweep_failed", "reclaimed",
        "expired", "right_censored", "gap_segments", "entry_skipped",
        "exit_path_censored", "completed_trades", "ignored_zones",
        "funding_unscorable_trades", "gap_entry_blocked",
        "cutoff_entry_censored", "gap_exit_censored", "cutoff_exit_censored",
    )}
    trades: list[Trade] = []
    scoreable_trades: list[Trade] = []
    strict_trades: list[Trade] = []
    events: list[tuple] = []
    daily_pnl: dict[int, float] = {}
    strict_daily_pnl: dict[int, float] = {}
    direction_daily_pnl = {"long": {}, "short": {}}
    direction_strict_daily_pnl = {"long": {}, "short": {}}
    segments = _segments(bars)
    audit["gap_segments"] = max(0, len(segments) - 1)
    for start, segment_stop in segments:
        segment = bars[start:segment_stop]
        zones = r4_zones(segment, DEFINITION)
        by_index = {zone.signal_index: zone for zone in zones}
        if len(by_index) != len(zones):
            raise ValueError("duplicate zones at a signal bar are invalid")
        audit["zones"] += len(zones)
        index = 0
        while index < len(segment):
            zone = by_index.get(index)
            if zone is None:
                index += 1
                continue
            decision = first_sweep_recovery(segment, zone)
            signal_ts = segment[zone.signal_index].timestamp
            event = {
                "signal_id": _event_id(
                    symbol, signal_ts, segment[zone.origin_index].timestamp,
                    zone.direction,
                ),
                "symbol": symbol, "direction": zone.direction,
                "signal_timestamp": signal_ts,
                "origin_timestamp": segment[zone.origin_index].timestamp,
                "zone_low": zone.low, "zone_high": zone.high,
                "status": decision.status,
            }
            if decision.sweep_index is not None:
                event["sweep_timestamp"] = segment[decision.sweep_index].timestamp
            if decision.confirmation_index is not None:
                event["confirmation_timestamp"] = segment[decision.confirmation_index].timestamp
            if decision.status not in ("reclaimed_same_bar", "reclaimed_next_bar"):
                if decision.status == "ordinary_retest_consumed":
                    audit["ordinary_retest_consumed"] += 1
                elif decision.status.startswith("expired"):
                    audit["expired"] += 1
                elif "censored" in decision.status:
                    audit["right_censored"] += 1
                    boundary = "gap" if segment_stop < len(bars) else "cutoff"
                    kind = "confirmation" if "confirmation" in decision.status else "setup"
                    event["status"] = (
                        f"{boundary}_{kind}_blocked" if boundary == "gap"
                        else f"cutoff_{kind}_censored"
                    )
                else:
                    audit["sweep_failed"] += 1
                if event_writer:
                    event_writer.write(json.dumps(event, sort_keys=True) + "\n")
                terminal = decision.consumed_index
                if decision.status == "expired_no_contact" and terminal is not None:
                    _record_ignored_zones(
                        audit, event_writer, symbol, segment, by_index,
                        index, terminal - 1, "ignored_active_zone",
                    )
                    index = terminal
                    continue
                if terminal is not None:
                    _record_ignored_zones(
                        audit, event_writer, symbol, segment, by_index,
                        index, terminal, "ignored_active_zone",
                    )
                index = terminal + 1 if terminal is not None else index + 1
                continue

            sweep_index = decision.sweep_index
            confirm_index = decision.confirmation_index
            sweep = segment[sweep_index]
            atr = _atr(segment, sweep_index)
            entry_index = confirm_index + 1
            if atr is None or entry_index >= len(segment):
                if entry_index >= len(segment):
                    boundary = "gap" if segment_stop < len(bars) else "cutoff"
                    event["status"] = "gap_entry_blocked" if boundary == "gap" else "cutoff_entry_censored"
                    audit["gap_entry_blocked" if boundary == "gap" else "cutoff_entry_censored"] += 1
                else:
                    event["status"] = "missing_sweep_atr"
                    audit["sweep_failed"] += 1
                if event_writer:
                    event_writer.write(json.dumps(event, sort_keys=True) + "\n")
                _record_ignored_zones(
                    audit, event_writer, symbol, segment, by_index,
                    index, confirm_index, "ignored_active_zone",
                )
                index = confirm_index + 1
                continue
            stop_price = (sweep.low - 0.10 * atr if zone.direction == "long"
                          else sweep.high + 0.10 * atr)
            entry = segment[entry_index].open
            if (entry <= stop_price if zone.direction == "long" else entry >= stop_price):
                event["status"] = "entry_skipped_gap_through_stop"
                event.update({
                    "sweep_timestamp": sweep.timestamp,
                    "confirmation_timestamp": segment[confirm_index].timestamp,
                    "entry_timestamp": segment[entry_index].timestamp,
                    "entry_price": entry, "stop": stop_price,
                    "target": None, "m2_included": False,
                })
                audit["entry_skipped"] += 1
                if event_writer:
                    event_writer.write(json.dumps(event, sort_keys=True) + "\n")
                _record_ignored_zones(
                    audit, event_writer, symbol, segment, by_index,
                    index, entry_index - 1, "ignored_active_zone",
                )
                index = entry_index
                continue
            risk = entry - stop_price if zone.direction == "long" else stop_price - entry
            if risk <= 0:
                event["status"] = "entry_skipped_nonpositive_risk"
                audit["entry_skipped"] += 1
                if event_writer:
                    event_writer.write(json.dumps(event, sort_keys=True) + "\n")
                _record_ignored_zones(
                    audit, event_writer, symbol, segment, by_index,
                    index, entry_index - 1, "ignored_active_zone",
                )
                index = entry_index
                continue
            target = (entry + REWARD_R * risk if zone.direction == "long"
                      else entry - REWARD_R * risk)
            setup = Setup(zone, entry_index, entry, stop_price, target)
            funding_in_segment = {
                ts: item for ts, item in funding.items()
                if segment[entry_index].timestamp <= ts
                <= segment[-1].timestamp + BAR_MS + 1_000
            }
            trade = simulate_trade(
                segment, setup, funding=funding_in_segment,
                fee_bps_per_side=4.0, slippage_bps_per_side=2.0,
                bar_duration_ms=BAR_MS,
                funding_order_policy=FUNDING_ORDER_POLICY,
            )
            if trade is None:
                boundary = "gap" if segment_stop < len(bars) else "cutoff"
                event["status"] = f"gap_exit_censored" if boundary == "gap" else "cutoff_exit_censored"
                event.update({"entry_timestamp": segment[entry_index].timestamp,
                              "entry_price": entry, "stop": stop_price,
                              "target": target, "m2_included": False})
                audit["exit_path_censored"] += 1
                audit["gap_exit_censored" if boundary == "gap" else "cutoff_exit_censored"] += 1
                if event_writer:
                    event_writer.write(json.dumps(event, sort_keys=True) + "\n")
                _record_ignored_zones(
                    audit, event_writer, symbol, segment, by_index,
                    entry_index - 1, len(segment) - 1,
                    "ignored_position_open",
                )
                break
            audit["reclaimed"] += 1
            audit["completed_trades"] += 1
            events.append((symbol, segment[entry_index].timestamp,
                           segment[trade.exit_index].timestamp + BAR_MS,
                           zone.signal_index + start, trade.exit_reason == "target",
                           zone.direction))
            event.update({
                "status": "entered", "sweep_timestamp": sweep.timestamp,
                "confirmation_timestamp": segment[confirm_index].timestamp,
                "entry_timestamp": segment[entry_index].timestamp,
                "entry_price": entry, "stop": stop_price, "target": target,
                "exit_timestamp": segment[trade.exit_index].timestamp,
                "exit_price": trade.exit_price, "exit_reason": trade.exit_reason,
                "gross_return": trade.gross_return,
                "funding_return": trade.funding_return,
                "cost_bps": trade.cost_bps,
                "net_return": trade.net_return,
                "funding_unscorable": trade.net_return is None,
                "m2_included": True,
                "ambiguous_funding_events": trade.ambiguous_funding_events,
                "funding_events": [
                    {
                        "timestamp": timestamp, "rate": item.rate,
                        "mark_price": item.mark_price,
                        "coverage_gap": item.coverage_gap,
                        "used_candle_close_fallback": item.used_candle_close_fallback,
                    }
                    for timestamp, item in sorted(funding_in_segment.items())
                    if segment[entry_index].timestamp <= timestamp
                    <= segment[trade.exit_index].timestamp + BAR_MS + 1_000
                ],
            })
            trades.append(trade)
            if trade.net_return is None:
                audit["funding_unscorable_trades"] += 1
            else:
                scored_daily = trade_daily_pnl(
                    segment, trade, funding=funding_in_segment,
                    bar_duration_ms=BAR_MS,
                )
                if scored_daily is None:
                    audit["funding_unscorable_trades"] += 1
                else:
                    scoreable_trades.append(trade)
                    direction = trade.setup.zone.direction
                    for day, value in scored_daily.items():
                        daily_pnl[day] = daily_pnl.get(day, 0.0) + value
                        direction_daily_pnl[direction][day] = (
                            direction_daily_pnl[direction].get(day, 0.0) + value
                        )
                    if trade.ambiguous_funding_events == 0:
                        strict_trades.append(trade)
                        for day, value in scored_daily.items():
                            strict_daily_pnl[day] = strict_daily_pnl.get(day, 0.0) + value
                            direction_strict_daily_pnl[direction][day] = (
                                direction_strict_daily_pnl[direction].get(day, 0.0) + value
                            )
            if event_writer:
                event_writer.write(json.dumps(event, sort_keys=True) + "\n")
            _record_ignored_zones(
                audit, event_writer, symbol, segment, by_index,
                entry_index - 1, trade.exit_index - 1,
                "ignored_position_open",
            )
            index = trade.exit_index
    return (trades, scoreable_trades, strict_trades, audit, events,
            daily_pnl, strict_daily_pnl, direction_daily_pnl,
            direction_strict_daily_pnl)


def _trial(barsets, *, event_writer=None) -> dict:
    trades: list[Trade] = []
    scored: list[Trade] = []
    strict: list[Trade] = []
    all_events = []
    audits = []
    symbols = []
    daily_by_symbol = {}
    strict_daily_by_symbol = {}
    direction_daily_by_symbol = {"long": {}, "short": {}}
    direction_strict_daily_by_symbol = {"long": {}, "short": {}}
    for symbol, bars, funding, _ in barsets:
        if not bars:
            continue
        symbols.append(symbol)
        (symbol_trades, symbol_scored, symbol_strict, audit, events, daily,
         strict_daily, direction_daily, direction_strict_daily) = simulate_symbol(
            symbol, bars, funding, event_writer=event_writer,
        )
        trades.extend(symbol_trades)
        scored.extend(symbol_scored)
        strict.extend(symbol_strict)
        audits.append(audit)
        all_events.extend(events)
        daily_by_symbol[symbol] = daily
        strict_daily_by_symbol[symbol] = strict_daily
        for direction in ("long", "short"):
            direction_daily_by_symbol[direction][symbol] = direction_daily[direction]
            direction_strict_daily_by_symbol[direction][symbol] = direction_strict_daily[direction]
    total_audit = {key: sum(row[key] for row in audits) for key in audits[0]} if audits else {}
    stats = trade_metrics([trade.net_return for trade in scored])
    strict_stats = trade_metrics([trade.net_return for trade in strict])
    first_day = min((bars[0].timestamp // 86_400_000 for _, bars, _, _ in barsets if bars), default=None)
    last_day = max((bars[-1].timestamp // 86_400_000 for _, bars, _, _ in barsets if bars), default=None)
    daily_returns = [] if first_day is None else [
        sum(daily_by_symbol[symbol].get(day, 0.0) for symbol in symbols) / len(symbols)
        for day in range(first_day, last_day + 1)
    ]
    strict_daily_returns = [] if first_day is None else [
        sum(strict_daily_by_symbol[symbol].get(day, 0.0) for symbol in symbols) / len(symbols)
        for day in range(first_day, last_day + 1)
    ]
    direction_daily_returns = {
        direction: [] if first_day is None else [
            sum(direction_daily_by_symbol[direction][symbol].get(day, 0.0)
                for symbol in symbols) / len(symbols)
            for day in range(first_day, last_day + 1)
        ]
        for direction in ("long", "short")
    }
    direction_strict_daily_returns = {
        direction: [] if first_day is None else [
            sum(direction_strict_daily_by_symbol[direction][symbol].get(day, 0.0)
                for symbol in symbols) / len(symbols)
            for day in range(first_day, last_day + 1)
        ]
        for direction in ("long", "short")
    }
    curve = curve_metrics(daily_returns, 365)
    strict_curve = curve_metrics(strict_daily_returns, 365)
    total = len(all_events)
    hits = sum(event[4] for event in all_events)
    nonoverlap_events = _nonoverlap_events(all_events)
    nonoverlap = len(nonoverlap_events)
    nonoverlap_hits = sum(event[4] for event in nonoverlap_events)
    by_direction = {
        direction: _direction_summary(
            direction, scored, strict, all_events,
            direction_daily_returns[direction],
            direction_strict_daily_returns[direction],
        )
        for direction in ("long", "short")
    }
    return {
        "status": "unscorable" if len(symbols) < MINIMUM_SYMBOLS or total_audit.get("funding_unscorable_trades", 0) else "completed",
        "symbols": len(symbols), "trades": len(scored), "total_trades": len(trades),
        "m2_signal_count": total, "m2_target_hits": hits,
        "m2_target_first_rate": hits / total if total else None,
        "m2_wilson_lower_95": wilson_lower(hits, total),
        "m2_nonoverlap_signal_count": nonoverlap,
        "m2_nonoverlap_target_hits": nonoverlap_hits,
        "m2_nonoverlap_target_first_rate": nonoverlap_hits / nonoverlap if nonoverlap else None,
        "m2_nonoverlap_wilson_lower_95": wilson_lower(nonoverlap_hits, nonoverlap),
        "by_direction": by_direction,
        "win_rate": stats.win_rate, "wilson_95_lower": stats.wilson_lower_95,
        "payoff_ratio": (stats.average_win / stats.average_loss
                         if stats.average_win and stats.average_loss else None),
        "profit_factor": stats.profit_factor, "expectancy_bps": stats.expectancy_bps,
        "cumulative_return": curve.cumulative_return,
        "max_drawdown": curve.max_drawdown,
        "annualized_sharpe": curve.annualized_sharpe,
        "solvent": curve.solvent,
        "strict_scored_trades": len(strict),
        "strict_win_rate": strict_stats.win_rate,
        "strict_profit_factor": strict_stats.profit_factor,
        "strict_expectancy_bps": strict_stats.expectancy_bps,
        "strict_cumulative_return": strict_curve.cumulative_return,
        "strict_max_drawdown": strict_curve.max_drawdown,
        "strict_annualized_sharpe": strict_curve.annualized_sharpe,
        "strict_solvent": strict_curve.solvent,
        "audit": total_audit,
        "detail": "TRAIN only; no OOS/robustness gate or G verdict",
    }


def _load():
    import data_access
    rows = []
    for symbol, bars, funding in data_access.iter_train_bars(timeframe=TIMEFRAME):
        closed = [bar for bar in bars if bar.complete]
        rows.append((symbol, closed, funding, len(bars) - len(closed)))
        common._check_memory()
    _validate_universe([row[0] for row in rows], _expected_symbols())
    return rows


def _expected_symbols() -> frozenset[str]:
    with UNIVERSE_PATH.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != ["symbol"]:
            raise ValueError("frozen crypto universe schema must contain only symbol")
        symbols = [row["symbol"].strip() for row in reader]
    if not symbols or any(not symbol for symbol in symbols):
        raise ValueError("frozen crypto universe contains an empty symbol")
    if len(symbols) != len(set(symbols)):
        raise ValueError("frozen crypto universe contains duplicate symbols")
    return frozenset(symbols)


def _validate_universe(actual_symbols: list[str],
                       expected_symbols: frozenset[str]) -> None:
    actual = set(actual_symbols)
    if len(actual_symbols) != len(actual):
        raise ValueError("TRAIN loader returned duplicate crypto symbols")
    missing = sorted(expected_symbols - actual)
    extra = sorted(actual - expected_symbols)
    if missing or extra:
        raise ValueError(
            f"TRAIN universe differs from frozen 35 symbols; missing={missing}, extra={extra}"
        )


def _nonoverlap_events(events: list[tuple]) -> list[tuple]:
    """Maximize non-overlapping events per symbol by earliest exit time."""
    selected = []
    last_end: dict[str, int] = {}
    for event in sorted(events, key=lambda row: (row[0], row[2], row[1], row[3])):
        symbol, entry_ts, exit_end_ts = event[:3]
        if entry_ts < last_end.get(symbol, -1):
            continue
        selected.append(event)
        last_end[symbol] = exit_end_ts
    return selected


def _direction_summary(direction: str, scored: list[Trade], strict: list[Trade],
                       events: list[tuple], daily_returns: list[float],
                       strict_daily_returns: list[float]) -> dict:
    direction_trades = [trade for trade in scored
                        if trade.setup.zone.direction == direction]
    direction_strict = [trade for trade in strict
                        if trade.setup.zone.direction == direction]
    direction_events = [event for event in events if event[5] == direction]
    stats = trade_metrics([trade.net_return for trade in direction_trades])
    strict_stats = trade_metrics([trade.net_return for trade in direction_strict])
    curve = curve_metrics(daily_returns, 365)
    strict_curve = curve_metrics(strict_daily_returns, 365)
    target_hits = sum(event[4] for event in direction_events)
    nonoverlap = _nonoverlap_events(direction_events)
    nonoverlap_hits = sum(event[4] for event in nonoverlap)
    return {
        "m2_signal_count": len(direction_events),
        "m2_target_hits": target_hits,
        "m2_target_first_rate": target_hits / len(direction_events) if direction_events else None,
        "m2_wilson_lower_95": wilson_lower(target_hits, len(direction_events)),
        "m2_nonoverlap_signal_count": len(nonoverlap),
        "m2_nonoverlap_target_first_rate": (
            nonoverlap_hits / len(nonoverlap) if nonoverlap else None
        ),
        "m2_nonoverlap_wilson_lower_95": wilson_lower(nonoverlap_hits, len(nonoverlap)),
        "scoreable_trades": len(direction_trades),
        "win_rate": stats.win_rate,
        "wilson_95_lower": stats.wilson_lower_95,
        "average_win_bps": stats.average_win * 10_000 if stats.average_win is not None else None,
        "average_loss_bps": stats.average_loss * 10_000 if stats.average_loss is not None else None,
        "payoff_ratio": (stats.average_win / stats.average_loss
                         if stats.average_win and stats.average_loss else None),
        "breakeven_win_rate": stats.breakeven_win_rate,
        "profit_factor": stats.profit_factor,
        "expectancy_bps": stats.expectancy_bps,
        "cumulative_return": curve.cumulative_return,
        "max_drawdown": curve.max_drawdown,
        "annualized_sharpe": curve.annualized_sharpe,
        "solvent": curve.solvent,
        "strict_scoreable_trades": len(direction_strict),
        "strict_win_rate": strict_stats.win_rate,
        "strict_average_win_bps": (
            strict_stats.average_win * 10_000
            if strict_stats.average_win is not None else None
        ),
        "strict_average_loss_bps": (
            strict_stats.average_loss * 10_000
            if strict_stats.average_loss is not None else None
        ),
        "strict_payoff_ratio": (
            strict_stats.average_win / strict_stats.average_loss
            if strict_stats.average_win and strict_stats.average_loss else None
        ),
        "strict_breakeven_win_rate": strict_stats.breakeven_win_rate,
        "strict_profit_factor": strict_stats.profit_factor,
        "strict_expectancy_bps": strict_stats.expectancy_bps,
        "strict_cumulative_return": strict_curve.cumulative_return,
        "strict_max_drawdown": strict_curve.max_drawdown,
        "strict_annualized_sharpe": strict_curve.annualized_sharpe,
        "strict_solvent": strict_curve.solvent,
    }


def _code_hash() -> str:
    digest = hashlib.sha256()
    for name in ("crypto.py", "search_crypto.py", "search_crypto_r9.py",
                 "data_access.py", "metrics.py", "resource_guard.py",
                 "universe/CRYPTO_35.csv"):
        digest.update((HERE / name).read_bytes())
    return digest.hexdigest()


_LOADED_CODE_SHA = _code_hash()
_LOADED_PREREG_SHA = hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest()


def _verified_loaded_code_hash() -> str:
    """Refuse to run if source files changed after Python imported this module."""
    current = _code_hash()
    if current != _LOADED_CODE_SHA:
        raise RuntimeError("R9 source changed after import; restart with the current code")
    return _LOADED_CODE_SHA


def _verified_loaded_prereg_hash() -> str:
    current = hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest()
    if current != _LOADED_PREREG_SHA:
        raise RuntimeError("R9 preregistration changed after import; restart before TRAIN")
    return _LOADED_PREREG_SHA


def _append(result: dict, fingerprint: str, event_file: str, code_sha: str,
            prereg_sha: str) -> None:
    row = {
        "trial_id": f"R9-crypto-{uuid.uuid4().hex}", "round": "R9-coin",
        "market_group": "crypto",
        "utc_timestamp": datetime.now(timezone.utc).isoformat(),
        "definition": json.dumps(CONFIG, sort_keys=True, separators=(",", ":")),
        "parameter_grid_hash": hashlib.sha256(json.dumps(
            CONFIG, sort_keys=True, separators=(",", ":")
        ).encode()).hexdigest(),
        "code_sha256": code_sha,
        "train_period": "4h bar close <=2023-11-06T16:00:00Z",
        "metric": json.dumps({**result, "train_input_fingerprint": fingerprint,
                               "prereg_sha256": prereg_sha,
                               "event_file": event_file}, sort_keys=True,
                              separators=(",", ":")),
        "rank": "", "notes": f"status={result['status']}; train_input_fingerprint={fingerprint}",
    }
    has_rows = common.CSV_PATH.exists() and common.CSV_PATH.stat().st_size > 0
    if has_rows:
        with common.CSV_PATH.open(newline="", encoding="utf-8") as stream:
            if tuple(next(csv.reader(stream))) != common.FIELDS:
                raise ValueError("TRAIN_TRIALS.csv schema mismatch")
    with common.CSV_PATH.open("a", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=common.FIELDS)
        if not has_rows:
            writer.writeheader()
        writer.writerow(row)


def _already_recorded(code_sha: str, grid_hash: str, fingerprint: str,
                      prereg_sha: str) -> bool:
    if not common.CSV_PATH.exists() or common.CSV_PATH.stat().st_size == 0:
        return False
    csv.field_size_limit(2**31 - 1)
    with common.CSV_PATH.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            if (row.get("round") != "R9-coin"
                    or row.get("code_sha256") != code_sha
                    or row.get("parameter_grid_hash") != grid_hash):
                continue
            try:
                metric = json.loads(row["metric"])
            except (json.JSONDecodeError, TypeError):
                continue
            if (metric.get("train_input_fingerprint") == fingerprint
                    and metric.get("prereg_sha256") == prereg_sha
                    and metric.get("status") in {"completed", "unscorable"}):
                return True
    return False


def run() -> dict:
    from resource_guard import heavy_task

    code_sha = _verified_loaded_code_hash()
    prereg_sha = _verified_loaded_prereg_hash()
    with heavy_task("B-R9-coin"):
        try:
            barsets = _load()
            if (_code_hash() != code_sha
                    or _verified_loaded_prereg_hash() != prereg_sha):
                raise RuntimeError("R9 source/prereg changed while TRAIN data was loading")
        except Exception as exc:
            _append({"status": "failed",
                     "detail": f"load/code verification failed: {type(exc).__name__}: {exc}"},
                    "unavailable", "", code_sha, prereg_sha)
            raise
        fingerprint = common._train_input_fingerprint(TIMEFRAME, barsets)
        grid_hash = hashlib.sha256(json.dumps(
            CONFIG, sort_keys=True, separators=(",", ":")
        ).encode()).hexdigest()
        if _already_recorded(code_sha, grid_hash, fingerprint, prereg_sha):
            raise RuntimeError(
                "matching R9 code/grid/TRAIN/prereg fingerprint already recorded"
            )
        cache = Path(os.environ.get("TRADING_DATA_DIR", Path.home() / "CODE/trading_data"))
        output = cache / "cache/orderblock"
        event_path = output / f"r9-events-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:8]}.jsonl"
        stream = None
        trial_started = False
        try:
            output.mkdir(parents=True, exist_ok=True)
            stream = event_path.open("x", encoding="utf-8")
            trial_started = True
            result = _trial(barsets, event_writer=stream)
            stream.flush()
            os.fsync(stream.fileno())
            stream.close()
            stream = None
        except Exception as exc:
            details = f"trial failed: {type(exc).__name__}: {exc}"
            if stream is not None:
                try:
                    stream.flush()
                    os.fsync(stream.fileno())
                except Exception as sync_exc:
                    details += f"; event sync failed: {type(sync_exc).__name__}: {sync_exc}"
                try:
                    stream.close()
                except Exception as close_exc:
                    details += f"; event close failed: {type(close_exc).__name__}: {close_exc}"
                stream = None
            if not trial_started:
                details = f"output setup failed: {type(exc).__name__}: {exc}"
                failure = {"status": "failed", "detail": details}
                _append(failure, fingerprint, "", code_sha, prereg_sha)
            else:
                failure = {"status": "failed", "detail": details}
                _append(failure, fingerprint, str(event_path), code_sha, prereg_sha)
            raise
        finally:
            if stream is not None:
                stream.close()
        _append(result, fingerprint, str(event_path), code_sha, prereg_sha)
        print(json.dumps({**result, "event_file": str(event_path)}, sort_keys=True), flush=True)
        return result


def main() -> None:
    argparse.ArgumentParser(description=__doc__).parse_args()
    run()


if __name__ == "__main__":
    main()
