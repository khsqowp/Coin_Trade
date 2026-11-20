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
from common.indicators import sma
SPEC_ID="c5-sc-connors-rsi2-sma200-sma5"
PARAMS={"threshold":10}
PARAM_GRID={"threshold":[5,10]}
TIMEFRAMES=["1d"]
SIDES="both"
DEVIATIONS=["Daily stock/index rule applied to cached crypto daily bars because source instruments are absent.","The permitted next-open entry timing is used; close-known signals fill at the next bar open.","RSI(2) uses Wilder smoothing (EWM alpha=1/2, adjust=False); warmup outputs are excluded.","Source explicitly gives only a long SMA(5) exit. Short exit is mirrored as close below SMA(5) to make the stated symmetric short entry executable.","Harness universe is crypto majors, not stocks/ETFs; no discretionary optional trailing stop is added."]
IMPLEMENTED_FIELDS=["entry_long","entry_short","exit","filters","timeframes"]
def _rsi(x,n=2):
    d=np.diff(x,prepend=np.nan); gain=np.where(d>0,d,0.); loss=np.where(d<0,-d,0.)
    gain[0]=np.nan; loss[0]=np.nan
    ag=pd.Series(gain).ewm(alpha=1/n,adjust=False,min_periods=n).mean().to_numpy(); al=pd.Series(loss).ewm(alpha=1/n,adjust=False,min_periods=n).mean().to_numpy()
    rs=np.divide(ag,al,out=np.full(len(x),np.inf),where=al!=0); return 100-100/(1+rs)
def signals(df,threshold=10):
    c=df.close.to_numpy(float); fast=sma(c,5); slow=sma(c,200); r=_rsi(c,2)
    le=(c>slow)&(r<float(threshold)); se=(c<slow)&(r>100-float(threshold))
    lx=c>fast; sx=c<fast
    return _out(df,long_entry=le,short_entry=se,long_exit=lx,short_exit=sx)
