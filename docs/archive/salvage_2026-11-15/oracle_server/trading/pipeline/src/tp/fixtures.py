"""Benchmark fixtures: strategy code with seeded defects (B*) and clean code (C*)."""

LEAK = ("lookahead_bias", "data_leakage")
FIXTURES = {
    "B1_shift_neg": {"label": "buggy", "accept": LEAK, "code": '''import pandas as pd

def generate_signals(df):
    # long when the next bar closes higher than the current one
    up_tomorrow = df["close"].shift(-1) > df["close"]
    return up_tomorrow.astype(float)
'''},
    "B2_centered_ma": {"label": "buggy", "accept": LEAK, "code": '''import pandas as pd

def generate_signals(df):
    ma = df["close"].rolling(21, center=True).mean()
    sig = (df["close"] > ma).astype(float)
    return sig.fillna(0.0)
'''},
    "B3_fullsample_zscore": {"label": "buggy", "accept": LEAK, "code": '''import pandas as pd

def generate_signals(df):
    c = df["close"]
    z = (c - c.mean()) / c.std()          # normalise price
    # buy deep dips, sell when back above average
    sig = (z < -0.5).astype(float)
    return sig
'''},
    "B4_fullsample_param_fit": {"label": "buggy", "accept": LEAK + ("overfitting",), "code": '''import pandas as pd

def generate_signals(df):
    c = df["close"]
    ret = c.pct_change().fillna(0.0)
    best_w, best_r = 20, -1e9
    for w in range(5, 120):
        s = (c > c.rolling(w).mean()).astype(float)
        r = float((s.shift(1).fillna(0.0) * ret).sum())
        if r > best_r:
            best_w, best_r = w, r
    return (c > c.rolling(best_w).mean()).astype(float)
'''},
    "B5_weekly_bfill": {"label": "buggy", "accept": LEAK, "code": '''import pandas as pd

def generate_signals(df):
    weekly = df["close"].resample("W").last()
    wk_trend = (weekly > weekly.rolling(10).mean()).astype(float)
    # map weekly signal back to daily bars
    sig = wk_trend.reindex(df.index, method="bfill")
    return sig.fillna(0.0)
'''},
    "B6_fullsample_quantile": {"label": "buggy", "accept": LEAK, "code": '''import pandas as pd

def generate_signals(df):
    ret = df["close"].pct_change()
    thr = ret.quantile(0.90)              # "big up day" threshold
    big_up = ret > thr
    # stay long for 3 bars after a big up day
    sig = big_up.rolling(3, min_periods=1).max().fillna(0.0)
    return sig.astype(float)
'''},
    "B7_anchor_last_close": {"label": "buggy", "accept": LEAK, "code": '''import pandas as pd

def generate_signals(df):
    c = df["close"]
    anchor = c.iloc[-1]                    # latest price as the reference level
    cheap = c < 0.9 * anchor
    trend = c > c.rolling(30).mean()
    return (cheap & trend).astype(float)
'''},
    "C1_sma_cross": {"label": "clean", "accept": (), "code": '''import pandas as pd

FAST, SLOW = 20, 50

def generate_signals(df):
    c = df["close"]
    fast = c.rolling(FAST).mean()
    slow = c.rolling(SLOW).mean()
    return (fast > slow).astype(float)
'''},
    "C2_rsi_meanrev": {"label": "clean", "accept": (), "code": '''import numpy as np
import pandas as pd

def generate_signals(df):
    d = df["close"].diff()
    gain = d.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    loss = (-d.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    rsi = 100 - 100 / (1 + gain / loss)
    state, out = 0.0, []
    for v in rsi.values:
        if not np.isnan(v):
            if v < 30:
                state = 1.0
            elif v > 55:
                state = 0.0
        out.append(state)
    return pd.Series(out, index=df.index)
'''},
    "C3_donchian": {"label": "clean", "accept": (), "code": '''import numpy as np
import pandas as pd

def generate_signals(df):
    c = df["close"]
    hi = c.rolling(20).max().shift(1)     # prior 20-bar high, excludes current bar
    lo = c.rolling(10).min().shift(1)
    state, out = 0.0, []
    for price, h, l in zip(c.values, hi.values, lo.values):
        if not np.isnan(h) and price > h:
            state = 1.0
        elif not np.isnan(l) and price < l:
            state = 0.0
        out.append(state)
    return pd.Series(out, index=df.index)
'''},
    "C4_vol_filtered_trend": {"label": "clean", "accept": (), "code": '''import pandas as pd

def generate_signals(df):
    c = df["close"]
    ret = c.pct_change()
    vol = ret.rolling(20).std()
    calm = vol < vol.rolling(100).median()
    trend = c > c.rolling(50).mean()
    return (calm & trend).astype(float)
'''},
    "C5_expanding_zscore": {"label": "clean", "accept": (), "code": '''import pandas as pd

def generate_signals(df):
    c = df["close"]
    mu = c.expanding(min_periods=100).mean()
    sd = c.expanding(min_periods=100).std()
    z = (c - mu) / sd                      # uses only data up to and including bar t
    return (z.between(-0.5, 1.5)).astype(float)
'''},
    "C6_weekly_lagged": {"label": "clean", "accept": (), "code": '''import pandas as pd

def generate_signals(df):
    weekly = df["close"].resample("W").last()
    wk_trend = (weekly > weekly.rolling(10).mean()).astype(float).shift(1)   # only completed prior weeks
    sig = wk_trend.reindex(df.index, method="ffill")
    return sig.fillna(0.0)
'''},
}

CODEGEN_SPECS = {
    "sma": ("Write a Python module defining generate_signals(df) -> pandas.Series for a long/flat strategy. "
            "df has a UTC DatetimeIndex and float columns open, high, low, close, volume. "
            "Rule: output 1.0 when SMA(close, 10) > SMA(close, 30), else 0.0. Bars where either SMA is undefined output 0.0. "
            "The returned Series must have exactly df's index, dtype float, values only 0.0 or 1.0, no NaN. "
            "The signal at bar t may use only data up to and including bar t (a separate engine executes it at the next bar's open, "
            "so do not shift for execution). Do not mutate df. Only pandas/numpy. Reply with ONE ```python code block and nothing else."),
    "rsi": ("Write a Python module defining generate_signals(df) -> pandas.Series for a long/flat strategy. "
            "df has a UTC DatetimeIndex and float columns open, high, low, close, volume. "
            "Compute RSI(14) with Wilder smoothing: gains/losses from close.diff(), each smoothed with ewm(alpha=1/14, adjust=False). "
            "State machine starting flat (0.0): enter long (1.0) when RSI < 30; exit to flat (0.0) when RSI > 55; otherwise keep the previous state. "
            "Bars with undefined RSI keep the current state. The returned Series must have exactly df's index, dtype float, values only 0.0/1.0, no NaN. "
            "The signal at bar t may use only data up to and including bar t (the engine executes at the next open; do not shift for execution). "
            "Do not mutate df. Only pandas/numpy. Reply with ONE ```python code block and nothing else."),
}
