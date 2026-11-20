import numpy as np,pandas as pd
from common.indicators import atr
SPEC_ID='turtle-system-2'; PARAMS={'entry_n':55,'exit_n':20,'n_len':20,'stop_n':2.0}; PARAM_GRID={'entry_n':[40,55,70],'exit_n':[10,20,30]}; TIMEFRAMES=['1d']; SIDES='both'
DEVIATIONS=['Engine generalizes instrument list across its primary universe.','Close-confirmed breakouts with next-open fills approximate the source intraday stop break.','Fixed-notional engine cannot implement volatility-normalized unit sizing.','Engine cannot add favorable-move pyramids; its ladder only adds against a position.']
IMPLEMENTED_FIELDS=['entry_long','entry_short','exit','stop_loss','timeframes']
def signals(df,entry_n=55,exit_n=20,n_len=20,stop_n=2.0,**kw):
 eh=df.high.rolling(int(entry_n),min_periods=int(entry_n)).max().shift(1); el=df.low.rolling(int(entry_n),min_periods=int(entry_n)).min().shift(1); xh=df.high.rolling(int(exit_n),min_periods=int(exit_n)).max().shift(1); xl=df.low.rolling(int(exit_n),min_periods=int(exit_n)).min().shift(1); a=atr(df.high,df.low,df.close,int(n_len))*float(stop_n)
 return pd.DataFrame({'long_entry':df.close>eh,'short_entry':df.close<el,'long_exit':df.close<xl,'short_exit':df.close>xh,'atr_stop':a},index=df.index).fillna({'long_entry':False,'short_entry':False,'long_exit':False,'short_exit':False})
