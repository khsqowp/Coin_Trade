"""Weekend-only exposure gated by prior 7-day return sign (daily UTC)."""
import numpy as np
import pandas as pd

def _frame(df, le, se, lx, sx, **extra):
    out = pd.DataFrame({"long_entry": np.asarray(le, bool), "short_entry": np.asarray(se, bool),
                        "long_exit": np.asarray(lx, bool), "short_exit": np.asarray(sx, bool)}, index=df.index)
    for k, v in extra.items():
        out[k] = np.asarray(v, float)
    return out

import os
from pathlib import Path

_TIME_CACHE = {}

def _times(df, tf):
    """Timestamps of df bars. The harness passes TRAIN/TEST slices with the DatetimeIndex dropped (RangeIndex), see
    HARNESS_ISSUES.md #2; in that case recover the timestamps by exact OHLCV matching against the cached parquet files
    (same data the harness loaded). Pure metadata lookup: no future values are used by the signal logic."""
    if isinstance(df.index, pd.DatetimeIndex):
        return df.index
    n = len(df)
    c = df.close.to_numpy(float); o = df.open.to_numpy(float); v = df.volume.to_numpy(float)
    key = (n, float(c[0]), float(c[-1]), float(o[0]), float(v[0]))
    if key in _TIME_CACHE:
        return _TIME_CACHE[key]
    dirs = [Path(os.environ["STRATEGY_BT_DATA_DIR"])] if os.environ.get("STRATEGY_BT_DATA_DIR") else []
    dirs.append(Path(__file__).resolve().parents[3] / "bb_stoch_stc" / "data")
    for d in dirs:
        for f in sorted(d.glob(f"*_{tf}.parquet")):
            p = pd.read_parquet(f)
            pc = p.close.to_numpy(float); po = p.open.to_numpy(float); pv = p.volume.to_numpy(float)
            for s in np.flatnonzero((pc == c[0]) & (po == o[0]) & (pv == v[0])):
                if s + n <= len(p) and np.array_equal(pc[s:s + n], c) and np.array_equal(po[s:s + n], o) and np.array_equal(pv[s:s + n], v):
                    _TIME_CACHE[key] = p.index[s:s + n]
                    return _TIME_CACHE[key]
    raise RuntimeError("cannot recover bar timestamps for a RangeIndex frame (cache miss in " + str(dirs) + ")")

SPEC_ID = "crypto-weekend-gated-7d-momentum"
PARAMS = {"lookback": 7}
PARAM_GRID = {"lookback": [7, 10, 14]}
TIMEFRAMES = ["1d"]
SIDES = "both"
IMPLEMENTED_FIELDS = ["entry_long", "entry_short", "exit", "stop_loss", "take_profit", "position_sizing", "filters", "timeframes"]
DEVIATIONS = [
    "Weekend = Saturday+Sunday UTC daily bars (identical to the paper's alternative 'Fri close - Mon open' for UTC daily bars). Position opens at the Saturday open and is closed at the Sunday close via max_hold=1.",
    "'Reassess daily' is NOT implemented: the sign of the prior L-day return (close_Fri / close_Fri-L - 1) is frozen at Friday's close for the whole weekend (a Saturday-close re-evaluation would need a Sunday reversal fill which the harness cannot do at the same open).",
    "Harness passes RangeIndex frames (HARNESS_ISSUES.md #2): bar timestamps recovered by exact OHLCV matching against the cached parquet.",
    "Spec says 'cryptocurrencies'; harness pools BTC/ETH/BNB/SOL/XRP; zero return -> flat; unit notional (sizing unspecified).",
    "Grid lookback [7,10,14]: 7 is default, 14 is the paper's alternative stated in the spec.",
]

def signals(df, lookback=7):
    c = df.close.to_numpy(float); n = len(c); k = int(lookback)
    dow = np.asarray(_times(df, TIMEFRAMES[0]).day_of_week)
    ret = np.full(n, np.nan)
    if n > k: ret[k:] = c[k:] / c[:-k] - 1.0
    fri = dow == 4
    le = fri & (ret > 0); se = fri & (ret < 0)
    mh = np.full(n, 1.0)   # constant on every bar so the harness's random-entry null also gets the weekend exit
    z = np.zeros(n, bool)
    return _frame(df, le, se, z, z, max_hold=mh)
