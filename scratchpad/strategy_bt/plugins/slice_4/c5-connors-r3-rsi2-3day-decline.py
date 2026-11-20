import numpy as np
import pandas as pd
from common.indicators import ema
SPEC_ID='c5-connors-r3-rsi2-3day-decline'
PARAMS={'rsi_len':2,'trend_len':200,'decline_n':3,'prior_max':60,'entry_max':10,'exit_level':70}
PARAM_GRID={'entry_max':[8,10,12]}
TIMEFRAMES=['1d']; SIDES='long'
DEVIATIONS=['Specification identifies daily ETFs, while the harness supplies crypto instruments; instrument universe is therefore generalized by the harness.','Wilder RSI is initialized with the first available simple-average gain/loss window. RSI crosses use prior RSI <= level and current RSI > level, the literal cross-up interpretation.','No stop or target is specified; positions remain open until the RSI exit or end of data.']
IMPLEMENTED_FIELDS=['entry_long','exit','filters','timeframes']
def _rsi(c,n):
 d=np.r_[np.nan,np.diff(c)]; g=np.where(d>0,d,0.); loss=np.where(d<0,-d,0.); out=np.full(len(c),np.nan)
 if len(c)>n:
  ag=np.nanmean(g[1:n+1]); al=np.nanmean(loss[1:n+1]); out[n]=100-100/(1+ag/al) if al else 100.
  for i in range(n+1,len(c)):
   ag=(ag*(n-1)+g[i])/n; al=(al*(n-1)+loss[i])/n; out[i]=100-100/(1+ag/al) if al else 100.
 return out
def signals(df,rsi_len=2,trend_len=200,decline_n=3,prior_max=60,entry_max=10,exit_level=70,**kw):
 c=df.close.to_numpy(float); r=_rsi(c,int(rsi_len)); e=ema(c,int(trend_len)); n=int(decline_n); le=np.zeros(len(c),bool)
 if len(c)>n: le[n:]=(c[n:]>e[n:])&(r[n:]<float(entry_max))&(r[:-n]<float(prior_max))&(r[n:]<r[n-1:-1])&(r[n-1:-1]<r[n-2:-2])&(r[n-2:-2]<r[n-3:-3])
 # Three consecutive declines: today < yesterday < two days ago < three days ago.
 lx=np.zeros(len(c),bool)
 if len(c)>1: lx[1:]=(r[1:]>float(exit_level))&(r[:-1]<=float(exit_level))
 z=np.zeros(len(c),bool)
 return pd.DataFrame({'long_entry':le,'short_entry':z,'long_exit':lx,'short_exit':z},index=df.index)
