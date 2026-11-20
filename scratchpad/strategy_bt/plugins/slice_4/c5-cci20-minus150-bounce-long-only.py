"""CCI oversold bounce; close-confirmed signals and fixed percent stop."""
import numpy as np
import pandas as pd

SPEC_ID = "c5-cci20-minus150-bounce-long-only"
PARAMS = {"cci_len": 20, "entry_level": -150.0, "exit_level": 150.0, "min_body": 0.0025, "stop": 0.08}
PARAM_GRID = {"entry_level": [-160.0, -150.0, -140.0]}
TIMEFRAMES = ["1h", "4h"]
SIDES = "long"
DEVIATIONS = [
    "The spec's prior-bar CCI < -150 condition is combined with a rising CCI on the signal bar, as stated literally.",
    "CCI uses typical price (H+L+C)/3 and the standard rolling mean absolute deviation formula.",
    "Harness executes at next open; its fixed stop_pct is set to 8% of fill price, approximating the spec's entry-price stop.",
    "Harness universe replaces any source chart-specific market selection."
]
IMPLEMENTED_FIELDS = ["entry_long", "exit", "stop_loss", "timeframes"]


def _cci(df, n):
    typical = (df.high.to_numpy(float) + df.low.to_numpy(float) + df.close.to_numpy(float)) / 3.0
    s = pd.Series(typical)
    mean = s.rolling(n, min_periods=n).mean()
    mad = s.rolling(n, min_periods=n).apply(lambda x: np.mean(np.abs(x - np.mean(x))), raw=True)
    return ((s - mean) / (0.015 * mad)).to_numpy()


def signals(df, cci_len=20, entry_level=-150.0, exit_level=150.0, min_body=0.0025, stop=0.08, **_):
    cci = _cci(df, int(cci_len))
    prev = np.r_[np.nan, cci[:-1]]
    body = df.close.to_numpy(float) / df.open.to_numpy(float) - 1.0
    entry = (prev < float(entry_level)) & (cci > prev) & (body >= float(min_body))
    exit_ = cci > float(exit_level)
    return pd.DataFrame({"long_entry": entry, "short_entry": False, "long_exit": exit_, "short_exit": False,
                         "stop_pct": float(stop)}, index=df.index).fillna(False)
