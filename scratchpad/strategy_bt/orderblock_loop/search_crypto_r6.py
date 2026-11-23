"""Preregistered R6 crypto order-block TRAIN-only search."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import search_crypto as common
from crypto import (Setup, _atr, enforce_single_active_zone, r4_zones,
                    simulate_trade, trade_daily_pnl)
from metrics import curve_metrics, trade_metrics

HERE = Path(__file__).resolve().parent
TIMEFRAME = "4h"
DURATION_MS = 14_400_000
MINIMUM_SYMBOLS = 30
FUNDING_ORDER_POLICY = "adverse_only"
ATR_LOOKBACK = 252
ATR_MINIMUM_HISTORY = 30
COMMON = {
    "definition": "bos_origin", "timeframe": TIMEFRAME, "direction": "long",
    "deadline": 48, "reward_r": 2.0, "minimum_symbols": MINIMUM_SYMBOLS,
    "funding_order_policy": FUNDING_ORDER_POLICY,
}
CONFIGS = tuple(
    {**COMMON, "experiment": "R6-A", "atr_bin": atr_bin,
     "stop_buffer_atr": buffer, "max_holding_bars": holding}
    for atr_bin in ("low", "high") for buffer in (0.05, 0.20)
    for holding in (24, 48)
) + tuple(
    {**COMMON, "experiment": "R6-B", "close_location_threshold": threshold,
     "max_holding_bars": holding}
    for threshold in (0.60, 0.80) for holding in (24, 48)
)


def _load_timeframe(loader):
    barsets = []
    for symbol, bars, funding in loader(timeframe=TIMEFRAME):
        closed = [bar for bar in bars if bar.complete]
        barsets.append((symbol, closed, funding, len(bars) - len(closed)))
        common._check_memory()
    return barsets


def _atr_fraction(bars, index):
    atr = _atr(bars, index)
    close = bars[index].close
    return atr / close if atr is not None and close > 0 else None


def _atr_bin(bars, signal_index):
    """Classify with the trailing 252 completed bars, excluding this signal."""
    current = _atr_fraction(bars, signal_index)
    start = max(0, signal_index - ATR_LOOKBACK)
    history = [value for index in range(start, signal_index)
               if (value := _atr_fraction(bars, index)) is not None]
    if current is None or len(history) < ATR_MINIMUM_HISTORY:
        return None
    history.sort()
    middle = len(history) // 2
    median = (history[middle] if len(history) % 2
              else (history[middle - 1] + history[middle]) / 2)
    return "low" if current <= median else "high"


def _close_location(bar):
    width = bar.high - bar.low
    return None if width <= 0 else (bar.close - bar.low) / width


def _setup_for_zone(bars, zone, config, audit=None):
    """Find the first retest, optionally requiring the next bar to confirm."""
    signal = zone.signal_index
    last = min(len(bars) - 1, signal + config["deadline"])
    for retest_index in range(signal + 1, last + 1):
        retest = bars[retest_index]
        invalid = retest.low <= zone.low
        overlap = retest.low <= zone.high and retest.high >= zone.low
        if invalid:
            return None
        if not overlap:
            continue
        if config["experiment"] == "R6-B":
            confirm_index = retest_index + 1
            if confirm_index >= len(bars) or not bars[confirm_index].complete:
                if audit is not None:
                    audit["right_censored_confirmation_setups"] += 1
                return None
            location = _close_location(bars[confirm_index])
            if location is None or location < config["close_location_threshold"]:
                return None
            entry_index = confirm_index + 1
        else:
            entry_index = retest_index + 1
        if entry_index >= len(bars) or not bars[entry_index].complete:
            if audit is not None:
                audit["right_censored_setups"] += 1
            return None
        entry = bars[entry_index].open
        if entry <= zone.low:
            return None
        buffer = config.get("stop_buffer_atr", 0.10)
        stop = zone.low - buffer * zone.atr_at_signal
        risk = entry - stop
        if risk <= 0:
            return None
        return Setup(zone, entry_index, entry, stop, entry + 2.0 * risk)
    if signal + config["deadline"] >= len(bars):
        if audit is not None:
            audit["right_censored_setups"] += 1
    return None


def _trades_for_symbol(bars, funding, config, zones, atr_bins):
    zones = [zone for zone in zones if zone.direction == "long"]
    if config["experiment"] == "R6-A":
        zones = [zone for zone in zones
                 if atr_bins.get(zone.signal_index) == config["atr_bin"]]
    trades = []
    audit = {"right_censored_setups": 0,
             "right_censored_confirmation_setups": 0,
             "time_exit_censored_setups": 0}
    busy_until = -1
    for zone in zones:
        if zone.signal_index <= busy_until:
            continue
        setup = _setup_for_zone(bars, zone, config, audit)
        if setup is None:
            continue
        trade = simulate_trade(
            bars, setup, funding=funding,
            max_holding_bars=config["max_holding_bars"],
            bar_duration_ms=DURATION_MS,
            funding_order_policy=FUNDING_ORDER_POLICY,
        )
        if trade is None:
            audit["time_exit_censored_setups"] += 1
            continue
        trades.append(trade)
        busy_until = trade.exit_index
    return trades, audit


def _trial(config, barsets, prepared=None):
    returns = []
    symbol_daily = {}
    scored_trades = 0
    total_trades = 0
    unscorable = 0
    atr_history_insufficient = 0
    censored = {"right_censored_setups": 0,
                "right_censored_confirmation_setups": 0,
                "time_exit_censored_setups": 0}
    symbols = []
    incomplete_excluded = 0
    for symbol, bars, funding, incomplete in barsets:
        incomplete_excluded += incomplete
        if not bars:
            continue
        symbols.append(symbol)
        symbol_daily[symbol] = {}
        if prepared is None:
            zones = r4_zones(bars, "bos_origin")
            atr_bins = {zone.signal_index: _atr_bin(bars, zone.signal_index)
                        for zone in zones}
        else:
            zones, atr_bins = prepared[symbol]
        if config["experiment"] == "R6-A":
            atr_history_insufficient += sum(
                atr_bins.get(zone.signal_index) is None for zone in zones
            )
        scoped_funding = common._funding_by_timestamp(bars, funding, DURATION_MS)
        trades, audit = _trades_for_symbol(
            bars, scoped_funding, config, zones, atr_bins
        )
        for key in censored:
            censored[key] += audit[key]
        total_trades += len(trades)
        for trade in trades:
            if trade.net_return is None:
                unscorable += 1
                continue
            daily = trade_daily_pnl(
                bars, trade,
                funding=scoped_funding,
                bar_duration_ms=DURATION_MS,
            )
            if daily is None:
                unscorable += 1
                continue
            scored_trades += 1
            returns.append(trade.net_return)
            for day, value in daily.items():
                symbol_daily[symbol][day] = symbol_daily[symbol].get(day, 0.0) + value
        common._check_memory()

    if symbols:
        days = [day for values in symbol_daily.values() for day in values]
        daily_returns = [
            sum(symbol_daily[symbol].get(day, 0.0) for symbol in symbols) / len(symbols)
            for day in range(min(days), max(days) + 1)
        ] if days else []
    else:
        daily_returns = []
    stats = trade_metrics(returns)
    curve = curve_metrics(daily_returns, 365)
    status = "completed"
    reasons = []
    if len(symbols) < MINIMUM_SYMBOLS:
        status = "unscorable"
        reasons.append(f"symbols {len(symbols)} < {MINIMUM_SYMBOLS}")
    if unscorable:
        status = "unscorable"
        reasons.append(f"funding/daily unscorable trades={unscorable}")
    return {
        "status": status, "symbols": len(symbols), "trades": scored_trades,
        "total_trades": total_trades, "unscorable_funding_trades": unscorable,
        **censored,
        "atr_history_insufficient_signals": atr_history_insufficient,
        "incomplete_bars_excluded": incomplete_excluded,
        "win_rate": stats.win_rate, "wilson_95_lower": stats.wilson_lower_95,
        "profit_factor": stats.profit_factor, "expectancy_bps": stats.expectancy_bps,
        "cumulative_return": curve.cumulative_return,
        "max_drawdown": curve.max_drawdown,
        "annualized_sharpe": curve.annualized_sharpe,
        "train_input_fingerprint": common._train_input_fingerprint(TIMEFRAME, barsets),
        "detail": "; ".join(reasons) if reasons else "TRAIN only; not a G decision",
    }


def _code_hash():
    digest = hashlib.sha256()
    for name in ("crypto.py", "search_crypto.py", "search_crypto_r6.py",
                 "data_access.py", "metrics.py", "resource_guard.py"):
        digest.update((HERE / name).read_bytes())
    return digest.hexdigest()


def _append(config, result, grid_hash, code_sha):
    config_json = json.dumps(config, sort_keys=True, separators=(",", ":"))
    config_hash = hashlib.sha256(config_json.encode()).hexdigest()
    metric = json.dumps(result, sort_keys=True, separators=(",", ":"))
    record = {
        "trial_id": f"R6-crypto-{config_hash[:12]}-{uuid.uuid4().hex}",
        "round": "R6-coin", "market_group": "crypto",
        "utc_timestamp": datetime.now(timezone.utc).isoformat(),
        "definition": config_json, "parameter_grid_hash": grid_hash,
        "code_sha256": code_sha, "train_period": "bar close <=2023-11-06T16:00:00Z",
        "metric": metric, "rank": "", "notes": f"status={result['status']}; TRAIN only",
    }
    has_rows = common.CSV_PATH.exists() and common.CSV_PATH.stat().st_size > 0
    if has_rows:
        with common.CSV_PATH.open(newline="", encoding="utf-8") as stream:
            if tuple(next(csv.reader(stream))) != common.FIELDS:
                raise ValueError("TRAIN_TRIALS.csv schema mismatch; R6 row not appended")
    with common.CSV_PATH.open("a", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=common.FIELDS)
        if not has_rows:
            writer.writeheader()
        writer.writerow(record)


def configs_for(experiment):
    if experiment not in ("R6-A", "R6-B"):
        raise ValueError("experiment must be R6-A or R6-B")
    return tuple(config for config in CONFIGS if config["experiment"] == experiment)


def run(experiment="R6-A"):
    import data_access

    loader = getattr(data_access, "iter_train_bars", None)
    if loader is None:
        raise RuntimeError("TRAIN-only data loader is unavailable")
    grid_hash = hashlib.sha256(json.dumps(
        CONFIGS, sort_keys=True, separators=(",", ":")
    ).encode()).hexdigest()
    code_sha = _code_hash()
    selected = configs_for(experiment)
    barsets = _load_timeframe(loader)
    prepared = {}
    for symbol, bars, _funding, _incomplete in barsets:
        if bars:
            zones = enforce_single_active_zone(
                bars, r4_zones(bars, "bos_origin"), deadline=COMMON["deadline"]
            )
            prepared[symbol] = (
                zones,
                {zone.signal_index: _atr_bin(bars, zone.signal_index)
                 for zone in zones},
            )
            common._check_memory()
    completed = 0
    for config in selected:
        try:
            result = _trial(config, barsets, prepared)
        except MemoryError as exc:
            result = {"status": "failed", "detail": f"MemoryError: {exc}"}
            _append(config, result, grid_hash, code_sha)
            raise
        except Exception as exc:
            result = {"status": "failed", "detail": f"{type(exc).__name__}: {exc}"}
        _append(config, result, grid_hash, code_sha)
        completed += 1
        print(f"[{completed}/{len(selected)}] {config['experiment']} {config}: "
              f"{result['status']} scored={result.get('trades', 0)}", flush=True)
    return completed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", choices=("R6-A", "R6-B"), default="R6-A")
    args = parser.parse_args()
    from resource_guard import heavy_task
    with heavy_task(f"B-{args.experiment}-coin"):
        count = run(args.experiment)
    expected = len(configs_for(args.experiment))
    if count != expected:
        raise RuntimeError(f"expected {expected} {args.experiment} trials, appended {count}")


if __name__ == "__main__":
    main()
