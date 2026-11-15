#!/usr/bin/env python3
"""Development-only KR/US ETF momentum screen before the equity holdout."""
import argparse
import csv
from pathlib import Path

import numpy as np
import pandas as pd

CACHE = Path(__file__).resolve().parents[2] / ".kis-cache-local"
CUTOFF = pd.Timestamp("2024-11-12T00:00:00Z")
KR_ETFS = (
    "069500", "091160", "091170", "091180", "102110", "102970", "114260", "114800",
    "117460", "117680", "117700", "132030", "133690", "139230", "139260", "140700",
    "140710", "143860", "148070", "153130", "157490", "229200", "244580", "261240",
    "305720", "307950",
)
US_ETFS = ("SPY", "QQQ", "IEF", "GLD", "DBC", "SHY")


def load(prefix, symbols):
    frames = {}
    for symbol in symbols:
        path = CACHE / f"{prefix}_{symbol}.csv"
        if not path.exists():
            continue
        records = []
        previous = None
        with path.open(encoding="utf-8") as stream:
            next(stream, None)  # header
            for line in stream:
                timestamp_text = line.partition(",")[0]
                timestamp = pd.Timestamp(timestamp_text)
                if timestamp >= CUTOFF:
                    break  # inspect only the timestamp; do not parse OHLCV past cutoff
                if previous is not None and timestamp <= previous:
                    raise ValueError(f"timestamps not strictly increasing before cutoff: {path}")
                previous = timestamp
                fields = line.rstrip("\r\n").split(",")
                records.append((timestamp, float(fields[1]), float(fields[4])))
        frame = pd.DataFrame(records, columns=("timestamp", "Open", "Close")).set_index("timestamp")
        if not frame.empty:
            frames[symbol] = frame
    return frames


def metrics(nav, net, exposure, turnover, name, costs):
    years = (nav.index[-1] - nav.index[0]).days / 365.2425
    drawdown = nav / nav.cummax() - 1
    annual = ((1 + net).groupby(net.index.year).prod() - 1) * 100
    return {
        "strategy": name, "cost_one_way_pct": costs * 100,
        "start": str(nav.index[0].date()), "end": str(nav.index[-1].date()),
        "cagr_pct": float((nav.iloc[-1] ** (1 / years) - 1) * 100),
        "mdd_pct": float(-drawdown.min() * 100),
        "sharpe": float(net.mean() / net.std() * np.sqrt(252)) if net.std() else 0.0,
        "exposure_pct": float(np.mean(exposure) * 100),
        "one_way_turnover_x": float(turnover),
        "annual_returns_pct": {str(int(year)): float(value) for year, value in annual.items()},
    }


def run_rotation(frames, name, one_way_cost, weighting="equal"):
    close = pd.concat({symbol: frame.Close for symbol, frame in frames.items()}, axis=1).sort_index()
    close = close.dropna(how="all").ffill()
    opens = pd.concat({symbol: frame.Open for symbol, frame in frames.items()}, axis=1)
    opens = opens.reindex(close.index).ffill()
    momentum = close / close.shift(126) - 1
    realized_vol = close.pct_change().rolling(60, min_periods=60).std()
    periods = close.index.tz_localize(None).to_period("M") if close.index.tz else close.index.to_period("M")
    month_ends = set(pd.Series(np.arange(len(close)), index=close.index).groupby(periods).last().to_numpy())
    start_idx = int(close.index.searchsorted(pd.Timestamp("2011-01-01", tz="UTC")))
    if start_idx < 1 or start_idx >= len(close):
        raise ValueError("need at least one pre-start bar and data after 2011-01-01")
    cash = 1.0
    shares = {symbol: 0.0 for symbol in close.columns}
    nav_values = [1.0]
    nav_dates = [close.index[start_idx - 1]]
    exposure_values = [0.0]
    turnover_values = []
    initial_entry_turnover = 0.0
    for i in range(start_idx, len(close)):
        day = close.index[i]
        op = opens.loc[day]
        nav_open = cash + sum(q * op[symbol] for symbol, q in shares.items()
                              if q and pd.notna(op[symbol]))
        turnover_fraction = 0.0
        if i and i - 1 in month_ends:
            scores = momentum.loc[close.index[i - 1]].dropna()
            picks = scores[scores > 0].nlargest(3).index.tolist()
            if weighting == "inverse_volatility" and picks:
                vol = realized_vol.loc[close.index[i - 1], picks].replace(0.0, np.nan).dropna()
                inverse = 1 / vol
                inverse = inverse / inverse.sum()
                weights = inverse.to_dict()
            else:
                weights = {symbol: 1 / len(picks) for symbol in picks} if picks else {}
            desired = {
                symbol: nav_open * weights[symbol] / op[symbol]
                if symbol in weights and pd.notna(op[symbol]) and op[symbol] > 0 else 0.0
                for symbol in close.columns
            }
            scale = 1.0
            for _ in range(3):
                target = {symbol: quantity * scale for symbol, quantity in desired.items()}
                turnover_dollars = sum(abs((target[symbol] - shares[symbol]) * op[symbol])
                                       for symbol in close.columns if pd.notna(op[symbol]))
                gross_buy = sum(target[symbol] * op[symbol] for symbol in close.columns
                                if pd.notna(op[symbol]))
                charges = turnover_dollars * one_way_cost
                if gross_buy + charges <= nav_open or gross_buy + charges <= 0:
                    break
                scale *= nav_open / (gross_buy + charges)
            target = {symbol: quantity * scale for symbol, quantity in desired.items()}
            turnover_dollars = sum(abs((target[symbol] - shares[symbol]) * op[symbol])
                                   for symbol in close.columns if pd.notna(op[symbol]))
            charges = turnover_dollars * one_way_cost
            gross_buy = sum(target[symbol] * op[symbol] for symbol in close.columns
                            if pd.notna(op[symbol]))
            previous_invested = sum(shares[symbol] * op[symbol] for symbol in close.columns
                                    if shares[symbol] and pd.notna(op[symbol]))
            if previous_invested <= 0 and gross_buy > 0 and initial_entry_turnover == 0:
                initial_entry_turnover = turnover_dollars / max(nav_open, 1e-12)
            cash = nav_open - gross_buy - charges
            shares = target
            turnover_fraction = turnover_dollars / max(nav_open, 1e-12)
        nav_post_trade = cash + sum(q * op[symbol] for symbol, q in shares.items()
                                    if q and pd.notna(op[symbol]))
        invested = sum(q * op[symbol] for symbol, q in shares.items()
                       if q and pd.notna(op[symbol]))
        nav_values.append(nav_post_trade)
        nav_dates.append(day)
        exposure_values.append(invested / nav_post_trade if nav_post_trade else 0.0)
        turnover_values.append(turnover_fraction)

    # Liquidate at the final observed open and include the one-way exit cost.
    final_open = opens.iloc[-1]
    final_invested = sum(q * final_open[symbol] for symbol, q in shares.items()
                         if q and pd.notna(final_open[symbol]))
    final_nav_before_exit = nav_values[-1]
    nav_values[-1] -= final_invested * one_way_cost
    exposure_values[-1] = 0.0
    terminal_one_way_turnover = final_invested / max(final_nav_before_exit, 1e-12)
    nav = pd.Series(nav_values, index=nav_dates)
    net = nav.pct_change().dropna()
    exposure = np.asarray(exposure_values)
    one_way_turnover = float(sum(turnover_values) / 2 + initial_entry_turnover / 2
                              + terminal_one_way_turnover)
    return metrics(nav, net, exposure, one_way_turnover, f"{name} ({weighting})", one_way_cost)


def run_buy_hold(frame, symbol, one_way_cost):
    opened = frame.Open
    opened = opened[opened.index < CUTOFF]
    start_idx = int(opened.index.searchsorted(pd.Timestamp("2011-01-01", tz="UTC")))
    if start_idx < 1 or start_idx >= len(opened):
        raise ValueError(f"need pre-start and post-start prices for {symbol}")
    prices = opened.iloc[start_idx:]
    # Start with cash at the preceding session, pay entry cost when buying at
    # the first in-period open, then pay exit cost on the final observed open.
    shares = 1 / (prices.iloc[0] * (1 + one_way_cost))
    values = shares * prices.to_numpy(float)
    values[-1] *= 1 - one_way_cost
    nav = pd.Series(np.r_[1.0, values], index=opened.index[start_idx - 1:].copy())
    years = (nav.index[-1] - nav.index[0]).days / 365.2425
    drawdown = nav / nav.cummax() - 1
    return {"benchmark": symbol, "cost_one_way_pct": one_way_cost * 100,
            "cagr_pct": float((nav.iloc[-1] ** (1 / years) - 1) * 100),
            "mdd_pct": float(-drawdown.min() * 100)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv-out", type=Path, help="optional summary CSV output")
    args = parser.parse_args()
    kr = load("KR", KR_ETFS)
    us = load("US", US_ETFS)
    rows = [
        run_rotation(kr, "KR ETF top-3 126-session positive momentum monthly", 0.00115),
        run_rotation(kr, "KR ETF top-3 126-session positive momentum monthly stress", 0.00165),
        run_rotation(us, "US ETF top-3 126-session positive momentum monthly", 0.0018),
        run_rotation(us, "US ETF top-3 126-session positive momentum monthly stress", 0.0061),
        run_rotation(kr, "KR ETF top-3 126-session positive momentum monthly", 0.00115, "inverse_volatility"),
        run_rotation(kr, "KR ETF top-3 126-session positive momentum monthly stress", 0.00165, "inverse_volatility"),
        run_rotation(us, "US ETF top-3 126-session positive momentum monthly", 0.0018, "inverse_volatility"),
        run_rotation(us, "US ETF top-3 126-session positive momentum monthly stress", 0.0061, "inverse_volatility"),
        run_buy_hold(kr["069500"], "KR 069500 buy-and-hold base cost", 0.00115),
        run_buy_hold(kr["069500"], "KR 069500 buy-and-hold stress cost", 0.00165),
        run_buy_hold(us["SPY"], "US SPY buy-and-hold base cost", 0.0018),
        run_buy_hold(us["SPY"], "US SPY buy-and-hold stress cost", 0.0061),
    ]
    for row in rows:
        print(row)
    if args.csv_out:
        args.csv_out.parent.mkdir(parents=True, exist_ok=True)
        fields = list(dict.fromkeys(key for row in rows for key in row))
        with args.csv_out.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)


if __name__ == "__main__":
    main()
