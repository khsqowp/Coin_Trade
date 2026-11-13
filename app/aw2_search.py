"""Append-only AW-2 research loop. Reads local cache only; no order paths."""
from __future__ import annotations

import argparse, hashlib, json, subprocess, time
import copy
from pathlib import Path

import numpy as np
import pandas as pd

from app import aw_engine
from app.aw2_strategies import candidates, weights
from app.aw2_walkforward import build as build_wf, write as write_wf
from app.aw_data import DATA_END, load_panel
from app.aw_run import _bench, _daily_metrics, metrics

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/"docs/research/aw2"
LEDGER=BASE/"ledger.jsonl"
LOG=BASE/"AW2_LOG.md"
FAMILIES=["F1","F2","F3","F4","F5","F6","F7","F8"]


def jsonsafe(x):
    if isinstance(x,dict): return {str(k):jsonsafe(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)): return [jsonsafe(v) for v in x]
    if isinstance(x,(np.integer,)): return int(x)
    if isinstance(x,(np.floating,float)):
        return float(x) if np.isfinite(x) else None
    if isinstance(x,(np.bool_,)): return bool(x)
    return x


def calc(curve, turnover, cost, start, end):
    sel=curve.loc[(curve.index>=start)&(curve.index<=end)]
    if len(sel)<2: return {"cagr":None,"mdd":None,"sharpe":None,"calmar":None,"turnover":None,"cost":None,"peryear":{}}
    m=metrics(sel); sh=_daily_metrics(sel)["sharpe"]
    mask=(turnover.index>=start)&(turnover.index<=end)
    yrs=max(mask.sum()/252,1e-12)
    return {"cagr":m["cagr"],"mdd":m["mdd"],"sharpe":sh,"calmar":m["calmar"],"turnover":float(turnover.loc[mask].sum()/yrs),"cost":float(cost.loc[mask].sum()/yrs),"peryear":m["peryear"]}


def revision():
    try:
        h=subprocess.check_output(["git","rev-parse","--short","HEAD"],cwd=ROOT,text=True).strip()
        dirty=bool(subprocess.check_output(["git","status","--porcelain"],cwd=ROOT,text=True).strip())
        return {"head":h,"dirty":dirty}
    except Exception: return {"head":"unknown","dirty":True}


def bench_curves(panel):
    ix="069500" if panel.market=="KR" else "SPY"
    out={"index_hold":_bench(panel,ix)}
    bill=next((s for s in panel.symbols if "단기채권" in panel.names[s] or s in ("BIL","SHY")),None)
    if bill:
        a=panel.c[ix].reindex(panel.dates).ffill().pct_change().fillna(0); b=panel.c[bill].reindex(panel.dates).ffill().pct_change().fillna(0)
        w=.6; curve=[1.]
        for t in range(1,len(panel.dates)):
            if panel.dates[t].month!=panel.dates[t-1].month: w=.6
            r=w*a.iloc[t]+(1-w)*b.iloc[t]; curve.append(curve[-1]*(1+r)); w=w*(1+a.iloc[t])/(1+r) if 1+r else w
        out["index60_bond40"]=pd.Series(curve,index=panel.dates)
    out["cash"]=pd.Series(1.,index=panel.dates)
    return out


def run_market(market, families=None):
    panel=load_panel(market,include_stocks=True)
    panel.dates=panel.dates[panel.dates<=DATA_END]
    # dataframes are already cutoff; no mutation of source cache.
    missing_etfs=panel.missing
    cutoff=pd.Timestamp("2022-12-31")
    hold_start=pd.Timestamp("2023-01-01")
    start=panel.dates[0]
    benchmarks=bench_curves(panel)
    rev=revision(); output={}; total=0
    for family in (families or FAMILIES):
        if family=="F8" and market!="KR": continue
        stock_symbols=[s for s in panel.symbols if panel.roles[s]=="stock"]
        stock_first=min((panel.c[s].first_valid_index() for s in stock_symbols if panel.c[s].notna().any()),default=start)
        family_start=stock_first if family in ("F4","F5","F6") else start
        params_list=candidates(market,family)
        if family=="F5":
            # Mapping is deliberately empty until primary, current industry evidence is available.
            params_list=[]
        fam_results=[]; curves=[]; all_turn=[]; all_cost=[]
        for i,params in enumerate(params_list):
            offset_curves=[]; offset_turn=[]; offset_cost=[]
            for offset in (0,7,14):
                target=weights(panel,family,params,offset)
                res=aw_engine.simulate(panel,target,drawdown_breaker=False)
                offset_curves.append(res["equity"]); offset_turn.append(res["turnover"]); offset_cost.append(res["costs"])
            curve=pd.concat(offset_curves,axis=1).mean(axis=1)
            turn=pd.concat(offset_turn,axis=1).mean(axis=1); cost=pd.concat(offset_cost,axis=1).mean(axis=1)
            search=calc(curve,turn,cost,family_start,min(cutoff,panel.dates[-1]))
            hold=calc(curve,turn,cost,hold_start,panel.dates[-1])
            full=calc(curve,turn,cost,family_start,panel.dates[-1])
            run_id=f"{market}-{family}-{int(time.time()*1000)}-{i:03d}"
            flags=["SURVIVOR"] if family in ("F4","F5","F6") else []
            if family in ("F4","F6"): flags.append("RISK_CAP_10PCT_ENFORCED")
            if missing_etfs: flags.append("MISSING_ETF_CACHE")
            row={"ts":pd.Timestamp.now(tz="UTC").isoformat(),"run_id":run_id,"market":market,"family":family,"params":params,"data_start":str(start.date()),"data_end":str(panel.dates[-1].date()),"n_offsets":3,"search_metrics":search,"holdout_metrics":hold,"full_metrics":full,"flags":flags,"code_rev":rev}
            BASE.mkdir(parents=True,exist_ok=True)
            with LEDGER.open("a",encoding="utf-8") as f: f.write(json.dumps(jsonsafe(row),ensure_ascii=False,allow_nan=False)+"\n")
            fam_results.append(row); curves.append(curve); all_turn.append(turn); all_cost.append(cost); total+=1
        stress_result=None
        if family in ("F4","F6") and fam_results:
            stock_syms=stock_symbols
            total_returns=panel.c[stock_syms].apply(lambda s: s.dropna().iloc[-1]/s.dropna().iloc[0]-1 if s.notna().sum()>=2 else np.nan).dropna()
            ex_post_top10=list(total_returns.sort_values(ascending=False).head(10).index)
            best_idx=max(range(len(fam_results)),key=lambda j:fam_results[j]["search_metrics"]["calmar"] if fam_results[j]["search_metrics"]["calmar"] is not None else -1e9)
            stress_params=copy.deepcopy(fam_results[best_idx]["params"]); stress_params["exclude_symbols"]=ex_post_top10
            stress_curves=[]; stress_turn=[]; stress_cost=[]
            for offset in (0,7,14):
                sr=aw_engine.simulate(panel,weights(panel,family,stress_params,offset),drawdown_breaker=False)
                stress_curves.append(sr["equity"]); stress_turn.append(sr["turnover"]); stress_cost.append(sr["costs"])
            sc=pd.concat(stress_curves,axis=1).mean(axis=1); st=pd.concat(stress_turn,axis=1).mean(axis=1); sx=pd.concat(stress_cost,axis=1).mean(axis=1)
            stress_row={"ts":pd.Timestamp.now(tz="UTC").isoformat(),"run_id":f"{market}-{family}-SURVIVOR_STRESS-{int(time.time()*1000)}","market":market,"family":family,"params":stress_params,"data_start":str(family_start.date()),"data_end":str(panel.dates[-1].date()),"n_offsets":3,"search_metrics":calc(sc,st,sx,family_start,min(cutoff,panel.dates[-1])),"holdout_metrics":calc(sc,st,sx,hold_start,panel.dates[-1]),"full_metrics":calc(sc,st,sx,family_start,panel.dates[-1]),"flags":["SURVIVOR","SURVIVOR_STRESS_TOP10_REMOVED"],"code_rev":rev}
            with LEDGER.open("a",encoding="utf-8") as f: f.write(json.dumps(jsonsafe(stress_row),ensure_ascii=False,allow_nan=False)+"\n")
            total+=1; stress_result={"excluded_top10":ex_post_top10,"search_metrics":stress_row["search_metrics"],"holdout_metrics":stress_row["holdout_metrics"],"full_metrics":stress_row["full_metrics"]}
        # Rank only on pre-registered search interval. Holdout is not passed to this selector.
        ranked=sorted(range(len(fam_results)),key=lambda j:(fam_results[j]["search_metrics"]["calmar"] if fam_results[j]["search_metrics"]["calmar"] is not None else -1e9),reverse=True)
        survivors=ranked[:min(2,len(ranked))]
        if survivors:
            selected_curves=[curves[j] for j in survivors]; selected_params=[fam_results[j]["params"] for j in survivors]
            wf_start=2015
            if family in ("F4","F5","F6"):
                first_stock=stock_first
                wf_start=pd.Timestamp(first_stock).year+3
            wf_curves=[c.loc[c.index>=family_start] for c in curves] if family in ("F4","F5","F6") else curves
            wf=build_wf(wf_curves, [x["params"] for x in fam_results], wf_start,panel.dates[-1].year)
            index=benchmarks["index_hold"]
            hold_sharpe=calc(pd.Series(wf["curve"]).set_axis(pd.to_datetime(list(wf["curve"].keys()))),pd.Series(0,index=pd.to_datetime(list(wf["curve"].keys()))),pd.Series(0,index=pd.to_datetime(list(wf["curve"].keys()))),hold_start,panel.dates[-1])["sharpe"] if wf["curve"] else None
            wf_dates=pd.to_datetime(list(wf["curve"].keys())) if wf["curve"] else pd.DatetimeIndex([])
            matched_index=index.reindex(wf_dates).ffill() if len(wf_dates) else index.iloc[:0]
            bm=metrics(matched_index); wfmdd=wf["mdd"] or 0; wfcagr=wf["cagr"] or 0
            bms=metrics(benchmarks["index_hold"])
            stable=False # One-step neighbor Sharpe perturbation has not been run; fail closed for A/B grading.
            grade="C"
            if wfcagr>=bms["cagr"] and wfmdd<=bms["mdd"]*.6 and (hold_sharpe or -999)>=_daily_metrics(index.loc[index.index>=hold_start])["sharpe"] and stable: grade="A"
            elif wfcagr>=bms["cagr"]*.7 and wfmdd<=bms["mdd"]*.5 and wf["annual_returns"].get("2022",0)>=-.08 and stable: grade="B"
            wf.update({"market":market,"family":family,"grade":grade,"decision_reason":"C: one-step neighbor Sharpe median gate not run; no A/B adoption without this required check" if grade=="C" else None,"top_search_candidates":selected_params,"search_trials":len(fam_results),"benchmark_index":{"cagr":bm["cagr"],"mdd":bm["mdd"]},"holdout_sharpe":hold_sharpe,"neighbor_stability":"NOT_VALIDATED","survivor_stress":stress_result})
            wf_path=BASE/"wf"/f"{market}_{family}.json"; write_wf(wf_path,jsonsafe(wf)); output[family]={"grade":grade,"wf":str(wf_path.relative_to(ROOT)),"trials":len(fam_results),"top_params":fam_results[ranked[0]]["params"] if ranked else None,"top_search":fam_results[ranked[0]]["search_metrics"] if ranked else None,"top_holdout":fam_results[ranked[0]]["holdout_metrics"] if ranked else None,"survivor_stress":stress_result}
        else:
            reason="No verifiable sector-stock mapping" if family=="F5" else "No candidate configurations"
            output[family]={"grade":"C","trials":0,"rejected":reason}
            write_wf(BASE/"wf"/f"{market}_{family}.json",{"market":market,"family":family,"grade":"C","decision":"REJECTED","reason":reason,"search_trials":0,"data_start":str(start.date()),"data_end":str(panel.dates[-1].date())})
        append_log(market,family,output[family],missing_etfs)
    return {"market":market,"trials":total,"families":output,"dates":[str(start.date()),str(panel.dates[-1].date())],"missing":missing_etfs}


def append_log(market,family,item,missing):
    BASE.mkdir(parents=True,exist_ok=True)
    text=f"\n## {pd.Timestamp.now(tz='UTC').isoformat()} — {market} {family}\n\n- 탐색 설정: {item.get('trials',0)}개; 오프셋 0/7/14 평균. 선택 지표는 2022-12-31 이전 구간만 사용.\n- 판정: {item.get('grade','C')}; 상위 검색 지표: `{json.dumps(item.get('top_search'),ensure_ascii=False)}`; 상위 설정: `{json.dumps(item.get('top_params'),ensure_ascii=False)}`. 홀드아웃은 원장에 분리 기록.\n- 누락 ETF 캐시: {', '.join(missing) if missing else '없음'}. 개별주 연장 미도착 여부: KR_005930 시작일 2018-01-02, 따라서 stock family는 2018년 이후만 유효하며 확장 감지 시 재실행 필요.\n- 다음: 다음 family 라운드, 이웃 안정성 및 미래 교란 검증 추가 확인.\n"
    with LOG.open("a",encoding="utf-8") as f: f.write(text)


def main(argv=None):
    p=argparse.ArgumentParser(); p.add_argument("--market",choices=("KR","US","BOTH"),default="BOTH"); p.add_argument("--family",choices=FAMILIES); a=p.parse_args(argv)
    markets=("KR","US") if a.market=="BOTH" else (a.market,)
    results=[run_market(m,[a.family] if a.family else None) for m in markets]
    print(json.dumps(results,ensure_ascii=False,indent=2,default=str))

if __name__=="__main__": main()
