#!/usr/bin/env python3
"""Round 6: volatility-targeted exposure overlay on US 126-session daily top-10 momentum.

Preregistered (fixed before the single run, no retry):
  * Stock selection and daily rebalance are identical to
    `equity_trend_gate_probe.us_run(..., gated=False, rebalance='daily')`.
  * realized_vol_t = sample std (ddof=1) of the last 20 daily returns of the
    *pre-overlay* momentum portfolio (same cost scenario), annualized by sqrt(252),
    using closes through t.
  * scale_t = min(1, target_vol / realized_vol_{t-1}) (Round 6: 0.15; Round 7: 0.22 via --target-vol); scale_t = 1 when realized_vol_{t-1}
    is missing (first 20 returns of warmup), zero or non-finite. No leverage.
  * At each open the account holds scale_t x NAV in the top-10 equal weights and the
    rest in zero-interest cash. Scale changes alter share counts, so they enter the
    same per-name |delta shares x open| turnover that is charged fee+slippage.
  * Costs reused unchanged: US base 8+10 bp, stress 36+25 bp per side.
"""
import argparse
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from equity_trend_gate_probe import K, metrics, read_market, us_run  # noqa: E402

TARGET_VOL = 0.15
LOOKBACK = 20
MAX_SCALE = 1.0
SCENARIOS = (('base', .0008, .0010), ('stress', .0036, .0025))


def _inputs(frames):
    """Same calendar / momentum construction as us_run (ungated)."""
    common_close = pd.concat({s: f.Close for s, f in frames.items()}, axis=1).dropna(how='any').sort_index()
    symbols = sorted(frames)
    common_open = pd.concat({s: frames[s].Open.reindex(common_close.index) for s in symbols}, axis=1)[symbols]
    common_close = common_close[symbols]
    momentum = pd.concat({s: (frames[s].Close / frames[s].Close.shift(126) - 1).reindex(common_close.index)
                          for s in symbols}, axis=1)[symbols]
    return symbols, common_open, common_close, momentum


def us_ledger(frames, fee, slip, scales=None):
    """Copy of us_run's daily ungated ledger with an optional per-day exposure scale.

    scales: pd.Series indexed by date (scale applied at that day's open) or None (=1.0).
    Returns (nav series, exposure list, cumulative one-way turnover).
    """
    symbols, common_open, common_close, momentum = _inputs(frames)
    dates = common_close.index
    cash = 1.; shares = {s: 0. for s in symbols}; navs = []; exposure = []; total_turnover = 0.
    for j, day in enumerate(dates):
        op = common_open.loc[day]
        close = common_close.loc[day]
        nav_open = cash + sum(q * op[s] for s, q in shares.items() if q and pd.notna(op[s]))
        if j:
            signal_day = dates[j - 1]
            scores = momentum.loc[signal_day].dropna().nlargest(K)
            weights = {s: 1 / len(scores) for s in scores.index} if len(scores) else {}
            k = 1. if scales is None else float(scales.loc[day])
            target = {s: (nav_open * weights[s] * k / op[s] if s in weights and pd.notna(op[s]) and op[s] > 0 else 0.)
                      for s in symbols}
            turnover = sum(abs((target[s] - shares[s]) * op[s]) for s in symbols if pd.notna(op[s]))
            charges = turnover * (fee + slip)
            gross_buy = sum(target[s] * op[s] for s in symbols if pd.notna(op[s]))
            if gross_buy + charges > nav_open and charges > 0:
                scale = nav_open / (gross_buy + charges)
                target = {s: q * scale for s, q in target.items()}
                turnover = sum(abs((target[s] - shares[s]) * op[s]) for s in symbols if pd.notna(op[s]))
                charges = turnover * (fee + slip)
                gross_buy = sum(target[s] * op[s] for s in symbols if pd.notna(op[s]))
            total_turnover += turnover / max(nav_open, 1e-12)
            cash = nav_open - gross_buy - charges
            shares = target
        nav_close = cash + sum(q * close[s] for s, q in shares.items() if q and pd.notna(close[s]))
        navs.append(nav_close)
        exposure.append(sum(q * close[s] for s, q in shares.items() if q and pd.notna(close[s])) / nav_close
                        if nav_close else 0.)
    return pd.Series(navs, index=dates), exposure, total_turnover / 2


def vol_target_scales(pre_nav, target_vol=TARGET_VOL):
    """scale_t from pre-overlay returns through t-1 only."""
    ret = pre_nav.pct_change()
    rvol = ret.rolling(LOOKBACK, min_periods=LOOKBACK).std(ddof=1) * np.sqrt(252)
    rvol_prev = rvol.shift(1)
    raw = target_vol / rvol_prev
    ok = np.isfinite(raw) & (rvol_prev > 0)
    scales = pd.Series(MAX_SCALE, index=pre_nav.index)
    scales[ok] = np.minimum(MAX_SCALE, raw[ok])
    return scales, rvol


def causality_check(pre_nav, scales, target_vol=TARGET_VOL):
    """Mutating returns from date t onward must not change scale on or before t."""
    cut = len(pre_nav) // 2
    mutated = pre_nav.copy()
    mutated.iloc[cut:] = mutated.iloc[cut:] * np.linspace(1., 3., len(mutated) - cut)
    s2, _ = vol_target_scales(mutated, target_vol)
    return bool(np.allclose(s2.iloc[:cut + 1], scales.iloc[:cut + 1]))


def summarize(nav, exposure, turnover, label, scales=None):
    m = metrics(nav, exposure, turnover, label)
    years = (nav.index[-1] - nav.index[0]).days / 365.2425
    m['turnover_per_year_x'] = float(turnover / years)
    if scales is not None:
        traded = scales.iloc[1:]
        m['mean_scale'] = float(traded.mean())
        m['median_scale'] = float(traded.median())
        m['min_scale'] = float(traded.min())
        m['pct_days_scale_below_1'] = float((traded < 1 - 1e-12).mean() * 100)
    m['passes_bar'] = bool(m['cagr_pct'] >= 20 and m['mdd_pct'] <= 30 and m['sharpe'] >= 1.0)
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--target-vol', type=float, default=TARGET_VOL,
                    help='annualized target vol (Round 6: 0.15; Round 7 preregistered single refinement: 0.22)')
    target_vol = ap.parse_args().target_vol
    us = read_market('US')
    assert len(us) == 92 and 'SPY' in us
    out = []
    for scenario, fee, slip in SCENARIOS:
        ref = us_run(us, False, fee, slip)
        pre_nav, pre_exp, pre_to = us_ledger(us, fee, slip)
        base = summarize(pre_nav, pre_exp, pre_to, 'US_mom126_daily_top10_base')
        for key in ('cagr_pct', 'mdd_pct', 'sharpe', 'one_way_turnover_x'):
            assert abs(base[key] - ref[key]) < 1e-9, (scenario, key, base[key], ref[key])
        scales, rvol = vol_target_scales(pre_nav, target_vol)
        assert causality_check(pre_nav, scales, target_vol)
        vt_nav, vt_exp, vt_to = us_ledger(us, fee, slip, scales)
        vt = summarize(vt_nav, vt_exp, vt_to, f'US_mom126_daily_top10_voltarget{round(target_vol * 100):d}_lb{LOOKBACK}', scales)
        rv = rvol.dropna()
        vt['pre_overlay_realized_vol_pct'] = {'mean': float(rv.mean() * 100), 'median': float(rv.median() * 100),
                                              'p90': float(rv.quantile(.9) * 100)}
        annual_scale = scales.iloc[1:].groupby(scales.index[1:].year).mean()
        vt['mean_scale_by_year'] = {str(int(y)): round(float(v), 4) for y, v in annual_scale.items()}
        vt['target_vol'] = target_vol
        for r in (base, vt):
            r['scenario'] = scenario
            out.append(r)
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
