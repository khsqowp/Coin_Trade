import numpy as np
import pandas as pd
SPEC_ID="crypto-15m-previous-candle-contrarian"
PARAMS={}; PARAM_GRID={}; TIMEFRAMES=["15m"]; SIDES="both"
DEVIATIONS=["Harness enters at next open and exits at the following open; because it cannot re-enter on the exit-fill bar, eligible trades are a subsample, about every other interval.","Harness round-trip fee plus slippage is 0.12%, exceeding the archived roughly 1.3 bp gross edge.","Archived instrument list is ignored by harness universe."]
IMPLEMENTED_FIELDS=["entry_long","entry_short","exit","timeframes"]
def signals(df,**params):
    r=df.close.pct_change().to_numpy(float)
    return pd.DataFrame({"long_entry":r<0,"short_entry":r>0,"long_exit":True,"short_exit":True},index=df.index).fillna(False)
