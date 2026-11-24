"""Preregistered R4 crypto order-block TRAIN grid; TEST is never opened here."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

import search_crypto as common
from crypto import r4_zones, simulate_orderblock, trade_daily_pnl
from metrics import curve_metrics, trade_metrics, wilson_lower

HERE = Path(__file__).resolve().parent
DEFINITIONS = ("displacement", "bos_origin", "volume_displacement")
TIMEFRAMES = ("15m", "1h", "4h")
DIRECTIONS = ("long", "short")
DEADLINES = (24, 48)
REWARD_R = (1.5, 2.0)
MINIMUM_SYMBOLS = 30
FUNDING_ORDER_POLICY = "adverse_only"
CONFIGS = tuple({
    "definition": definition, "timeframe": timeframe, "direction": direction,
    "deadline": deadline, "reward_r": reward_r,
    "minimum_symbols": MINIMUM_SYMBOLS,
    "funding_order_policy": FUNDING_ORDER_POLICY,
} for definition in DEFINITIONS for timeframe in TIMEFRAMES
  for direction in DIRECTIONS for deadline in DEADLINES for reward_r in REWARD_R)


def _load_timeframe(loader, timeframe):
    barsets = []
    for symbol, bars, funding in loader(timeframe=timeframe):
        closed = [bar for bar in bars if bar.complete]
        barsets.append((symbol, closed, funding, len(bars) - len(closed)))
        common._check_memory()
    return barsets


def _m2_metrics(events: Sequence[tuple[str, int, int, int, bool]]) -> dict:
    """Score target-first labels overall and per-symbol non-overlapping intervals."""
    total_hits = sum(event[4] for event in events)
    last_exit_end = {}
    nonoverlap_hits = nonoverlap_count = 0
    for symbol, entry_ts, exit_end_ts, signal_index, target_first in sorted(
            events, key=lambda event: (event[0], event[1], event[3])):
        if entry_ts < last_exit_end.get(symbol, -1):
            continue
        nonoverlap_count += 1
        nonoverlap_hits += target_first
        last_exit_end[symbol] = exit_end_ts
    total = len(events)
    return {
        "m2_signal_count": total,
        "m2_target_hits": total_hits,
        "m2_target_first_rate": total_hits / total if total else None,
        "m2_wilson_lower_95": wilson_lower(total_hits, total),
        "m2_nonoverlap_signal_count": nonoverlap_count,
        "m2_nonoverlap_target_hits": nonoverlap_hits,
        "m2_nonoverlap_target_first_rate": (
            nonoverlap_hits / nonoverlap_count if nonoverlap_count else None
        ),
        "m2_nonoverlap_wilson_lower_95": wilson_lower(nonoverlap_hits, nonoverlap_count),
    }


def _trial(config, barsets, zone_cache):
    returns = []
    strict_returns = []
    symbol_daily = {}
    strict_symbol_daily = {}
    symbols = []
    m2_events = []
    total_trades = unscorable = strict_unscorable = ambiguous_events = 0
    time_exit_censored = right_censored = 0
    missing_mark_symbols = set()
    coverage_gap_symbols = set()
    fallbacks = 0
    first_day = last_day = None
    duration = {"15m": 900_000, "1h": 3_600_000, "4h": 14_400_000}[config["timeframe"]]

    for symbol, bars, funding, _incomplete in barsets:
        if not bars:
            continue
        symbols.append(symbol)
        fallbacks += sum(event.used_candle_close_fallback for event in funding.values())
        if any(not common.funding_price_available(event) for event in funding.values()):
            missing_mark_symbols.add(symbol)
        if any(event.coverage_gap for event in funding.values()):
            coverage_gap_symbols.add(symbol)
        symbol_daily[symbol] = {}
        strict_symbol_daily[symbol] = {}
        start = bars[0].timestamp // 86_400_000
        end = bars[-1].timestamp // 86_400_000
        first_day = start if first_day is None else min(first_day, start)
        last_day = end if last_day is None else max(last_day, end)

        key = (symbol, config["timeframe"], config["definition"])
        if key not in zone_cache:
            zone_cache[key] = r4_zones(bars, config["definition"])
        funding_in_range = common._funding_by_timestamp(bars, funding, duration)
        audit = {}
        trades = simulate_orderblock(
            bars, config["definition"], config["direction"],
            deadline=config["deadline"], reward_r=config["reward_r"],
            funding=funding_in_range, r4_definition=True,
            funding_order_policy=FUNDING_ORDER_POLICY,
            bar_duration_ms=duration,
            candidate_zones=zone_cache[key], audit=audit,
        )
        time_exit_censored += audit.get("time_exit_censored", 0)
        right_censored += audit.get("right_censored", 0)
        total_trades += len(trades)
        for trade in trades:
            entry_ts = bars[trade.setup.entry_index].timestamp
            exit_end_ts = bars[trade.exit_index].timestamp + duration
            m2_events.append((
                symbol, entry_ts, exit_end_ts, trade.setup.zone.signal_index,
                trade.exit_reason == "target",
            ))
            ambiguous_events += trade.ambiguous_funding_events
            strict_unknown = trade.net_return is None or trade.ambiguous_funding_events > 0
            if trade.net_return is None:
                unscorable += 1
                strict_unscorable += 1
                continue
            daily = trade_daily_pnl(
                bars, trade, funding=funding_in_range, bar_duration_ms=duration,
            )
            if daily is None:
                unscorable += 1
                strict_unscorable += 1
                continue
            if strict_unknown:
                strict_unscorable += 1
            else:
                strict_returns.append(trade.net_return)
                for day, value in daily.items():
                    strict_symbol_daily[symbol][day] = (
                        strict_symbol_daily[symbol].get(day, 0.0) + value
                    )
            returns.append(trade.net_return)
            for day, value in daily.items():
                symbol_daily[symbol][day] = symbol_daily[symbol].get(day, 0.0) + value

    n_symbols = len(symbols)
    if first_day is None or last_day is None:
        daily_returns = []
    else:
        daily_returns = [
            sum(symbol_daily[symbol].get(day, 0.0) for symbol in symbols) / n_symbols
            for day in range(first_day, last_day + 1)
        ] if n_symbols else []
    trade_stats = trade_metrics(returns)
    curve = curve_metrics(daily_returns, 365)
    strict_trade_stats = trade_metrics(strict_returns)
    strict_curve = None
    if strict_returns:
        strict_daily_returns = [
            sum(strict_symbol_daily[symbol].get(day, 0.0) for symbol in symbols) / n_symbols
            for day in range(first_day, last_day + 1)
        ] if n_symbols else []
        strict_curve = curve_metrics(strict_daily_returns, 365)
    payoff = (trade_stats.average_win / trade_stats.average_loss
              if trade_stats.average_win and trade_stats.average_loss else None)
    status = "unscorable" if n_symbols < MINIMUM_SYMBOLS or unscorable else "completed"
    return {
        "status": status, "symbols": n_symbols, "trades": total_trades - unscorable,
        "total_trades": total_trades, "unscorable_funding_trades": unscorable,
        "strict_unscorable_funding_trades": strict_unscorable,
        "strict_scoreable_trades": total_trades - strict_unscorable,
        "ambiguous_funding_events": ambiguous_events,
        "symbols_unresolved_funding_prices": sorted(missing_mark_symbols),
        "symbols_with_funding_coverage_gaps": sorted(coverage_gap_symbols),
        "funding_close_fallbacks": fallbacks,
        "time_exit_censored_setups": time_exit_censored,
        "right_censored_setups": right_censored,
        "win_rate": trade_stats.win_rate,
        "wilson_95_lower": trade_stats.wilson_lower_95,
        "payoff_ratio": payoff, "profit_factor": trade_stats.profit_factor,
        "expectancy_bps": trade_stats.expectancy_bps,
        "cumulative_return": curve.cumulative_return,
        "max_drawdown": curve.max_drawdown,
        "annualized_sharpe": curve.annualized_sharpe,
        "solvent": curve.solvent,
        "strict_scored_trades": len(strict_returns),
        "strict_win_rate": strict_trade_stats.win_rate,
        "strict_wilson_95_lower": strict_trade_stats.wilson_lower_95,
        "strict_profit_factor": strict_trade_stats.profit_factor,
        "strict_expectancy_bps": strict_trade_stats.expectancy_bps,
        "strict_cumulative_return": strict_curve.cumulative_return if strict_curve else None,
        "strict_max_drawdown": strict_curve.max_drawdown if strict_curve else None,
        "strict_annualized_sharpe": strict_curve.annualized_sharpe if strict_curve else None,
        "strict_solvent": strict_curve.solvent if strict_curve else None,
        **_m2_metrics(m2_events),
        "detail": (f"{n_symbols} symbols; {unscorable} funding-unscorable trades"
                   if status == "unscorable" else "TRAIN only; not a G decision"),
    }


def _code_hash():
    digest = hashlib.sha256()
    for name in ("crypto.py", "search_crypto.py", "search_crypto_r4.py",
                 "data_access.py", "metrics.py", "resource_guard.py"):
        digest.update((HERE / name).read_bytes())
    return digest.hexdigest()


def _append(config, result, fingerprint, grid_hash, code_sha):
    config_json = json.dumps(config, sort_keys=True, separators=(",", ":"))
    config_hash = hashlib.sha256(config_json.encode()).hexdigest()
    metric = {**result, "train_input_fingerprint": fingerprint}
    record = {
        "trial_id": f"R4-crypto-{config_hash[:12]}-{uuid.uuid4().hex}",
        "round": "R4-coin", "market_group": "crypto",
        "utc_timestamp": datetime.now(timezone.utc).isoformat(),
        "definition": config_json, "parameter_grid_hash": grid_hash,
        "code_sha256": code_sha,
        "train_period": "bar close <=2023-11-06T16:00:00Z",
        "metric": json.dumps(metric, sort_keys=True, separators=(",", ":")),
        "rank": "", "notes": f"status={result['status']}; train_input_fingerprint={fingerprint}",
    }
    has_rows = common.CSV_PATH.exists() and common.CSV_PATH.stat().st_size > 0
    if has_rows:
        with common.CSV_PATH.open(newline="", encoding="utf-8") as stream:
            if tuple(next(csv.reader(stream))) != common.FIELDS:
                raise ValueError("TRAIN_TRIALS.csv schema mismatch; R4 row not appended")
    with common.CSV_PATH.open("a", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=common.FIELDS)
        if not has_rows:
            writer.writeheader()
        writer.writerow(record)


def _registered_trials(grid_hash, code_sha, timeframe, fingerprint):
    if not common.CSV_PATH.exists() or common.CSV_PATH.stat().st_size == 0:
        return set()
    csv.field_size_limit(sys.maxsize)
    registered = set()
    with common.CSV_PATH.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            if (row["round"] != "R4-coin"
                    or row["parameter_grid_hash"] != grid_hash
                    or row["code_sha256"] != code_sha):
                continue
            try:
                config = json.loads(row["definition"])
                metric = json.loads(row["metric"])
            except (json.JSONDecodeError, TypeError):
                continue
            if (isinstance(config, dict) and isinstance(metric, dict)
                    and config.get("timeframe") == timeframe
                    and metric.get("train_input_fingerprint") == fingerprint):
                registered.add(row["definition"])
    return registered


def run():
    import data_access

    loader = getattr(data_access, "iter_train_bars", None)
    if loader is None:
        raise RuntimeError("TRAIN-only data loader is unavailable")
    grid_hash = hashlib.sha256(json.dumps(
        CONFIGS, sort_keys=True, separators=(",", ":")
    ).encode()).hexdigest()
    code_sha = _code_hash()
    completed = 0
    for timeframe in TIMEFRAMES:
        barsets = _load_timeframe(loader, timeframe)
        fingerprint = common._train_input_fingerprint(timeframe, barsets)
        registered = _registered_trials(grid_hash, code_sha, timeframe, fingerprint)
        zone_cache = {}
        for config in CONFIGS:
            if config["timeframe"] != timeframe:
                continue
            config_json = json.dumps(config, sort_keys=True, separators=(",", ":"))
            if config_json in registered:
                completed += 1
                print(f"[{completed}/{len(CONFIGS)}] already recorded: {config_json}", flush=True)
                continue
            try:
                result = _trial(config, barsets, zone_cache)
            except MemoryError as exc:
                result = {"status": "failed", "detail": f"MemoryError: {exc}"}
                _append(config, result, fingerprint, grid_hash, code_sha)
                raise
            except Exception as exc:
                result = {"status": "failed", "detail": f"{type(exc).__name__}: {exc}"}
            _append(config, result, fingerprint, grid_hash, code_sha)
            registered.add(config_json)
            completed += 1
            print(f"[{completed}/{len(CONFIGS)}] {config['definition']} {timeframe} "
                  f"{config['direction']} D{config['deadline']} R{config['reward_r']}: "
                  f"{result['status']} scored={result.get('trades', 0)} "
                  f"unscorable={result.get('unscorable_funding_trades', 0)}",
                  flush=True)
        del barsets, zone_cache
    return completed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    from resource_guard import heavy_task
    with heavy_task("B-R4-coin"):
        count = run()
    if count != len(CONFIGS):
        raise RuntimeError(f"expected {len(CONFIGS)} R4 trials, appended {count}")


if __name__ == "__main__":
    main()
