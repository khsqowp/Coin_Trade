import numpy as np, pandas as pd
SPEC_ID='btc-adx-di-24-9'; PARAMS={'adx_len':24,'adx_min':9}; PARAM_GRID={'adx_len':[18,24,30],'adx_min':[7,9,11]}; TIMEFRAMES=['1d']; SIDES='both'
DEVIATIONS=['Instrument list BTC is ignored; harness evaluates its primary universe.','Direction reversal exits at next open; engine cannot reverse and re-enter on the same bar.']
IMPLEMENTED_FIELDS=['entry_long','entry_short','exit','filters','timeframes']
def _rma(x,n):
 x=np.asarray(x,float); o=np.full(len(x),np.nan)
 if len(x)>=n:
  o[n-1]=np.nanmean(x[:n])
  for i in range(n,len(x)): o[i]=o[i-1]+(x[i]-o[i-1])/n
 return o
def _di(df,n):
 h,l,c=[df[k].to_numpy(float) for k in ('high','low','close')]; up=np.r_[np.nan,np.diff(h)]; dn=np.r_[np.nan,-np.diff(l)]; plus=np.where((up>dn)&(up>0),up,0.); minus=np.where((dn>up)&(dn>0),dn,0.); pc=np.r_[np.nan,c[:-1]]; tr=np.maximum.reduce([h-l,np.abs(h-pc),np.abs(l-pc)]); a=_rma(tr,n); p=100*_rma(plus,n)/a; m=100*_rma(minus,n)/a; dx=100*np.abs(p-m)/(p+m); return p,m,_rma(dx,n)
def signals(df,adx_len=24,adx_min=9,**kw):
 p,m,a=_di(df,int(adx_len)); bull=(p>m)&(a>=adx_min); bear=(m>p)&(a>=adx_min)
 return pd.DataFrame({'long_entry':bull,'short_entry':bear,'long_exit':~bull,'short_exit':~bear},index=df.index).fillna(False)
