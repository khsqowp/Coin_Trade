import numpy as np,pandas as pd
SPEC_ID='btc-donchian-37-6'; PARAMS={'entry_n':37,'exit_n':6}; PARAM_GRID={'entry_n':[30,37,45],'exit_n':[5,6,8]}; TIMEFRAMES=['1d']; SIDES='long'
DEVIATIONS=['Instrument list BTC is ignored; harness evaluates its primary universe.','Uses close-confirmed channel breaks and next-open fills; source describes a break that could be intrabar.']
IMPLEMENTED_FIELDS=['entry_long','exit','timeframes']
def signals(df,entry_n=37,exit_n=6,**kw):
 eh=df.high.rolling(int(entry_n),min_periods=int(entry_n)).max().shift(1); el=df.low.rolling(int(exit_n),min_periods=int(exit_n)).min().shift(1)
 return pd.DataFrame({'long_entry':df.close>eh,'short_entry':False,'long_exit':df.close<el,'short_exit':False},index=df.index).fillna(False)
