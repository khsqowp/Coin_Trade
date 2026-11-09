"""OOS 90-day block paths and paired bootstrap for the preregistered grid."""
import json, sys, time
from pathlib import Path
import numpy as np, pandas as pd
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[4]; sys.path.insert(0,str(ROOT/'trading'))
from rebal_C_engine import run

def main():
 t0=time.time(); rp=HERE/'results.json'; z=json.load(open(rp));
 scratch=Path(z['meta']['panel']); a=np.load(scratch,allow_pickle=True)
 days=pd.DatetimeIndex(a['days'],tz='UTC'); H=a['H'].astype(float); L=a['L'].astype(float); C=a['C'].astype(float); FD=a['FD'].astype(float)
 nd,_,n=C.shape; cf=C.reshape(nd*24,n); hf=H.reshape(nd*24,n); lf=L.reshape(nd*24,n)
 score=np.full_like(cf,np.nan); score[336:]=cf[336:]/cf[:-336]-1
 names=[str(x) for x in a['names']]; btc=names.index('BTC' if 'BTC' in names else 'BTCUSDT')
 dc=C[:,23,:]; br=np.full(nd,np.nan); br[14:]=dc[14:,btc]/dc[:-14,btc]-1; crash=(np.isfinite(br)&(br<-.10)).astype(np.uint8)
 start=int(z['meta']['is_end']); end=int(z['meta']['d1']); blocks=[]
 for lo in range(start,end-89,90): blocks.append((lo,lo+90))
 phase_by_p={x['period']:[v['phase'] for v in x['phases']] for x in z['grid'] if x['lambda_']==.15}
 out=[]
 for bi,(lo,hi) in enumerate(blocks):
  byp=[]
  for p in range(1,73):
   vals=[]
   offs=phase_by_p[p]
   for ph in offs:
    local_phase=(ph-(lo-start)*24)%p
    r=run(hf,lf,cf,FD,score,crash,p,local_phase,lo,hi,.15,0.,0.,20261101,True,True)
    vals.append(float(np.log(max(r[0],1e-12))*365/(hi-lo)))
   byp.append(vals)
  out.append(dict(start=str(days[lo].date()),end=str(days[hi-1].date()),annualized_log_growth=byp))
  print(f"BLOCK {bi+1}/{len(blocks)} {days[lo].date()}..{days[hi-1].date()}",flush=True)
 z['oos_90d_blocks']=dict(block_days=90,windows=out)
 rp.write_text(json.dumps(z,indent=2))
 print(f"DONE blocks={len(blocks)} seconds={time.time()-t0:.1f}",flush=True)
if __name__=='__main__': main()
