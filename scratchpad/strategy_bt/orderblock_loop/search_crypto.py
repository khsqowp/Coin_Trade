"""Train-only crypto order-block grid search.

The data access contract is intentionally narrow: data_access.iter_train_bars
must yield (symbol, bars, funding_events) for one timeframe and shard.  It must
enforce the registered train cutoff and must never expose test rows.
The recorded net returns come from crypto.simulate_trade, which applies the
PREREG arithmetic rule: price return + funding cash flow - two one-way costs.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import resource
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from crypto import active_zones, first_retest, simulate_trade, trade_daily_pnl  # noqa: E402
from metrics import trade_metrics  # noqa: E402

DEFINITIONS = ("displacement", "bos_origin", "volume_displacement")
TIMEFRAMES = ("15m", "1h", "4h")
DIRECTIONS = ("long", "short")
DEADLINES = (24, 48)
REWARD_R = (1.5, 2.0)
MEMORY_LIMIT_BYTES = 3 * 1024**3
CSV_PATH = HERE / "TRAIN_TRIALS.csv"
FIELDS = ("trial_id", "round", "market_group", "utc_timestamp", "definition",
          "parameter_grid_hash", "code_sha256", "train_period", "metric", "rank", "notes")


def _check_memory() -> None:
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # macOS reports ru_maxrss in bytes; Linux reports it in KiB.
    peak_bytes = peak if sys.platform == "darwin" else peak * 1024
    if peak_bytes > MEMORY_LIMIT_BYTES:
        raise MemoryError(f"peak RSS exceeded 3 GiB: {peak_bytes} bytes")


def _drawdown(returns: list[float]) -> float | None:
    equity = peak = 1.0
    worst = 0.0
    for result in returns:
        equity += result
        if equity <= 0:
            return 1.0
        peak = max(peak, equity)
        worst = max(worst, (peak - equity) / peak)
    return worst if returns else None


def _trial_id(config: dict[str, object]) -> str:
    raw = json.dumps(config, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def _funding_by_timestamp(bars, funding):
    """Keep exact settlement timestamps inside the candle series' time span."""
    if not bars:
        return {}
    first, last = bars[0].timestamp, bars[-1].timestamp
    relevant = {timestamp: event for timestamp, event in funding.items()
                if first <= timestamp <= last}
    if any(timestamp != event.timestamp for timestamp, event in relevant.items()):
        raise ValueError("funding key must equal its exact settlement timestamp")
    return relevant


def _append(row: dict[str, object]) -> None:
    config = {key: row[key] for key in
              ("definition", "timeframe", "direction", "deadline", "reward_r")}
    config_json = json.dumps(config, sort_keys=True, separators=(",", ":"))
    config_hash = _trial_id(config)
    grid = [{"definition": definition, "timeframe": timeframe,
             "direction": direction, "deadline": deadline, "reward_r": reward}
            for timeframe in TIMEFRAMES for definition in DEFINITIONS
            for direction in DIRECTIONS for deadline in DEADLINES for reward in REWARD_R]
    grid_hash = hashlib.sha256(json.dumps(grid, sort_keys=True,
                                           separators=(",", ":")).encode()).hexdigest()
    code_hash = hashlib.sha256()
    for filename in ("crypto.py", "search_crypto.py", "data_access.py", "metrics.py",
                     "resource_guard.py"):
        code_hash.update((HERE / filename).read_bytes())
    metric = {key: row.get(key) for key in
              ("symbols", "trades", "win_rate", "wilson_95_lower", "payoff_ratio",
               "profit_factor", "expectancy_bps", "max_drawdown",
               "incomplete_bars_excluded", "unscorable_funding_trades",
               "time_exit_censored_setups", "symbols_excluded_missing_funding_marks",
               "symbols_missing_funding_marks", "symbols_excluded_funding_gap",
               "symbols_funding_gap", "symbols_without_bars",
               "status", "detail")}
    now = str(row["timestamp_utc"])
    record = {
        "trial_id": f"R2-crypto-{config_hash[:16]}", "round": "R2",
        "market_group": "crypto", "utc_timestamp": now,
        "definition": config_json, "parameter_grid_hash": grid_hash,
        "code_sha256": code_hash.hexdigest(),
        "train_period": "<=2023-11-06T12:00:00Z (common cutoff inclusive)",
        "metric": json.dumps(metric, sort_keys=True, separators=(",", ":")),
        "rank": "", "notes": f"attempted_config_sha256={config_hash}; status={row['status']}",
    }
    exists = CSV_PATH.exists()
    if exists and CSV_PATH.stat().st_size:
        with CSV_PATH.open(newline="", encoding="utf-8") as stream:
            existing_fields = next(csv.reader(stream))
        if tuple(existing_fields) != FIELDS:
            raise ValueError(f"trial ledger schema mismatch: {existing_fields!r}")
    with CSV_PATH.open("a", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        if not exists:
            writer.writeheader()
        writer.writerow(record)


def _run_trial(config: dict[str, object], barsets, zone_cache) -> dict[str, object]:
    trade_returns: list[float] = []
    symbols_seen: list[str] = []
    incomplete_bars_excluded = 0
    unscorable_funding_trades = 0
    time_exit_censored_setups = 0
    mark_missing_symbols: set[str] = set()
    funding_gap_symbols: set[str] = set()
    valid_symbols: set[str] = set()
    empty_symbols: set[str] = set()
    symbol_day_pnl: dict[str, dict[int, float]] = {}
    first_day: int | None = None
    last_day: int | None = None
    for symbol, bars, funding, excluded_count in barsets:
        _check_memory()
        if not bars:
            empty_symbols.add(symbol)
            continue
        if any(event.coverage_gap for event in funding.values()):
            funding_gap_symbols.add(symbol)
            continue
        if any(event.mark_price is None for event in funding.values()):
            mark_missing_symbols.add(symbol)
            continue
        symbols_seen.append(symbol)
        valid_symbols.add(symbol)
        incomplete_bars_excluded += excluded_count
        if bars:
            symbol_day_pnl[symbol] = {}
            first_day = min(first_day, bars[0].timestamp // 86_400_000) if first_day is not None else bars[0].timestamp // 86_400_000
            last_day = max(last_day, bars[-1].timestamp // 86_400_000) if last_day is not None else bars[-1].timestamp // 86_400_000
        cache_key = (symbol, config["definition"], config["deadline"])
        zones = zone_cache.get(cache_key)
        if zones is None:
            zones = active_zones(
                bars, config["definition"], deadline=config["deadline"],
                displacement_atr=1.5, volume_multiple=1.5,
            )
            zone_cache[cache_key] = zones
        funding_by_timestamp = _funding_by_timestamp(bars, funding)
        next_free = -1
        for zone in zones:
            if zone.direction != config["direction"] or zone.signal_index < next_free:
                continue
            setup = first_retest(bars, zone, deadline=config["deadline"],
                                 reward_r=config["reward_r"], validated=True)
            if setup is None:
                continue
            trade = simulate_trade(
                bars, setup, funding=funding_by_timestamp,
                bar_duration_ms={"15m": 900_000, "1h": 3_600_000,
                                 "4h": 14_400_000}[config["timeframe"]],
                validated=True,
            )
            if trade is None:
                time_exit_censored_setups += 1
            else:
                if trade.net_return is None:
                    unscorable_funding_trades += 1
                else:
                    trade_returns.append(trade.net_return)
                    daily_pnl = trade_daily_pnl(
                        bars, trade, funding=funding_by_timestamp,
                        bar_duration_ms={"15m": 900_000, "1h": 3_600_000,
                                         "4h": 14_400_000}[config["timeframe"]],
                    )
                    if daily_pnl is None:
                        unscorable_funding_trades += 1
                        trade_returns.pop()
                    else:
                        for utc_day, value in daily_pnl.items():
                            symbol_day_pnl[symbol][utc_day] = symbol_day_pnl[symbol].get(utc_day, 0.0) + value
                next_free = trade.exit_index + 1
    metrics = trade_metrics(trade_returns)
    payoff = (metrics.average_win / metrics.average_loss
              if metrics.average_win is not None and metrics.average_loss else None)
    portfolio_daily = []
    if symbols_seen and first_day is not None and last_day is not None:
        portfolio_daily = [
            sum(symbol_day_pnl.get(symbol, {}).get(day, 0.0) for symbol in symbols_seen)
            / len(symbols_seen)
            for day in range(first_day, last_day + 1)
        ]
    return {
        "symbols": len(set(symbols_seen)), "trades": metrics.count,
        "symbols_excluded_missing_funding_marks": len(mark_missing_symbols),
        "symbols_missing_funding_marks": sorted(mark_missing_symbols),
        "symbols_excluded_funding_gap": len(funding_gap_symbols),
        "symbols_funding_gap": sorted(funding_gap_symbols),
        "symbols_without_bars": len(empty_symbols),
        "win_rate": metrics.win_rate, "wilson_95_lower": metrics.wilson_lower_95,
        "payoff_ratio": payoff, "profit_factor": metrics.profit_factor,
        "expectancy_bps": metrics.expectancy_bps,
        "max_drawdown": _drawdown(portfolio_daily),
        "incomplete_bars_excluded": incomplete_bars_excluded,
        "unscorable_funding_trades": unscorable_funding_trades,
        "time_exit_censored_setups": time_exit_censored_setups,
        "status": ("unscorable" if unscorable_funding_trades or len(valid_symbols) < 30
                   else "completed"),
        "detail": "; ".join(filter(None, (
            f"{unscorable_funding_trades} trades crossed missing funding marks"
            if unscorable_funding_trades else "",
            f"excluded {len(mark_missing_symbols)} symbols with missing funding marks"
            if mark_missing_symbols else "",
            f"excluded {len(funding_gap_symbols)} symbols with funding cadence gaps"
            if funding_gap_symbols else "",
            f"{len(empty_symbols)} symbols have no train bars"
            if empty_symbols else "",
            f"only {len(valid_symbols)} valid symbols; need 30"
            if len(valid_symbols) < 30 else "",
        ))),
    }


def _run() -> int:
    try:
        resource.setrlimit(resource.RLIMIT_AS, (MEMORY_LIMIT_BYTES, MEMORY_LIMIT_BYTES))
    except (OSError, ValueError):
        # macOS may report an unusable RLIMIT_AS infinity sentinel; _check_memory
        # remains the hard stop at every symbol/trial boundary.
        pass
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shard", default="0/1", help="stable shard index/count, e.g. 0/4")
    args = parser.parse_args()
    try:
        shard_index, shard_count = (int(part) for part in args.shard.split("/", 1))
    except (ValueError, TypeError):
        parser.error("--shard must be INDEX/COUNT")
    if shard_count < 1 or not 0 <= shard_index < shard_count:
        parser.error("shard must satisfy 0 <= INDEX < COUNT")
    try:
        import data_access
    except ImportError as exc:
        print(f"data_access unavailable: {exc}", file=sys.stderr)
        return 2
    loader = getattr(data_access, "iter_train_bars", None)
    if loader is None:
        print("data_access.iter_train_bars contract missing", file=sys.stderr)
        return 2

    for timeframe in TIMEFRAMES:
        # Load one bounded timeframe once; reuse it across its 24 preregistered trials.
        barsets = []
        for symbol, bars, funding in loader(timeframe=timeframe,
                                            shard_index=shard_index,
                                            shard_count=shard_count):
            excluded_count = sum(not bar.complete for bar in bars)
            closed_bars = [bar for bar in bars if bar.complete]
            barsets.append((symbol, closed_bars, funding, excluded_count))
            _check_memory()
        zone_cache = {}
        for definition in DEFINITIONS:
            for direction in DIRECTIONS:
                for deadline in DEADLINES:
                    for reward_r in REWARD_R:
                        config = {"definition": definition, "timeframe": timeframe,
                                  "direction": direction, "deadline": deadline,
                                  "reward_r": reward_r}
                        trial_id = _trial_id(config)
                        timestamp = datetime.now(timezone.utc).isoformat()
                        try:
                            result = _run_trial(config, barsets, zone_cache)
                            status, detail = "completed", ""
                        except Exception as exc:  # preserve trial-level failure evidence
                            result = dict.fromkeys(("symbols", "trades", "win_rate",
                                "wilson_95_lower", "payoff_ratio", "profit_factor",
                                "expectancy_bps", "max_drawdown",
                                "incomplete_bars_excluded", "unscorable_funding_trades",
                                "time_exit_censored_setups", "symbols_excluded_missing_funding_marks",
                                "symbols_missing_funding_marks", "symbols_excluded_funding_gap",
                                "symbols_funding_gap", "symbols_without_bars",
                                "status", "detail"))
                            status, detail = "failed", f"{type(exc).__name__}: {exc}"
                        else:
                            status, detail = result.pop("status"), result.pop("detail")
                        _append({"timestamp_utc": timestamp, "trial_id": trial_id,
                                 **config, **result, "status": status, "detail": detail})
    return 0


def main() -> int:
    from resource_guard import heavy_task
    with heavy_task("B"):
        return _run()


if __name__ == "__main__":
    raise SystemExit(main())
