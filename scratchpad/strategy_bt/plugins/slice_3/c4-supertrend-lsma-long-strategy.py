import numpy as np,pandas as pd
SPEC_ID='c4-supertrend-lsma-long-strategy'; PARAMS={'atr_period':14,'factor':3.0,'lsma_len':101}; PARAM_GRID={'factor':[2.,3.,4.],'lsma_len':[75,101,150]}; TIMEFRAMES=['1h','4h']; SIDES='long'
DEVIATIONS=['Source date range 2010-2021 is ignored.','Harness applies strategy to its primary universe; source has no fixed instrument.','Pine supertrend direction/band initialization is approximated with first valid ATR bar as the initial trend state.']
IMPLEMENTED_FIELDS=['entry_long','exit','filters','timeframes']
def _atr(h,l,c,n):
 pc=np.r_[np.nan,c[:-1]]; tr=np.maximum.reduce([h-l,np.abs(h-pc),np.abs(l-pc)]); o=np.full(len(c),np.nan)
 if len(c)>=n:
  o[n-1]=np.nanmean(tr[:n])
  for i in range(n,len(c)):o[i]=o[i-1]+(tr[i]-o[i-1])/n
 return o
def _lsma(x,n):
 out=np.full(len(x),np.nan); t=np.arange(n,dtype=float); denom=((t-t.mean())**2).sum(); w=(t-t.mean())/denom
 for i in range(n-1,len(x)):
  y=x[i-n+1:i+1]; out[i]=y.mean()+np.dot(w,y)*(n-1-t.mean())
 return out
def signals(df,atr_period=14,factor=3.,lsma_len=101,**kw):
 h,l,c=[df[k].to_numpy(float) for k in ('high','low','close')]; a=_atr(h,l,c,int(atr_period)); mid=(h+l)/2; up=mid+float(factor)*a; dn=mid-float(factor)*a; fu=up.copy(); fd=dn.copy(); direction=np.ones(len(c),int)
 for i in range(1,len(c)):
  if not np.isfinite(a[i]): continue
  if np.isfinite(a[i-1]):
   fu[i]=up[i] if (up[i]<fu[i-1] or c[i-1]>fu[i-1]) else fu[i-1]; fd[i]=dn[i] if (dn[i]>fd[i-1] or c[i-1]<fd[i-1]) else fd[i-1]
   direction[i]=(-1 if c[i]>fu[i-1] else 1) if direction[i-1]>0 else (1 if c[i]<fd[i-1] else -1)
  else: direction[i]=1
 ls=_lsma(c,int(lsma_len)); ch=np.r_[False,direction[1:]!=direction[:-1]]; prev=np.r_[direction[0],direction[:-1]]; entry=ch&(direction<0)&(c>ls); ex=ch&(prev<0)&(direction>0)
 return pd.DataFrame({'long_entry':entry,'short_entry':False,'long_exit':ex,'short_exit':False},index=df.index).fillna(False)
