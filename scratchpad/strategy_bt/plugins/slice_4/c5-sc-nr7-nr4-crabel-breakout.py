import numpy as np,pandas as pd
from common.indicators import atr
SPEC_ID='c5-sc-nr7-nr4-crabel-breakout'
PARAMS={'nr7_n':7,'nr4_n':4,'n_len':14}
PARAM_GRID={'nr7_n':[6,7,8]}; TIMEFRAMES=['1d']; SIDES='both'
DEVIATIONS=['A bar qualifies when its high-low range is a strict minimum over the preceding NR window including itself; NR7 and NR4 are combined.','Breakout is approximated by a close beyond the most recent qualifying bar extreme, then next-open execution; the engine cannot place resting stop orders.','Opposite side of the narrow-range bar is implemented as fixed stop distance measured from breakout signal close, so next-open gaps alter the intended stop level.','The source permits first-day close or first profitable close. This implementation uses a one-bar maximum hold as the literal first-day exit.']
IMPLEMENTED_FIELDS=['entry_long','entry_short','exit','stop_loss','timeframes']
def signals(df,nr7_n=7,nr4_n=4,n_len=14,**kw):
 h=df.high.to_numpy(float); l=df.low.to_numpy(float); c=df.close.to_numpy(float); r=h-l; nr=np.zeros(len(df),bool)
 for k in {int(nr7_n),int(nr4_n)}:
  mn=pd.Series(r,index=df.index).rolling(k,min_periods=k).min().to_numpy(); nr|=(r==mn)
 top=np.full(len(df),np.nan); bot=top.copy()
 for i in range(len(df)):
  prior=np.flatnonzero(nr[:i])
  if len(prior): top[i]=h[prior[-1]]; bot[i]=l[prior[-1]]
 le=(c>top)&(np.r_[False,c[:-1]<=np.nan_to_num(top[:-1],nan=np.inf)]); se=(c<bot)&(np.r_[False,c[:-1]>=np.nan_to_num(bot[:-1],nan=-np.inf)])
 # stop distance derives from the prior NR day low/high and the signal close
 stop=np.where(le,(c-bot)/c,np.where(se,(top-c)/c,np.nan)); stop=np.where(stop>0,stop,np.nan); mh=np.where(le|se,1,np.nan); z=np.zeros(len(df),bool)
 return pd.DataFrame({'long_entry':le,'short_entry':se,'long_exit':z,'short_exit':z,'stop_pct':stop,'max_hold':mh},index=df.index)
