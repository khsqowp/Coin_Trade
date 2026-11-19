#!/usr/bin/env python3
"""Fixed-rule KODEX 200 volatility-target development backtest; standard library only."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
from datetime import datetime, timezone
from pathlib import Path

CUTOFF = datetime.fromisoformat("2024-11-12T00:00:00+00:00")
BASE_COST = 0.00115
STRESS_COST = 0.00165
SESSIONS_PER_YEAR = 252
TRIAL_ID = "KR-KODEX200-VOL10-LB20-20261120-DEV"
SENSITIVITY_LOOKBACKS = (16, 20, 24)
SENSITIVITY_TARGETS = (0.08, 0.10, 0.12)


def _finite(value: float, name: str) -> float:
    if not math.isfinite(value):
        raise ValueError(f"non-finite {name}")
    return value


def load_prefix(path: Path):
    """Read and fingerprint only CSV rows strictly before CUTOFF."""
    digest = hashlib.sha256()
    rows = []
    with path.open("rb") as stream:
        header = stream.readline()
        if not header:
            raise ValueError("empty input")
        digest.update(header)
        expected = ("timestamp", "Open", "High", "Low", "Close", "Volume")
        if tuple(next(csv.reader([header.decode("utf-8-sig").rstrip("\r\n")]))) != expected:
            raise ValueError("unexpected CSV header")
        for raw in stream:
            try:
                text = raw.decode("utf-8").rstrip("\r\n")
                stamp_text = text.partition(",")[0]
                stamp = datetime.fromisoformat(stamp_text.replace("Z", "+00:00"))
                if stamp.tzinfo is None:
                    raise ValueError("timestamp must carry a UTC offset")
                stamp = stamp.astimezone(timezone.utc)
            except Exception as exc:
                raise ValueError("invalid timestamp before cutoff") from exc
            if stamp >= CUTOFF:
                break
            digest.update(raw)
            fields = next(csv.reader([text]))
            if len(fields) != 6:
                raise ValueError("wrong field count")
            o, h, low, c, volume = map(float, fields[1:])
            vals = (o, h, low, c, volume)
            if not all(math.isfinite(v) for v in vals):
                raise ValueError(f"non-finite OHLCV at {stamp.isoformat()}")
            if min(o, h, low, c) <= 0 or volume < 0 or h < max(o, low, c) or low > min(o, h, c):
                raise ValueError(f"invalid OHLCV at {stamp.isoformat()}")
            if rows and stamp <= rows[-1][0]:
                raise ValueError("timestamps must be strictly increasing")
            rows.append((stamp, o, h, low, c, volume))
    if len(rows) < 300:
        raise ValueError("insufficient pre-cutoff history")
    return rows, digest.hexdigest()


def target_weight(closes: list[float], signal_i: int, lookback: int, target_vol: float) -> float:
    if lookback < 2 or signal_i < lookback:
        raise ValueError("insufficient volatility history")
    daily_returns = [closes[i] / closes[i - 1] - 1.0 for i in range(signal_i - lookback + 1, signal_i + 1)]
    mean = sum(daily_returns) / len(daily_returns)
    variance = sum((r - mean) ** 2 for r in daily_returns) / (len(daily_returns) - 1)
    annualized = math.sqrt(max(variance, 0.0)) * math.sqrt(SESSIONS_PER_YEAR)
    if annualized == 0.0:
        return 1.0
    return min(1.0, target_vol / annualized)


def _month_end_indices(rows):
    last = {}
    for i, row in enumerate(rows):
        key = (row[0].year, row[0].month)
        last[key] = i
    return set(last.values())


def _metric_block(nav, returns, dates, exposures, turnover, rebalance_count):
    if not returns or len(nav) != len(returns) + 1:
        raise ValueError("invalid NAV path")
    for value in nav + returns:
        _finite(value, "NAV/return")
    if any(x <= 0 for x in nav) or any(x <= -1 for x in returns):
        raise ValueError("nonpositive NAV or return <= -100%")
    years = (dates[-1] - dates[0]).total_seconds() / (365.2425 * 86400)
    if years <= 0:
        raise ValueError("nonpositive test duration")
    peak = nav[0]
    mdd = 0.0
    for value in nav:
        peak = max(peak, value)
        mdd = max(mdd, 1.0 - value / peak)
    mean = sum(returns) / len(returns)
    variance = sum((r - mean) ** 2 for r in returns) / max(1, len(returns) - 1)
    std = math.sqrt(variance)
    sharpe = mean / std * math.sqrt(SESSIONS_PER_YEAR) if std else 0.0
    annual = {}
    for date, ret in zip(dates[1:], returns):
        year = str(date.year)
        annual[year] = annual.get(year, 1.0) * (1.0 + ret)
    return {
        "start": dates[0].date().isoformat(), "end": dates[-1].date().isoformat(),
        "terminal_nav": nav[-1], "total_return_pct": (nav[-1] - 1.0) * 100.0,
        "cagr_pct": (nav[-1] ** (1.0 / years) - 1.0) * 100.0,
        "mdd_pct": mdd * 100.0, "sharpe_252": sharpe,
        "avg_exposure_pct": sum(exposures) / len(exposures) * 100.0,
        "one_way_turnover_x": turnover, "rebalance_events": rebalance_count,
        "annual_returns_pct": {k: (v - 1.0) * 100.0 for k, v in sorted(annual.items())},
        "nav": nav, "returns": returns, "dates": [d.isoformat() for d in dates],
        "exposures": exposures,
    }


def simulate(rows, lookback: int, target_vol: float, cost: float):
    closes = [r[4] for r in rows]
    opens = [r[1] for r in rows]
    dates = [r[0] for r in rows]
    month_ends = _month_end_indices(rows)
    schedule = {}
    for signal_i in sorted(month_ends):
        execution_i = signal_i + 1
        if signal_i >= lookback and execution_i < len(rows):
            schedule[execution_i] = target_weight(closes, signal_i, lookback, target_vol)
    if not schedule:
        raise ValueError("no eligible monthly rebalance")
    first_i = min(schedule)
    nav = [1.0]
    returns = []
    exposures = []
    weight = 0.0
    turnover = 0.0
    events = 0
    for i in range(first_i, len(rows) - 1):
        if i in schedule:
            new_weight = schedule[i]
            delta = abs(new_weight - weight)
            if delta > 1e-12:
                fee_factor = 1.0 - cost * delta
                turnover += delta
                events += 1
            else:
                fee_factor = 1.0
            weight = new_weight
        else:
            fee_factor = 1.0
        gross = opens[i + 1] / opens[i]
        ret = fee_factor * (1.0 + weight * (gross - 1.0)) - 1.0
        nav.append(nav[-1] * (1.0 + ret))
        returns.append(ret)
        exposures.append(weight)
    if weight > 0.0:
        exit_cost = cost * weight
        nav[-1] *= 1.0 - exit_cost
        if returns:
            previous_nav = nav[-2]
            returns[-1] = nav[-1] / previous_nav - 1.0
        turnover += weight
    path_dates = [dates[first_i]] + dates[first_i + 1:]
    # Reconcile net daily returns after open-time rebalance and terminal costs to NAV.
    check_nav = 1.0
    for ret in returns:
        check_nav *= 1.0 + ret
    if not math.isclose(check_nav, nav[-1], rel_tol=1e-9, abs_tol=1e-10):
        raise AssertionError("return path does not reconcile to terminal NAV")
    return _metric_block(nav, returns, path_dates, exposures, turnover, events)


def buy_hold(rows, cost: float):
    # Match the strategy's first and final open timestamps mechanically.
    closes = [r[4] for r in rows]
    first_exec = next(i + 1 for i in sorted(_month_end_indices(rows)) if i >= 20 and i + 1 < len(rows))
    opens = [r[1] for r in rows]
    dates = [r[0] for r in rows]
    nav = [1.0]
    returns = []
    for i in range(first_exec, len(rows) - 1):
        entry = (1.0 - cost) if i == first_exec else 1.0
        gross = opens[i + 1] / opens[i]
        ret = entry * gross - 1.0
        nav.append(nav[-1] * (1.0 + ret))
        returns.append(ret)
    nav[-1] *= 1.0 - cost
    returns[-1] = nav[-1] / nav[-2] - 1.0
    return _metric_block(nav, returns, [dates[first_exec]] + dates[first_exec + 1:], [1.0] * len(returns), 2.0, 1)


def cash_path(rows, first_date, last_date):
    dates = [r[0] for r in rows if first_date <= r[0] <= last_date]
    if len(dates) < 2:
        raise ValueError("cash benchmark has insufficient dates")
    returns = [0.0] * (len(dates) - 1)
    return _metric_block([1.0] * len(dates), returns, dates, [0.0] * len(returns), 0.0, 0)


def _percentile(values, q):
    ordered = sorted(values)
    pos = (len(ordered) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo)


def paired_block_bootstrap(strategy_returns, benchmark_returns, block=20, paths=1000, seed=20261120):
    if len(strategy_returns) != len(benchmark_returns) or len(strategy_returns) < block:
        raise ValueError("paired bootstrap requires aligned returns and at least one full block")
    rng = random.Random(seed)
    n = len(strategy_returns)
    dd_values = []
    log_wealth_diffs = []
    for _ in range(paths):
        s_nav = b_nav = s_peak = b_peak = 1.0
        s_dd = b_dd = 0.0
        count = 0
        while count < n:
            start = rng.randrange(0, n - block + 1)
            for j in range(start, min(start + block, n - count)):
                sr, br = strategy_returns[j], benchmark_returns[j]
                s_nav *= 1.0 + sr
                b_nav *= 1.0 + br
                s_peak = max(s_peak, s_nav)
                b_peak = max(b_peak, b_nav)
                s_dd = max(s_dd, 1.0 - s_nav / s_peak)
                b_dd = max(b_dd, 1.0 - b_nav / b_peak)
                count += 1
        dd_values.append(s_dd)
        log_wealth_diffs.append(math.log(s_nav) - math.log(b_nav))
    return {
        "paths": paths, "block_sessions": block, "seed": seed,
        "strategy_mdd_p95_pct": _percentile(dd_values, 0.95) * 100.0,
        "strategy_beats_benchmark_fraction": sum(x > 0 for x in log_wealth_diffs) / paths,
        "paired_log_wealth_difference_ci95": [_percentile(log_wealth_diffs, 0.025), _percentile(log_wealth_diffs, 0.975)],
    }


def period_metrics(result, start_year, end_year):
    dates = [datetime.fromisoformat(x) for x in result["dates"]]
    selected = [i for i in range(1, len(dates)) if start_year <= dates[i].year <= end_year]
    if not selected:
        return None
    nav = [1.0]
    returns = []
    out_dates = [dates[selected[0] - 1]]
    for i in selected:
        ret = result["returns"][i - 1]
        returns.append(ret)
        nav.append(nav[-1] * (1.0 + ret))
        out_dates.append(dates[i])
    return _metric_block(nav, returns, out_dates, [result["exposures"][i - 1] for i in selected], 0.0, 0)


def run(path: Path, out_dir: Path):
    rows, input_sha = load_prefix(path)
    primary = simulate(rows, 20, 0.10, BASE_COST)
    stress = simulate(rows, 20, 0.10, STRESS_COST)
    benchmark = buy_hold(rows, BASE_COST)
    benchmark_stress = buy_hold(rows, STRESS_COST)
    cash = cash_path(rows, datetime.fromisoformat(primary["start"] + "T00:00:00+00:00"), datetime.fromisoformat(primary["end"] + "T00:00:00+00:00"))
    # Candidate and buy-and-hold daily returns are aligned to identical open-to-open timestamps.
    primary_bootstrap = paired_block_bootstrap(primary["returns"], benchmark["returns"])
    stress_bootstrap = paired_block_bootstrap(stress["returns"], benchmark_stress["returns"])
    periods = {f"{a}-{b}": period_metrics(primary, a, b) for a, b in ((2010, 2014), (2015, 2019), (2020, 2024))}
    sensitivity = []
    for lookback in SENSITIVITY_LOOKBACKS:
        for target in SENSITIVITY_TARGETS:
            for case, cost in (("base", BASE_COST), ("stress", STRESS_COST)):
                res = simulate(rows, lookback, target, cost)
                sensitivity.append({"lookback": lookback, "target_vol_pct": target * 100, "cost_case": case,
                                   **{k: res[k] for k in ("terminal_nav", "cagr_pct", "mdd_pct", "sharpe_252", "rebalance_events")}})
    # Strip potentially large raw paths from the persisted summary after bootstrap/sensitivity.
    def compact(result):
        return {k: v for k, v in result.items() if k not in {"nav", "returns", "dates", "exposures"}}
    result = {
        "trial_id": TRIAL_ID, "status": "DEVELOPMENT_ONLY_EXPLORATORY",
        "data_source_path": str(path), "data_prefix_sha256_before_cutoff": input_sha,
        "cutoff_exclusive_utc": CUTOFF.isoformat(), "source_rows_before_cutoff": len(rows),
        "source_first_timestamp_utc": rows[0][0].isoformat(), "source_last_timestamp_utc": rows[-1][0].isoformat(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "primary_base": compact(primary), "primary_stress": compact(stress),
        "benchmark_kodex_base": compact(benchmark), "benchmark_kodex_stress": compact(benchmark_stress),
        "cash_benchmark": compact(cash),
        "paired_bootstrap_base_vs_kodex": primary_bootstrap,
        "paired_bootstrap_stress_vs_kodex": stress_bootstrap,
        "descriptive_periods_base": {k: compact(v) if v else None for k, v in periods.items()},
        "sensitivity": sensitivity,
        "limitations": [
            "No genuinely unseen OOS; this cache/window has been used in related exploratory studies.",
            "Only one Korean ETF; cannot represent all KR equities/ETFs or cross-sectional selection.",
            "KIS adjusted-price/corporate-action/distribution semantics and exact retrieval parameters are unverified.",
            "Zero-yield cash assumption; no taxes, market impact, tracking error, or intraday execution model.",
            "Sensitivity cells are diagnostics and were not used to select a replacement parameter.",
        ],
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "kr_kodex200_vol_target_20261120_dev.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("trial_id", "status", "source_rows_before_cutoff", "source_first_timestamp_utc", "source_last_timestamp_utc", "data_prefix_sha256_before_cutoff", "script_sha256", "primary_base", "primary_stress", "benchmark_kodex_base", "cash_benchmark", "paired_bootstrap_base_vs_kodex", "descriptive_periods_base")}, ensure_ascii=False, indent=2, allow_nan=False))
    print(f"saved={out_path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True, type=Path, help="read-only local KODEX 200 OHLCV CSV")
    parser.add_argument("--out-dir", type=Path, default=Path("docs/research/results"))
    args = parser.parse_args()
    run(args.data, args.out_dir)


if __name__ == "__main__":
    main()
