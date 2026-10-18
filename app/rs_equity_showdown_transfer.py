"""Transfer the 112 crypto showdown policy combinations to US/KR stocks.

This is a daily long/short equity adaptation. The source crypto maintenance
margin rule remains a synthetic stress proxy because stock-specific broker
margin/liquidation rules are not present in the local market data.
"""
from __future__ import annotations

import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd

from app.crypto_strategy_showdown import LEVERAGES, REGIMES, STOP_MODES, STOP_PCTS
from app.rs_equity_round12_13_portfolio import _costs
from app.rs_equity_transfer import EquityPanel, load_equity_panel

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/research/equity_transfer_2026-10/full_runs/showdown_policy_transfer.json"
START = pd.Timestamp("2019-01-01")
LOOKBACK, REBALANCE, TOP_K = 14, 3, 8
FUNDING_DRAG = .04
MAINT_MARGIN = .005


def configurations():
    out = []
    for regime, mode, stop, leverage in itertools.product(REGIMES, STOP_MODES, STOP_PCTS, LEVERAGES):
        if mode == "none" and stop != 0.0:
            continue
        if mode != "none" and stop == 0.0:
            continue
        out.append({"regime": regime, "mode": mode, "stop_pct": stop, "leverage": leverage})
    return out


def portfolio_inputs(panel: EquityPanel):
    dates = panel.dates
    n = len(dates)
    close = pd.DataFrame(panel.c, index=dates, columns=panel.symbols)
    valid = np.isfinite(panel.c) & (panel.c > 0) & panel.eligible
    returns = close.pct_change(fill_method=None).to_numpy(float)
    momentum = close.pct_change(LOOKBACK, fill_method=None).to_numpy(float)
    proxy = pd.Series(panel.proxy_close, index=dates)
    bull = (proxy > proxy.rolling(200, min_periods=200).mean()).fillna(False).to_numpy(bool)
    start = max(LOOKBACK + 1, 200, int(dates.searchsorted(START)))
    out_dates = dates[start:]
    result = {}
    for regime in REGIMES:
        weights = np.zeros(len(panel.symbols), dtype=float)
        daily_ret, delta_abs, long_sell = [], [], []
        for i in range(start, n):
            row = np.nan_to_num(returns[i], nan=0.0, posinf=0.0, neginf=0.0)
            daily_ret.append(float(np.dot(weights, row)))
            delta_abs.append(np.zeros_like(weights))
            long_sell.append(np.zeros_like(weights))
            if (i - start) % REBALANCE == 0:
                scores = momentum[i].copy()
                scores[~valid[i]] = np.nan
                eligible = np.flatnonzero(np.isfinite(scores))
                if len(eligible) >= TOP_K * 2:
                    order = sorted(eligible, key=lambda j: (-scores[j], panel.symbols[j]))
                    long_weight, short_weight = .5, .5
                    if regime == "regime_tilt" and bull[i]:
                        long_weight, short_weight = .7, .3
                    elif regime == "regime_longonly" and bull[i]:
                        long_weight, short_weight = 1., 0.
                    elif regime == "regime_cash":
                        long_weight, short_weight = (1., 0.) if bull[i] else (0., 0.)
                    new_weights = np.zeros_like(weights)
                    if long_weight:
                        new_weights[order[:TOP_K]] = long_weight / TOP_K
                    if short_weight:
                        new_weights[order[-TOP_K:]] = -short_weight / TOP_K
                    delta = new_weights - weights
                    delta_abs[-1] = np.abs(delta)
                    # Distinguish KR tax on reduced long exposure from short trades.
                    long_sell[-1] = np.maximum(np.minimum(-delta, np.maximum(weights, 0.)), 0.)
                    weights = new_weights
        result[regime] = {
            "returns": np.asarray(daily_ret), "turnover_by_symbol": np.asarray(delta_abs),
            "long_sell_by_symbol": np.asarray(long_sell),
        }
    return out_dates, result, bull[start:]


def simulate(inputs, dates, bull, config, cost, market):
    port = inputs[config["regime"]]["returns"]
    turnover = inputs[config["regime"]]["turnover_by_symbol"]
    long_sell = inputs[config["regime"]]["long_sell_by_symbol"]
    cost_name, fee_pct, slip, tax = cost
    fee = fee_pct / 100.
    slippage = np.asarray(slip, dtype=float)
    if slippage.ndim == 0:
        slippage = np.full(turnover.shape[1], float(slippage))
    leverage, stop_pct, mode = config["leverage"], config["stop_pct"], config["mode"]
    base_funding = FUNDING_DRAG / 365.
    borrow_annual = .01 if market == "US" else .03
    equity = peak = 1.
    mdd = 0.
    halted = 0
    delevered = False
    liquidation_date = None
    curve, daily, yearly, year_start = [], [], {}, {}
    for k, day in enumerate(dates):
        year_start.setdefault(day.year, equity)
        effective_leverage = leverage / 2 if mode == "delever" and delevered else leverage
        if mode == "flatten" and halted > 0:
            halted -= 1
            if halted == 0 and not bull[k]:
                halted = 1
            curve.append(equity); daily.append(0.)
            yearly[day.year] = equity / year_start[day.year] - 1.
            continue
        fee_cost = float(np.dot(turnover[k], fee + slippage)) * effective_leverage
        tax_cost = float(long_sell[k].sum()) * tax * effective_leverage
        short_exposure = .5 if config["regime"] in ("neutral", "regime_tilt") else (0. if bull[k] else .5)
        if config["regime"] == "regime_tilt" and bull[k]:
            short_exposure = .3
        borrow = short_exposure * borrow_annual / 365. * effective_leverage
        funding = base_funding * max(effective_leverage - 1., 0.)
        r = port[k] * effective_leverage - fee_cost - tax_cost - borrow - funding
        liquidation_threshold = 1. / effective_leverage - MAINT_MARGIN
        if r <= -liquidation_threshold:
            equity = 0.
            liquidation_date = str(day.date())
            daily.append(r); curve.append(equity)
            yearly[day.year] = -1.
            break
        equity *= 1. + r
        daily.append(r); curve.append(equity)
        peak = max(peak, equity)
        drawdown = (peak - equity) / peak
        mdd = max(mdd, drawdown)
        yearly[day.year] = equity / year_start[day.year] - 1.
        if stop_pct > 0 and drawdown >= stop_pct:
            if mode == "flatten":
                halted = 5
            elif mode == "delever":
                delevered = True
        if mode == "delever" and delevered and equity >= peak:
            delevered = False
    years = max((dates[len(curve)-1] - dates[0]).days / 365.25, 1/365.25)
    returns = pd.Series(daily, dtype=float)
    insolvent = equity <= 0.
    cagr = -100. if insolvent else (equity ** (1./years) - 1.) * 100.
    mdd = 100. if insolvent else mdd * 100.
    sharpe = float(returns.mean() / returns.std() * np.sqrt(365.)) if returns.std() > 0 else 0.
    return {
        "config": config, "cost_case": cost_name,
        "metrics": {"cagr": cagr, "mdd": mdd, "sharpe": sharpe,
                    "final": float(equity), "insolvent": bool(insolvent),
                    "liquidation_date": liquidation_date, "years": years},
        "daily_dates": [str(d.date()) for d in dates[:len(curve)]],
        "daily_equity": [float(x) for x in curve],
        "daily_returns": [float(x) for x in daily],
        "yearly_returns_pct": {str(y): round(v * 100., 4) for y, v in sorted(yearly.items())},
    }


def run_market(market):
    panel = load_equity_panel(market)
    dates, inputs, bull = portfolio_inputs(panel)
    configs = configurations()
    if len(configs) != 112:
        raise AssertionError(f"source showdown grid expected 112 configurations, got {len(configs)}")
    rows = []
    for i, config in enumerate(configs, 1):
        for cost in _costs(panel):
            rows.append(simulate(inputs, dates, bull, config, cost, market))
        if i % 20 == 0:
            print(f"{market}: {i}/112 showdown configurations", flush=True)
    return {"market": market, "symbols": panel.symbols,
            "dates": [str(d.date()) for d in dates], "configuration_count": 112,
            "row_count": len(rows), "rows": rows,
            "definition": "14d cross-sectional momentum, rebalance every 3 daily bars, top/bottom 8, next-day holdings; stock proxy regime; crypto liquidation barrier retained as synthetic stress only."}


def run():
    payload = {"markets": {m: run_market(m) for m in ("US", "KR")}}
    payload["row_count"] = sum(x["row_count"] for x in payload["markets"].values())
    OUT.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"US": payload["markets"]["US"]["row_count"],
                      "KR": payload["markets"]["KR"]["row_count"],
                      "total": payload["row_count"]}))
    return payload


if __name__ == "__main__":
    run()
