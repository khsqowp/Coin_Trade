import numpy as np
import pandas as pd
SPEC_ID="c5-nick-radge-bollinger-blast-unholy-grail"
PARAMS={"length":10,"entry_sd":3.0,"exit_sd":1.0}
PARAM_GRID={"length":[10],"entry_sd":[3.0],"exit_sd":[1.0]}
TIMEFRAMES=["1h","4h"]
SIDES="long"
DEVIATIONS=["The 10% initial capital loss is approximated as a 10% close-price drawdown from the signal close; exit fills next open.","The archived stop ID mismatch may make its source stop inactive; implemented as stated in stop_loss.","The price stop is stateful within signals and does not use per-bar stop columns."]
IMPLEMENTED_FIELDS=["entry_long","exit","stop_loss","timeframes","filters"]
def signals(df,length=10,entry_sd=3.0,exit_sd=1.0,**kw):
 c=df.close.to_numpy(float); s=pd.Series(c); m=s.rolling(int(length),min_periods=int(length)).mean().to_numpy(); sd=s.rolling(int(length),min_periods=int(length)).std(ddof=0).to_numpy(); hi=m+float(entry_sd)*sd; lo=m-float(exit_sd)*sd; prev=np.r_[np.nan,c[:-1]]
 cross=(prev<=np.r_[np.nan,hi[:-1]])&(c>hi); exit_cross=(prev>=np.r_[np.nan,lo[:-1]])&(c<lo)
 en=np.zeros(len(c),bool); ex=np.zeros(len(c),bool); in_pos=False; entry_price=np.nan
 for i in range(len(c)):
  if in_pos and (exit_cross[i] or c[i]<=entry_price*.9): ex[i]=True; in_pos=False
  elif not in_pos and cross[i]: en[i]=True; in_pos=True; entry_price=c[i]
 return pd.DataFrame({"long_entry":en,"short_entry":False,"long_exit":ex,"short_exit":False},index=df.index).fillna(False)
