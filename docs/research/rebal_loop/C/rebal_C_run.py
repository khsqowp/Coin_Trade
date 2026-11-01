"""Run preregistered offline cadence grid against the local OLD hourly panel."""
from __future__ import annotations

import json, os, sys, time
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
TRADING = ROOT / "trading"
sys.path.insert(0, str(TRADING))
from app import rs_lev_r2c_data as D
from app import rs_lev_r2c_engine as R2C
from rebal_C_engine import run

SCRATCH = Path("/private/tmp/claude-501/-Users-user-Desktop-CODE-Ochestration/b40d7700-4bab-493b-9b2c-b8bac464cd8e/scratchpad/panel")
OUT = HERE / "results.json"
LOG = HERE / "run.log"

def log(msg):
    print(msg, flush=True)
    with LOG.open("a", encoding="utf8") as f: f.write(msg+"\n")

def main():
    tstart=time.time()
    if LOG.exists(): LOG.unlink()
    p=SCRATCH/"rs_final_panel.npz"
    z=np.load(p,allow_pickle=True)
    days=pd.DatetimeIndex(z["days"],tz="UTC")
    H=z["H"].astype(np.float64); L=z["L"].astype(np.float64); C=z["C"].astype(np.float64); FD=z["FD"].astype(np.float64)
    names=[str(x) for x in z["names"]]
    nd,nh,n=C.shape
    log(f"PANEL old_survivor names={n} days={nd} hours_per_day={nh} range={days[0].date()}..{days[-1].date()}")
    # Exact hourly close return input; score uses only information available at each bar close.
    CF=C.reshape(nd*24,n); HF=H.reshape(nd*24,n); LF=L.reshape(nd*24,n)
    score=np.full_like(CF,np.nan)
    score[336:]=CF[336:]/CF[:-336]-1.0
    btc=names.index("BTC" if "BTC" in names else "BTCUSDT")
    daily_close=C[:,23,:]
    bret=np.full(nd,np.nan); bret[14:]=daily_close[14:,btc]/daily_close[:-14,btc]-1.0
    crash=(np.isfinite(bret)&(bret<-.10)).astype(np.uint8)
    d0=int(days.searchsorted(pd.Timestamp("2022-01-01",tz="UTC")))
    is1=int(days.searchsorted(pd.Timestamp("2024-07-01",tz="UTC")))
    d1=nd
    log(f"WINDOW IS={days[d0].date()}..{days[is1-1].date()} OOS={days[is1].date()}..{days[d1-1].date()} flash_2025-10-10_in_panel={bool(days[0] <= pd.Timestamp('2025-10-10',tz='UTC') <= days[-1])}")
    log(f"ENGINE numba={__import__('numba').__version__}; prereg phases=8; lambda=0/.15/.30; fee=5bp/side; slip=0; failure=0")

    # Matched R2C V0 72h parity: daily close (phase 23), same OLD panel / interval / kill fidelity.
    S=dict(names=names,days=days,H=H,L=L,C=C,FD=FD,member=np.ones((nd,n),bool))
    sc_daily=D.scores(S); cr_daily=D.crash(S); r1=D.r1_vec(names)
    jcd=np.zeros((1,R2C.MAXK),np.int64); jph=np.zeros_like(jcd)
    evd=-np.ones((1,n),np.int64); evml=np.ones((1,n)); evms=np.ones((1,n)); cm=np.ones((1,n),np.uint8)
    d0par=d0; d1par=d1
    par=R2C.make_par(lev=4.,dep=.95,kill=.35,lam=.15,hourly=1,cool=14,cost=.0005,K=8,rebal=3,phase=0,d0=d0par,d1=d1par)[None,:]
    ro,_,req,_=R2C.run_batch(H,L,C,FD,sc_daily,cr_daily,r1,cm,par,jcd,jph,evd,evml,evms,True)
    legacy=float(ro[0,R2C.O_FINAL]); legacy_kills=float(ro[0,R2C.O_KILLS])
    ours=run(HF,LF,CF,FD,score,crash,72,23,d0,d1,.15,0.,0.,20261101,False,True)
    parity=dict(r2c_final=legacy,hourly_final=float(ours[0]),relative_error=float((ours[0]-legacy)/max(abs(legacy),1e-12)),r2c_kills=legacy_kills,hourly_kills=int(ours[2]),r2c_gross_note="V0 kept-quantity R2C; daily funding timestamp and kill settlement semantics aligned in final attempt; residual path mismatch remains unexplained")
    log("PARITY "+json.dumps(parity,sort_keys=True))

    allres=[]
    # Fixed eight phase offsets, repeated by cadence; phase 23 is included where possible for daily-close alignment.
    for lam in (0.0,.15,.30):
      for period in range(1,73):
        if period<8: phases=list(range(period))
        else: phases=sorted(set(int(round(k*(period-1)/7)) for k in range(8)))
        # Make the baseline phase grid identical across paired cadence paths through deterministic phase indices.
        vals=[]
        for ix,ph in enumerate(phases):
          ans=run(HF,LF,CF,FD,score,crash,period,ph,d0,d1,lam,0.,0.,20261101,True,True)
          ais=run(HF,LF,CF,FD,score,crash,period,ph,d0,is1,lam,0.,0.,20261101,True,True)
          aoos=run(HF,LF,CF,FD,score,crash,period,ph,is1,d1,lam,0.,0.,20261101,True,True)
          vals.append(dict(phase=ph,final=float(ans[0]),mdd=float(ans[1]),kills=int(ans[2]),rebals=int(ans[3]),attempts=int(ans[4]),failures=int(ans[5]),min_cushion=float(ans[6]),worst_wick_eq=float(ans[7]),is_final=float(ais[0]),is_mdd=float(ais[1]),is_kills=int(ais[2]),oos_final=float(aoos[0]),oos_mdd=float(aoos[1]),oos_kills=int(aoos[2]),oos_rebals=int(aoos[3]),oos_attempts=int(aoos[4])))
        allres.append(dict(lambda_=lam,period=period,phases=vals))
        if period%6==0 or period==1 or period==72:
          log(f"GRID lambda={lam:.2f} p={period:02d} phases={len(vals)} mean_final={np.mean([v['final'] for v in vals]):.5g} mean_MDD={np.mean([v['mdd'] for v in vals]):.4f}")
    # Pre-fixed OOS sensitivity subset: execution friction combinations at 6 cadence anchors.
    sens=[]
    for period in (1,6,12,24,48,72):
      phases=list(range(period)) if period<8 else sorted(set(int(round(k*(period-1)/7)) for k in range(8)))
      for slip in (0.,2.,5.,10.):
       for fail in (0.,.02,.05):
        outcomes=[]
        for ph in phases:
          ans=run(HF,LF,CF,FD,score,crash,period,ph,is1,d1,.15,slip,fail,20261101,True,True)
          outcomes.append(dict(phase=ph,final=float(ans[0]),mdd=float(ans[1]),kills=int(ans[2]),rebals=int(ans[3]),attempts=int(ans[4]),failures=int(ans[5]),min_cushion=float(ans[6])))
        sens.append(dict(period=period,slippage_bp=slip,fill_failure=fail,phases=outcomes))
      log(f"SENS p={period:02d} finished scenarios=12")
    result=dict(meta=dict(panel=str(p),range=[str(days[0].date()),str(days[-1].date())],n_symbols=n,d0=d0,is_end=is1,d1=d1,fee_per_side=.0005,slippage_bp=0,fill_failure=0,phase_rule="8 evenly spaced integer offsets; all offsets if period<8",seed=20261101),parity=parity,grid=allres,cost_failure_sensitivity_oos=sens)
    OUT.write_text(json.dumps(result,indent=2),encoding="utf8")
    log(f"DONE seconds={time.time()-tstart:.1f} result={OUT}")

if __name__=="__main__": main()
