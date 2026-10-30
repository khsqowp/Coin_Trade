"""Reviewer audit of R2C 'safety asymmetry': was the current cell simply FLAT (post-kill) on the stress days, or exposed with what gross/eq?
Uses a copy of the R2C engine (aud_engine.py) that additionally records held-at-day-open and gross/eq-at-open. Same seeds as r2c_main full runs."""
import os, sys
sys.dont_write_bytecode = True
ROOT = "/Users/user/Desktop/CODE/Ochestration/trading"
sys.path.insert(0, ROOT); sys.path.insert(0, ROOT + "/docs/research/lev_loop/R2C"); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
import aud_engine as AE
from app import rs_lev_r2c_lib as LIB, rs_lev_r2c_engine as E
import r2c_samples as RS
cs = LIB.combos(); idx = {c: i for i, c in enumerate(cs)}
KEY = [(4.0, 0.35, 0.15), (4.0, None, None), (5.0, 0.35, 0.15), (5.0, None, None), (4.0, 0.5, 0.15)]
STRESS = {"OLDPIT": ["2025-10-10", "2025-11-05", "2025-11-06", "2026-07-04", "2026-07-05", "2026-05-20", "2024-12-09"],
          "NEW": ["2020-03-12", "2021-01-11", "2021-02-15", "2021-05-07", "2021-05-19"],
          "OLD": ["2025-10-10", "2024-12-09", "2024-03-05", "2026-08-22"]}
def run_aud(S, R, seed, cs_):
    rng = np.random.default_rng(seed)
    st = LIB.first_active_day(S)
    off = rng.integers(0, 30, size=R); phases = rng.integers(0, 3, size=R)
    jcd, jph = E.jitter(R, int(rng.integers(1 << 30)))
    d0s = st + off; d1s = np.full(R, S.b)
    nc = len(cs_); PAR = LIB._pars(S, cs_, d0s, d1s, phases)
    JC = np.tile(jcd, (nc, 1)); JP = np.tile(jph, (nc, 1)); CM = np.tile(S.ones, (nc * R, 1))
    EVD = -np.ones((nc * R, S.n), np.int64); EVML = np.ones((nc * R, S.n)); EVMS = np.ones((nc * R, S.n))
    P = S.P
    O, KD, EQ, PS, HELD, GRO = AE.run_batch(P["H"], P["L"], P["C"], P["FD"], S.sc, S.cr, S.r1, CM, PAR, JC, JP, EVD, EVML, EVMS, False)
    return O.reshape(nc, R, -1), HELD.reshape(nc, R, -1), GRO.reshape(nc, R, -1), d0s
for name, seed in (("OLD", 20261101), ("NEW", 20261102), ("OLDPIT", 20261103)):
    S = getattr(RS, name.lower() if name != "OLDPIT" else "old_pit")()
    ref = LIB.full_runs(S, 48, seed + 4, cs=[k for k in KEY])
    O, HELD, GRO, d0s = run_aud(S, 48, seed + 4, list(KEY))
    par = np.nanmax(np.abs(O - ref["O"][:, :, :O.shape[2]]))
    print(f"\n=== {name}: parity of audit-engine outputs vs R2C engine (max abs diff over all output columns) = {par:.3g}")
    days = S.P["days"]
    for k_i, k in enumerate(KEY):
        row = []
        for d in STRESS[name]:
            di = int(days.searchsorted(pd.Timestamp(d, tz="UTC")))
            inrun = d0s <= di
            h = HELD[k_i, :, di].astype(bool) & inrun
            g = GRO[k_i, h, di]
            row.append(f"{d}: held {int(h.sum())}/{int(inrun.sum())} gross/eq@open med {np.median(g) if len(g) else float('nan'):.2f} max {g.max() if len(g) else float('nan'):.2f}")
        # share of all in-run days that are held
        tot = np.mean([HELD[k_i, r, d0s[r]:].mean() for r in range(48)])
        print(f"{str(k):22s} held-share-of-days {tot:.2f} | " + " | ".join(row))
