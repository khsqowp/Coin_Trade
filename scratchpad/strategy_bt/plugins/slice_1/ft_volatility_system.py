"""Freqtrade VolatilitySystem: stop-and-reverse on close change exceeding 2*ATR(14) of a 3h resample."""
import numpy as np
import pandas as pd

def _atr(h, l, c, n):
    """Pine ta.atr: RMA of true range (tr[0] = high-low), SMA seed."""
    h = np.asarray(h, float); l = np.asarray(l, float); c = np.asarray(c, float); n = int(n)
    pc = np.r_[np.nan, c[:-1]]
    tr = np.maximum.reduce([h - l, np.nan_to_num(np.abs(h - pc), nan=0.0), np.nan_to_num(np.abs(l - pc), nan=0.0)])
    out = np.full(len(c), np.nan)
    if len(c) >= n:
        out[n - 1] = tr[:n].mean()
        for i in range(n, len(c)):
            out[i] = (out[i - 1] * (n - 1) + tr[i]) / n
    return out

def _sticky(entry, opp_exit, own_exit):
    """Harness workaround (see HARNESS_ISSUES.md #1): a same-bar reversal cannot fill at the exit bar's open, so a
    reversal entry signal is repeated one bar later (unless the new position's own exit fired meanwhile)."""
    e = np.asarray(entry, bool); ox = np.asarray(opp_exit, bool); wx = np.asarray(own_exit, bool)
    prev = np.zeros(len(e), bool)
    if len(e) > 1:
        prev[1:] = (e[:-1] & ox[:-1]) & ~wx[1:]
    return e | prev

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

SPEC_ID = "ft_volatility_system"
PARAMS = {"atr_mult": 2.0, "resample_hours": 3}
PARAM_GRID = {"atr_mult": [1.5, 2.0, 2.5], "resample_hours": [2, 3, 4]}
TIMEFRAMES = ["1h"]
SIDES = "both"
IMPLEMENTED_FIELDS = ["entry_long", "entry_short", "exit", "stop_loss", "take_profit", "filters", "timeframes"]
DEVIATIONS = [
    "Rule from the cited source (VolatilitySystem.py): on a 180-minute resample of the 1h data, atr = ATR(14)*2 and close_change = close.diff(); on the 1h rows enter_long = close_change > atr.shift(1), enter_short = -close_change > atr.shift(1); exit_short = enter_long and exit_long = enter_short (stop-and-reverse). The spec's 'resample lookahead check' is honoured: each 1h row only sees the last 3h bucket that was COMPLETE by that row's open time (like technical.resampled_merge), then shift(1) on 1h rows.",
    "Harness passes RangeIndex frames (HARNESS_ISSUES.md #2): bar timestamps recovered by exact OHLCV matching against the cached parquet.",
    "Resampled ATR uses Wilder ATR(14) via own implementation instead of TA-Lib (tiny seed differences). Buckets with missing bars are dropped.",
    "Source's 50% initial stake + one position-adjustment add and 2x leverage are NOT modelled (harness: one fixed notional). roi (10000%) and stoploss (-100%) are effectively disabled in the source. Reversal fills one bar later (HARNESS_ISSUES.md #1).",
]

def signals(df, atr_mult=2.0, resample_hours=3):
    n = len(df); k = int(resample_hours)
    c = df.close.to_numpy(float); h = df.high.to_numpy(float); l = df.low.to_numpy(float)
    z = np.zeros(n, bool)
    if n < 10: return _frame(df, z, z, z, z)
    ts = _times(df, TIMEFRAMES[0])      # harness passes RangeIndex frames (HARNESS_ISSUES.md #2)
    idx = ts.tz_convert("UTC").tz_localize(None) if ts.tz is not None else ts
    r = pd.DataFrame({"high": h, "low": l, "close": c}, index=idx)
    cnt = r.close.resample(f"{k}h").count()
    b = r.resample(f"{k}h").agg({"high": "max", "low": "min", "close": "last"})
    b = b[cnt.reindex(b.index).to_numpy() == k]
    if len(b) < 20: return _frame(df, z, z, z, z)
    atr_b = _atr(b.high.to_numpy(), b.low.to_numpy(), b.close.to_numpy(), 14) * float(atr_mult)
    chg_b = np.r_[np.nan, np.diff(b.close.to_numpy())]
    ends = (b.index + pd.Timedelta(hours=k)).to_numpy()
    pos = np.searchsorted(ends, idx.to_numpy(), side="right") - 1      # last bucket completed at or before this row's open
    ok = pos >= 0
    atr = np.where(ok, atr_b[np.clip(pos, 0, None)], np.nan); chg = np.where(ok, chg_b[np.clip(pos, 0, None)], np.nan)
    atr_prev = np.r_[np.nan, atr[:-1]]
    el = chg > atr_prev; es = (-chg) > atr_prev
    return _frame(df, _sticky(el, el, es), _sticky(es, es, el), es, el)
