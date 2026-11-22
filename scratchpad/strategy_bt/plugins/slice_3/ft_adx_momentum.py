import numpy as np,pandas as pd
SPEC_ID='ft_adx_momentum'; PARAMS={'adx_len':14,'di_len':25,'mom_len':14,'adx_min':25,'di_min':25,'stop':.25,'roi':.01}; PARAM_GRID={'adx_min':[20,25,30],'di_min':[20,25,30]}; TIMEFRAMES=['1h']; SIDES='long'
DEVIATIONS=['Time-zero 1% minimal ROI is represented as a fixed +1% target, not time-based candle ROI evaluation.','SAR is listed but unused by the spec rules and is not implemented.','Harness primary universe replaces the source universe.']
IMPLEMENTED_FIELDS=['entry_long','exit','stop_loss','take_profit','timeframes']
def _rma(x,n):
 o=np.full(len(x),np.nan)
 if len(x)>=n:
  o[n-1]=np.nanmean(x[:n])
  for i in range(n,len(x)):o[i]=o[i-1]+(x[i]-o[i-1])/n
 return o
def _di(df,n):
 h,l,c=[df[k].to_numpy(float) for k in ('high','low','close')]; u=np.r_[np.nan,np.diff(h)]; d=np.r_[np.nan,-np.diff(l)]; pc=np.r_[np.nan,c[:-1]]; tr=np.maximum.reduce([h-l,np.abs(h-pc),np.abs(l-pc)]); a=_rma(tr,n); p=100*_rma(np.where((u>d)&(u>0),u,0.),n)/a; m=100*_rma(np.where((d>u)&(d>0),d,0.),n)/a; dx=100*np.abs(p-m)/(p+m); return p,m,_rma(dx,n)
def signals(df,adx_len=14,di_len=25,mom_len=14,adx_min=25,di_min=25,stop=.25,roi=.01,**kw):
 p,m,_=_di(df,int(di_len)); _,_,a=_di(df,int(adx_len)); c=df.close.to_numpy(float); lag=np.full(len(c),np.nan); ml=int(mom_len)
 if ml<len(c): lag[ml:]=c[:-ml]
 mom=c-lag
 ent=(a>adx_min)&(mom>0)&(p>di_min)&(p>m); ex=(a>adx_min)&(mom<0)&(m>di_min)&(p<m)
 return pd.DataFrame({'long_entry':ent,'short_entry':False,'long_exit':ex,'short_exit':False,'stop_pct':float(stop),'tp_pct':float(roi)},index=df.index).fillna(False)
