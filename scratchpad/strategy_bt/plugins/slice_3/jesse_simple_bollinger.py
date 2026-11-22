import numpy as np,pandas as pd
from common.indicators import bollinger
SPEC_ID='jesse_simple_bollinger'; PARAMS={'bb_len':20,'bb_k':2.,'conv':9,'base':26,'span_b':52,'disp':26}; PARAM_GRID={'bb_len':[15,20,25],'bb_k':[1.5,2.,2.5]}; TIMEFRAMES=['1h']; SIDES='long'
DEVIATIONS=['Ichimoku cloud displacement is interpreted causally: value at t comes from computed span at t-disp; Jesse displacement semantics were not verified.','Harness uses fixed notional rather than source all-in sizing.','Source instrument universe is generalized by harness.']
IMPLEMENTED_FIELDS=['entry_long','exit','filters','timeframes']
def signals(df,bb_len=20,bb_k=2.,conv=9,base=26,span_b=52,disp=26,**kw):
 h=df.high; l=df.low; c=df.close; hl2=((h+l)/2).to_numpy(float); mid,upper,_=bollinger(hl2,int(bb_len),float(bb_k))
 convv=(h.rolling(int(conv),min_periods=int(conv)).max()+l.rolling(int(conv),min_periods=int(conv)).min())/2; basev=(h.rolling(int(base),min_periods=int(base)).max()+l.rolling(int(base),min_periods=int(base)).min())/2; sa=((convv+basev)/2).shift(int(disp)); sb=((h.rolling(int(span_b),min_periods=int(span_b)).max()+l.rolling(int(span_b),min_periods=int(span_b)).min())/2).shift(int(disp))
 return pd.DataFrame({'long_entry':(c.to_numpy()>upper)&(c.to_numpy()>sa.to_numpy())&(c.to_numpy()>sb.to_numpy()),'short_entry':False,'long_exit':c.to_numpy()<mid,'short_exit':False},index=df.index).fillna(False)
