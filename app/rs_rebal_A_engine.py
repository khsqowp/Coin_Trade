"""Offline hourly-resolution rebalancing research engine; no live integrations."""
import numpy as np
from numba import njit, prange

@njit(cache=True)
def run(H, L, C, FH, score, crash, d0, d1, p, offset, cost, resize, kill_mode=0,
        lev=4.0, deploy=0.95, K=8, kill=0.35, cool=14, mmr=0.005, W0=1.0):
    nd, _, n=C.shape; T=nd*24
    q=np.zeros(n); e=np.zeros(n); px=np.zeros(n)
    eqh=np.full(T,np.nan); wh=np.full(T,np.nan); flags=np.zeros(T,np.uint8)
    hwm=W0; W=W0; halted=False; halt_t=-10**9; last=-10**9
    turns=0; costs=0.; kills=0; liqs=0; rebs=0; gross_turn=0.
    prev_crash=False
    start=d0*24; end=d1*24
    # Hourly time loop. Positions are marked at close; risk uses simultaneous adverse H/L.
    for t in range(start,end):
        day=t//24; hour=t%24
        held=False; pnl=0.; worst=W; maint=0.; fund=0.
        for j in range(n):
            if q[j]!=0:
                held=True
                a=L[day,hour,j] if q[j]>0 else H[day,hour,j]
                if np.isfinite(a): pnl+=q[j]*(a-e[j])
                if np.isfinite(FH[day,hour,j]): fund-=q[j]*FH[day,hour,j]
                hi=H[day,hour,j]
                if np.isfinite(hi): maint+=abs(q[j])*max(hi,e[j])*mmr
        worst=W+fund+pnl
        if held:
            W+=fund
            if worst<=maint:
                liqs+=1; flags[t]=1
        # hourly close mark, fallback to entry when missing
        eq=W
        for j in range(n):
            v=C[day,hour,j]
            px[j]=v if np.isfinite(v) else (e[j] if e[j]>0 else np.nan)
            if q[j]!=0 and np.isfinite(px[j]): eq+=q[j]*(px[j]-e[j])
        eqh[t]=eq; wh[t]=worst
        if kill_mode==0:
            if hour==23 and eq>hwm: hwm=eq
        elif eq>hwm: hwm=eq
        dd=1-eq/hwm if hwm>0 else 0.
        if kill_mode==0:
            trigger=(hour==23 and dd>=kill)
        else:
            trigger=(held and worst>maint and dd>=kill)
        if not halted and trigger:
            cst=0.
            for j in range(n):
                if q[j]!=0:
                    pxout=(L[day,hour,j] if q[j]>0 else H[day,hour,j]) if kill_mode else px[j]
                    if not np.isfinite(pxout): pxout=px[j]
                    W+=q[j]*(pxout-e[j]); cst+=abs(q[j])*pxout*cost
                    gross_turn+=abs(q[j])*pxout; turns+=1; q[j]=0.; e[j]=0.
            W-=cst; costs+=cst; halted=True; halt_t=t; kills+=1
            continue
        if halted:
            if hour==23 and cool>0 and day-halt_t//24>=cool:
                halted=False; hwm=eq; last=-10**9
            else: continue
        # V0 has an immediate risk-flag transition rebalance at the UTC close.
        # Keep it in addition to the cadence schedule for exact reproduction.
        crash_now=bool(crash[t])
        force=(hour==23 and crash_now!=prev_crash)
        if hour==23: prev_crash=crash_now
        cadence_due = t>=start+offset and (last < 0 or t-last>=p)
        due=cadence_due or force
        if due:
            if t>=end-1: continue
            if crash[t]:
                sides=np.zeros(n)
            else:
                cnt=0
                for j in range(n):
                    if np.isfinite(score[t,j]): cnt+=1
                if cnt<2*K: continue
                # Match rs_final_engine._sim: descending score, stable NumPy
                # argsort tie order; the previous ascending/reversed selection
                # inverted equal-score tie membership on both portfolio tails.
                order=np.argsort(-np.where(np.isfinite(score[t]),score[t],-1e18))
                sides=np.zeros(n)
                for z in range(K): sides[order[z]]=1.
                for z in range(K): sides[order[cnt-1-z]]=-1.
            target=max(eq,0.)*deploy*lev/(2*K); cst=0.
            for j in range(n):
                s=sides[j]; cs=1. if q[j]>0 else (-1. if q[j]<0 else 0.)
                if q[j]!=0 and s==cs:
                    if resize and np.isfinite(px[j]) and px[j]>0:
                        nq=s*target/px[j]
                        if abs(nq/q[j]-1.)>0.15:
                            dq=nq-q[j]; cst+=abs(dq)*px[j]*cost; gross_turn+=abs(dq)*px[j]; turns+=1
                            if abs(nq)<abs(q[j]): W+=q[j]*(px[j]-e[j])*(1.-abs(nq)/abs(q[j]))
                            else: e[j]=(abs(q[j])*e[j]+abs(dq)*px[j])/abs(nq)
                            q[j]=nq
                    continue
                if q[j]!=0:
                    W+=q[j]*(px[j]-e[j]); cst+=abs(q[j])*px[j]*cost; gross_turn+=abs(q[j])*px[j]; turns+=1
                    q[j]=0.; e[j]=0.
                if s!=0 and np.isfinite(px[j]) and px[j]>0:
                    q[j]=s*target/px[j]; e[j]=px[j]; cst+=target*cost; gross_turn+=target; turns+=1
            W-=cst; costs+=cst
            if cadence_due: last=t
            rebs+=1
    return eqh,wh,np.array([W,kills,liqs,rebs,turns,gross_turn,costs])


@njit(cache=True, parallel=True)
def run_batch(H, L, C, FH, score, crash, d0, d1, cost, resize, kill_mode=0,
              lev=4.0, deploy=0.95, K=8, kill=0.35, cool=14, mmr=0.005, W0=1.0):
    """Run all p=1..72 offsets in parallel; return compact daily paths and accounting."""
    total = 72 * 73 // 2
    nd = d1 - d0
    rets = np.full((total, nd), np.nan)
    # p, offset, close MDD, worst-hour MDD, kills, liquidation flags, rebals,
    # fills, traded notional, costs, ending equity
    meta = np.zeros((total, 11))
    ps = np.empty(total, np.int64); os_ = np.empty(total, np.int64)
    z = 0
    for p in range(1, 73):
        for o in range(p):
            ps[z] = p; os_[z] = o; z += 1
    for k in prange(total):
        p = ps[k]; o = os_[k]
        eq, worst, st = run(H,L,C,FH,score,crash,d0,d1,p,o,cost,resize,kill_mode,
                            lev,deploy,K,kill,cool,mmr,W0)
        high = W0; whigh = W0; mdd = 0.; wmdd = 0.; prev = W0
        for i in range(nd):
            day = d0+i; close = eq[day*24+23]
            if np.isfinite(close):
                if close > high: high=close
                dd = 1.-close/high if high>0 else 1.
                if dd>mdd: mdd=dd
                rets[k,i] = np.log(max(close,1e-12)/max(prev,1e-12))
                prev=close
            for h in range(24):
                w = worst[day*24+h]
                if np.isfinite(w):
                    if w>whigh: whigh=w
                    dd=1.-w/whigh if whigh>0 else 1.
                    if dd>wmdd: wmdd=dd
        meta[k,0]=p; meta[k,1]=o; meta[k,2]=mdd; meta[k,3]=wmdd
        meta[k,4]=st[1]; meta[k,5]=st[2]; meta[k,6]=st[3]; meta[k,7]=st[4]
        meta[k,8]=st[5]; meta[k,9]=st[6]; meta[k,10]=prev
    return rets,meta
