import numpy as np
import pandas as pd
SPEC_ID="tv_dca_rsi_martingale"
PARAMS={"rsi_len":14,"rsi_level":30,"n_adds":5,"add_spacing_pct":5.0,"add_size_mult":1.5,"tp":0.03}
PARAM_GRID={"rsi_level":[25,30,35],"tp":[0.02,0.03,0.04]}; TIMEFRAMES=["1h","4h"]; SIDES="long"
DEVIATIONS=["Archived source is explicitly described as a lossy summary; implementation follows supplied RSI-crossunder and ladder rules.","Harness uses fixed base notional and each add is base*1.5 rather than compounding 1.5^k; spacing is from last fill.","No stop is specified; remaining martingale position is marked to final close by harness.","Harness ladder may execute add at an intrabar level without event ordering or liquidation modeling."]
IMPLEMENTED_FIELDS=["entry_long","exit","take_profit","position_sizing","timeframes"]
def _rsi(x,n):
    x=np.asarray(x,float); n=int(n); out=np.full(len(x),np.nan)
    if len(x)<=n:return out
    d=np.diff(x); g=np.maximum(d,0); loss=np.maximum(-d,0); ag=np.mean(g[:n]); al=np.mean(loss[:n])
    out[n]=100. if al==0 and ag>0 else (0. if ag==0 else 100-100/(1+ag/al))
    for i in range(n+1,len(x)):
        ag=(ag*(n-1)+g[i-1])/n; al=(al*(n-1)+loss[i-1])/n
        out[i]=100. if al==0 and ag>0 else (0. if ag==0 else 100-100/(1+ag/al))
    return out
def signals(df,rsi_len=14,rsi_level=30,n_adds=5,add_spacing_pct=5.,add_size_mult=1.5,tp=.03):
    r=_rsi(df.close,int(rsi_len)); prev=np.r_[np.nan,r[:-1]]; en=(r<float(rsi_level))&(prev>=float(rsi_level))
    return pd.DataFrame({"long_entry":en,"short_entry":False,"long_exit":False,"short_exit":False,"tp_pct":float(tp)},index=df.index).fillna(False)
