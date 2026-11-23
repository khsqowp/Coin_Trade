"""R4 train-only equity search with point-in-time membership gating.

The runner refuses legacy snapshot universes. TEST access is deliberately absent.
"""
from __future__ import annotations

import argparse
import csv
import json
import hashlib
import os
import sys
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd

from data_access import EQUITY_COMMON_SPLIT_MS
from equities import Bar, Trade, simulate_c1, preregistered_costs
from data_quality import SymbolQualityError, filter_equity_bars
from resource_guard import heavy_task

ROOT = Path(__file__).resolve().parent
MEMBERSHIP_FIELDS = {"market", "symbol", "alive_from", "alive_through", "source", "source_asof"}
MARKETS = {"US", "KR"}
LOOKBACKS = (10, 20)
RETESTS = (10, 20)
TARGET_RS = (2, 3)
HOLDINGS = (20, 40)
NEW_CANDIDATES = (
    "E2-A momentum 252d",
    "E2-B Donchian 55d",
    "E2-C Bollinger rebound",
    "E2-D weekly Donchian 20w",
    "E2-E weekly SMA pullback",
    "E2-F volatility contraction breakout",
)


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
                             membership: Membership,
                             signal_bars: list[Bar] | None = None) -> tuple[list[Trade], int]:
    """Keep trades alive at signal time; exclude positions lacking an in-life exit."""
    kept, delisting_gap = [], 0
    signal_bars = signal_bars or daily_bars
    for trade in trades:
        signal_day = pd.Timestamp(signal_bars[trade.signal_index].timestamp, unit="ms", tz="UTC").date()
        exit_day = pd.Timestamp(daily_bars[trade.exit_index].timestamp, unit="ms", tz="UTC").date()
        if not membership.alive(signal_day):
            continue
        if not membership.alive(exit_day):
            delisting_gap += 1
            continue
        kept.append(trade)
    return kept, delisting_gap


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
        complete = bool(getattr(row, "complete", True))
        bar = Bar(stamp, float(row.open), float(row.high), float(row.low),
                  float(row.close), complete)
        if not complete:
            raise ValueError(f"incomplete bar for {membership.symbol} at {day}")
        if output and stamp <= output[-1].timestamp:
            raise ValueError(f"non-increasing timestamp for {membership.symbol}")
        output.append(bar)
    return output


def _configs() -> list[dict[str, object]]:
    return [{"strategy": "C1", "timeframe": "weekly", "lookback": lookback,
             "retest_bars": retest, "target_r": target, "holding_bars": holding}
            for lookback in LOOKBACKS for retest in RETESTS
            for target in TARGET_RS for holding in HOLDINGS]


def _weekly_bars(daily: list[Bar]) -> list[Bar]:
    weeks: dict[tuple[int, int], list[Bar]] = {}
    for bar in daily:
        stamp = datetime.fromtimestamp(bar.timestamp / 1000, timezone.utc).date().isocalendar()
        weeks.setdefault((stamp.year, stamp.week), []).append(bar)
    result = []
    for rows in weeks.values():
        weekdays = [datetime.fromtimestamp(row.timestamp / 1000, timezone.utc).weekday()
                    for row in rows]
        if weekdays != [0, 1, 2, 3, 4]:
            continue
        last_day = datetime.fromtimestamp(rows[-1].timestamp / 1000, timezone.utc).date()
        close_time = datetime.combine(last_day, time(23, 59), timezone.utc)
        result.append(Bar(int(close_time.timestamp() * 1000), rows[0].open,
                          max(bar.high for bar in rows), min(bar.low for bar in rows),
                          rows[-1].close))
    return result


def evaluate_c1(bars: list[Bar], market: str, membership: Membership,
                config: dict[str, object]) -> dict[str, object]:
    weekly = _weekly_bars(bars)
    all_trades = simulate_c1(weekly, timeframe="weekly", lookback=int(config["lookback"]),
                             retest_bars=int(config["retest_bars"]),
                             reward_r=int(config["target_r"]),
                             holding_bars=int(config["holding_bars"]), market=market,
                             execution_bars=bars)
    trades, gap_count = survivorship_safe_trades(all_trades, bars, membership, weekly)
    returns = [trade.net_return for trade in trades]
    wins = sum(value > 0 for value in returns)
    gross_profit = sum(value for value in returns if value > 0)
    gross_loss = -sum(value for value in returns if value < 0)
    return {"trades": len(trades), "survivorship_excluded_signals": len(all_trades) - len(trades) - gap_count,
            "delisting_gap": gap_count, "win_rate_pct": 100 * wins / len(trades) if trades else None,
            "profit_factor": gross_profit / gross_loss if gross_loss else None,
            "expectancy_net_bps": 10_000 * sum(returns) / len(returns) if returns else None,
            "status": "TRAIN_ONLY_NOT_G"}


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else float("nan")


def _sample_std(values: list[float]) -> float:
    mean = _mean(values)
    return (sum((value - mean) ** 2 for value in values) / (len(values) - 1)) ** .5 if len(values) > 1 else float("nan")


def _crossed_weekly(daily: list[Bar]) -> tuple[list[Bar], list[int]]:
    weekly, last_daily = [], []
    grouped: dict[tuple[int, int], list[tuple[int, Bar]]] = {}
    for index, bar in enumerate(daily):
        iso = datetime.fromtimestamp(bar.timestamp / 1000, timezone.utc).date().isocalendar()
        grouped.setdefault((iso.year, iso.week), []).append((index, bar))
    for rows in grouped.values():
        if [datetime.fromtimestamp(b.timestamp / 1000, timezone.utc).weekday() for _, b in rows] != [0, 1, 2, 3, 4]:
            continue
        ix, bars = zip(*rows)
        day = datetime.fromtimestamp(bars[-1].timestamp / 1000, timezone.utc).date()
        stamp = int(datetime.combine(day, time(23, 59), timezone.utc).timestamp() * 1000)
        weekly.append(Bar(stamp, bars[0].open, max(b.high for b in bars), min(b.low for b in bars), bars[-1].close))
        last_daily.append(ix[-1])
    return weekly, last_daily


def _e2_signal(candidate: str, bars: list[Bar], i: int, weekly: list[Bar], week_last: list[int]) -> tuple[float, float | None, float | None] | None:
    """Return (target, stop, target level); all calculations end at signal bar."""
    b = bars[i]
    if candidate == "E2-A" and i >= 252 and b.close > bars[i - 252].close:
        return (20, None, None)
    if candidate == "E2-B" and i >= 55 and b.close > max(x.high for x in bars[i - 55:i]):
        risk = _atr(bars, i, 20)
        return (40, b.close - 2 * risk, None) if risk else None
    if candidate == "E2-C" and i >= 20:
        closes = [x.close for x in bars[i - 20:i]]
        lower = _mean(closes) - 2 * _sample_std(closes)
        if b.close < lower:
            return (10, None, _mean(closes))
    if candidate in ("E2-D", "E2-E"):
        pos = next((p for p, ix in enumerate(week_last) if ix == i), None)
        if pos is None:
            return None
        w = weekly[pos]
        if candidate == "E2-D" and pos >= 20 and w.close > max(x.high for x in weekly[pos - 20:pos]):
            return (100, min(x.low for x in weekly[max(0, pos - 9):pos + 1]), None)
        if candidate == "E2-E" and pos >= 20:
            c = [x.close for x in weekly[:pos + 1]]
            sma10, sma20 = _mean(c[-10:]), _mean(c[-20:])
            prior_sma10 = _mean(c[-11:-1])
            if w.close > sma20 and weekly[pos - 1].close < prior_sma10 and w.close > sma10:
                return (50, None, None)
    if candidate == "E2-F" and i >= 40:
        short = [bars[k].close / bars[k - 1].close - 1 for k in range(i - 9, i + 1)]
        long = [bars[k].close / bars[k - 1].close - 1 for k in range(i - 39, i + 1)]
        s10, s40 = _sample_std(short), _sample_std(long)
        if s40 > 0 and s10 <= .6 * s40 and b.close > max(x.high for x in bars[i - 20:i]):
            risk = _atr(bars, i, 14)
            return (20, b.close - 2 * risk, b.close + 4 * risk) if risk else None
    return None


def _atr(bars: list[Bar], i: int, period: int) -> float:
    if i + 1 < period:
        return 0.0
    ranges = []
    for k in range(i - period + 1, i + 1):
        prev = bars[k - 1].close if k else bars[k].open
        ranges.append(max(bars[k].high - bars[k].low, abs(bars[k].high - prev), abs(bars[k].low - prev)))
    return sum(ranges) / period


def simulate_e2(candidate: str, bars: list[Bar], market: str) -> tuple[list[Trade], int]:
    """Fixed preregistered long-only E2 rules; no overlapping positions."""
    if candidate not in {f"E2-{x}" for x in "ABCDEF"}:
        raise ValueError(f"unknown E2 candidate: {candidate}")
    weekly, week_last = _crossed_weekly(bars)
    costs = preregistered_costs(market)
    cost_bps = costs.commission_bps_per_side * 2 + costs.slippage_bps_per_side * 2 + costs.sell_tax_bps
    trades, gaps, busy_until = [], 0, -1
    for i in range(len(bars) - 1):
        if i <= busy_until:
            continue
        setup = _e2_signal(candidate, bars, i, weekly, week_last)
        if setup is None:
            continue
        hold, stop, target = setup
        # E2-C's preregistered confirmation is next-bar open above prior high.
        entry_i = i + 1
        if candidate == "E2-C" and bars[entry_i].open <= bars[i].high:
            continue
        entry = bars[entry_i].open
        if entry <= 0:
            continue
        if candidate == "E2-B":
            stop = entry - 2 * _atr(bars, i, 20)
        elif candidate == "E2-F":
            risk = _atr(bars, i, 14)
            stop, target = entry - 2 * risk, entry + 4 * risk
        if candidate == "E2-D":
            p = next((p for p, ix in enumerate(week_last) if ix == i), None)
            if p is None: continue
            end_week = min(len(weekly) - 1, p + 20)
            deadline = week_last[end_week]
            stop = min(x.low for x in weekly[max(0, p - 9):p + 1])
            exit_limit = deadline
        elif candidate == "E2-E":
            p = next((p for p, ix in enumerate(week_last) if ix == i), None)
            if p is None: continue
            exit_limit = week_last[min(len(weekly) - 1, p + 10)]
        else:
            exit_limit = min(len(bars) - 1, entry_i + hold)
        exit_i, exit_price, reason = None, None, "time"
        for j in range(entry_i, exit_limit + 1):
            bar = bars[j]
            # Conservative stop-first when both barriers trade in one candle.
            if stop is not None and bar.low <= stop:
                exit_i, exit_price, reason = j, min(bar.open, stop), "stop"
                break
            if target is not None and bar.high >= target:
                exit_i, exit_price, reason = j, max(bar.open, target), "target"
                break
            if candidate == "E2-C" and bar.high >= setup[2]:
                exit_i, exit_price = j, max(bar.open, setup[2]); break
            if candidate == "E2-E" and j in week_last:
                wp = week_last.index(j)
                if wp >= 9 and weekly[wp].close < _mean([x.close for x in weekly[wp - 9:wp + 1]]):
                    exit_i, exit_price = j, bar.close; break
        if exit_i is None:
            exit_i = exit_limit
            exit_price = (bars[exit_limit].open if candidate == "E2-A" and exit_limit == entry_i + hold
                          else bars[exit_limit].close)
        gross = exit_price / entry - 1
        net = gross - cost_bps / 10_000
        trades.append(Trade(candidate, i, entry_i, exit_i, entry, exit_price, reason, gross, cost_bps, net))
        busy_until = exit_i
    return trades, gaps


def _metrics(trades: list[Trade]) -> dict[str, object]:
    returns = [t.net_return for t in trades]
    wins = sum(x > 0 for x in returns)
    gross_profit = sum(x for x in returns if x > 0)
    gross_loss = -sum(x for x in returns if x < 0)
    return {"trades": len(trades), "win_rate_pct": 100 * wins / len(trades) if trades else None,
            "profit_factor": gross_profit / gross_loss if gross_loss else None,
            "expectancy_net_bps": 10_000 * sum(returns) / len(returns) if returns else None}


def _append_trials(rows: list[dict[str, object]], trials_path: Path) -> None:
    fields = ["trial_id", "round", "market_group", "utc_timestamp", "definition",
              "parameter_grid_hash", "code_sha256", "train_period", "metric", "rank", "notes"]
    if trials_path.exists() and trials_path.stat().st_size:
        with trials_path.open(newline="", encoding="utf-8") as handle:
            if next(csv.reader(handle)) != fields:
                raise ValueError("TRAIN_TRIALS.csv schema mismatch")
    code = hashlib.sha256()
    for name in ("search_equities_r4.py", "search_equities_r3.py", "data_access.py", "equities.py", "resource_guard.py"):
        code.update(name.encode() + b"\0" + (ROOT / name).read_bytes())
    code_sha = code.hexdigest()
    prereg = hashlib.sha256((ROOT / "PREREG.md").read_bytes()).hexdigest()
    now = datetime.now(timezone.utc).isoformat()
    with trials_path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        if handle.tell() == 0: writer.writeheader()
        for rank, result in enumerate(rows, 1):
            writer.writerow({"trial_id": f"R4-{result['market']}-{result['strategy']}", "round": "R4",
                "market_group": result["market"], "utc_timestamp": now,
                "definition": json.dumps(result["parameters"], sort_keys=True, separators=(",", ":")),
                "parameter_grid_hash": prereg, "code_sha256": code_sha,
                "train_period": "<=2018-10-26T23:59:00Z",
                "metric": json.dumps(result, sort_keys=True, separators=(",", ":")), "rank": rank,
                "notes": "TRAIN only; not G; PIT gated; survivorship-only view flagged when applicable"})


def run(universe_path: Path, membership_path: Path, split_file: Path,
        survivors_only: bool = False, trials_path: Path | None = None) -> list[dict[str, object]]:
    from search_equities_r3 import _load_train

    memberships = load_membership(membership_path)
    with universe_path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    required = {"market", "symbol", "daily_path"}
    if not rows or not required.issubset(rows[0]):
        raise ValueError(f"universe CSV requires {sorted(required)}")
    if any((row["market"], row["symbol"]) not in memberships for row in rows):
        raise ValueError("universe contains symbol without PIT membership record")
    if any(row["market"] not in MARKETS for row in rows):
        raise ValueError("universe market must be US or KR")
    results = []
    trial_rows = []
    survivor_rows = []
    trial_trades: dict[tuple[str, str], list[Trade]] = {}
    survivor_trades: dict[tuple[str, str], list[Trade]] = {}
    symbol_accounting: dict[str, dict[str, dict[str, object]]] = {}
    for row in rows:
        market, symbol = row["market"], row["symbol"]
        member = memberships[(market, symbol)]
        quality_stats: dict[str, int] = {"invalid_ohlc": 0, "halt_bars": 0}
        try:
            frame = _load_train(Path(row["daily_path"]).expanduser(), symbol, market, split_file)
            bars = _daily_bars(frame, member, quality_stats)
            symbol_accounting.setdefault(market, {})[symbol] = {"status": "valid", **quality_stats}
            for config in _configs():
                metrics = evaluate_c1(bars, market, member, config)
                results.append({"market": market, "symbol": symbol, "parameters": config, **metrics})
                if survivors_only and bars and member.alive(pd.Timestamp(bars[-1].timestamp, unit="ms", tz="UTC").date()):
                    survivor_rows.append({"market": market, "symbol": symbol, "strategy": "C1",
                        "parameters": {**config, "view": "survivors_only"}, **metrics,
                        "survivorship_biased": True, "status": "TRAIN_ONLY_NOT_G"})
            for offset, candidate in enumerate(NEW_CANDIDATES):
                code = f"E2-{chr(ord('A') + offset)}"
                trades, _ = simulate_e2(code, bars, market)
                accepted, gaps = survivorship_safe_trades(trades, bars, member)
                trial_trades.setdefault((market, code), []).extend(accepted)
                results.append({"market": market, "symbol": symbol, "strategy": code,
                                "parameters": {"candidate": code}, **_metrics(accepted),
                                "delisting_gap": gaps, "survivorship_biased": False,
                                "status": "TRAIN_ONLY_NOT_G"})
                if survivors_only and bars:
                    endpoint = pd.Timestamp(bars[-1].timestamp, unit="ms", tz="UTC").date()
                    if member.alive(endpoint):
                        survivor_trades.setdefault((market, code), []).extend(trades)
                        biased = {"market": market, "symbol": symbol, "strategy": code,
                            "parameters": {"candidate": code, "view": "survivors_only"},
                            **_metrics(trades), "survivorship_biased": True, "status": "TRAIN_ONLY_NOT_G"}
                        survivor_rows.append(biased)
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

    # One row per registered market/configuration, aggregating symbol-level trades.
    for market in MARKETS:
        c1_results = [r for r in results if r["market"] == market and r.get("parameters", {}).get("strategy") == "C1"]
        for config in _configs():
            subset = [r for r in c1_results if r["parameters"] == config]
            if subset:
                trial_rows.append({"market": market, "strategy": f"C1-{config['lookback']}-{config['retest_bars']}-{config['target_r']}-{config['holding_bars']}",
                    "parameters": config, "symbols": len(subset), "trades": sum(r["trades"] for r in subset),
                    "expectancy_net_bps": (sum(r["expectancy_net_bps"] for r in subset if r["expectancy_net_bps"] is not None) /
                        max(1, sum(r["expectancy_net_bps"] is not None for r in subset))),
                    "invalid_ohlc_rows_filtered": sum(int(a["invalid_ohlc"]) for a in symbol_accounting.get(market, {}).values()),
                    "halt_bars_filtered": sum(int(a["halt_bars"]) for a in symbol_accounting.get(market, {}).values()),
                    "symbols_quality_excluded": sum(a["status"] == "quality_excluded" for a in symbol_accounting.get(market, {}).values()),
                    "symbols_data_error": sum(a["status"] == "data_error" for a in symbol_accounting.get(market, {}).values()),
                    "symbol_accounting": symbol_accounting.get(market, {}),
                    "survivorship_biased": False, "status": "TRAIN_ONLY_NOT_G"})
        market_results = [r for r in results if r["market"] == market and r.get("strategy")]
        for candidate in [f"E2-{x}" for x in "ABCDEF"]:
            subset = [r for r in market_results if r["strategy"] == candidate]
            if subset:
                merged = {"market": market, "strategy": candidate, "parameters": {"candidate": candidate},
                          "symbols": len(subset), "trades": sum(r.get("trades", 0) for r in subset),
                          "invalid_ohlc_rows_filtered": sum(int(a["invalid_ohlc"]) for a in symbol_accounting.get(market, {}).values()),
                          "halt_bars_filtered": sum(int(a["halt_bars"]) for a in symbol_accounting.get(market, {}).values()),
                          "symbols_quality_excluded": sum(a["status"] == "quality_excluded" for a in symbol_accounting.get(market, {}).values()),
                    "symbols_data_error": sum(a["status"] == "data_error" for a in symbol_accounting.get(market, {}).values()),
                          "symbol_accounting": symbol_accounting.get(market, {}),
                          "survivorship_biased": False, "status": "TRAIN_ONLY_NOT_G"}
                merged.update(_metrics(trial_trades.get((market, candidate), [])))
                merged["symbols"] = len(subset)
                trial_rows.append(merged)
    if trials_path is not None and trial_rows:
        _append_trials(trial_rows, trials_path)
    for (market, candidate), trades in survivor_trades.items():
        survivor_rows.append({"market": market, "strategy": candidate,
            "parameters": {"candidate": candidate, "view": "survivors_only"},
            "symbols": sum(1 for r in rows if r["market"] == market),
            **_metrics(trades), "survivorship_biased": True, "status": "TRAIN_ONLY_NOT_G"})
    return results + survivor_rows


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
        raise RuntimeError("R4 requires an effective nice value of at least 10")
    if args.membership.resolve() == args.universe.resolve():
        raise ValueError("membership must be a separate PIT source file")
    with heavy_task("C"):
        results = run(args.universe, args.membership, args.split_file, args.survivors_only, args.trials)
    print(json.dumps({"rows": len(results), "train_cutoff_ms": EQUITY_COMMON_SPLIT_MS,
                      "new_candidates_registered": list(NEW_CANDIDATES),
                      "result_scope": "C1 weekly robustness and E2 A-F; train only",
                      "results": results}, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
