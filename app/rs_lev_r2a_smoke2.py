"""assert-only plumbing smoke for runner on a tiny path count (prints PASS/FAIL only, never values)."""
import sys, os
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import numpy as np
from app import rs_lev_r2a_run as R
R.SPECS = R.SPECS[:4]
for cell in ("C0_control", "X2_G46_N05_S12", "C1_norm"):
    for km in ("daily", "lam15"):
        runs = R.run_paths(cell, km, "IS")
        S = R.summarise(runs, "IS")
        assert np.all(np.isfinite(S["g"])) and S["n_unique"] >= 1 and len(S["fstar"]["anti"]) == 4
        assert all(np.isfinite(r["final"]) and r["final"] > 0 for r in runs)
        assert S["blk"][("tier", "anti", 0.75)][1].sum() > 100
        for r in runs:  # accounting invariants: gross cap/net cap respected where requested
            if cell.startswith("X2"):
                assert np.nanmax(r["gcl"]) <= 4.6 * 1.002 and np.nanmax(r["scl"]) <= 0.456 * 1.002
print("PASS plumbing")
sub = R.run_subsets("G42", "daily", "IS"); assert len(sub["tp1"]) == 30
a = R.boot_P_rel(R.summarise(R.run_paths("G42", "daily", "IS"), "IS"), R.summarise(R.run_paths("C0_control", "daily", "IS"), "IS"))
print("PASS subsets+bootstrap")
