"""Independent saved-result and future-prefix validation for Round6 transfer."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from app.crypto_bucket_ensemble_research import NAMES
from app.rs_equity_round12_13_portfolio import _costs
from app.rs_equity_round5_transfer import _frames
from app.rs_equity_round6_transfer import (
    CAPS, OUT, PERIODS, _audit_cap_decisions, _book, _metrics, _period_run,
    _proxy_period, _shock, _simulate,
)
from app.rs_equity_transfer import load_equity_panel

ROOT=OUT.parents[1]
VALIDATION=OUT.parent/"round6_prefix_validation.json"


def _metrics_equal(actual,stored):
    for key in ("cagr","mdd","sharpe","final","trades"):
        np.testing.assert_allclose(actual[key],stored[key],rtol=0,atol=1e-9)


def validate():
    saved=json.loads(OUT.read_text(encoding="utf-8"))
    totals={"full_curve_replays":0,"independent_period_replays":0,"prefix_curve_checks":0,
            "feature_prefix_checks":0}
    results={}
    for market,market_saved in saved["markets"].items():
        panel=load_equity_panel(market); frames=_frames(panel); books=_book(frames); book=books[NAMES[0]]
        market_result={"cost_cases":{},"passed":True}
        for cost in _costs(panel):
            row=next(x for x in market_saved["cost_cases"] if x["cost_case"]==cost[0])
            baseline=_simulate(panel,book,cost)
            _metrics_equal(baseline["metrics"],row["baseline"]["metrics"])
            dates=[str(x.date()) for x in baseline["dates"]]
            assert dates==row["baseline"]["daily_dates"]
            np.testing.assert_allclose(baseline["curve"],row["baseline"]["daily_equity"],rtol=0,atol=1e-10)
            totals["full_curve_replays"]+=1
            base_periods=[]
            for start,end in PERIODS:
                run=_period_run(panel,book,cost,None,start,end)
                metric=_metrics(run["curve"],run["dates"],len(run["trades"]))
                proxy=_proxy_period(panel,start,end)
                base_periods.append((metric,proxy))
                totals["independent_period_replays"]+=1
            for strategy in row["btc_relative_strategy_reclassification"]:
                strategy_book=books[strategy["signal_family"]]
                strategy_run=_simulate(panel,strategy_book,cost,settings=strategy["settings"])
                _metrics_equal(strategy_run["metrics"],strategy["metrics"])
                totals["full_curve_replays"]+=1
                for index,(start,end) in enumerate(PERIODS):
                    period_run=_period_run(panel,strategy_book,cost,None,start,end,strategy["settings"])
                    metric=_metrics(period_run["curve"],period_run["dates"],len(period_run["trades"]))
                    saved_period=strategy["periods"][index]
                    _metrics_equal(metric,saved_period["metrics"])
                    assert bool(metric["cagr"]>saved_period["proxy"]["cagr"])==saved_period["proxy_excess_pass"]
                    totals["independent_period_replays"]+=1
            for cap in CAPS:
                stored_cap=next(x for x in row["caps"] if x["cap"]==cap)
                current=_simulate(panel,book,cost,cap)
                _metrics_equal(current["metrics"],stored_cap["metrics"])
                assert [str(x.date()) for x in current["dates"]]==stored_cap["daily_dates"]
                np.testing.assert_allclose(current["curve"],stored_cap["daily_equity"],rtol=0,atol=1e-10)
                blocked=_audit_cap_decisions(current,cap)
                assert blocked==stored_cap["blocked_decisions"]
                totals["full_curve_replays"]+=1
                for index,(start,end) in enumerate(PERIODS):
                    run=_period_run(panel,book,cost,cap,start,end)
                    metric=_metrics(run["curve"],run["dates"],len(run["trades"]))
                    stored_period=stored_cap["periods"][index]
                    _metrics_equal(metric,stored_period["metrics"])
                    assert abs(metric["cagr"]-base_periods[index][1]["cagr"]-stored_period["proxy_excess_cagr_pp"])<1e-8
                    totals["independent_period_replays"]+=1
                cutoff=pd.Timestamp(stored_cap["future_prefix"]["cutoff"])
                shocked=_shock(panel,cutoff); shocked_frames=_frames(shocked); shocked_book=_book(shocked_frames)[NAMES[0]]
                alternative=_simulate(shocked,shocked_book,cost,cap)
                prefix=int((current["dates"]<=cutoff).sum())
                np.testing.assert_allclose(current["curve"][:prefix],alternative["curve"][:prefix],rtol=0,atol=1e-12)
                for symbol in book:
                    pd.testing.assert_frame_equal(book[symbol].loc[:cutoff],shocked_book[symbol].loc[:cutoff])
                    totals["feature_prefix_checks"]+=1
                totals["prefix_curve_checks"]+=1
            market_result["cost_cases"][cost[0]]={"passed":True,"caps":len(CAPS)}
        results[market]=market_result
    totals["all_checks_passed"]=(totals["full_curve_replays"]==40 and
        totals["independent_period_replays"]==320 and totals["prefix_curve_checks"]==12 and
        totals["feature_prefix_checks"]==708)
    output={"markets":results,**totals}
    VALIDATION.write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(output,ensure_ascii=False))
    return output


if __name__=="__main__":
    validate()
