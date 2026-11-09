"""Research-only: per-position take-profit overlay on the rs_final_engine core (design 0 only).
With tp disabled (XL=XS=0) the arithmetic is identical to rs_final_engine._sim (asserted in docs/research/tp_loop/A/run.py).
Intrabar TP on hourly H/L: long closes when H >= e*(1+X), short when L <= e*(1-X). Adds a trade log.
Does not touch any live module. No network.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from numba import njit
from app.rs_final_engine import Sim as BaseSim, params, P_MINN, P_EQ0

# trade-log columns
(T_SYM, T_SIDE, T_ED, T_XD, T_TYPE, T_PNL, T_EQE, T_NOT, T_EPX, T_XPX, T_HR, T_N) = range(12)
TYPE_REB, TYPE_TP, TYPE_PART, TYPE_KILL = 0, 1, 2, 3


def tp_params(XL=0.0, XS=0.0, frac=1.0, lockout=0, fillmode=0, slipx=0.003):
    return np.array([XL, XS, frac, lockout, fillmode, slipx], dtype=float)


@njit(cache=True)
def _sim_tp(Hh, Ll, Cc, FD, CF, score, flat_flag, pr, minn_j, step_j, d0, d1, pt, tlog):
    nd, _, n = Cc.shape
    rebal = int(pr[0]); K0 = int(pr[1]); lev0 = pr[2]; deploy = pr[3]; cost = pr[4]; mmr = pr[5]; kill = pr[6]
    cool = int(pr[16]); minn = pr[18]; W = pr[19]
    phase = int(pr[20]); fund_on = pr[21] > 0
    XL = pt[0]; XS = pt[1]; fr = pt[2]; lockout = pt[3] > 0; fillmode = int(pt[4]); slipx = pt[5]
    tpon = (XL > 0) or (XS > 0)
    q = np.zeros(n); e = np.zeros(n)
    th = np.full(n, 24, np.int64); fillp = np.zeros(n)
    done = np.zeros(n, np.bool_); ban = np.zeros(n, np.bool_)
    ent_d = np.zeros(n, np.int64); ent_eq = np.zeros(n); ec = np.zeros(n); facc = np.zeros(n)
    eq_c = np.full(nd, np.nan); eq_w = np.full(nd, np.nan); expo = np.zeros(nd)
    hwm = W; prev_eq = W
    halted = False; halt_day = -1
    last_reb = -10 ** 9
    n_att = 0; n_skip = 0; n_kill = 0; n_reb = 0; n_tp = 0; liq = False; npos_sum = 0.0; npos_cnt = 0
    nt = 0
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
        maint = 0.0
        for j in range(n):
            th[j] = 24
        if held_any:
            if tpon:
                for j in range(n):
                    if q[j] == 0.0:
                        continue
                    if q[j] > 0:
                        if XL <= 0 or done[j]:
                            continue
                        lv = e[j] * (1.0 + XL)
                        for h in range(24):
                            v = Hh[i, h, j]
                            if np.isfinite(v) and v >= lv:
                                th[j] = h
                                break
                        if th[j] < 24:
                            f_ = lv
                            if fillmode == 1:
                                f_ = lv * (1.0 - slipx)
                            elif fillmode == 2 and np.isfinite(Cc[i, th[j], j]):
                                f_ = Cc[i, th[j], j]
                            fillp[j] = f_
                    else:
                        if XS <= 0 or done[j]:
                            continue
                        lv = e[j] * (1.0 - XS)
                        for h in range(24):
                            v = Ll[i, h, j]
                            if np.isfinite(v) and v <= lv:
                                th[j] = h
                                break
                        if th[j] < 24:
                            f_ = lv
                            if fillmode == 1:
                                f_ = lv * (1.0 + slipx)
                            elif fillmode == 2 and np.isfinite(Cc[i, th[j], j]):
                                f_ = Cc[i, th[j], j]
                            fillp[j] = f_
            wmin = 1e300
            for h in range(24):
                s = 0.0
                for j in range(n):
                    if q[j] != 0.0:
                        a = Ll[i, h, j] if q[j] > 0 else Hh[i, h, j]
                        if h <= th[j]:
                            if np.isfinite(a):
                                s += q[j] * (a - e[j])
                        else:
                            s += q[j] * fr * (fillp[j] - e[j])
                            if np.isfinite(a):
                                s += q[j] * (1.0 - fr) * (a - e[j])
                            else:
                                pass
                if s < wmin:
                    wmin = s
            if fund_on:
                for j in range(n):
                    if q[j] != 0.0:
                        if th[j] < 24:
                            f1 = 0.0; f2 = 0.0
                            for h in range(24):
                                if h <= th[j]:
                                    f1 += CF[i, h, j]
                                else:
                                    f2 += CF[i, h, j]
                            fj = -q[j] * f1 - q[j] * (1.0 - fr) * f2
                        else:
                            fj = -q[j] * FD[i, j]
                        fund += fj
                        facc[j] += fj
            worst = W + fund + wmin
            for j in range(n):
                if q[j] != 0.0:
                    mx = 0.0
                    for h in range(24):
                        if h > th[j]:
                            break
                        v = Hh[i, h, j]
                        if np.isfinite(v) and v > mx:
                            mx = v
                    maint += abs(q[j]) * max(mx, e[j]) * mmr
            W += fund
        if held_any and worst <= maint:
            liq = True
            eq_c[i] = 0.0; eq_w[i] = 0.0
            break
        # ---- realise TPs (after the liquidation test)
        if held_any and tpon:
            for j in range(n):
                if th[j] >= 24 or q[j] == 0.0:
                    continue
                qq = q[j] * fr
                gross = qq * (fillp[j] - e[j])
                xc = abs(qq) * fillp[j] * cost
                W += gross - xc
                n_tp += 1
                if nt < tlog.shape[0]:
                    tlog[nt, T_SYM] = j; tlog[nt, T_SIDE] = 1.0 if q[j] > 0 else -1.0
                    tlog[nt, T_ED] = ent_d[j]; tlog[nt, T_XD] = i
                    tlog[nt, T_TYPE] = TYPE_TP if fr >= 1.0 else TYPE_PART
                    tlog[nt, T_PNL] = gross - xc - fr * ec[j] + fr * facc[j]
                    tlog[nt, T_EQE] = ent_eq[j]; tlog[nt, T_NOT] = abs(qq) * e[j]
                    tlog[nt, T_EPX] = e[j]; tlog[nt, T_XPX] = fillp[j]; tlog[nt, T_HR] = th[j]
                    nt += 1
                ec[j] *= (1.0 - fr); facc[j] *= (1.0 - fr)
                if fr >= 1.0:
                    q[j] = 0.0; e[j] = 0.0; done[j] = False; ec[j] = 0.0; facc[j] = 0.0
                    if lockout:
                        ban[j] = True
                else:
                    q[j] = q[j] - qq
                    done[j] = True
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
        npos_sum += npos; npos_cnt += 1
        if eq > hwm:
            hwm = eq
        dd = 1.0 - eq / hwm
        # ---- kill / halt
        if (not halted) and dd >= kill:
            c_ = 0.0
            for j in range(n):
                if q[j] != 0.0:
                    pn = q[j] * (px[j] - e[j]); xc = abs(q[j]) * px[j] * cost
                    W += pn; c_ += xc
                    if nt < tlog.shape[0]:
                        tlog[nt, T_SYM] = j; tlog[nt, T_SIDE] = 1.0 if q[j] > 0 else -1.0
                        tlog[nt, T_ED] = ent_d[j]; tlog[nt, T_XD] = i; tlog[nt, T_TYPE] = TYPE_KILL
                        tlog[nt, T_PNL] = pn - xc - ec[j] + facc[j]; tlog[nt, T_EQE] = ent_eq[j]
                        tlog[nt, T_NOT] = abs(q[j]) * e[j]; tlog[nt, T_EPX] = e[j]; tlog[nt, T_XPX] = px[j]
                        nt += 1
                    q[j] = 0.0; e[j] = 0.0; done[j] = False
            W -= c_
            halted = True; halt_day = i; n_kill += 1
            for j in range(n):
                ban[j] = False
            continue
        if halted:
            if cool > 0 and i - halt_day >= cool:
                halted = False
                hwm = eq; dd = 0.0
                last_reb = -10 ** 9
            else:
                continue
        lev = lev0
        want_flat = flat_flag[i] > 0
        force = False
        if want_flat != prev_flag:
            force = True
        prev_flag = want_flat
        due = (i >= d0 + phase) and ((i - last_reb) >= rebal)
        if not (due or force) or i >= d1 - 1:
            continue
        # ---- targets
        sc = score[i].copy()
        for j in range(n):
            if ban[j]:
                sc[j] = np.nan
        cnt = 0
        for j in range(n):
            if np.isfinite(sc[j]):
                cnt += 1
        K = K0
        side = np.zeros(n)
        if cnt >= 2 * K0 and not want_flat:
            order = np.argsort(-np.where(np.isfinite(sc), sc, -1e18))
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
        for j in range(n):
            ban[j] = False
        tgt = eq * deploy * lev / (2.0 * K)
        c_ = 0.0
        for j in range(n):
            s = side[j]
            cs = 1.0 if q[j] > 0 else (-1.0 if q[j] < 0 else 0.0)
            if q[j] != 0.0 and s == cs:
                continue
            if q[j] != 0.0:
                pn = q[j] * (px[j] - e[j]); xc = abs(q[j]) * px[j] * cost
                W += pn; c_ += xc
                if nt < tlog.shape[0]:
                    tlog[nt, T_SYM] = j; tlog[nt, T_SIDE] = cs
                    tlog[nt, T_ED] = ent_d[j]; tlog[nt, T_XD] = i; tlog[nt, T_TYPE] = TYPE_REB
                    tlog[nt, T_PNL] = pn - xc - ec[j] + facc[j]; tlog[nt, T_EQE] = ent_eq[j]
                    tlog[nt, T_NOT] = abs(q[j]) * e[j]; tlog[nt, T_EPX] = e[j]; tlog[nt, T_XPX] = px[j]
                    nt += 1
                q[j] = 0.0; e[j] = 0.0; done[j] = False
            if s != 0.0 and np.isfinite(px[j]) and px[j] > 0:
                n_att += 1
                qty = tgt / px[j]
                mn = max(minn, minn_j[j])
                if minn > 0:
                    st = step_j[j]
                    if st <= 0:
                        st = 10.0 ** np.ceil(np.log10(0.1 / px[j]))
                    qty = np.floor(qty / st + 1e-9) * st
                if qty <= 0 or qty * px[j] < mn:
                    n_skip += 1
                    continue
                q[j] = s * qty; e[j] = px[j]
                ent_d[j] = i; ent_eq[j] = eq; ec[j] = qty * px[j] * cost; facc[j] = 0.0; done[j] = False
                c_ += qty * px[j] * cost
        W -= c_
        if due:
            last_reb = i
        n_reb += 1
    npos_avg = npos_sum / max(npos_cnt, 1)
    return eq_c, eq_w, expo, np.array([n_att, n_skip, n_kill, n_reb, 1.0 if liq else 0.0, npos_avg, n_tp, nt])


class TPSim(BaseSim):
    def __init__(self, P, CF):
        super().__init__(P)
        self.CF = np.ascontiguousarray(CF)
        self.tlog = np.zeros((60000, T_N))

    def run(self, tp=None, lbs=(14,), crash_flat=True, d0=None, d1=None, **kw):
        pr = params(**kw)
        pt = tp_params(**(tp or {}))
        d0 = self.d_start() if d0 is None else d0
        d1 = self.nd if d1 is None else d1
        tlog = np.zeros((60000, T_N))
        flag = self.crash.astype(np.float64) if crash_flat else np.zeros(self.nd)
        ec, ew, ex, st = _sim_tp(self.H, self.L, self.C, self.FD, self.CF, self.signal(lbs), flag, pr,
                                 self.minj(pr[P_MINN]), self.step_j, d0, d1, pt, tlog)
        nt = int(st[7])
        return dict(eq=pd.Series(ec, index=self.days), worst=pd.Series(ew, index=self.days),
                    expo=pd.Series(ex, index=self.days), att=st[0], skip=st[1], kills=st[2], nreb=st[3],
                    liq=bool(st[4]), npos=st[5], ntp=int(st[6]), eq0=pr[P_EQ0], d0=d0, trades=tlog[:nt].copy())
