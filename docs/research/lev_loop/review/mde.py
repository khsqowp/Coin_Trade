import numpy as np, pandas as pd
import indep_sim as s
d0=int(s.DAYS.searchsorted(pd.Timestamp("2022-01-01",tz="UTC")))
oos=int(s.DAYS.searchsorted(pd.Timestamp("2024-07-01",tz="UTC")))
e=s.run(lev=1.0,dep=1.0,phase=0,kill=1.0,cool=0)["eq"]
x=e[d0:]; x=x[np.isfinite(x)]; r=np.diff(x)/x[:-1]
rng=np.random.default_rng(1)
def boot(d,block=15,B=4000):
    T=len(d); nb=int(np.ceil(T/block)); st=rng.integers(0,T-block+1,size=(B,nb))
    idx=(st[:,:,None]+np.arange(block)[None,None,:]).reshape(B,-1)[:,:T]
    return 365*d[idx].mean(axis=1)
print("days",len(r))
for a,b in ((4,5),(4,3),(4,6),(3,5)):
    d=np.log1p(b*r)-np.log1p(a*r)
    bm=boot(d)
    print(f"g({b})-g({a}): point {365*d.mean():+.3f}/yr  SE(15d block) {bm.std():.3f}  95%CI [{np.percentile(bm,2.5):+.3f},{np.percentile(bm,97.5):+.3f}]  MDE(80%,5%) {2.8*bm.std():.2f}")
print("annual vol of 1x series",r.std()*np.sqrt(365), "n eff blocks (4.8y/15d) ~",len(r)/15)
