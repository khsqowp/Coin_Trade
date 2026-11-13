"""Final Round-2 validation: exact one-coordinate neighbors and 3-offset stock stress."""
from __future__ import annotations
import copy,json
from pathlib import Path
import numpy as np,pandas as pd
from app import aw_engine
from app.aw2_round2 import BASE,LEDGER,_calc,_jsonsafe,_write_row,_revision,STOCK_FAMILIES
from app.aw2_spaces import space
from app.aw2_strategies import weights
from app.aw2_walkforward import build as build_wf
from app.aw_data import DATA_END,load_panel
from app.aw_run import _bench,_daily_metrics,metrics

def _wf_curve(row):
    p=BASE/"raw"/f"R2_{row['market']}_{row['family']}_{row['config_id']}.json"
    if not p.exists():return None
    x=json.loads(p.read_text(encoding="utf-8"));return pd.Series(x["curve_values"],index=pd.to_datetime(x["curve_dates"]))

def _params_neighbor(a,b):
    pa,pb=a["params"],b["params"]
    keys=set(pa)|set(pb);diff=[k for k in keys if pa.get(k)!=pb.get(k)]
    dependent={"max_weight","k","trend"}
    if "k" in diff and "max_weight" in diff:diff.remove("max_weight")
    if "sector_count" in diff or "per_sector" in diff:diff=[k for k in diff if k not in ("k",)]
    if "trend_filter" in diff and "trend" in diff:diff.remove("trend")
    return len(diff)==1

def _append_stress(market,family,panel,best,excluded):
    p={**best["params"],"exclude_symbols":excluded};curves=[];turns=[];costs=[]
    for off in (0,7,14):
        r=aw_engine.simulate(panel,weights(panel,family,copy.deepcopy(p),off),drawdown_breaker=False)
        curves.append(r["equity"]);turns.append(r["turnover"]);costs.append(r["costs"])
    eq=pd.concat(curves,axis=1).mean(axis=1);to=pd.concat(turns,axis=1).mean(axis=1);co=pd.concat(costs,axis=1).mean(axis=1)
    start=pd.Timestamp(best["data_start"])
    row={"ts":pd.Timestamp.now(tz="UTC").isoformat(),"run_id":f"R2-{market}-{family}-TOP10-EXCLUSION-3OFFSET","round":2,"config_id":f"stress-v2-{market}-{family}","search_phase":"survivor_stress","market":market,"family":family,"params":p,"data_start":str(start.date()),"data_end":str(panel.dates[-1].date()),"n_offsets":3,"search_metrics":_calc(eq,to,co,start,min(pd.Timestamp("2022-12-31"),panel.dates[-1])),"holdout_metrics":_calc(eq,to,co,pd.Timestamp("2023-01-01"),panel.dates[-1]),"full_metrics":_calc(eq,to,co,start,panel.dates[-1]),"flags":["SURVIVOR","TOP10_WINNER_EXCLUSION","THREE_OFFSETS"],"code_rev":_revision()}
    _write_row(row);return row

def finalize_group(market,family):
    stock=family in STOCK_FAMILIES;panel=load_panel(market,include_stocks=stock);panel.dates=panel.dates[panel.dates<=DATA_END]
    rows=[]
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        try:r=json.loads(line)
        except json.JSONDecodeError:continue
        if r.get("round")==2 and r.get("market")==market and r.get("family")==family and r.get("config_id") and "TOP10_WINNER_EXCLUSION" not in r.get("flags",[]):rows.append(r)
    latest={}
    for r in rows:latest[r["config_id"]]=r
    rows=[r for r in latest.values() if r.get("search_metrics",{}).get("calmar") is not None]
    rows.sort(key=lambda r:r["search_metrics"].get("calmar") if r["search_metrics"].get("calmar") is not None else -1e9,reverse=True)
    if not rows:return None
    best=rows[0];startyear=(pd.Timestamp(best["data_start"]).year+3) if stock else 2015
    pairs=[(r,_wf_curve(r)) for r in rows];pairs=[(r,c) for r,c in pairs if c is not None]
    curves=[c for _,c in pairs];params=[r["params"] for r,_ in pairs]
    wf=build_wf(curves,params,startyear,panel.dates[-1].year)
    bi=next(i for i,(r,_) in enumerate(pairs) if r["config_id"]==best["config_id"])
    best_curve=curves[bi]
    candidate_neighbor_curves=[]
    for j,(r,c) in enumerate(pairs):
        if r["config_id"]!=best["config_id"] and _params_neighbor(best,r):
            one=build_wf([c],[r["params"]],startyear,panel.dates[-1].year)
            if one.get("sharpe") is not None:candidate_neighbor_curves.append(one["sharpe"])
    neighbor=float(np.median(candidate_neighbor_curves)) if candidate_neighbor_curves else None
    stable=neighbor is not None and wf.get("sharpe") is not None and neighbor>=.6*wf["sharpe"]
    p={k:v for k,v in best["params"].items() if k not in ("exclude_symbols",)}
    original=weights(panel,family,copy.deepcopy(p),0)
    altered=copy.copy(panel);altered.c=panel.c.copy();altered.c.loc[altered.c.index>pd.Timestamp("2022-12-31")]*=1.5
    changed=weights(altered,family,copy.deepcopy(p),0)
    perturb=bool(np.allclose(original.loc[original.index<=pd.Timestamp("2022-12-31")],changed.loc[changed.index<=pd.Timestamp("2022-12-31")],equal_nan=True))
    stress=None
    if stock:
        symbols=[s for s in panel.symbols if panel.roles[s]=="stock"]
        total=panel.c[symbols].apply(lambda x:x.dropna().iloc[-1]/x.dropna().iloc[0]-1 if x.notna().sum()>1 else np.nan).dropna()
        excluded=list(total.nlargest(10).index);stress=_append_stress(market,family,panel,best,excluded)
    benchmark=_bench(panel,"069500" if market=="KR" else "SPY")
    wf_dates=pd.to_datetime(list(wf.get("curve",{})))
    b=benchmark.reindex(wf_dates).ffill() if len(wf_dates) else benchmark.iloc[:0]
    bm=metrics(b) if len(b)>2 else {}
    wfcurve=pd.Series(wf.get("curve",{}),dtype=float);wfcurve.index=pd.to_datetime(wfcurve.index) if len(wfcurve) else wfcurve.index
    hold=_daily_metrics(wfcurve.loc[wfcurve.index>=pd.Timestamp("2023-01-01")])["sharpe"] if len(wfcurve)>2 else None
    idx_hold=_daily_metrics(benchmark.loc[benchmark.index>=pd.Timestamp("2023-01-01")])["sharpe"]
    grade="C";reason=""
    if stable and perturb:
        if wf.get("cagr",-np.inf)>=bm.get("cagr",np.inf) and wf.get("mdd",np.inf)<=bm.get("mdd",0)*.6 and (hold if hold is not None else -999)>=idx_hold:grade="A"
        elif wf.get("cagr",-np.inf)>=bm.get("cagr",0)*.7 and wf.get("mdd",np.inf)<=bm.get("mdd",0)*.5 and wf.get("annual_returns",{}).get("2022",0)>=-.08:grade="B"
    if not stable:reason="one-step neighbor WF Sharpe median below 60% or no valid neighbor"
    if not perturb:reason=(reason+"; " if reason else "")+"future perturbation changed pre-cutoff targets"
    wf.update({"market":market,"family":family,"grade":grade,"decision_reason":reason or "performance conditions not met","top_params":best["params"],"search_trials":len(rows),"search_ledger_rows":len([r for r in rows]),"neighbor_sharpe_median":neighbor,"neighbor_count":len(candidate_neighbor_curves),"neighbor_stable":stable,"future_perturbation_pass":perturb,"holdout_sharpe":hold,"benchmark":{"cagr":bm.get("cagr"),"mdd":bm.get("mdd"),"holdout_sharpe":idx_hold},"survivor_stress_3offset":stress})
    path=BASE/"wf"/f"{market}_{family}_R2.json";path.write_text(json.dumps(_jsonsafe(wf),ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    with (BASE/"AW2_LOG.md").open("a",encoding="utf-8") as f:f.write(f"\n#### Final verification — {market} {family}\n\n- Unique config rows: {len(rows)}; exact one-value-neighbor WF count: {len(candidate_neighbor_curves)}; median Sharpe: {neighbor}; stable={stable}. Future perturbation pass={perturb}. Top-10 survivor stress uses 3 offsets: {stress['search_metrics'] if stress else 'not applicable'}. Decision: {grade}.\n")
    return wf

def main():
    for family in ("F1","F2","F3","F4","F5","F6","F7","F8","F10","F11","F12","F13"):
        for market in ("KR","US"):
            if family=="F8" and market=="US" or family=="F11" and market=="US":continue
            finalize_group(market,family)
    import csv
    from app.aw_universe import stocks
    from app.aw_data import _cache_path
    audit=BASE/"stock_cache_first_dates.csv"
    with audit.open("w",newline="",encoding="utf-8") as f:
        writer=csv.writer(f);writer.writerow(["market","symbol","first_bar","cache_status"])
        for market in ("KR","US"):
            for item in stocks(market):
                path=_cache_path(market,item["code"])
                if not path.exists():writer.writerow([market,item["code"],"","MISSING"]);continue
                try:first=pd.read_csv(path,usecols=["timestamp"],nrows=1).iloc[0,0]
                except Exception:first=""
                writer.writerow([market,item["code"],str(first)[:10],"PRESENT" if first else "EMPTY"])
    from app.aw2_report_r2 import build
    build()
if __name__=="__main__":main()
