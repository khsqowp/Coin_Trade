"""30 random 30-symbol universes (C's seed) x lev x phase: cushion under (a) WC antisync L/H, (b) wick-fraction f, (c) sync-low/high.
Reproduces C's '4x: 1/30 subsets liquidated (U3_23), 5x: 8/30'."""
import numpy as np, pandas as pd, json
import indep_sim as s
from liq_scan import REF, r1
N=s.N
def cush(r, f=1.0, mode="anti", rate="tier"):
    eq=r["eq"]; best=9e9; bday=None
    for i,(q,e,W) in r["rec"].items():
        prev=eq[i-1] if i>0 and np.isfinite(eq[i-1]) else 1.0
        held=q!=0
        ref=np.where(np.isfinite(REF[i]),REF[i],e)
        Lh=np.where(np.isfinite(s.L[i]),s.L[i],ref); Hh=np.where(np.isfinite(s.H[i]),s.H[i],ref)
        al=Lh+(1-f)*(ref-Lh); ash=Hh-(1-f)*(Hh-ref)
        variants=[]
        if mode=="anti": variants=[np.where(q>0,al,ash)]
        else: variants=[al,ash]   # sync: all at low, or all at high
        for a in variants:
            pnl=np.sum(np.where(held,q*(a-e),0.0),axis=1)
            Nn=np.abs(q)*a*held
            m=np.sum(Nn*(r1 if rate=="tier" else 0.03),axis=1)
            c=((W+pnl-m)/prev).min()
            if c<best: best=c; bday=i
    return float(best), bday
if __name__=="__main__":
    rng=np.random.default_rng(20261030)
    subs=[sorted(rng.choice(N,size=30,replace=False).tolist()) for _ in range(30)]
    d0=int(s.DAYS.searchsorted(pd.Timestamp("2022-01-01",tz="UTC")))
    res={}
    for lev in (3.0,4.0,5.0):
        cnt={k:0 for k in ("anti_f1","anti_f0.75","anti_f0.5","sync_f1")}
        tot=0; mins={k:[] for k in cnt}
        for k,cols in enumerate(subs):
            for ph in range(3):
                r=s.run(cols=cols,lev=lev,dep=0.95,phase=ph,record=True)
                tot+=1
                vals={"anti_f1":cush(r,1.0,"anti")[0],"anti_f0.75":cush(r,0.75,"anti")[0],"anti_f0.5":cush(r,0.5,"anti")[0],"sync_f1":cush(r,1.0,"sync")[0]}
                for kk,v in vals.items():
                    mins[kk].append(v); cnt[kk]+= (v<=0)
                if vals["anti_f1"]<=0: print("  lev",lev,"subset",k,"ph",ph,"anti_f1 cushion",round(vals["anti_f1"],3),"sync",round(vals["sync_f1"],3),"f.5",round(vals["anti_f0.5"],3),flush=True)
        res[lev]=dict(n=tot,breach=cnt,min={k:float(np.min(v)) for k,v in mins.items()},p10={k:float(np.percentile(v,10)) for k,v in mins.items()})
        print("LEV",lev,res[lev],flush=True)
    json.dump(res,open("liq_subsets.json","w"))
