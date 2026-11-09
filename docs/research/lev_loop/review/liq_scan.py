"""Cushion scan: for each path, min over days/hours of (margin - MM)/prev_close_equity under wick-fraction f
(f=1 -> longs at hourly L & shorts at hourly H simultaneously = A/B/C 'worst-case'; f=0 -> marks stay at previous hourly close).
Independent of A/B/C code; uses indep_sim positions."""
import numpy as np, pandas as pd, sys, json
import indep_sim as s
N=s.N
r1=np.array([0.004 if b in("BTC","ETH") else 0.01 for b in s.NAMES])
REF=np.concatenate([np.concatenate([s.CL[:1]*np.nan, s.CL[:-1]],0)[:,None,:], s.C[:,:-1,:]],1)  # prev-hour close, ND x 24 x N
REF=REF.copy()
fs=[1.0,0.75,0.5,0.25]
def scan(r, d0):
    res={f:{"tier":(9e9,None),"flat3":(9e9,None)} for f in fs}
    eq=r["eq"]
    for i,(q,e,W) in r["rec"].items():
        prev=eq[i-1] if i>0 and np.isfinite(eq[i-1]) else 1.0
        held=q!=0
        ref=np.where(np.isfinite(REF[i]),REF[i],e)      # 24xN
        Lh=np.where(np.isfinite(s.L[i]),s.L[i],ref); Hh=np.where(np.isfinite(s.H[i]),s.H[i],ref)
        for f in fs:
            al=Lh+(1-f)*(ref-Lh); ash=Hh-(1-f)*(Hh-ref)
            a=np.where(q>0,al,ash)
            pnl=np.sum(np.where(held,q*(a-e),0.0),axis=1)
            Nn=np.abs(q)*a*held
            for nm,rate in (("tier",r1),("flat3",0.03)):
                m=np.sum(Nn*rate,axis=1)
                c=((W+pnl-m)/prev).min()
                if c<res[f][nm][0]: res[f][nm]=(float(c),int(i))
    return res
if __name__=="__main__":
    out={}
    levs=[3.0,3.5,4.0,5.0,6.0]
    for lev in levs:
        rows=[]
        for off in range(0,40,5):
            for ph in range(3):
                r=s.run(lev=lev,dep=0.95,phase=ph,d0=s.DAYS.searchsorted(pd.Timestamp("2022-01-01",tz="UTC"))+off,record=True)
                sc=scan(r,0)
                rows.append(dict(off=off,ph=ph,kills=r["kills"],legacy_liq=r["liq"],legacy_day=r["day"],sc=sc,final=float(r["eq"][np.isfinite(r["eq"])][-1]) if not r["liq"] else None))
        out[str(lev)]=rows
        print("lev",lev,"done",flush=True)
    json.dump(out,open("liq_scan.json","w"),default=float)
    for lev in levs:
        rows=out[str(lev)]
        print("== lev",lev,"x0.95 gross",round(lev*0.95,2),"paths",len(rows),"legacy-daily-liq paths",sum(x["legacy_liq"] for x in rows))
        for f in fs:
            for nm in ("tier","flat3"):
                v=[x["sc"][f][nm][0] for x in rows]; days=[x["sc"][f][nm][1] for x in rows]
                dd=pd.Series([str(s.DAYS[d].date()) for d in days]).value_counts().head(2).to_dict()
                print(f"  f={f:4.2f} {nm:5s} min cushion {min(v):+.3f} median {np.median(v):+.3f} paths<=0: {sum(x<=0 for x in v)}/{len(v)}  argmin days {dd}")
