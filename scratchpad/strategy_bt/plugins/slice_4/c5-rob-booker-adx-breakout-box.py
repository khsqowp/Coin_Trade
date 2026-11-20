"""Low ADX 20-bar box breakout with box-width stop and target."""
import numpy as np
import pandas as pd

SPEC_ID = "c5-rob-booker-adx-breakout-box"
PARAMS = {"adx_len": 14, "box_len": 20, "adx_max": 18.0, "stop_width": 0.5, "target_width": 1.0}
PARAM_GRID = {"adx_max": [16.0, 18.0, 20.0]}
TIMEFRAMES = ["1h", "4h"]
SIDES = "both"
DEVIATIONS = [
    "Breakout crosses use prior-bar 20-bar extremes and next-open execution, matching the harness signal contract.",
    "ADX uses Wilder smoothing for true range, directional movement, and DX.",
    "Stop and target width are frozen from the box on the signal bar and converted to a fraction of that bar's close; next-open fill can differ from that reference price.",
    "Harness universe replaces the forex-origin market selection."
]
IMPLEMENTED_FIELDS = ["entry_long", "entry_short", "exit", "stop_loss", "take_profit", "timeframes"]


def _rma(x, n):
    out = np.full(len(x), np.nan)
    if len(x) >= n:
        out[n - 1] = np.nanmean(x[:n])
        for i in range(n, len(x)):
            out[i] = (out[i - 1] * (n - 1) + x[i]) / n
    return out


def _adx(df, n):
    h, l, c = (df[k].to_numpy(float) for k in ("high", "low", "close"))
    up = np.r_[np.nan, np.diff(h)]
    down = np.r_[np.nan, -np.diff(l)]
    pc = np.r_[np.nan, c[:-1]]
    tr = np.maximum.reduce([h - l, np.abs(h - pc), np.abs(l - pc)])
    atr = _rma(tr, n)
    plus = 100 * _rma(np.where((up > down) & (up > 0), up, 0.0), n) / atr
    minus = 100 * _rma(np.where((down > up) & (down > 0), down, 0.0), n) / atr
    dx = 100 * np.abs(plus - minus) / (plus + minus)
    return _rma(dx, n)


def signals(df, adx_len=14, box_len=20, adx_max=18.0, stop_width=0.5, target_width=1.0, **_):
    c = df.close.to_numpy(float)
    upper = df.high.rolling(int(box_len), min_periods=int(box_len)).max().shift(1).to_numpy()
    lower = df.low.rolling(int(box_len), min_periods=int(box_len)).min().shift(1).to_numpy()
    adx = _adx(df, int(adx_len))
    pc = np.r_[np.nan, c[:-1]]
    pu = np.r_[np.nan, upper[:-1]]
    pl = np.r_[np.nan, lower[:-1]]
    le = (adx < float(adx_max)) & (c > upper) & (pc <= pu)
    se = (adx < float(adx_max)) & (c < lower) & (pc >= pl)
    width_pct = np.divide(upper - lower, c, out=np.full(len(c), np.nan), where=c != 0)
    stop = width_pct * float(stop_width)
    target = width_pct * float(target_width)
    return pd.DataFrame({"long_entry": le, "short_entry": se, "long_exit": False, "short_exit": False,
                         "stop_pct": stop, "tp_pct": target}, index=df.index)
