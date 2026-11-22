import numpy as np, pandas as pd
from common.indicators import ema
SPEC_ID="c5-ema-rainbow-10-20-50-100-150-200-stack"
PARAMS={"trail":.08}; PARAM_GRID={"trail":[.08]}
TIMEFRAMES=["1h","4h"]
SIDES="long"
DEVIATIONS=["The 8% stop is represented as a causal close signal below the ratcheting 8%-under-highest-close level; harness fills the following open, not an intrabar stop.","The source specifies default strategy sizing; harness fixed notional is used."]
IMPLEMENTED_FIELDS=["entry_long","exit","stop_loss","timeframes","filters"]
def signals(df,trail=.08,**kw):
 c=df.close.to_numpy(float); n=len(c); es={k:ema(c,k) for k in (5,10,20,50,100,150,200)}; stack=(es[10]>es[20])&(es[20]>es[50])&(es[100]>es[150])&(es[150]>es[200]); prev=np.r_[np.nan,c[:-1]]; e10p=np.r_[np.nan,es[10][:-1]]; e5p=np.r_[np.nan,es[5][:-1]]
 entry=stack&(((prev<=e10p)&(c>es[10]))|((prev>=e5p)&(c<es[5])))
 exit=np.zeros(n,bool); peak=-np.inf
 for i,x in enumerate(c):
  if entry[i]: peak=x
  elif peak!=-np.inf:
   peak=max(peak,x); exit[i]=x<=peak*(1-float(trail))
   if exit[i]: peak=-np.inf
 return pd.DataFrame({"long_entry":entry,"short_entry":False,"long_exit":exit,"short_exit":False},index=df.index).fillna(False)
