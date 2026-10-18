"""Unified evaluation engine (numba, offline). Live-faithful core derived from rs_risk_engine.simulate:
 - signal at UTC day close, executed at that close; same-side positions KEEP quantity (live apply_targets);
 - per-position notional = equity*deploy*lev/(2K) for NEW entries; cost 0.10%/side; real funding;
 - hourly high/low worst-case (longs low, shorts high, simultaneous) cross-margin intraday equity;
 - min-notional + lot truncation on entries only (kept positions are not re-checked, as live);
Additions: hysteresis band, multi-horizon score input, regime flat flag, vol-target, delever designs, kill + re-entry,
 constant-weight mode (resize all every rebalance) for reconciliation.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from numba import njit

# parameter vector indices
(P_REBAL, P_K, P_LEV, P_DEPLOY, P_COST, P_MMR, P_KILL, P_BAND, P_VT, P_VLB, P_CAP, P_DESIGN, P_DLV, P_RLV,
 P_RESIZE, P_REARM, P_COOL, P_CW, P_MINN, P_EQ0, P_PHASE, P_FUND, P_DMULT, P_SAFE, P_KMIN, P_GN, P_N) = range(27)


def params(rebal=3, K=8, lev=1.0, deploy=1.0, cost=0.001, mmr=0.005, kill=1.0, band=0, vt=0.0, vlb=60, cap=1.5,
           design=0, dlv=0.20, rlv=0.15, resize=0, rearm=0, cool=0, cw=0, minn=0.0, eq0=1.0, phase=0, fund=1,
           dmult=0.5, safe=1.25, kmin=3, gn=0):
    v = np.zeros(P_N)
    for i, x in zip(range(P_N), (rebal, K, lev, deploy, cost, mmr, kill, band, vt, vlb, cap, design, dlv, rlv, resize,
                                 rearm, cool, cw, minn, eq0, phase, fund, dmult, safe, kmin, gn)):
        v[i] = x
    return v


@njit(cache=True)
def _sim(Hh, Ll, Cc, FD, score, flat_flag, pr, minn_j, step_j, d0, d1):
    nd, _, n = Cc.shape
    rebal = int(pr[0]); K0 = int(pr[1]); lev0 = pr[2]; deploy = pr[3]; cost = pr[4]; mmr = pr[5]; kill = pr[6]
    band = int(pr[7]); vt = pr[8]; vlb = int(pr[9]); cap = pr[10]; design = int(pr[11]); dlv = pr[12]; rlv = pr[13]
    resize_lvl = pr[14] > 0; rearm = int(pr[15]); cool = int(pr[16]); cw = pr[17] > 0; minn = pr[18]; W = pr[19]
    phase = int(pr[20]); fund_on = pr[21] > 0; dmult = pr[22]; safe = pr[23]; kmin = int(pr[24]); gnorm = pr[25] > 0
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
        sret[i] = eq / prev_eq - 1.0 if prev_eq > 0 else 0.0
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
                    W += q[j] * (px[j] - e[j]); c_ += abs(q[j]) * px[j] * cost
                    q[j] = 0.0; e[j] = 0.0
            W -= c_
            halted = True; halt_day = i; n_kill += 1
            continue
        if halted:
            if cool > 0 and i - halt_day >= cool:
                halted = False
                hwm = eq; dd = 0.0; lvl = 0
                last_reb = -10 ** 9
            else:
                continue
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
        lev = lev * mult
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
        force = False
        if want_flat != prev_flag:
            force = True
        prev_flag = want_flat
        if resize_lvl and lvl != old_lvl:
            force = True
        due = (i >= d0 + phase) and ((i - last_reb) >= rebal)
        if not (due or force) or i >= d1 - 1:
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
        resize_all = cw or (force and resize_lvl and not want_flat and lvl != old_lvl)
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
    return eq_c, eq_w, expo, np.array([n_att, n_skip, n_kill, n_reb, 1.0 if liq else 0.0, npos_avg])


# ------------------------------------------------------------------------------------------------ helpers
def zscore_signal(C: np.ndarray, lbs: tuple) -> np.ndarray:
    """cross-sectional rank z-score averaged across lookbacks (cadence-engine convention); ineligible = NaN."""
    dc = C[:, -1, :]
    sc = []; el = np.ones(dc.shape, bool)
    for lb in lbs:
        m = np.full_like(dc, np.nan); m[lb:] = dc[lb:] / dc[:-lb] - 1
        ok = np.isfinite(m); r = pd.DataFrame(m).rank(axis=1).to_numpy(); cnt = ok.sum(1, keepdims=True)
        sc.append((r - (cnt + 1) / 2) / np.sqrt(np.maximum((cnt * cnt - 1) / 12, 1))); el &= ok
    s = np.mean(sc, axis=0); s[~el] = np.nan
    return s


def btc_flags(P, thr=-0.10, lb=14, sma_n=200):
    j = P["names"].index("BTC"); c = P["C"][:, -1, j]
    sma = pd.Series(c).rolling(sma_n, min_periods=sma_n).mean().to_numpy()
    bull = np.isfinite(sma) & (c > sma)
    r14 = np.full_like(c, np.nan); r14[lb:] = c[lb:] / c[:-lb] - 1
    crash = np.isfinite(r14) & (r14 < thr)
    return bull, crash


class Sim:
    def __init__(self, P):
        self.P = P
        self.H = np.ascontiguousarray(P["H"]); self.L = np.ascontiguousarray(P["L"]); self.C = np.ascontiguousarray(P["C"])
        self.FD = np.ascontiguousarray(P["FD"]); self.names = P["names"]; self.days = P["days"]
        self.nd = len(self.days)
        self.bull, self.crash = btc_flags(P)
        self._sig = {}
        n = len(self.names)
        self.step_j = np.zeros(n)
        for b in ("BTC", "ETH"):
            if b in self.names:
                self.step_j[self.names.index(b)] = 0.001

    def minj(self, generic):
        m = np.zeros(len(self.names))
        if generic > 0:
            for b, v in (("BTC", 100.0), ("ETH", 20.0)):
                if b in self.names:
                    m[self.names.index(b)] = v
        return m

    def signal(self, lbs, regime_b=False):
        key = (tuple(lbs), regime_b)
        if key not in self._sig:
            s = zscore_signal(self.C, tuple(lbs))
            if regime_b:
                s28 = zscore_signal(self.C, (28,))
                s = np.where(self.bull[:, None], s28, s)
            self._sig[key] = s
        return self._sig[key]

    def d_start(self, date="2022-01-01"):
        return int(self.days.searchsorted(pd.Timestamp(date, tz="UTC")))

    def run(self, lbs=(14,), regime_b=False, crash_flat=False, d0=None, d1=None, crash_thr=-0.10, crash_lb=14, **kw):
        a = kw.pop("a", None); b = kw.pop("b", None)  # noqa: F841 (metrics window handled by caller)
        pr = params(**kw)
        score = self.signal(lbs, regime_b)
        if crash_flat:
            if (crash_thr, crash_lb) == (-0.10, 14):
                flag = self.crash.astype(np.float64)
            else:
                flag = btc_flags(self.P, crash_thr, crash_lb)[1].astype(np.float64)
        else:
            flag = np.zeros(self.nd)
        d0 = self.d_start() if d0 is None else d0
        d1 = self.nd if d1 is None else d1
        eq_c, eq_w, expo, st = _sim(self.H, self.L, self.C, self.FD, score, flag, pr,
                                    self.minj(pr[P_MINN]), self.step_j, d0, d1)
        return dict(eq=pd.Series(eq_c, index=self.days), worst=pd.Series(eq_w, index=self.days),
                    expo=pd.Series(expo, index=self.days), att=st[0], skip=st[1], kills=st[2], nreb=st[3],
                    liq=bool(st[4]), npos=st[5], eq0=pr[P_EQ0], d0=d0)


def window_metrics(res, a=None, b=None) -> dict | None:
    s = res["eq"].dropna(); w = res["worst"].reindex(s.index)
    if a: s = s[s.index >= pd.Timestamp(a, tz="UTC")]
    if b: s = s[s.index <= pd.Timestamp(b, tz="UTC")]
    if len(s) < 30:
        return None
    w = w.reindex(s.index)
    s0 = s.iloc[0]
    sn = s / s0; wn = w / s0
    yrs = len(s) / 365.0
    end = sn.iloc[-1]
    cagr = end ** (1 / yrs) - 1 if end > 0 else -1.0
    hw = sn.cummax()
    mdd = float(((hw - sn) / hw).max())
    prev_hw = hw.shift(1).fillna(1.0).clip(lower=1.0)
    imdd = float(((np.maximum(prev_hw, hw) - np.minimum(wn, sn)) / np.maximum(prev_hw, hw)).max())
    r = sn.pct_change().dropna()
    sd = r.std()
    yearly = {int(y): float(g.iloc[-1] / (g.iloc[0] if k == 0 else 1.0) - 1) for k, (y, g) in enumerate([])}
    return dict(cagr=float(cagr), mdd=mdd, imdd=imdd, calmar=float(cagr / imdd) if imdd > 0 else 0.0,
                sharpe=float(r.mean() / sd * np.sqrt(365)) if sd > 0 else 0.0, worst_day=float(r.min()),
                end=float(end), days=len(s))


def yearly_returns(res) -> dict:
    s = res["eq"].dropna()
    out = {}
    prev = s.iloc[0]
    for y, g in s.groupby(s.index.year):
        out[int(y)] = float(g.iloc[-1] / prev - 1); prev = g.iloc[-1]
    return out
