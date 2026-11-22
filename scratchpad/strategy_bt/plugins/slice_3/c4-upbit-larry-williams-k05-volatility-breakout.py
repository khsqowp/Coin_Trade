import numpy as np
import pandas as pd
SPEC_ID="c4-upbit-larry-williams-k05-volatility-breakout"
PARAMS={"k":0.5}; PARAM_GRID={"k":[0.4,0.5,0.6]}; TIMEFRAMES=["15m","1h"]; SIDES="long"
DEVIATIONS=["Daily trigger is derived from completed prior UTC day; entry signal follows first intraday high touch and harness fills next open, not at trigger price.","If first bar of day touches trigger, its next-open fill is used; intraday ordering within that bar is unavailable.","Harness reset_index(drop=True) removes UTC timestamps in train/test slices (HARNESS_ISSUES.md #1); timestamps are restored from the shared cached BTCUSDT index when slice length equals the full/60%/40% length of the 15m/1h/4h cache (only timestamps recovered, real gaps preserved). The TEST slice has no preceding-day/session history, so the first prior-session/prior-day dependent decisions are flat/absent.","Last intraday slot exit signal fills at next UTC-day open, matching overnight holding approximately.","Archived Upbit BTC-only instrument restriction is ignored by harness universe."]
IMPLEMENTED_FIELDS=["entry_long","exit","timeframes"]
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

def signals(df,k=0.5):
    idx=_utc_index(df); day=idx.normalize(); mins=15 if len(idx)>1 and (idx[1]-idx[0]).total_seconds()<=900 else 60
    d=pd.DataFrame({"open":df.open.to_numpy(float),"high":df.high.to_numpy(float),"low":df.low.to_numpy(float)},index=idx).groupby(day).agg(open=("open","first"),high=("high","max"),low=("low","min"))
    trigger=d.open + float(k)*(d.high.shift(1)-d.low.shift(1))
    t=trigger.reindex(day).to_numpy(float); touch=df.high.to_numpy(float)>=t
    ts=pd.Series(touch,index=idx); hit=(ts & ts.groupby(day).cumsum().eq(1)).to_numpy(bool)
    last=np.asarray((idx.hour*60+idx.minute)==1440-mins,bool)
    return pd.DataFrame({"long_entry":hit & ~last,"short_entry":False,"long_exit":last,"short_exit":False},index=df.index).fillna(False)
