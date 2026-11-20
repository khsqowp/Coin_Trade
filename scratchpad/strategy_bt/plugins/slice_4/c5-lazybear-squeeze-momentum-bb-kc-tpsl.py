import numpy as np,pandas as pd
from common.indicators import bollinger,sma
SPEC_ID='c5-lazybear-squeeze-momentum-bb-kc-tpsl'
PARAMS={'length':20,'bb_mult':2.0,'kc_mult':1.5,'tp':0.01,'sl':0.005}
PARAM_GRID={'length':[18,20,22]}; TIMEFRAMES=['1h','4h']; SIDES='both'
DEVIATIONS=['The archived default is logic type2: momentum turns up below zero for longs and down above zero for shorts; optional squeeze-off filtering is disabled.','The LazyBear momentum expression is implemented as rolling least-squares linear regression of close minus the specified midpoint baseline; the baseline uses highest(hl2), lowest(low), and SMA(hl2).','Engine evaluates fixed TP/SL against average fill price and cannot prioritize opposite signal over intrabar bracket fills.']
IMPLEMENTED_FIELDS=['entry_long','entry_short','exit','stop_loss','take_profit','filters','timeframes']
def _linreg_last(x,n):
 out=np.full(len(x),np.nan); xx=np.arange(n,dtype=float); xm=xx.mean(); den=((xx-xm)**2).sum()
 for i in range(n-1,len(x)):
  y=x[i-n+1:i+1]
  if np.isfinite(y).all(): out[i]=np.polyfit(xx,y,1)[0]*(n-1)+y.mean()
 return out
def signals(df,length=20,bb_mult=2.,kc_mult=1.5,tp=.01,sl=.005,**kw):
 n=int(length); c=df.close.to_numpy(float); h=df.high.to_numpy(float); l=df.low.to_numpy(float); hl2=(h+l)/2
 mid,up,dn=bollinger(c,n,float(bb_mult)); rang=sma(h-l,n); km=sma(hl2,n); ku=km+float(kc_mult)*rang; kl=km-float(kc_mult)*rang
 sq=(up<ku)&(dn>kl)
 base=(np.maximum.accumulate(np.lib.stride_tricks.sliding_window_view(hl2,n),axis=1)[:,-1] + np.minimum.accumulate(np.lib.stride_tricks.sliding_window_view(l,n),axis=1)[:,-1])/2 if len(c)>=n else np.array([])
 av=sma(hl2,n); b=np.full(len(c),np.nan); b[n-1:]=(base+av[n-1:])/2
 val=_linreg_last(c-b,n); prev=np.r_[np.nan,val[:-1]]; prev2=np.r_[np.nan,prev[:-1]]
 le=(val<0)&(val>prev)&(prev<=prev2); se=(val>0)&(val<prev)&(prev>=prev2); z=np.zeros(len(c),bool)
 return pd.DataFrame({'long_entry':le,'short_entry':se,'long_exit':se,'short_exit':le,'stop_pct':np.full(len(c),float(sl)),'tp_pct':np.full(len(c),float(tp))},index=df.index)
