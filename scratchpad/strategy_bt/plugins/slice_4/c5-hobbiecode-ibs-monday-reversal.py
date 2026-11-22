from pathlib import Path
import numpy as np
import pandas as pd

_DAILY_CACHE={}

def _utc_index(df):
    idx=df.index
    if isinstance(idx,pd.DatetimeIndex): return idx.tz_localize("UTC") if idx.tz is None else idx.tz_convert("UTC")
    here=Path(__file__).resolve()
    data=next((parent/"bb_stoch_stc"/"data" for parent in here.parents if (parent/"bb_stoch_stc"/"data").is_dir()),None)
    if data is None: raise RuntimeError("cannot locate bb_stoch_stc/data to restore timestamps")
    n=len(df)
    if n==0: return pd.DatetimeIndex([],tz="UTC")
    # Match observed OHLC values to a contiguous cached interval. This
    # also handles the short arbitrary prefixes used by the causal harness.
    price_cols=("open","high","low","close")
    if all(col in df for col in price_cols):
        for path in sorted(data.glob("*_1d.parquet")):
            key=str(path)
            if key not in _DAILY_CACHE: _DAILY_CACHE[key]=pd.read_parquet(path)
            ref=_DAILY_CACHE[key]; closes=ref.close.to_numpy()
            if len(closes)<n: continue
            starts=np.flatnonzero(closes[:len(closes)-n+1]==df.close.to_numpy()[0])
            for start in starts:
                if all(np.array_equal(ref[col].to_numpy()[start:start+n],df[col].to_numpy(),equal_nan=True) for col in price_cols):
                    ix=ref.index[start:start+n]
                    return ix.tz_localize("UTC") if ix.tz is None else ix.tz_convert("UTC")
    raise ValueError(f"UTC index removed; no cached 1d series matches frame values (length={n})")

def _out(df,**cols):
    out=pd.DataFrame(cols,index=df.index)
    for name in ("long_entry","short_entry","long_exit","short_exit"):
        if name in out: out[name]=out[name].fillna(False).astype(bool)
    return out
SPEC_ID="c5-hobbiecode-ibs-monday-reversal"
PARAMS={"ibs_max":0.5,"hold_bars":4}
PARAM_GRID={"ibs_max":[0.45,0.5,0.55],"hold_bars":[4]}
TIMEFRAMES=["1d"]
SIDES="long"
DEVIATIONS=["SPY/S&P 500 source rule applied to cached crypto daily bars; no ETF/index market is present.","Entry described at close is emitted as a close-known signal and harness fills next open.","Previous Friday close is mapped to the immediately preceding Friday daily bar; missing calendar bars are not repaired.","RangeIndex slices recover UTC timestamps only from a cached 1d series with matching OHLC values; TEST starts without previous-week data.","Five trading days (four bars since entry) is modeled with max_hold=4; engine time exit fills at bar close.","Harness universe is crypto majors rather than SPY/futures."]
IMPLEMENTED_FIELDS=["entry_long","exit","filters","timeframes"]
def signals(df,ibs_max=.5,hold_bars=4):
    idx=_utc_index(df); c=df.close.to_numpy(float); hi=df.high.to_numpy(float); lo=df.low.to_numpy(float)
    span=hi-lo; ibs=np.divide(c-lo,span,out=np.full(len(c),np.nan),where=span!=0)
    weekdays=idx.day_of_week; friday_close=np.full(len(c),np.nan)
    lastfri=np.nan
    for i,d in enumerate(idx):
        if d.weekday()==4: lastfri=c[i]
        if d.weekday()==0: friday_close[i]=lastfri
    le=(weekdays==0)&(c<friday_close)&(ibs<float(ibs_max))
    prevhigh=np.r_[np.nan,hi[:-1]]; lx=c>prevhigh
    return _out(df,long_entry=le,short_entry=np.zeros(len(c),bool),long_exit=lx,short_exit=np.zeros(len(c),bool),max_hold=np.full(len(c),int(hold_bars)))
