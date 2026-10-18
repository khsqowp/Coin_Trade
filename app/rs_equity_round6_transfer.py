"""Transfer Round6 BTC-relative checks and causal symbol trade-share caps."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import pandas as pd

from app.crypto_bucket_ensemble_research import NAMES, volume_prep
from app.crypto_round3_research import prep as source_prep
from app.rs_equity_round12_13_portfolio import _costs
from app.rs_equity_round5_transfer import END, PERIODS, START, _frames, _metrics
from app.rs_equity_transfer import load_equity_panel
from app.round13_costs import simulate_cost_portfolio
from app.technical_portfolio_engine import prepare

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/research/equity_transfer_2026-10/full_runs/round6_policy_transfer.json"
CAPS = (.10, .15, .20)


def _shock(panel, cutoff):
    changed = copy.copy(panel)
    future = panel.dates > cutoff
    for field in ("o", "h", "l", "c"):
        setattr(changed, field, getattr(panel, field).copy())
        getattr(changed, field)[future] *= 3.
    changed.v = panel.v.copy()
    changed.v[future] *= 7.
    changed.proxy_close = panel.proxy_close.copy()
    changed.proxy_close[future] *= 3.
    return changed


def _book(frames):
    return {NAMES[0]: volume_prep(frames),
            NAMES[1]: source_prep(NAMES[1], frames),
            NAMES[2]: source_prep(NAMES[2], frames)}


def _simulate(panel, book, cost, cap=None, settings=None):
    arrays = prepare(book)
    _, fee, slippage, tax = cost
    if np.asarray(slippage).ndim:
        slippage = np.asarray(slippage)[[panel.symbols.index(s) for s in arrays[1]]]
    kwargs=dict(settings or {})
    if kwargs.get("resume_mode")=="btc_sma50":
        proxy=pd.Series(panel.proxy_close,index=panel.dates)
        kwargs["btc_resume"]=(proxy>proxy.rolling(50,min_periods=50).mean()).fillna(False).to_dict()
    result = simulate_cost_portfolio(book, prepared=arrays, top_k=8, hold_days=20,
        fee_pct_one_way=fee, slippage=slippage, sell_tax=tax,
        symbol_trade_share_cap=cap, return_trace=True, **kwargs)
    trace = result.pop("trace")
    records = result.pop("records")
    allocations = result.pop("allocations")
    share_log = result.pop("symbol_share_log", [])
    dates = pd.DatetimeIndex(pd.to_datetime([x["date"] for x in trace]))
    curve = np.asarray([x["closing"] for x in trace], float)
    metrics = {k:(int(v) if k=="trades" else float(v) if isinstance(v,(int,float,np.number)) else v)
               for k,v in result.items() if k not in ("breaker_log","paused_age_final")}
    return {"dates":dates,"curve":curve,"metrics":metrics,"trades":records,
            "allocations":allocations,"share_log":share_log}


def _proxy_period(panel, start, end):
    proxy = pd.Series(panel.proxy_close, index=panel.dates).loc[start:end].dropna()
    years = (proxy.index[-1]-proxy.index[0]).days/365.25
    final = float(proxy.iloc[-1]/proxy.iloc[0])
    return {"actual_start":str(proxy.index[0].date()),"actual_end":str(proxy.index[-1].date()),
            "final":final,"cagr":float((final**(1/years)-1)*100),"years":years}


def _concentration(trades, final):
    rows={}
    for trade in trades:
        row=rows.setdefault(trade["symbol"],{"trades":0,"pnl":0.})
        row["trades"]+=1; row["pnl"]+=trade["pnl"]
    ranked=sorted(rows.items(),key=lambda x:(-x[1]["pnl"],x[0]))
    net=final-1.
    return {"top5":[s for s,_ in ranked[:5]],
            "top5_net_pct":sum(x["pnl"] for _,x in ranked[:5])/net*100 if abs(net)>1e-12 else None,
            "top5_trade_pct":sum(x["trades"] for _,x in sorted(rows.items(),key=lambda x:(-x[1]["trades"],x[0]))[:5])/max(len(trades),1)*100,
            "symbols":[{"symbol":s,**row} for s,row in ranked]}


def _audit_cap_decisions(run, cap):
    trades=run["trades"]
    by_date={}
    for event in run["share_log"]:
        prior=[t for t in trades if t["exit_date"]<event["date"]]
        same=sum(t["symbol"]==event["symbol"] for t in prior)
        blocked=bool(prior and same>cap*len(prior))
        assert event["completed_total"]==len(prior)
        assert event["completed_symbol"]==same
        assert bool(event["blocked"])==blocked
        by_date[(event["date"],event["symbol"])]=event
    for allocation in run["allocations"]:
        assert not by_date[(allocation["date"],allocation["symbol"])]["blocked"]
    return sum(bool(x["blocked"]) for x in run["share_log"])


def _period_run(panel, book, cost, cap, start, end, settings=None):
    sliced={s:f.loc[start:end] for s,f in book.items() if len(f.loc[start:end])}
    return _simulate(panel,sliced,cost,cap,settings)


def _benchmark_strategies(panel, frames, cost):
    books=_book(frames)
    cases=[("volume_spike_cap5",NAMES[0],{}),
           *[(f"heikin_ashi_cb{n}_proxy_sma50","heikin_ashi",
              {"dd_trigger":n/100,"resume_mode":"btc_sma50","cooldown_days":20})
             for n in (15,20,25,30)],
           ("frvp_cb20_cooldown60","frvp",{"dd_trigger":.20,"resume_mode":"cooldown","cooldown_days":60})]
    rows=[]
    for label,name,settings in cases:
        selected=books[name]
        full=_simulate(panel,selected,cost,settings=settings)
        full_proxy=_proxy_period(panel,str(full["dates"][0].date()),str(full["dates"][-1].date()))
        periods=[]
        for start,end in PERIODS:
            run=_period_run(panel,selected,cost,None,start,end,settings)
            proxy=_proxy_period(panel,start,end)
            metric=_metrics(run["curve"],run["dates"],len(run["trades"]))
            periods.append({"requested_start":start,"requested_end":end,
                "actual_start":str(run["dates"][0].date()),"actual_end":str(run["dates"][-1].date()),
                "metrics":metric,"proxy":proxy,"proxy_excess_cagr_pp":metric["cagr"]-proxy["cagr"],
                "absolute_pass":bool(metric["cagr"]>=0 and metric["sharpe"]>=.5),
                "proxy_excess_pass":bool(metric["cagr"]>proxy["cagr"])})
        rows.append({"name":label,"signal_family":name,"settings":settings,
            "metrics":full["metrics"],"proxy_full_cagr":full_proxy["cagr"],
            "proxy_full_excess_cagr_pp":full["metrics"]["cagr"]-full_proxy["cagr"],
            "periods":periods,"absolute_failures":sum(not p["absolute_pass"] for p in periods),
            "proxy_excess_failures":sum(not p["proxy_excess_pass"] for p in periods)})
    return rows


def run_market(market):
    panel=load_equity_panel(market)
    frames=_frames(panel)
    book=_book(frames)[NAMES[0]]
    output={"market":market,"symbols":panel.symbols,"source_window":[str(START.date()),str(END.date())],
            "actual_start":str(min(x.index.min() for x in frames.values()).date()),
            "actual_end":str(max(x.index.max() for x in frames.values()).date()),
            "cost_cases":[]}
    for cost in _costs(panel):
        benchmark_cases=_benchmark_strategies(panel,frames,cost)
        baseline=_simulate(panel,book,cost)
        baseline_syms=_concentration(baseline["trades"],baseline["curve"][-1])
        base_periods=[]
        for start,end in PERIODS:
            r=_period_run(panel,book,cost,None,start,end)
            proxy=_proxy_period(panel,start,end)
            base_periods.append({"requested_start":start,"requested_end":end,
                "actual_start":str(r["dates"][0].date()),"actual_end":str(r["dates"][-1].date()),
                "metrics":_metrics(r["curve"],r["dates"],len(r["trades"])),"proxy":proxy,
                "proxy_excess_cagr_pp":_metrics(r["curve"],r["dates"],len(r["trades"]))["cagr"]-proxy["cagr"]})
        case={"cost_case":cost[0],"btc_relative_strategy_reclassification":benchmark_cases,
            "baseline":{"metrics":baseline["metrics"],
            "daily_dates":[str(x.date()) for x in baseline["dates"]],"daily_equity":baseline["curve"].tolist(),
            "trades":baseline["trades"],"concentration":baseline_syms,"periods":base_periods},"caps":[]}
        for cap in CAPS:
            run=_simulate(panel,book,cost,cap)
            blocked_count=_audit_cap_decisions(run,cap)
            syms=_concentration(run["trades"],run["curve"][-1])
            losses={"top5_reduction_pp":baseline_syms["top5_net_pct"]-syms["top5_net_pct"],
                    "cagr_loss_pp":baseline["metrics"]["cagr"]-run["metrics"]["cagr"],
                    "sharpe_loss_relative_pct":(1-run["metrics"]["sharpe"]/baseline["metrics"]["sharpe"])*100
                       if baseline["metrics"]["sharpe"] else None}
            threshold_pass=bool(losses["top5_reduction_pp"]>=10 and losses["cagr_loss_pp"]<20
                and losses["sharpe_loss_relative_pct"] is not None and losses["sharpe_loss_relative_pct"]<20)
            periods=[]
            for start,end in PERIODS:
                r=_period_run(panel,book,cost,cap,start,end)
                proxy=_proxy_period(panel,start,end)
                metrics=_metrics(r["curve"],r["dates"],len(r["trades"]))
                periods.append({"requested_start":start,"requested_end":end,
                    "actual_start":str(r["dates"][0].date()),"actual_end":str(r["dates"][-1].date()),
                    "metrics":metrics,"proxy":proxy,"proxy_excess_cagr_pp":metrics["cagr"]-proxy["cagr"]})
            cutoff=baseline["dates"][len(baseline["dates"])//2]
            changed=_shock(panel,cutoff); changed_frames=_frames(changed); changed_book=_book(changed_frames)[NAMES[0]]
            altered=_simulate(changed,changed_book,cost,cap)
            prefix=int((baseline["dates"]<=cutoff).sum())
            np.testing.assert_allclose(run["curve"][:prefix],altered["curve"][:prefix],rtol=0,atol=1e-12)
            feature_checks=0
            plain=book; shocked=changed_book
            for symbol in plain:
                pd.testing.assert_frame_equal(plain[symbol].loc[:cutoff],shocked[symbol].loc[:cutoff])
                feature_checks+=1
            case["caps"].append({"cap":cap,"metrics":run["metrics"],
                "daily_dates":[str(x.date()) for x in run["dates"]],"daily_equity":run["curve"].tolist(),
                "trades":run["trades"],"decisions":run["share_log"],"concentration":syms,
                "blocked_decisions":blocked_count,
                "losses_vs_baseline":losses,"mitigation_threshold_pass":threshold_pass,
                "periods":periods,"future_prefix":{"cutoff":str(cutoff.date()),
                    "max_curve_difference":float(np.max(np.abs(run["curve"][:prefix]-altered["curve"][:prefix]))),
                    "feature_prefix_checks":feature_checks,"passed":True}})
        output["cost_cases"].append(case)
    return output


def run():
    payload={"source":"app/crypto_round6_research.py","caps":CAPS,"periods":PERIODS,
             "markets":{m:run_market(m) for m in ("US","KR")}}
    payload["portfolio_runs"]=sum(len(x["cost_cases"])*4 for x in payload["markets"].values())
    payload["btc_relative_strategy_runs"]=sum(len(x["cost_cases"])*6 for x in payload["markets"].values())
    payload["independent_period_replays"]=sum(len(x["cost_cases"])*len(PERIODS)*10 for x in payload["markets"].values())
    payload["future_prefix_curve_checks"]=12
    payload["all_prefix_checks_passed"]=all(cap["future_prefix"]["passed"]
        for market in payload["markets"].values() for cost in market["cost_cases"] for cap in cost["caps"])
    OUT.write_text(json.dumps(payload,ensure_ascii=False),encoding="utf-8")
    print(json.dumps({k:payload[k] for k in ("portfolio_runs","independent_period_replays",
        "future_prefix_curve_checks","all_prefix_checks_passed")}))
    return payload


if __name__=="__main__":
    run()
