"""R2-C analysis library: samples, cell grid, window / full-sample runners, block bootstrap, verdict logic. Offline research only."""
from __future__ import annotations
import os
import numpy as np
import pandas as pd
from scipy import stats
from app import rs_lev_r2c_engine as E
from app import rs_lev_r2c_data as D

LEVS = (3.0, 3.5, 4.0, 5.0)           # 3.0 = reference only
KILLS = (0.35, 0.5, 0.6, None)        # None = no kill
LAMS = (0.0, 0.15, 0.3)
BASE = (4.0, 0.35)
DEP = 0.95
WIN = 90                               # non-overlapping window length (days)
Z_MDE = 2.8                            # 80% power, 5% two-sided
DELTA_LEV, DELTA_KILL = 0.05, 0.12     # target effects (per year of ln W)


def combos():
    """list of (lev, kill, lam); kill None has no lambda dependence (stored with lam=None)."""
    out = []
    for lev in LEVS:
        for k in KILLS:
            if k is None:
                out.append((lev, None, None))
            else:
                for lam in LAMS:
                    out.append((lev, k, lam))
    return out


class Sample:
    def __init__(self, name, P, start, end):
        self.name = name; self.P = P
        self.n = len(P["names"]); self.nd = len(P["days"])
        self.sc = D.scores(P); self.cr = D.crash(P); self.r1 = D.r1_vec(P["names"])
        self.a = D.day_index(P, start); self.b = D.day_index(P, end) if end else self.nd
        self.ones = np.ones(self.n, np.uint8)

    def windows(self, first_active=None):
        a = self.a if first_active is None else first_active
        ws = []
        s = a
        while s + WIN <= self.b:
            ws.append((s, s + WIN)); s += WIN
        return ws


def _pars(S, cs, d0s, d1s, phases):
    """cs: list of combos; d0s/d1s/phases: arrays per rep -> PAR rows ordered combo-major."""
    R = len(d0s); rows = []
    for (lev, k, lam) in cs:
        for r in range(R):
            rows.append(E.make_par(lev=lev, dep=DEP, kill=(9.0 if k is None else k), lam=(0.0 if lam is None else lam), hourly=1,
                                   phase=int(phases[r]), d0=int(d0s[r]), d1=int(d1s[r])))
    return np.array(rows)


def run_grid(S, cs, d0s, d1s, phases, jcd, jph, colmask=None, ev=None, want_eq=False):
    """Run all combos x reps. jcd/jph shape (R,MAXK). colmask (n,) or (R,n) uint8; ev=(evd(R,n),evml(R,n),evms(R,n)) or None.
    Returns OUT (ncomb,R,O_N), KD (ncomb,R,MAXK), EQ or None, PS (ncomb,R,n)."""
    R = len(d0s); nc = len(cs)
    PAR = _pars(S, cs, d0s, d1s, phases)
    JC = np.tile(jcd, (nc, 1)); JP = np.tile(jph, (nc, 1))
    if colmask is None:
        CM = np.tile(S.ones, (nc * R, 1))
    else:
        cmk = np.asarray(colmask, np.uint8)
        CM = np.tile(cmk, (nc, 1)) if cmk.ndim == 2 else np.tile(cmk, (nc * R, 1))
    if ev is None:
        EVD = -np.ones((nc * R, S.n), np.int64); EVML = np.ones((nc * R, S.n)); EVMS = np.ones((nc * R, S.n))
    else:
        EVD = np.tile(ev[0], (nc, 1)); EVML = np.tile(ev[1], (nc, 1)); EVMS = np.tile(ev[2], (nc, 1))
    P = S.P
    O, KD, EQ, PS = E.run_batch(P["H"], P["L"], P["C"], P["FD"], S.sc, S.cr, S.r1, CM, PAR, JC, JP, EVD, EVML, EVMS, want_eq)
    return (O.reshape(nc, R, -1), KD.reshape(nc, R, -1), (EQ.reshape(nc, R, -1) if want_eq else None), PS.reshape(nc, R, -1))


def ann_lg(final, ndays):
    return np.log(np.maximum(final, 1e-6)) * 365.0 / ndays


def first_active_day(S, K=8):
    """first day >= S.a on which at least 2K symbols have a finite score (strategy can trade)."""
    cnt = np.isfinite(S.sc).sum(1)
    for i in range(S.a, S.b):
        if cnt[i] >= 2 * K:
            return i
    return S.b


def window_matrix(S, R, seed, cs=None, colmask=None, ev=None, win_from=None):
    """Per non-overlapping WIN-day window (restart from W=1): mean over R jittered reps of annualised ln W, per combo.
    Returns G (nw, ncombo), U (nw, ncombo) unique-final counts, wins list, KEP (kill epochs)."""
    cs = combos() if cs is None else cs
    wins = S.windows(first_active_day(S) if win_from is None else win_from)
    rng = np.random.default_rng(seed)
    G = np.zeros((len(wins), len(cs))); U = np.zeros((len(wins), len(cs)), int); KILLS_ = np.zeros((len(wins), len(cs)))
    for w, (s0, s1) in enumerate(wins):
        jcd, jph = E.jitter(R, int(rng.integers(1 << 30)))
        phases = rng.integers(0, 3, size=R)
        O, KD, _, _ = run_grid(S, cs, np.full(R, s0), np.full(R, s1), phases, jcd, jph, colmask, ev)
        G[w] = ann_lg(O[:, :, E.O_FINAL], s1 - s0).mean(axis=1)
        for c in range(len(cs)):
            U[w, c] = len(np.unique(np.round(O[c, :, E.O_FINAL], 9)))
        KILLS_[w] = O[:, :, E.O_KILLS].mean(axis=1)
    return G, U, wins, KILLS_


def full_runs(S, R, seed, cs=None, colmask=None, ev=None, start=None, want_eq=False):
    """Continuous run over [start+offset, end) with per-rep start offset 0..29 days, phase 0..2, kill jitter."""
    cs = combos() if cs is None else cs
    rng = np.random.default_rng(seed)
    st = first_active_day(S) if start is None else start
    off = rng.integers(0, 30, size=R); phases = rng.integers(0, 3, size=R)
    jcd, jph = E.jitter(R, int(rng.integers(1 << 30)))
    d0s = st + off; d1s = np.full(R, S.b)
    O, KD, EQ, PS = run_grid(S, cs, d0s, d1s, phases, jcd, jph, colmask, ev, want_eq)
    g = ann_lg(O[:, :, E.O_FINAL], (d1s - d0s)[None, :])
    return dict(cs=cs, O=O, KD=KD, EQ=EQ, PS=PS, g=g, d0s=d0s, d1s=d1s)


def unique_traj(O):
    """number of distinct final equities per combo (ncomb,R) -> (ncomb,)"""
    return np.array([len(np.unique(np.round(O[c, :, E.O_FINAL], 9))) for c in range(O.shape[0])])


def kill_epochs(KD, gap=7):
    """number of distinct kill 'epochs' per combo across reps: kill days sorted & merged when within `gap` days."""
    out = []
    for c in range(KD.shape[0]):
        d = np.sort(KD[c][KD[c] >= 0].ravel())
        if len(d) == 0:
            out.append(0); continue
        out.append(1 + int((np.diff(d) > gap).sum()))
    return np.array(out)


def boot_stats(d, B=10000, seed=7):
    """paired window-level bootstrap of the mean: returns dict(mean, se, lo, hi, p_le0, n)."""
    d = np.asarray(d, float); n = len(d)
    if n == 0:
        return dict(mean=np.nan, se=np.nan, lo=np.nan, hi=np.nan, p_le0=np.nan, n=0)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(B, n))
    bm = d[idx].mean(axis=1)
    return dict(mean=float(d.mean()), se=float(bm.std()), lo=float(np.percentile(bm, 2.5)), hi=float(np.percentile(bm, 97.5)),
                p_le0=float((bm <= 0).mean()), n=n)


def block_boot_unit(r, G_list, block=15, B=4000, seed=1):
    """15-day block bootstrap of fixed-fraction ln growth differences: returns {(a,b): se} for leverage pairs (effective G)."""
    rng = np.random.default_rng(seed); T = len(r); nb = int(np.ceil(T / block))
    st = rng.integers(0, T - block + 1, size=(B, nb))
    idx = (st[:, :, None] + np.arange(block)[None, None, :]).reshape(B, -1)[:, :T]
    out = {}
    for (a, b) in G_list:
        d = np.log1p(b * r) - np.log1p(a * r)
        out[(a, b)] = float(365 * d[idx].mean(axis=1).std())
    return out


def delta_for(cell, base=BASE):
    return DELTA_KILL if cell[1] != base[1] else DELTA_LEV


def t_stats(d):
    """two-sided 95% t interval of the mean of window diffs + small-sample MDE (80% power, 5% two-sided)."""
    d = np.asarray(d, float); n = len(d)
    if n < 2:
        return dict(mean=np.nan, lo=np.nan, hi=np.nan, mde=np.nan, se=np.nan, n=n)
    sd = d.std(ddof=1); se = sd / np.sqrt(n); t975 = stats.t.ppf(0.975, n - 1); t80 = stats.t.ppf(0.80, n - 1)
    return dict(mean=float(d.mean()), lo=float(d.mean() - t975 * se), hi=float(d.mean() + t975 * se), mde=float((t975 + t80) * se), se=float(se), n=n)


def pos_fraction(d, tol=1e-12):
    """(fraction of non-tied windows with d>0, number of non-tied windows)"""
    d = np.asarray(d, float); nt = np.abs(d) > tol
    return (float((d[nt] > 0).mean()) if nt.any() else np.nan), int(nt.sum())


def holm(pvals):
    """Holm step-down adjusted p-values (input list) -> list"""
    m = len(pvals); order = np.argsort(pvals); adj = np.zeros(m); run = 0.0
    for r, k in enumerate(order):
        run = max(run, (m - r) * pvals[k]); adj[k] = min(1.0, run)
    return list(adj)
