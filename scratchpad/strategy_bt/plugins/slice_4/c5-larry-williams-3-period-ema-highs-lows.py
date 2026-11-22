import numpy as np
import pandas as pd
from common.indicators import ema

SPEC_ID = "c5-larry-williams-3-period-ema-highs-lows"
PARAMS = {"length": 3}
PARAM_GRID = {"length": [2, 3, 4]}
TIMEFRAMES = ["1h"]
SIDES = "long"
DEVIATIONS = [
    "The archived helper used security() lookahead_on; implementation evaluates EMA(3) of the chart's confirmed high/low series causally at bar close, as directed by the archived implementation note.",
    "No stop or short rule is present in the archived specification.",
]
IMPLEMENTED_FIELDS = ["entry_long", "exit", "timeframes"]

def signals(df, length=3):
    n = int(length)
    eh = ema(df.high.to_numpy(float), n)
    el = ema(df.low.to_numpy(float), n)
    c = df.close.to_numpy(float)
    z = np.zeros(len(df), bool)
    return pd.DataFrame({"long_entry": c < el, "short_entry": z, "long_exit": c > eh, "short_exit": z}, index=df.index).fillna(False)
