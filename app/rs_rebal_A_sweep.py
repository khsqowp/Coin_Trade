"""Preregistered offline cadence sweep. Writes bulk arrays only to RS_FINAL_SCRATCH/rebalA."""
import argparse, os, time
import numpy as np
import pandas as pd
from numba import set_num_threads
from app.rs_final_data import load_panel
from app.rs_final_engine import Sim
from app.rs_rebal_A_engine import run_batch

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--bench',action='store_true'); ap.add_argument('--gross',action='store_true'); a=ap.parse_args()
    set_num_threads(11)
    root=os.environ['RS_FINAL_SCRATCH']; out=os.path.join(root,'rebalA'); os.makedirs(out,exist_ok=True)
    P=load_panel(); sim=Sim(P); nd=sim.nd
    from app.rs_risk_load import load
    from app.rs_risk_engine import build_panel
    ohlc,fund=load(); raw=build_panel({k:v for k,v in ohlc.items() if k in sim.names},{k:v for k,v in fund.items() if k in sim.names})
    ri={n:i for i,n in enumerate(raw['names'])}; FH=np.zeros_like(sim.C)
    for j,n in enumerate(sim.names):
        if n in ri: FH[:,:,j]=sim.C[:,:,j]*raw['F'][:,:,ri[n]]
    err=float(np.nanmax(np.abs(np.nansum(FH,axis=1)-sim.FD)))
    if err>1e-10: raise RuntimeError(f'funding FD reconciliation failed: {err}')
    # Correct hourly 336h signal: daily close replication is not valid for sub-day decisions.
    hc=sim.C.reshape(nd*24,-1)
    mom=np.full_like(hc,np.nan); mom[336:]=hc[336:]/hc[:-336]-1
    ok=np.isfinite(mom); cnt=ok.sum(axis=1,keepdims=True)
    ranks=pd.DataFrame(mom).rank(axis=1).to_numpy()
    denom=np.sqrt(np.maximum((cnt*cnt-1)/12,1))
    score=(ranks-(cnt+1)/2)/denom; score[~ok]=np.nan
    btc=sim.names.index('BTC'); btc_mom=np.full(nd*24,np.nan); btc_mom[336:]=hc[336:,btc]/hc[:-336,btc]-1
    crash=np.isfinite(btc_mom)&(btc_mom<-.10)
    win={'IS':(sim.d_start('2022-01-01'),sim.d_start('2024-07-01')),
         'OOS':(sim.d_start('2024-07-01'),nd),
         'FULL':(sim.d_start('2022-01-01'),nd)}
    costs=[.0005+x/10000 for x in (0,2,5,10)]
    todo=[]
    if a.bench: todo=[('FULL',costs[0],0)]
    elif a.gross: todo=[(w,0.,r) for w in win for r in (0,1)]
    else:
        todo=[(w,c,r) for w,(c,_) in zip((),())] if False else [(w,c,r) for w in win for c in costs for r in (0,1)]
    manifest=[]
    for window,cost,resize in todo:
        d0,d1=win[window]; t=time.monotonic()
        rets,meta=run_batch(sim.H,sim.L,sim.C,FH,score,crash,d0,d1,cost,resize,0,4.,.95,8,.35,14,.005,1.)
        elapsed=time.monotonic()-t
        name=f'{window}_slip{round((cost-.0005)*10000):02d}_resize{resize}.npz'
        path=os.path.join(out,name); np.savez_compressed(path,rets=rets,meta=meta,d0=d0,d1=d1,cost=cost,resize=resize,window=window)
        manifest.append(f'{window} cost={cost:.5f} resize={resize} seconds={elapsed:.2f} file={name}')
        print('DONE',manifest[-1],flush=True)
    with open(os.path.join(out,'manifest.txt'),'a',encoding='utf-8') as f:
        f.write(f"run_utc={time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())} threads=11 funding_max_abs_error={err:.12g}\n")
        f.write('\n'.join(manifest)+'\n')
if __name__=='__main__': main()
