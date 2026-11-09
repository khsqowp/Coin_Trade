import numpy as np, pandas as pd
import indep_sim as s
from liq_subsets import cush
rng=np.random.default_rng(20261030)
subs=[sorted(rng.choice(s.N,size=30,replace=False).tolist()) for _ in range(30)]
def fstar(r):
    lo,hi=0.0,1.0
    if cush(r,1.0,"anti")[0]>0: return None
    for _ in range(18):
        m=(lo+hi)/2
        if cush(r,m,"anti")[0]>0: lo=m
        else: hi=m
    return lo
for lev,ks in ((4.0,[23]),(5.0,[1,2,3,6,9,11,19,23]),(6.0,list(range(30)))):
    out=[]
    for k in ks:
        r=s.run(cols=subs[k],lev=lev,dep=0.95,phase=0,record=True)
        f=fstar(r); out.append((k,None if f is None else round(f,2)))
    liq=[x for x in out if x[1] is not None]
    print(lev,"liquidated subsets (anti-sync, f=1):",len(liq),"/",len(ks) if lev<6 else 30, "break-even f:",out if lev<6 else [x for x in liq][:30])
    if liq: print("   median break-even f among liquidated:",np.median([x[1] for x in liq]))
# U1 base universe for 6x, 5x : cushion at f=1 positive => nothing; report f for 8x? skip
