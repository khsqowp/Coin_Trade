"""Offline map: common evaluation core. Long-short cases run on app.rs_final_engine._sim (unmodified); long-only/weight cases run on
sim_w below, which mimics the engine's constant-weight model (cw=1): daily UTC close execution, 0.10%/side on turnover, real funding.
sim_w is reconciled against the engine (see recon())."""
from __future__ import annotations
import numpy as np, pandas as pd
from numba import njit
from app.rs_final_engine import _sim, params, zscore_signal, btc_flags

SEL_A, SEL_B = "2022-01-01", "2026-06-11"
HOLD_A = "2026-06-12"
FOLDS = [("2022-01-01", "2023-04-30"), ("2023-05-01", "2024-08-31"), ("2024-09-01", "2026-06-11")]
CADENCES = (1, 2, 3, 7)
KS = (4, 6, 8, 10, 12)


class Ctx:
    """holds panel arrays + index helpers"""
    def __init__(self, D):
        self.D = D; P = D["P"]
        self.names = D["names"]; self.days = D["days"]; self.nd = len(self.days); self.n = len(self.names)
        self.H = np.ascontiguousarray(P["H"]); self.L = np.ascontiguousarray(P["L"]); self.C = np.ascontiguousarray(P["C"])
        self.FD = np.ascontiguousarray(P["FD"]); self.dc = np.ascontiguousarray(self.C[:, -1, :])
        self.btc = self.names.index("BTC")
        self.bull, self.crash = btc_flags(P)
        self.step_j = np.zeros(self.n)
        for b in ("BTC", "ETH"):
            self.step_j[self.names.index(b)] = 0.001
        self.minj0 = np.zeros(self.n)
        self.d0 = int(self.days.searchsorted(pd.Timestamp(SEL_A, tz="UTC")))
        self.d_hold = int(self.days.searchsorted(pd.Timestamp(HOLD_A, tz="UTC")))
        self.rng = np.random.RandomState(11)
        self.tie = self.rng.normal(size=self.n) * 1e-9
        self.first_valid = np.array([int(np.argmax(np.isfinite(self.dc[:, j]))) for j in range(self.n)])
        self.pre2022 = self.first_valid < self.d0   # symbols listed before the selection window
        # inverse-vol weights: 1/20d stdev of daily returns (lagged by construction: uses data to day i)
        r = np.full_like(self.dc, np.nan); r[1:] = self.dc[1:] / self.dc[:-1] - 1
        self.vol20 = pd.DataFrame(r).rolling(20, min_periods=15).std().to_numpy()
        self.sma200_btc = pd.Series(self.dc[:, self.btc]).rolling(200, min_periods=200).mean().to_numpy()
        self.sma50_btc = pd.Series(self.dc[:, self.btc]).rolling(50, min_periods=50).mean().to_numpy()
        self.btc_up = np.isfinite(self.sma200_btc) & (self.dc[:, self.btc] > self.sma200_btc)

    def widx(self, a, b=None):
        i0 = int(self.days.searchsorted(pd.Timestamp(a, tz="UTC")))
        i1 = self.nd if b is None else int(self.days.searchsorted(pd.Timestamp(b, tz="UTC"), side="right"))
        return i0, i1


# ---------------------------------------------------------------- engine wrapper (long-short)
def run_engine(cx: Ctx, score, K, rebal, phase=0, cost=0.001, fund=1, vt=0.0, cap=1.5, cw=1, flat=None, d1=None):
    """returns daily equity array (nd,) (nan before d0)"""
    pr = params(rebal=rebal, K=K, lev=(cap if vt > 0 else 1.0), cost=cost, vt=vt, cap=cap, cw=cw, phase=phase, fund=fund)
    fl = np.zeros(cx.nd) if flat is None else flat.astype(np.float64)
    d1 = cx.nd if d1 is None else d1
    eq, _, _, st = _sim(cx.H, cx.L, cx.C, cx.FD, np.ascontiguousarray(score), fl, pr, cx.minj0, cx.step_j, cx.d0, d1)
    return eq, st


# ---------------------------------------------------------------- weight simulator (long-only or any weights)
@njit(cache=True)
def _simw(C, FD, Wt, flat, rebal, phase, cost, fund_on, vt, cap, vlb, d0, d1):
    nd, n = C.shape
    E = 1.0
    q = np.zeros(n)
    px = np.full(n, np.nan)
    eq = np.full(nd, np.nan); sret = np.zeros(nd); expo = np.zeros(nd)
    last_reb = -10 ** 9
    prev = 1.0
    for i in range(d0, d1):
        # mark to market day i
        for j in range(n):
            c = C[i, j]
            if q[j] != 0.0:
                if np.isfinite(c) and np.isfinite(px[j]):
                    E += q[j] * (c - px[j])
                if fund_on:
                    E -= q[j] * FD[i, j]
            if np.isfinite(c):
                px[j] = c
        eq[i] = E
        sret[i] = E / prev - 1.0
        prev = E
        g = 0.0
        for j in range(n):
            if q[j] != 0.0 and np.isfinite(px[j]):
                g += abs(q[j] * px[j])
        expo[i] = g / max(E, 1e-12)
        if E <= 0:
            break
        due = (i >= d0 + phase) and ((i - last_reb) >= rebal)
        want_flat = flat[i] > 0
        if not due or i >= d1 - 1:
            continue
        lev = 1.0
        if vt > 0:
            if i - d0 >= max(10, vlb // 2):
                lo = max(d0, i - vlb + 1)
                m_ = 0.0; gg = 0.0; c_n = 0
                for t in range(lo, i + 1):
                    m_ += sret[t]; gg += expo[t]; c_n += 1
                m_ /= c_n; gg /= c_n
                m2 = 0.0
                for t in range(lo, i + 1):
                    m2 += (sret[t] - m_) ** 2
                sd = np.sqrt(m2 / c_n)
                vol = sd * np.sqrt(365.0) / max(gg, 0.25)
                if vol > 0:
                    lev = min(cap, vt / vol)
                else:
                    lev = cap
        cst = 0.0
        for j in range(n):
            tw = 0.0 if want_flat else Wt[i, j]
            if not np.isfinite(tw):
                tw = 0.0
            c = px[j]
            if not np.isfinite(c) or c <= 0:
                continue
            nq = tw * lev * E / c
            cst += abs(nq - q[j]) * c * cost
            q[j] = nq
        E -= cst
        last_reb = i
    return eq


def run_w(cx: Ctx, Wt, rebal, phase=0, cost=0.001, fund=1, vt=0.0, cap=1.5, flat=None, d1=None):
    fl = np.zeros(cx.nd) if flat is None else flat.astype(np.float64)
    d1 = cx.nd if d1 is None else d1
    return _simw(cx.dc, cx.FD, np.ascontiguousarray(Wt), fl, int(rebal), int(phase), cost, fund > 0, vt, cap, 60, cx.d0, d1)


# ---------------------------------------------------------------- metrics
def rets(eq):
    e = np.asarray(eq, float)
    r = np.full(len(e), np.nan)
    ok = np.isfinite(e)
    idx = np.where(ok)[0]
    if len(idx) > 1:
        r[idx[1:]] = e[idx[1:]] / e[idx[:-1]] - 1.0
    return r


def mets(r, i0, i1):
    """r daily returns array; window [i0,i1)"""
    x = r[i0:i1]; x = x[np.isfinite(x)]
    if len(x) < 30:
        return None
    c = np.cumprod(1 + x)
    yrs = len(x) / 365.0
    end = c[-1]
    cagr = end ** (1 / yrs) - 1 if end > 0 else -1.0
    hw = np.maximum.accumulate(np.concatenate([[1.0], c]))[1:]
    mdd = float(np.max(1 - c / hw))
    sd = x.std()
    return dict(cagr=float(cagr), mdd=mdd, calmar=float(cagr / mdd) if mdd > 1e-9 else 0.0,
                sharpe=float(x.mean() / sd * np.sqrt(365)) if sd > 0 else 0.0, n=len(x), worst=float(x.min()))


def phase_avg(fn, rebal):
    """fn(phase)->eq array; returns (mean daily-return series across phases, list of eq)"""
    rs = [rets(fn(p)) for p in range(rebal)]
    return np.nanmean(np.vstack(rs), axis=0) if len(rs) > 1 else rs[0]


def phase_mets(rs, i0, i1):
    ms = [mets(r, i0, i1) for r in rs]
    if any(m is None for m in ms):
        return None
    return {k: float(np.mean([m[k] for m in ms])) for k in ("cagr", "mdd", "calmar", "sharpe", "worst")}


# ---------------------------------------------------------------- constructions
def ls_score(cx: Ctx, strength):
    return strength + cx.tie[None, :]


def rank_z(x):
    """cross-sectional rank z-score per row (NaN-safe), same convention as rs_final_engine.zscore_signal"""
    ok = np.isfinite(x)
    r = pd.DataFrame(x).rank(axis=1).to_numpy()
    cnt = ok.sum(1, keepdims=True)
    z = (r - (cnt + 1) / 2) / np.sqrt(np.maximum((cnt * cnt - 1) / 12, 1))
    z[~ok] = np.nan
    return z


def w_longonly_ew(cx: Ctx, pos, ivol=False):
    """per-symbol signals aggregated long-only equal weight: each ON symbol gets 1/N_eligible (cash otherwise)."""
    el = np.isfinite(pos) & np.isfinite(cx.dc)
    on = el & (pos > 0)
    nel = el.sum(1, keepdims=True).astype(float)
    if ivol:
        iv = np.where(el & np.isfinite(cx.vol20) & (cx.vol20 > 0), 1.0 / cx.vol20, np.nan)
        mean_iv = np.nanmean(iv, axis=1, keepdims=True)
        w = np.where(on, np.nan_to_num(iv / mean_iv, nan=1.0), 0.0) / np.maximum(nel, 1)
        g = w.sum(1, keepdims=True)
        # keep gross <= 1
        w = w / np.maximum(g, 1.0)
        return w
    return np.where(on, 1.0 / np.maximum(nel, 1), 0.0)


def w_topn_gate(cx: Ctx, pos, strength, N, ivol=False, gate=True):
    """top-N (by strength) among ON symbols, weight 1/N each (cash if fewer ON), BTC>SMA200 gate."""
    el = np.isfinite(pos) & np.isfinite(cx.dc) & np.isfinite(strength)
    on = el & (pos > 0)
    s = np.where(on, strength + cx.tie[None, :], -np.inf)
    nd, n = s.shape
    order = np.argsort(-s, axis=1)
    rank = np.empty_like(order)
    np.put_along_axis(rank, order, np.arange(n)[None, :].repeat(nd, 0), 1)
    sel = on & (rank < N)
    if ivol:
        iv = np.where(sel & np.isfinite(cx.vol20) & (cx.vol20 > 0), 1.0 / cx.vol20, 0.0)
        tot = iv.sum(1, keepdims=True)
        nsel = sel.sum(1, keepdims=True)
        w = np.where(tot > 0, iv / np.maximum(tot, 1e-12) * nsel / N, 0.0)
    else:
        w = np.where(sel, 1.0 / N, 0.0)
    if gate:
        w = w * cx.btc_up[:, None]
    return w


def overlay_score(cx: Ctx, pos, strength, mode, base_lbs=(14,)):
    """overlay on the live rotation score (14d z). modes: tilt0.5, tilt1.0, agree. returns score matrix"""
    base = zscore_signal(cx.C, tuple(base_lbs))
    if mode.startswith("tilt"):
        lam = float(mode[4:])
        z = rank_z(strength)
        sc = base + lam * np.nan_to_num(z, nan=0.0)
        sc[~np.isfinite(base)] = np.nan
        return sc
    if mode == "agree":
        p = np.nan_to_num(pos, nan=0.0)
        sc = base + 10.0 * np.sign(p)
        sc[~np.isfinite(base)] = np.nan
        return sc
    raise ValueError(mode)


def overlay_flat(cx: Ctx, pos, mode):
    """flat flag for overlay modes 'gate' (BTC family state must be >0) combined with live crash filter"""
    f = cx.crash.copy()
    if mode == "gate":
        p = np.nan_to_num(pos[:, cx.btc], nan=0.0)
        f = f | (p <= 0)
    return f


# ---------------------------------------------------------------- live controls
def rotation_score(cx: Ctx, lbs=(14,)):
    return zscore_signal(cx.C, tuple(lbs))


def control_runs(cx: Ctx, d1=None, cost=0.001, fund=1, per_phase=False):
    """live-rotation controls: dict name -> mean daily returns across phases (or the list of per-phase returns)"""
    out = {}
    for lb, rb, K in ((14, 3, 8), (14, 2, 12)):
        sc = rotation_score(cx, (lb,))
        for crash in (False, True):
            fl = cx.crash if crash else None
            for cw, tag in ((0, "A"), (1, "B")):
                rl = [rets(run_engine(cx, sc, K, rb, p, cost, fund, 0.0, 1.5, cw, fl, d1)[0]) for p in range(rb)]
                r = rl if per_phase else (np.nanmean(np.vstack(rl), axis=0) if len(rl) > 1 else rl[0])
                out[f"rot{lb}/{rb}d/K{K}{'+crash' if crash else ''}|{tag}"] = r
    return out
