import numpy as np
import pandas as pd
from common.indicators import bollinger
SPEC_ID="c5-bb-percent-b-21-meanrev-1.2-lines"
PARAMS={"length":21,"stdev":2.0}
PARAM_GRID={"length":[21],"stdev":[2.0]}
TIMEFRAMES=["1h","4h"]
SIDES="both"
DEVIATIONS=["20% equity sizing is not modeled; harness uses fixed notional.","Entry and exit thresholds are literal level conditions (not cross events), as the archived wording says when %B is below/above the level."]
IMPLEMENTED_FIELDS=["entry_long","entry_short","exit","timeframes","filters"]
def signals(df,length=21,stdev=2.0,**kw):
 c=df.close.to_numpy(float); mid,up,lo=bollinger(c,int(length),float(stdev)); b=(c-lo)/(up-lo); b=np.where((up==lo)|~np.isfinite(up),np.nan,b)
 z=np.zeros(len(df),bool); return pd.DataFrame({"long_entry":b<-.2,"short_entry":b>1.2,"long_exit":b>=.2,"short_exit":b<=1.0},index=df.index).fillna(False)
