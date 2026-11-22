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
SPEC_ID="c5-connors-3day-reversion-etf"
PARAMS={"ema_len":5,"trend_filter":0}
PARAM_GRID={"ema_len":[4,5,6],"trend_filter":[0,1]}
TIMEFRAMES=["1d"]
SIDES="long"
DEVIATIONS=["ETF/daily rule evaluated on cached crypto daily bars because no ETF series exists in harness universe.","Optional close > EMA(200) is exposed as trend_filter (default off); EMA(5) exit follows the authoritative Pine spec rather than book SMA exit.","Train/test RangeIndex timestamps are restored from cached BTCUSDT index as described in plugins/slice_3/HARNESS_ISSUES.md; TEST has no preceding-bar context.","Harness universe is crypto majors rather than the source ETF universe."]
IMPLEMENTED_FIELDS=["entry_long","exit","filters","timeframes"]
def signals(df,ema_len=5,trend_filter=0):
    c=df.close.to_numpy(float); h=df.high.to_numpy(float); l=df.low.to_numpy(float)
    ema=pd.Series(c).ewm(span=int(ema_len),adjust=False,min_periods=int(ema_len)).mean().to_numpy()
    ema200=pd.Series(c).ewm(span=200,adjust=False,min_periods=200).mean().to_numpy()
    # Direct four-bar comparisons avoid any future alignment.
    pat=np.zeros(len(c),bool)
    if len(c)>3: pat[3:]=(h[3:]<h[2:-1])&(h[2:-1]<h[1:-2])&(h[1:-2]<h[:-3])&(l[3:]<l[2:-1])&(l[2:-1]<l[1:-2])&(l[1:-2]<l[:-3])
    trend=(c>ema200) if int(trend_filter) else np.ones(len(c),bool)
    le=(c<ema)&pat&trend
    lx=np.zeros(len(c),bool)
    if len(c)>1: lx[1:]=(c[1:]>ema[1:])&(c[:-1]<=ema[:-1])
    return _out(df,long_entry=le,short_entry=np.zeros(len(c),bool),long_exit=lx,short_exit=np.zeros(len(c),bool))
