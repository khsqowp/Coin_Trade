"""BTC 08 UTC: daytime = negative sign of previous day-session return, nighttime long."""
import numpy as np
import pandas as pd

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

SPEC_ID = "btc-08utc-reversal-long"
PARAMS = {"cutoff_hour": 8}
PARAM_GRID = {}   # fixed 08 UTC boundary exactly as archived; no tuning (paper's cutoff search is the data-mining risk)
TIMEFRAMES = ["1h"]
SIDES = "both"
DAY_RULE = "rev"      # rule for [cutoff, cutoff+12h) UTC; one of long/short/cash/mom/rev
NIGHT_RULE = "long"  # rule for [cutoff+12h, cutoff+24h) UTC
IMPLEMENTED_FIELDS = ["entry_long", "entry_short", "exit", "stop_loss", "take_profit", "position_sizing", "filters", "timeframes"]
DEVIATIONS = [
    "Spec is BTCUSD only; harness pools the 5 majors (BTC, ETH, BNB, SOL, XRP) with the same BTC-derived rule applied to each symbol.",
    "Session returns are computed on Binance-style USDT spot/perp hourly bars: session return = close of last hourly bar / open of first hourly bar of the PREVIOUS same-type session (needs all 12 bars, else flat).",
    "Harness passes RangeIndex frames (HARNESS_ISSUES.md #2): bar timestamps are recovered by exact OHLCV matching against the cached parquet. Entries fill at the next-bar open = session start (signal on the last hourly bar of the preceding session); session end is realised by max_hold=11 bars, i.e. exit at the close of the final hourly bar (= next session open). No explicit exit signal is used so back-to-back sessions need no reversal workaround.",
    "Zero previous-session return maps to flat (as the spec's filter says). Unit notional = harness fixed 1000 per session leg. Paper's costs exclude fees/slippage; harness charges 0.04%+0.02% per fill (so ~0.12% round trip per 12h leg).",
    "Cutoff hour fixed at 08 UTC exactly as the archived spec; the paper's cutoff-hour search is NOT replicated (no grid).",
]

def _keys(ts, base, cutoff):
    sh = ts - pd.Timedelta(hours=int(cutoff))
    d = np.asarray((sh.normalize() - base).days)
    return d * 2 + (np.asarray(sh.hour) >= 12).astype(int)

def _dir(rule, prev_ret):
    if rule == "long": return np.ones(len(prev_ret))
    if rule == "short": return -np.ones(len(prev_ret))
    if rule == "cash": return np.zeros(len(prev_ret))
    s = np.sign(np.nan_to_num(prev_ret, nan=0.0))   # NaN or zero -> flat
    return s if rule == "mom" else -s

def signals(df, cutoff_hour=8):
    idx = _times(df, TIMEFRAMES[0]); n = len(df); cutoff = int(cutoff_hour)
    o = df.open.to_numpy(float); c = df.close.to_numpy(float)
    base = (idx[0] - pd.Timedelta(hours=cutoff)).normalize()
    key = _keys(idx, base, cutoff)
    g = pd.DataFrame({"k": key, "o": o, "c": c}).groupby("k")
    cnt = g["o"].count(); first_o = g["o"].first(); last_c = g["c"].last()
    ret = (last_c / first_o - 1.0).where(cnt == 12)          # complete sessions only
    nxt_key = _keys(idx + pd.Timedelta(hours=1), base, cutoff)
    prev_ret = pd.Series(nxt_key - 2).map(ret).to_numpy(float)  # previous same-type session, completed before the signal bar closes
    nh = (np.asarray(idx.hour) + 1) % 24
    day_b = nh == cutoff; night_b = nh == (cutoff + 12) % 24
    dirs = np.zeros(n)
    dirs[day_b] = _dir(DAY_RULE, prev_ret)[day_b]
    dirs[night_b] = _dir(NIGHT_RULE, prev_ret)[night_b]
    le = dirs > 0; se = dirs < 0
    mh = np.full(n, 11.0)   # constant on every bar so the harness's random-entry null also gets the session-end exit
    z = np.zeros(n, bool)
    out = pd.DataFrame({"long_entry": le, "short_entry": se, "long_exit": z, "short_exit": z, "max_hold": mh}, index=df.index)
    return out
