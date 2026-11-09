import json, pandas as pd, numpy as np, sys
s=json.load(open("/private/tmp/claude-501/-Users-user-Desktop-CODE-Ochestration/b40d7700-4bab-493b-9b2c-b8bac464cd8e/scratchpad/live_state.json"))
eh=pd.DataFrame(s["equity_history"]); eh["ts"]=pd.to_datetime(eh["ts"],utc=True); eh=eh.set_index("ts")
E=eh.equity_usdt
r=E.pct_change()
print("samples",len(E),E.index[0],E.index[-1])
print("largest 1-sample equity moves (pct):"); print(r.abs().sort_values(ascending=False).head(8).round(4).to_string())
# 5-min regular segment (from 2026-09-25 06:00)
E5=E["2026-09-25 06:00":]
# drop the halted days where positions flat (10-12 05:50 - 10-12 ~) keep all but mark
print("range:",E5.min(),E5.max())
def maxdd(x):
    hw=x.cummax(); return float((1-x/hw).max()), x.index[(1-x/hw).values.argmax()]
print("MaxDD raw (all samples, mixed 15s/5m):",maxdd(E))
print("MaxDD 5-min series:",maxdd(E5))
H1=E5.resample("1h").last().dropna(); print("MaxDD hourly-close subsample:",maxdd(H1))
D1=E5.resample("1D").last().dropna(); print("MaxDD daily-close subsample (00:00-23:59 UTC last):",maxdd(D1))
# within-hour wick: (close - min)/close , (max-min)/mean using 5-min samples
g=E5.groupby(E5.index.floor("1h"))
cnt=g.size(); ok=cnt[cnt>=9].index
mn=g.min().loc[ok]; mx=g.max().loc[ok]; last=g.last().loc[ok]; first=g.first().loc[ok]
drop=(last-mn)/last                         # how far below hourly close the 5-min path dipped
rng=(mx-mn)/last
print("hours",len(ok))
print("5-min dip below hourly close (last-min)/last: mean %.4f p50 %.4f p90 %.4f p99 %.4f max %.4f"%(drop.mean(),drop.median(),drop.quantile(.9),drop.quantile(.99),drop.max()))
print("5-min range per hour (max-min)/last: mean %.4f p50 %.4f p90 %.4f p99 %.4f max %.4f"%(rng.mean(),rng.median(),rng.quantile(.9),rng.quantile(.99),rng.max()))
# hourly close-to-close change distribution
hr=H1.pct_change().dropna()
print("hourly close-to-close ret: std %.4f min %.4f  p1 %.4f"%(hr.std(),hr.min(),hr.quantile(.01)))
# same for daily
print("daily ret: std %.4f min %.4f"%(D1.pct_change().std(),D1.pct_change().min()))
# live DD (trigger-style): max over hours of 1 - min5min / running max of ... compare 3 DD definitions
hw=E5.cummax()
dd5=(1-E5/hw)
H_hw=H1.cummax(); ddH=(1-H1/H_hw)
print("max dd: 5min %.4f | hourly-close %.4f | daily-close %.4f"%(dd5.max(),ddH.max(),(1-D1/D1.cummax()).max()))
# per day: worst 5-min dd vs the day-close dd
dday=pd.DataFrame({"dd5_min_in_day":dd5.groupby(dd5.index.floor("1D")).max()})
dday["dd_close"]=(1-D1/D1.cummax()).reindex(dday.index)
dday["gap"]=dday.dd5_min_in_day-dday.dd_close
print("daily: dd5(max within day) - dd(day close): mean %.4f p90 %.4f max %.4f"%(dday.gap.mean(),dday.gap.quantile(.9),dday.gap.max()))
print(dday.sort_values("gap",ascending=False).head(5).round(4).to_string())
