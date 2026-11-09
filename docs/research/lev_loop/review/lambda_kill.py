"""Reviewer: kill-fidelity interpolation. Hourly kill test on eq_h(lambda) = close_h - lambda*(close_h - anti-sync-worst_h).
lambda=0 -> A mode 3 / B T2 / C K1 (hourly close); lambda=1 -> A mode 1 / B T1 / C K2 (anti-sync L/H worst case, exit at that price).
Independent implementation (own sim). HWM = running max of hourly CLOSE equity (as A/B/C)."""
import numpy as np, pandas as pd, sys
import indep_sim as s
N=s.N
def run(lam, lev=4.0, dep=0.95, phase=0, kill=0.35, cool=14, cost=0.001, d0=None, d1=None, K=8, rebal=3, nokill=False):
    sc=s.scores(list(range(N)))
    d0=int(s.DAYS.searchsorted(pd.Timestamp("2022-01-01",tz="UTC"))) if d0 is None else d0
    d1=s.ND if d1 is None else d1
    q=np.zeros(N); e=np.zeros(N); W=1.0; hwm=1.0
    halted=False; halt_day=-1; last_reb=-10**9; prev_flag=False; kills=0
    eqs=np.full(s.ND,np.nan)
    for i in range(d0,d1):
        held=np.any(q!=0); killed=False
        if held:
            W+=-np.sum(np.where(q!=0,q*np.nan_to_num(s.FD[i]),0.0))
            cl=np.where(np.isfinite(s.C[i]),s.C[i],e)
            Lh=np.where(np.isfinite(s.L[i]),s.L[i],cl); Hh=np.where(np.isfinite(s.H[i]),s.H[i],cl)
            hm=q!=0
            pc=np.sum(np.where(hm,q*(cl-e),0.0),axis=1)
            pw=np.sum(np.where(hm,q*(np.where(q>0,Lh,Hh)-e),0.0),axis=1)
            if not nokill:
              for h in range(24):
                pl=pc[h]-lam*(pc[h]-pw[h])
                if 1-(W+pl)/hwm>=kill:
                    # exit at that hour; cost on closing notional at hour close prices
                    cst=np.sum(np.where(hm,np.abs(q)*cl[h]*cost,0.0))
                    W+=pl-cst; q[:]=0; e[:]=0; halted=True; halt_day=i; kills+=1; killed=True
                    eqs[i]=W; break
                hwm=max(hwm,W+pc[h])
            if killed: continue
        px=np.where(np.isfinite(s.CL[i]),s.CL[i],np.where(e>0,e,np.nan))
        eq=W+np.nansum(np.where(q!=0,q*(px-e),0.0)); eqs[i]=eq
        hwm=max(hwm,eq); dd=1-eq/hwm
        if (not halted) and (not nokill) and dd>=kill:
            W+=np.nansum(np.where(q!=0,q*(px-e),0.0))-np.sum(np.where(q!=0,np.abs(q)*px*cost,0.0))
            q[:]=0;e[:]=0;halted=True;halt_day=i;kills+=1; continue
        if halted:
            if cool>0 and i-halt_day>=cool: halted=False; hwm=eq; last_reb=-10**9
            else: continue
        flag=bool(s.CRASH[i]); force=flag!=prev_flag; prev_flag=flag
        due=(i>=d0+phase) and (i-last_reb>=rebal)
        if not(due or force) or i>=d1-1: continue
        ok=np.isfinite(sc[i]); cnt=ok.sum(); side=np.zeros(N)
        if cnt>=2*K and not flag:
            idx=np.where(ok)[0]; order=idx[np.argsort(-sc[i,idx],kind="stable")]
            side[order[:K]]=1.0
            for j in order[::-1]:
                if (side==-1).sum()>=K: break
                if side[j]==0: side[j]=-1.0
        elif cnt<2*K and not flag: continue
        tgt=eq*dep*lev/(2.0*K); c_=0.0
        for j in range(N):
            sd=side[j]; cs=np.sign(q[j])
            if q[j]!=0 and sd==cs: continue
            if q[j]!=0:
                W+=q[j]*(px[j]-e[j]); c_+=abs(q[j])*px[j]*cost; q[j]=0; e[j]=0
            if sd!=0 and np.isfinite(px[j]) and px[j]>0:
                qty=tgt/px[j]; q[j]=sd*qty; e[j]=px[j]; c_+=qty*px[j]*cost
        W-=c_
        if due: last_reb=i
    ev=eqs[np.isfinite(eqs)]
    return float(ev[-1]), kills
if __name__=="__main__":
    print("lambda | final equity ph0/ph1/ph2 | kills ph0/1/2 | CAGR(mean of phases geom) ")
    yrs=(s.ND-int(s.DAYS.searchsorted(pd.Timestamp("2022-01-01",tz='UTC'))))/365.0
    for lam in (0.0,0.05,0.1,0.2,0.3,0.5,1.0):
        res=[run(lam,phase=p) for p in range(3)]
        g=np.mean([np.log(max(r[0],1e-9)) for r in res])/yrs
        print(f"{lam:5.2f} | "+" / ".join(f"{r[0]:.3f}" for r in res)+" | "+"/".join(str(r[1]) for r in res)+f" | ann.log-growth {g:+.3f} CAGR {np.exp(g)-1:+.1%}",flush=True)
    r=[run(0,phase=p,nokill=True) for p in range(3)]
    g=np.mean([np.log(x[0]) for x in r])/yrs
    print("no kill |"," / ".join(f"{x[0]:.3f}" for x in r),f"| ann.log-growth {g:+.3f} CAGR {np.exp(g)-1:+.1%}")
