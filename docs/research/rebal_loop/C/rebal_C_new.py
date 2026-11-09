"""Separate historical NEW PIT cadence grid; not pooled with OLD IS/OOS."""
import json,sys,time
from pathlib import Path
import numpy as np,pandas as pd
HERE=Path(__file__).resolve().parent; ROOT=HERE.parents[4]; sys.path.insert(0,str(ROOT/'trading'))
from rebal_C_engine import run

def main():
 t0=time.time(); rp=HERE/'results.json'; result=json.load(open(rp)); pth=ROOT/'trading/docs/research/lev_loop/R2C/data/new_panel_2020_2021.npz'; z=np.load(pth,allow_pickle=True)
 days=pd.DatetimeIndex(z['days'],tz='UTC'); H=z['H'].astype(float); L=z['L'].astype(float); C=z['C'].astype(float); FD=z['FD'].astype(float); member=z['member'].astype(bool)
 nd,_,n=C.shape; cf=C.reshape(nd*24,n); hf=H.reshape(nd*24,n); lf=L.reshape(nd*24,n); score=np.full_like(cf,np.nan); score[336:]=cf[336:]/cf[:-336]-1
 score[~np.repeat(member,24,axis=0)]=np.nan
 names=[str(x) for x in z['names']]; btc=names.index('BTC' if 'BTC' in names else 'BTCUSDT'); dc=C[:,23,:]; br=np.full(nd,np.nan); br[14:]=dc[14:,btc]/dc[:-14,btc]-1; crash=(np.isfinite(br)&(br<-.10)).astype(np.uint8)
 start=int(days.searchsorted(pd.Timestamp('2020-03-01',tz='UTC'))); end=int(days.searchsorted(pd.Timestamp('2022-01-01',tz='UTC'))); grid=[]
 for lam in (0.,.15,.30):
  for period in range(1,73):
   phases=list(range(period)) if period<8 else sorted(set(int(round(k*(period-1)/7)) for k in range(8))); reps=[]
   for ph in phases:
    a=run(hf,lf,cf,FD,score,crash,period,ph,start,end,lam,0.,0.,20261101,True,True)
    reps.append(dict(phase=ph,final=float(a[0]),mdd=float(a[1]),kills=int(a[2]),rebals=int(a[3]),attempts=int(a[4]),min_cushion=float(a[6])))
   grid.append(dict(lambda_=lam,period=period,phases=reps))
   if period%12==0: print(f"NEW lambda={lam:.2f} p={period}",flush=True)
 result['new_historical_sample']=dict(panel=str(pth),range=[str(days[start].date()),str(days[end-1].date())],symbols=n,period_days=end-start,not_pooled_with_old=True,grid=grid)
 rp.write_text(json.dumps(result,indent=2)); print(f"DONE NEW seconds={time.time()-t0:.1f}",flush=True)
if __name__=='__main__': main()
