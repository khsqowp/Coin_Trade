import numpy as np, pandas as pd
import indep_sim as s
from liq_subsets import cush
D=int(s.DAYS.searchsorted(pd.Timestamp("2025-10-10",tz="UTC")))
d0=int(s.DAYS.searchsorted(pd.Timestamp("2022-01-01",tz="UTC")))
print("lev kill | cushion tier f=1 (min over paths) | list distinct per-phase(offset0) | gross/eq on 10-10 | final eq | #distinct finals over 24 paths")
for lev,kill in ((4.0,0.35),(4.0,1.0),(4.0,0.5),(5.0,1.0),(3.0,1.0),(6.0,1.0)):
    vals=[];gr=[];fin=[]
    for off in range(0,40,5):
        for ph in range(3):
            r=s.run(lev=lev,dep=0.95,phase=ph,kill=kill,cool=14 if kill<1 else 0,d0=d0+off,record=True)
            c,dd=cush(r,1.0,"anti"); vals.append(c)
            if D in r["rec"]:
                q,e,W=r["rec"][D]; gr.append(float(np.sum(np.abs(q)*s.CL[D-1]*(q!=0))/r["eq"][D-1]))
            fin.append(round(float(r["eq"][np.isfinite(r["eq"])][-1]),3) if not r["liq"] else 0)
    print(lev,kill,"|",round(min(vals),3),round(np.median(vals),3),"| gross/eq",np.round(np.percentile(gr,[0,50,100]),2) if gr else None,"| distinct finals",len(set(fin)),"of",len(fin), "| liq-legacy", sum(f==0 for f in fin))
