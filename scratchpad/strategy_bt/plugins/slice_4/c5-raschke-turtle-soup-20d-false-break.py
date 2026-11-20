import numpy as np,pandas as pd
SPEC_ID="c5-raschke-turtle-soup-20d-false-break"
PARAMS={"lookback":20,"age_days":3,"reentry_points":10.0,"trail_points":60.0}
PARAM_GRID={"lookback":[20],"age_days":[3],"trail_points":[60.0]}
TIMEFRAMES=["1h"]
SIDES="both"
DEVIATIONS=["Daily ranges are aggregated from available UTC H1 bars; strategy explicitly requires D1 range/H1 entry and cached Upbit session candles are unavailable.","The archived 10 and 50-70 point values are treated literally as absolute quote-price units (10.0 and midpoint 60.0), with no instrument-specific conversion.","Entry on intrabar range return is approximated by close crossing the re-entry threshold and fills at next open.","A 60-point trailing stop based on the post-entry favorable extreme is emitted as a close signal, so harness fills next open; initial stop is beyond the false-break extreme and cannot be represented as a position-dependent price stop.","Cached UTC timestamps are restored for RangeIndex train/test frames by matching their lengths to the 1h reference index; TEST begins without prior-session history."]
IMPLEMENTED_FIELDS=["entry_long","entry_short","exit","stop_loss","timeframes","filters"]
def _utc_index(df):
 if isinstance(df.index,pd.DatetimeIndex): return df.index.tz_localize("UTC") if df.index.tz is None else df.index.tz_convert("UTC")
 from pathlib import Path
 here=Path(__file__).resolve(); data=next((q/"bb_stoch_stc"/"data" for q in here.parents if (q/"bb_stoch_stc"/"data").is_dir()),None)
 if data is None: raise RuntimeError("cached data directory not found for timestamp restoration")
 ref=pd.read_parquet(data/"BTCUSDT_1h.parquet",columns=["close"]).index; n=len(df); k=int(len(ref)*.6)
 for size,idx in ((len(ref),ref),(k,ref[:k]),(len(ref)-k,ref[k:])):
  if n==size:return pd.DatetimeIndex(idx)
 raise ValueError("cannot restore UTC index for this slice length")
def signals(df,lookback=20,age_days=3,reentry_points=10.,trail_points=60.,**kw):
 idx=_utc_index(df); c=df.close.to_numpy(float); h=df.high.to_numpy(float); l=df.low.to_numpy(float); day=idx.normalize(); daily=pd.DataFrame({"h":h,"l":l},index=idx).groupby(day).agg({"h":"max","l":"min"}); dh=daily.h.to_numpy(); dl=daily.l.to_numpy(); dates=daily.index;
 highs=np.full(len(dh),np.nan); lows=highs.copy(); ages_h=np.zeros(len(dh),int); ages_l=np.zeros(len(dh),int)
 for j in range(len(dh)):
  if j>=lookback:
   a=j-lookback; b=j; hs=dh[a:b]; ls=dl[a:b]; highs[j]=np.max(hs); lows[j]=np.min(ls); ages_h[j]=j-1-int(np.flatnonzero(hs==highs[j])[-1]+a); ages_l[j]=j-1-int(np.flatnonzero(ls==lows[j])[-1]+a)
 # threshold for current session comes only from completed earlier daily bars
 mapidx={d:i for i,d in enumerate(dates)}; le=np.zeros(len(c),bool); se=le.copy(); lx=le.copy(); sx=le.copy(); state=0; extreme=np.nan; peak=np.nan
 for i,d in enumerate(day):
  j=mapidx[d]
  if j>=len(dh) or not np.isfinite(highs[j]): continue
  oldlo=lows[j]; oldhi=highs[j]; validlo=ages_l[j]>=age_days; validhi=ages_h[j]>=age_days
  if state==0:
   if validlo and l[i]<oldlo: state=1; extreme=l[i]
   elif validhi and h[i]>oldhi: state=-1; extreme=h[i]
  elif state==1:
   extreme=min(extreme,l[i])
   if c[i]>=oldlo+reentry_points: le[i]=True; state=2; peak=c[i]
  elif state==-1:
   extreme=max(extreme,h[i])
   if c[i]<=oldhi-reentry_points: se[i]=True; state=-2; peak=c[i]
  elif state==2:
   peak=max(peak,h[i]); lx[i]=c[i]<=peak-trail_points
   if lx[i]:state=0
  elif state==-2:
   peak=min(peak,l[i]); sx[i]=c[i]>=peak+trail_points
   if sx[i]:state=0
 return pd.DataFrame({"long_entry":le,"short_entry":se,"long_exit":lx,"short_exit":sx},index=df.index).fillna(False)
