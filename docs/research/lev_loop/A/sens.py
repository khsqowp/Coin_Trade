"""Post-selection exploratory sensitivities: cooldown 7, kill_mode 2 (HWM on best-case)."""
import os, sys, pickle
from lib import *
from summ import *
if __name__ == "__main__":
    cool = os.environ.get("LEV_COOL", "14"); kms = [int(x) for x in sys.argv[1].split(",")]
    cells = [(4.0, .35), (4.0, .5), (4.0, 1.0), (5.0, .25), (5.0, .35), (5.0, .5), (5.0, 1.0), (3.0, .35)]
    out = []
    for win in ("IS", "OOS", "FULL"):
        tasks = [(c, win, sc, km, o, p, False) for c in cells for (o, p) in PATHS for km in kms for sc in ("BASE", "VOL")]
        r = pd.DataFrame(run_batch(tasks))
        r["win"] = win; out.append(r)
    df = pd.concat(out)
    df.to_pickle(f"sens_cool{cool}_km{sys.argv[1].replace(',','')}.pkl")
    for win in ("IS", "OOS", "FULL"):
        for km in kms:
            print(f"--- cool {cool} kmode {km} {win}")
            for c in cells:
                g = df[(df.win == win) & (df.kmode == km) & (df.scen == "BASE") & (df.cell == c)]
                v = df[(df.win == win) & (df.kmode == km) & (df.scen == "VOL") & (df.cell == c)]
                print(f"  {c}: g_mean {g.g.mean():+.2f} W_med {g.wend.median():7.2f} kills {g.kills.mean():5.1f} liqBASE {int(g.liq_flat.sum()):3d} liqVOL {int(v.liq_flat.sum()):3d}")
