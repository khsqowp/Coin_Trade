"""Independent, deliberately small implementation of the archived strategy rules.

No imports from common/ or plugins/. Signals use only current/past OHLC observations.
Ambiguities resolved literally: BB uses population standard deviation; ROC is simple;
Donchian signals use prior-bar channels and the harness's fixed-notional fills.
"""
import numpy as np
import pandas as pd
from datetime import date, timedelta
from zoneinfo import ZoneInfo
from dateutil.easter import easter

FEE=.0004; SLIPPAGE=.0002; CAPITAL=10000.; NOTIONAL=1000.
IDS=['btc-max10-nyse-close','btc-bollinger-37-16','btc-ema-5-30','btc-roc-36-9pct','jesse_turtle','btc-macd-15-41-12','c4-ema-supertrend','c4-strategy-myth-busting-12-osgfc-supertrend-myn','turtle-system-1','btc-adx-di-24-9','turtle-system-2','jesse_simple_bollinger']
TF={'btc-max10-nyse-close':'15m','c4-ema-supertrend':'4h','c4-strategy-myth-busting-12-osgfc-supertrend-myn':'4h','jesse_simple_bollinger':'1h'}
SIDE={'btc-max10-nyse-close':'long','btc-bollinger-37-16':'long','btc-roc-36-9pct':'long','c4-ema-supertrend':'long','jesse_simple_bollinger':'long'}
PARAMS={'btc-max10-nyse-close':{'n':8},'btc-bollinger-37-16':{'k':1.4,'n':45},'btc-ema-5-30':{'fast':5,'slow':25},'btc-roc-36-9pct':{'n':36,'thr':.07},'jesse_turtle':{'atr_n':20,'entry':20,'exit':12,'stop_n':2.},'btc-macd-15-41-12':{'fast':18,'slow':47,'signal':12},'c4-ema-supertrend':{'len1':28,'len2':70,'len4':233},'c4-strategy-myth-busting-12-osgfc-supertrend-myn':{'extrasmthper':10,'factor':2.5,'smthper':10,'st_atr':10},'turtle-system-1':{'atr_n':20,'entry_n':15,'exit_n':10,'fallback_n':55,'stop_mult':2.},'btc-adx-di-24-9':{'adx_len':24,'adx_min':7},'turtle-system-2':{'entry_n':40,'exit_n':20,'n_len':20,'stop_n':2.},'jesse_simple_bollinger':{'base':26,'bb_k':2.5,'bb_len':25,'conv':9,'disp':26,'span_b':52}}

def ema(x,n): return pd.Series(np.asarray(x,float)).ewm(span=max(1,int(n)),adjust=False).mean().to_numpy()
def rma(x,n):
 x=np.asarray(x,float); out=np.full(len(x),np.nan); n=max(1,int(n))
 if len(x)>=n:
  out[n-1]=np.nanmean(x[:n])
  for i in range(n,len(x)): out[i]=out[i-1]+(x[i]-out[i-1])/n
 return out
def atr(df,n):
 h,l,c=[df[k].to_numpy(float) for k in ('high','low','close')]; pc=np.r_[c[0],c[:-1]]
 return rma(np.maximum.reduce([h-l,abs(h-pc),abs(l-pc)]),n)
def cross(a,b,up=True):
 a=np.asarray(a); b=np.asarray(b); z=np.zeros(len(a),bool)
 if len(a)>1: z[1:]=((a[1:]>b[1:])&(a[:-1]<=b[:-1])) if up else ((a[1:]<b[1:])&(a[:-1]>=b[:-1]))
 return z
def frame(df,le=None,se=None,lx=None,sx=None,**kw):
 def bits(v): return np.full(len(df),False if v is None else bool(v),dtype=bool) if v is None or isinstance(v,(bool,np.bool_)) else np.asarray(v,dtype=bool)
 d=pd.DataFrame({'long_entry':bits(le),'short_entry':bits(se),'long_exit':bits(lx),'short_exit':bits(sx)},index=df.index)
 for k,v in kw.items(): d[k]=v
 d[['long_entry','short_entry','long_exit','short_exit']]=d[['long_entry','short_entry','long_exit','short_exit']].fillna(False).astype(bool)
 return d

def sig_btc_max10_nyse_close(df,n=8):
 # Calendar rules mirror the spec's full-day US exchange closures; early closes are excluded.
 def nth(y,m,w,k):
  d=date(y,m,1);return d+timedelta(days=(w-d.weekday())%7+7*(k-1))
 def last(y,m,w):
  d=date(y+(m==12),m%12+1,1)-timedelta(days=1);return d-timedelta(days=(d.weekday()-w)%7)
 def holidays(y):
  fixed=[date(y,1,1),date(y,7,4),date(y,12,25)]+([date(y,6,19)] if y>=2022 else [])
  obs=[]
  for x in fixed: obs.append(x if x.month==1 and x.weekday()==5 else x+(timedelta(days=-1) if x.weekday()==5 else timedelta(days=1) if x.weekday()==6 else timedelta()))
  return set(obs+[nth(y,1,0,3),nth(y,2,0,3),easter(y)-timedelta(days=2),last(y,5,0),nth(y,9,0,1),nth(y,11,3,4)])
 times=pd.DatetimeIndex(df.index)+pd.Timedelta(minutes=15); loc=times.tz_convert('America/New_York'); entries=np.zeros(len(df),bool); exits=np.zeros(len(df),bool); vals=[]; ix=[]
 for i,t in enumerate(loc):
  d=t.date()
  if t.hour==16 and t.minute==0 and d.weekday()<5 and d not in holidays(d.year): vals.append(float(df.close.iloc[i]));ix.append(i)
 for j,i in enumerate(ix):
  if j+1>=int(n) and vals[j]>=max(vals[j-int(n)+1:j+1]):entries[i]=True
 for i,t in enumerate(loc):
  d=t.date()
  if t.hour==9 and t.minute==30 and d.weekday()<5 and d not in holidays(d.year):exits[i]=True
 return frame(df,entries,lx=exits)
def sig_btc_bollinger_37_16(df,n=45,k=1.4):
 c=df.close.to_numpy(float); s=pd.Series(c,index=df.index); m=s.rolling(int(n),min_periods=int(n)).mean().to_numpy(); sd=s.rolling(int(n),min_periods=int(n)).std(ddof=0).to_numpy(); u=m+float(k)*sd
 return frame(df,cross(c,u),lx=c<=m)
def sig_btc_ema_5_30(df,fast=5,slow=25):
 c=df.close.to_numpy(float); a,b=ema(c,fast),ema(c,slow); up=cross(a,b); dn=cross(a,b,False)
 # Keep the opposite entry alive one additional bar because the harness exits at next open.
 le=up.copy();se=dn.copy()
 if len(c)>1: le[1:]|=up[:-1]&~dn[1:];se[1:]|=dn[:-1]&~up[1:]
 return frame(df,le,se,dn,up)
def sig_btc_roc_36_9pct(df,n=36,thr=.07):
 c=df.close.to_numpy(float); roc=pd.Series(c,index=df.index)/pd.Series(c,index=df.index).shift(int(n))-1; return frame(df,roc>thr,lx=roc<=thr)
def sig_jesse_turtle(df,entry=20,exit=12,atr_n=20,stop_n=2.):
 h,l,c=df.high,df.low,df.close; up=h.shift().rolling(int(entry),min_periods=int(entry)).max(); dn=l.shift().rolling(int(entry),min_periods=int(entry)).min(); xu=h.shift().rolling(int(exit),min_periods=int(exit)).max(); xl=l.shift().rolling(int(exit),min_periods=int(exit)).min(); le=h>=up; se=l<=dn
 return frame(df,le,se,(l<=xl)|se,(h>=xu)|le,atr_stop=atr(df,atr_n)*float(stop_n))
def sig_btc_macd_15_41_12(df,fast=18,slow=47,signal=12):
 c=df.close.to_numpy(float); m=ema(c,fast)-ema(c,slow); s=ema(m,signal); up=cross(m,s); dn=cross(m,s,False); warm=np.arange(len(c))<int(slow)+int(signal); up[warm]=False;dn[warm]=False
 le=up.copy();se=dn.copy()
 if len(c)>1: le[1:]|=(up[:-1]&up[:-1])&~dn[1:];se[1:]|=(dn[:-1]&dn[:-1])&~up[1:]
 return frame(df,le,se,dn,up)
def sig_c4_ema_supertrend(df,len1=28,len2=70,len4=233):
 c=df.close.to_numpy(float); a,b,z=ema(c,len1),ema(c,len2),ema(c,len4); le=cross(a,b)|((c>a)&(c>b)&(a>b)&(c>z)); lx=cross(c,b,False); le[:int(len4)]=False; return frame(df,le,lx=lx)
def sig_c4_strategy_myth_busting_12_osgfc_supertrend_myn(df,smthper=10,extrasmthper=10,factor=2.5,st_atr=10):
 # The archive JSON does not encode filter equations, cross state, or TP/SL defaults.
 # Minimal literal proxy: smoothed close slope cross, with ATR trend gate; unresolved rules flagged in report.
 c=df.close.to_numpy(float); sm=ema(c,extrasmthper); up=cross(sm,np.r_[sm[0],sm[:-1]]); dn=cross(sm,np.r_[sm[0],sm[:-1]],False); return frame(df,up,dn,dn,up,tp_pct=np.full(len(c),1.0))
def sig_turtle_system_1(df,entry_n=15,exit_n=10,fallback_n=55,stop_mult=2.,atr_n=20):
 h,l,c=df.high,df.low,df.close; hh=h.shift().rolling(int(entry_n),min_periods=int(entry_n)).max(); ll=l.shift().rolling(int(entry_n),min_periods=int(entry_n)).min(); xh=h.shift().rolling(int(exit_n),min_periods=int(exit_n)).max(); xl=l.shift().rolling(int(exit_n),min_periods=int(exit_n)).min(); hf=h.shift().rolling(int(fallback_n),min_periods=int(fallback_n)).max(); lf=l.shift().rolling(int(fallback_n),min_periods=int(fallback_n)).min()
 return frame(df,(c>hh)|(c>hf),(c<ll)|(c<lf),c<xl,c>xh,atr_stop=atr(df,atr_n)*float(stop_mult))
def sig_btc_adx_di_24_9(df,adx_len=24,adx_min=7):
 h,l,c=[df[k].to_numpy(float) for k in ('high','low','close')]; up=np.r_[0,np.diff(h)]; dn=np.r_[0,-np.diff(l)]; p=np.where((up>dn)&(up>0),up,0.); m=np.where((dn>up)&(dn>0),dn,0.); pc=np.r_[c[0],c[:-1]]; tr=np.maximum.reduce([h-l,abs(h-pc),abs(l-pc)]); a=rma(tr,adx_len); p=100*rma(p,adx_len)/a; m=100*rma(m,adx_len)/a; dx=100*abs(p-m)/(p+m); adx=rma(dx,adx_len); bull=(p>m)&(adx>=adx_min); bear=(m>p)&(adx>=adx_min); return frame(df,bull,bear,~bull,~bear)
def sig_turtle_system_2(df,entry_n=40,exit_n=20,n_len=20,stop_n=2.):
 h,l,c=df.high,df.low,df.close; hh=h.shift().rolling(int(entry_n),min_periods=int(entry_n)).max();ll=l.shift().rolling(int(entry_n),min_periods=int(entry_n)).min();xh=h.shift().rolling(int(exit_n),min_periods=int(exit_n)).max();xl=l.shift().rolling(int(exit_n),min_periods=int(exit_n)).min();return frame(df,c>hh,c<ll,c<xl,c>xh,atr_stop=atr(df,n_len)*float(stop_n))
def sig_jesse_simple_bollinger(df,bb_len=25,bb_k=2.5,conv=9,base=26,span_b=52,disp=26):
 h,l,c=df.high,df.low,df.close; hl=(h+l)/2; s=pd.Series(hl,index=df.index); mid=s.rolling(int(bb_len),min_periods=int(bb_len)).mean(); u=mid+float(bb_k)*s.rolling(int(bb_len),min_periods=int(bb_len)).std(ddof=0); cv=(h.rolling(int(conv)).max()+l.rolling(int(conv)).min())/2; bv=(h.rolling(int(base)).max()+l.rolling(int(base)).min())/2; sa=((cv+bv)/2).shift(int(disp)); sb=((h.rolling(int(span_b)).max()+l.rolling(int(span_b)).min())/2).shift(int(disp)); return frame(df,(c>u)&(c>sa)&(c>sb),lx=c<mid)
SIGNALS={x:globals()['sig_'+x.replace('-','_')] for x in IDS}

def simulate(df,sig,side='both',fee=FEE,slippage=SLIPPAGE,capital=CAPITAL,notional=NOTIONAL):
 """Harness matching simulator; returned net is price PnL less entry/exit costs."""
 n=len(df); o,h,l,c=[df[x].to_numpy(float) for x in ('open','high','low','close')]; le=sig.long_entry.to_numpy(bool);se=sig.short_entry.to_numpy(bool);lx=sig.long_exit.to_numpy(bool);sx=sig.short_exit.to_numpy(bool); stop=np.asarray(sig['stop_pct'] if 'stop_pct' in sig else np.full(n,np.nan),float); ast=np.asarray(sig['atr_stop'] if 'atr_stop' in sig else np.full(n,np.nan),float); tp=np.asarray(sig['tp_pct'] if 'tp_pct' in sig else np.full(n,np.nan),float); mh=np.asarray(sig['max_hold'] if 'max_hold' in sig else np.full(n,np.nan),float)
 pos=0; trades=[]; cash=0.; ent=0; qty=avg=cost=0.; sd=np.nan;td=np.nan;hold=0
 def close(i,price,reason):
  nonlocal pos,cash,qty,avg,cost
  ep=price*(1-slippage if pos>0 else 1+slippage); net=(ep-avg)*qty*pos-cost-ep*qty*fee; trades.append({'symbol':'','side':'long' if pos>0 else 'short','entry':ent,'exit':i,'entry_time':str(df.index[ent]),'exit_time':str(df.index[i]),'entry_fill':avg,'exit_fill':ep,'qty':qty,'net':net,'pct':net/capital*100,'reason':reason}); cash+=net;pos=0;qty=avg=cost=0.
 for i in range(n):
  if pos:
   st=avg*(1-pos*sd) if np.isfinite(sd) else None; target=avg*(1+pos*td) if np.isfinite(td) and td>0 else None
   sh=st is not None and (l[i]<=st if pos>0 else h[i]>=st); th=target is not None and (h[i]>=target if pos>0 else l[i]<=target)
   if sh: close(i,o[i] if (o[i]<st if pos>0 else o[i]>st) else st,'stop');continue
   if th: close(i,o[i] if (o[i]>target if pos>0 else o[i]<target) else target,'tp');continue
   if (hold and i-ent>=hold) or (i>0 and (lx[i-1] if pos>0 else sx[i-1])): close(i,c[i] if hold and i-ent>=hold else o[i],'time' if hold and i-ent>=hold else 'signal');continue
  if not pos and i>0:
   d=1 if side!='short' and le[i-1] else (-1 if side!='long' and se[i-1] else 0)
   if d:
    pos=d;ent=i;avg=o[i]*(1+d*slippage);qty=notional/avg;cost=avg*qty*fee; sd=stop[i-1] if np.isfinite(stop[i-1]) else (ast[i-1]/avg if np.isfinite(ast[i-1]) else np.nan);td=tp[i-1];hold=int(mh[i-1]) if np.isfinite(mh[i-1]) and mh[i-1]>0 else int(0)
    st=avg*(1-d*sd) if np.isfinite(sd) else None;target=avg*(1+d*td) if np.isfinite(td) and td>0 else None
    if st is not None and (l[i]<=st if d>0 else h[i]>=st):close(i,o[i] if (o[i]<st if d>0 else o[i]>st) else st,'stop')
    elif target is not None and (h[i]>=target if d>0 else l[i]<=target):close(i,o[i] if (o[i]>target if d>0 else o[i]<target) else target,'tp')
 if pos:close(n-1,c[-1],'end_mark')
 for t in trades:t['symbol']=''
 return trades
