#!/usr/bin/env python3
"""Exploratory KR stress-reversal and US 12-1 momentum event studies."""
import argparse
import csv
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

CACHE = Path(__file__).resolve().parents[2] / ".kis-cache-local"
CUTOFF = pd.Timestamp("2024-11-12T00:00:00Z")
EVAL_START = None
KR_ETFS = {
    "069500", "091160", "091170", "091180", "102110", "102970", "114260", "114800",
    "117460", "117680", "117700", "132030", "133690", "139230", "139260", "140700",
    "140710", "143860", "148070", "153130", "157490", "229200", "244580", "261240",
    "305720", "307950",
}
US_ETFS = {
    "BIL", "DBC", "EEM", "EFA", "GLD", "IBB", "IEF", "ITA", "IWM", "KRE", "MTUM",
    "QQQ", "QUAL", "SH", "SHY", "SMH", "SOXX", "SPY", "TIP", "TLT", "USMV", "UUP",
    "VNQ", "VLUE", "XBI", "XHB", "XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP",
    "XLRE", "XLU", "XLV", "XLY", "XME",
}
US_BASE_COST, US_STRESS_COST = 0.0036, 0.0122
KR_COMM, KR_TAX, KR_BASE_SLIP, KR_STRESS_SLIP = 0.00015, 0.0018, 0.0010, 0.0020


def load_daily(path):
    records = []
    with path.open(encoding="utf-8") as stream:
        header = next(stream).strip().split(",")
        col = {name: i for i, name in enumerate(header)}
        previous = None
        for line in stream:
            stamp = pd.Timestamp(line.partition(",")[0])
            if stamp >= CUTOFF:
                break
            if previous is not None and stamp <= previous:
                raise ValueError(f"non-monotonic timestamp: {path}")
            previous = stamp
            fields = line.rstrip("\r\n").split(",")
            records.append((stamp, *(float(fields[col[k]]) for k in ("Open", "High", "Low", "Close", "Volume"))))
    return {r[0]: (r[1], r[2], r[3], r[4], r[5]) for r in records}


def month_ends(calendar):
    by_month = {}
    for day in calendar:
        by_month[day.strftime("%Y-%m")] = day
    return list(by_month.values())


def clustered_ci(values, dates, seed, block_months=1):
    if not values:
        return (float("nan"), float("nan"))
    groups = defaultdict(list)
    for value, day in zip(values, dates):
        groups[day.strftime("%Y-%m")].append(value)
    first, last = pd.Period(min(groups), freq="M"), pd.Period(max(groups), freq="M")
    months = [str(period) for period in pd.period_range(first, last, freq="M")]
    rng = np.random.default_rng(seed)
    means = np.empty(2000)
    for b in range(len(means)):
        sampled = []
        if block_months == 1:
            chosen = rng.choice(len(months), len(months), replace=True)
            for i in chosen:
                sampled.extend(groups[months[i]])
        else:
            blocks = int(np.ceil(len(months) / block_months))
            starts = rng.integers(0, max(1, len(months) - block_months + 1), blocks)
            for start in starts:
                for i in range(start, min(start + block_months, len(months))):
                    sampled.extend(groups[months[i]])
            means[b] = np.mean(sampled) if sampled else np.nan
    return tuple(map(float, np.nanquantile(means, [0.025, 0.975])))


def net_kr(entry, exit_price, slip):
    buy = KR_COMM + slip
    sell = KR_COMM + KR_TAX + slip
    return (exit_price / entry) * (1 - sell) / (1 + buy) - 1


def kr_stress_reversal():
    market = load_daily(CACHE / "KR_069500.csv")
    calendar = sorted(market)
    files = sorted(CACHE.glob("KR_*.csv"))
    stocks = {p.stem[3:]: load_daily(p) for p in files if p.stem[3:] not in KR_ETFS}
    samples = defaultdict(list)
    cohort_rows = []
    for i in range(6, len(calendar) - 6):
        day, signal_window = calendar[i], calendar[i - 5:i + 1]
        if EVAL_START is not None and day < EVAL_START:
            continue
        market_ret = market[day][3] / market[calendar[i - 1]][3] - 1
        ranked = []
        for symbol, prices in stocks.items():
            if any(d not in prices for d in signal_window):
                continue
            entry_day, exit_day = calendar[i + 1], calendar[i + 5]
            trade_window = calendar[i + 1:i + 6]
            if entry_day not in prices or exit_day not in prices:
                continue
            if any(d not in prices for d in trade_window):
                continue
            values = [prices[d] for d in signal_window]
            if min(x[3] for x in values) <= 0 or prices[entry_day][0] <= 0:
                continue
            ranked.append((prices[day][3] / prices[calendar[i - 5]][3] - 1, symbol,
                           prices[entry_day][0], prices[exit_day][3]))
        if len(ranked) < 10:
            continue
        ranked.sort()
        count = max(1, int(np.ceil(len(ranked) * 0.10)))
        low_decile = ranked[:count]
        stress = market_ret <= -0.02
        candidates = low_decile if stress else []
        for name, group in (("stress_bottom_decile", candidates), ("all_day_bottom_decile", low_decile)):
            if not group:
                continue
            for cost, slip in (("base", KR_BASE_SLIP), ("stress", KR_STRESS_SLIP)):
                daily = float(np.mean([net_kr(x[2], x[3], slip) for x in group]))
                samples[(name, cost)].append((daily, day, len(group)))
        if stress:
            etf_entry, etf_exit = market[calendar[i + 1]][0], market[calendar[i + 5]][3]
            etf_stress = net_kr(etf_entry, etf_exit, KR_STRESS_SLIP)
            cohort_rows.append((day, market_ret, len(low_decile),
                                float(np.mean([net_kr(x[2], x[3], KR_BASE_SLIP) for x in low_decile])),
                                float(np.mean([net_kr(x[2], x[3], KR_STRESS_SLIP) for x in low_decile])),
                                net_kr(etf_entry, etf_exit, KR_BASE_SLIP), etf_stress))
    out = []
    for (strategy, cost), data in sorted(samples.items()):
        values, dates = [x[0] * 100 for x in data], [x[1] for x in data]
        out.append({"market": "KR", "strategy": strategy, "cost_case": cost,
                    "signal_days": len(data), "event_count": sum(x[2] for x in data),
                    "mean_cohort_net_pct": float(np.mean(values)),
                    "median_cohort_net_pct": float(np.median(values)),
                    "six_month_block95_pct": clustered_ci(values, dates, 119 + (cost == "stress") + (strategy != "stress_bottom_decile"), 6),
                    "benchmark": "069500 stress proxy; event-study cohorts, no account sizing"})
    dates = [x[0] for x in cohort_rows]
    for j, (cost, stock_col, etf_col) in enumerate((("base", 3, 5), ("stress", 4, 6))):
        values = [x[etf_col] * 100 for x in cohort_rows]
        out.append({"market": "KR", "strategy": "069500_same_5session_stress_cohorts", "cost_case": cost,
                    "signal_days": len(values), "event_count": len(values),
                    "mean_cohort_net_pct": float(np.mean(values)) if values else float("nan"),
                    "median_cohort_net_pct": float(np.median(values)) if values else float("nan"),
                    "six_month_block95_pct": clustered_ci(values, dates, 129 + j, 6),
                    "benchmark": "069500 ETF held next open through close after 5 sessions"})
        differences = [(x[stock_col] - x[etf_col]) * 100 for x in cohort_rows]
        out.append({"market": "KR", "strategy": "stress_bottom_decile_minus_069500_matched", "cost_case": cost,
                    "signal_days": len(differences), "event_count": len(differences),
                    "mean_cohort_net_pct": float(np.mean(differences)) if differences else float("nan"),
                    "median_cohort_net_pct": float(np.median(differences)) if differences else float("nan"),
                    "six_month_block95_pct": clustered_ci(differences, dates, 139 + j, 6),
                    "benchmark": "paired stress-date cohort return spread"})
        for year in sorted({x[0].year for x in cohort_rows}):
            group = [x for x in cohort_rows if x[0].year == year]
            out.append({"market": "KR", "strategy": "stress_bottom_decile_annual", "cost_case": cost,
                        "year": year, "signal_days": len(group), "event_count": sum(x[2] for x in group),
                        "mean_cohort_net_pct": float(np.mean([x[stock_col] for x in group]) * 100),
                        "matched_069500_mean_pct": float(np.mean([x[etf_col] for x in group]) * 100),
                        "benchmark": "annual descriptive breakdown; not an independent test"})
    return out, {"kr_stock_files": len(stocks), "stress_days": len(cohort_rows), "first_stress": str(cohort_rows[0][0].date()) if cohort_rows else "", "last_stress": str(cohort_rows[-1][0].date()) if cohort_rows else ""}


def us_momentum():
    spy = load_daily(CACHE / "US_SPY.csv")
    calendar = sorted(spy)
    stock_files = [p for p in sorted(CACHE.glob("US_*.csv")) if p.stem[3:] not in US_ETFS]
    data = {p.stem[3:]: load_daily(p) for p in stock_files}
    cohort_values, broad_values, benchmark_values, signal_dates = [], [], [], []
    for day in month_ends(calendar):
        if EVAL_START is not None and day < EVAL_START:
            continue
        i = calendar.index(day)
        if i < 253 or i + 1 >= len(calendar):
            continue
        entry_day = calendar[i + 1]
        next_month = (day.year + (day.month == 12), 1 if day.month == 12 else day.month + 1)
        exit_days = [d for d in calendar if (d.year, d.month) == next_month]
        if not exit_days:
            continue
        exit_day = exit_days[-1]
        scores = []
        for symbol, prices in data.items():
            past, recent = calendar[i - 252], calendar[i - 21]
            if any(d not in prices for d in calendar[i - 252:i + 1]) or any(d not in prices for d in (entry_day, exit_day)):
                continue
            if prices[past][3] <= 0 or prices[entry_day][0] <= 0:
                continue
            score = prices[recent][3] / prices[past][3] - 1
            gross = prices[exit_day][0] / prices[entry_day][0] - 1
            scores.append((score, symbol, gross))
        if len(scores) < 20:
            continue
        scores.sort(reverse=True)
        top = scores[:int(np.ceil(len(scores) * 0.20))]
        base_gross = float(np.mean([x[2] for x in top]))
        broad_gross = float(np.mean([x[2] for x in scores]))
        spy_gross = spy[exit_day][0] / spy[entry_day][0] - 1
        cohort_values.append((base_gross - US_BASE_COST, base_gross - US_STRESS_COST))
        broad_values.append((broad_gross - US_BASE_COST, broad_gross - US_STRESS_COST))
        benchmark_values.append((spy_gross - US_BASE_COST, spy_gross - US_STRESS_COST))
        signal_dates.append(day)
    out = []
    for label, values in (("top_quintile_12_1", cohort_values), ("eligible_universe_equal_cohort", broad_values), ("SPY_same_month", benchmark_values)):
        if not values:
            continue
        for j, cost in enumerate(("base", "stress")):
            sample = [x[j] * 100 for x in values]
            out.append({"market": "US", "strategy": label, "cost_case": cost,
                        "month_cohorts": len(sample), "mean_net_pct_per_month": float(np.mean(sample)),
                        "median_net_pct_per_month": float(np.median(sample)),
                        "six_month_block95_pct": clustered_ci(sample, signal_dates, 219 + j + (label != "top_quintile_12_1"), 6),
                        "benchmark": "cross-sectional monthly cohort event study; no account sizing"})
    for label, comparator in (("top_quintile_minus_universe", broad_values), ("top_quintile_minus_SPY", benchmark_values)):
        if not cohort_values or not comparator:
            continue
        for j, cost in enumerate(("base", "stress")):
            diffs = [(cohort_values[i][j] - comparator[i][j]) * 100 for i in range(len(cohort_values))]
            out.append({"market": "US", "strategy": label, "cost_case": cost,
                        "month_cohorts": len(diffs), "mean_net_pct_per_month": float(np.mean(diffs)),
                        "median_net_pct_per_month": float(np.median(diffs)),
                        "six_month_block95_pct": clustered_ci(diffs, signal_dates, 319 + j + (label != "top_quintile_minus_universe"), 6),
                        "benchmark": "paired monthly return spread; equal costs cancel"})
    for year in sorted({day.year for day in signal_dates}):
        indices = [i for i, day in enumerate(signal_dates) if day.year == year]
        for cost_index, cost in enumerate(("base", "stress")):
            out.append({"market": "US", "strategy": "12_1_momentum_annual", "cost_case": cost,
                        "year": year, "month_cohorts": len(indices),
                        "mean_top_quintile_pct": float(np.mean([cohort_values[i][cost_index] for i in indices]) * 100),
                        "mean_universe_pct": float(np.mean([broad_values[i][cost_index] for i in indices]) * 100),
                        "mean_SPY_pct": float(np.mean([benchmark_values[i][cost_index] for i in indices]) * 100),
                        "mean_excess_universe_pct": float(np.mean([cohort_values[i][cost_index] - broad_values[i][cost_index] for i in indices]) * 100),
                        "benchmark": "annual descriptive breakdown; not an independent test"})
    return out, {"us_stock_files": len(data), "first_month": str(signal_dates[0].date()) if signal_dates else "", "last_month": str(signal_dates[-1].date()) if signal_dates else ""}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv-out", type=Path, required=True)
    parser.add_argument("--start", help="optional evaluation start; earlier rows are lookback-only")
    parser.add_argument("--end-exclusive", help="exclusive data/evaluation end")
    args = parser.parse_args()
    global CUTOFF, EVAL_START
    if args.start:
        EVAL_START = pd.to_datetime(args.start, utc=True)
    if args.end_exclusive:
        CUTOFF = pd.to_datetime(args.end_exclusive, utc=True)
    kr_rows, kr_meta = kr_stress_reversal()
    us_rows, us_meta = us_momentum()
    rows = kr_rows + us_rows
    for row in rows:
        row["evaluation_start_utc"] = EVAL_START.isoformat() if EVAL_START is not None else "full_pre_cutoff_dev"
        row["end_exclusive_utc"] = CUTOFF.isoformat()
    args.csv_out.parent.mkdir(parents=True, exist_ok=True)
    with args.csv_out.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(dict.fromkeys(k for row in rows for k in row)), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print("KR", kr_meta)
    print("US", us_meta)
    for row in rows:
        print(row)


if __name__ == "__main__":
    main()
