"""Reviewer audit: re-run R2C headline cells with LIVE-LIKE sizing (retained positions resized to target when |cur-tgt|/tgt > 15%, as in momentum_rotation_exec.apply_targets)
versus V0 kept-qty (normtol=-1, parity with R2C engine). Same seeds/jitter/windows as R2C. Output only in review2/."""
import os, sys, time
sys.dont_write_bytecode = True
ROOT = "/Users/user/Desktop/CODE/Ochestration/trading"
sys.path.insert(0, ROOT); sys.path.insert(0, ROOT + "/docs/research/lev_loop/R2C"); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
import aud_engine as AE
from app import rs_lev_r2c_lib as LIB, rs_lev_r2c_engine as E
import r2c_samples as RS
CELLS = [(3.5, 0.35, 0.15), (4.0, 0.35, 0.0), (4.0, 0.35, 0.15), (4.0, 0.35, 0.30), (4.0, 0.5, 0.15), (4.0, 0.6, 0.15), (4.0, None, None), (5.0, 0.35, 0.15), (5.0, 0.5, 0.15), (5.0, None, None)]
def pars(cs, d0s, d1s, phases, normtol):
    rows = []
    for (lev, k, lam) in cs:
        for r in range(len(d0s)):
            rows.append(AE.make_par(lev=lev, dep=0.95, kill=(9.0 if k is None else k), lam=(0.0 if lam is None else lam), hourly=1,
                                    phase=int(phases[r]), d0=int(d0s[r]), d1=int(d1s[r]), normtol=normtol))
    return np.array(rows)
def run(S, cs, d0s, d1s, phases, jcd, jph, normtol):
    nc = len(cs); R = len(d0s)
    PAR = pars(cs, d0s, d1s, phases, normtol)
    JC = np.tile(jcd, (nc, 1)); JP = np.tile(jph, (nc, 1)); CM = np.tile(S.ones, (nc * R, 1))
    EVD = -np.ones((nc * R, S.n), np.int64); EVML = np.ones((nc * R, S.n)); EVMS = np.ones((nc * R, S.n))
    P = S.P
    O, KD, EQ, PS, HELD, GRO = AE.run_batch(P["H"], P["L"], P["C"], P["FD"], S.sc, S.cr, S.r1, CM, PAR, JC, JP, EVD, EVML, EVMS, False)
    return O.reshape(nc, R, -1), HELD.reshape(nc, R, -1), GRO.reshape(nc, R, -1)
def full(S, R, seed, cs, normtol):
    rng = np.random.default_rng(seed); st = LIB.first_active_day(S)
    off = rng.integers(0, 30, size=R); phases = rng.integers(0, 3, size=R)
    jcd, jph = E.jitter(R, int(rng.integers(1 << 30)))
    d0s = st + off; d1s = np.full(R, S.b)
    O, H, G = run(S, cs, d0s, d1s, phases, jcd, jph, normtol)
    g = LIB.ann_lg(O[:, :, E.O_FINAL], (d1s - d0s)[None, :])
    return O, g
def windows(S, R, seed, cs, normtol):
    wins = S.windows(LIB.first_active_day(S)); rng = np.random.default_rng(seed)
    G = np.zeros((len(wins), len(cs)))
    for w, (s0, s1) in enumerate(wins):
        jcd, jph = E.jitter(R, int(rng.integers(1 << 30))); phases = rng.integers(0, 3, size=R)
        O, _, _ = run(S, cs, np.full(R, s0), np.full(R, s1), phases, jcd, jph, normtol)
        G[w] = LIB.ann_lg(O[:, :, E.O_FINAL], s1 - s0).mean(axis=1)
    return G, wins
name_k = lambda c: f"{c[0]:.1f}/{'none' if c[1] is None else format(c[1],'.2f')}/{'-' if c[2] is None else format(c[2],'.2f')}"
for name, seed in (("OLD", 20261101), ("NEW", 20261102), ("OLDPIT", 20261103)):
    S = getattr(RS, name.lower() if name != "OLDPIT" else "old_pit")()
    t = time.time()
    res = {}
    for tag, nt in (("V0 kept-qty", -1.0), ("LIVE-like norm tol15%", 0.15)):
        O, g = full(S, 48, seed + 4, CELLS, nt)
        G, wins = windows(S, 24, seed, CELLS, nt)
        res[tag] = (O, g, G)
    print(f"\n===== {name}  (R=48 full reps; windows n={len(res['V0 kept-qty'][2])}; {time.time()-t:.0f}s)")
    print("cell            | V0: g (CAGR) kills/path maxgr ruin liq75T/F3 liq1.0T/F3 | LIVE-like: g (CAGR) kills/path maxgr ruin liq75T/F3 liq1.0T/F3")
    for ci, c in enumerate(CELLS):
        line = []
        for tag in res:
            O, g, G = res[tag]
            br = [int((O[ci, :, E.O_C0 + m] > 0).sum()) for m in range(6)]
            line.append(f"{g[ci].mean():+.3f} ({np.expm1(g[ci].mean()):+6.1%}) {O[ci,:,E.O_KILLS].mean():5.1f} {O[ci,:,E.O_MAXGR].max():6.2f} {int((O[ci,:,E.O_RUIN]>0).sum()):2d} {br[2]}/{br[3]} {br[4]}/{br[5]}")
        print(f"{name_k(c):15s} | " + " | ".join(line))
    # paired window contrasts vs base (4,.35,.15) both modes
    base = CELLS.index((4.0, 0.35, 0.15))
    print("paired window diff vs (4,.35,.15) same mode [mean, boot95 lo/hi]  V0 || LIVE-like")
    for ci, c in enumerate(CELLS):
        if ci == base: continue
        parts = []
        for tag in res:
            G = res[tag][2]; d = G[:, ci] - G[:, base]
            b = LIB.boot_stats(d, seed=11)
            parts.append(f"{b['mean']:+.3f} [{b['lo']:+.3f},{b['hi']:+.3f}]")
        print(f"  {name_k(c):15s} " + "  ||  ".join(parts))
    # cross-mode: live-like base vs V0 base
    d = res["LIVE-like norm tol15%"][2][:, base] - res["V0 kept-qty"][2][:, base]
    b = LIB.boot_stats(d, seed=11); print(f"  BASE(4,.35,.15) LIVE-like minus V0: {b['mean']:+.3f} [{b['lo']:+.3f},{b['hi']:+.3f}] (window-level, n={len(d)})")
