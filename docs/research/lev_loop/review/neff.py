import numpy as np, pandas as pd
import indep_sim as s
d0=int(s.DAYS.searchsorted(pd.Timestamp("2022-01-01",tz="UTC")))
fin={};eqs={}
for off in range(40):
    for ph in range(3):
        r=s.run(lev=4.0,dep=0.95,phase=ph,d0=d0+off)
        e=r["eq"]; fin[(off,ph)]=round(float(e[np.isfinite(e)][-1]),4); eqs[(off,ph)]=e
vals=np.array(list(fin.values()))
print("paths",len(vals),"distinct final equities (4dp):",len(set(vals)), "min/med/max",vals.min(),np.median(vals),vals.max())
# cluster by (rounded) final: group counts
from collections import Counter
c=Counter(vals); print("cluster sizes (top 10):",sorted(c.values(),reverse=True)[:10])
# coalescence: day after which path (off,ph) equals path (0,0) up to scale (ratio constant)
base=eqs[(0,0)]
co=[]
for k,e in eqs.items():
    ok=np.isfinite(e)&np.isfinite(base)
    ratio=e[ok]/base[ok]
    # last index where ratio deviates >1e-6 from final ratio
    dev=np.where(np.abs(ratio/ratio[-1]-1)>1e-6)[0]
    co.append(dev[-1] if len(dev) else 0)
days=np.where(np.isfinite(base))[0]
cd=[str(s.DAYS[days[0]+c].date()) for c in co]
print("paths whose trajectory is proportional to path (0,0) from some day on:",sum(1 for c in co if c<len(days)-30),"/",len(co))
print("coalescence date distribution:",pd.Series(cd).value_counts().head(8).to_dict())
