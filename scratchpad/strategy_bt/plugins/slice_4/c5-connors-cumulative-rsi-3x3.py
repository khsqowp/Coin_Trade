import numpy as np
import pandas as pd

SPEC_ID = "c5-connors-cumulative-rsi-3x3"
PARAMS = {"entry": 60, "exit": 282}
PARAM_GRID = {"entry": [55, 60, 65], "exit": [270, 282, 294]}
TIMEFRAMES = ["1h", "4h"]
SIDES = "long"
DEVIATIONS = [
    "The archived source specifies RSI(3) and a three-bar sum; Wilder RSI uses the conventional Wilder recursive smoothing seeded by the first three-period average gains/losses.",
    "The optional EMA(100) filter defaults false and is therefore omitted.",
    "The source's specified cross-up entry (< threshold then >= threshold) is preserved despite differing from classic Connors entry semantics.",
]
IMPLEMENTED_FIELDS = ["entry_long", "exit", "filters", "timeframes"]

def _rsi_wilder(close, n=3):
    c = np.asarray(close, float)
    d = np.diff(c, prepend=np.nan)
    gain = np.where(d > 0, d, 0.0); loss = np.where(d < 0, -d, 0.0)
    gain[0] = loss[0] = np.nan
    ag = np.full(len(c), np.nan); al = np.full(len(c), np.nan)
    if len(c) > n:
        ag[n] = np.nanmean(gain[1:n+1]); al[n] = np.nanmean(loss[1:n+1])
        for i in range(n+1, len(c)):
            ag[i] = (ag[i-1]*(n-1)+gain[i])/n
            al[i] = (al[i-1]*(n-1)+loss[i])/n
    rs = np.divide(ag, al, out=np.full(len(c), np.inf), where=al != 0)
    out = 100. - 100./(1. + rs)
    out[al == 0] = 100.
    out[~np.isfinite(ag)] = np.nan
    return out

def signals(df, entry=60, exit=282):
    rsi = _rsi_wilder(df.close.to_numpy(float), 3)
    cum = pd.Series(rsi, index=df.index).rolling(3, min_periods=3).sum().to_numpy()
    prev = np.r_[np.nan, cum[:-1]]
    le = (prev < float(entry)) & (cum >= float(entry))
    lx = (prev < float(exit)) & (cum >= float(exit))
    z = np.zeros(len(df), bool)
    return pd.DataFrame({"long_entry": le, "short_entry": z, "long_exit": lx, "short_exit": z}, index=df.index).fillna(False)
