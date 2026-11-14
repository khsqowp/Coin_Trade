"""Deterministic causal indicators (value at bar t uses bars <= t only). Shared by regime features and the strategy pool."""
import numpy as np
import pandas as pd


def sma(s, n):
    return s.rolling(n, min_periods=n).mean()


def ema(s, n):
    return s.ewm(span=n, adjust=False, min_periods=n).mean()


def true_range(df):
    pc = df["close"].shift(1)
    return pd.concat([df["high"] - df["low"], (df["high"] - pc).abs(), (df["low"] - pc).abs()], axis=1).max(axis=1)


def atr(df, n=14):
    return true_range(df).ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()


def rsi(s, n=14):
    d = s.diff()
    up = d.clip(lower=0).ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()
    rs = up / dn.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50.0).where(up.notna())


def bollinger(s, n=20, k=2.0):
    m = sma(s, n)
    sd = s.rolling(n, min_periods=n).std(ddof=0)
    return m, m + k * sd, m - k * sd


def roc(s, n):
    return s / s.shift(n) - 1.0


def donchian_high(df, n):
    """Highest high of the PREVIOUS n bars (excludes the current bar)."""
    return df["high"].shift(1).rolling(n, min_periods=n).max()


def donchian_low(df, n):
    return df["low"].shift(1).rolling(n, min_periods=n).min()


def px_features(df):
    """Latest-bar feature dict from a closed-bar OHLCV frame (all causal)."""
    c = df["close"]
    f = {}
    e20, e50 = ema(c, 20), ema(c, 50)
    s200 = sma(c, 200)
    last = lambda x: (None if pd.isna(x.iloc[-1]) else float(x.iloc[-1]))
    f["close"] = last(c)
    f["trend_ema20_vs_ema50_pct"] = None if e50.iloc[-1] != e50.iloc[-1] else round(float(e20.iloc[-1] / e50.iloc[-1] - 1) * 100, 3)
    f["close_vs_sma200_pct"] = None if pd.isna(s200.iloc[-1]) else round(float(c.iloc[-1] / s200.iloc[-1] - 1) * 100, 3)
    f["ema20_slope_10bars_pct"] = None if pd.isna(e20.iloc[-1]) or len(e20) < 11 else round(float(e20.iloc[-1] / e20.iloc[-11] - 1) * 100, 3)
    r10 = roc(c, 10)
    f["momentum_roc10_pct"] = None if pd.isna(r10.iloc[-1]) else round(float(r10.iloc[-1]) * 100, 3)
    acc = r10 - r10.shift(10)
    f["momentum_accel_pct"] = None if pd.isna(acc.iloc[-1]) else round(float(acc.iloc[-1]) * 100, 3)
    a = atr(df, 14)
    f["atr14_pct"] = None if pd.isna(a.iloc[-1]) else round(float(a.iloc[-1] / c.iloc[-1]) * 100, 4)
    ret = c.pct_change()
    v20, v100 = ret.tail(20).std(), ret.tail(100).std()
    f["realized_vol_ratio_20_vs_100"] = None if not v100 or v100 != v100 else round(float(v20 / v100), 3)
    vol = df["volume"]
    v10, v50 = vol.tail(10).mean(), vol.tail(50).mean()
    f["volume_change_10_vs_50_pct"] = None if not v50 else round(float(v10 / v50 - 1) * 100, 2)
    f["drawdown_from_90bar_high_pct"] = round(float(c.iloc[-1] / c.tail(90).max() - 1) * 100, 2)
    return f
