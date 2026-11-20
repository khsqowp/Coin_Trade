"""Daily BTC upper Bollinger breakout with center-line exit."""
import pandas as pd
from common.indicators import bollinger

SPEC_ID = "btc-bollinger-37-16"
PARAMS = {"n": 37, "k": 1.6}
PARAM_GRID = {"n": [30, 37, 45], "k": [1.4, 1.6, 1.8]}
TIMEFRAMES = ["1d"]
SIDES = "long"
DEVIATIONS = [
    "The archived source leaves its volatility measure undefined; population standard deviation is assumed.",
    "The archived short entry returning to the center moving average is treated as the long exit, consistent with its long-only filter.",
    "Signals execute at the next open under the harness.",
]
IMPLEMENTED_FIELDS = ["entry_long", "entry_short", "exit", "filters", "timeframes"]


def signals(df, n=37, k=1.6):
    close = pd.to_numeric(df["close"], errors="coerce").to_numpy(float)
    mid, upper, _ = bollinger(close, int(n), float(k))
    c = pd.Series(close, index=df.index)
    mid = pd.Series(mid, index=df.index)
    upper = pd.Series(upper, index=df.index)
    entry = (c > upper) & (c.shift(1) <= upper.shift(1))
    exit_ = c <= mid
    return pd.DataFrame({"long_entry": entry, "short_entry": False, "long_exit": exit_, "short_exit": False}, index=df.index).fillna(False).astype(bool)
