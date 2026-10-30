"""BACKTESTER-C leverage-realism engine (research only). Derived from rs_final_engine._sim.
Default flags (kill_mode=1, mm_mode=0) reproduce rs_final_engine._sim exactly (asserted in rs_lev_c_check.py).
Additions (all optional, see docs/research/lev_loop/C/prereg.md):
  kill_mode 1 daily close | 2 hourly close equity | 3 hourly worst-case equity | 4 = 3 + 1% slippage on closed notional
  mm_mode   0 legacy daily flat | 1 hourly tiered per-symbol | 2 hourly flat 3%
  monitors (non-terminating): tier, flat3, gap5, gap10, flash F1, flash F2 -> min buffer + first breach day
  cap_on: per-symbol max-leverage initial-margin rejection of new entries
  ev_on : delisting stress (held position hit by -90% (long) / +100% (short), then removed)
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from numba import njit
from app.rs_final_engine import Sim, params, P_MINN, zscore_signal

GAP1, GAP2 = 0.05, 0.10


@njit(cache=True)
def tier_mm(N, r1):
    if N < 5000.0:
        return N * r1
    if N < 25000.0:
        v = N * 0.025 - 75.0
    elif N < 100000.0:
        v = N * 0.05 - 700.0
    elif N < 250000.0:
        v = N * 0.10 - 5700.0
    else:
        v = N * 0.125 - 11950.0
    return max(v, N * r1)


@njit(cache=True)
def _sim_c(Hh, Ll, Cc, FD, score, flat_flag, pr, minn_j, step_j, d0, d1,
           xp, r1_j, cap_j, ev_day, ev_u, fmult, wick):
    nd, _, n = Cc.shape
    rebal = int(pr[0]); K0 = int(pr[1]); lev0 = pr[2]; deploy = pr[3]; cost = pr[4]; mmr = pr[5]; kill = pr[6]
    band = int(pr[7]); vt = pr[8]; vlb = int(pr[9]); cap = pr[10]; design = int(pr[11]); dlv = pr[12]; rlv = pr[13]
    resize_lvl = pr[14] > 0; rearm = int(pr[15]); cool = int(pr[16]); cw = pr[17] > 0; minn = pr[18]; W = pr[19]
    phase = int(pr[20]); fund_on = pr[21] > 0; dmult = pr[22]; safe = pr[23]; kmin = int(pr[24]); gnorm = pr[25] > 0
    kmode = int(xp[0]); mmmode = int(xp[1]); cap_on = xp[2] > 0; ev_on = xp[3] > 0; slip = xp[4]; usd = xp[5]
    q = np.zeros(n); e = np.zeros(n)
    eq_c = np.full(nd, np.nan); eq_w = np.full(nd, np.nan); expo = np.zeros(nd)
    kill_day = np.zeros(nd)
    sret = np.zeros(nd)
    mon = np.full((7, 3), np.nan)
    for m in range(7):
        mon[m, 0] = 1e9; mon[m, 1] = -1.0; mon[m, 2] = -1.0
    buf = np.zeros(7)
    hwm = W; prev_eq = W
    lvl = 0; halted = False; halt_day = -1; flat_days = 0
    last_reb = -10 ** 9
    n_att = 0; n_skip = 0; n_kill = 0; n_reb = 0; liq = False; liq_day = -1; npos_sum = 0.0; npos_cnt = 0
    prev_flag = False; imu_max = 0.0; n_ev = 0
    px = np.zeros(n)
    for i in range(d0, d1):
        held_any = False
        for j in range(n):
            if q[j] != 0.0:
                held_any = True
                break
        # ---- delisting event (mutates the caller's COPIES of H/L/C/score)
        if ev_on and held_any and ev_day[i] > 0:
            cntp = 0
            for j in range(n):
                if q[j] != 0.0:
                    cntp += 1
            pick = int(ev_u[i] * cntp)
            if pick >= cntp:
                pick = cntp - 1
            c2 = 0
            for j in range(n):
                if q[j] != 0.0:
                    if c2 == pick:
                        mlt = 0.1 if q[j] > 0 else 2.0
                        for h in range(12, 24):
                            Hh[i, h, j] *= mlt; Ll[i, h, j] *= mlt; Cc[i, h, j] *= mlt
                        for t in range(i, nd):
                            score[t, j] = np.nan
                        ev_day[i] = j + 1000   # mark victim
                        n_ev += 1
                        break
                    c2 += 1
        fundv = 0.0
        wmin = 0.0
        Wref = W
        den = prev_eq if prev_eq > 1e-12 else 1e-12
        killed = False
        maint_leg = 0.0
        if held_any:
            if fund_on:
                for j in range(n):
                    if q[j] != 0.0:
                        fundv -= q[j] * FD[i, j] * fmult[i]
            W += fundv
            Wref = W
            wmin = 1e300
            for h in range(24):
                s_adv = 0.0; s_cl = 0.0; mm_t = 0.0; mm_f = 0.0; mm_p = 0.0
                bestrel = -1.0; bestN = 0.0
                for j in range(n):
                    if q[j] != 0.0:
                        a = Ll[i, h, j] if q[j] > 0 else Hh[i, h, j]
                        c = Cc[i, h, j]
                        if not np.isfinite(a):
                            a = e[j]
                        if not np.isfinite(c):
                            c = e[j]
                        s_adv += q[j] * (a - e[j])
                        s_cl += q[j] * (c - e[j])
                        N = abs(q[j]) * a
                        mm_t += tier_mm(N * usd, r1_j[j]) / usd
                        mm_f += 0.03 * N
                        # gap: largest adverse relative move vs previous close
                        if h > 0:
                            ref = Cc[i, h - 1, j]
                        elif i > 0:
                            ref = Cc[i - 1, 23, j]
                        else:
                            ref = np.nan
                        if np.isfinite(ref) and ref > 0:
                            rel = (ref - a) / ref if q[j] > 0 else (a - ref) / ref
                            if rel > bestrel:
                                bestrel = rel; bestN = N
                if s_adv < wmin:
                    wmin = s_adv
                eqh = Wref + s_adv
                if mmmode == 1:
                    mm_p = mm_t
                else:
                    mm_p = mm_f
                # monitors: 0 tier,1 flat3,2 gap5,3 gap10
                buf[0] = (eqh - mm_t) / den
                buf[1] = (eqh - mm_f) / den
                buf[2] = (eqh - GAP1 * bestN - mm_t) / den
                buf[3] = (eqh - GAP2 * bestN - mm_t) / den
                for m in range(4):
                    if buf[m] < mon[m, 0]:
                        mon[m, 0] = buf[m]; mon[m, 2] = i
                    if buf[m] <= 0.0 and mon[m, 1] < 0:
                        mon[m, 1] = i
                if mmmode >= 1 and eqh <= mm_p:
                    liq = True; liq_day = i
                    break
                if kmode >= 2 and (not halted):
                    eq_test = (Wref + s_cl) if kmode == 2 else eqh
                    if hwm > 0 and 1.0 - eq_test / hwm >= kill:
                        c_ = 0.0
                        for j in range(n):
                            if q[j] != 0.0:
                                if kmode == 2:
                                    pp = Cc[i, h, j]
                                else:
                                    pp = Ll[i, h, j] if q[j] > 0 else Hh[i, h, j]
                                if not np.isfinite(pp):
                                    pp = e[j]
                                W += q[j] * (pp - e[j]); c_ += abs(q[j]) * pp * (cost + (slip if (kmode == 4 or kmode == 6) else 0.0))
                                q[j] = 0.0; e[j] = 0.0
                        if kmode >= 5:
                            # POST-HOC variant: continuous monitor executes at the threshold-crossing level, not the bar extreme
                            W = hwm * (1.0 - kill)
                        W -= c_
                        halted = True; halt_day = i; n_kill += 1; kill_day[i] = 1.0
                        killed = True
                        break
                    if (Wref + s_cl) > hwm:
                        hwm = Wref + s_cl
            if liq:
                eq_c[i] = 0.0; eq_w[i] = 0.0
                break
            if mmmode == 0:
                # legacy day-level test, identical to rs_final_engine
                for j in range(n):
                    if q[j] != 0.0:
                        mx = 0.0
                        for h in range(24):
                            v = Hh[i, h, j]
                            if np.isfinite(v) and v > mx:
                                mx = v
                        maint_leg += abs(q[j]) * max(mx, e[j]) * mmr
                if Wref + wmin <= maint_leg:
                    liq = True; liq_day = i
                    eq_c[i] = 0.0; eq_w[i] = 0.0
                    break
        if killed:
            eq_c[i] = W
            eq_w[i] = Wref + wmin if wmin < 1e299 else W
            expo[i] = 0.0
            sret[i] = W / prev_eq - 1.0 if prev_eq > 0 else 0.0
            prev_eq = W
            continue
        worst = Wref + wmin if held_any else W
        for j in range(n):
            v = Cc[i, 23, j]
            px[j] = v if np.isfinite(v) else (e[j] if e[j] > 0 else np.nan)
        # ---- flash monitors (4: F1 on close equity, 5: F2 on worst-case equity)
        if held_any:
            eqc = W; lossw = 0.0; mm_c = 0.0; lossl = 0.0
            for j in range(n):
                if q[j] != 0.0:
                    eqc += q[j] * (px[j] - e[j])
                    wj = wick[j]
                    lossw += abs(q[j]) * px[j] * wj
                    if q[j] > 0:
                        lossl += q[j] * px[j] * wj
                    mm_c += tier_mm(abs(q[j]) * px[j] * usd, r1_j[j]) / usd
            buf[4] = (eqc - lossw - mm_c) / den
            buf[5] = (worst - lossw - mm_c) / den
            buf[6] = (eqc - lossl - mm_c) / den
            for m in range(4, 7):
                if buf[m] < mon[m, 0]:
                    mon[m, 0] = buf[m]; mon[m, 2] = i
                if buf[m] <= 0.0 and mon[m, 1] < 0:
                    mon[m, 1] = i
        # ---- delisting: realise the victim at the (mutated) close and drop it
        if ev_on and ev_day[i] >= 1000:
            jv = int(ev_day[i]) - 1000
            if q[jv] != 0.0:
                W += q[jv] * (px[jv] - e[jv]); W -= abs(q[jv]) * px[jv] * cost
                q[jv] = 0.0; e[jv] = 0.0
        eq = W
        gross_n = 0.0
        npos = 0
        imu = 0.0
        for j in range(n):
            if q[j] != 0.0:
                eq += q[j] * (px[j] - e[j])
                gross_n += abs(q[j] * px[j])
                imu += abs(q[j] * px[j]) / cap_j[j]
                npos += 1
        eq_c[i] = eq; eq_w[i] = worst
        if eq > 0 and imu / eq > imu_max:
            imu_max = imu / eq
        expo[i] = gross_n / max(eq, 1e-12)
        sret[i] = eq / prev_eq - 1.0 if prev_eq > 0 else 0.0
        prev_eq = eq
        npos_sum += npos; npos_cnt += 1
        if eq > hwm:
            hwm = eq
        dd = 1.0 - eq / hwm
        if (not halted) and dd >= kill:
            c_ = 0.0
            for j in range(n):
                if q[j] != 0.0:
                    W += q[j] * (px[j] - e[j]); c_ += abs(q[j]) * px[j] * cost
                    q[j] = 0.0; e[j] = 0.0
            W -= c_
            halted = True; halt_day = i; n_kill += 1; kill_day[i] = 1.0
            continue
        if halted:
            if cool > 0 and i - halt_day >= cool:
                halted = False
                hwm = eq; dd = 0.0; lvl = 0
                last_reb = -10 ** 9
            else:
                continue
        if rearm > 0:
            if npos == 0:
                flat_days += 1
                if flat_days >= rearm and dd > 0:
                    hwm = eq; dd = 0.0; flat_days = 0
            else:
                flat_days = 0
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
        lev = lev * mult
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
        want_flat = flat_flag[i] > 0
        force = False
        if want_flat != prev_flag:
            force = True
        prev_flag = want_flat
        if resize_lvl and lvl != old_lvl:
            force = True
        due = (i >= d0 + phase) and ((i - last_reb) >= rebal)
        if not (due or force) or i >= d1 - 1:
            continue
        cnt = 0
        for j in range(n):
            if np.isfinite(score[i, j]):
                cnt += 1
        K = K0
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
        resize_all = cw or (force and resize_lvl and not want_flat and lvl != old_lvl)
        im_base = 0.0
        if cap_on:
            for j in range(n):
                cs_ = 1.0 if q[j] > 0 else (-1.0 if q[j] < 0 else 0.0)
                if q[j] != 0.0 and side[j] == cs_ and np.isfinite(px[j]):
                    im_base += abs(q[j]) * px[j] / cap_j[j]
        c_ = 0.0
        for j in range(n):
            s = side[j]
            cs = 1.0 if q[j] > 0 else (-1.0 if q[j] < 0 else 0.0)
            if q[j] != 0.0 and s == cs:
                if resize_all and np.isfinite(px[j]):
                    new_q = s * tgt / px[j]
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
                if minn > 0:
                    st = step_j[j]
                    if st <= 0:
                        st = 10.0 ** np.ceil(np.log10(0.1 / px[j]))
                    qty = np.floor(qty / st + 1e-9) * st
                if qty <= 0 or qty * px[j] < mn:
                    n_skip += 1
                    continue
                if cap_on:
                    imn = qty * px[j] / cap_j[j]
                    if im_base + imn > eq:
                        n_skip += 1
                        continue
                    im_base += imn
                q[j] = s * qty; e[j] = px[j]
                c_ += qty * px[j] * cost
        W -= c_
        if due:
            last_reb = i
        n_reb += 1
    npos_avg = npos_sum / max(npos_cnt, 1)
    return eq_c, eq_w, expo, kill_day, mon, np.array([n_att, n_skip, n_kill, n_reb, 1.0 if liq else 0.0, npos_avg,
                                                      float(liq_day), imu_max, float(n_ev)])


MAJOR = ("BNB", "XRP", "SOL", "TRX", "DOGE", "ADA", "LINK", "LTC", "BCH", "AVAX", "XLM")


class LSim(Sim):
    def __init__(self, P):
        super().__init__(P)
        n = len(self.names)
        nm = [str(x) for x in self.names]
        self.nm = nm
        self.r1_base = np.array([0.004 if b in ("BTC", "ETH") else 0.01 for b in nm])
        self.cap_base = np.array([100.0 if b in ("BTC", "ETH") else 50.0 for b in nm])
        self.cap_a = np.array([100.0 if b in ("BTC", "ETH") else (50.0 if b in MAJOR else 10.0) for b in nm])
        self.cap_b = np.array([100.0 if b in ("BTC", "ETH") else 5.0 for b in nm])
        # flash F1 wick magnitudes from 2025-10-10
        d = int(self.days.searchsorted(pd.Timestamp("2025-10-10", tz="UTC")))
        ref = self.C[d - 1, 23, :]
        lo = np.nanmin(np.where(np.isfinite(self.L[d]), self.L[d], np.inf), axis=0)
        w = np.where(np.isfinite(ref) & np.isfinite(lo) & (lo < 1e300), np.maximum(0.0, 1.0 - lo / ref), np.nan)
        med = float(np.nanmedian(w))
        self.wick = np.where(np.isfinite(w), w, med)
        self.wick_day = d
        # funding-stress window: 30d sum of cross-sectional mean |FD| max (strategy independent)
        fd = np.abs(np.nan_to_num(self.FD))
        m = fd.mean(axis=1)
        d0 = self.d_start()
        s = pd.Series(m).rolling(30).sum().to_numpy().copy()
        s[:d0 + 29] = -1
        e_ = int(np.nanargmax(s))
        self.fwin = (e_ - 29, e_)
        self._ones = np.ones(self.nd)

    def score_sub(self, cols, lbs=(14,)):
        key = ("sub", tuple(cols), tuple(lbs))
        if key not in self._sig:
            s = np.full(self.C.shape[0:1] + (self.C.shape[2],), np.nan)
            s[:, list(cols)] = zscore_signal(np.ascontiguousarray(self.C[:, :, list(cols)]), tuple(lbs))
            self._sig[key] = s
        return self._sig[key]

    def fmult_stress(self, mult=3.0):
        f = np.ones(self.nd)
        f[self.fwin[0]:self.fwin[1] + 1] = mult
        return f

    def make_events(self, seed, d_from):
        rng = np.random.default_rng(seed)
        ev = np.zeros(self.nd); u = np.zeros(self.nd)
        yrs = self.days.year
        for y in sorted(set(int(v) for v in yrs[d_from:])):
            idx = np.where((yrs == y))[0]
            idx = idx[(idx >= d_from + 30) & (idx <= self.nd - 30)]
            if len(idx) < 3:
                continue
            ch = rng.choice(idx, size=3, replace=False)
            for c in ch:
                ev[c] = 1.0; u[c] = rng.random()
        return ev, u

    def run_c(self, lev, deploy, phase=0, d0=None, d1=None, kill_mode=1, mm_mode=0, r1=None, capj=None, cap_on=0,
              cols=None, events=None, fmult=None, minn=0.0, eq0=1.0, kill=0.35, slip=0.01, usd=127.0, crash_flat=True):
        pr = params(rebal=3, K=8, lev=lev, deploy=deploy, cost=0.001, kill=kill, cool=14, fund=1, minn=minn, eq0=eq0,
                    phase=phase)
        score = self.signal((14,)) if cols is None else self.score_sub(cols)
        d0 = self.d_start() if d0 is None else d0
        d1 = self.nd if d1 is None else d1
        flag = self.crash.astype(np.float64) if crash_flat else np.zeros(self.nd)
        H, L, C = self.H, self.L, self.C
        ev_on = 0.0
        evd = np.zeros(self.nd); evu = np.zeros(self.nd)
        if events is not None:
            H, L, C = H.copy(), L.copy(), C.copy()
            score = score.copy()
            evd = events[0].copy(); evu = events[1]; ev_on = 1.0
        xp = np.array([kill_mode, mm_mode, float(cap_on), ev_on, slip, 1.0 if eq0 != 1.0 and usd == 127.0 and eq0 > 1 else usd])
        # usd: converts normalised equity to USD for tier brackets (eq0=1 normalised -> $127 account)
        xp[5] = 1.0 if eq0 > 1.0 else usd
        r1 = self.r1_base if r1 is None else r1
        capj = self.cap_base if capj is None else capj
        fm = self._ones if fmult is None else fmult
        eq_c, eq_w, expo, kd, mon, st = _sim_c(H, L, C, self.FD, score, flag, pr, self.minj(pr[P_MINN]), self.step_j,
                                              d0, d1, xp, r1, capj, evd, evu, fm, self.wick)
        liq = bool(st[4])
        if liq:
            li = int(st[6])
            prev = eq_c[:li][np.isfinite(eq_c[:li])]
            eq_c[li] = 0.01 * (prev[-1] if len(prev) else eq0)
        return dict(eq=pd.Series(eq_c, index=self.days), worst=pd.Series(eq_w, index=self.days),
                    expo=pd.Series(expo, index=self.days), kill_day=kd, mon=mon, att=st[0], skip=st[1], kills=st[2],
                    nreb=st[3], liq=liq, liq_day=int(st[6]), npos=st[5], imu=st[7], nev=st[8], eq0=eq0, d0=d0)
