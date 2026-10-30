import numpy as np, pandas as pd
import indep_sim as s
import flash_overlay as fo
print("4x0.95, V0 daily-close kill variants: gross/eq on holding days and break-even long-wick fraction f (all longs hit simultaneously; h = share recouped on shorts)")
print("kill | final eq (3 phases) | gross/eq p50 p95 p99 max | f* h=0 / 0.5 / 1 | worst day h=0")
for kill,cool in ((0.25,14),(0.35,14),(0.5,14),(0.6,14),(0.7,14),(1.0,0)):
    st=[];fins=[]
    for ph in range(3):
        r=s.run(lev=4.0,dep=0.95,phase=ph,kill=kill,cool=cool,record=True)
        e=r["eq"]; fins.append(round(float(e[np.isfinite(e)][-1]),2) if not r["liq"] else 0.0)
        if ph==0: st=fo.day_stats(r)
    gr=np.array([N.sum()/eqc for i,eqc,N,sg in st])
    be=[fo.breakeven(st,h,"tier") for h in (0.0,0.5,1.0)]
    wd=fo.mincush(st,be[0]+0.01,0.0,"tier")[1]
    print(f"{kill:4} | {fins} | {np.percentile(gr,50):.2f} {np.percentile(gr,95):.2f} {np.percentile(gr,99):.2f} {gr.max():.2f} | {be[0]:.2f} / {be[1]:.2f} / {min(be[2],1.5):.2f} | {s.DAYS[wd].date()}",flush=True)
