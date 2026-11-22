"""Time helpers for slice_0 plugins.

bar_times exists because common.protocol.evaluate drops the index before calling
signals. In that case timestamps are recovered by matching OHLC values exactly
against cached source parquet rows.
"""
from functools import lru_cache
from pathlib import Path
import os
import numpy as np
import pandas as pd


@lru_cache(maxsize=64)
def _read_ohlc(path):
    frame = pd.read_parquet(path)
    if "open_time" in frame:
        times = pd.to_datetime(frame.pop("open_time"), utc=True)
    elif isinstance(frame.index, pd.DatetimeIndex):
        times = pd.to_datetime(frame.index, utc=True)
    else:
        raise ValueError(f"Parquet {path} has neither open_time column nor DatetimeIndex")
    return times, frame[["open", "high", "low", "close"]].to_numpy(float)


def bar_times(df, tf):
    """Return UTC bar-open times aligned with df, recovering reset indexes by OHLC."""
    if isinstance(df.index, pd.DatetimeIndex):
        idx = df.index
        return idx.tz_localize("UTC") if idx.tz is None else idx.tz_convert("UTC")
    root = Path(__file__).resolve().parents[3] / "bb_stoch_stc" / "data"
    data_dir = Path(os.environ.get("S0_DATA_DIR", root))
    files = sorted(data_dir.glob(f"*_{tf}.parquet"))
    if not files:
        raise ValueError(f"No parquet files matching *_{tf}.parquet in {data_dir}")
    wanted = df[["open", "high", "low", "close"]].to_numpy(float)
    if not len(wanted):
        raise ValueError("Cannot recover timestamps for an empty frame")
    k = min(8, len(wanted)); matches = []
    for path in files:
        times, values = _read_ohlc(str(path))
        if len(values) < len(wanted):
            continue
        starts = np.flatnonzero(np.all(values[:len(values)-k+1] == wanted[0], axis=1))
        for j in starts:
            if j + len(wanted) <= len(values) and np.array_equal(values[j:j+k], wanted[:k]) and np.array_equal(values[j+len(wanted)-1], wanted[-1]):
                matches.append((path, int(j), times))
    if len(matches) != 1:
        raise ValueError(f"Timestamp recovery for {len(df)} {tf} bars found {len(matches)} exact matches in {data_dir}; expected exactly one")
    _, offset, times = matches[0]
    return pd.DatetimeIndex(times[offset:offset+len(df)])


def session_signals(df, tf_hours, cut, day_mode, night_mode):
    """Build boundary entries for two 12-hour blocks using completed prior sessions."""
    times = bar_times(df, f"{tf_hours}h")
    n = len(df); le = np.zeros(n, bool); se = np.zeros(n, bool)
    mh = np.full(n, np.nan)
    opens = df.open.to_numpy(float); closes = df.close.to_numpy(float)
    lookup = {int(t.value // 10**9): i for i, t in enumerate(times)}
    # A valid session return requires all twelve hourly bars with no time gap.
    returns = {}
    for i, t in enumerate(times):
        hour = t.hour
        start_hour = cut if cut <= hour < (cut+12)%24 else (cut+12)%24
        if cut+12 >= 24:
            # The two intervals wrap midnight; hour membership is determined by UTC modulo.
            day = (hour >= cut or hour < cut+12-24)
        else:
            day = cut <= hour < cut+12
        start = t.normalize() + pd.Timedelta(hours=(cut if day else (cut+12)%24))
        if start > t: start -= pd.Timedelta(days=1)
        key = int(start.value // 10**9)
        if key in returns: continue
        ids = [lookup.get(key + h*3600) for h in range(12)]
        if all(x is not None for x in ids) and np.all(np.isfinite(opens[ids])) and np.all(np.isfinite(closes[ids])):
            returns[key] = closes[ids[-1]] / opens[ids[0]] - 1
        else: returns[key] = np.nan
    for i, t in enumerate(times):
        boundary_hour = t.hour
        if boundary_hour not in (cut-1, (cut+11)%24): continue
        start = t + pd.Timedelta(hours=1)
        mode = day_mode if start.hour == cut else night_mode
        if mode == "cash": continue
        prior_start = start - pd.Timedelta(days=1)
        prev = returns.get(int(prior_start.value // 10**9), np.nan)
        direction = {"long": 1, "short": -1, "mom": int(np.sign(prev)) if np.isfinite(prev) else 0,
                    "rev": -int(np.sign(prev)) if np.isfinite(prev) else 0}[mode]
        if direction > 0: le[i] = True
        elif direction < 0: se[i] = True
        if direction: mh[i] = 11
    return pd.DataFrame({"long_entry":le,"short_entry":se,"long_exit":False,"short_exit":False,"max_hold":mh}, index=df.index)
