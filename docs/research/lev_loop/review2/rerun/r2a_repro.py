"""Reviewer re-run of R2A headline: control f* median & P(anti,.75,tier) and G42 -- fresh engine runs, compared to stored stage1 pickle. Output only here."""
import sys, os, pickle, numpy as np, time
sys.dont_write_bytecode = True
ROOT = "/Users/user/Desktop/CODE/Ochestration/trading"
sys.path.insert(0, ROOT)
from app import rs_lev_r2a_run as R
st = pickle.load(open(ROOT + "/docs/research/lev_loop/R2A/out/stage1_IS.pkl", "rb"))
for km in ("daily", "lam15"):
    for cell in ("C0_control", "G42"):
        t = time.time()
        runs = R.run_paths(cell, km, "IS"); S = R.summarise(runs, "IS")
        P = S["P"][("tier", "anti", 0.75)]; P1 = S["P"][("tier", "anti", 1.0)]
        fs = float(np.median(S["fstar"]["anti"]))
        S0 = st[cell][km]["S"]
        P0 = S0["P"][("tier", "anti", 0.75)]; fs0 = float(np.median(S0["fstar"]["anti"]))
        print(f"{cell:10s} {km:6s} NEW f*med={fs:.4f} P75={P:.4f} P1.0={P1:.4f} n_uniq={S['n_unique']} | STORED f*med={fs0:.4f} P75={P0:.4f} n_uniq={S0['n_unique']} | match={abs(fs-fs0)<1e-9 and abs(P-P0)<1e-9} ({time.time()-t:.0f}s)", flush=True)
