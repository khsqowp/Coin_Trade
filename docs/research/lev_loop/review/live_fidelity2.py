import json, pandas as pd, numpy as np
s=json.load(open("/private/tmp/claude-501/-Users-user-Desktop-CODE-Ochestration/b40d7700-4bab-493b-9b2c-b8bac464cd8e/scratchpad/live_state.json"))
eh=pd.DataFrame(s["equity_history"]); eh["ts"]=pd.to_datetime(eh["ts"],utc=True); eh=eh.set_index("ts")
E=eh.equity_usdt
# (1) 15s vs 5min undersampling factor on first 33h of 15-s data
E15=E["2026-09-25 04:58":"2026-09-25 23:59"]
print("15s samples:",len(E15), "median dt",E15.index.to_series().diff().dt.total_seconds().median())
def dips(x):
    g=x.groupby(x.index.floor("1h")); c=g.size(); ok=c[c>=3].index
    return ((g.last()-g.min())/g.last()).loc[ok]
d15=dips(E15)
E5s=E15.iloc[::18]            # ~ every 5 minutes
d5=dips(E5s)
common=d15.index.intersection(d5.index)
print("hours",len(common),"mean dip 15s %.4f vs 5min-sub %.4f  (ratio %.2f); p90 %.4f vs %.4f; max %.4f vs %.4f"%(d15[common].mean(),d5[common].mean(),d15[common].mean()/d5[common].mean(),d15[common].quantile(.9),d5[common].quantile(.9),d15[common].max(),d5[common].max()))
# (2) gross-3.8 windows only
w1=E["2026-09-25 06:00":"2026-10-11 09:00"]; w2=E["2026-10-24 10:00":]
for nm,w in (("W1 09-25..10-11 (gross~3.8)",w1),("W2 10-24..10-30 (gross~3.6)",w2),("W1 overlap with panel 09-25..10-09",E["2026-09-25 06:00":"2026-10-09 00:00"])):
    d=dips(w)
    g=w.groupby(w.index.floor("1h")); rng=((g.max()-g.min())/g.last())
    print(f"{nm}: hours {len(d)} dip mean {d.mean():.4f} p50 {d.median():.4f} p90 {d.quantile(.9):.4f} p99 {d.quantile(.99):.4f} max {d.max():.4f} | hourly range p50 {rng.median():.4f} p99 {rng.quantile(.99):.4f}")
# (3) running DD with different sampling (using HWM reset at 10-12 not applied) in W1 and W2 separately
def maxdd(x): hw=x.cummax(); dd=1-x/hw; return float(dd.max())
for nm,w in (("W1",w1),("W2",w2)):
    print(nm,"maxDD 5min %.4f | hourly-close %.4f | daily-close %.4f"%(maxdd(w),maxdd(w.resample('1h').last().dropna()),maxdd(w.resample('1D').last().dropna())))
