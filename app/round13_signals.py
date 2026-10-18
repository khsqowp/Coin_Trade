"""Forward-only daily indicators; completed aggregate bars published at close."""

import numpy as np
import pandas as pd
from app.round12_signals import find_signals as prior
from app.technical_signal_common import ta

FAMILIES = ["aroon", "williams", "ichimoku", "psar", "trix", "awesome", "keltner"]


def psar_direction(h, l, c):
    high, low = h.to_numpy(), l.to_numpy()
    result = np.ones(len(c), dtype=int)
    if len(c) < 2:
        return pd.Series(result, index=c.index)
    bull, sar, extreme, acceleration = True, low[0], high[0], 0.02
    for i in range(1, len(c)):
        sar += acceleration * (extreme - sar)
        if bull:
            sar = min(sar, low[i - 1], low[max(0, i - 2)])
            if low[i] < sar:
                bull, sar, extreme, acceleration = False, extreme, low[i], 0.02
            elif high[i] > extreme:
                extreme, acceleration = high[i], min(0.2, acceleration + 0.02)
        else:
            sar = max(sar, high[i - 1], high[max(0, i - 2)])
            if high[i] > sar:
                bull, sar, extreme, acceleration = True, extreme, high[i], 0.02
            elif low[i] < extreme:
                extreme, acceleration = low[i], min(0.2, acceleration + 0.02)
        result[i] = 1 if bull else -1
    return pd.Series(result, index=c.index)


def find_signals(frame, family, **params):
    if family not in FAMILIES:
        return prior(frame, family, **params)
    out = prior(frame, "rebound")  # shared causal fields, signal replaced below
    c, h, l = frame.Close, frame.High, frame.Low
    trend = c > c.rolling(200).mean()
    if family == "aroon":
        up = h.rolling(26).apply(lambda x: np.argmax(x) / 25 * 100, raw=True)
        down = l.rolling(26).apply(lambda x: np.argmin(x) / 25 * 100, raw=True)
        signal = (up > down) & (up.shift(1) <= down.shift(1)) & (up >= 70) & trend
    elif family == "williams":
        upper, lower = h.rolling(14).max(), l.rolling(14).min()
        wr = -100 * (upper - c) / (upper - lower).replace(0, np.nan)
        signal = (wr > -80) & (wr.shift(1) <= -80) & trend
    elif family == "ichimoku":
        tenkan = (h.rolling(9).max() + l.rolling(9).min()) / 2
        kijun = (h.rolling(26).max() + l.rolling(26).min()) / 2
        span_a = ((tenkan + kijun) / 2).shift(26)
        span_b = ((h.rolling(52).max() + l.rolling(52).min()) / 2).shift(26)
        cloud = pd.concat([span_a, span_b], axis=1).max(axis=1)
        # No backward-displaced Chikou column or future cloud access.
        signal = (c > cloud) & (c.shift(1) <= cloud.shift(1)) & (tenkan > kijun)
    elif family == "psar":
        direction = psar_direction(h, l, c)
        signal = (direction > 0) & (direction.shift(1) < 0) & trend
    elif family == "trix":
        e = c.ewm(span=15, adjust=False, min_periods=15).mean()
        e = e.ewm(span=15, adjust=False, min_periods=15).mean()
        e = e.ewm(span=15, adjust=False, min_periods=15).mean()
        trix = e.pct_change(fill_method=None)
        signal = (trix > 0) & (trix.shift(1) <= 0) & trend
    elif family == "awesome":
        mid = (h + l) / 2
        ao = mid.rolling(5).mean() - mid.rolling(34).mean()
        signal = (ao > 0) & (ao.shift(1) <= 0) & trend
    else:
        center = c.ewm(span=20, adjust=False, min_periods=20).mean()
        upper = center + 2 * ta.atr(h, l, c, length=20)
        signal = (c > upper) & (c.shift(1) <= upper.shift(1)) & trend
    out["SIGNAL"] = signal.fillna(False)
    out.iloc[: 200 if family != "ichimoku" else 78, out.columns.get_loc("SIGNAL")] = (
        False
    )
    return out


def hysteresis(close, width=0.03):
    average = close.rolling(200).mean()
    state, values = False, []
    for price, ma in zip(close, average):
        if np.isfinite(ma):
            if price > ma * (1 + width):
                state = True
            elif price < ma * (1 - width):
                state = False
        values.append(state)
    return pd.Series(values, index=close.index)
