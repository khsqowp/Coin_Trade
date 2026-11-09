"""EXPLORATORY: vol-stress headroom of the blunt-kill structure (liquidation paths of 120 vs vol multiplier). Offline research only."""
import os, sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import app.rs_lev_b_run as R
from app.rs_lev_b_engine import BSim
ctx = R.Ctx()
P = ctx.base.P
print("| lev | vol mult | window | T1 liq/120 (median growth) | T2 liq/120 (median growth) |")
print("|---|---|---|---|---|")
for m in (1.25, 1.5, 1.75, 2.0):
    ctx.vol = BSim(P, m_vol=m)
    for lev, kill in ((3.0, 0.35), (4.0, 0.35), (5.0, 0.35), (4.0, 0.50)):
        for w in ("IS", "OOS"):
            cells = []
            for t in (1, 2):
                c = R.run_cell(ctx, R.D(lev=lev, kill=kill), t, w, "sc2")["rows"]
                cells.append(f"{int((c.liq_f > 0).sum())} ({c.logg.median():+.2f})")
            print(f"| {lev:g}{'' if kill==0.35 else ' kill'+str(kill)} | {m} | {w} | {cells[0]} | {cells[1]} |")
