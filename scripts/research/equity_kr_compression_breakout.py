#!/usr/bin/env python3
"""Reproduce the frozen development-only KR ETF compression breakout test."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

CUTOFF = pd.Timestamp("2024-11-12T00:00:00Z")
COMMISSION = 0.00015
COSTS = {"base": 0.0010, "stress": 0.0015}


def json_safe(value):
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if isinstance(value, (float, np.floating)) and not math.isfinite(float(value)):
        return None
    if isinstance(value, (np.integer,)):
        return int(value)
    return value


def load_bars(path):
    digest = hashlib.sha256()
    dates, opens, closes = [], [], []
    with path.open("rb") as handle:
        header = handle.readline()
        digest.update(header)
        names = next(csv.reader([header.decode("utf-8").rstrip("\r\n")]))
        if not {"timestamp", "Open", "Close"}.issubset(names):
            raise ValueError("missing required CSV columns")
        columns = {name: i for i, name in enumerate(names)}
        previous = None
        for raw in handle:
            stamp_text = raw.partition(b",")[0].decode("utf-8")
            stamp = pd.Timestamp(stamp_text)
            if stamp >= CUTOFF:
                break
            if previous is not None and stamp <= previous:
                raise ValueError(f"non-monotonic timestamp: {stamp}")
            previous = stamp
            digest.update(raw)
            fields = next(csv.reader([raw.decode("utf-8").rstrip("\r\n")]))
            dates.append(stamp)
            opens.append(float(fields[columns["Open"]]))
            closes.append(float(fields[columns["Close"]]))
    return pd.DatetimeIndex(dates), np.asarray(opens), np.asarray(closes), digest.hexdigest()


def signals_and_features(close):
    close = pd.Series(close, dtype=float)
    returns = close.pct_change()
    vol10 = returns.rolling(10, min_periods=10).std(ddof=1)
    threshold = vol10.shift(1).rolling(252, min_periods=252).quantile(0.30)
    sma20 = close.rolling(20, min_periods=20).mean()
    sma200 = close.rolling(200, min_periods=200).mean()
    prior_high = close.shift(1).rolling(20, min_periods=20).max()
    previous_high = prior_high.shift(1)
    signal = (
        (vol10 <= threshold)
        & (close > prior_high)
        & (close.shift(1) <= previous_high)
        & (close > sma200)
    ).fillna(False).to_numpy(bool)
    return signal, sma20.to_numpy(), sma200.to_numpy(), threshold.to_numpy()


def block_cagr_ci(nav, dates, benchmark_nav=None, seed=69500, draws=10_000,
                  block_months=6):
    monthly_nav = pd.Series(nav, index=dates).resample("ME").last().dropna()
    returns = monthly_nav.pct_change().dropna().to_numpy()
    benchmark_returns = None
    if benchmark_nav is not None:
        benchmark_monthly = pd.Series(benchmark_nav, index=dates).resample("ME").last().dropna()
        benchmark_returns = benchmark_monthly.pct_change().dropna().to_numpy()
        if len(benchmark_returns) != len(returns):
            raise ValueError("paired monthly returns must align")
    if len(returns) < block_months:
        nan_pair = [float("nan"), float("nan")]
        return nan_pair, nan_pair
    rng = np.random.default_rng(seed)
    n = len(returns)
    block_count = int(np.ceil(n / block_months))
    offsets = np.arange(block_months)
    cagr = np.empty(draws)
    relative_cagr = np.empty(draws) if benchmark_returns is not None else None
    for draw in range(draws):
        starts = rng.integers(0, n, size=block_count)
        idx = np.concatenate([(start + offsets) % n for start in starts])[:n]
        cagr[draw] = np.prod(1 + returns[idx]) ** (12 / n) - 1
        if relative_cagr is not None:
            benchmark_cagr = np.prod(1 + benchmark_returns[idx]) ** (12 / n) - 1
            relative_cagr[draw] = cagr[draw] - benchmark_cagr
    ci = list(map(float, np.quantile(cagr, [0.025, 0.975])))
    if relative_cagr is None:
        return ci, [float("nan"), float("nan")]
    return ci, list(map(float, np.quantile(relative_cagr, [0.025, 0.975])))


def apply_buy(cash, price, slip):
    shares = cash / (price * (1 + slip) * (1 + COMMISSION))
    return 0.0, shares


def apply_sell(cash, shares, price, slip):
    return cash + shares * price * (1 - slip) * (1 - COMMISSION), 0.0


def summarize(name, nav, dates, turnover, trades, cost_case, benchmark_nav=None):
    years = (dates[-1] - dates[0]).total_seconds() / (365.2425 * 86400)
    cagr = (nav[-1] / nav[0]) ** (1 / years) - 1
    mdd = float(np.min(nav / np.maximum.accumulate(nav) - 1))
    ci, relative_ci = block_cagr_ci(nav, dates, benchmark_nav)
    return {
        "strategy": name, "cost_case": cost_case, "cagr_pct": 100 * cagr,
        "mdd_pct": 100 * mdd, "turnover_x": turnover / float(np.mean(nav)),
        "final_nav": float(nav[-1]), "cagr_block95_low_pct": 100 * ci[0],
        "cagr_block95_high_pct": 100 * ci[1], "trades": len(trades),
        "benchmark_relative_cagr_block95_low_pct": 100 * relative_ci[0],
        "benchmark_relative_cagr_block95_high_pct": 100 * relative_ci[1],
        "trade_years": len({pd.Timestamp(t["entry_date"]).year for t in trades}),
    }


def simulate_breakout(dates, opens, closes, signals, sma20, start, slip, cost_case,
                      benchmark_nav):
    n = len(dates)
    nav = np.ones(n - start)
    cash, shares, entry_index = 1.0, 0.0, None
    pending_entry, pending_exit, exit_reason = False, False, None
    turnover, trades = 0.0, []
    for i in range(start, n):
        if pending_exit:
            exit_notional = shares * opens[i]
            cash, shares = apply_sell(cash, shares, opens[i], slip)
            turnover += exit_notional
            trade = trades[-1]
            trade.update(exit_date=dates[i].isoformat(), exit_open=float(opens[i]),
                         exit_reason=exit_reason,
                         net_return_pct=100 * (cash / trade["starting_nav"] - 1),
                         gross_return_pct=100 * (opens[i] / trade["entry_open"] - 1))
            pending_exit, exit_reason, entry_index = False, None, None
        if pending_entry:
            starting_nav = cash
            cash, shares = apply_buy(cash, opens[i], slip)
            turnover += shares * opens[i]
            entry_index = i
            trades.append({
                "signal_date": dates[i - 1].isoformat(), "entry_date": dates[i].isoformat(),
                "entry_open": float(opens[i]), "starting_nav": starting_nav,
                "cost_case": cost_case,
            })
            pending_entry = False
        nav[i - start] = cash + shares * closes[i]
        if shares > 0:
            held = i - entry_index + 1
            if closes[i] < sma20[i]:
                pending_exit, exit_reason = True, "close_below_sma20"
            elif held >= 10:
                pending_exit, exit_reason = True, "10_session_expiry"
        elif signals[i] and i < n - 1:
            pending_entry = True
    if shares > 0 or pending_exit or pending_entry:
        raise AssertionError("position not completely closed before cutoff")
    row = summarize("compression_breakout_069500", nav, dates[start:], turnover,
                    trades, cost_case, benchmark_nav)
    return row, trades, nav


def simulate_sma200(dates, opens, closes, sma200, start, slip, cost_case):
    nav = np.ones(len(dates) - start)
    cash, shares, turnover = 1.0, 0.0, 0.0
    for i in range(start, len(dates)):
        desired = closes[i - 1] > sma200[i - 1] if i > 0 else False
        if desired and shares == 0:
            cash, shares = apply_buy(cash, opens[i], slip)
            turnover += shares * opens[i]
        elif not desired and shares > 0:
            notional = shares * opens[i]
            cash, shares = apply_sell(cash, shares, opens[i], slip)
            turnover += notional
        nav[i - start] = cash + shares * closes[i]
    if shares > 0:
        notional = shares * closes[-1]
        cash, shares = apply_sell(cash, shares, closes[-1], slip)
        turnover += notional
        nav[-1] = cash
    return summarize("sma200_long_cash", nav, dates[start:], turnover, [], cost_case), nav


def simulate_buy_hold(dates, opens, closes, start, slip, cost_case):
    cash, shares = apply_buy(1.0, opens[start], slip)
    nav = shares * closes[start:]
    turnover = shares * opens[start]
    notional = shares * closes[-1]
    cash, _ = apply_sell(0.0, shares, closes[-1], slip)
    turnover += notional
    nav[-1] = cash
    return summarize("069500_buy_hold", nav, dates[start:], turnover, [], cost_case), nav


def run(data_path, output, trades_output):
    dates, opens, closes, digest = load_bars(data_path)
    signals, sma20, sma200, threshold = signals_and_features(closes)
    eligible = np.flatnonzero(np.isfinite(sma200) & np.isfinite(threshold))
    if not len(eligible):
        raise ValueError("insufficient history")
    start = int(eligible[0])
    # Remove signals that cannot complete the maximum 10 sessions plus next-open exit.
    tail = np.zeros(len(signals), dtype=bool)
    tail[:max(0, len(signals) - 11)] = True
    skipped_tail = int(np.count_nonzero(signals & ~tail))
    signals &= tail
    summaries, trade_output = [], []
    for cost_case, slip in COSTS.items():
        hold_row, hold_nav = simulate_buy_hold(dates, opens, closes, start, slip, cost_case)
        strategy, trades, _ = simulate_breakout(
            dates, opens, closes, signals, sma20, start, slip, cost_case, hold_nav
        )
        trend_row, _ = simulate_sma200(dates, opens, closes, sma200, start, slip, cost_case)
        summaries.extend((strategy, hold_row, trend_row, {
            "strategy": "cash", "cost_case": cost_case, "cagr_pct": 0.0,
            "mdd_pct": 0.0, "turnover_x": 0.0, "final_nav": 1.0,
            "cagr_block95_low_pct": 0.0, "cagr_block95_high_pct": 0.0,
            "benchmark_relative_cagr_block95_low_pct": 0.0,
            "benchmark_relative_cagr_block95_high_pct": 0.0,
            "trades": 0, "trade_years": 0,
        }))
        trade_output.extend(trades)
    result = {
        "hypothesis": "069500 low-volatility compression plus 20-session close breakout above SMA200; next-open entry; exit next open below SMA20 or after 10 completed sessions",
        "symbol": "069500", "cutoff_exclusive": CUTOFF.isoformat(),
        "source_sha256": digest, "source_pre_cutoff_rows": len(dates),
        "evaluation_start": dates[start].isoformat(), "evaluation_end": dates[-1].isoformat(),
        "signal_count": int(np.count_nonzero(signals)), "skipped_tail_signals": skipped_tail,
        "summary": summaries, "trades": trade_output,
        "limitations": [
            "Previously inspected development data; not OOS",
            "Corporate-action and distribution adjustment are not independently verified",
            "Costs are assumed, not measured fills; cash earns zero; no liquidity or account sizing",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(json_safe(result), indent=2, allow_nan=False) + "\n", encoding="utf-8")
    trades_output.write_text(json.dumps(json_safe(trade_output), indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in (
        "source_sha256", "source_pre_cutoff_rows", "evaluation_start",
        "evaluation_end", "signal_count", "skipped_tail_signals", "summary"
    )}, indent=2))
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=Path(".kis-cache-local/KR_069500.csv"))
    parser.add_argument("--output", type=Path, default=Path(
        "docs/research/equity_kr_compression_breakout_20261115.json"
    ))
    parser.add_argument("--trades", type=Path, default=Path(
        "docs/research/equity_kr_compression_breakout_trades_20261115.json"
    ))
    args = parser.parse_args()
    run(args.data, args.output, args.trades)


if __name__ == "__main__":
    main()
