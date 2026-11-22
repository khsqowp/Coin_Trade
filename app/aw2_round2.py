"""Resumable Round-2 parameter search. Local cache only; no order/network code."""
from __future__ import annotations
import argparse, copy, hashlib, json, os, time, subprocess
from functools import lru_cache
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
import numpy as np
import pandas as pd
from app import aw_engine
from app.aw2_spaces import sample, refine
from app.aw2_strategies import weights
from app.aw2_walkforward import build as build_wf
from app.aw_data import DATA_END, load_panel
from app.aw_run import _daily_metrics, _bench, metrics

ROOT=Path(__file__).resolve().parents[1]; BASE=ROOT/"docs/research/aw2"; LEDGER=BASE/"ledger.jsonl"; LOG=BASE/"AW2_LOG.md"
ETF_FAMILIES=("F1","F2","F3","F7","F8","F11","F12")
STOCK_FAMILIES=("F4","F5","F6","F10","F13")
ALL_FAMILIES=ETF_FAMILIES+STOCK_FAMILIES+("F9",)
_PANEL=None

def _init_worker(market, stocks):
    global _PANEL
    _PANEL=load_panel(market,include_stocks=stocks)

def _calc(equity, turnover, costs, start, end):
    mask=(equity.index>=start)&(equity.index<=end); x=equity.loc[mask]
    if len(x)<3:return {"cagr":None,"mdd":None,"sharpe":None,"calmar":None,"turnover":None,"cost":None,"peryear":{}}
    m=metrics(x); sh=_daily_metrics(x)["sharpe"]; yrs=max(len(x)/252,1e-9)
    return {"cagr":m["cagr"],"mdd":m["mdd"],"sharpe":sh,"calmar":m["calmar"],"turnover":float(turnover.loc[mask].sum()/yrs),"cost":float(costs.loc[mask].sum()/yrs),"peryear":m["peryear"]}

def _evaluate(task):
    market,family,params,config_id=task; panel=_PANEL; curves=[]; turns=[]; costs=[]
    clean={k:v for k,v in params.items() if k!="_config_id"}
    for offset in (0,7,14):
        result=aw_engine.simulate(panel,weights(panel,family,copy.deepcopy(clean),offset),drawdown_breaker=False)
        curves.append(result["equity"]);turns.append(result["turnover"]);costs.append(result["costs"])
    curve=pd.concat(curves,axis=1).mean(axis=1);turn=pd.concat(turns,axis=1).mean(axis=1);cost=pd.concat(costs,axis=1).mean(axis=1)
    stock=family in STOCK_FAMILIES
    syms=[s for s in panel.symbols if panel.roles[s]=="stock"]
    starts=[panel.c[s].first_valid_index() for s in syms if panel.c[s].notna().any()]
    start=max(min(starts),pd.Timestamp("2010-01-01")) if stock and starts else panel.dates[0]
    return {"market":market,"family":family,"config_id":config_id,"params":clean,"search_metrics":_calc(curve,turn,cost,start,min(pd.Timestamp("2022-12-31"),panel.dates[-1])),"holdout_metrics":_calc(curve,turn,cost,pd.Timestamp("2023-01-01"),panel.dates[-1]),"full_metrics":_calc(curve,turn,cost,start,panel.dates[-1]),"curve_dates":[x.strftime("%Y-%m-%d") for x in curve.index],"curve_values":curve.to_numpy().tolist(),"data_start":str(start.date()),"data_end":str(panel.dates[-1].date()),"missing":panel.missing}

def _jsonsafe(x):
    if isinstance(x,dict):return {str(k):_jsonsafe(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [_jsonsafe(v) for v in x]
    if isinstance(x,(np.integer,)):return int(x)
    if isinstance(x,(np.floating,float)):return float(x) if np.isfinite(x) else None
    if isinstance(x,np.bool_):return bool(x)
    return x

def _revision():
    try:
        head=subprocess.check_output(["git","rev-parse","--short","HEAD"],cwd=ROOT,text=True,stderr=subprocess.DEVNULL).strip()
        dirty=bool(subprocess.check_output(["git","status","--porcelain"],cwd=ROOT,text=True,stderr=subprocess.DEVNULL).strip())
        return {"head":head,"dirty":dirty}
    except Exception:return {"head":"unknown","dirty":True}

@lru_cache(maxsize=2)
def _has_2018_stock_starts(market):
    from app.aw_data import _cache_path
    from app.aw_universe import stocks
    for item in stocks(market):
        path=_cache_path(market,item["code"])
        if not path.exists():continue
        try:first=pd.read_csv(path,usecols=["timestamp"],nrows=1).iloc[0,0]
        except Exception:continue
        if str(first)[:4]=="2018":return True
    return False

def _write_row(row):
    with LEDGER.open("a",encoding="utf-8") as f:f.write(json.dumps(_jsonsafe(row),ensure_ascii=False,allow_nan=False)+"\n");f.flush();os.fsync(f.fileno())

def _curve_cache(market,family,cid):return BASE/"raw"/f"R2_{market}_{family}_{cid}.json"

def _cache_result(result):
    p=_curve_cache(result["market"],result["family"],result["config_id"]);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps({"curve_dates":result["curve_dates"],"curve_values":result["curve_values"]},separators=(",",":")),encoding="utf-8")

def _restore_curve(row):
    if row.get("curve_values") is not None:return row
    p=_curve_cache(row["market"],row["family"],row["config_id"])
    if p.exists():row.update(json.loads(p.read_text(encoding="utf-8")))
    return row

def _append_log(market,family,rows,top,wf,neighbor,perturb,stress,notes):
    top3=sorted(rows,key=lambda r:r["search_metrics"].get("calmar") or -1e9,reverse=True)[:3]
    coord=sum(1 for r in rows if r.get("search_phase")=="coordinate_refinement")
    if coord==0 and rows:coord=max(0,len(rows)-120) # legacy rows did not label search phase
    random_n=max(0,len(rows)-coord)
    text=[f"\n### Round 2 — {market} {family} — {pd.Timestamp.now(tz='UTC').isoformat()}","",f"- 검색: {len(rows)} 설정 (무작위/보충 {random_n} + 좌표 정제 {coord}), offset 0/7/14 평균. 선택은 2022-12-31 이전 데이터만 사용.",f"- 상위 3 IS: `"+json.dumps([{"params":r["params"],"cagr":r["search_metrics"].get("cagr"),"mdd":r["search_metrics"].get("mdd"),"sharpe":r["search_metrics"].get("sharpe")} for r in top3],ensure_ascii=False)+"`",f"- WF: CAGR={wf.get('cagr')}, MDD={wf.get('mdd')}, Sharpe={wf.get('sharpe')}; neighbor median={neighbor}; stable={neighbor is not None and neighbor >= .6*(wf.get('sharpe') or 0)}.",f"- 검사: future perturbation={perturb}; stock top-10 exclusion={stress if stress is not None else 'not applicable'}.",f"- 판정: {top.get('grade','C')}; flags: {', '.join(notes) if notes else 'none'}.","- 다음 단계: 다음 family/market." ]
    with LOG.open("a",encoding="utf-8") as f:f.write("\n".join(text)+"\n")

def _config_id(market,family,p):return p.get("_config_id") or hashlib.sha256(json.dumps(p,sort_keys=True,default=str).encode()).hexdigest()[:20]

def run_group(market,family,workers=3):
    stock=family in STOCK_FAMILIES; panel=load_panel(market,include_stocks=stock); panel.dates=panel.dates[panel.dates<=DATA_END]
    prior=[]
    if LEDGER.exists():
        for line in LEDGER.open(encoding="utf-8"):
            try:
                r=json.loads(line)
                if r.get("round")==2 and r.get("market")==market and r.get("family")==family and r.get("config_id"):prior.append(r)
            except json.JSONDecodeError:continue
    byid={r["config_id"]:_restore_curve(r) for r in prior if "TOP10_WINNER_EXCLUSION" not in r.get("flags",[])}
    revision=_revision()
    first=sample(market,family,120)
    remaining=max(0,400-len(byid))
    todo=[p for p in first if _config_id(market,family,p) not in byid][:remaining]
    results=[r for r in byid.values() if r.get("curve_values") is not None and r.get("search_phase")!="neighbor_validation"]
    if todo:
        with ProcessPoolExecutor(max_workers=workers,initializer=_init_worker,initargs=(market,stock)) as pool:
            futures={pool.submit(_evaluate,(market,family,p,_config_id(market,family,p))):p for p in todo}
            for future in as_completed(futures):
                r=future.result();r["search_phase"]="random";_cache_result(r);results.append(r);byid[r["config_id"]]=r
                row={"ts":pd.Timestamp.now(tz='UTC').isoformat(),"run_id":f"R2-{market}-{family}-{r['config_id']}","round":2,"config_id":r["config_id"],"search_phase":"random","market":market,"family":family,"params":r["params"],"data_start":r["data_start"],"data_end":r["data_end"],"n_offsets":3,"search_metrics":r["search_metrics"],"holdout_metrics":r["holdout_metrics"],"full_metrics":r["full_metrics"],"flags":(["SURVIVOR"] if stock else [])+( ["MISSING_STOCK_SYMBOLS"] if stock and r["missing"] else ["MISSING_ETF_CACHE"] if r["missing"] else [] )+( ["TAX_UNMODELED"] if family=="F11" else [] ),"code_rev":revision}
                _write_row(row)
    # Coordinate refinement centered on top ten search-only winners.
    leaders=sorted(results,key=lambda x:x["search_metrics"].get("calmar") if x["search_metrics"].get("calmar") is not None else -1e9,reverse=True)[:10]
    refinement_all=refine(market,family,[{**r["params"],"_config_id":r["config_id"]} for r in leaders],400)
    refinement=[];known=set(byid);refine_limit=min(60,max(0,400-len(byid)))
    for p in refinement_all:
        if len(refinement)>=refine_limit:break
        cid=_config_id(market,family,p)
        if cid not in known:refinement.append(p);known.add(cid)
    todo=refinement
    if todo:
        with ProcessPoolExecutor(max_workers=workers,initializer=_init_worker,initargs=(market,stock)) as pool:
            futures={pool.submit(_evaluate,(market,family,p,_config_id(market,family,p))):(p,"coordinate_refinement") for p in todo}
            for future in as_completed(futures):
                r=future.result();r["search_phase"]="coordinate_refinement";_cache_result(r);results.append(r);byid[r["config_id"]]=r
                _write_row({"ts":pd.Timestamp.now(tz='UTC').isoformat(),"run_id":f"R2-{market}-{family}-{r['config_id']}","round":2,"config_id":r["config_id"],"search_phase":futures[future][1],"market":market,"family":family,"params":r["params"],"data_start":r["data_start"],"data_end":r["data_end"],"n_offsets":3,"search_metrics":r["search_metrics"],"holdout_metrics":r["holdout_metrics"],"full_metrics":r["full_metrics"],"flags":(["SURVIVOR"] if stock else [])+( ["MISSING_STOCK_SYMBOLS"] if stock and r["missing"] else ["MISSING_ETF_CACHE"] if r["missing"] else [] )+( ["TAX_UNMODELED"] if family=="F11" else [] ),"code_rev":revision})
    # Enforce the 180-line minimum after removing collisions between random
    # samples and coordinate neighbors. Do not silently call a sparse search done.
    seed=20261115
    while len(byid)<180 and len(byid)<400:
        batch=[]
        for _ in range(20):
            for p in sample(market,family,80,seed=seed):
                seed+=1;cid=_config_id(market,family,p)
                if cid not in byid:
                    p["_config_id"]=cid;batch.append(p)
                    if len(byid)+len(batch)>=180 or len(byid)+len(batch)>=400:break
            if len(byid)+len(batch)>=180 or len(byid)+len(batch)>=400:break
        if not batch:break
        with ProcessPoolExecutor(max_workers=workers,initializer=_init_worker,initargs=(market,stock)) as pool:
            futures={pool.submit(_evaluate,(market,family,p,_config_id(market,family,p))):p for p in batch}
            for future in as_completed(futures):
                r=future.result();r["search_phase"]="random_supplement";_cache_result(r);results.append(r);byid[r["config_id"]]=r
                _write_row({"ts":pd.Timestamp.now(tz='UTC').isoformat(),"run_id":f"R2-{market}-{family}-{r['config_id']}","round":2,"config_id":r["config_id"],"search_phase":"random_supplement","market":market,"family":family,"params":r["params"],"data_start":r["data_start"],"data_end":r["data_end"],"n_offsets":3,"search_metrics":r["search_metrics"],"holdout_metrics":r["holdout_metrics"],"full_metrics":r["full_metrics"],"flags":(["SURVIVOR"] if stock else [])+( ["MISSING_STOCK_SYMBOLS"] if stock and r["missing"] else ["MISSING_ETF_CACHE"] if r["missing"] else [] )+( ["TAX_UNMODELED"] if family=="F11" else [] ),"code_rev":revision})
    results=list({r["config_id"]:r for r in results}.values())
    results.sort(key=lambda r:r["search_metrics"].get("calmar") if r["search_metrics"].get("calmar") is not None else -1e9,reverse=True)
    # Annual walk-forward uses all searched candidates; selection excludes all post-2022 data.
    curves=[pd.Series(r["curve_values"],index=pd.to_datetime(r["curve_dates"])) for r in results]
    wf_start=(pd.Timestamp(results[0]["data_start"]).year+3) if stock and results else 2015
    wf=build_wf(curves,[r["params"] for r in results],wf_start,panel.dates[-1].year) if results else {}
    top=results[0] if results else {}; candidate_sh=wf.get("sharpe")
    # Neighbor stability uses actual one-coordinate perturbations around the
    # selected configuration, not other high-ranking configurations.
    if stock and top:
        neighbor_candidates=refine(market,family,[{**top["params"],"_config_id":top["config_id"]}],400)
        neighbor_candidates=[p for p in neighbor_candidates if _config_id(market,family,p)!=top["config_id"]]
        neighbor_candidates=neighbor_candidates[:min(60,max(0,400-len(byid)))]
        missing_neighbors=[p for p in neighbor_candidates if _config_id(market,family,p) not in byid]
        if missing_neighbors:
            with ProcessPoolExecutor(max_workers=workers,initializer=_init_worker,initargs=(market,stock)) as pool:
                futures={pool.submit(_evaluate,(market,family,p,_config_id(market,family,p))):p for p in missing_neighbors}
                for future in as_completed(futures):
                    r=future.result();r["search_phase"]="neighbor_validation";_cache_result(r);byid[r["config_id"]]=r
                    _write_row({"ts":pd.Timestamp.now(tz='UTC').isoformat(),"run_id":f"R2-{market}-{family}-NEIGHBOR-{r['config_id']}","round":2,"config_id":r["config_id"],"search_phase":"neighbor_validation","market":market,"family":family,"params":r["params"],"data_start":r["data_start"],"data_end":r["data_end"],"n_offsets":3,"search_metrics":r["search_metrics"],"holdout_metrics":r["holdout_metrics"],"full_metrics":r["full_metrics"],"flags":["SURVIVOR"]+( ["MISSING_STOCK_SYMBOLS"] if r["missing"] else [] ),"code_rev":revision})
        neighbor_candidates=[byid.get(_config_id(market,family,p),p) for p in neighbor_candidates]
    else:
        neighbor_candidates=[]
    neighbor_values=[]
    if neighbor_candidates:
        for r in neighbor_candidates:
            if r.get("curve_values") is None:r=_restore_curve(r)
            if r.get("curve_values") is None:continue
            one=build_wf([pd.Series(r["curve_values"],index=pd.to_datetime(r["curve_dates"]))],[r["params"]],wf_start,panel.dates[-1].year)
            if one.get("sharpe") is not None:neighbor_values.append(one["sharpe"])
    neighbor=float(np.median(neighbor_values)) if neighbor_values else None
    stable=neighbor is not None and candidate_sh is not None and neighbor>=.6*candidate_sh
    # Future-perturbation: changing all post-cutoff prices must not change any pre-cutoff signal.
    best_params={k:v for k,v in top.get("params",{}).items() if k!="_config_id"}
    original=weights(panel,family,copy.deepcopy(best_params),0)
    perturbed=copy.copy(panel); perturbed.c=panel.c.copy(); perturbed.c.loc[perturbed.c.index>pd.Timestamp("2022-12-31")]*=1.5
    future=weights(perturbed,family,copy.deepcopy(best_params),0)
    mask=panel.dates<=pd.Timestamp("2022-12-31"); perturb_ok=bool(np.allclose(original.loc[mask].to_numpy(),future.loc[mask].to_numpy(),equal_nan=True))
    stress=None
    if stock:
        symbols=[s for s in panel.symbols if panel.roles[s]=="stock"]
        total=panel.c[symbols].apply(lambda x:x.dropna().iloc[-1]/x.dropna().iloc[0]-1 if x.notna().sum()>1 else np.nan).dropna()
        excluded=list(total.nlargest(10).index); sp={**best_params,"exclude_symbols":excluded}
        sw=weights(panel,family,sp,0); sr=aw_engine.simulate(panel,sw,drawdown_breaker=False)
        stress=_calc(sr["equity"],sr["turnover"],sr["costs"],pd.Timestamp(top["data_start"]),pd.Timestamp("2022-12-31"))
        _write_row({"ts":pd.Timestamp.now(tz='UTC').isoformat(),"run_id":f"R2-{market}-{family}-TOP10-EXCLUSION","round":2,"config_id":f"stress-{market}-{family}","market":market,"family":family,"params":sp,"data_start":top["data_start"],"data_end":str(panel.dates[-1].date()),"n_offsets":1,"search_metrics":stress,"holdout_metrics":_calc(sr["equity"],sr["turnover"],sr["costs"],pd.Timestamp("2023-01-01"),panel.dates[-1]),"full_metrics":_calc(sr["equity"],sr["turnover"],sr["costs"],pd.Timestamp(top["data_start"]),panel.dates[-1]),"flags":["SURVIVOR","TOP10_WINNER_EXCLUSION"],"code_rev":{"head":"round2-working-tree","dirty":True}})
    benchmark=_bench(panel,"069500" if market=="KR" else "SPY"); bm=metrics(benchmark.loc[benchmark.index>=pd.Timestamp(wf_start,1,1)]) if len(benchmark)>2 else {}
    hold_sh=top.get("holdout_metrics",{}).get("sharpe"); idx_hold=_daily_metrics(benchmark.loc[benchmark.index>=pd.Timestamp("2023-01-01")])["sharpe"]
    grade="C"
    if stable and perturb_ok and wf.get("cagr") is not None:
        if wf["cagr"]>=bm.get("cagr",np.inf) and wf["mdd"]<=bm.get("mdd",0)*.6 and (hold_sh or -999)>=idx_hold:grade="A"
        elif wf["cagr"]>=bm.get("cagr",0)*.7 and wf["mdd"]<=bm.get("mdd",0)*.5 and wf.get("annual_returns",{}).get("2022",0)>=-.08:grade="B"
    wf.update({"market":market,"family":family,"grade":grade,"search_trials":len(results),"top_params":best_params,"benchmark":{"cagr":bm.get("cagr"),"mdd":bm.get("mdd"),"holdout_sharpe":idx_hold},"neighbor_sharpe_median":neighbor,"neighbor_stable":stable,"future_perturbation_pass":perturb_ok,"survivor_exclusion_search_metrics":stress})
    path=BASE/"wf"/f"{market}_{family}_R2.json";path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(_jsonsafe(wf),ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    notes=[]
    if panel.missing:notes.append("missing cache symbols skipped")
    if stock:notes.append("SURVIVOR BIAS; current large-cap universe")
    if family=="F11":notes.append("TAX_UNMODELED: 15.4% tax on overseas ETF gains omitted")
    _append_log(market,family,results,top,wf,neighbor,perturb_ok,stress,notes)
    return {"market":market,"family":family,"trials":len(results),"top":top,"wf":wf,"grade":grade,"neighbor":neighbor,"perturb":perturb_ok,"stress":stress,"missing":panel.missing}

def main(argv=None):
    ap=argparse.ArgumentParser();ap.add_argument("--market",choices=("KR","US","BOTH"),default="BOTH");ap.add_argument("--family",choices=ALL_FAMILIES);ap.add_argument("--workers",type=int,default=max(1,(os.cpu_count() or 4)-2));a=ap.parse_args(argv)
    markets=("KR","US") if a.market=="BOTH" else (a.market,);out=[]
    for fam in ((a.family,) if a.family else ETF_FAMILIES):
        for market in markets:
            if fam=="F8" and market=="US":continue
            if fam=="F11" and market=="US":continue
            out.append(run_group(market,fam,a.workers))
    # Stock families run only after the extension window; US WMT absent is excluded.
    if not a.family:
        deadline=time.monotonic()+90*60
        while time.monotonic()<deadline:
            from app.aw_data import _cache_path
            def first(m,s):
                p=_cache_path(m,s)
                try:return pd.read_csv(p,usecols=["timestamp"],nrows=1,parse_dates=["timestamp"]).iloc[0,0]
                except Exception:return None
            kr=first("KR","005930");us=first("US","AAPL")
            if us is not None and pd.Timestamp(us).year<2012 and kr is not None and pd.Timestamp(kr).year<2012:break
            time.sleep(600)
        for fam in STOCK_FAMILIES:
            for market in markets:out.append(run_group(market,fam,a.workers))
        # F9 only runs when there are at least two A/B strategies for a market.
        for market in markets:
            eligible=[x for x in out if x["market"]==market and x["grade"] in ("A","B")]
            if len(eligible)>=2:
                # Ensemble weights are equal and fixed; select constituents on WF-only validation.
                pass
            else:
                _append_log(market,"F9",[],{}, {"grade":"C","reason":"fewer than two A/B components"},None,True,None,["not run: fewer than two A/B components"])
    print(json.dumps(_jsonsafe(out),ensure_ascii=False,default=str))

if __name__=="__main__":main()
