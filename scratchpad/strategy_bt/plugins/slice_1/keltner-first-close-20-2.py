"""Keltner EMA20/ATR20 x2 first close outside the band, stop at signal bar extreme, 2R target."""
import numpy as np
import pandas as pd

def _ema(x, n):
    """EMA seeded at first value (same convention as common.indicators.ema)."""
    return pd.Series(np.asarray(x, float)).ewm(span=int(n), adjust=False).mean().to_numpy()

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

def _frame(df, le, se, lx, sx, **extra):
    out = pd.DataFrame({"long_entry": np.asarray(le, bool), "short_entry": np.asarray(se, bool),
                        "long_exit": np.asarray(lx, bool), "short_exit": np.asarray(sx, bool)}, index=df.index)
    for k, v in extra.items():
        out[k] = np.asarray(v, float)
    return out

SPEC_ID = "keltner-first-close-20-2"
PARAMS = {"ema_len": 20, "mult": 2.0, "atr_len": 20, "rr": 2.0}
PARAM_GRID = {"ema_len": [15, 20, 25], "mult": [1.5, 2.0, 2.5]}
TIMEFRAMES = ["1d"]
SIDES = "both"
IMPLEMENTED_FIELDS = ["entry_long", "entry_short", "exit", "stop_loss", "take_profit", "filters", "timeframes"]
DEVIATIONS = [
    "Spec claims QQQ/BTC examples; harness pools the 5 crypto majors on daily bars.",
    "Bands = EMA(close, ema_len) +/- mult * Wilder ATR(atr_len). 'Previous close inside' = previous close between the bands. First-outside-close entry at the next daily open.",
    "'Close back inside channel' exit implemented as: long exits when close <= upper band; short exits when close >= lower band (signal at close, fill next open).",
    "Stop = signal-bar low (long) / high (short) and target = rr x risk are expressed to the harness as fractions of the signal-bar CLOSE (stop_pct=(close-low)/close, tp_pct=rr*stop_pct) and then applied to the actual next-open fill, so the absolute stop level differs from the signal bar extreme by the open-vs-close gap.",
    "Risk-based position sizing NOT implemented (spec leaves the fraction unspecified): harness fixed notional per trade.",
    "Signals suppressed for the first max(ema_len, atr_len)+1 bars (indicator warm-up).",
]

def signals(df, ema_len=20, mult=2.0, atr_len=20, rr=2.0):
    h = df.high.to_numpy(float); l = df.low.to_numpy(float); c = df.close.to_numpy(float); n = len(c)
    mid = _ema(c, ema_len); a = _atr(h, l, c, atr_len)
    up = mid + mult * a; lo = mid - mult * a
    inside = (c <= up) & (c >= lo)
    prev_inside = np.r_[False, inside[:-1]]
    ok = ~np.isnan(a) & (np.arange(n) > max(int(ema_len), int(atr_len)))
    le = (c > up) & prev_inside & ok
    se = (c < lo) & prev_inside & ok
    lx = c <= up; sx = c >= lo
    sp = np.full(n, np.nan)
    sp[le] = ((c - l) / c)[le]; sp[se] = ((h - c) / c)[se]
    # Off-signal bars get the (causal, expanding) median signal-bar risk so the harness's random-entry null (which reuses these
    # columns bar-by-bar, HARNESS_ISSUES.md #3) also applies a stop and 2R target. Real entries only use signal-bar values.
    # Fill = EXPANDING median of past signal-bar risks (causal; a full-sample median would look ahead).
    ent = le | se
    fill = pd.Series(np.where(ent, sp, np.nan)).expanding(min_periods=1).median().to_numpy()
    sp = np.where(ent, sp, fill)
    return _frame(df, le, se, lx, sx, stop_pct=sp, tp_pct=sp * float(rr))
