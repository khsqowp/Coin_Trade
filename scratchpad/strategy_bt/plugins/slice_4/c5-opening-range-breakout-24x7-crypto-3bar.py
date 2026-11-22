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
SPEC_ID="c5-opening-range-breakout-24x7-crypto-3bar"
PARAMS={"range_bars":3,"min_volume_x":1.0}
PARAM_GRID={"range_bars":[2,3,4],"min_volume_x":[0.9,1.0,1.1]}
TIMEFRAMES=["1h","4h"]
SIDES="both"
DEVIATIONS=["Source's externally reset window is interpreted as each UTC calendar day; its default 5m data is unavailable, so cached 1h and 4h bars are used.","Opening range is the first range_bars bars of each UTC day; entries may occur only after all range bars have completed.","Volume filter compares breakout bar volume to mean volume of range bars, matching the summarized range-volume average.","Harness timestamp reset is repaired from cached BTCUSDT timeframe index; first partial day in TEST lacks earlier window bars.","Harness fixes stop and target at next-open entry from per-bar fractions; midpoint distance and 2R fractions are estimated from signal-bar close, so gaps from close to next open alter realized R.","Source's crypto futures universe is approximated by harness crypto spot-like OHLCV data; funding, liquidation, and contract mechanics are absent."]
IMPLEMENTED_FIELDS=["entry_long","entry_short","exit","stop_loss","take_profit","timeframes"]
def signals(df,range_bars=3,min_volume_x=1.0):
    idx=_utc_index(df); day=idx.normalize(); n=len(df)
    op=df.open.to_numpy(float); hi=df.high.to_numpy(float); lo=df.low.to_numpy(float); cl=df.close.to_numpy(float); vol=df.volume.to_numpy(float)
    pos=pd.Series(np.arange(n),index=idx).groupby(day).cumcount().to_numpy()
    dh=pd.Series(hi,index=idx).groupby(day).transform(lambda s:s.iloc[:int(range_bars)].max()).to_numpy()
    dl=pd.Series(lo,index=idx).groupby(day).transform(lambda s:s.iloc[:int(range_bars)].min()).to_numpy()
    # Daily range-volume mean, broadcast causally; first N bars are known before subsequent bars.
    rv=np.full(n,np.nan)
    for d in pd.unique(day):
        ix=np.flatnonzero(day==d); k=min(int(range_bars),len(ix)); avg=np.mean(vol[ix[:k]]) if k else np.nan; rv[ix]=avg
    valid=(pos>=int(range_bars))&(vol>=float(min_volume_x)*rv)
    le=valid&(cl>dh); se=valid&(cl<dl)
    mid=(dh+dl)/2; longrisk=np.divide(cl-mid,cl,out=np.zeros(n),where=cl!=0); shortrisk=np.divide(mid-cl,cl,out=np.zeros(n),where=cl!=0)
    le &= longrisk>0; se &= shortrisk>0
    stop=np.where(le,longrisk,np.where(se,shortrisk,np.nan)); tp=2*stop
    return _out(df,long_entry=le,short_entry=se,long_exit=np.zeros(n,bool),short_exit=np.zeros(n,bool),stop_pct=stop,tp_pct=tp)
