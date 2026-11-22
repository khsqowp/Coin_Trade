"""MACD pullback with trend and ADX filters."""
import numpy as np
import pandas as pd
from common.indicators import atr, ema

SPEC_ID = "tv_macd_pullback_adx"
PARAMS = {"adx_min": 20, "stop_atr": 2.0, "rr": 2.0}
PARAM_GRID = {"adx_min": [15, 20, 25], "stop_atr": [1.5, 2.0, 2.5], "rr": [1.5, 2.0, 2.5]}
TIMEFRAMES = ["1h", "4h"]
SIDES = "both"
DEVIATIONS = [
    "Short trading is enabled from the archived allowShort summary.",
    "The optional opposite MACD cross exit is assumed enabled.",
    "The harness has no equity-risk sizing interface; archived 1% risk sizing and 1x equity cap are not implemented.",
    "Take-profit distance is expressed as rr*stop_atr*ATR divided by the signal-bar close, approximating the next-open entry price.",
    "MACD and EMA use common.indicators.ema, whose first finite observation seeds the recursive EMA.",
    "ADX uses Wilder sums seeded from bars 1 through period, then Wilder smoothing; initial values remain NaN until defined.",
]
IMPLEMENTED_FIELDS = ["entry_long", "entry_short", "exit", "stop_loss", "take_profit", "filters", "timeframes"]


def cross_up(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    return np.r_[False, (a[1:] > b[1:]) & (a[:-1] <= b[:-1])]


def cross_down(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    return np.r_[False, (a[1:] < b[1:]) & (a[:-1] >= b[:-1])]


def adx_wilder(high, low, close, period=14):
    h, l, c = (np.asarray(v, float) for v in (high, low, close))
    n = len(c); p = int(period)
    tr = np.full(n, np.nan); plus = np.zeros(n); minus = np.zeros(n)
    if n < 2: return np.full(n, np.nan)
    up, down = h[1:] - h[:-1], l[:-1] - l[1:]
    plus[1:] = np.where((up > down) & (up > 0), up, 0.0)
    minus[1:] = np.where((down > up) & (down > 0), down, 0.0)
    tr[1:] = np.maximum.reduce((h[1:] - l[1:], np.abs(h[1:] - c[:-1]), np.abs(l[1:] - c[:-1])))
    out = np.full(n, np.nan)
    if n <= p: return out
    tr_s, plus_s, minus_s = np.sum(tr[1:p+1]), np.sum(plus[1:p+1]), np.sum(minus[1:p+1])
    dx = np.full(n, np.nan)
    def dx_at(i):
        pdi = 100 * plus_s / tr_s if tr_s else 0.0
        mdi = 100 * minus_s / tr_s if tr_s else 0.0
        denom = pdi + mdi
        dx[i] = 100 * abs(pdi - mdi) / denom if denom else 0.0
    dx_at(p)
    for i in range(p + 1, n):
        tr_s = tr_s - tr_s / p + tr[i]
        plus_s = plus_s - plus_s / p + plus[i]
        minus_s = minus_s - minus_s / p + minus[i]
        dx_at(i)
    first_adx = 2 * p - 1
    if n <= first_adx: return out
    out[first_adx] = np.mean(dx[p:first_adx+1])
    for i in range(first_adx + 1, n): out[i] = (out[i-1] * (p - 1) + dx[i]) / p
    return out


def signals(df, adx_min=20, stop_atr=2.0, rr=2.0):
    close = df.close.to_numpy(float); high = df.high.to_numpy(float); low = df.low.to_numpy(float)
    macd = ema(close, 12) - ema(close, 26); sig = ema(macd, 9)
    trend = ema(close, 200); adx = adx_wilder(high, low, close, 14); volatility = atr(high, low, close, 14)
    up, down = cross_up(macd, sig), cross_down(macd, sig)
    le = up & (macd < 0) & (close > trend) & (adx >= adx_min)
    se = down & (macd > 0) & (close < trend) & (adx >= adx_min)
    risk = stop_atr * volatility
    tp = rr * risk / close
    return pd.DataFrame({"long_entry": le, "short_entry": se, "long_exit": down, "short_exit": up,
                         "atr_stop": risk, "tp_pct": tp}, index=df.index)
