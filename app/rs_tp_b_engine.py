"""BACKTESTER-B research: per-position volatility-adaptive take-profit / trailing / scale-out overlay.
Core copied from rs_final_engine._sim (live-faithful model A) with unused features removed (band, vol-target,
delever designs, lot truncation).  mode=0 must reproduce rs_final_engine.Sim.run exactly (asserted in rs_tp_b_run).
Offline only; no network, no live state.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from numba import njit
from app.rs_final_engine import Sim as BaseSim

MAXT = 60000
MAXE = 30000


def tp_params(mode=0, kA=0.0, kB=0.0, redeploy=0, nextbar=0, slip=0.0005, fund_mult=1.0, fund_extra=0.0):
    return np.array([mode, kA, kB, redeploy, nextbar, slip, fund_mult, fund_extra], dtype=float)


@njit(cache=True)
def _sim(Hh, Ll, Cc, FD, score, flat_flag, VOL, rebal, K0, lev0, deploy, cost, mmr, kill, cool, W0, phase, fund_on,
         tp, d0, d1):
    nd, _, n = Cc.shape
    mode = int(tp[0]); kA = tp[1]; kB = tp[2]; redeploy = tp[3] > 0; nextbar = tp[4] > 0; slip = tp[5]
    fm = tp[6]; fx = tp[7]
    W = W0
    q = np.zeros(n); e = np.zeros(n)
    anc = np.zeros(n); vol_e = np.zeros(n); peak = np.zeros(n)
    active = np.zeros(n, np.bool_); scaled = np.zeros(n, np.bool_)
    tr_pnl = np.zeros(n); tr_day = np.zeros(n, np.int64); tr_eq = np.ones(n)
    fj = np.zeros(n)
    tl = np.zeros((MAXT, 6)); nT = 0
    ev = np.zeros((MAXE, 7)); nE = 0
    eq_c = np.full(nd, np.nan); eq_w = np.full(nd, np.nan); expo = np.zeros(nd)
    hwm = W0
    halted = False; halt_day = -1
    last_reb = -10 ** 9
    n_att = 0; n_skip = 0; n_kill = 0; n_reb = 0; liq = False
    prev_flag = False
    px = np.zeros(n)
    for i in range(d0, d1):
        held_any = False
        for j in range(n):
            if q[j] != 0.0:
                held_any = True
                break
        fund = 0.0
        worst = W
        adj = 0.0
        if held_any:
            for j in range(n):
                fj[j] = 0.0
            if fund_on:
                for j in range(n):
                    if q[j] != 0.0:
                        f_ = -(q[j] * FD[i, j] * fm)
                        if fx > 0.0:
                            cj = Cc[i, 23, j]
                            if np.isfinite(cj):
                                f_ -= abs(q[j]) * cj * fx
                        fj[j] = f_
                        fund += f_
                        tr_pnl[j] += f_
            maint = 0.0
            for j in range(n):
                if q[j] != 0.0:
                    mx = 0.0
                    for h in range(24):
                        v = Hh[i, h, j]
                        if np.isfinite(v) and v > mx:
                            mx = v
                    maint += abs(q[j]) * max(mx, e[j]) * mmr
            wmin = 1e300
            for h in range(24):
                # ---- per-position exits on hour h
                if mode != 0:
                    for j in range(n):
                        if q[j] == 0.0:
                            continue
                        vj = vol_e[j]
                        if not (vj > 0.0):
                            continue
                        hi = Hh[i, h, j]; lo = Ll[i, h, j]
                        if not (np.isfinite(hi) and np.isfinite(lo)):
                            continue
                        s_ = 1.0 if q[j] > 0 else -1.0
                        a_ = anc[j]
                        if s_ > 0:
                            fhi = hi / a_ - 1.0; flo = lo / a_ - 1.0
                        else:
                            fhi = 1.0 - lo / a_; flo = 1.0 - hi / a_
                        trig = False; frac = 1.0; ffill = 0.0; etype = 0
                        if mode == 1:
                            if fhi >= kA * vj:
                                trig = True; ffill = kA * vj; etype = 1
                        elif mode == 2:
                            if fhi > peak[j]:
                                peak[j] = fhi
                            if peak[j] >= kA * vj:
                                active[j] = True
                            if active[j] and flo <= peak[j] - kB * vj:
                                trig = True; ffill = peak[j] - kB * vj; etype = 2
                        else:
                            if (not scaled[j]) and fhi >= kA * vj:
                                trig = True; frac = 0.5; ffill = kA * vj; etype = 3
                        if not trig:
                            continue
                        p = a_ * (1.0 + s_ * ffill)
                        if nextbar:
                            cc = Cc[i, h, j]
                            if np.isfinite(cc):
                                p = cc
                        p = p * (1.0 - s_ * slip)
                        xq = q[j] * frac
                        pnl = xq * (p - e[j]); cst = abs(xq) * p * cost
                        adj += pnl - cst
                        tr_pnl[j] += pnl - cst
                        # funding refund for the exited part (8h settlements at 00/08/16 already passed)
                        sf = (1.0 + (1.0 if h >= 8 else 0.0) + (1.0 if h >= 16 else 0.0)) / 3.0
                        rf = -fj[j] * frac * (1.0 - sf)
                        fund += rf; tr_pnl[j] += rf
                        fj[j] = fj[j] * (1.0 - frac)
                        q[j] -= xq
                        if nE < MAXE:
                            ev[nE, 0] = i; ev[nE, 1] = h; ev[nE, 2] = j; ev[nE, 3] = s_; ev[nE, 4] = p
                            ev[nE, 5] = etype; ev[nE, 6] = frac; nE += 1
                        if frac < 1.0:
                            scaled[j] = True
                        else:
                            q[j] = 0.0
                            if nT < MAXT:
                                tl[nT, 0] = tr_day[j]; tl[nT, 1] = i; tl[nT, 2] = j; tl[nT, 3] = s_
                                tl[nT, 4] = tr_pnl[j] / tr_eq[j]; tl[nT, 5] = etype; nT += 1
                            e[j] = 0.0; tr_pnl[j] = 0.0
                        if redeploy:
                            rel = abs(xq) * p
                            wsum = 0.0
                            for k in range(n):
                                if k != j and q[k] * s_ > 0.0 and np.isfinite(Cc[i, h, k]):
                                    wsum += abs(q[k]) * Cc[i, h, k]
                            if wsum > 0.0:
                                for k in range(n):
                                    if k != j and q[k] * s_ > 0.0 and np.isfinite(Cc[i, h, k]):
                                        pk = Cc[i, h, k]
                                        nk = rel * (abs(q[k]) * pk) / wsum
                                        pf = pk * (1.0 + s_ * slip)
                                        dq = nk / pf
                                        e[k] = (abs(q[k]) * e[k] + dq * pf) / (abs(q[k]) + dq)
                                        q[k] += s_ * dq
                                        c2 = dq * pf * cost
                                        adj -= c2; tr_pnl[k] -= c2
                # ---- hourly worst-case equity of positions still held
                s = 0.0
                for j in range(n):
                    if q[j] != 0.0:
                        a = Ll[i, h, j] if q[j] > 0 else Hh[i, h, j]
                        if np.isfinite(a):
                            s += q[j] * (a - e[j])
                t_ = adj + s
                if t_ < wmin:
                    wmin = t_
            worst = W + fund + wmin
            if worst <= maint:
                liq = True
                eq_c[i] = 0.0; eq_w[i] = 0.0
                break
            W += fund
            W += adj
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
        if eq > hwm:
            hwm = eq
        dd = 1.0 - eq / hwm
        # ---- kill / halt
        if (not halted) and dd >= kill:
            c_ = 0.0
            for j in range(n):
                if q[j] != 0.0:
                    pn = q[j] * (px[j] - e[j]); cc_ = abs(q[j]) * px[j] * cost
                    W += pn; c_ += cc_
                    if nT < MAXT:
                        tl[nT, 0] = tr_day[j]; tl[nT, 1] = i; tl[nT, 2] = j; tl[nT, 3] = 1.0 if q[j] > 0 else -1.0
                        tl[nT, 4] = (tr_pnl[j] + pn - cc_) / tr_eq[j]; tl[nT, 5] = 4; nT += 1
                    q[j] = 0.0; e[j] = 0.0; tr_pnl[j] = 0.0
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
        want_flat = flat_flag[i] > 0
        force = False
        if want_flat != prev_flag:
            force = True
        prev_flag = want_flat
        due = (i >= d0 + phase) and ((i - last_reb) >= rebal)
        if not (due or force) or i >= d1 - 1:
            continue
        cnt = 0
        for j in range(n):
            if np.isfinite(score[i, j]):
                cnt += 1
        K = K0
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
        tgt = eq * deploy * lev0 / (2.0 * K)
        c_ = 0.0
        for j in range(n):
            s = side[j]
            cs = 1.0 if q[j] > 0 else (-1.0 if q[j] < 0 else 0.0)
            if q[j] != 0.0 and s == cs:
                continue
            if q[j] != 0.0:
                pn = q[j] * (px[j] - e[j]); cc_ = abs(q[j]) * px[j] * cost
                W += pn; c_ += cc_
                if nT < MAXT:
                    tl[nT, 0] = tr_day[j]; tl[nT, 1] = i; tl[nT, 2] = j; tl[nT, 3] = cs
                    tl[nT, 4] = (tr_pnl[j] + pn - cc_) / tr_eq[j]; tl[nT, 5] = 0; nT += 1
                q[j] = 0.0; e[j] = 0.0; tr_pnl[j] = 0.0
            if s != 0.0 and np.isfinite(px[j]) and px[j] > 0:
                n_att += 1
                qty = tgt / px[j]
                if qty <= 0:
                    n_skip += 1
                    continue
                q[j] = s * qty; e[j] = px[j]
                c_ += qty * px[j] * cost
                anc[j] = px[j]; vol_e[j] = VOL[i, j] if np.isfinite(VOL[i, j]) else 0.0
                peak[j] = 0.0; active[j] = False; scaled[j] = False
                tr_pnl[j] = -qty * px[j] * cost; tr_day[j] = i; tr_eq[j] = eq
        W -= c_
        if due:
            last_reb = i
        n_reb += 1
    return eq_c, eq_w, expo, np.array([n_att, n_skip, n_kill, n_reb, 1.0 if liq else 0.0]), tl[:nT].copy(), ev[:nE].copy()


def vol_panels(C, H, L):
    """ATR14% and RV(14d std of log ret)*sqrt(3), known at day-close i (uses days <= i)."""
    dc = C[:, -1, :]
    dh = np.nanmax(np.where(np.isfinite(H), H, -np.inf), axis=1); dh[~np.isfinite(dh)] = np.nan
    dl = np.nanmin(np.where(np.isfinite(L), L, np.inf), axis=1); dl[~np.isfinite(dl)] = np.nan
    pc = np.full_like(dc, np.nan); pc[1:] = dc[:-1]
    tr = np.fmax(dh - dl, np.fmax(np.abs(dh - pc), np.abs(dl - pc)))
    atr = pd.DataFrame(tr).rolling(14, min_periods=14).mean().to_numpy() / dc
    lr = np.full_like(dc, np.nan); lr[1:] = np.log(dc[1:] / dc[:-1])
    rv = pd.DataFrame(lr).rolling(14, min_periods=14).std().to_numpy() * np.sqrt(3.0)
    return atr, rv


class TPSim(BaseSim):
    def __init__(self, P):
        super().__init__(P)
        self.atr, self.rv = vol_panels(self.C, self.H, self.L)

    def run_tp(self, tp=None, rebal=3, K=8, lev=4.0, deploy=0.95, cost=0.001, kill=0.35, cool=14, phase=0,
               fund=1, vol="atr", d0=None, d1=None):
        tp = tp_params() if tp is None else tp
        d0 = self.d_start() if d0 is None else d0
        d1 = self.nd if d1 is None else d1
        VOL = self.atr if vol == "atr" else self.rv
        out = _sim(self.H, self.L, self.C, self.FD, self.signal((14,)), self.crash.astype(np.float64),
                   np.ascontiguousarray(VOL), rebal, K, lev, deploy, cost, 0.005, kill, cool, 1.0, phase, fund > 0,
                   tp, d0, d1)
        ec, ew, ex, st, tl, ev = out
        return dict(eq=pd.Series(ec, index=self.days), worst=pd.Series(ew, index=self.days),
                    expo=pd.Series(ex, index=self.days), stats=st, trades=tl, events=ev, d0=d0)
