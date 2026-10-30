import numpy as np, pandas as pd
import indep_sim as s
r=s.run(lev=4.0,dep=0.95,phase=0,record=True)
rows=[]
for i,(q,e,W) in r["rec"].items():
    held=q!=0
    cl=np.where(np.isfinite(s.C[i]),s.C[i],e)
    Lh=np.where(np.isfinite(s.L[i]),s.L[i],cl); Hh=np.where(np.isfinite(s.H[i]),s.H[i],cl)
    pc=np.sum(np.where(held,q*(cl-e),0.0),axis=1)                 # close
    adv=np.where(q>0,Lh,Hh); pw=np.sum(np.where(held,q*(adv-e),0.0),axis=1)     # anti-sync WC
    fav=np.where(q>0,Hh,Lh); pb=np.sum(np.where(held,q*(fav-e),0.0),axis=1)
    sl=np.sum(np.where(held,q*(Lh-e),0.0),axis=1); sh=np.sum(np.where(held,q*(Hh-e),0.0),axis=1)  # sync low/high
    sw=np.minimum(sl,sh)
    ec=W+pc
    for h in range(24):
        rows.append((i,h,ec[h],(ec[h]-(W+pw[h]))/ec[h],(ec[h]-(W+sw[h]))/ec[h],((W+pb[h])-(W+pw[h]))/ec[h]))
df=pd.DataFrame(rows,columns=["day","h","ec","gap_anti","gap_sync","range_anti"])
df["date"]=s.DAYS[df.day]
def desc(x,name):
    print(f"{name:34s} mean {x.mean():.4f} p50 {x.median():.4f} p90 {x.quantile(.9):.4f} p99 {x.quantile(.99):.4f} max {x.max():.4f}")
live=df[(df.date>="2026-09-25")]
print("sim V0 4x0.95 (positions from sim), hourly gap = (close eq - adverse eq)/close eq")
for nm,d in (("live overlap 2026-09-25..10-09",live),("all history",df)):
    print("--",nm,"hours",len(d))
    desc(d.gap_anti,"anti-sync L/H (A/B/C model)"); desc(d.gap_sync,"sync low/high"); desc(d.range_anti,"range (best-worst)/close anti")
print("ratio live-5min p50/p99 dip vs sim anti-sync (overlap): ", 0.0017/live.gap_anti.median(), 0.0192/live.gap_anti.quantile(.99))
df.to_pickle("sim_hourly_gap.pkl")
