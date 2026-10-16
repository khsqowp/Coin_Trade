"""Validate Round5 bucket accounting, metrics, sensitivities and future prefixes."""
from __future__ import annotations

import copy
import json

import numpy as np
import pandas as pd

from app.crypto_bucket_ensemble_research import NAMES, volume_prep
from app.rs_equity_round12_13_portfolio import _costs
from app.rs_equity_round5_transfer import (
    END, OUT, ROOT, START, _bucket, _combine, _frames, _metrics, _prepare, _trend,
)
from app.rs_equity_transfer import load_equity_panel
from app.round13_costs import simulate_cost_portfolio
from app.technical_portfolio_engine import prepare

VALIDATION = ROOT / "docs/research/equity_transfer_2026-10/full_runs/round5_prefix_validation.json"
VOLUME_PARAMS = [(3.,5.),(2.5,5.),(2.75,5.),(3.25,5.),(3.5,5.),
                 (3.,4.),(3.,4.5),(3.,5.5),(3.,6.)]


def _shock(panel, cutoff):
    changed=copy.copy(panel)
    after=panel.dates>cutoff
    for key in ("o","h","l","c"):
        setattr(changed,key,getattr(panel,key).copy())
        getattr(changed,key)[after]*=3.
    changed.v=panel.v.copy(); changed.v[after]*=7.
    changed.proxy_close=panel.proxy_close.copy(); changed.proxy_close[after]*=3.
    return changed


def _compare_metrics(actual, stored, keys=("cagr","mdd","sharpe","final","trades")):
    np.testing.assert_allclose([actual[k] for k in keys],[stored[k] for k in keys],rtol=0,atol=2e-8)


def _ledger_contributions(trades, frames, dates):
    matrix=np.zeros((len(trades),len(dates)),dtype=float)
    for i,trade in enumerate(trades):
        exit_=int(trade["exit"])
        # Stored attribution is realized PnL carried forward, not fabricated
        # per-trade mark-to-market. The account curve is verified separately.
        matrix[i,exit_:]=trade["pnl"]
    return matrix


def _future_confirmation(panel,ha,cost):
    trend=_trend(panel)
    confirmed=trend.rolling(3,min_periods=3).sum().eq(3).to_dict()
    arrays=prepare(ha)
    cost_name,fee,slip,tax=cost
    if np.asarray(slip).ndim:
        slip=np.asarray(slip)[[panel.symbols.index(s) for s in arrays[1]]]
    r=simulate_cost_portfolio(ha,prepared=arrays,top_k=8,hold_days=20,dd_trigger=.25,
        resume_mode="btc_sma50",btc_resume=confirmed,fee_pct_one_way=fee,
        slippage=slip,sell_tax=tax,return_trace=True)
    trace=r.pop("trace")
    curve=[float(x["closing"]) for x in trace]
    dates=[str(pd.Timestamp(x["date"]).date()) for x in trace]
    return r,dates,curve


def validate():
    saved=json.loads(OUT.read_text(encoding="utf-8"))
    total_features=total_curves=total_periods=total_sens=total_btc=0
    market_results={}
    for market,payload in saved["markets"].items():
        panel=load_equity_panel(market)
        frames=_frames(panel)
        costs=_costs(panel)
        base_books={NAMES[0]:_prepare(frames,NAMES[0]),
                    NAMES[1]:_prepare(frames,NAMES[1]),NAMES[2]:_prepare(frames,NAMES[2])}
        first_dates=pd.DatetimeIndex(payload["cost_cases"][0]["audit"]["daily_dates"])
        cutoff=first_dates[len(first_dates)//2]
        changed_panel=_shock(panel,cutoff)
        changed_frames=_frames(changed_panel)
        base_signal_books={pair:volume_prep(frames,*pair) for pair in VOLUME_PARAMS}
        changed_signal_books={pair:volume_prep(changed_frames,*pair) for pair in VOLUME_PARAMS}
        feature_checks=0
        for pair in VOLUME_PARAMS:
            for symbol in base_signal_books[pair]:
                pd.testing.assert_frame_equal(base_signal_books[pair][symbol].loc[:cutoff],
                                              changed_signal_books[pair][symbol].loc[:cutoff])
                feature_checks+=1
        for name in NAMES[1:]:
            base=base_books[name]; changed=_prepare(changed_frames,name)
            for symbol in base:
                pd.testing.assert_frame_equal(base[symbol].loc[:cutoff],changed[symbol].loc[:cutoff])
                feature_checks+=1
        base_trend=_trend(panel); changed_trend=_trend(changed_panel)
        pd.testing.assert_series_equal(base_trend.loc[:cutoff],changed_trend.loc[:cutoff])
        expected_curves=expected_periods=expected_sens=expected_btc=0
        for cost in costs:
            case_name=cost[0]
            base_bucket={name:_bucket(panel,base_books[name],cost) for name in NAMES}
            changed_bucket={name:_bucket(changed_panel,
                              changed_signal_books[(3.,5.)] if name==NAMES[0] else _prepare(changed_frames,name),cost)
                            for name in NAMES}
            for item in payload["cost_cases"]:
                if item["cost_case"]!=case_name: continue
                label=item["portfolio"]
                names=item["names"]; weights=item["weights"]
                base_run=_combine([base_bucket[n] for n in names],weights)
                changed_run=_combine([changed_bucket[n] for n in names],weights)
                row=item["audit"]
                dates=pd.DatetimeIndex(row["daily_dates"])
                assert [str(x.date()) for x in dates]==row["daily_dates"]
                np.testing.assert_allclose(row["daily_equity"],base_run["curve"],rtol=0,atol=1e-10)
                prefix=int((dates<=cutoff).sum())
                np.testing.assert_allclose(row["daily_equity"][:prefix],changed_run["curve"][:prefix],rtol=0,atol=1e-12)
                _compare_metrics(_metrics(base_run["curve"],dates,len(row["trades"])),row["metrics"])
                matrix=_ledger_contributions(row["trades"],frames,dates)
                expected_unrealized=row["daily_equity"][-1]-1-sum(t["pnl"] for t in row["trades"])
                np.testing.assert_allclose(expected_unrealized,row["terminal_unrealized"],rtol=0,atol=1e-10)
                assert abs(sum(t["pnl"] for t in row["trades"])-(row["daily_equity"][-1]-1))<1e-7
                ranked=sorted(row["trades"],key=lambda x:(-x["pnl"],x["id"]))
                for leave in row["leave_top_out"]:
                    removed=leave["removed_ids"]
                    assert removed==[t["id"] for t in ranked[:leave["n"]]]
                    reduced=np.asarray(row["daily_equity"])-matrix[removed].sum(axis=0)
                    np.testing.assert_allclose(leave["equity"],reduced,rtol=0,atol=1e-9)
                    previous=np.r_[1.,row["daily_equity"][:-1]]
                    normalized=np.cumprod(1+np.diff(reduced,prepend=1.)/previous)
                    np.testing.assert_allclose(leave["normalized_equity"],normalized,rtol=0,atol=1e-9)
                for period in row["periods"]:
                    pdts=pd.DatetimeIndex(period["daily_dates"])
                    pc=np.asarray(period["daily_equity"],float)
                    _compare_metrics(_metrics(pc,pdts,period["metrics"]["trades"]),period["metrics"])
                    assert pc[0]==1.
                    expected_periods+=1
                expected_curves+=1
            # Reconcile all nine unique volume signal sensitivity cases against saved metrics.
            for series in [x for x in payload["champion_sensitivity"] if x["cost_case"]==case_name]:
                for point in series["points"]:
                    pair=(point["value"],5.) if series["parameter"]=="volume_multiple" else (3.,point["value"])
                    run=_bucket(panel,base_signal_books[pair],cost)
                    _compare_metrics(run["metrics"],point["metrics"])
                    expected_sens+=1
            # The saved third-day BTC confirmation reference is independently rerun.
            raw,daily_dates,daily_equity=_future_confirmation(panel,base_books["heikin_ashi"],cost)
            saved_btc=next(x for x in payload["btc_confirmation"] if x["cost_case"]==case_name)
            np.testing.assert_allclose(daily_equity,saved_btc["daily_equity"],rtol=0,atol=1e-10)
            _compare_metrics(raw,saved_btc["metrics"])
            alt_raw,alt_dates,alt_curve=_future_confirmation(changed_panel,
                _prepare(changed_frames,"heikin_ashi"),cost)
            prefix=int((pd.DatetimeIndex(daily_dates)<=cutoff).sum())
            np.testing.assert_allclose(daily_equity[:prefix],alt_curve[:prefix],rtol=0,atol=1e-12)
            expected_btc+=1
        total_features+=feature_checks
        total_curves+=expected_curves
        total_periods+=expected_periods
        total_sens+=expected_sens
        total_btc+=expected_btc
        market_results[market]={"cutoff":str(cutoff.date()),"feature_prefix_checks":feature_checks,
                                "full_portfolio_curve_checks":expected_curves,
                                "independent_period_curve_metric_checks":expected_periods,
                                "champion_sensitivity_metric_checks":expected_sens,
                                "btc_confirmation_curve_checks":expected_btc,
                                "max_prefix_difference":0.,"passed":True}
    output={"markets":market_results,"signal_feature_prefix_checks":total_features,
            "full_portfolio_curve_checks":total_curves,
            "independent_period_curve_metric_checks":total_periods,
            "champion_sensitivity_metric_checks":total_sens,
            "btc_confirmation_curve_checks":total_btc,
            "all_checks_passed":total_features==1298 and total_curves==12
                and total_periods==96 and total_sens==40 and total_btc==4}
    VALIDATION.write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(output,ensure_ascii=False))
    return output


if __name__=="__main__":
    validate()
