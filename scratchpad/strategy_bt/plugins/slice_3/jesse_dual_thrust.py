import numpy as np
import pandas as pd
from common.indicators import atr
SPEC_ID="jesse_dual_thrust"
PARAMS={"n_up":21,"n_down":21,"up_coeff":0.71,"down_coeff":0.67,"atr_len":14,"atr_mult":2.0}
PARAM_GRID={"up_coeff":[0.6,0.71,0.8],"down_coeff":[0.57,0.67,0.77]}; TIMEFRAMES=["1h","4h"]; SIDES="both"
DEVIATIONS=["Anchor timeframe is not specified by archived implementation notes; assumed UTC calendar day for both requested timeframes.","Only completed prior UTC daily bars feed ranges; same-day daily open is used from its first intraday bar.","Harness reset_index(drop=True) removes UTC timestamps in train/test slices (HARNESS_ISSUES.md #1); timestamps are restored from the shared cached BTCUSDT index when slice length equals the full/60%/40% length of the 15m/1h/4h cache (only timestamps recovered, real gaps preserved). The TEST slice has no preceding-day/session history, so the first prior-session/prior-day dependent decisions are flat/absent.","Harness stop is an ATR distance from next-open fill, whereas archived stop is described relative to entry; position sizing risk_to_qty 2% is not implemented because harness uses fixed notional.","Archived instrument restriction is ignored by harness universe."]
IMPLEMENTED_FIELDS=["entry_long","entry_short","exit","stop_loss","timeframes"]
def _utc_index(df):
    """Return the UTC bar-open DatetimeIndex of df.
    Workaround for HARNESS_ISSUES.md #1: common.protocol.evaluate() resets the index of the
    train/test slices to a RangeIndex. The cached 15m/1h/4h parquet files of every symbol share
    one identical, gap-containing index, so a RangeIndex slice whose length equals the full /
    first-60% / last-40% length of a cached reference file is mapped back onto that reference
    index (only timestamps are recovered; no price information from the reference is used)."""
    from pathlib import Path
    idx = df.index
    if isinstance(idx, pd.DatetimeIndex):
        return idx.tz_localize("UTC") if idx.tz is None else idx.tz_convert("UTC")
    n = len(df)
    here = Path(__file__).resolve()
    for base in here.parents:
        data = base / "bb_stoch_stc" / "data"
        if not data.is_dir():
            data = base.parent / "bb_stoch_stc" / "data"
        if data.is_dir():
            break
    else:
        raise RuntimeError("cannot locate bb_stoch_stc/data to restore timestamps")
    for tf in ("15m", "1h", "4h"):
        ref = pd.read_parquet(data / f"BTCUSDT_{tf}.parquet", columns=["close"]).index
        full = len(ref); tr = int(full * 0.6)
        for length, part in ((full, ref), (tr, ref[:tr]), (full - tr, ref[tr:])):
            if n == length:
                return pd.DatetimeIndex(part)
    raise ValueError("UTC index was removed and slice length matches no cached 15m/1h/4h split")

def signals(df,n_up=21,n_down=21,up_coeff=.71,down_coeff=.67,atr_len=14,atr_mult=2.):
    idx=_utc_index(df); day=idx.normalize()
    d=pd.DataFrame({"open":df.open.to_numpy(float),"high":df.high.to_numpy(float),"low":df.low.to_numpy(float),"close":df.close.to_numpy(float)},index=idx).groupby(day).agg(open=("open","first"),high=("high","max"),low=("low","min"),close=("close","last"))
    # N completed anchor bars before D: rolling on daily values then shift one day.
    up_range=pd.concat([d.high.rolling(int(n_up)).max()-d.close.rolling(int(n_up)).min(),d.close.rolling(int(n_up)).max()-d.low.rolling(int(n_up)).min()],axis=1).max(axis=1).shift(1)
    dn_range=pd.concat([d.high.rolling(int(n_down)).max()-d.close.rolling(int(n_down)).min(),d.close.rolling(int(n_down)).max()-d.low.rolling(int(n_down)).min()],axis=1).max(axis=1).shift(1)
    ao=d.open.reindex(day).to_numpy(float); ur=up_range.reindex(day).to_numpy(float); dr=dn_range.reindex(day).to_numpy(float); c=df.close.to_numpy(float)
    le=c>ao+float(up_coeff)*ur; se=c<ao-float(down_coeff)*dr
    av=atr(df.high.to_numpy(float),df.low.to_numpy(float),df.close.to_numpy(float),int(atr_len))*float(atr_mult)
    return pd.DataFrame({"long_entry":le,"short_entry":se,"long_exit":se,"short_exit":le,"atr_stop":av},index=df.index).fillna({"long_entry":False,"short_entry":False,"long_exit":False,"short_exit":False})
