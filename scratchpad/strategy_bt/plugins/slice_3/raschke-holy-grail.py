import numpy as np,pandas as pd
from common.indicators import ema
SPEC_ID='raschke-holy-grail'; PARAMS={'adx_len':14,'adx_min':30,'ema_len':20,'max_hold':10,'swing_n':20}; PARAM_GRID={'adx_min':[25,30,35],'ema_len':[15,20,25]}; TIMEFRAMES=['1d']; SIDES='both'
DEVIATIONS=['Engine cannot represent a buy/sell stop valid only intrabar on the setup-following bar; approximates trigger with next bar close crossing setup high/low, then fills following open.','If swing objective is already passed or nonpositive at signal close, take-profit is omitted.','Instrument list is generalized by harness to its primary universe.']
IMPLEMENTED_FIELDS=['entry_long','entry_short','exit','stop_loss','take_profit','filters','timeframes']
def _rma(x,n):
 o=np.full(len(x),np.nan)
 if len(x)>=n:
  o[n-1]=np.nanmean(x[:n])
  for i in range(n,len(x)):o[i]=o[i-1]+(x[i]-o[i-1])/n
 return o
def _dmi(df,n):
 h,l,c=[df[k].to_numpy(float) for k in ('high','low','close')]; u=np.r_[np.nan,np.diff(h)]; d=np.r_[np.nan,-np.diff(l)]; pc=np.r_[np.nan,c[:-1]]; tr=np.maximum.reduce([h-l,np.abs(h-pc),np.abs(l-pc)]); a=_rma(tr,n); p=100*_rma(np.where((u>d)&(u>0),u,0.),n)/a; m=100*_rma(np.where((d>u)&(d>0),d,0.),n)/a; dx=100*np.abs(p-m)/(p+m); return p,m,_rma(dx,n)
def signals(df,adx_len=14,adx_min=30,ema_len=20,max_hold=10,swing_n=20,**kw):
 n=len(df); h=df.high.to_numpy(float); l=df.low.to_numpy(float); c=df.close.to_numpy(float); p,m,a=_dmi(df,int(adx_len)); e=ema(c,int(ema_len)); prevc=np.r_[np.nan,c[:-1]]; preve=np.r_[np.nan,e[:-1]]; rising=np.r_[False,a[1:]>a[:-1]]
 setupL=(a>adx_min)&rising&(p>m)&(prevc>preve)&(l<=e); setupS=(a>adx_min)&rising&(m>p)&(prevc<preve)&(h>=e)
 le=np.zeros(n,bool); se=le.copy(); sl=np.full(n,np.nan); tp=np.full(n,np.nan); mh=np.full(n,np.nan); sh=max(1,int(swing_n))
 if n>1:
  le[1:]=setupL[:-1]&(c[1:]>h[:-1]); se[1:]=setupS[:-1]&(c[1:]<l[:-1]); sl[1:]=(c[1:]-l[:-1])/c[1:]; sl[1:]=np.where((sl[1:]<=0),np.nan,sl[1:]); tpL=(pd.Series(h,index=df.index).rolling(sh,min_periods=sh).max().to_numpy()-c)/c; tpS=(c-pd.Series(l,index=df.index).rolling(sh,min_periods=sh).min().to_numpy())/c; tp[1:]=np.where(le[1:],tpL[1:],tpS[1:]); tp=np.where(tp>0,tp,np.nan); mh[le|se]=int(max_hold); le &= np.isfinite(sl); se &= np.isfinite(sl)
 return pd.DataFrame({'long_entry':le,'short_entry':se,'long_exit':False,'short_exit':False,'stop_pct':sl,'tp_pct':tp,'max_hold':mh},index=df.index).fillna({'long_entry':False,'short_entry':False,'long_exit':False,'short_exit':False})
