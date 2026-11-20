import numpy as np,pandas as pd
from common.indicators import ema
SPEC_ID='pk_double_ema'; PARAMS={'fast':9,'slow':21,'trend':200,'stop':.20}; PARAM_GRID={'fast':[7,9,12],'slow':[18,21,26]}; TIMEFRAMES=['1h']; SIDES='long'
DEVIATIONS=['ROI table is referenced as see source and is not specified in the archived JSON; no target is implemented.','Harness primary universe replaces source universe.']
IMPLEMENTED_FIELDS=['entry_long','exit','stop_loss','filters','timeframes']
def signals(df,fast=9,slow=21,trend=200,stop=.20,**kw):
 c=df.close.to_numpy(float); f=ema(c,int(fast)); s=ema(c,int(slow)); t=ema(c,int(trend)); low=df.low.to_numpy(float); up=np.r_[False,(f[1:]>s[1:])&(f[:-1]<=s[:-1])]; dn=np.r_[False,(f[1:]<s[1:])&(f[:-1]>=s[:-1])];
 return pd.DataFrame({'long_entry':up&(low>t),'short_entry':False,'long_exit':dn|(low<t),'short_exit':False,'stop_pct':float(stop)},index=df.index).fillna(False)
