"""Offline hourly cadence research engine. Reads panels, writes no inputs/live state."""
from __future__ import annotations

import numpy as np
from numba import njit


@njit(cache=True)
def run(H, L, C, FD, score, crash, period, phase, d0, d1, lam, slip, fail_rate,
        seed, resize, kill_on=True, fixed_exposure=False):
    """One OLD-panel path. Arrays are flattened UTC hours; daily funding posts at UTC hour 0."""
    n = C.shape[1]
    q = np.zeros(n); entry = np.zeros(n); lastpx = np.zeros(n)
    haspx = np.zeros(n, np.uint8)
    W = 1.0; peak = 1.0; halted = False; halt_at = -10000000
    prev_crash = 0
    kills = 0; rebals = 0; attempts = 0; fails = 0
    min_cushion = 1e9; worst_eq = 1e9; mdd = 0.0
    eq_peak = 1.0; prev_equity = 1.0; eq0 = 1.0
    # deterministic common random stream, independent of cadence/phase
    t0 = d0 * 24; t1 = d1 * 24
    last_rebal = t0 + phase - period
    for t in range(t0, t1):
        day = t // 24
        if t % 24 == 0:
            # R2C books the aggregated UTC-day funding before that day's hourly path.
            for j in range(n):
                if q[j] != 0.0 and np.isfinite(FD[day,j]): W -= q[j]*FD[day,j]
        held = False
        eq = W
        gross = 0.0
        for j in range(n):
            if np.isfinite(C[t, j]):
                lastpx[j] = C[t, j]; haspx[j] = 1
            px = C[t, j] if np.isfinite(C[t, j]) else (lastpx[j] if haspx[j] else entry[j])
            if q[j] != 0.0:
                held = True
                eq += q[j] * (px - entry[j])
                gross += abs(q[j] * px)
        if held:
            # Hourly adverse mark; lambda interpolates from close mark to intrabar wick.
            pc = 0.0; pw = 0.0; maint = 0.0; notion = 0.0
            for j in range(n):
                if q[j] == 0.0: continue
                px = C[t, j] if np.isfinite(C[t, j]) else lastpx[j]
                adverse = L[t, j] if q[j] > 0 else H[t, j]
                if not np.isfinite(adverse): adverse = px
                ref = px
                pc += q[j] * (px - entry[j])
                pw += q[j] * (adverse - entry[j])
                notion += abs(q[j]) * px
                # flat 3% maintenance approximation (R2C reports both tier models separately)
                maint += abs(q[j]) * max(px, entry[j]) * 0.03
            # Close mark liquidation cushion and true worst wick cushion, both equity-relative.
            min_cushion = min(min_cushion, (eq - maint) / max(eq, 1e-9))
            eq_wick = W + (1.0-lam)*pc + lam*pw
            worst_eq = min(worst_eq, eq_wick)
            if kill_on and not halted and peak > 0 and 1.0-eq_wick/peak >= 0.35:
                close_fee = 0.0
                for j in range(n):
                    if q[j] != 0.0:
                        px = C[t, j] if np.isfinite(C[t,j]) else lastpx[j]
                        close_fee += abs(q[j])*px*(0.0005+slip/10000.0)
                        q[j]=0.0; entry[j]=0.0
                # R2C liquidates at the portfolio lambda-interpolated mark, not
                # the close PnL; commissions use the observed close notional.
                W = eq_wick - close_fee
                halted=True; halt_at=day; kills += 1
                eq=W
            elif (W + pc) > peak:
                # R2C semantics: trigger uses lambda-adjusted close/wick mark, while
                # the trailing high-water mark is updated from the hourly close mark.
                peak=W + pc
        if t % 24 == 23:
            eq = W
            for j in range(n):
                if q[j] != 0.0:
                    px=C[t,j] if np.isfinite(C[t,j]) else lastpx[j]
                    eq += q[j]*(px-entry[j])
            if eq > eq_peak: eq_peak=eq
            dd=1.0-eq/max(eq_peak,1e-12); mdd=max(mdd,dd)
            if eq > peak: peak=eq
            prev_equity=eq
        resumed = False
        if halted:
            if day-halt_at < 14 or t % 24 != 23: continue
            halted=False; peak=max(W,1e-9); resumed=True
        due = resumed or ((t >= t0+phase) and ((t-last_rebal) >= period))
        if t % 24 == 23:
            flag = crash[day]
            if flag != prev_crash: due=True
            prev_crash = flag
        if not due or t >= t1-1: continue
        last_rebal=t
        rebals += 1
        # Rank only symbols with a valid trailing 336-hour return and observed price.
        idx=np.empty(n,np.int64); vals=np.empty(n); cnt=0
        for j in range(n):
            if np.isfinite(score[t,j]): idx[cnt]=j; vals[cnt]=-score[t,j]; cnt+=1
        if cnt < 16: continue
        order=np.argsort(vals[:cnt]); side=np.zeros(n)
        for k in range(8): side[idx[order[k]]]=1.0
        ns=0
        for k in range(cnt-1,-1,-1):
            j=idx[order[k]]
            if side[j]==0 and ns<8: side[j]=-1.0; ns+=1
        equity=W
        for j in range(n):
            if q[j]!=0:
                px=C[t,j] if np.isfinite(C[t,j]) else lastpx[j]
                equity += q[j]*(px-entry[j])
        if equity <= 1e-9: continue
        target=(0.95*4.0/16.0) if fixed_exposure else (equity*0.95*4.0/16.0)
        # Include crash flat and 15% live-like resize. Failed orders are deferred for that leg.
        for j in range(n):
            want=0.0 if crash[day] else side[j]
            old=1.0 if q[j]>0 else (-1.0 if q[j]<0 else 0.0)
            px=C[t,j] if np.isfinite(C[t,j]) else lastpx[j]
            if not np.isfinite(px) or px<=0: continue
            if want==old and old!=0:
                notional=abs(q[j]*px)
                if not resize or abs(notional-target)/max(target,1e-9)<=0.15: continue
            attempts+=1
            # Common random number keyed by timestamp and symbol, independent of the
            # number/order of other orders generated by a cadence path.
            rng = np.uint64(seed) ^ (np.uint64(t+1) * np.uint64(0x9E3779B185EBCA87)) ^ (np.uint64(j+1) * np.uint64(0xC2B2AE3D27D4EB4F))
            rng = rng ^ (rng >> np.uint64(30)); rng *= np.uint64(0xBF58476D1CE4E5B9)
            rng = rng ^ (rng >> np.uint64(27)); rng *= np.uint64(0x94D049BB133111EB)
            rng = rng ^ (rng >> np.uint64(31))
            u=float(rng % np.uint64(1000000))/1000000.0
            if u < fail_rate: fails+=1; continue
            newq=want*target/px
            # Charge transaction cost on traded notional; close/reverse/re-size legs in one net fill.
            traded=abs(newq-q[j])*px
            W += q[j]*(px-entry[j]) - traded*(0.0005+slip/10000.0)
            q[j]=newq; entry[j]=px if newq!=0 else 0.0
    final=W
    last_day=d1-1
    t=last_day*24+23
    for j in range(n):
        if q[j]!=0:
            px=C[t,j] if np.isfinite(C[t,j]) else lastpx[j]
            final += q[j]*(px-entry[j])
    return final, mdd, kills, rebals, attempts, fails, min_cushion, worst_eq, (final>0)
