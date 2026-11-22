from pathlib import Path
import numpy as np
import pandas as pd

def _utc_index(df):
    idx=df.index
    if isinstance(idx,pd.DatetimeIndex): return idx.tz_localize("UTC") if idx.tz is None else idx.tz_convert("UTC")
    n=len(df); here=Path(__file__).resolve()
    for base in here.parents:
        data=base/"bb_stoch_stc"/"data"
        if not data.is_dir(): data=base.parent/"bb_stoch_stc"/"data"
        if data.is_dir(): break
    else: raise RuntimeError("cannot locate bb_stoch_stc/data to restore timestamps")
    for tf in ("1d","1h","4h"):
        path=data/f"BTCUSDT_{tf}.parquet"
        if not path.exists(): continue
        ref=pd.read_parquet(path,columns=["close"]).index; k=int(len(ref)*.6)
        for length,part in ((len(ref),ref),(k,ref[:k]),(len(ref)-k,ref[k:])):
            if n==length: return pd.DatetimeIndex(part)
    raise ValueError("UTC index removed and slice length not recognized")

def _out(df,**cols):
    out=pd.DataFrame(cols,index=df.index)
    for name in ("long_entry","short_entry","long_exit","short_exit"):
        if name in out: out[name]=out[name].fillna(False).astype(bool)
    return out
SPEC_ID="c5-strat-inside-outside-bar-3pct-1pct"
PARAMS={"tp":0.03,"sl":0.01}
PARAM_GRID={"tp":[0.025,0.03,0.035],"sl":[0.008,0.01,0.012]}
TIMEFRAMES=["1d"]
SIDES="both"
DEVIATIONS=["Daily crypto is followed from the spec description; current bar's close-confirmed directional break is emitted as a signal and fills at next open, approximating the source buy/sell stop.","A previous bar qualifies when it is strictly inside or strictly outside the bar before it, using the stated inequalities.","Source's stop entry at current close conflicts with next-open harness execution; signal contract is followed.","Harness checks stop and target from next-open fill and cannot retain a signal-bar stop entry price.","Harness universe is major crypto bars; archived instrument-specific details are unavailable."]
IMPLEMENTED_FIELDS=["entry_long","entry_short","stop_loss","take_profit","timeframes"]
def signals(df,tp=.03,sl=.01):
    o=df.open.to_numpy(float); h=df.high.to_numpy(float); l=df.low.to_numpy(float); c=df.close.to_numpy(float); n=len(c)
    inside=np.zeros(n,bool); outside=np.zeros(n,bool)
    if n>2:
        inside[1:-1]=(h[1:-1]<h[:-2])&(l[1:-1]>l[:-2])
        outside[1:-1]=(h[1:-1]>h[:-2])&(l[1:-1]<l[:-2])
    setup=np.r_[False,inside[:-1]|outside[:-1]]
    le=setup&(c>o)&(h>np.r_[np.nan,h[:-1]])
    se=setup&(c<o)&(l<np.r_[np.nan,l[:-1]])
    return _out(df,long_entry=le,short_entry=se,long_exit=np.zeros(n,bool),short_exit=np.zeros(n,bool),stop_pct=np.full(n,float(sl)),tp_pct=np.full(n,float(tp)))
