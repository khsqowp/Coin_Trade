import numpy as np
import pandas as pd
from common.indicators import ema,atr
SPEC_ID="tv_trend_pullback_ema21"
PARAMS={"ema_fast":21,"ema_mid":50,"ema_slow":200,"rsi_len":14,"atr_len":14,"sl_buf":0.5,"tp_r":2,"cooldown":8}
PARAM_GRID={"tp_r":[1,2,3]}; TIMEFRAMES=["1h","4h"]; SIDES="both"
DEVIATIONS=["The supplied specification treats TP1/TP2/TP3 as mutually exclusive single-target variants; harness cannot scale out.","Cooldown means no earlier same-side qualifying signal in the prior cooldown bars, excluding current bar.","Stop distance is computed from signal close although actual entry fills next open; per harness stop_pct is relative to actual fill, so risk distance varies with gap.","Archived TradingView artifact is an indicator and extracted rules are a lossy summary."]
IMPLEMENTED_FIELDS=["entry_long","entry_short","stop_loss","take_profit","filters","timeframes"]
def _rsi(x,n):
    x=np.asarray(x,float); n=int(n); out=np.full(len(x),np.nan)
    if len(x)<=n:return out
    d=np.diff(x); g=np.maximum(d,0); loss=np.maximum(-d,0); ag=np.mean(g[:n]); al=np.mean(loss[:n])
    out[n]=100. if al==0 and ag>0 else (0. if ag==0 else 100-100/(1+ag/al))
    for i in range(n+1,len(x)):
        ag=(ag*(n-1)+g[i-1])/n; al=(al*(n-1)+loss[i-1])/n
        out[i]=100. if al==0 and ag>0 else (0. if ag==0 else 100-100/(1+ag/al))
    return out
def signals(df,ema_fast=21,ema_mid=50,ema_slow=200,rsi_len=14,atr_len=14,sl_buf=.5,tp_r=2,cooldown=8):
    c=df.close.to_numpy(float); o=df.open.to_numpy(float); h=df.high.to_numpy(float); l=df.low.to_numpy(float)
    ef=ema(c,int(ema_fast)); em=ema(c,int(ema_mid)); es=ema(c,int(ema_slow)); r=_rsi(c,int(rsi_len)); a=atr(h,l,c,int(atr_len))
    long=(c>es)&(ef>em)&(l<=ef)&(c>ef)&(c>o)&(r>50)
    short=(c<es)&(ef<em)&(h>=ef)&(c<ef)&(c<o)&(r<50)
    n=len(c); cd=int(cooldown)
    # Causal prior-signal cooldown: reject if same-side qualifying condition occurred in preceding cd bars.
    if cd>0:
        lp=pd.Series(long.astype(int)).shift(1).rolling(cd,min_periods=1).sum().fillna(0).to_numpy()==0
        sp=pd.Series(short.astype(int)).shift(1).rolling(cd,min_periods=1).sum().fillna(0).to_numpy()==0
    else: lp=np.ones(n,bool); sp=np.ones(n,bool)
    long &= lp; short &= sp
    ls=l-float(sl_buf)*a; ss=h+float(sl_buf)*a
    lr=(c-ls)/c; sr=(ss-c)/c
    validl=np.isfinite(lr)&(lr>0); valids=np.isfinite(sr)&(sr>0)
    long &= validl; short &= valids
    stop=np.where(long,lr,np.where(short,sr,np.nan)); tp=np.where(long|short,stop*float(tp_r),np.nan)
    return pd.DataFrame({"long_entry":long,"short_entry":short,"long_exit":False,"short_exit":False,"stop_pct":stop,"tp_pct":tp},index=df.index).fillna({"long_entry":False,"short_entry":False,"long_exit":False,"short_exit":False})
