"""R2-B step 6: re-run reviewer's lambda-interpolated hourly kill backtest (current cell 4x/.95/kill .35/cool 14) on a fine lambda grid; uses lambda_kill.run unchanged.
usage: python rs_lev_r2b_kill.py <lam_lo> <lam_mid> <lam_hi>   (empirical lambda bracket)"""
import os, sys, json
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "docs", "research", "lev_loop", "review"))
import lambda_kill as K, indep_sim as s
R2B = os.path.join(HERE, "..", "docs", "research", "lev_loop", "R2B")
yrs = (s.ND - int(s.DAYS.searchsorted(pd.Timestamp("2022-01-01", tz="UTC")))) / 365.0
def cell(lam):
    r = [K.run(lam, phase=p) for p in range(3)]
    g = np.mean([np.log(max(x[0], 1e-9)) for x in r]) / yrs
    return float(np.exp(g) - 1), float(np.mean([x[1] for x in r])), g
grid = [round(x, 3) for x in np.arange(0, 0.601, 0.01)]
tab = {lam: cell(lam) for lam in grid}
print("lambda | CAGR | mean kills (3 phases)")
for lam in grid:
    if abs(lam * 100 % 5) < 1e-9 or lam in (0.01, 0.02, 0.03): print(f"{lam:.2f} | {tab[lam][0]:+.1%} | {tab[lam][1]:.1f}")
lo, mid, hi = (float(a) for a in sys.argv[1:4])
def window(a, b):
    xs = [tab[l] for l in grid if a - 1e-9 <= l <= b + 1e-9]
    c = np.array([x[0] for x in xs]); return len(xs), float(np.mean(c)), float(np.min(c)), float(np.max(c)), float(np.median(c))
for name, (a, b) in dict(empirical_lo_hi=(lo, hi), empirical_mid_pm0_05=(max(0, mid - .05), mid + .05), review_0_1_to_0_3=(.1, .3), tail_0_1_to_0_5=(.1, .5)).items():
    n, m, mn, mx, md = window(a, b)
    print(f"window {name} lambda [{a:.2f},{b:.2f}] n={n}: mean CAGR {m:+.1%} median {md:+.1%} min {mn:+.1%} max {mx:+.1%}")
no = [K.run(0, phase=p, nokill=True) for p in range(3)]
g = np.mean([np.log(x[0]) for x in no]) / yrs
print(f"no-kill CAGR {np.exp(g)-1:+.1%}")
json.dump({str(k): v for k, v in tab.items()}, open(os.path.join(R2B, "kill_grid.json"), "w"))
