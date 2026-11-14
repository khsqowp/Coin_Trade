"""Building blocks for the deterministic strategy pool. Everything is causal (bar t uses bars <= t)."""
import numpy as np
import pandas as pd


def base_delta(df):
    if len(df) < 3:
        return pd.Timedelta("1h")
    return pd.Timedelta(pd.Series(df.index[:200]).diff().median())     # median: robust to weekend gaps


def htf_align(df, mult, fn):
    """Evaluate fn(htf_df)->Series on bars resampled to `mult` x the base timeframe, then align to the base index using
    ONLY completed higher-timeframe bars (a HTF bar is usable once its end <= the close time of the base bar)."""
    td = base_delta(df)
    rule = td * mult
    agg = df.resample(rule, label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna()
    s = fn(agg)
    right = pd.DataFrame({"t": (s.index + rule).astype("datetime64[ns, UTC]"), "v": s.values.astype(float)})
    left = pd.DataFrame({"t": (df.index + td).astype("datetime64[ns, UTC]")})
    out = pd.merge_asof(left, right.sort_values("t"), on="t", direction="backward")
    return pd.Series(out["v"].values, index=df.index)


def position_loop(entry, close, atr, exit_sig=None, *, trail_mult=None, hard_stop_pct=None, max_bars=None,
                  rearm_after_stop=True):
    """Generic long/flat state machine.
    entry, exit_sig: boolean arrays (exit_sig = non-stateful exit conditions). trail_mult: exit when close < highest close
    since entry - trail_mult*ATR. hard_stop_pct: exit when close <= entry*(1-pct). max_bars: time stop.
    A bar that exits cannot re-enter (no same-bar flip) and, after a protective stop, a fresh entry edge is required."""
    n = len(close)
    sig = np.zeros(n)
    pos, entry_px, highest, held = False, 0.0, 0.0, 0
    armed = True
    for i in range(n):
        exited = False
        if pos:
            held += 1
            highest = max(highest, close[i])
            stop = False
            if trail_mult is not None and atr[i] == atr[i] and close[i] < highest - trail_mult * atr[i]:
                stop = True
            if hard_stop_pct is not None and close[i] <= entry_px * (1.0 - hard_stop_pct):
                stop = True
            if max_bars is not None and held >= max_bars:
                stop = True
            if stop or (exit_sig is not None and exit_sig[i]):
                pos, exited = False, True
                if stop and rearm_after_stop:
                    armed = False
        if not entry[i]:
            armed = True
        if (not pos) and (not exited) and entry[i] and armed:
            pos, entry_px, highest, held = True, close[i], close[i], 0
        sig[i] = 1.0 if pos else 0.0
    return sig


def to_series(arr, df):
    return pd.Series(arr, index=df.index, dtype=float)


def b(x):
    """Boolean ndarray from a Series, NaN -> False."""
    return np.asarray(x.fillna(False).astype(bool).values if hasattr(x, "fillna") else x, dtype=bool)


def cond(disabled, name, series):
    """Rule switch: a disabled rule counts as always satisfied."""
    if name in disabled:
        return np.ones(len(series), dtype=bool)
    return b(series)
