#!/usr/bin/env python3
"""Fixed exploratory KR daily failed-breakdown event study; no portfolio sizing."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from datetime import date
from pathlib import Path

import numpy as np

KR_ETFS = {
    "069500", "091160", "091170", "091180", "102110", "102970", "114260", "114800",
    "117460", "117680", "117700", "132030", "133690", "139230", "139260", "140700",
    "140710", "143860", "148070", "153130", "157490", "229200", "244580", "261240",
    "305720", "307950", "360750", "449450",
}
CUTOFF = date(2024, 11, 12)
LOOKBACK = 20
HOLD_SESSIONS = 5
COMM = 0.00015
TAX = 0.0018
BASE_SLIP = 0.0010
STRESS_SLIP = 0.0020
ETF_SLIP = 0.0010


def load_before_cutoff(path: Path) -> tuple[dict[date, dict[str, float]], str]:
    rows: dict[date, dict[str, float]] = {}
    digest = hashlib.sha256()
    with path.open(encoding="utf-8", newline="") as stream:
        header = next(stream).rstrip("\r\n")
        expected = "timestamp,Open,High,Low,Close,Volume"
        if header != expected:
            raise ValueError(f"unexpected header in {path}: {header}")
        digest.update((header + "\n").encode())
        previous = None
        for line in stream:
            timestamp_text = line.partition(",")[0]
            stamp = date.fromisoformat(timestamp_text[:10])
            if stamp >= CUTOFF:
                break
            if previous is not None and stamp <= previous:
                raise ValueError(f"non-monotonic pre-cutoff dates in {path}")
            previous = stamp
            fields = next(csv.reader([line]))
            values = {key.lower(): float(value) for key, value in
                      zip(("Open", "High", "Low", "Close", "Volume"), fields[1:])}
            if not all(np.isfinite(value) for value in values.values()):
                raise ValueError(f"non-finite pre-cutoff value in {path} at {stamp}")
            rows[stamp] = values
            digest.update(line.encode())
    return rows, digest.hexdigest()


def failed_breakdown_signal(prior_lows, signal_low: float, signal_close: float) -> bool:
    """At close t, reject a fresh 20-session low that closes back above that level."""
    if len(prior_lows) != LOOKBACK or not all(np.isfinite(x) and x > 0 for x in prior_lows):
        return False
    level = min(prior_lows)
    return bool(np.isfinite(signal_low) and np.isfinite(signal_close)
                and signal_low < level and signal_close > level)


def net_long(entry: float, exit_price: float, slip: float, *, etf: bool = False) -> float:
    buy_cost = COMM + slip
    sell_cost = COMM + slip + (0.0 if etf else TAX)
    return exit_price * (1 - sell_cost) / (entry * (1 + buy_cost)) - 1


def moving_block_ci(values: list[float], month_keys: list[str], *, seed: int,
                    replicates: int = 5000, block_months: int = 6) -> list[float] | None:
    if not values:
        return None
    grouped: dict[str, list[float]] = defaultdict(list)
    for value, key in zip(values, month_keys):
        grouped[key].append(value)
    first_year, first_month = map(int, min(grouped).split("-"))
    last_year, last_month = map(int, max(grouped).split("-"))
    months = []
    year, month = first_year, first_month
    while (year, month) <= (last_year, last_month):
        months.append(f"{year:04d}-{month:02d}")
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    if len(months) < block_months:
        return None
    rng = np.random.default_rng(seed)
    blocks = int(np.ceil(len(months) / block_months))
    draws = np.empty(replicates, dtype=float)
    for draw in range(replicates):
        sampled = []
        for start in rng.integers(0, len(months), size=blocks):
            for offset in range(block_months):
                index = (int(start) + offset) % len(months)
                sampled.extend(grouped.get(months[index], ()))
        draws[draw] = float(np.mean(sampled)) if sampled else np.nan
    return [float(x) for x in np.nanquantile(draws, [0.025, 0.975])]


def run(cache: Path) -> dict:
    paths = sorted(cache.glob("KR_*.csv"))
    loaded = {path.stem[3:]: load_before_cutoff(path) for path in paths}
    if "069500" not in loaded:
        raise ValueError("KR 069500 market-proxy cache is missing")
    benchmark, _ = loaded["069500"]
    calendar = sorted(benchmark)
    stock_symbols = [symbol for symbol in sorted(loaded)
                     if symbol not in KR_ETFS and symbol.isdigit()]
    records = []
    counts = defaultdict(lambda: {"eligible": 0, "signals": 0, "trades": 0, "censored": 0})

    for symbol in stock_symbols:
        prices, _ = loaded[symbol]
        last_exit = -1
        for i in range(LOOKBACK, len(calendar) - HOLD_SESSIONS):
            required = calendar[i - LOOKBACK:i + HOLD_SESSIONS + 1]
            if any(day not in prices for day in required):
                continue
            counts[symbol]["eligible"] += 1
            prior_lows = [prices[day]["low"] for day in calendar[i - LOOKBACK:i]]
            current = prices[calendar[i]]
            if not failed_breakdown_signal(prior_lows, current["low"], current["close"]):
                continue
            counts[symbol]["signals"] += 1
            entry_i, exit_i = i + 1, i + HOLD_SESSIONS
            if entry_i <= last_exit:
                continue
            entry_day, exit_day = calendar[entry_i], calendar[exit_i]
            entry = prices[entry_day]["open"]
            exit_price = prices[exit_day]["close"]
            etf_entry = benchmark[entry_day]["open"]
            etf_exit = benchmark[exit_day]["close"]
            if min(entry, exit_price, etf_entry, etf_exit) <= 0:
                counts[symbol]["censored"] += 1
                continue
            row = {"symbol": symbol, "signal_date": calendar[i].isoformat(),
                   "entry_date": entry_day.isoformat(), "exit_date": exit_day.isoformat(),
                   "gross_return": exit_price / entry - 1,
                   "benchmark_gross_return": etf_exit / etf_entry - 1,
                   "net_base": net_long(entry, exit_price, BASE_SLIP),
                   "net_stress": net_long(entry, exit_price, STRESS_SLIP),
                   "benchmark_net_base": net_long(etf_entry, etf_exit, ETF_SLIP, etf=True),
                   "benchmark_net_stress": net_long(etf_entry, etf_exit, ETF_SLIP * 2, etf=True)}
            records.append(row)
            counts[symbol]["trades"] += 1
            last_exit = exit_i

    def summarize(values, dates, seed):
        arr = np.asarray(values, dtype=float)
        positive = (arr > 0).astype(float)
        n = len(arr)
        p = float(positive.mean()) if n else None
        if n:
            z = 1.959963984540054
            denominator = 1 + z * z / n
            center = (p + z * z / (2 * n)) / denominator
            half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
            wilson = [float(center - half), float(center + half)]
        else:
            wilson = None
        positive_ci = moving_block_ci(list(positive), dates, seed=seed + 1)
        mean_ci = moving_block_ci(list(arr), dates, seed=seed)
        return {"n": int(len(arr)), "mean_pct": float(arr.mean() * 100) if len(arr) else None,
                "median_pct": float(np.median(arr) * 100) if len(arr) else None,
                "positive_rate": p, "positive_rate_wilson95": wilson,
                "six_month_block_ci_positive_rate":
                    [x * 100 for x in positive_ci] if positive_ci else None,
                "six_month_block_ci_mean_pct":
                    [x * 100 for x in mean_ci] if mean_ci else None}

    signal_months = [row["signal_date"][:7] for row in records]
    base = [row["net_base"] for row in records]
    stress = [row["net_stress"] for row in records]
    delta_base = [row["net_base"] - row["benchmark_net_base"] for row in records]
    delta_stress = [row["net_stress"] - row["benchmark_net_stress"] for row in records]
    per_symbol_metrics = {}
    for symbol in stock_symbols:
        subset = [row for row in records if row["symbol"] == symbol]
        months = [row["signal_date"][:7] for row in subset]
        per_symbol_metrics[symbol] = {
            "base_net_trade_return": summarize([row["net_base"] for row in subset], months,
                                                2026111510 + len(per_symbol_metrics)),
            "stress_net_trade_return": summarize([row["net_stress"] for row in subset], months,
                                                  2026111520 + len(per_symbol_metrics)),
            "paired_minus_069500_base": summarize(
                [row["net_base"] - row["benchmark_net_base"] for row in subset], months,
                2026111530 + len(per_symbol_metrics)),
        }
    years = sorted({row["signal_date"][:4] for row in records})
    event_hash = hashlib.sha256()
    for row in records:
        event_hash.update((json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n").encode())
    yearly = []
    for year in years:
        subset = [row for row in records if row["signal_date"].startswith(year)]
        values = [row["net_base"] for row in subset]
        yearly.append({"year": year, "events": len(subset),
                       "mean_net_base_pct": float(np.mean(values) * 100),
                       "positive_rate": float(np.mean(np.asarray(values) > 0))})
    return {
        "status": "DEVELOPMENT_ONLY_EXPLORATORY_NOT_OOS",
        "hypothesis": "long after a daily low breaks the prior 20-session low but closes back above it; enter next session open, exit at the close of the fifth holding session",
        "cutoff_exclusive": CUTOFF.isoformat(),
        "lookback_sessions": LOOKBACK, "holding_sessions_including_entry": HOLD_SESSIONS,
        "universe": stock_symbols, "universe_count": len(stock_symbols),
        "data_rows_by_symbol": {symbol: len(rows) for symbol, (rows, _) in loaded.items()},
        "data_bounds_by_symbol": {
            symbol: ([min(rows).isoformat(), max(rows).isoformat()] if rows else None)
            for symbol, (rows, _) in loaded.items()},
        "pre_cutoff_hashes": {symbol: digest for symbol, (_, digest) in loaded.items()},
        "counts_by_symbol": {
            symbol: {**values,
                     "signal_coverage": values["signals"] / values["eligible"]
                         if values["eligible"] else 0.0,
                     "executed_trade_coverage": values["trades"] / values["eligible"]
                         if values["eligible"] else 0.0}
            for symbol, values in sorted(counts.items())},
        "events": len(records), "event_rows_sha256": event_hash.hexdigest(),
        "metrics_by_symbol": per_symbol_metrics,
        "base_cost": {"buy_commission": COMM, "sell_commission": COMM,
                      "sell_tax_stock": TAX, "slippage_each_side": BASE_SLIP},
        "stress_cost": {"buy_commission": COMM, "sell_commission": COMM,
                        "sell_tax_stock": TAX, "slippage_each_side": STRESS_SLIP},
        "benchmark_cost": {"commission_each_side": COMM, "slippage_each_side_base": ETF_SLIP,
                            "slippage_each_side_stress": ETF_SLIP * 2, "sell_tax": 0},
        "metrics": {
            "base_net_trade_return": summarize(base, signal_months, 2026111501),
            "stress_net_trade_return": summarize(stress, signal_months, 2026111502),
            "paired_minus_069500_base": summarize(delta_base, signal_months, 2026111503),
            "paired_minus_069500_stress": summarize(delta_stress, signal_months, 2026111504),
        },
        "yearly_base": yearly,
        "limitations": [
            "This is a post-hoc exploratory screen on repeatedly viewed current-cache data; no OOS claim.",
            "Universe is current/survivor-selected, not point-in-time and lacks delisted securities.",
            "Prices are local KIS adjusted-price cache; historical adjustment provenance is not independently verified.",
            "Event-study returns do not represent a capital-sized portfolio or annual return.",
            "Six-month circular calendar-month block intervals preserve shared month shocks, but do not cluster by symbol; treat as descriptive.",
            "No spread/depth/partial-fill data; slippage is an explicit assumption, not measured execution.",
            "The fixed 20-session and five-session horizons were selected once for this candidate, not searched in this run; the broader research history still creates multiplicity risk.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", required=True, type=Path, help="local .kis-cache directory")
    parser.add_argument("--output", required=True, type=Path, help="write result JSON outside the input cache")
    args = parser.parse_args()
    result = run(args.cache)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    metrics = result["metrics"]
    print(json.dumps({"events": result["events"], "symbols": result["universe_count"],
                      "base": metrics["base_net_trade_return"],
                      "stress": metrics["stress_net_trade_return"],
                      "paired_base": metrics["paired_minus_069500_base"],
                      "paired_stress": metrics["paired_minus_069500_stress"]}, indent=2))


if __name__ == "__main__":
    main()
