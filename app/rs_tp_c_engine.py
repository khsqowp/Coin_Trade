"""BACKTESTER-C research engine: intra-rebalance per-position exits (offline, research only).

Derived line-by-line from app/rs_final_engine._sim (live-faithful model A). With all exit switches off the arithmetic is
identical (asserted in rs_tp_c_run.py). Only the features used by V0 are kept (band/vt/design/rearm/cw/minn = off).
Exits are evaluated at the UTC daily close, ONLY on days that are NOT scheduled rebalance days (strictly intra-rebalance),
and only use information available at that close. An exited symbol can only re-enter at the next scheduled rebalance.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from numba import njit
from app.rs_final_engine import zscore_signal, btc_flags, window_metrics  # noqa: F401  (re-exported)

# exit parameter vector xp
# 0 modeA: 0 off, 1 long-fav (Z>=z), 2 short-fav (Z<=-z), 3 both fav, 4 adverse both (long Z<=-z, short Z>=z)
# 1 z threshold   2 margin m for rank-decay (0=off)   3 trim opposite side (0/1)
# 4 placebo flag (1 -> ignore signals, exit with Bernoulli prob U<pL / U<pS)   5 pL   6 pS
XP_N = 7


def xparams(modeA=0, z=3.0, m=0, trim=0, plc=0, pL=0.0, pS=0.0):
    return np.array([modeA, z, m, trim, plc, pL, pS], dtype=np.float64)


@njit(cache=True)
def _sim(Hh, Ll, Cc, FD, score, flat_flag, Zx, RK, CNT, U, sched, use_sched, rebal, K0, lev0, deploy, cost, mmr, kill,
         cool, W, phase, d0, d1, xp):
    nd, _, n = Cc.shape
    modeA = int(xp[0]); zthr = xp[1]; marg = int(xp[2]); trim = xp[3] > 0
    plc = xp[4] > 0; pL = xp[5]; pS = xp[6]
    q = np.zeros(n); e = np.zeros(n)
    eq_c = np.full(nd, np.nan); eq_w = np.full(nd, np.nan); expo = np.zeros(nd)
    tn = np.zeros(nd)            # traded notional per day (all legs)
    exL = np.zeros(nd); exS = np.zeros(nd)   # intra-rebalance exits per day
    pdL = np.zeros(nd); pdS = np.zeros(nd)   # held positions per day, on exit-eligible days only (hazard denominators)
    hwm = W; prev_eq = W
    halted = False; halt_day = -1
    last_reb = -10 ** 9
    n_kill = 0; n_reb = 0; liq = False
    prev_flag = False
    px = np.zeros(n)
    fund_on = True
    for i in range(d0, d1):
        held_any = False
        for j in range(n):
            if q[j] != 0.0:
                held_any = True
                break
        fund = 0.0
        worst = W
        maint = 0.0
        if held_any:
            wmin = 1e300
            for h in range(24):
                s = 0.0
                for j in range(n):
                    if q[j] != 0.0:
                        a = Ll[i, h, j] if q[j] > 0 else Hh[i, h, j]
                        if np.isfinite(a):
                            s += q[j] * (a - e[j])
                if s < wmin:
                    wmin = s
            if fund_on:
                for j in range(n):
                    if q[j] != 0.0:
                        fund -= q[j] * FD[i, j]
            worst = W + fund + wmin
            for j in range(n):
                if q[j] != 0.0:
                    mx = 0.0
                    for h in range(24):
                        v = Hh[i, h, j]
                        if np.isfinite(v) and v > mx:
                            mx = v
                    maint += abs(q[j]) * max(mx, e[j]) * mmr
            W += fund
        if held_any and worst <= maint:
            liq = True
            eq_c[i] = 0.0; eq_w[i] = 0.0
            break
        for j in range(n):
            v = Cc[i, 23, j]
            px[j] = v if np.isfinite(v) else (e[j] if e[j] > 0 else np.nan)
        eq = W
        gross_n = 0.0
        npos = 0
        for j in range(n):
            if q[j] != 0.0:
                eq += q[j] * (px[j] - e[j])
                gross_n += abs(q[j] * px[j])
                npos += 1
        eq_c[i] = eq; eq_w[i] = worst
        expo[i] = gross_n / max(eq, 1e-12)
        prev_eq = eq
        if eq > hwm:
            hwm = eq
        dd = 1.0 - eq / hwm
        # ---- kill / halt
        if (not halted) and dd >= kill:
            c_ = 0.0
            for j in range(n):
                if q[j] != 0.0:
                    W += q[j] * (px[j] - e[j]); c_ += abs(q[j]) * px[j] * cost
                    tn[i] += abs(q[j]) * px[j]
                    q[j] = 0.0; e[j] = 0.0
            W -= c_
            halted = True; halt_day = i; n_kill += 1
            continue
        if halted:
            if cool > 0 and i - halt_day >= cool:
                halted = False
                hwm = eq; dd = 0.0
                last_reb = -10 ** 9
            else:
                continue
        # ---- decide rebalance (computed BEFORE exits so exits never act on a rebalance day)
        want_flat = flat_flag[i] > 0
        force = False
        if want_flat != prev_flag:
            force = True
        prev_flag = want_flat
        if use_sched:
            due = (i >= d0) and sched[i] > 0
        else:
            due = (i >= d0 + phase) and ((i - last_reb) >= rebal)
        # ---- intra-rebalance exits
        do_exit = (not due) and (not force) and (not want_flat) and (modeA > 0 or marg > 0 or plc)
        if do_exit:
            Lb = 0.0; Sb = 0.0
            for j in range(n):
                if q[j] > 0:
                    Lb += q[j] * px[j]
                elif q[j] < 0:
                    Sb += -q[j] * px[j]
            XL = 0.0; XS = 0.0
            c_ = 0.0
            cnt_ = CNT[i]
            for j in range(n):
                if q[j] == 0.0 or not np.isfinite(px[j]):
                    continue
                if q[j] > 0:
                    pdL[i] += 1.0
                else:
                    pdS[i] += 1.0
                go = False
                if plc:
                    if q[j] > 0:
                        go = U[i, j] < pL
                    else:
                        go = U[i, j] < pS
                else:
                    z = Zx[i, j]
                    if modeA > 0 and np.isfinite(z):
                        if q[j] > 0:
                            if (modeA == 1 or modeA == 3) and z >= zthr:
                                go = True
                            elif modeA == 4 and z <= -zthr:
                                go = True
                        else:
                            if (modeA == 2 or modeA == 3) and z <= -zthr:
                                go = True
                            elif modeA == 4 and z >= zthr:
                                go = True
                    if (not go) and marg > 0 and cnt_ >= 2 * K0:
                        r = RK[i, j]
                        if r >= 0:
                            if q[j] > 0 and r >= K0 + marg:
                                go = True
                            elif q[j] < 0 and r < cnt_ - K0 - marg:
                                go = True
                if go:
                    notl = abs(q[j]) * px[j]
                    W += q[j] * (px[j] - e[j]); c_ += notl * cost
                    tn[i] += notl
                    if q[j] > 0:
                        XL += notl; exL[i] += 1.0
                    else:
                        XS += notl; exS[i] += 1.0
                    q[j] = 0.0; e[j] = 0.0
            if trim and (XL > 0 or XS > 0):
                La = 0.0; Sa = 0.0
                for j in range(n):
                    if q[j] > 0:
                        La += q[j] * px[j]
                    elif q[j] < 0:
                        Sa += -q[j] * px[j]
                d = (La - Sa) - (Lb - Sb)
                if d > 0 and La > 0:
                    cut = min(1.0, d / La)
                    for j in range(n):
                        if q[j] > 0:
                            W += q[j] * cut * (px[j] - e[j]); c_ += q[j] * cut * px[j] * cost
                            tn[i] += q[j] * cut * px[j]
                            q[j] *= 1.0 - cut
                elif d < 0 and Sa > 0:
                    cut = min(1.0, -d / Sa)
                    for j in range(n):
                        if q[j] < 0:
                            W += q[j] * cut * (px[j] - e[j]); c_ += -q[j] * cut * px[j] * cost
                            tn[i] += -q[j] * cut * px[j]
                            q[j] *= 1.0 - cut
            W -= c_
        if not (due or force) or i >= d1 - 1:
            continue
        # ---- targets (identical to rs_final_engine, band=0)
        cnt = 0
        for j in range(n):
            if np.isfinite(score[i, j]):
                cnt += 1
        K = K0
        lev = lev0
        side = np.zeros(n)
        if cnt >= 2 * K0 and not want_flat:
            order = np.argsort(-np.where(np.isfinite(score[i]), score[i], -1e18))
            nl = 0; ns = 0
            for z in range(cnt):
                if nl >= K:
                    break
                j = order[z]
                if side[j] == 0.0:
                    side[j] = 1.0; nl += 1
            for z in range(cnt - 1, -1, -1):
                if ns >= K:
                    break
                j = order[z]
                if side[j] == 0.0:
                    side[j] = -1.0; ns += 1
        elif cnt < 2 * K0 and not want_flat:
            continue
        tgt = eq * deploy * lev / (2.0 * K)
        c_ = 0.0
        for j in range(n):
            s = side[j]
            cs = 1.0 if q[j] > 0 else (-1.0 if q[j] < 0 else 0.0)
            if q[j] != 0.0 and s == cs:
                continue
            if q[j] != 0.0:
                W += q[j] * (px[j] - e[j]); c_ += abs(q[j]) * px[j] * cost
                tn[i] += abs(q[j]) * px[j]
                q[j] = 0.0; e[j] = 0.0
            if s != 0.0 and np.isfinite(px[j]) and px[j] > 0:
                qty = tgt / px[j]
                if qty <= 0:
                    continue
                q[j] = s * qty; e[j] = px[j]
                c_ += qty * px[j] * cost
                tn[i] += qty * px[j]
        W -= c_
        if due:
            last_reb = i
        n_reb += 1
    return eq_c, eq_w, expo, tn, exL, exS, pdL, pdS, np.array([n_kill, n_reb, 1.0 if liq else 0.0])


class TPSim:
    """Panel wrapper. `cols` selects a symbol subset (signals computed within the subset); BTC flags always from the full panel."""

    def __init__(self, P, cols=None, zh=2):
        names = list(P["names"])
        self.days = P["days"]; self.nd = len(self.days)
        jb = names.index("BTC")
        c = P["C"][:, -1, jb]
        sma = pd.Series(c).rolling(200, min_periods=200).mean().to_numpy()
        self.btc = c; self.sma200 = sma
        self.bull_flag, self.crash = btc_flags(P)
        cols = list(range(len(names))) if cols is None else list(cols)
        self.cols = cols
        self.names = [names[j] for j in cols]
        self.H = np.ascontiguousarray(P["H"][:, :, cols]); self.L = np.ascontiguousarray(P["L"][:, :, cols])
        self.C = np.ascontiguousarray(P["C"][:, :, cols]); self.FD = np.ascontiguousarray(P["FD"][:, cols])
        self.score = zscore_signal(self.C, (14,))
        dc = self.C[:, -1, :]
        r = np.full_like(dc, np.nan); r[zh:] = dc[zh:] / dc[:-zh] - 1
        mu = np.nanmean(r, axis=1, keepdims=True); sd = np.nanstd(r, axis=1, keepdims=True)
        with np.errstate(invalid="ignore", divide="ignore"):
            self.Z = np.where(np.isfinite(r), (r - mu) / sd, np.nan)
        s = self.score
        ok = np.isfinite(s)
        self.CNT = ok.sum(1).astype(np.int64)
        rk = np.full(s.shape, -1, np.int64)
        order = np.argsort(-np.where(ok, s, -1e18), axis=1, kind="stable")
        for i in range(self.nd):
            for z in range(self.CNT[i]):
                rk[i, order[i, z]] = z
        self.RK = rk
        self.U0 = np.zeros((self.nd, len(cols)))
        self.d0 = int(self.days.searchsorted(pd.Timestamp("2022-01-01", tz="UTC")))

    def run(self, rebal=3, K=8, lev=2.0, deploy=1.0, cost=0.001, kill=0.35, cool=14, phase=0, xp=None, Z=None, U=None,
            sched=None, crash_flat=True, d0=None, d1=None, eq0=1.0):
        xp = xparams() if xp is None else xp
        d0 = self.d0 if d0 is None else d0
        d1 = self.nd if d1 is None else d1
        flag = self.crash.astype(np.float64) if crash_flat else np.zeros(self.nd)
        sch = np.zeros(self.nd) if sched is None else sched.astype(np.float64)
        out = _sim(self.H, self.L, self.C, self.FD, self.score, flag, self.Z if Z is None else Z, self.RK, self.CNT,
                   self.U0 if U is None else U, sch, sched is not None, rebal, K, lev, deploy, cost, 0.005, kill, cool,
                   eq0, phase, d0, d1, xp)
        eq_c, eq_w, expo, tn, exL, exS, pdL, pdS, st = out
        return dict(eq=pd.Series(eq_c, index=self.days), worst=pd.Series(eq_w, index=self.days),
                    expo=pd.Series(expo, index=self.days), tn=tn, exL=exL, exS=exS, pdL=pdL, pdS=pdS,
                    kills=st[0], nreb=st[1], liq=bool(st[2]), d0=d0, eq0=eq0)
