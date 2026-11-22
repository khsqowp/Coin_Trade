"""Daily simple ROC threshold long trend rule."""
import pandas as pd

SPEC_ID = "btc-roc-36-9pct"
PARAMS = {"n": 36, "thr": 0.09}
PARAM_GRID = {"n": [30, 36, 42], "thr": [0.07, 0.09, 0.11]}
TIMEFRAMES = ["1d"]
SIDES = "long"
DEVIATIONS = [
    "The archived source calls this a 36-day return without specifying simple or log return; simple return close/close.shift(n)-1 is assumed.",
    "Signals execute at the next open under the harness.",
]
IMPLEMENTED_FIELDS = ["entry_long", "exit", "filters", "timeframes"]


def signals(df, n=36, thr=0.09):
    close = pd.to_numeric(df["close"], errors="coerce")
    roc = close / close.shift(int(n)) - 1.0
    entry = roc > float(thr)
    exit_ = roc <= float(thr)
    return pd.DataFrame({"long_entry": entry, "short_entry": False, "long_exit": exit_, "short_exit": False}, index=df.index).fillna(False).astype(bool)
