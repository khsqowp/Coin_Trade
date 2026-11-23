"""R3 train-only stock hypothesis search; test-window access is absent by design."""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import math
import os
import resource
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

import pandas as pd

from data_access import EQUITY_COMMON_SPLIT_MS, load_bars
from data_quality import SymbolQualityError, filter_equity_bars
from equities import Bar, preregistered_costs
from metrics import trade_metrics
from resource_guard import heavy_task

ROOT = Path(__file__).resolve().parent
MEMORY_LIMIT_BYTES = 3 * 1024**3
MARKETS = ("US", "KR")


def _default_split_path() -> Path:
    data_dir = Path(os.environ.get("TRADING_DATA_DIR") or (Path.home() / "CODE/trading_data"))
    return data_dir / "cache/orderblock/equity_splits_r3.json"


GRID = {
    "US": {
        "A": {"lookback": (126, 252), "stop_atr": (2, 3), "holding_days": (20, 40)},
        "B": {"gap_pct": (2, 4), "close_strength": (0.25, 0.5), "holding_days": (5, 10)},
        "C": {"vol_window": (10, 20), "breakout_buffer_pct": (0, 1), "holding_days": (10, 20)},
    },
    "KR": {
        "A": {"lookback": (126, 252), "stop_atr": (2, 3), "holding_days": (20, 40)},
        "B": {"gap_pct": (2, 4), "close_strength": (0.25, 0.5), "holding_days": (5, 10)},
        "C": {"touch_atr": (0, 0.5), "stop_atr": (1.5, 2.5), "holding_days": (10, 20)},
    },
}
TRIAL_FIELDS = ["trial_id", "round", "market_group", "utc_timestamp", "definition",
                "parameter_grid_hash", "code_sha256", "train_period", "metric", "rank", "notes"]


class DataQualityError(ValueError):
    """A malformed TRAIN source bar; prices are never silently repaired."""


def _validate_bar(bar: Bar, row_number: int) -> None:
    if not bar.complete:
        raise DataQualityError(
            f"incomplete TRAIN bar at row={row_number} timestamp={bar.timestamp}"
        )


def _configs(market: str) -> list[dict[str, Any]]:
    if market not in GRID:
        raise ValueError(f"unsupported market {market!r}")
    configs = []
    for family, axes in GRID[market].items():
        names, values = tuple(axes), tuple(axes.values())
        for combination in itertools.product(*values):
            configs.append({"family": family, **dict(zip(names, combination))})
    return configs


def _bars(frame: pd.DataFrame, symbol: str,
          quality_stats: dict[str, int] | None = None) -> list[Bar]:
    frame, filter_stats = filter_equity_bars(frame, symbol)
    if quality_stats is not None:
        quality_stats.update(filter_stats)
    required = {"open_time", "open", "high", "low", "close"}
    if not required.issubset(frame.columns):
        raise ValueError(f"bar columns missing: {sorted(required - set(frame.columns))}")
    if "complete" in frame.columns and not pd.api.types.is_bool_dtype(frame["complete"].dtype):
        raise DataQualityError("complete column must contain boolean values")
    try:
        bars = [Bar(int(row.open_time), float(row.open), float(row.high), float(row.low),
                    float(row.close), bool(getattr(row, "complete", True)))
                for row in frame.itertuples(index=False)]
    except (TypeError, ValueError, OverflowError) as exc:
        raise DataQualityError(f"unparseable TRAIN OHLC/time row: {exc}") from exc
    for index, bar in enumerate(bars):
        _validate_bar(bar, index)
        if index and bar.timestamp <= bars[index - 1].timestamp:
            raise DataQualityError(
                f"non-increasing TRAIN timestamp at row={index}: "
                f"{bars[index - 1].timestamp} then {bar.timestamp}"
            )
    return bars


def _atr(bars: list[Bar], end: int, period: int = 14) -> float | None:
    if end + 1 < period:
        return None
    ranges = []
    for i in range(end - period + 1, end + 1):
        previous = bars[i - 1].close if i else bars[i].open
        ranges.append(max(bars[i].high - bars[i].low,
                          abs(bars[i].high - previous), abs(bars[i].low - previous)))
    return sum(ranges) / period


def _signal(bars: list[Bar], i: int, config: dict[str, Any], market: str) -> tuple[float, float] | None:
    family = config["family"]
    if family == "A":
        lookback = config["lookback"]
        atr = _atr(bars, i)
        if i < lookback or atr is None:
            return None
        if bars[i].close > max(b.high for b in bars[i - lookback:i]) and bars[i].close > bars[i].open:
            return bars[i].close - config["stop_atr"] * atr, 2.0
    elif family == "B":
        if i < 1:
            return None
        previous = bars[i - 1].close
        gap = (bars[i].open / previous - 1) * 100
        strength = ((bars[i].close - bars[i].low) / (bars[i].high - bars[i].low)
                    if bars[i].high > bars[i].low else 0)
        if market == "US" and gap >= config["gap_pct"] and bars[i].close > bars[i].open and strength >= config["close_strength"]:
            return bars[i].low, 2.0
        if (market == "KR" and gap <= -config["gap_pct"] and bars[i].close > bars[i].open
                and bars[i].close >= previous and strength >= config["close_strength"]):
            return bars[i].low, 2.0
    elif family == "C" and config.get("touch_atr") is not None:
        atr = _atr(bars, i)
        if i < 200 or atr is None:
            return None
        sma200 = mean(b.close for b in bars[i - 199:i + 1])
        sma20 = mean(b.close for b in bars[i - 19:i + 1])
        if bars[i].close > sma200 and bars[i].low <= sma20 + config["touch_atr"] * atr and bars[i].close > sma20 and bars[i].close > bars[i].open:
            return bars[i].close - config["stop_atr"] * atr, 2.0
    elif family == "C":
        window = config["vol_window"]
        if i < max(40, window + 20):
            return None
        recent = [bars[j].close / bars[j - 1].close - 1 for j in range(i - window + 1, i + 1)]
        prior = [bars[j].close / bars[j - 1].close - 1 for j in range(i - 40 + 1, i + 1)]
        recent_vol = math.sqrt(mean(x * x for x in recent))
        prior_vol = math.sqrt(mean(x * x for x in prior))
        atr = _atr(bars, i)
        threshold = max(b.high for b in bars[i - 20:i]) * (1 + config["breakout_buffer_pct"] / 100)
        if atr and recent_vol <= prior_vol * 0.6 and bars[i].close > threshold:
            return bars[i].close - 2 * atr, 2.0
    return None


def _simulate(bars: list[Bar], market: str, config: dict[str, Any], *,
              audit: dict[str, int] | None = None) -> list[dict[str, Any]]:
    for index, bar in enumerate(bars):
        _validate_bar(bar, index)
        if index and bar.timestamp <= bars[index - 1].timestamp:
            raise DataQualityError(f"non-increasing timestamp at bar index={index}")
    costs = preregistered_costs(market)
    round_trip = (2 * (costs.commission_bps_per_side + costs.slippage_bps_per_side)
                  + costs.sell_tax_bps)
    trades, i = [], 0
    while i < len(bars):
        setup = _signal(bars, i, config, market)
        if setup is None:
            i += 1
            continue
        if i + 1 >= len(bars):
            if audit is not None:
                audit["unfilled_signal_censored"] = audit.get("unfilled_signal_censored", 0) + 1
            break
        entry_i = i + 1
        entry = bars[entry_i].open
        stop, _ = setup
        if entry <= stop or not math.isfinite(entry):
            if audit is not None:
                audit["entries_skipped_at_or_below_stop"] = (
                    audit.get("entries_skipped_at_or_below_stop", 0) + 1
                )
            i += 1
            continue
        risk = entry - stop
        target = entry + 2 * risk
        horizon = config["holding_days"]
        horizon_exit_i = entry_i + horizon - 1
        available_exit_i = min(horizon_exit_i, len(bars) - 1)
        reason, exit_price = "time", 0.0
        barrier_exit = False
        exit_i = available_exit_i
        for j in range(entry_i, available_exit_i + 1):
            bar = bars[j]
            if bar.open <= stop:
                exit_i, exit_price, reason = j, bar.open, "stop"
                barrier_exit = True
                break
            if bar.low <= stop:
                exit_i, exit_price, reason = j, stop, "stop"
                barrier_exit = True
                break
            if bar.high >= target:
                exit_i, exit_price, reason = j, target, "target"
                barrier_exit = True
                break
        if not barrier_exit:
            if horizon_exit_i >= len(bars):
                if audit is not None:
                    audit["right_censored"] = audit.get("right_censored", 0) + 1
                break
            exit_i, exit_price, reason = horizon_exit_i, bars[horizon_exit_i].close, "time"
        net = exit_price / entry - 1 - round_trip / 10_000
        daily_pnl = {}
        previous = entry
        for j in range(entry_i, exit_i + 1):
            mark = exit_price if j == exit_i else bars[j].close
            day = bars[j].timestamp // 86_400_000
            daily_pnl[day] = daily_pnl.get(day, 0.0) + (mark - previous) / entry
            previous = mark
        entry_cost = (costs.commission_bps_per_side + costs.slippage_bps_per_side) / 10_000
        exit_cost = entry_cost + costs.sell_tax_bps / 10_000
        entry_day = bars[entry_i].timestamp // 86_400_000
        exit_day = bars[exit_i].timestamp // 86_400_000
        daily_pnl[entry_day] = daily_pnl.get(entry_day, 0.0) - entry_cost
        daily_pnl[exit_day] = daily_pnl.get(exit_day, 0.0) - exit_cost
        if not math.isclose(sum(daily_pnl.values()), net, rel_tol=1e-9, abs_tol=1e-10):
            raise ValueError("daily marks do not reconcile with net trade return")
        trades.append({"exit_time": bars[exit_i].timestamp, "net_return": net,
                       "reason": reason, "entry": entry, "exit": exit_price,
                       "daily_pnl": daily_pnl})
        i = exit_i + 1
    return trades


def _metrics(trades: list[dict[str, Any]], symbol_count: int = 1) -> dict[str, Any]:
    returns = [t["net_return"] for t in trades]
    stats = trade_metrics(returns)
    wins = [x for x in returns if x > 0]
    losses = [-x for x in returns if x < 0]
    daily = defaultdict(float)
    for trade in trades:
        for day, value in trade.get("daily_pnl", {}).items():
            daily[day] += value / max(symbol_count, 1)
    equity = peak = 1.0
    mdd = 0.0
    for day in sorted(daily):
        equity += daily[day]
        peak = max(peak, equity)
        if peak > 0:
            mdd = max(mdd, (peak - equity) / peak)
    return {"trades": len(returns), "win_rate_pct": stats.win_rate * 100 if stats.win_rate is not None else None,
            "wilson_95_lower_pct": stats.wilson_lower_95 * 100 if stats.wilson_lower_95 is not None else None,
            "payoff_ratio": mean(wins) / mean(losses) if wins and losses else None,
            "profit_factor": stats.profit_factor, "expectancy_net_bps": stats.expectancy_bps,
            "mdd_pct": mdd * 100}


def _load_train(path: Path, symbol: str, market: str, split_file: Path) -> pd.DataFrame:
    return load_bars(path, window="train", split_file=split_file, symbol=symbol,
                     end_ms=EQUITY_COMMON_SPLIT_MS, fixed_split_ms=EQUITY_COMMON_SPLIT_MS)


def _frame_sha256(frame: pd.DataFrame) -> str:
    columns = ["open_time", "open", "high", "low", "close"]
    if "complete" in frame.columns:
        columns.append("complete")
    digest = hashlib.sha256(
        ("R3-TRAIN-OHLC-v2\0" + ",".join(columns) + "\n").encode()
    )
    for row in frame[columns].itertuples(index=False, name=None):
        values = []
        for value in row:
            if pd.isna(value):
                values.append(["missing"])
                continue
            try:
                number = float(value)
            except (TypeError, ValueError, OverflowError):
                values.append(["non_numeric", str(value)])
            else:
                values.append(["number", number.hex()] if math.isfinite(number)
                              else ["nonfinite", repr(number)])
        digest.update((json.dumps(values, separators=(",", ":"), allow_nan=True) + "\n").encode())
    return digest.hexdigest()


def _source_code_sha256() -> str:
    digest = hashlib.sha256()
    for name in ("search_equities_r3.py", "data_access.py", "equities.py", "metrics.py",
                 "resource_guard.py"):
        digest.update(name.encode() + b"\0")
        digest.update((ROOT / name).read_bytes())
    return digest.hexdigest()


def run(universe_path: Path, trials_path: Path, split_file: Path) -> list[dict[str, Any]]:
    with universe_path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    if not rows or not {"market", "symbol", "daily_path"}.issubset(rows[0]):
        raise ValueError("universe CSV needs market,symbol,daily_path columns")
    if any(row["market"] not in MARKETS for row in rows):
        raise ValueError("universe market must be US or KR")
    seen_symbols: set[tuple[str, str]] = set()
    for row in rows:
        key = (row["market"], row["symbol"])
        if key in seen_symbols:
            raise ValueError(f"duplicate market-symbol universe row: {key[0]} {key[1]}")
        seen_symbols.add(key)
    requested_markets = sorted({row["market"] for row in rows})
    results = {(market, family, json.dumps(config, sort_keys=True)): []
               for market in requested_markets for family in GRID[market]
               for config in _configs(market) if config["family"] == family}
    configs = {market: _configs(market) for market in requested_markets}
    universe_counts = {market: sum(1 for row in rows if row["market"] == market)
                       for market in requested_markets}
    symbols = defaultdict(set)
    ranges = defaultdict(list)
    failures: dict[tuple[str, str], dict[str, str]] = {}
    empty_symbols: dict[str, set[str]] = defaultdict(set)
    right_censored = defaultdict(int)
    unfilled_censored = defaultdict(int)
    entries_skipped = defaultdict(int)
    train_hashes = defaultdict(hashlib.sha256)
    quality_stats = defaultdict(lambda: {"invalid_ohlc": 0, "halt_bars": 0})
    universe_sha = hashlib.sha256(universe_path.read_bytes()).hexdigest()
    for row in rows:
        market, symbol = row["market"], row["symbol"]
        try:
            frame = _load_train(Path(row["daily_path"]).expanduser(), symbol, market, split_file)
            frame_sha = _frame_sha256(frame)
            train_hashes[market].update(symbol.encode() + b"\0" + frame_sha.encode() + b"\n")
            if frame.empty:
                empty_symbols[market].add(symbol)
                continue
            symbol_quality: dict[str, int] = {}
            try:
                bars = _bars(frame, symbol, symbol_quality)
            finally:
                quality_stats[market]["invalid_ohlc"] += symbol_quality.get("invalid_ohlc", 0)
                quality_stats[market]["halt_bars"] += symbol_quality.get("halt_bars", 0)
            if not bars:
                empty_symbols[market].add(symbol)
                continue
            local_trades = {}
            local_censored = {}
            local_unfilled = {}
            local_entry_skips = {}
            for config in configs[market]:
                key = (market, config["family"], json.dumps(config, sort_keys=True))
                audit: dict[str, int] = {}
                local_trades[key] = _simulate(bars, market, config, audit=audit)
                local_censored[key] = audit.get("right_censored", 0)
                local_unfilled[key] = audit.get("unfilled_signal_censored", 0)
                local_entry_skips[key] = audit.get("entries_skipped_at_or_below_stop", 0)
            peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            if peak * (1 if sys.platform == "darwin" else 1024) > MEMORY_LIMIT_BYTES:
                raise MemoryError("peak RSS exceeded 3 GiB")
            symbols[market].add(symbol)
            ranges[market].extend((bars[0].timestamp, bars[-1].timestamp))
            for key, trades in local_trades.items():
                results[key].extend((symbol, trade) for trade in trades)
                right_censored[key] += local_censored[key]
                unfilled_censored[key] += local_unfilled[key]
                entries_skipped[key] += local_entry_skips[key]
        except MemoryError:
            raise
        except (DataQualityError, SymbolQualityError) as exc:
            failures[(market, symbol)] = {"kind": "invalid_ohlc_or_time", "detail": str(exc)}
            train_hashes[market].update(symbol.encode() + b"\0INVALID\0" + str(exc).encode() + b"\n")
        except Exception as exc:
            print(f"{market},{symbol}: {type(exc).__name__}: {exc}", file=sys.stderr)
            failures[(market, symbol)] = {"kind": "loader_or_simulation_error",
                                          "detail": f"{type(exc).__name__}: {exc}"}
            train_hashes[market].update(symbol.encode() + b"\0ERROR\0" + repr(exc).encode() + b"\n")
    if trials_path.exists() and trials_path.stat().st_size:
        with trials_path.open(newline="", encoding="utf-8") as handle:
            if next(csv.reader(handle)) != TRIAL_FIELDS:
                raise ValueError("TRAIN_TRIALS.csv schema mismatch")
    prereg = hashlib.sha256((ROOT / "PREREG.md").read_bytes()).hexdigest()
    code_sha = _source_code_sha256()
    now = datetime.now(timezone.utc).isoformat()
    output = []
    with trials_path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=TRIAL_FIELDS)
        if handle.tell() == 0:
            writer.writeheader()
        for market in requested_markets:
            market_rows = []
            for config in configs[market]:
                key = (market, config["family"], json.dumps(config, sort_keys=True))
                trades = results[key]
                stats = _metrics([t for _, t in trades], len(symbols[market]))
                result = {"market": market, "family": config["family"], "parameters": config,
                          "symbols_in_universe": universe_counts[market],
                          "symbols_valid": len(symbols[market]),
                          "symbols": len(symbols[market]),
                          "symbols_empty_train": len(empty_symbols[market]),
                          "symbols_failed": sum(1 for m, _ in failures if m == market),
                          "symbols_invalid_ohlc_or_time": sum(1 for (m, _), issue in failures.items()
                                                               if m == market and issue["kind"] == "invalid_ohlc_or_time"),
                          "symbols_loader_or_simulation_error": sum(1 for (m, _), issue in failures.items()
                                                                     if m == market and issue["kind"] == "loader_or_simulation_error"),
                          "invalid_ohlc_rows_filtered": quality_stats[market]["invalid_ohlc"],
                          "halt_bars_filtered": quality_stats[market]["halt_bars"],
                          "symbol_failures": {symbol: issue for (m, symbol), issue in sorted(failures.items())
                                              if m == market},
                          "empty_train_symbols": sorted(empty_symbols[market]),
                          "right_censored_setups": right_censored[key],
                          "unfilled_signal_censored": unfilled_censored[key],
                          "entries_skipped_at_or_below_stop": entries_skipped[key],
                          "train_data_sha256": train_hashes[market].hexdigest(),
                          "universe_sha256": universe_sha,
                          "train_trades": stats["trades"],
                          **stats, "survivorship_bias": "PRESENT/UNKNOWN"}
                market_rows.append(result)
                output.append(result)
            ranked = sorted(market_rows, key=lambda row: (row["expectancy_net_bps"] is not None,
                                                          row["expectancy_net_bps"] or -math.inf), reverse=True)
            for rank, result in enumerate(ranked, 1):
                writer.writerow({"trial_id": f"R3-{market}-{rank:03d}", "round": "R3",
                                 "market_group": market, "utc_timestamp": now,
                                 "definition": json.dumps(result["parameters"], sort_keys=True, separators=(",", ":")),
                                 "parameter_grid_hash": prereg, "code_sha256": code_sha,
                                 "train_period": f"<=2018-10-26T23:59:00Z; symbols={result['symbols']}",
                                 "metric": json.dumps({k: v for k, v in result.items() if k not in ("parameters",)},
                                                      sort_keys=True, separators=(",", ":")),
                                 "rank": rank, "notes": "TRAIN only; not G; survivorship=PRESENT/UNKNOWN"})
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--universe", type=Path, default=ROOT / "universe/R2.csv")
    parser.add_argument("--trials", type=Path, default=ROOT / "TRAIN_TRIALS.csv")
    parser.add_argument("--split-file", type=Path, default=_default_split_path())
    args = parser.parse_args()
    if os.getpriority(os.PRIO_PROCESS, 0) < 10:
        raise RuntimeError("R3 requires an effective nice value of at least 10")
    with heavy_task("C"):
        for result in run(args.universe, args.trials, args.split_file):
            print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
