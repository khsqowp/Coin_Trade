"""R2C post-hoc descriptive (declared in AMENDMENT-2; NOT used in verdicts): where do liquidation-buffer minima occur? Same seeds as r2c_main full runs."""
import os, sys
sys.path.insert(0, "/Users/user/Desktop/CODE/Ochestration/trading"); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from app import rs_lev_r2c_lib as LIB, rs_lev_r2c_engine as E
import r2c_samples as RS
cs = LIB.combos(); idx = {c: i for i, c in enumerate(cs)}
KEY = [(4.0, 0.35, 0.15), (4.0, 0.5, 0.15), (4.0, 0.6, 0.15), (4.0, None, None), (3.5, None, None), (5.0, 0.35, 0.15), (5.0, 0.5, 0.15), (5.0, 0.6, 0.15), (5.0, None, None)]
for name, seed in (("OLD", 20261101), ("NEW", 20261102), ("OLDPIT", 20261103)):
    S = getattr(RS, name.lower() if name != "OLDPIT" else "old_pit")()
    f = LIB.full_runs(S, 48, seed + 4); O = f["O"]
    print(f"\n=== {name}: worst-buffer day (f=0.75 tier, and f=1.0 flat3) across 48 reps; format date:count(min buffer over reps at that date)")
    for k in KEY:
        c = idx[k]
        out = []
        for m, lab in ((2, "f.75T"), (5, "f1F3")):
            d = O[c, :, E.O_D0 + m].astype(int); b = O[c, :, E.O_B0 + m]
            ser = pd.Series(b).groupby(pd.Series([str(S.P["days"][x].date()) for x in d])).agg(["count", "min"])
            ser = ser.sort_values("min").head(3)
            out.append(lab + " " + "; ".join(f"{i}:{int(r['count'])}({r['min']:+.2f})" for i, r in ser.iterrows()))
        print(f"{k}: " + " | ".join(out))
