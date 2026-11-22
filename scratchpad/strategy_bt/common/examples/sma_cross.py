"""Minimal causal SMA crossover plugin."""
import numpy as np
import pandas as pd
from common.indicators import sma

SPEC_ID="example-sma-cross"
PARAMS={"fast":5,"slow":18}
PARAM_GRID={"fast":[4,6],"slow":[16,20]}
TIMEFRAMES=["4h"]
SIDES="both"
DEVIATIONS=["Example fixture strategy; not asserted to reproduce an archived specification."]
IMPLEMENTED_FIELDS=["entry_long","entry_short","exit","timeframes"]

def signals(df, fast=5, slow=18):
    c=df.close.to_numpy(float); f=sma(c,int(fast)); s=sma(c,int(slow))
    up=np.r_[False,(f[1:]>s[1:])&(f[:-1]<=s[:-1])]; down=np.r_[False,(f[1:]<s[1:])&(f[:-1]>=s[:-1])]
    z=np.zeros(len(df),bool)
    return pd.DataFrame({"long_entry":up,"short_entry":down,"long_exit":down,"short_exit":up},index=df.index).fillna(False)
