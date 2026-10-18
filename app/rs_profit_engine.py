"""Offline profit overlays. Core copied from rs_final_engine._sim; mode=0 preserves arithmetic."""
from __future__ import annotations
import numpy as np
import pandas as pd
from numba import njit
from app.rs_final_engine import Sim as BaseSim, params, P_MINN, P_EQ0


def profit_params(mode=0, activation=.20, drop=.15, pause=7, scale=.5,
                  original_base=False, proportional=False, window=7, threshold=.10, rolling=False):
    return np.array([mode, activation, drop, pause, scale, original_base, proportional,
                     window, threshold, rolling], dtype=float)


@njit(cache=False)
def _sim(Hh, Ll, Cc, FD, score, flat_flag, pr, minn_j, step_j, d0, d1, pp):
    nd, _, n = Cc.shape
    rebal = int(pr[0]); K0 = int(pr[1]); lev0 = pr[2]; deploy = pr[3]; cost = pr[4]; mmr = pr[5]; kill = pr[6]
    band = int(pr[7]); vt = pr[8]; vlb = int(pr[9]); cap = pr[10]; design = int(pr[11]); dlv = pr[12]; rlv = pr[13]
    resize_lvl = pr[14] > 0; rearm = int(pr[15]); cool = int(pr[16]); cw = pr[17] > 0; minn = pr[18]; W = pr[19]
    phase = int(pr[20]); fund_on = pr[21] > 0; dmult = pr[22]; safe = pr[23]; kmin = int(pr[24]); gnorm = pr[25] > 0
    mode = int(pp[0]); activation = pp[1]; drop = pp[2]; pause = int(pp[3])
    scale = pp[4]; original_base = pp[5] > 0; proportional = pp[6] > 0
    window = int(pp[7]); threshold = pp[8]; rolling = pp[9] > 0
    base = W; peak = W; lock_level = W; withdrawn = 0.0
    profit_halt = False; profit_day = -1; factor = 1.0
    window_start = d0; window_eq = W
    withdrawals = np.zeros(nd); events = np.zeros(nd); loss_events = np.zeros(nd)
    total_worst = np.full(nd, np.nan)
    q = np.zeros(n); e = np.zeros(n)
    eq_c = np.full(nd, np.nan); eq_w = np.full(nd, np.nan); expo = np.zeros(nd)
    sret = np.zeros(nd)
    hwm = W; prev_eq = W
    lvl = 0; halted = False; halt_day = -1; flat_days = 0
    last_reb = -10 ** 9
    n_att = 0; n_skip = 0; n_kill = 0; n_reb = 0; liq = False; npos_sum = 0.0; npos_cnt = 0
    prev_flag = False; lev_prev_mult = 1.0
    px = np.zeros(n)
    for i in range(d0, d1):
        withdrawals[i] = withdrawn
        # ---- day i path with positions q
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
            eq_c[i] = 0.0; eq_w[i] = 0.0; total_worst[i] = withdrawn
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
        eq_c[i] = eq; eq_w[i] = worst; total_worst[i] = worst + withdrawn
        expo[i] = gross_n / max(eq, 1e-12)
        sret[i] = eq / prev_eq - 1.0 if prev_eq > 0 else 0.0
        prev_eq = eq
        npos_sum += npos; npos_cnt += 1
        if eq > hwm:
            hwm = eq
        dd = 1.0 - eq / hwm
        if mode == 4 and ((not rolling and (i - d0) % window == 0) or
                          (rolling and i - window_start >= window)):
            window_start = i; window_eq = eq
            if profit_halt:
                profit_halt = False; last_reb = -10 ** 9
        # ---- kill / halt
        if (not halted) and dd >= kill:
            c_ = 0.0
            for j in range(n):
                if q[j] != 0.0:
                    W += q[j] * (px[j] - e[j]); c_ += abs(q[j]) * px[j] * cost
                    q[j] = 0.0; e[j] = 0.0
            W -= c_
            halted = True; halt_day = i; n_kill += 1; loss_events[i] = 1
            continue
        if halted:
            if cool > 0 and i - halt_day >= cool:
                halted = False
                hwm = eq; dd = 0.0; lvl = 0
                last_reb = -10 ** 9
            else:
                continue
        # Profit actions are strictly AFTER the traded-equity loss kill/halt.
        profit_force = False
        if profit_halt:
            if mode == 1 and i - profit_day >= pause:
                profit_halt = False; peak = eq; hwm = eq; dd = 0.0
                if not original_base:
                    base = eq
                last_reb = -10 ** 9
            else:
                continue
        new_peak = eq > peak
        if new_peak:
            peak = eq
        flatten_profit = False
        if mode == 1 and peak / base - 1.0 >= activation and eq <= peak * (1.0 - drop):
            flatten_profit = True
        if mode == 4 and eq / window_eq - 1.0 >= threshold:
            flatten_profit = True
        if flatten_profit:
            c_ = 0.0
            for j in range(n):
                if q[j] != 0.0:
                    W += q[j] * (px[j] - e[j]); c_ += abs(q[j]) * px[j] * cost
                    q[j] = 0.0; e[j] = 0.0
            W -= c_
            eq_c[i] = W
            profit_halt = True; profit_day = i; events[i] = 1
            # Rolling windows start at the trigger and wait a complete W days.
            if mode == 4 and rolling:
                window_start = i; window_eq = W
            continue
        if mode == 2:
            old_factor = factor
            if new_peak:
                factor = 1.0
            elif peak / base - 1.0 >= activation and eq <= peak * (1.0 - drop):
                factor = scale
            if factor != old_factor:
                profit_force = True
                if factor < old_factor:
                    events[i] = 1
        if mode == 3 and new_peak and eq >= lock_level * (1.0 + activation):
            amount = scale * (eq - lock_level)
            W -= amount; withdrawn += amount; events[i] = 1
            if proportional:
                ratio = (eq - amount) / eq
                c_ = 0.0
                for j in range(n):
                    if q[j] != 0.0:
                        new_abs = abs(q[j]) * ratio
                        if minn > 0:
                            new_abs = min(abs(q[j]), max(new_abs, max(minn, minn_j[j]) / px[j]))
                        cut = 1.0 - new_abs / abs(q[j])
                        W += q[j] * cut * (px[j] - e[j])
                        c_ += abs(q[j]) * cut * px[j] * cost
                        q[j] *= 1.0 - cut
                W -= c_
                eq -= c_
            eq -= amount
            eq_c[i] = eq; withdrawals[i] = withdrawn
            lock_level = eq; hwm = eq; dd = 0.0; peak = eq
        # ---- flat re-arm (dd frozen while flat is the live trap)
        if rearm > 0:
            if npos == 0:
                flat_days += 1
                if flat_days >= rearm and dd > 0:
                    hwm = eq; dd = 0.0; flat_days = 0
            else:
                flat_days = 0
        # ---- delever level
        old_lvl = lvl
        if dd >= dlv:
            lvl = 1
        elif dd < rlv:
            lvl = 0
        lev = lev0
        mult = 1.0
        if design == 1:
            if lvl == 1 and lev0 > 1.0:
                lev = 1.0
        elif design == 2 or design == 3:
            if lvl == 1:
                mult = dmult
        lev = lev * mult * factor
        # vol target (rs_risk_engine convention)
        if vt > 0:
            if i - d0 >= max(10, vlb // 2):
                lo = max(d0, i - vlb + 1)
                m_ = 0.0; m2 = 0.0; g_ = 0.0; c = 0
                for t in range(lo, i + 1):
                    m_ += sret[t]; g_ += expo[t]; c += 1
                m_ /= c; g_ /= c
                for t in range(lo, i + 1):
                    m2 += (sret[t] - m_) ** 2
                sd = np.sqrt(m2 / c)
                vol = sd * np.sqrt(365.0) / max(g_, 0.25)
                if vol > 0:
                    lev = min(lev, vt / vol, cap)
            else:
                lev = min(lev, 1.0)
        # ---- decide rebalance
        want_flat = flat_flag[i] > 0
        force = profit_force
        if want_flat != prev_flag:
            force = True
        prev_flag = want_flat
        if resize_lvl and lvl != old_lvl:
            force = True
        due = (i >= d0 + phase) and ((i - last_reb) >= rebal)
        if not (due or force) or (i >= d1 - 1 and not profit_force):
            continue
        # ---- targets
        cnt = 0
        for j in range(n):
            if np.isfinite(score[i, j]):
                cnt += 1
        K = K0
        # design 3: shrink K (not gross) whenever per-position notional would fall below min*safe
        if design == 3 and minn > 0:
            per = eq * deploy * lev / (2.0 * K)
            if per < minn * safe:
                kk = int(np.floor(eq * deploy * lev / (2.0 * minn * safe)))
                if kk < kmin:
                    kk = kmin
                    lev = min(lev0, 2.0 * kk * minn * safe / max(eq * deploy, 1e-12))
                K = max(1, min(K, kk))
        side = np.zeros(n)
        if cnt >= 2 * K0 and not want_flat:
            order = np.argsort(-np.where(np.isfinite(score[i]), score[i], -1e18))
            rank = np.empty(n, np.int64)
            for z in range(n):
                rank[order[z]] = z
            nl = 0; ns = 0
            if band > 0:
                for z in range(cnt):
                    j = order[z]
                    if q[j] > 0 and rank[j] < K + band and nl < K:
                        side[j] = 1.0; nl += 1
                for z in range(cnt - 1, -1, -1):
                    j = order[z]
                    if q[j] < 0 and rank[j] >= cnt - K - band and ns < K and side[j] == 0.0:
                        side[j] = -1.0; ns += 1
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
            # not enough eligible names: live skips the rebalance entirely
            continue
        tgt = eq * deploy * lev / (2.0 * K)
        if gnorm:
            kept_g = 0.0; n_new = 0
            for j in range(n):
                cs_ = 1.0 if q[j] > 0 else (-1.0 if q[j] < 0 else 0.0)
                if side[j] != 0.0 and side[j] == cs_:
                    kept_g += abs(q[j]) * px[j]
                elif side[j] != 0.0:
                    n_new += 1
            if n_new > 0:
                tgt = max(eq * deploy * lev - kept_g, 0.0) / n_new
        resize_all = cw or (mode == 2 and (profit_force or factor < 1.0)) or (force and resize_lvl and not want_flat and lvl != old_lvl)
        if mode == 2 and minn > 0:
            # New entries respect the exchange floor; resizing is fractional.
            tgt = max(tgt, minn)
        c_ = 0.0
        for j in range(n):
            s = side[j]
            cs = 1.0 if q[j] > 0 else (-1.0 if q[j] < 0 else 0.0)
            if q[j] != 0.0 and s == cs:
                if resize_all and np.isfinite(px[j]):
                    new_q = s * tgt / px[j]
                    if mode == 2 and minn > 0:
                        new_q = s * max(abs(new_q), max(minn, minn_j[j]) / px[j])
                    dq = new_q - q[j]
                    if abs(new_q) < abs(q[j]):
                        W += q[j] * (1.0 - abs(new_q) / abs(q[j])) * (px[j] - e[j])
                    else:
                        e[j] = (abs(q[j]) * e[j] + abs(dq) * px[j]) / abs(new_q)
                    c_ += abs(dq) * px[j] * cost
                    q[j] = new_q
                continue
            if q[j] != 0.0:
                W += q[j] * (px[j] - e[j]); c_ += abs(q[j]) * px[j] * cost
                q[j] = 0.0; e[j] = 0.0
            if s != 0.0 and np.isfinite(px[j]) and px[j] > 0:
                n_att += 1
                qty = tgt / px[j]
                mn = max(minn, minn_j[j])
                if minn > 0:   # lot truncation only in the small-account scenario
                    st = step_j[j]
                    if st <= 0:
                        st = 10.0 ** np.ceil(np.log10(0.1 / px[j]))
                    qty = np.floor(qty / st + 1e-9) * st
                if qty <= 0 or qty * px[j] < mn:
                    n_skip += 1
                    continue
                q[j] = s * qty; e[j] = px[j]
                c_ += qty * px[j] * cost
        W -= c_
        if due:
            last_reb = i
        n_reb += 1
    npos_avg = npos_sum / max(npos_cnt, 1)
    return eq_c, eq_w, expo, np.array([n_att, n_skip, n_kill, n_reb, 1.0 if liq else 0.0, npos_avg]), withdrawals, events, loss_events, total_worst



class Sim(BaseSim):
    def run(self, profit=None, lbs=(14,), crash_flat=True, d0=None, d1=None, **kw):
        pr = params(**kw)
        pp = profit_params(**(profit or {}))
        d0 = self.d_start() if d0 is None else d0
        d1 = self.nd if d1 is None else d1
        out = _sim(self.H, self.L, self.C, self.FD, self.signal(lbs),
                   self.crash.astype(float) if crash_flat else np.zeros(self.nd),
                   pr, self.minj(pr[P_MINN]), self.step_j, d0, d1, pp)
        ec, ew, ex, st, wd, ev, loss, tw = out
        # A liquidated traded account stays at zero; withdrawn funds remain safe.
        if st[4] and pp[0] != 0:
            end = np.flatnonzero(np.isfinite(ec))[-1]
            ec[end + 1:d1] = 0; ew[end + 1:d1] = 0
            wd[end + 1:d1] = wd[end]; tw[end + 1:d1] = wd[end]
        return dict(eq=ec[d0:d1], worst=ew[d0:d1], expo=ex[d0:d1],
                    wealth=(ec + wd)[d0:d1], total_worst=tw[d0:d1],
                    withdrawn=wd[d0:d1], events=ev[d0:d1], loss=loss[d0:d1],
                    days=self.days[d0:d1], eq0=pr[P_EQ0], stats=st)
