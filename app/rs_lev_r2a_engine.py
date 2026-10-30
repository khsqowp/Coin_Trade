"""R2-A engine: V0 (momentum long/short rotation, kept-qty) + hourly layer for (i) kill-model bracket
(daily close / hourly close / lambda-interpolated) and (ii) structural tail caps (gross/eq, |net|/eq, single symbol).
Research only, offline. Semantics mirror review/indep_sim.py (V0) and review/lambda_kill.py (hourly kill).
Numba-compiled; reads only the saved panel npz (path from env RS_FINAL_SCRATCH)."""
import os, numpy as np, pandas as pd
from numba import njit

SCR = os.environ["RS_FINAL_SCRATCH"]
PANEL_PATH = os.path.join(SCR, "rs_final_panel.npz")
Z = np.load(PANEL_PATH, allow_pickle=True)
NAMES = [str(x) for x in Z["names"]]
DAYS = pd.DatetimeIndex(Z["days"], tz="UTC")
H, L, C, FD = [np.ascontiguousarray(Z[k], dtype=np.float64) for k in ("H", "L", "C", "FD")]
ND, _, N = C.shape
CL = np.ascontiguousarray(C[:, 23, :])
MMR = np.array([0.004 if b in ("BTC", "ETH") else 0.01 for b in NAMES])      # tier-1 maintenance rates (review)
REF = np.ascontiguousarray(np.concatenate([np.concatenate([CL[:1] * np.nan, CL[:-1]], 0)[:, None, :], C[:, :-1, :]], 1))

def day_idx(s):
    return int(DAYS.searchsorted(pd.Timestamp(s, tz="UTC")))

def crash_flags():
    b = CL[:, NAMES.index("BTC")]
    r = np.full(ND, np.nan); r[14:] = b[14:] / b[:-14] - 1
    return np.isfinite(r) & (r < -0.10)
CRASH = crash_flags()

def scores(cols):
    s = np.full((ND, N), np.nan)
    m = np.full((ND, len(cols)), np.nan)
    sub = CL[:, cols]
    m[14:] = sub[14:] / sub[:-14] - 1
    s[:, cols] = m
    return s

@njit(cache=False)
def _resize(q, e, j, newq, px, W, cost):
    old = q[j]
    if newq == old:
        return W, 0.0
    tr = abs(newq - old) * px
    if abs(newq) < abs(old) and newq * old >= 0:
        W += (old - newq) * (px - e[j])
        q[j] = newq
        if newq == 0.0:
            e[j] = 0.0
    else:
        e[j] = (old * e[j] + (newq - old) * px) / newq
        q[j] = newq
    return W - tr * cost, tr

@njit(cache=False)
def _caps(q, e, W, pxh, gcap, ncap, scap_eq, cost, cnt):
    """apply net -> symbol -> gross caps at prices pxh. cnt[0..2] event counts, cnt[3] traded notional/eq accumulator (x1e0)."""
    n = q.shape[0]
    pnl = 0.0
    for j in range(n):
        if q[j] != 0.0:
            pnl += q[j] * (pxh[j] - e[j])
    eq = W + pnl
    if eq <= 1e-12:
        return W
    if ncap > 0.0:
        Lg = 0.0; S = 0.0
        for j in range(n):
            v = q[j] * pxh[j]
            if v > 0: Lg += v
            elif v < 0: S -= v
        net = (Lg - S) / eq
        if abs(net) > ncap and Lg > 0.0 and S > 0.0:
            t = (ncap - 0.1) * eq
            if net < 0: t = -t
            Gt = Lg + S
            Lp = (Gt + t) / 2.0; Sp = (Gt - t) / 2.0
            if Lp > 0.0 and Sp > 0.0:
                a = Lp / Lg; b = Sp / S
                for j in range(n):
                    if q[j] > 0: W, tr = _resize(q, e, j, q[j] * a, pxh[j], W, cost); cnt[3] += tr / eq
                    elif q[j] < 0: W, tr = _resize(q, e, j, q[j] * b, pxh[j], W, cost); cnt[3] += tr / eq
                cnt[1] += 1
    if scap_eq > 0.0:
        pnl = 0.0
        for j in range(n):
            if q[j] != 0.0: pnl += q[j] * (pxh[j] - e[j])
        eq = W + pnl
        hit = False
        for j in range(n):
            if q[j] != 0.0 and abs(q[j]) * pxh[j] > scap_eq * eq:
                nq = np.sign(q[j]) * scap_eq * eq / pxh[j]
                W, tr = _resize(q, e, j, nq, pxh[j], W, cost); cnt[3] += tr / eq
                hit = True
        if hit: cnt[2] += 1
    if gcap > 0.0:
        pnl = 0.0; G = 0.0
        for j in range(n):
            if q[j] != 0.0:
                pnl += q[j] * (pxh[j] - e[j]); G += abs(q[j]) * pxh[j]
        eq = W + pnl
        if eq > 1e-12 and G / eq > gcap:
            f = 0.95 * gcap / (G / eq)
            for j in range(n):
                if q[j] != 0.0:
                    W, tr = _resize(q, e, j, q[j] * f, pxh[j], W, cost); cnt[3] += tr / eq
            cnt[0] += 1
    return W

@njit(cache=False)
def _sim(Hh, Ll, Cc, FDd, CLl, REFf, sc, CRASHf, MMRr, d0, d1, lev, dep, phase, kill, cool0, cost, K, rebal,
         kmode, lam, norm, gcap, ncap, scap, cool_j, delay_j):
    ND_, _, N_ = Cc.shape
    q = np.zeros(N_); e = np.zeros(N_); W = 1.0; hwm = 1.0
    halted = False; halt_day = -1; last_reb = -10**9; prev_flag = False
    kills = 0; dead = False
    eqs = np.full(ND_, np.nan); gcl = np.full(ND_, np.nan); ncl = np.full(ND_, np.nan); scl = np.full(ND_, np.nan)
    snapA = np.zeros((ND_, N_)); eqA = np.full(ND_, np.nan)
    snapB = np.zeros((ND_, N_)); eqB = np.full(ND_, np.nan)
    cmin = 9e9; cmin_day = -1; cmin_sync = 9e9; liq_hours = 0
    cnt = np.zeros(4)
    px = np.zeros(N_); pxh = np.zeros(N_)
    scap_eq = scap * lev * dep if scap > 0 else 0.0
    for i in range(d0, d1):
        held = False
        for j in range(N_):
            if q[j] != 0.0: held = True
        killed = False
        if held:
            for j in range(N_):
                if q[j] != 0.0:
                    f_ = FDd[i, j]
                    if np.isfinite(f_): W += -q[j] * f_
            prev = 1.0
            if i > 0 and np.isfinite(eqs[i - 1]): prev = eqs[i - 1]
            for j in range(N_):
                pxh[j] = e[j]
            for h in range(24):
                # ---- liquidation cushion for hour h (book held during the hour), antisync L/H f=1 & synchronous, tier MM, adjusted notional
                pa = 0.0; ma = 0.0; pl_ = 0.0; ml_ = 0.0; ph_ = 0.0; mh_ = 0.0; any_ = False
                for j in range(N_):
                    if q[j] != 0.0:
                        any_ = True
                        ref = REFf[i, h, j]
                        if not np.isfinite(ref): ref = e[j]
                        lo = Ll[i, h, j]
                        if not np.isfinite(lo): lo = ref
                        hi = Hh[i, h, j]
                        if not np.isfinite(hi): hi = ref
                        a = lo if q[j] > 0 else hi
                        pa += q[j] * (a - e[j]); ma += abs(q[j]) * a * MMRr[j]
                        pl_ += q[j] * (lo - e[j]); ml_ += abs(q[j]) * lo * MMRr[j]
                        ph_ += q[j] * (hi - e[j]); mh_ += abs(q[j]) * hi * MMRr[j]
                if any_:
                    c1 = (W + pa - ma) / prev
                    c2 = (W + pl_ - ml_) / prev; c3 = (W + ph_ - mh_) / prev
                    cs = min(c2, c3)
                    if c1 < cmin: cmin = c1; cmin_day = i
                    if cs < cmin_sync: cmin_sync = cs
                    if c1 <= 0: liq_hours += 1
                if h == 21:
                    for j in range(N_): snapA[i, j] = q[j] * pxh[j]
                    p_ = 0.0
                    for j in range(N_):
                        if q[j] != 0.0: p_ += q[j] * (pxh[j] - e[j])
                    eqA[i] = W + p_
                # ---- hour-h close prices (nan -> entry)
                for j in range(N_):
                    c_ = Cc[i, h, j]
                    pxh[j] = c_ if np.isfinite(c_) else e[j]
                if kmode == 1:
                    pc = 0.0; pw = 0.0
                    for j in range(N_):
                        if q[j] != 0.0:
                            pc += q[j] * (pxh[j] - e[j])
                            lo = Ll[i, h, j]
                            if not np.isfinite(lo): lo = pxh[j]
                            hi = Hh[i, h, j]
                            if not np.isfinite(hi): hi = pxh[j]
                            a = lo if q[j] > 0 else hi
                            pw += q[j] * (a - e[j])
                    plk = pc - lam * (pc - pw)
                    if 1.0 - (W + plk) / hwm >= kill:
                        cst = 0.0
                        for j in range(N_):
                            if q[j] != 0.0: cst += abs(q[j]) * pxh[j] * cost
                        W += plk - cst
                        for j in range(N_):
                            q[j] = 0.0; e[j] = 0.0
                        halted = True; halt_day = i; kills += 1; killed = True
                        eqs[i] = W
                        break
                    if W + pc > hwm: hwm = W + pc
                if h < 23 and (gcap > 0.0 or ncap > 0.0 or scap_eq > 0.0):
                    W = _caps(q, e, W, pxh, gcap, ncap, scap_eq, cost, cnt)
            if killed:
                continue
        # ---- day close (V0)
        anyq = False
        for j in range(N_):
            c_ = CLl[i, j]
            if np.isfinite(c_): px[j] = c_
            elif e[j] > 0: px[j] = e[j]
            else: px[j] = np.nan
            if q[j] != 0.0: anyq = True
        pnl = 0.0
        for j in range(N_):
            if q[j] != 0.0: pnl += q[j] * (px[j] - e[j])
        eq = W + pnl
        eqs[i] = eq
        if anyq:
            for j in range(N_):
                if q[j] != 0.0: snapB[i, j] = q[j] * px[j]
            eqB[i] = eq
        if eq <= 1e-9:
            dead = True
            break
        if eq > hwm: hwm = eq
        dd = 1.0 - eq / hwm
        if (not halted) and dd >= kill:
            cst = 0.0
            for j in range(N_):
                if q[j] != 0.0: cst += abs(q[j]) * px[j] * cost
            W += pnl - cst
            for j in range(N_):
                q[j] = 0.0; e[j] = 0.0
            halted = True; halt_day = i; kills += 1
            continue
        if halted:
            kj = kills - 1
            if kj < 0: kj = 0
            if cool0 > 0 and i - halt_day >= cool0 + cool_j[kj]:
                halted = False; hwm = eq
                dl = delay_j[kj]
                last_reb = -10**9 if dl == 0 else i + dl - rebal
            else:
                continue
        flag = CRASHf[i]; force = flag != prev_flag; prev_flag = flag
        due = (i >= d0 + phase) and (i - last_reb >= rebal)
        do_reb = (due or force) and (i < d1 - 1)
        side = np.zeros(N_)
        if do_reb:
            cntf = 0
            for j in range(N_):
                if np.isfinite(sc[i, j]): cntf += 1
            if (not flag) and cntf < 2 * K:
                do_reb = False
            elif not flag:
                idx = np.empty(cntf, np.int64); m = 0
                for j in range(N_):
                    if np.isfinite(sc[i, j]):
                        idx[m] = j; m += 1
                ordr = idx[np.argsort(-sc[i, idx], kind="mergesort")]
                for t in range(K): side[ordr[t]] = 1.0
                for t in range(K): side[ordr[cntf - 1 - t]] = -1.0
        if do_reb:
            tgt = eq * dep * lev / (2.0 * K); c_ = 0.0
            for j in range(N_):
                s_ = side[j]; cs_ = 0.0
                if q[j] > 0: cs_ = 1.0
                elif q[j] < 0: cs_ = -1.0
                if q[j] != 0.0 and s_ == cs_:
                    if norm == 1 and np.isfinite(px[j]) and px[j] > 0:
                        W, tr = _resize(q, e, j, s_ * tgt / px[j], px[j], W, cost)
                        cnt[3] += tr / eq
                    continue
                if q[j] != 0.0:
                    W += q[j] * (px[j] - e[j]); c_ += abs(q[j]) * px[j] * cost; q[j] = 0.0; e[j] = 0.0
                if s_ != 0.0 and np.isfinite(px[j]) and px[j] > 0:
                    qty = tgt / px[j]
                    q[j] = s_ * qty; e[j] = px[j]; c_ += qty * px[j] * cost
            W -= c_
            if due: last_reb = i
        # ---- end-of-day caps (after rebalance) and day-close book stats
        if gcap > 0.0 or ncap > 0.0 or scap_eq > 0.0:
            W = _caps(q, e, W, px, gcap, ncap, scap_eq, cost, cnt)
        anyq = False; pnl = 0.0; G = 0.0; Nt = 0.0; mx = 0.0
        for j in range(N_):
            if q[j] != 0.0:
                anyq = True
                pnl += q[j] * (px[j] - e[j]); v = abs(q[j]) * px[j]; G += v; Nt += q[j] * px[j]
                if v > mx: mx = v
        if anyq:
            eq2 = W + pnl
            if eq2 > 1e-12:
                gcl[i] = G / eq2; ncl[i] = Nt / eq2; scl[i] = mx / eq2
    ev = np.nan
    for i in range(d1 - 1, d0 - 1, -1):
        if np.isfinite(eqs[i]):
            ev = eqs[i]; break
    return eqs, gcl, ncl, scl, snapA, eqA, snapB, eqB, cmin, cmin_day, cmin_sync, liq_hours, kills, ev, cnt, dead

# kill models: name -> (kmode, lam)
KILLMODELS = {"daily": (0, 0.0), "hourly": (1, 0.0), "lam05": (1, 0.05), "lam15": (1, 0.15), "lam30": (1, 0.30)}

# cells: name -> dict(norm, gcap, ncap, scap)   (scap = fraction of TARGET gross (lev*dep) per symbol, in equity units)
def run(cols=None, lev=4.0, dep=0.95, phase=0, kill=0.35, cool=14, cost=0.001, d0=None, d1=None, K=8, rebal=3,
        km="daily", norm=0, gcap=0.0, ncap=0.0, scap=0.0, cool_j=None, delay_j=None):
    cols = list(range(N)) if cols is None else list(cols)
    sc = scores(cols)
    d0 = day_idx("2022-01-01") if d0 is None else d0
    d1 = ND if d1 is None else d1
    kmode, lam = KILLMODELS[km]
    cj = np.zeros(64, np.int64) if cool_j is None else np.asarray(cool_j, np.int64)
    dj = np.zeros(64, np.int64) if delay_j is None else np.asarray(delay_j, np.int64)
    out = _sim(H, L, C, FD, CL, REF, sc, CRASH, MMR, d0, d1, lev, dep, phase, kill, cool, cost, K, rebal,
               kmode, lam, norm, gcap, ncap, scap, cj, dj)
    keys = ("eqs", "gcl", "ncl", "scl", "snapA", "eqA", "snapB", "eqB", "cmin", "cmin_day", "cmin_sync", "liq_hours", "kills", "final", "cnt", "dead")
    r = dict(zip(keys, out)); r["d0"] = d0; r["d1"] = d1
    return r
