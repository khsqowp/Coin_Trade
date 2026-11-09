"""BACKTESTER-B (lev_loop) research engine. OFFLINE ONLY (no live code touched).

Derived line-by-line from rs_final_engine._sim (V0 semantics: signal at UTC day close executed at that close, same-side
quantities KEPT, cost per side, real funding applied at start of day, hourly simultaneous worst-case H/L equity).
Additions (all gated; with defaults the result is BIT-IDENTICAL to rs_final_engine._sim, asserted in rs_lev_b_check.py):
  intra   : kill / ladder evaluated every HOUR on worst-case equity (longs at L, shorts at H) vs HWM (HWM from hourly close
            marks); executed at that hour's adverse marks (conservative stand-in for the live 15 s check + market order).
            intra=0 -> daily-close evaluation (V0 behaviour).
  norm    : after each rebalance scale ALL positions uniformly so gross = eq*deploy*lev_eff*m (gross normalisation).
  ladder  : DD rungs (rd[k] -> exposure multiplier rm[k]) scale all positions down at once; re-lever (one rung/day) when
            close-DD < rec_frac*rung; the new (higher) size is applied at the next rebalance (norm).
  vol tgt : lev_eff = clip(vt / unit_vol, vmin, vcap); unit_vol = trailing vwin-day stdev of (daily equity return /
            start-of-day gross exposure) * sqrt(365); warm-up lev vwarm until >=10 valid days.
  re-entry: multiplier re_m for re_days after cooldown ends.
  expx    : sizing base = W0^(1-expx) * eq^expx (1 = compounding, 0 = fixed notional).
  liquidation: hourly cross-margin test eqW <= maintenance, for BOTH tiered (0.5/1/2.5/5% by per-position USD notional,
            usd = account scale) and flat mflat (3%). Flags only (the path continues), plus max margin ratio.
"""
from __future__ import annotations
import numpy as np
from numba import njit

from app.rs_final_engine import Sim, params

(B_INTRA, B_NORM, B_NR, B_RECF, B_REM, B_REDAYS, B_VT, B_VCAP, B_VWIN, B_VWARM, B_EXPX, B_USD, B_MFLAT, B_VMIN,
 B_SLIP, B_EXEC, B_MBREAK, B_HW, B_TT, B_TW, B_N) = range(21)
NTR = 60000


def pbvec(intra=1, norm=0, nr=0, rec_frac=0.5, re_m=1.0, re_days=0, vt=0.0, vcap=6.0, vwin=20, vwarm=2.0, expx=1.0,
          usd=10000.0, mflat=0.03, vmin=1.0, slip=0.002, exec_=0, mbreak=1, hw=0, tt=0.0, tw=90):
    v = np.zeros(B_N)
    for i, x in zip(range(B_N), (intra, norm, nr, rec_frac, re_m, re_days, vt, vcap, vwin, vwarm, expx, usd, mflat, vmin, slip, exec_, mbreak, hw, tt, tw)):
        v[i] = x
    return v


@njit(cache=True)
def _scale_down(q, e, pxv, s, cost, contrib, trp, ntr, eqref, n):
    dW = 0.0
    for j in range(n):
        if q[j] != 0.0:
            pj = pxv[j]
            if not np.isfinite(pj):
                pj = e[j]
            part = q[j] * (1.0 - s)
            pnl = part * (pj - e[j])
            dW += pnl - abs(part) * pj * cost
            contrib[j] += pnl / eqref
            if ntr < trp.shape[0]:
                trp[ntr] = pnl / eqref
                ntr += 1
            q[j] *= s
    return dW, ntr


@njit(cache=True)
def _cross_marks(q, e, Cc, pxp, i, h, advp, W, T, adv_mode, xv, n):
    """first-passage marks: book equity moves linearly from previous-hour close marks c0 to adverse marks a;
    returns marks x = c0 + lam*(a-c0) at the point where equity == T (lam in [0,1]); adv_mode -> x = a."""
    ep = W; ew = W
    for j in range(n):
        if q[j] != 0.0:
            c0 = pxp[j] if h == 0 else Cc[i, h - 1, j]
            if not np.isfinite(c0):
                c0 = e[j]
            a = advp[j] if np.isfinite(advp[j]) else c0
            ep += q[j] * (c0 - e[j]); ew += q[j] * (a - e[j])
    if adv_mode:
        lam = 1.0
    elif ep - ew <= 1e-15:
        lam = 1.0
    else:
        lam = min(1.0, max(0.0, (ep - T) / (ep - ew)))
    for j in range(n):
        if q[j] != 0.0:
            c0 = pxp[j] if h == 0 else Cc[i, h - 1, j]
            if not np.isfinite(c0):
                c0 = e[j]
            a = advp[j] if np.isfinite(advp[j]) else c0
            xv[j] = c0 + lam * (a - c0)
        else:
            xv[j] = np.nan
    return lam


@njit(cache=True)
def _simb(Hh, Ll, Cc, FD, score, flat_flag, pr, pb, rd, rm, d0, d1, rec_h):
    nd, _, n = Cc.shape
    rebal = int(pr[0]); K0 = int(pr[1]); lev0 = pr[2]; deploy = pr[3]; cost = pr[4]; kill = pr[6]
    cool = int(pr[16]); W0 = pr[19]; W = pr[19]; phase = int(pr[20]); fund_on = pr[21] > 0
    intra = pb[0] > 0; norm = pb[1] > 0; nr = int(pb[2]); rec_frac = pb[3]; re_m = pb[4]; re_days = int(pb[5])
    vt = pb[6]; vcap = pb[7]; vwin = int(pb[8]); vwarm = pb[9]; expx = pb[10]; usd = pb[11]; mflat = pb[12]; vmin = pb[13]; slip = pb[14]; exec_adv = pb[15] > 0
    mbreak = int(pb[16]); hw = int(pb[17]); tt = pb[18]; tw = int(pb[19])
    trig = int(pb[0])
    rec = rec_h.shape[0] > 1
    q = np.zeros(n); e = np.zeros(n); px = np.zeros(n); pxp = np.zeros(n); advp = np.zeros(n); advw = np.zeros(n); xv = np.zeros(n)
    contrib = np.zeros(n); trp = np.zeros(NTR); ntr = 0
    eq_c = np.full(nd, np.nan); eq_w = np.full(nd, np.nan); expo = np.zeros(nd)
    sret = np.zeros(nd); uarr = np.full(nd, np.nan)
    hwm = W; prev_eq = W
    halted = False; halt_day = -1
    last_reb = -10 ** 9
    n_kill = 0; n_dlv = 0; n_reb = 0; n_skip = 0
    liq_t = 0.0; liq_f = 0.0; mr_t = 0.0; mr_f = 0.0; hloss = 0.0
    prev_flag = False
    rung = 0; mact = 1.0; reentry_day = -10 ** 9
    gsum = 0.0; gcnt = 0; gmax = 0.0; hdays = 0
    eq = W
    liq_day = -1
    hwm_l = W; dpk_run = W; dpk_start = d0
    dpk = np.full(nd, np.nan); uw = np.full(nd, np.nan)
    for i in range(d0, d1):
        dpk_run = 0.0
        if hw > 0:
            hwm_l = 0.0
            for t in range(max(d0, i - hw, dpk_start), i):
                if np.isfinite(dpk[t]) and dpk[t] > hwm_l:
                    hwm_l = dpk[t]
            if hwm_l <= 0.0:
                hwm_l = prev_eq
        else:
            hwm_l = hwm
        held_any = False
        for j in range(n):
            if q[j] != 0.0:
                held_any = True
                break
        fund = 0.0
        worst = W
        g_start = 0.0
        killed_today = False
        if held_any:
            gs = 0.0
            for j in range(n):
                if q[j] != 0.0:
                    p_ = pxp[j]
                    if not np.isfinite(p_):
                        p_ = e[j]
                    gs += abs(q[j]) * p_
            g_start = gs / prev_eq if prev_eq > 0 else 0.0
            if fund_on:
                for j in range(n):
                    if q[j] != 0.0:
                        fund -= q[j] * FD[i, j]
            if intra:
                W += fund
                fund = 0.0
            wmin = 1e300
            hl_day = 0.0
            if intra:
                worst = 1e300
            for h in range(24):
                sadv = 0.0; sc = 0.0; mt = 0.0; mf = 0.0; ep_ = W
                for j in range(n):
                    advp[j] = np.nan; advw[j] = np.nan
                    if q[j] != 0.0:
                        a = Ll[i, h, j] if q[j] > 0 else Hh[i, h, j]
                        c = Cc[i, h, j]
                        c0_ = pxp[j] if h == 0 else Cc[i, h - 1, j]
                        if np.isfinite(c0_):
                            ep_ += q[j] * (c0_ - e[j])
                        if np.isfinite(a):
                            sadv += q[j] * (a - e[j])
                            nt = abs(q[j]) * a
                            mf += nt * mflat
                            nu = nt * usd
                            if nu <= 5e4:
                                rt = 0.005
                            elif nu <= 2.5e5:
                                rt = 0.01
                            elif nu <= 1e6:
                                rt = 0.025
                            else:
                                rt = 0.05
                            mt += nt * rt
                            advp[j] = a; advw[j] = a
                        if np.isfinite(c):
                            sc += q[j] * (c - e[j])
                if sadv < wmin:
                    wmin = sadv
                eqW = W + fund + sadv
                eqCm = W + fund + sc
                if ep_ > 0 and (ep_ - eqW) / ep_ > hl_day:
                    hl_day = (ep_ - eqW) / ep_
                liqf = eqW <= mf
                liqt = eqW <= mt
                if liqt:
                    liq_t = 1.0
                if liqf:
                    liq_f = 1.0
                if eqW > 0:
                    if mt / eqW > mr_t:
                        mr_t = mt / eqW
                    if mf / eqW > mr_f:
                        mr_f = mf / eqW
                else:
                    mr_t = 1e9; mr_f = 1e9
                if (mbreak == 1 and liqf) or (mbreak == 0 and liqt):
                    liq_day = i
                    break
                if intra:
                    ew_post = eqW
                    if trig == 2:
                        eqT = eqCm
                        for j in range(n):
                            if q[j] != 0.0:
                                advp[j] = Cc[i, h, j]
                    else:
                        eqT = eqW
                    # ladder reference (rolling or all-time HWM)
                    hl_ref = hwm_l
                    ddw = 1.0 - eqT / hwm
                    ddl = 1.0 - eqT / hl_ref
                    if nr > 0 and ddl >= rd[0]:
                        rr = 0
                        for k in range(nr):
                            if ddl >= rd[k]:
                                rr = k + 1
                        while rung < rr:
                            Tk = hl_ref * (1.0 - rd[rung])
                            _cross_marks(q, e, Cc, pxp, i, h, advp, W, Tk, exec_adv, xv, n)
                            rung += 1
                            m_ = rm[rung - 1]
                            if m_ < mact:
                                dW, ntr = _scale_down(q, e, xv, m_ / mact, cost + slip, contrib, trp, ntr, max(Tk, 1e-12), n)
                                W += dW
                                mact = m_
                                n_dlv += 1
                        sadv = 0.0
                        sadw = 0.0
                        for j in range(n):
                            if q[j] != 0.0 and np.isfinite(advp[j]):
                                sadv += q[j] * (advp[j] - e[j])
                            if q[j] != 0.0 and np.isfinite(advw[j]):
                                sadw += q[j] * (advw[j] - e[j])
                        eqT = W + sadv
                        ew_post = W + sadw
                        ddw = 1.0 - eqT / hwm
                    if (not halted) and ddw >= kill:
                        Tk = hwm * (1.0 - kill)
                        _cross_marks(q, e, Cc, pxp, i, h, advp, W, Tk, exec_adv, xv, n)
                        c_ = 0.0
                        for j in range(n):
                            if q[j] != 0.0:
                                a = xv[j]
                                pnl = q[j] * (a - e[j])
                                W += pnl; c_ += abs(q[j]) * a * (cost + slip)
                                contrib[j] += pnl / max(Tk, 1e-12)
                                if ntr < NTR:
                                    trp[ntr] = pnl / max(Tk, 1e-12); ntr += 1
                                q[j] = 0.0; e[j] = 0.0
                        W -= c_
                        halted = True; halt_day = i; n_kill += 1; killed_today = True
                        mact = 1.0; rung = 0
                        if W < worst:
                            worst = W
                        break
                    if ew_post < worst:
                        worst = ew_post
                    eqC = W
                    for j in range(n):
                        if q[j] != 0.0:
                            c = Cc[i, h, j]
                            if np.isfinite(c):
                                eqC += q[j] * (c - e[j])
                    if eqC > hwm:
                        hwm = eqC
                    if eqC > hwm_l:
                        hwm_l = eqC
                    if eqC > dpk_run:
                        dpk_run = eqC
                    if rec:
                        rec_h[i, h] = eqC
                else:
                    if rec:
                        rec_h[i, h] = eqCm
            if liq_day == i:
                eq_c[i] = 0.0; eq_w[i] = 0.0
                break
            if not intra:
                worst = W + fund + wmin
            if hl_day > hloss:
                hloss = hl_day
            if g_start > 0.2 and hl_day > 0:
                uw[i] = hl_day / g_start
        else:
            if rec:
                for h in range(24):
                    rec_h[i, h] = W
        if killed_today:
            eq = W
            dpk[i] = max(dpk_run, eq)
            eq_c[i] = eq; eq_w[i] = worst; expo[i] = 0.0
            sret[i] = eq / prev_eq - 1.0 if prev_eq > 0 else 0.0
            prev_eq = eq
            if rec:
                rec_h[i, 23] = eq
            continue
        if held_any and (not intra):
            W += fund
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
        dpk[i] = max(dpk_run, eq)
        expo[i] = gross_n / max(eq, 1e-12)
        sret[i] = eq / prev_eq - 1.0 if prev_eq > 0 else 0.0
        if held_any and g_start > 0.2:
            uarr[i] = sret[i] / g_start
        prev_eq = eq
        if npos > 0:
            gsum += expo[i]; gcnt += 1
            if expo[i] > gmax:
                gmax = expo[i]
        for j in range(n):
            pxp[j] = px[j]
        if eq > hwm:
            hwm = eq
        dd = 1.0 - eq / hwm
        if (not halted) and dd >= kill:
            c_ = 0.0
            for j in range(n):
                if q[j] != 0.0:
                    pnl = q[j] * (px[j] - e[j])
                    W += pnl; c_ += abs(q[j]) * px[j] * cost
                    contrib[j] += pnl / max(eq, 1e-12)
                    if ntr < NTR:
                        trp[ntr] = pnl / max(eq, 1e-12); ntr += 1
                    q[j] = 0.0; e[j] = 0.0
            W -= c_
            halted = True; halt_day = i; n_kill += 1
            mact = 1.0; rung = 0
            continue
        if halted:
            hdays += 1
            if cool > 0 and i - halt_day >= cool:
                halted = False
                hwm = eq; dd = 0.0
                last_reb = -10 ** 9
                reentry_day = i; dpk_start = i
                rung = 0; mact = 1.0
            else:
                continue
        # ---- daily-close ladder (trig=0) and re-lever (all modes)
        if nr > 0:
            ref_l = hwm_l if hwm_l > eq else eq
            ddl = 1.0 - eq / ref_l
            if not intra:
                rr = 0
                for k in range(nr):
                    if ddl >= rd[k]:
                        rr = k + 1
                if rr > rung:
                    rung = rr
                    m_ = rm[rr - 1]
                    if m_ < mact:
                        dW, ntr = _scale_down(q, e, px, m_ / mact, cost, contrib, trp, ntr, max(eq, 1e-12), n)
                        W += dW
                        mact = m_
                        n_dlv += 1
            if rung > 0 and ddl < rec_frac * rd[rung - 1]:
                rung -= 1
        # ---- decide rebalance
        want_flat = flat_flag[i] > 0
        force = False
        if want_flat != prev_flag:
            force = True
        prev_flag = want_flat
        due = (i >= d0 + phase) and ((i - last_reb) >= rebal)
        if not (due or force) or i >= d1 - 1:
            continue
        # ---- sizing
        lev_eff = lev0
        if vt > 0:
            cntv = 0; sm = 0.0; sm2 = 0.0
            lo = max(d0, i - vwin + 1)
            for t in range(lo, i + 1):
                v = uarr[t]
                if np.isfinite(v):
                    cntv += 1; sm += v
            if cntv >= 10:
                mean_ = sm / cntv
                for t in range(lo, i + 1):
                    v = uarr[t]
                    if np.isfinite(v):
                        sm2 += (v - mean_) ** 2
                uvol = np.sqrt(sm2 / cntv) * np.sqrt(365.0)
                lev_eff = min(vcap, max(vmin, vt / max(uvol, 1e-9)))
            else:
                lev_eff = vwarm
        if tt > 0:
            cnt2 = 0; mx = 0.0
            lo2 = max(d0, i - tw + 1)
            for t in range(lo2, i + 1):
                v = uw[t]
                if np.isfinite(v):
                    cnt2 += 1
                    if v > mx:
                        mx = v
            if cnt2 >= 20:
                l2 = min(vcap, max(vmin, tt / max(mx, 1e-9)))
            else:
                l2 = vwarm
            lev_eff = l2 if vt <= 0 else min(lev_eff, l2)
        m_size = 1.0
        if rung > 0:
            m_size = rm[rung - 1]
        if re_days > 0 and (i - reentry_day) < re_days:
            m_size = m_size * re_m
        if expx == 1.0:
            eqs = eq
        else:
            eqs = W0 ** (1.0 - expx) * eq ** expx
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
        tgt = eqs * deploy * lev_eff * m_size / (2.0 * K)
        c_ = 0.0
        for j in range(n):
            s = side[j]
            cs = 1.0 if q[j] > 0 else (-1.0 if q[j] < 0 else 0.0)
            if q[j] != 0.0 and s == cs:
                continue
            if q[j] != 0.0:
                pnl = q[j] * (px[j] - e[j])
                W += pnl; c_ += abs(q[j]) * px[j] * cost
                contrib[j] += pnl / max(eq, 1e-12)
                if ntr < NTR:
                    trp[ntr] = pnl / max(eq, 1e-12); ntr += 1
                q[j] = 0.0; e[j] = 0.0
            if s != 0.0 and np.isfinite(px[j]) and px[j] > 0:
                qty = tgt / px[j]
                if qty <= 0:
                    n_skip += 1
                    continue
                q[j] = s * qty; e[j] = px[j]
                c_ += qty * px[j] * cost
        W -= c_
        if norm:
            G = 0.0
            for j in range(n):
                if q[j] != 0.0 and np.isfinite(px[j]):
                    G += abs(q[j]) * px[j]
            if G > 0:
                eq_now = W
                for j in range(n):
                    if q[j] != 0.0 and np.isfinite(px[j]):
                        eq_now += q[j] * (px[j] - e[j])
                Gt = max(eqs * (eq_now / max(eq, 1e-12)), 0.0) * deploy * lev_eff * m_size
                s_ = min(4.0, max(0.25, Gt / G))
                c2 = 0.0
                for j in range(n):
                    if q[j] != 0.0 and np.isfinite(px[j]):
                        dq = q[j] * (s_ - 1.0)
                        if s_ < 1.0:
                            pnl = -dq * (px[j] - e[j])
                            W += pnl
                            contrib[j] += pnl / max(eq, 1e-12)
                        else:
                            e[j] = (abs(q[j]) * e[j] + abs(dq) * px[j]) / (abs(q[j]) + abs(dq))
                        c2 += abs(dq) * px[j] * cost
                        q[j] += dq
                W -= c2
        mact = m_size
        if due:
            last_reb = i
        n_reb += 1
    # unrealised marks into attribution
    for j in range(n):
        if q[j] != 0.0 and np.isfinite(px[j]):
            contrib[j] += q[j] * (px[j] - e[j]) / max(eq, 1e-12)
    avg_g = gsum / max(gcnt, 1)
    st = np.array([n_kill, n_dlv, n_reb, liq_t, liq_f, mr_t, mr_f, avg_g, gmax, hdays, ntr, n_skip, hloss, liq_day], dtype=np.float64)
    return eq_c, eq_w, expo, st, contrib, trp[:ntr].copy(), uarr


STAT = ("kills", "dlv", "nreb", "liq_t", "liq_f", "mr_t", "mr_f", "avg_g", "max_g", "halt_days", "ntr", "skip", "hloss", "liq_day")


class BSim(Sim):
    """Adds run_b(...). Optional stress panels (vol multiplier m_vol on log price; fee/funding multipliers)."""

    def __init__(self, P, m_vol=1.0, fund_mult=1.0):
        super().__init__(P)
        if m_vol != 1.0:
            C0 = self.C
            first = np.ones(C0.shape[2])
            for j in range(C0.shape[2]):
                ok = np.where(np.isfinite(C0[:, :, j].ravel()))[0]
                if len(ok):
                    first[j] = C0[:, :, j].ravel()[ok[0]]
            orig_n = C0[:, 23, :] / first[None, :]
            for k in ("H", "L", "C"):
                a = getattr(self, k)
                setattr(self, k, np.ascontiguousarray((a / first[None, None, :]) ** m_vol))
            # funding is a fraction of notional: FD' = FD * C'/C = FD * C_norm^(m-1) / first
            rr = np.where(np.isfinite(orig_n) & (orig_n > 0), orig_n ** (m_vol - 1.0) / first[None, :], 1.0)
            self.FD = np.ascontiguousarray(np.asarray(self.FD) * rr)
        if fund_mult != 1.0:
            self.FD = np.ascontiguousarray(self.FD * fund_mult)

    def run_b(self, d0, d1, phase=0, pb=None, rd=None, rm=None, rec_h=False, **kw):
        kw.setdefault("rebal", 3); kw.setdefault("K", 8); kw.setdefault("kill", 0.35); kw.setdefault("cool", 14)
        kw.setdefault("cost", 0.001); kw.setdefault("fund", 1)
        pr = params(phase=phase, **kw)
        score = self.signal((14,), False)
        flag = self.crash.astype(np.float64)
        pb = pbvec() if pb is None else pb
        rd = np.zeros(4) if rd is None else np.asarray(rd, float)
        rm = np.ones(4) if rm is None else np.asarray(rm, float)
        rh = np.zeros((self.nd, 24)) if rec_h else np.zeros((1, 1))
        eq_c, eq_w, expo, st, contrib, trp, uarr = _simb(self.H, self.L, self.C, self.FD, score, flag, pr, pb, rd, rm,
                                                          d0, d1, rh)
        out = dict(eq=eq_c, worst=eq_w, expo=expo, contrib=contrib, trp=trp, uarr=uarr, d0=d0, d1=d1)
        out.update({k: float(v) for k, v in zip(STAT, st)})
        if rec_h:
            out["rec_h"] = rh
        return out
