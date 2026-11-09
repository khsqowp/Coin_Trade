"""Kill-free constant-notional diagnostic, OOS only; no compound-sized entries."""
import json,sys,time
from pathlib import Path
import numpy as np,pandas as pd
HERE=Path(__file__).resolve().parent; ROOT=HERE.parents[4]; sys.path.insert(0,str(ROOT/'trading'))
from rebal_C_engine import run

def main():
 t0=time.time(); rp=HERE/'results.json'; z=json.load(open(rp)); a=np.load(Path(z['meta']['panel']),allow_pickle=True)
 days=pd.DatetimeIndex(a['days'],tz='UTC'); H=a['H'].astype(float); L=a['L'].astype(float); C=a['C'].astype(float); FD=a['FD'].astype(float)
 nd,_,n=C.shape; cf=C.reshape(nd*24,n); hf=H.reshape(nd*24,n); lf=L.reshape(nd*24,n); score=np.full_like(cf,np.nan); score[336:]=cf[336:]/cf[:-336]-1
 names=[str(x) for x in a['names']]; btc=names.index('BTC' if 'BTC' in names else 'BTCUSDT'); dc=C[:,23,:]; br=np.full(nd,np.nan); br[14:]=dc[14:,btc]/dc[:-14,btc]-1; crash=(np.isfinite(br)&(br<-.10)).astype(np.uint8)
 start=int(z['meta']['is_end']); end=int(z['meta']['d1']); out=[]
 for p in range(1,73):
  phases=list(range(p)) if p<8 else sorted(set(int(round(k*(p-1)/7)) for k in range(8))); vals=[]
  for ph in phases:
   r=run(hf,lf,cf,FD,score,crash,p,ph,start,end,.15,0.,0.,20261101,True,False,True)
   vals.append(dict(phase=ph,final=float(r[0]),mdd=float(r[1]),kills=int(r[2]),rebals=int(r[3]),attempts=int(r[4]),min_cushion=float(r[6])))
  out.append(dict(period=p,phases=vals))
  if p%12==0: print(f"FIXED_GRID p={p}",flush=True)
 z['oos_kill_free_fixed_exposure']=dict(initial_gross_notional=3.8,fee_per_side=.0005,windows=out)
 rp.write_text(json.dumps(z,indent=2)); print(f"DONE seconds={time.time()-t0:.1f}",flush=True)
if __name__=='__main__': main()
