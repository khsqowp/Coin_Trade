"""Reviewer counterfactual: shift the 2025-10-10 21:00 UTC bar (the worst hour) onto every day's realised V0 portfolio.
Longs repriced at ref*rL_j (rL = L/prev-hour-close), shorts at ref*rH_j (rH = H/prev-hour-close)  [anti-sync, f=1];
f scales the move: r_f = 1 + f*(r-1). Also 'sync' variant: shorts get the same-hour LOW (hedge works) -> shorts gain.
Reports share of holding-days with cushion<=0 (tier r1 and flat3) for lev 3/3.5/4/5/6."""
import numpy as np, pandas as pd
import indep_sim as s
D=int(s.DAYS.searchsorted(pd.Timestamp("2025-10-10",tz="UTC"))); h=21
ref=s.C[D,h-1,:]
rL=s.L[D,h,:]/ref; rH=s.H[D,h,:]/ref
rL=np.where(np.isfinite(rL),rL,np.nanmedian(rL)); rH=np.where(np.isfinite(rH),rH,np.nanmedian(rH))
r1=np.array([0.004 if b in("BTC","ETH") else 0.01 for b in s.NAMES])
print("shock bar: median long move %.1f%%, median short(H) move %+.1f%%, p10 long %.1f%%"%((np.median(rL)-1)*100,(np.median(rH)-1)*100,(np.percentile(rL,10)-1)*100))
d0=int(s.DAYS.searchsorted(pd.Timestamp("2022-01-01",tz="UTC")))
rows=[]
for lev in (3.0,3.5,4.0,5.0,6.0):
    r=s.run(lev=lev,dep=0.95,phase=0,record=True)
    res={}
    days=[]
    for i,(q,e,W) in r["rec"].items():
        px=np.where(np.isfinite(s.CL[i]),s.CL[i],e); held=q!=0
        eqc=W+np.sum(np.where(held,q*(px-e),0.0))
        if eqc<=0: continue
        N=np.where(held,np.abs(q)*px,0.0); lg=N*(q>0); sh=N*(q<0)
        days.append((eqc,lg,sh,N))
    for f in (1.0,0.75,0.5):
        for mode in ("anti","hedged"):
            bad_t=bad_f=0;mins=[]
            for eqc,lg,sh,N in days:
                lossL=np.sum(lg*(1-(1+f*(rL-1))))                     # long loss = N*(1-r)
                if mode=="anti": lossS=np.sum(sh*((1+f*(rH-1))-1))       # short loss at hourly high
                else:            lossS=-np.sum(sh*(1-(1+f*(rL-1))))       # short GAINS the same-hour low move
                loss=lossL+lossS
                ct=(eqc-loss-np.sum(N*r1))/eqc; cf=(eqc-loss-0.03*N.sum())/eqc
                bad_t+=ct<=0; bad_f+=cf<=0; mins.append(ct)
            res[(f,mode)]=(bad_t/len(days),bad_f/len(days),min(mins))
    print(f"lev {lev}x0.95 holding-days {len(days)}")
    for k,v in res.items(): print(f"   f={k[0]:.2f} {k[1]:6s} P(liq|event on random day): tier {v[0]:.1%} flat3 {v[1]:.1%} | worst-day tier cushion {v[2]:+.2f}")
