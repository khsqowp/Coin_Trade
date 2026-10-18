"""Transfer Round5 champion and fixed-initial-capital ensembles to equities."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

from app.crypto_bucket_ensemble_research import NAMES, jumps, volume_prep
from app.crypto_round3_research import prep as source_prep
from app.rs_equity_round12_13_portfolio import _costs
from app.rs_equity_round3_transfer import stock_frames
from app.rs_equity_transfer import EquityPanel, load_equity_panel
from app.round13_costs import simulate_cost_portfolio
from app.technical_portfolio_engine import prepare

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs/round5-results-2026-10-07.json"
OUT = ROOT / "docs/research/equity_transfer_2026-10/full_runs/round5_policy_transfer.json"
PERIODS = [("2019-09-08", "2022-12-31"), ("2023-01-01", "2026-10-05")]
PERIODS += [(f"{year}-09-08", f"{year+2}-09-07") for year in range(2019, 2024)]
PERIODS += [("2024-10-06", "2026-10-05")]
START, END = pd.Timestamp("2019-09-08"), pd.Timestamp("2026-10-05")


def _frames(panel: EquityPanel):
    frames = stock_frames(panel)
    return {symbol: frame.loc[(frame.index >= START) & (frame.index <= END)]
            for symbol, frame in frames.items()}


def _prepare(frames, name, volume_multiple=3., price_cap=5.):
    if name == "volume_spike_cap5":
        return volume_prep(frames, volume_multiple, price_cap)
    return source_prep(name, frames)


def _bucket(panel, book, cost, *, with_ledger=True):
    arrays = prepare(book)
    cost_name, fee, slip, tax = cost
    keys = arrays[1]
    slip = np.asarray(slip, dtype=float)
    if slip.ndim:
        slip = slip[[panel.symbols.index(symbol) for symbol in keys]]
    result = simulate_cost_portfolio(book, prepared=arrays, top_k=8, hold_days=20,
                                     fee_pct_one_way=fee, slippage=slip, sell_tax=tax,
                                     return_trace=True)
    trace = result.pop("trace")
    records = result.pop("records")
    dates = pd.DatetimeIndex(pd.to_datetime([x["date"] for x in trace]))
    curve = np.asarray([x["closing"] for x in trace], dtype=float)
    contributions = np.zeros((len(records), len(curve)), dtype=float)
    for i, trade in enumerate(records):
        # Attribute realized PnL from exit onward. This deliberately avoids
        # inventing per-trade mark-to-market paths from a portfolio-level trace.
        exit_ = int(trade["exit"])
        contributions[i, exit_:] = trade["pnl"]
    summary = {k: (int(v) if k in ("trades", "stopped", "tp_hit", "breaker_events", "breaker_resumes", "blocked_days")
                   else bool(v) if isinstance(v, (bool, np.bool_))
                   else float(v) if isinstance(v, (int, float, np.number)) else v)
               for k, v in result.items() if k not in ("breaker_log", "paused_age_final")}
    return {"metrics": summary, "dates": dates, "curve": curve, "records": records,
            "contributions": contributions,
            "daily_returns": pd.Series(curve, index=dates).pct_change().fillna(0.).to_numpy(float)}


def _combine(runs, weights):
    weights = np.asarray(weights, dtype=float)
    if len(runs) != len(weights) or (weights <= 0).any() or not np.isclose(weights.sum(), 1):
        raise ValueError("fixed initial-capital weights must be positive and sum to one")
    dates = runs[0]["dates"]
    for run in runs:
        if not run["dates"].equals(dates):
            raise ValueError("bucket calendars must be identical; no interpolation is allowed")
        if abs(run["curve"][0] - 1.) > 1e-12:
            raise AssertionError("every bucket starts with normalized NAV=1")
    curve = sum(w * run["curve"] for w, run in zip(weights, runs))
    contributions, trades = [], []
    for bucket_index, (w, run) in enumerate(zip(weights, runs)):
        contributions.extend(run["contributions"] * w)
        for trade in run["records"]:
            item = dict(trade, id=len(trades), bucket=bucket_index, bucket_trade_id=trade["id"])
            for key in ("qty", "cost", "proceeds", "pnl"):
                item[key] *= w
            trades.append(item)
    contributions = np.asarray(contributions, dtype=float)
    return {"dates": dates, "curve": curve, "contributions": contributions,
            "records": trades, "metrics": _metrics(curve, dates, len(trades)),
            "weights": weights.tolist()}


def _metrics(curve, dates, trades):
    equity = pd.Series(curve, index=dates)
    years = (dates[-1] - dates[0]).days / 365.25
    daily = equity.pct_change().dropna()
    cagr = float((equity.iloc[-1] ** (1/years)-1)*100) if equity.iloc[-1] > 0 else -100.
    return {"cagr": cagr,
            "mdd": float(((equity.cummax()-equity)/equity.cummax()).max()*100),
            "sharpe": float(daily.mean()/daily.std()*np.sqrt(365)) if daily.std() else 0.,
            "trades": int(trades), "final": float(equity.iloc[-1]), "years": years}


def _concentration(records, final):
    ranked = sorted(records, key=lambda x: (-x["pnl"], x["id"]))
    positive = sum(max(0., x["pnl"]) for x in records)
    net = final - 1.
    return {str(n): {"pnl": sum(x["pnl"] for x in ranked[:n]),
                     "net_pct": sum(x["pnl"] for x in ranked[:n])/net*100 if abs(net)>1e-12 else None,
                     "positive_pct": sum(x["pnl"] for x in ranked[:n])/positive*100 if positive else 0.}
            for n in (10,20)}


def _leave_out(run):
    curve, contrib, records, dates = run["curve"], run["contributions"], run["records"], run["dates"]
    ranked = sorted(records, key=lambda x: (-x["pnl"], x["id"]))
    out = []
    for n in (5,10,20,50):
        removed = [x["id"] for x in ranked[:n]]
        reduced = curve-contrib[removed].sum(axis=0)
        previous = np.r_[1.,curve[:-1]]
        normalized = np.cumprod(1+np.diff(reduced,prepend=1.)/previous)
        out.append({"n":n,"removed_ids":removed,"metrics":_metrics(reduced,dates,len(records)-n),
                    "equity":reduced.tolist(),"normalized_metrics":_metrics(normalized,dates,len(records)-n),
                    "normalized_equity":normalized.tolist()})
    return out


def _symbol_audit(panel, frames, books, cost, weights, run):
    grouped = defaultdict(lambda: {"trades":0,"pnl":0.})
    for item in run["records"]:
        grouped[item["symbol"]]["trades"] += 1
        grouped[item["symbol"]]["pnl"] += item["pnl"]
    symbols = [{"symbol":s,**grouped[s]} for s in sorted(frames)]
    symbols.sort(key=lambda x:(-x["pnl"],x["symbol"]))
    top = symbols[:5]
    net = run["curve"][-1]-1.
    net_share = sum(x["pnl"] for x in top)/net*100 if abs(net)>1e-12 else None
    by_count=sorted(symbols,key=lambda x:(-x["trades"],x["symbol"]))[:5]
    audit={"rows":symbols,"top5":[x["symbol"] for x in top],"net_pct":net_share,
           "trades_pct":sum(x["trades"] for x in top)/max(len(run["records"]),1)*100,
           "top5_by_count":[x["symbol"] for x in by_count],
           "top5_count_pct":sum(x["trades"] for x in by_count)/max(len(run["records"]),1)*100}
    if net_share is not None and net_share>=50:
        excluded=set(audit["top5"])
        restricted={name:{s:f for s,f in book.items() if s not in excluded} for name,book in books.items()}
        audit["excluded_metrics"]=_combine([_bucket(panel,restricted[name],cost) for name in books],weights)["metrics"]
    return audit


def _audit(panel, frames, books, cost, weights, run, period_books):
    full={"metrics":run["metrics"],"daily_dates":[str(x.date()) for x in run["dates"]],
          "daily_equity":run["curve"].tolist(),"trades":run["records"],
          "terminal_unrealized":float(run["curve"][-1]-1-sum(x["pnl"] for x in run["records"])),
          "weights":weights,"concentration":_concentration(run["records"],run["curve"][-1]),
          "leave_top_out":_leave_out(run),"periods":[]}
    for period, sliced_books in zip(PERIODS,period_books):
        bucket_runs=[_bucket(panel,sliced_books[name],cost,with_ledger=False) for name in books]
        combined=_combine(bucket_runs,weights)
        start,end=period
        if combined["dates"][0] < pd.Timestamp(start) or combined["dates"][-1] > pd.Timestamp(end):
            raise AssertionError("independent period dates outside requested window")
        full["periods"].append({"requested_start":start,"requested_end":end,
                                "actual_start":str(combined["dates"][0].date()),
                                "actual_end":str(combined["dates"][-1].date()),
                                "metrics":combined["metrics"],"initial_equity":float(combined["curve"][0]),
                                "daily_dates":[str(x.date()) for x in combined["dates"]],
                                "daily_equity":combined["curve"].tolist()})
    full["symbols"]=_symbol_audit(panel,frames,{name:books[name] for name in books},cost,weights,run)
    return full


def _verdict(row, sensitivity_jumps):
    flags={"periods":bool(any(p["metrics"]["sharpe"]<.5 or p["metrics"]["cagr"]<0 for p in row["periods"])),
           "concentration":bool(row["concentration"]["10"]["net_pct"] is not None and row["concentration"]["10"]["net_pct"]>=50),
           "sensitivity":bool(any(x["unstable"] for x in sensitivity_jumps)),
           "symbols":bool(row["symbols"]["net_pct"] is not None and row["symbols"]["net_pct"]>=50)}
    count=sum(flags.values())
    row.update(flags=flags,unstable_count=count,verdict="기각" if count>=2 else "통과" if count==0 else "조건부 보류")


def _trend(panel):
    close=pd.Series(panel.proxy_close,index=panel.dates)
    return (close>close.rolling(50,min_periods=50).mean()).fillna(False)


def run_market(market):
    panel=load_equity_panel(market)
    frames=_frames(panel)
    source=json.loads(SOURCE.read_text(encoding="utf-8"))
    volume_params=[(3.,5.),(2.5,5.),(2.75,5.),(3.25,5.),(3.5,5.),
                   (3.,4.),(3.,4.5),(3.,5.5),(3.,6.)]
    volume_books={pair:_prepare(frames,NAMES[0],*pair) for pair in volume_params}
    books={"volume_spike_cap5":volume_books[(3.,5.)],
           "heikin_ashi":_prepare(frames,"heikin_ashi"),"frvp":_prepare(frames,"frvp")}
    cost_cases=_costs(panel)
    periods=[]
    for start,end in PERIODS:
        periods.append({name:{s:f.loc[start:end] for s,f in book.items() if len(f.loc[start:end])}
                        for name,book in books.items()})
    output={"market":market,"symbols":panel.symbols,
            "actual_full_start":str(min(frame.index.min() for frame in frames.values()).date()),
            "actual_full_end":str(max(frame.index.max() for frame in frames.values()).date()),
            "source_window":[str(START.date()),str(END.date())],"period_definitions":PERIODS,
            "cost_cases":[],"champion_sensitivity":[],"ensembles":[],"bucket_runs":[],
            "btc_confirmation":[]}
    for cost in cost_cases:
        bucket_runs={name:_bucket(panel,book,cost) for name,book in books.items()}
        for name,run in bucket_runs.items():
            output["bucket_runs"].append({"cost_case":cost[0],"name":name,
                "metrics":run["metrics"],"daily_dates":[str(x.date()) for x in run["dates"]],
                "daily_equity":run["curve"].tolist(),"trades":run["records"]})
        configs=[("champion",[NAMES[0]],[1.]),("N2",NAMES[:2],[.5,.5]),("N3",NAMES,[1/3]*3)]
        portfolio_runs={}
        for label,names,weights in configs:
            run=_combine([bucket_runs[name] for name in names],weights)
            row=_audit(panel,frames,{name:books[name] for name in names},cost,weights,run,periods)
            portfolio_runs[label]=run
            output["cost_cases"].append({"cost_case":cost[0],"portfolio":label,
                                         "names":names,"weights":weights,"audit":row})
        # Champion's predeclared one-dimensional signal sweeps; 9 unique points including baseline.
        champion_sensitivity={"volume_multiple":[],"price_cap":[]}
        for pair in volume_params:
            run=_bucket(panel,volume_books[pair],cost)
            metric=run["metrics"]
            if pair[1]==5.:
                champion_sensitivity["volume_multiple"].append({"value":pair[0],"metrics":metric})
            if pair[0]==3.:
                champion_sensitivity["price_cap"].append({"value":pair[1],"metrics":metric})
        for series_name,points in champion_sensitivity.items():
            points.sort(key=lambda x:x["value"])
            output["champion_sensitivity"].append({"cost_case":cost[0],"parameter":series_name,
                "points":points,"jumps":jumps(points)})
        # Ensemble weight sensitivities are pointwise combinations of saved bucket curves.
        for n,label,grid in [(2,"N2",[.3,.4,.5,.6,.7]),(3,"N3",[.2,.3,1/3,.4,.5])]:
            names=NAMES[:n]
            points=[]
            for w in grid:
                weights=[w,1-w] if n==2 else [w,(1-w)/2,(1-w)/2]
                points.append({"value":w,"weights":weights,
                               "metrics":_combine([bucket_runs[name] for name in names],weights)["metrics"]})
            output["ensembles"].append({"cost_case":cost[0],"portfolio":label,
                                        "weight_sensitivity":{"points":points,"jumps":jumps(points)}})
        # Three-day completed-proxy confirmation on the source HA 25% breaker.
        trend=_trend(panel)
        confirmed=trend.rolling(3,min_periods=3).sum().eq(3).to_dict()
        ha=books["heikin_ashi"]
        arrays=prepare(ha)
        fee,slip,tax=cost[1:]
        if np.asarray(slip).ndim:
            slip=np.asarray(slip)[[panel.symbols.index(s) for s in arrays[1]]]
        confirmation=simulate_cost_portfolio(ha,prepared=arrays,top_k=8,hold_days=20,
            dd_trigger=.25,resume_mode="btc_sma50",btc_resume=confirmed,
            fee_pct_one_way=fee,slippage=slip,sell_tax=tax,return_trace=True)
        trace=confirmation.pop("trace")
        confirmation.pop("records",None)
        confirmation.pop("allocations",None)
        confirmation.pop("breaker_log",None)
        output["btc_confirmation"].append({"cost_case":cost[0],
            "metrics":{k:(int(v) if k in ("trades","stopped","breaker_events","breaker_resumes","blocked_days") else
                          bool(v) if isinstance(v,(bool,np.bool_)) else
                          float(v) if isinstance(v,(int,float,np.number)) else v)
                       for k,v in confirmation.items() if k!="paused_age_final"},
            "daily_dates":[str(pd.Timestamp(t["date"]).date()) for t in trace],
            "daily_equity":[float(t["closing"]) for t in trace]})
    for item in output["cost_cases"]:
        if item["portfolio"]=="champion":
            jumps_for_verdict=[jump for series in output["champion_sensitivity"]
                               if series["cost_case"]==item["cost_case"] for jump in series["jumps"]]
        else:
            ensemble=next(x for x in output["ensembles"] if x["cost_case"]==item["cost_case"]
                          and x["portfolio"]==item["portfolio"])
            jumps_for_verdict=ensemble["weight_sensitivity"]["jumps"]
        _verdict(item["audit"],jumps_for_verdict)
    return output


def run():
    source=json.loads(SOURCE.read_text(encoding="utf-8"))
    payload={"source_file":SOURCE.name,"source_config":source["config"],
             "source_periods":source["periods"],
             "markets":{market:run_market(market) for market in ("US","KR")}}
    payload["full_bucket_curves"]=sum(len(x["bucket_runs"]) for x in payload["markets"].values())
    payload["portfolio_audits"]=sum(len(x["cost_cases"]) for x in payload["markets"].values())
    payload["independent_period_replays"]=sum(len(x["cost_cases"])*8 for x in payload["markets"].values())
    payload["champion_sensitivity_replays"]=sum(
        len({case["cost_case"] for case in market["cost_cases"]})*9
        for market in payload["markets"].values())
    OUT.write_text(json.dumps(payload,ensure_ascii=False),encoding="utf-8")
    print(json.dumps({"bucket_curves":payload["full_bucket_curves"],
                      "portfolio_audits":payload["portfolio_audits"],
                      "independent_period_replays":payload["independent_period_replays"],
                      "champion_sensitivity_replays":payload["champion_sensitivity_replays"]}))
    return payload


if __name__=="__main__":
    run()
