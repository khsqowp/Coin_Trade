"""Train-only, symbol-sharded search for preregistered equity C1-C4 settings.

The universe CSV contains ``market,symbol,daily_path``. Paths may point to a
symbol panel; data_access filters one symbol at a time. Weekly bars are formed
from that symbol's daily train rows. Bars are loaded through data_access with window=train;
this runner has no test-window option. Results are descriptive train metrics,
not a G-gate or evidence of out-of-sample performance.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import resource
import sys
from collections import defaultdict
from datetime import datetime, time, timezone
from pathlib import Path
from statistics import mean
from typing import Any

import pandas as pd

from data_access import EQUITY_COMMON_SPLIT_MS, load_bars
from equities import Bar, preregistered_costs, simulate_c1, simulate_c2, simulate_c3, simulate_c4
from metrics import trade_metrics

ROOT = Path(__file__).resolve().parent
CUTOFF = "2026-05-31"
MEMORY_LIMIT_BYTES = 3 * 1024**3


def _check_memory_limit() -> None:
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak_bytes = peak if sys.platform == "darwin" else peak * 1024
    if peak_bytes > MEMORY_LIMIT_BYTES:
        raise MemoryError(f"peak RSS exceeded 3 GiB: {peak_bytes} bytes")


def _configs() -> list[dict[str, Any]]:
    configs = []
    for timeframe in ("daily", "weekly"):
        for lookback in (10, 20):
            for retest in (10, 20):
                for reward in (2, 3):
                    for holding in (20, 40):
                        configs.append({"family": "C1", "timeframe": timeframe,
                                        "lookback": lookback, "retest_bars": retest,
                                        "reward_r": reward, "holding_bars": holding})
    for gap_atr in (1.0, 1.5):
        for holding in (5, 10):
            configs.append({"family": "C2", "timeframe": "daily",
                            "gap_atr": gap_atr, "holding_bars": holding})
    for lookback in (126, 252):
        for stop_atr in (2, 3):
            for reward in (2, 3):
                for holding in (20, 40):
                    configs.append({"family": "C3", "timeframe": "daily",
                                    "lookback": lookback, "stop_atr": stop_atr,
                                    "reward_r": reward, "holding_bars": holding})
    for distance_atr in (0.5, 1.0):
        for stop_buffer in (0, 0.5):
            for reward in (2, 3):
                for holding in (10, 20):
                    configs.append({"family": "C4", "timeframe": "daily",
                                    "distance_atr": distance_atr, "stop_buffer": stop_buffer,
                                    "reward_r": reward, "holding_bars": holding})
    return configs


def _bars(frame: pd.DataFrame) -> list[Bar]:
    required = {"open_time", "open", "high", "low", "close"}
    if not required.issubset(frame.columns):
        raise ValueError(f"bar columns missing: {sorted(required - set(frame.columns))}")
    complete = frame.get("complete", pd.Series(True, index=frame.index))
    return [Bar(int(row.open_time), float(row.open), float(row.high),
                float(row.low), float(row.close), bool(is_complete))
            for row, is_complete in zip(frame.itertuples(index=False), complete)]


def _load_train(path: Path, split_file: Path, symbol: str, market: str) -> list[Bar]:
    if market not in ("US", "KR"):
        raise ValueError(f"unsupported equity market: {market}")
    frame = load_bars(path, window="train", split_file=split_file, symbol=symbol,
                      end_ms=EQUITY_COMMON_SPLIT_MS,
                      fixed_split_ms=EQUITY_COMMON_SPLIT_MS)
    return _bars(frame)


def _weekly_bars(daily: list[Bar]) -> list[Bar]:
    weeks: dict[tuple[int, int], list[Bar]] = defaultdict(list)
    for bar in daily:
        date = datetime.fromtimestamp(bar.timestamp / 1000, timezone.utc).date()
        iso = date.isocalendar()
        weeks[(iso.year, iso.week)].append(bar)
    result = []
    for rows in weeks.values():
        weekdays = [datetime.fromtimestamp(row.timestamp / 1000, timezone.utc).weekday()
                    for row in rows]
        if weekdays != [0, 1, 2, 3, 4]:
            continue  # Require a complete Mon-Fri week; holiday-short weeks are excluded.
        week_close = datetime.combine(
            datetime.fromtimestamp(rows[-1].timestamp / 1000, timezone.utc).date(),
            time(23, 59), timezone.utc)
        result.append(Bar(int(week_close.timestamp() * 1000), rows[0].open,
                          max(row.high for row in rows), min(row.low for row in rows),
                          rows[-1].close))
    return result


def _max_drawdown(trades: list[tuple[int, float]]) -> float:
    """Fixed-capital MDD; same-day cross-symbol PnL is aggregated before marking."""
    equity = peak = 1.0
    maximum = 0.0
    daily_pnl: dict[int, float] = defaultdict(float)
    for timestamp, value in trades:
        daily_pnl[timestamp] += value
    for _, value in sorted(daily_pnl.items()):
        equity += value
        peak = max(peak, equity)
        if peak:
            maximum = max(maximum, (peak - equity) / peak)
    return maximum * 100


def _daily_trade_pnl(bars: list[Bar], trade, market: str) -> dict[int, float]:
    """Daily fixed-capital mark-to-market PnL, including asymmetric KR sell tax."""
    costs = preregistered_costs(market)
    entry_cost = (costs.commission_bps_per_side + costs.slippage_bps_per_side) / 10_000
    exit_cost = entry_cost + costs.sell_tax_bps / 10_000
    values: dict[int, float] = {}
    previous = trade.entry_price
    for index in range(trade.entry_index, trade.exit_index + 1):
        bar = bars[index]
        mark = trade.exit_price if index == trade.exit_index else bar.close
        day = bar.timestamp // 86_400_000
        values[day] = values.get(day, 0.0) + (mark - previous) / trade.entry_price
        previous = mark
    entry_day = bars[trade.entry_index].timestamp // 86_400_000
    exit_day = bars[trade.exit_index].timestamp // 86_400_000
    values[entry_day] = values.get(entry_day, 0.0) - entry_cost
    values[exit_day] = values.get(exit_day, 0.0) - exit_cost
    if not math.isclose(sum(values.values()), trade.net_return, rel_tol=1e-9, abs_tol=1e-10):
        raise ValueError("daily equity marks do not reconcile to trade net return")
    return values


def _metric_row(config: dict[str, Any], market: str, symbol_count: int,
                records: list[tuple[str, int, float]], errors: int,
                train_start: int | str, train_end: int | str,
                daily_marks: list[tuple[str, int, float]]) -> dict[str, Any]:
    returns = [item[2] for item in records]
    stats = trade_metrics(returns)
    gross_wins = sum(value for value in returns if value > 0)
    gross_losses = -sum(value for value in returns if value < 0)
    payoff = (mean([v for v in returns if v > 0]) / mean([-v for v in returns if v < 0])
              if any(v > 0 for v in returns) and any(v < 0 for v in returns) else None)
    return {
        "survivorship_bias": "PRESENT/UNKNOWN: PIT coverage and delisted-price completeness not established",
        "market": market, "family": config["family"], "timeframe": config["timeframe"],
        "parameters": json.dumps(config, sort_keys=True, separators=(",", ":")),
        "symbols": symbol_count, "train_start": train_start,
        "train_end": train_end or CUTOFF, "trades": stats.count,
        "win_rate_pct": stats.win_rate * 100 if stats.win_rate is not None else "",
        "wilson_95_lower_pct": stats.wilson_lower_95 * 100 if stats.wilson_lower_95 is not None else "",
        "payoff_ratio": payoff, "profit_factor": stats.profit_factor,
        "expectancy_net_bps": stats.expectancy_bps,
        "mdd_daily_mtm_pct": _max_drawdown(
            [(r[1], r[2] / max(symbol_count, 1)) for r in daily_marks]),
        "data_errors": errors,
    }


def _simulate(config: dict[str, Any], bars: list[Bar], market: str,
              daily: list[Bar] | None) -> list[Any]:
    kwargs = {key: value for key, value in config.items()
              if key not in ("family", "timeframe")}
    if config["family"] == "C1":
        return simulate_c1(bars, timeframe=config["timeframe"], market=market,
                           execution_bars=daily if config["timeframe"] == "weekly" else None,
                           **kwargs)
    if config["family"] == "C2":
        return simulate_c2(bars, market=market, **kwargs)
    if config["family"] == "C3":
        return simulate_c3(bars, market=market, **kwargs)
    return simulate_c4(bars, market=market, **kwargs)


def run(universe_path: Path, out_path: Path, split_file: Path) -> int:
    with universe_path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    if not rows or not {"market", "symbol", "daily_path"}.issubset(rows[0]):
        raise ValueError("universe CSV needs market,symbol,daily_path columns")
    if any(row["market"] not in ("US", "KR") for row in rows):
        raise ValueError("universe market must be US or KR")
    requested_markets = sorted({row["market"] for row in rows})

    configs = _configs()
    definition = json.dumps(configs, sort_keys=True, separators=(",", ":"))
    grid_sha = hashlib.sha256(definition.encode()).hexdigest()
    results: dict[tuple[str, int], list[tuple[str, int, float]]] = defaultdict(list)
    daily_marks: dict[tuple[str, int], list[tuple[str, int, float]]] = defaultdict(list)
    errors: dict[tuple[str, int], int] = defaultdict(int)
    symbols_seen: dict[str, set[str]] = defaultdict(set)
    train_ranges: dict[str, list[int]] = defaultdict(list)

    # Read and simulate one symbol at a time so resident bar data is shard-bounded.
    for item in rows:
        market, symbol = item["market"], item["symbol"]
        try:
            daily = _load_train(Path(item["daily_path"]).expanduser(), split_file, symbol, market)
            if not daily:
                raise ValueError("empty train window")
            train_ranges[market].extend((daily[0].timestamp, daily[-1].timestamp))
            weekly = _weekly_bars(daily)
            symbols_seen[market].add(symbol)
            for idx, config in enumerate(configs):
                if config["timeframe"] == "weekly" and len(weekly) < 2:
                    errors[(market, idx)] += 1
                    continue
                trades = _simulate(config, weekly if config["timeframe"] == "weekly" else daily,
                                   market, daily)
                exit_bars = daily if config["timeframe"] == "weekly" else daily
                for trade in trades:
                    results[(market, idx)].append(
                        (symbol, exit_bars[trade.exit_index].timestamp,
                         trade.net_return))
                    daily_marks[(market, idx)].extend(
                        (symbol, day, pnl) for day, pnl in
                        _daily_trade_pnl(exit_bars, trade, market).items())
            _check_memory_limit()
        except MemoryError:
            raise
        except Exception as exc:  # preserve per-symbol failures in the trial ledger
            print(f"{market},{symbol}: {type(exc).__name__}: {exc}", file=sys.stderr)
            for idx in range(len(configs)):
                errors[(market, idx)] += 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Keep the coordinator's existing ledger schema. One trial is one
    # market x parameter configuration; symbol shards contribute to its metrics.
    fields = ["trial_id", "round", "market_group", "utc_timestamp", "definition",
              "parameter_grid_hash", "code_sha256", "train_period", "metric", "rank", "notes"]
    if out_path.exists() and out_path.stat().st_size:
        with out_path.open(newline="", encoding="utf-8") as handle:
            existing_fields = next(csv.reader(handle))
        if existing_fields != fields:
            raise ValueError(f"trial ledger schema mismatch: {existing_fields!r}")
    code_hash = hashlib.sha256()
    for filename in ("search_equities.py", "equities.py", "data_access.py",
                     "metrics.py", "resource_guard.py"):
        code_hash.update((ROOT / filename).read_bytes())
    code_sha = code_hash.hexdigest()
    now = datetime.now(timezone.utc).isoformat()
    with out_path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        if handle.tell() == 0:
            writer.writeheader()
        for market in requested_markets:
            for idx, config in enumerate(configs):
                row = _metric_row(config, market, len(symbols_seen[market]),
                                  results[(market, idx)], errors[(market, idx)],
                                  min(train_ranges[market]) if train_ranges[market] else "",
                                  max(train_ranges[market]) if train_ranges[market] else "",
                                  daily_marks[(market, idx)])
                metrics = {key: value for key, value in row.items()
                           if key not in ("market", "family", "timeframe",
                                          "parameters", "grid_sha256")}
                writer.writerow({
                    "trial_id": f"R2-{market}-{idx:03d}-{grid_sha[:12]}",
                    "round": "R2", "market_group": market, "utc_timestamp": now,
                    "definition": json.dumps(config, sort_keys=True, separators=(",", ":")),
                    "parameter_grid_hash": grid_sha, "code_sha256": code_sha,
                    "train_period": f"{row['train_start']}..{row['train_end']}",
                    "metric": json.dumps(metrics, sort_keys=True, separators=(",", ":")),
                    "rank": "", "notes": "TRAIN only; survivorship bias PRESENT/UNKNOWN; "
                    f"symbols={row['symbols']}; data_errors={row['data_errors']}; logged_at={now}",
                })
    return len(configs) * len(requested_markets)


def main() -> None:
    parser = argparse.ArgumentParser(description="Search preregistered equity families on train only")
    parser.add_argument("--universe", type=Path, required=True)
    parser.add_argument("--trials", type=Path, default=ROOT / "TRAIN_TRIALS.csv")
    parser.add_argument("--splits", type=Path,
                        default=ROOT / "equities_splits.json")
    args = parser.parse_args()
    _check_memory_limit()
    from resource_guard import heavy_task
    with heavy_task("C"):
        print(f"logged trial rows: {run(args.universe, args.trials, args.splits)}")


if __name__ == "__main__":
    main()
