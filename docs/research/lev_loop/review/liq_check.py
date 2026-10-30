import numpy as np, pandas as pd
import indep_sim as s
n=s.N
rng=np.random.default_rng(20261030)
subs=[sorted(rng.choice(n,size=30,replace=False).tolist()) for _ in range(30)]
r1=np.array([0.004 if b in("BTC","ETH") else 0.01 for b in s.NAMES])
D=int(s.DAYS.searchsorted(pd.Timestamp("2025-10-10",tz="UTC")))
print("event day idx",D,s.DAYS[D], "last bar", s.DAYS[-1])

def cushions(rec, day, prev_eq):
    """per-hour cushion (margin - MM)/prev_eq under price models for positions held at the start of `day`."""
    q,e,W=rec[day]
    out={}
    held=q!=0
    for name,pf in (("WC L/H simult",lambda h:np.where(q>0,s.L[day,h],s.H[day,h])),
                    ("longs L, shorts CLOSE",lambda h:np.where(q>0,s.L[day,h],s.C[day,h])),
                    ("all hourly CLOSE",lambda h:s.C[day,h])):
        best={}
        for mmname,mm in (("tier(r1)",None),("flat3",0.03)):
            mn=1e9;mh=None
            for h in range(24):
                a=pf(h); a=np.where(np.isfinite(a),a,e)
                pnl=np.sum(np.where(held,q*(a-e),0.0))
                N=np.abs(q)*a*held
                m=np.sum(N*(r1 if mm is None else mm))
                c=(W+pnl-m)/prev_eq
                if c<mn: mn=c;mh=h
            best[mmname]=(round(mn,3),mh)
        out[name]=best
    return out

for k in (23,):
    cols=subs[k]
    print("U3_%d"%k, [s.NAMES[j] for j in cols][:30])
    for ph in range(3):
        r=s.run(cols=cols,phase=ph,record=True)
        if r["liq"]: print(" phase",ph,"legacy-liq day",r["day"],s.DAYS[r["day"]].date()); 
        if D in r["rec"]:
            prev=r["eq"][D-1]
            q,e,W=r["rec"][D]
            print(" phase",ph,"held",int((q!=0).sum()),"gross/eq(prev close)", round(float(np.sum(np.abs(q)*s.CL[D-1]*(q!=0)))/prev,2),"prev_eq",round(prev,3))
            for k2,v in cushions(r["rec"],D,prev).items(): print("   ",k2,v)
        else:
            print(" phase",ph,"flat/halted on event day; liq",r["liq"])
