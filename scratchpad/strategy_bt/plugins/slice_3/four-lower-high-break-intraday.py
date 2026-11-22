import numpy as np
import pandas as pd

SPEC_ID="four-lower-high-break-intraday"
PARAMS={"n_lower":4}
PARAM_GRID={"n_lower":[3,4,5]}
TIMEFRAMES=["15m","1h"]
SIDES="long"
DEVIATIONS=["Intraday OHLC signals at the first bar whose high touches the stop; harness enters next open, not trigger price, and cannot model a gap-open stop fill.","Daily OHLC is aggregated from available intraday bars; only prior UTC calendar days are used, and missing bars are not repaired.","Harness reset_index(drop=True) removes UTC timestamps in train/test slices (HARNESS_ISSUES.md #1); timestamps are restored from the shared cached BTCUSDT index when slice length equals the full/60%/40% length of the 15m/1h/4h cache (only timestamps recovered, real gaps preserved). The TEST slice has no preceding-day/session history, so the first prior-session/prior-day dependent decisions are flat/absent.","Exit signal on final intraday slot fills at next day's open, approximating entry-day close exit.","Archived instrument list is ignored by harness universe."]
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

def signals(df,n_lower=4):
    idx=_utc_index(df); day=idx.normalize(); minutes=15 if len(idx)>1 and (idx[1]-idx[0]).total_seconds()<=900 else 60
    last=np.asarray((idx.hour*60+idx.minute)==1440-minutes,bool)
    daily=pd.DataFrame({"high":df.high.to_numpy(float)},index=idx).groupby(day).agg(high=("high","max"))
    lower=daily.high.lt(daily.high.shift(1))
    setup=lower.rolling(int(n_lower),min_periods=int(n_lower)).sum().eq(int(n_lower)).shift(1)
    trigger=daily.high.shift(1); valid=setup.reindex(day).fillna(False).to_numpy(bool)
    t=trigger.reindex(day).to_numpy(float); h=df.high.to_numpy(float)
    touch=valid & (h>=t)
    ts=pd.Series(touch,index=idx); first=(ts & ts.groupby(day).cumsum().eq(1)).to_numpy(bool)
    le=first & ~last
    return pd.DataFrame({"long_entry":le,"short_entry":False,"long_exit":last,"short_exit":False},index=df.index).fillna(False)
