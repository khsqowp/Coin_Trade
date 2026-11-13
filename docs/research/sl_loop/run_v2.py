"""Revised v2 hourly SL grid. Run from trading/: python docs/research/sl_loop/run_v2.py."""
from __future__ import annotations
import os, sys, json, math, hashlib, concurrent.futures as cf
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
os.environ["RS_FINAL_SCRATCH"] = str(ROOT / ".rs_cache/sl_panel")
os.environ["NUMBA_CACHE_DIR"] = str(ROOT / ".rs_cache/sl_nbc")
sys.path.insert(0, str(ROOT))
from docs.research.sl_loop.lib import load_all, ENVA, phase_mean

OUT = Path(__file__).resolve().parent
PHASES = (0,1,2)
_ENGINE = None

def _json(obj): return json.dumps(obj,separators=(",",":"),default=lambda x: x.item() if isinstance(x,np.generic) else str(x))

def _init_worker():
    global _ENGINE
    panel_cache = np.load(os.path.join(os.environ["RS_FINAL_SCRATCH"], "rs_final_panel.npz"), allow_pickle=True)
    P = {k: np.load(os.path.join(os.environ["RS_FINAL_SCRATCH"], k + ".npy"), mmap_mode="r") for k in ("H","L","C","FD")}
    P["names"] = list(panel_cache["names"]); P["days"] = __import__("pandas").DatetimeIndex(panel_cache["days"], tz="UTC")
    from app.rs_sl_engine import TPSim
    CF = np.load(os.path.join(os.environ["RS_FINAL_SCRATCH"], "CF.npy"), mmap_mode="r")
    _ENGINE = TPSim(P, CF)

def _one(cell, phase):
    global _ENGINE
    kw = dict(ENVA); kw["lev"] = cell.get("lev",4.); kw["cost"] = cell.get("cost",.001)
    sl = dict(SL=cell.get("sL",-1.), SS=cell.get("sS",-1.), lockout=int(cell.get("lock",0)),
              fillmode=cell.get("fill",1), slipx=.003)
    tp = dict(XL=cell.get("xL",0.), XS=cell.get("xS",0.), frac=1., lockout=int(cell.get("lock",0)),
              fillmode=cell.get("fill",1), slipx=.003)
    r = _ENGINE.run(sl=sl, phase=phase, crash_mode=cell.get("crash",1), **kw)
    from app.rs_final_engine import window_metrics
    m = {w: window_metrics(r,a,b) for w,(a,b) in {"IS":("2022-01-01","2024-06-30"),"OOS":("2024-07-01",None),"full":(None,None)}.items()}
    m["years"] = {str(y): window_metrics(r,f"{y}-01-01",f"{y}-12-31") for y in range(2022,2027)}
    trades = r["trades"]
    types = {"reb":0,"sl":0,"kill":0}
    tnames = {0:"reb",3:"kill",4:"sl"}
    for row in trades: types[tnames.get(int(row[4]),"reb")] += 1
    days = len(r["eq"].dropna())
    m["operating"] = dict(kills=int(r["kills"]), liq=int(r["liq"]), stops=int(r.get("nsl",0)), tps=int(r.get("ntp",0)),
                          stop_long=sum(int(x[4])==4 and x[1]>0 for x in trades), stop_short=sum(int(x[4])==4 and x[1]<0 for x in trades),
                          events=types, exposure=float(r["expo"].replace([np.inf,-np.inf],np.nan).mean()),
                          flat_share=float((r["expo"]==0).mean()), mean_npos=float(r["npos"]), days=days,
                          avg_equity=float(r["eq"].dropna().mean()), cost_paid=float(r["cost_paid"]), turnover=float(r["turnover"]))
    return cell["id"], phase, m, trades.tolist()

def _cell_id(d):
    keys=("lev","sL","sS","lock","fill","crash")
    canon = json.dumps({k:d[k] for k in keys},sort_keys=True,separators=(",",":"))
    return hashlib.sha1(canon.encode()).hexdigest()[:12]

def _add(reg, **kw):
    d=dict(lev=4.,sL=-1.,sS=-1.,lock=0,fill=1,crash=1,family="base")
    d.update(kw)
    d["id"]=_cell_id(d); reg[d["id"]]=d; return d["id"]

def _primary():
    reg={}; _add(reg, family="baseline",s=None)
    levels=(0.,.005,.01,.015,.02,.03,.04,.05,.06,.07,.08,.09,.10,.12,.14,.16,.18,.20,.225,.25,.275,.30,.35,.40,.50,.60,.75,1.)
    for s in levels:
        _add(reg,sL=s,sS=s,family="both_reentry",s=s)
        _add(reg,sL=s,sS=s,lock=1,family="both_lockout",s=s)
    return reg,levels

def _write_cell(cell, phase_results, phase_trades, allcells):
    row={"id":cell["id"],"params":cell,"phase_results":{str(p):phase_results[p] for p in PHASES}}
    for w in ("IS","OOS","full"):
        mm=[phase_results[p][w] for p in PHASES]
        row[w]={k:float(np.mean([x[k] for x in mm])) for k in ("cagr","mdd","imdd","sharpe","end")}
        row[w]["calmar_i"]=float(np.mean([x["cagr"]/x["imdd"] if x["imdd"]>0 else 0 for x in mm]))
        row[w]["calmar_i_worst"]=float(min(x["cagr"]/x["imdd"] if x["imdd"]>0 else 0 for x in mm))
        row[w]["end_wealth_multiple"] = row[w]["end"]
    row["kills_mean"]=float(np.mean([phase_results[p]["operating"]["kills"] for p in PHASES]))
    row["liquidations"]=int(sum(phase_results[p]["operating"]["liq"] for p in PHASES))
    yrs=float(np.mean([phase_results[p]["operating"]["days"] for p in PHASES]))/365.
    row["stops_per_year"]={side:float(np.mean([phase_results[p]["operating"]["stop_"+side] for p in PHASES])/max(yrs,1e-9)) for side in ("long","short")}
    row["stops_per_year"]["all"]=sum(row["stops_per_year"].values())
    row["kills_per_year"]=row["kills_mean"]/yrs
    row["turnover_x_per_year"]=float(np.mean([phase_results[p]["operating"]["turnover"]/max(phase_results[p]["operating"]["avg_equity"],1e-12)/yrs for p in PHASES]))
    row["cost_pct_avg_equity_per_year"]=float(np.mean([phase_results[p]["operating"]["cost_paid"]/max(phase_results[p]["operating"]["avg_equity"],1e-12)/yrs for p in PHASES]))
    # retain compact close event rows for audit and follow-on attribution
    eventdir=ROOT/".rs_cache"/"sl_events_v2"; eventdir.mkdir(parents=True,exist_ok=True)
    eventpath=eventdir/(cell["id"]+".jsonl")
    with eventpath.open("w") as f:
        for p in PHASES:
            for t in phase_trades[p]:
                f.write(_json({"phase":p,"symbol_index":int(t[0]),"side":int(t[1]),"entry_day":int(t[2]),"exit_day":int(t[3]),"type":int(t[4]),"pnl":t[5],"equity_entry":t[6],"notional":t[7],"entry_px":t[8],"exit_px":t[9],"hour":int(t[10]),"adverse_excursion":t[11]})+"\n")
    row["events_file"]=str(eventpath)
    row["grid_version"]=2
    allcells[cell["id"]]=row
    with (OUT/"ledger.jsonl").open("a") as f: f.write(_json(row)+"\n")
    return row

def _run_batch(reg, workers):
    rows={}; pending={}
    with cf.ProcessPoolExecutor(max_workers=workers,initializer=_init_worker) as pool:
        for d in reg.values():
            pending[d["id"]]={p:pool.submit(_one,d,p) for p in PHASES}
        for cid,d in reg.items():
            pres={}; ptr={}
            for p in PHASES:
                got= pending[cid][p].result(); pres[p]=got[2]; ptr[p]=got[3]
            rows[cid]=_write_cell(d,pres,ptr,rows)
    return rows

def main():
    P,CFUND=load_all()
    ledger=OUT/"ledger.jsonl"
    existing={}
    if ledger.exists():
        for line in ledger.read_text().splitlines():
            if not line.strip(): continue
            row=json.loads(line)
            if row.get("grid_version")==2: existing[row["id"]]=row
    reg,levels=_primary()
    primary={cid:existing[cid] for cid in reg if cid in existing}
    primary.update(_run_batch({cid:d for cid,d in reg.items() if cid not in existing},9))
    base=next(v for v in primary.values() if v["params"]["family"]=="baseline")
    eligible=[]
    for cid,row in primary.items():
        p=row["params"]
        if p["family"] == "both_reentry" and p.get("s") is not None:
            if row["IS"]["end"]>=.85*base["IS"]["end"]: eligible.append(row)
    top3=sorted(eligible,key=lambda x:x["IS"]["calmar_i"],reverse=True)[:3]
    best_both=top3[0] if top3 else base
    extra={}
    # Leverage robustness: complete both-side reentry curves and baseline.
    for lev in (2.,3.):
        _add(extra,lev=lev,family="leverage_baseline",s=None)
        for s in levels: _add(extra,lev=lev,sL=s,sS=s,family="leverage_both",s=s)
    # Crash reference rows; mode 0 overlaps baseline and selected fill robustness.
    for crash in (0,2):
        _add(extra,crash=crash,family="crash_reference",crash_name=crash,ref_stop="none",s=None)
        s=best_both["params"].get("s")
        _add(extra,crash=crash,sL=-1. if s is None else s,sS=-1. if s is None else s,family="crash_reference",crash_name=crash,ref_stop=s,s=s)
    # Fill mode robustness for fixed IS-selected cells, including baseline.
    fixed=[base,*top3]
    for cand in fixed:
        p=cand["params"]
        for fill in (0,2):
            _add(extra,lev=p["lev"],sL=p["sL"],sS=p["sS"],lock=0,fill=fill,crash=1,family="fill_robustness",ref=p["id"],s=p.get("s"))
    extra={cid:d for cid,d in extra.items() if cid not in primary and cid not in existing}
    secondary={cid:existing[cid] for cid in extra if cid in existing}
    secondary.update(_run_batch({cid:d for cid,d in extra.items() if cid not in existing},9))
    cells={**primary,**secondary}
    v1_count=sum(1 for line in ledger.read_text().splitlines() if line.strip() and json.loads(line).get("grid_version",1)==1)
    data={"meta":{"grid_version":2,"prereg":"prereg.md","panel_days":len(P["days"]),"panel_first":str(P["days"][0]),"panel_last":str(P["days"][-1]),"phases":PHASES,"unique_trials":len(cells),"phase_jobs":len(cells)*3,"primary_family_cells":len(reg),"secondary_unique_cells":len(secondary),"workers":9,"engine":"app/rs_sl_engine.py","v1_trials":v1_count,"total_trials":v1_count+len(cells)},"baseline_id":base["id"],"selected":{"best_both":best_both["id"],"top3_both":[x["id"] for x in top3]},"cells":cells,"superseded_v1":"superseded_v1/results_v1.json"}
    out=OUT/"results_v2.json"
    out.write_text(json.dumps(data,indent=2,allow_nan=False,default=lambda x: x.item() if isinstance(x,np.generic) else str(x)))
    (OUT/"results.json").write_text(json.dumps(data,indent=2,allow_nan=False,default=lambda x: x.item() if isinstance(x,np.generic) else str(x)))
    print(json.dumps(data["meta"],indent=2)); print("SELECTED",json.dumps(data["selected"]))

if __name__=="__main__": main()
