"""REVIEWER: inspect T09 (short TP -40%) events for wick/data artifacts and post-exit behaviour."""
import sys; sys.dont_write_bytecode = True
sys.path.insert(0, "/Users/user/Desktop/CODE/Ochestration/trading/docs/research/tp_loop/A")
import numpy as np, pandas as pd, lib
from lib import ENVS, TPSim
from app.rs_final_data import load_panel
P = load_panel(); CF = lib.load_all()[1]; S = TPSim(P, CF); N = S.names
rows = []
for ph in range(3):
    r = S.run(tp=dict(XL=0, XS=.4, frac=1, lockout=0), phase=ph, **ENVS["A"]); tr = r["trades"]
    for t in tr[tr[:, 4] == 1]:
        j = int(t[0]); xd = int(t[3]); ed = int(t[2]); h = int(t[10]); e = t[8]; f = t[9]
        H, L, C = S.H[xd, :, j], S.L[xd, :, j], S.C[xd, :, j]
        c_h = C[h]; c_d = C[23]
        nxt = [S.C[min(xd + k, S.nd - 1), 23, j] for k in (1, 2, 3, 7)]
        prevc = S.C[xd - 1, 23, j] if xd > 0 else np.nan
        rows.append(dict(ph=ph, sym=N[j], entry=S.days[ed].date(), exit=S.days[xd].date(), hold=xd - ed, hr=h, entry_px=e, fill=f,
                         close_hr_vs_fill=c_h / f - 1, close_day_vs_fill=c_d / f - 1, prev_close_vs_fill=prevc / f - 1,
                         nx1=nxt[0] / f - 1, nx3=nxt[2] / f - 1, nx7=nxt[3] / f - 1, pnl_eq=t[5] / t[6]))
D = pd.DataFrame(rows); pd.set_option("display.width", 250); pd.set_option("display.max_rows", 200)
print(len(D), "events (3 phases); unique (sym,exit):", D.drop_duplicates(["sym", "exit"]).shape[0])
U = D.drop_duplicates(["sym", "exit"]).sort_values("exit")
print(U[["sym", "entry", "exit", "hold", "hr", "close_hr_vs_fill", "close_day_vs_fill", "prev_close_vs_fill", "nx1", "nx3", "nx7"]].round(3).to_string())
print("median hold", U.hold.median(), " share where prev-day close was already <= fill:", (U.prev_close_vs_fill <= 0.0).mean().round(3))
print("share where same-day close is >5% above fill (wick-reversal):", (U.close_day_vs_fill > 0.05).mean().round(3))
print("share close_day > 20% above fill:", (U.close_day_vs_fill > 0.20).mean().round(3))
print("mean nx3", U.nx3.mean().round(3), "median", U.nx3.median().round(3), " mean nx7", U.nx7.mean().round(3))
U.to_csv("/Users/user/Desktop/CODE/Ochestration/trading/docs/research/tp_loop/review/t09_events.csv", index=False)
