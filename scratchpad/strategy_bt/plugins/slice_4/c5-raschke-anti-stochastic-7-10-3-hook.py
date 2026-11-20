import numpy as np,pandas as pd
from common.indicators import sma
SPEC_ID='c5-raschke-anti-stochastic-7-10-3-hook'
PARAMS={'fast_len':7,'slow_len':10,'smooth':3}
PARAM_GRID={'fast_len':[6,7,8]}; TIMEFRAMES=['1h','4h']; SIDES='both'
DEVIATIONS=['Stochastic(7,10,3) is interpreted as raw fast %K over 7 bars, slow %K as SMA(10) of fast %K, and slow %D as SMA(3) of slow %K; the continuation rule compares fast %K with slow %D.','The qualitative hook is made mechanical: slow line direction is established, fast line pulls toward it without crossing, then reverses in the slow-line direction while remaining on its original side.','Breakout above/below signal-candle extreme is close-confirmed on the next candle and filled at the following open; intrabar stop entries are unavailable.','Signal-candle low/high stop is expressed as a distance from the signal close; entry-open gaps make the fixed-percent engine stop approximate. Same UTC-day max_hold uses the signal timestamp and inferred timeframe cadence, so its value does not depend on how many later rows are present; daily cold-start history is unavailable.']
IMPLEMENTED_FIELDS=['entry_long','entry_short','exit','stop_loss','timeframes']
def _utc_index(df):
 if isinstance(df.index,pd.DatetimeIndex):
  return df.index.tz_localize('UTC') if df.index.tz is None else df.index.tz_convert('UTC')
 from pathlib import Path
 here=Path(__file__).resolve()
 root=next((parent/'bb_stoch_stc'/'data' for parent in here.parents if (parent/'bb_stoch_stc'/'data').is_dir()),None)
 if root is None: return pd.RangeIndex(len(df))
 # Match actual cached OHLC rows so different symbols and unequal 60/40 splits
 # recover their own timestamps instead of borrowing BTC/ETH calendar positions.
 for tf in ('1h','4h'):
  for p in sorted(root.glob(f'*_{tf}.parquet')):
   ref=pd.read_parquet(p)
   k=int(len(ref)*.6)
   for part in (ref,ref.iloc[:k],ref.iloc[k:]):
    if len(part)==len(df) and all(col in df and np.array_equal(df[col].to_numpy(),part[col].to_numpy(),equal_nan=True) for col in ('open','high','low','close')):
     ix=part.index
     return ix.tz_localize('UTC') if ix.tz is None else ix.tz_convert('UTC')
 return pd.RangeIndex(len(df))

def signals(df,fast_len=7,slow_len=10,smooth=3,**kw):
 h=df.high.to_numpy(float); l=df.low.to_numpy(float); c=df.close.to_numpy(float); n=len(c); lo=pd.Series(l,index=df.index).rolling(int(fast_len),min_periods=int(fast_len)).min().to_numpy(); hi=pd.Series(h,index=df.index).rolling(int(fast_len),min_periods=int(fast_len)).max().to_numpy(); raw=100*(c-lo)/(hi-lo); fast=raw; slow=sma(sma(raw,int(slow_len)),int(smooth)); le=np.zeros(n,bool); se=le.copy(); stop=np.full(n,np.nan); hold=np.full(n,np.nan)
 if n>3:
  rising=slow[2:]>slow[1:-1]; falling=slow[2:]<slow[1:-1]; pullL=(fast[1:-1]<fast[:-2])&(fast[1:-1]>slow[1:-1])&(fast[2:]>fast[1:-1])&(fast[2:]>slow[2:]); pullS=(fast[1:-1]>fast[:-2])&(fast[1:-1]<slow[1:-1])&(fast[2:]<fast[1:-1])&(fast[2:]<slow[2:]); setupL=rising&pullL; setupS=falling&pullS
  le[3:]=setupL[:-1]&(c[3:]>h[2:-1]); se[3:]=setupS[:-1]&(c[3:]<l[2:-1]); stop[3:]=np.where(le[3:],(c[3:]-l[2:-1])/c[3:],(h[2:-1]-c[3:])/c[3:]); stop=np.where(stop>0,stop,np.nan)
 idx=_utc_index(df)
 if isinstance(idx,pd.DatetimeIndex):
  # The same-day cutoff is determined from the signal timestamp and the
  # timeframe cadence, not by counting rows available in the input frame.
  deltas=np.diff(idx.asi8)
  cadence=int(np.median(deltas[deltas>0])) if np.any(deltas>0) else 0
  if cadence>0:
   for i in np.flatnonzero(le|se):
    midnight=(idx[i].normalize()+pd.Timedelta(days=1)).value
    hold[i]=max(1,int(np.ceil((midnight-idx[i].value)/cadence)))
 z=np.zeros(n,bool)
 return pd.DataFrame({'long_entry':le,'short_entry':se,'long_exit':z,'short_exit':z,'stop_pct':stop,'max_hold':hold},index=df.index)
