"""Reviewer flash overlay: take the portfolio actually held at each day's CLOSE on the V0 path (kill .35 daily, cool 14),
apply a one-shot shock to longs = f * w_j  (w_j = 2025-10-10 last-price wick of symbol j, median .64) and a gain on shorts = h * f * w_j,
margin check vs tier MM (r1) and flat 3%. Report min cushion over all days (worst-gross day) and the break-even f (cushion=0)."""
import numpy as np, pandas as pd, json
import indep_sim as s
D=int(s.DAYS.searchsorted(pd.Timestamp("2025-10-10",tz="UTC")))
ref=s.CL[D-1]; lo=np.nanmin(np.where(np.isfinite(s.L[D]),s.L[D],np.inf),axis=0)
w=np.where(np.isfinite(ref)&np.isfinite(lo)&(lo<1e300),np.maximum(0,1-lo/ref),np.nan); w=np.where(np.isfinite(w),w,np.nanmedian(w))
r1=np.array([0.004 if b in("BTC","ETH") else 0.01 for b in s.NAMES])
d0=int(s.DAYS.searchsorted(pd.Timestamp("2022-01-01",tz="UTC")))
def day_stats(r):
    out=[]
    eq=r["eq"]
    for i,(q,e,W) in r["rec"].items():
        px=np.where(np.isfinite(s.CL[i]),s.CL[i],e); held=q!=0
        eqc=W+np.sum(np.where(held,q*(px-e),0.0)); 
        if eqc<=0: continue
        out.append((i,eqc,np.where(held,np.abs(q)*px,0.0),np.sign(q)))
    return out
def mincush(stats,f,h,rate):
    best=9e9;bi=None
    for i,eqc,N,sg in stats:
        long=N*(sg>0); sh=N*(sg<0)
        loss=np.sum(long*w*f); gain=np.sum(sh*w*f*h)
        mm=np.sum(N*(r1 if rate=="tier" else 0.03))
        c=(eqc-loss+gain-mm)/eqc          # cushion as fraction of equity at the time
        if c<best: best=c;bi=i
    return best,bi
def breakeven(stats,h,rate):
    lo_,hi_=0.0,1.5
    for _ in range(30):
        m=(lo_+hi_)/2
        if mincush(stats,m,h,rate)[0]>0: lo_=m
        else: hi_=m
    return lo_
res={}
print("lev | gross/eq on holding days p50 p95 max | break-even f (worst day) for h=0 / 0.5 / 1 (tier) | flat3 h=0 | worst day (h=0)")
for lev in (2.0,3.0,3.5,4.0,5.0,6.0):
    r=s.run(lev=lev,dep=0.95,phase=0,record=True)
    st=day_stats(r)
    gr=np.array([N.sum()/eqc for i,eqc,N,sg in st])
    be=[breakeven(st,h,"tier") for h in (0.0,0.5,1.0)]
    bf=breakeven(st,0.0,"flat3")
    wd=mincush(st,be[0]+0.01,0.0,"tier")[1]
    res[lev]=dict(gr_p50=float(np.median(gr)),gr_p95=float(np.percentile(gr,95)),gr_max=float(gr.max()),be_h0=be[0],be_h05=be[1],be_h1=be[2],be_flat_h0=bf,worst_day=str(s.DAYS[wd].date()))
    print(f"{lev:3.1f}x0.95 | {np.median(gr):.2f} {np.percentile(gr,95):.2f} {gr.max():.2f} | {be[0]:.2f} / {be[1]:.2f} / {be[2] if be[2]<1.49 else '>1.5'} | {bf:.2f} | {s.DAYS[wd].date()}",flush=True)
json.dump(res,open("flash_overlay.json","w"))
print("f = fraction of the 2025-10-10 last-price wick (median wick 0.64 of price) applied to ALL longs at once; h = fraction of that move recouped on shorts")
