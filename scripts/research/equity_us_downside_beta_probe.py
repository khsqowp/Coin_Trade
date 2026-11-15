#!/usr/bin/env python3
"""Frozen, local-only ETF downside-beta backtest; reads only pre-cutoff cache rows."""
from pathlib import Path
import argparse
import json

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / ".kis-cache-local"
CUTOFF = pd.Timestamp("2024-11-12", tz="UTC")
UNIVERSE = ("SPY", "QQQ", "IEF", "GLD", "DBC", "SHY")
BENCHMARKS = ("SPY", "BIL")
BASE_RT = 0.0036
STRESS_RT = 0.0122
SEED = 20261115
BOOTSTRAPS = 10_000
BLOCK_MONTHS = 12


def read_prices(ticker, cache):
    path = cache / f"US_{ticker}.csv"
    rows = []
    with path.open(encoding="utf-8") as stream:
        next(stream)
        previous = None
        for line in stream:
            stamp = pd.Timestamp(line.partition(",")[0])
            if stamp >= CUTOFF:
                break
            if previous is not None and stamp <= previous:
                raise ValueError(f"non-increasing timestamp in {path}")
            previous = stamp
            fields = line.rstrip("\r\n").split(",")
            rows.append((stamp, float(fields[1]), float(fields[4])))
    return pd.DataFrame(rows, columns=("date", "open", "close")).set_index("date")


def bootstrap_ci(returns):
    values = np.asarray(returns, dtype=float)
    n = len(values)
    if n < BLOCK_MONTHS:
        return [float("nan"), float("nan")]
    rng = np.random.default_rng(SEED)
    block_count = int(np.ceil(n / BLOCK_MONTHS))
    offsets = np.arange(BLOCK_MONTHS)
    samples = np.empty(BOOTSTRAPS)
    for draw in range(BOOTSTRAPS):
        starts = rng.integers(0, n, size=block_count)
        indexes = np.concatenate([(start + offsets) % n for start in starts])[:n]
        samples[draw] = np.prod(1 + values[indexes]) ** (12 / n) - 1
    return (np.quantile(samples, [0.025, 0.975]) * 100).tolist()


def run(cache=CACHE):
    prices = {ticker: read_prices(ticker, cache) for ticker in (*UNIVERSE, *BENCHMARKS)}
    close = pd.concat({ticker: prices[ticker].close for ticker in UNIVERSE}, axis=1)
    close = close.dropna(how="any")
    daily = close.pct_change().dropna()
    all_close = pd.concat(
        {ticker: prices[ticker].close for ticker in (*UNIVERSE, *BENCHMARKS)}, axis=1
    ).dropna(how="any")
    all_close = all_close.loc[all_close.index < CUTOFF]
    valid_months = set(all_close.index.to_period("M"))
    calendar_months = pd.period_range(
        close.index.min().to_period("M"),
        (CUTOFF - pd.Timedelta(days=1)).to_period("M"),
        freq="M",
    )
    full_months = []
    for month in calendar_months:
        if month.end_time.tz_localize("UTC") >= CUTOFF or month not in valid_months:
            continue
        complete_days = all_close.index[all_close.index.to_period("M") == month]
        candidate_days = close.index[close.index.to_period("M") == month]
        if len(complete_days) and complete_days.equals(candidate_days):
            full_months.append(month)
    month_end_positions = {
        month: int(np.flatnonzero(close.index.to_period("M") == month)[-1])
        for month in full_months
    }
    selected = {}
    for month in full_months:
        previous_month = month - 1
        if previous_month not in month_end_positions:
            continue
        end = month_end_positions[previous_month]
        if end < 60:
            continue
        window = daily.iloc[end - 59:end + 1]
        if len(window) != 60 or window.isna().any().any():
            continue
        downside = window.loc[window.SPY < 0]
        if len(downside) < 2 or downside.SPY.var(ddof=1) <= 0:
            continue
        beta = {
            ticker: downside[ticker].cov(downside.SPY) / downside.SPY.var(ddof=1)
            for ticker in UNIVERSE
        }
        beta = {ticker: value for ticker, value in beta.items() if np.isfinite(value)}
        if len(beta) < 3:
            continue
        low_beta = sorted(beta, key=lambda ticker: (beta[ticker], ticker))[:3]
        momentum = (1 + window).prod() - 1
        high_momentum = sorted(
            UNIVERSE, key=lambda ticker: (-float(momentum[ticker]), ticker)
        )[:3]
        selected[month] = {"downside_beta": low_beta, "momentum": high_momentum}
    evaluation_months = [month for month in full_months if month in selected]
    if len(evaluation_months) < 24:
        raise RuntimeError(f"insufficient complete eligible months: {len(evaluation_months)}")

    def simulate(strategy, round_trip_cost):
        nav = 1.0
        daily_nav = []
        turnover = 0.0
        prior_weights = {ticker: 0.0 for ticker in (*UNIVERSE, *BENCHMARKS)}
        first_days = all_close.index[all_close.index.to_period("M") == evaluation_months[0]]
        baseline = all_close.index[all_close.index < first_days[0]][-1]
        daily_nav.append((baseline, nav))
        for month in evaluation_months:
            if strategy == "SPY":
                weights = {"SPY": 1.0}
            elif strategy == "BIL":
                weights = {"BIL": 1.0}
            else:
                picks = selected[month][strategy]
                weights = {ticker: 1 / len(picks) for ticker in picks}
            tickers = set(prior_weights) | set(weights)
            l1_turnover = sum(
                abs(weights.get(ticker, 0) - prior_weights.get(ticker, 0))
                for ticker in tickers
            )
            nav *= 1 - round_trip_cost / 2 * l1_turnover
            turnover += l1_turnover / 2
            month_days = all_close.index[all_close.index.to_period("M") == month]
            preceding_day = all_close.index[all_close.index < month_days[0]][-1:]
            path = all_close.loc[preceding_day.append(month_days)]
            for index in range(1, len(path)):
                daily_returns = path.iloc[index] / path.iloc[index - 1] - 1
                portfolio_return = sum(
                    weights.get(ticker, 0) * daily_returns[ticker] for ticker in weights
                )
                nav *= 1 + portfolio_return
                daily_nav.append((path.index[index], nav))
            prior_weights = {ticker: weights.get(ticker, 0) for ticker in prior_weights}
        curve = pd.Series(dict(daily_nav)).sort_index()
        curve = curve[~curve.index.duplicated(keep="last")]
        month_nav = curve.groupby(curve.index.to_period("M")).last()
        month_nav = month_nav[month_nav.index >= evaluation_months[0]]
        monthly_returns = month_nav.pct_change()
        if len(monthly_returns):
            monthly_returns.iloc[0] = month_nav.iloc[0] - 1
        terminal_fee = round_trip_cost / 2 * sum(prior_weights.values())
        curve.iloc[-1] *= 1 - terminal_fee
        month_nav.iloc[-1] *= 1 - terminal_fee
        turnover += sum(prior_weights.values()) / 2
        monthly_returns.iloc[-1] = (
            month_nav.iloc[-1] / (month_nav.iloc[-2] if len(month_nav) > 1 else 1) - 1
        )
        return curve, monthly_returns, turnover

    results = []
    for cost in (BASE_RT, STRESS_RT):
        for strategy in ("downside_beta", "momentum", "SPY", "BIL"):
            curve, monthly, turnover = simulate(strategy, cost)
            years = (curve.index[-1] - curve.index[0]).days / 365.2425
            cagr = curve.iloc[-1] ** (1 / years) - 1
            drawdown = curve / curve.cummax() - 1
            annual = ((1 + monthly).groupby(monthly.index.year).prod() - 1) * 100
            results.append({
                "strategy": strategy, "round_trip_cost_pct": cost * 100,
                "months": len(monthly), "start": str(curve.index[0].date()),
                "end": str(curve.index[-1].date()), "CAGR_pct": cagr * 100,
                "MDD_pct": drawdown.min() * 100,
                "annual_turnover_x": turnover / years, "total_turnover_x": turnover,
                "annual_returns_pct": {str(int(year)): float(value)
                                       for year, value in annual.items()},
                "CAGR_CI95_pct": bootstrap_ci(monthly),
            })
    fingerprints = {}
    for ticker, frame in prices.items():
        series = frame.loc[frame.index < CUTOFF, "close"]
        returns = series.pct_change().dropna()
        fingerprints[ticker] = {
            "rows": len(series),
            "first": str(series.index[0].date()) if len(series) else None,
            "last": str(series.index[-1].date()) if len(series) else None,
            "sum_daily_returns": float(returns.sum()),
            "sum_squared_daily_returns": float((returns * returns).sum()),
        }
    exclusions = {
        "calendar_months_before_cutoff": len(calendar_months),
        "partial_or_missing_price_months": len(calendar_months) - len(full_months),
        "months_without_60_session_signal": len(full_months) - len(selected),
        "evaluated_months": len(evaluation_months),
        "universe": "SPY,QQQ,IEF,GLD,DBC,SHY; BIL benchmark only",
    }
    return {"exclusions": exclusions, "pre_cutoff_data_fingerprint": fingerprints,
            "results": results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, default=CACHE)
    args = parser.parse_args()
    print(json.dumps(run(args.cache), indent=2))
