"""EXPLORATORY (post-hoc, NOT pre-registered): no-kill / very deep kill at lev 4,5 + neighbour plateau of D18/D06/D00. Offline research only."""
import os, sys, pickle
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import app.rs_lev_b_run as R
from app.rs_lev_b_analyze_lib import boot_diff

ctx = R.Ctx()
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs/research/lev_loop/B")
ex = {
 "NK4": R.D(lev=4.0, kill=1.0, cool=0, desc="no kill lev4"),
 "NK5": R.D(lev=5.0, kill=1.0, cool=0, desc="no kill lev5"),
 "NK6": R.D(lev=6.0, kill=1.0, cool=0, desc="no kill lev6"),
 "K60": R.D(lev=4.0, kill=0.60, desc="kill 60%"),
 "K70": R.D(lev=4.0, kill=0.70, desc="kill 70%"),
 # +-25% neighbours (diagnostic)
 "D18a": R.D(kill=0.375, desc="D18 kill -25%"), "D18b": R.D(kill=0.625, desc="D18 kill +25%"),
 "D18c": R.D(kill=0.5, cool=10, desc="D18 cool -25%"), "D18d": R.D(kill=0.5, cool=18, desc="D18 cool +25%"),
 "D06a": R.D(cool=5, desc="D06 cool -25%"), "D06b": R.D(cool=9, desc="D06 cool +25%"),
 "D06c": R.D(cool=7, kill=0.26, desc="D06 kill -25%"), "D06d": R.D(cool=7, kill=0.44, desc="D06 kill +25%"),
 "D00a": R.D(kill=0.26), "D00b": R.D(kill=0.44), "D00c": R.D(cool=10), "D00d": R.D(cool=18),
}
R.DESIGNS.update(ex)
lines = []
cache = {}
def get(d, t, w):
    k = (d, t, w)
    if k not in cache:
        res = {}
        for sc in ("sc0", "sc1", "sc2", "sc3") + (("sc4",) if t == 1 else ()):
            res[sc] = R.run_cell(ctx, R.DESIGNS[d], t, w, sc, keep_eq=(sc == "sc0"))
        cache[k] = res
    return cache[k]
def row(d, t, w):
    res = get(d, t, w); r = res["sc0"]["rows"]
    liq = "/".join(str(int(((v['rows'].liq_f > 0) | (v['rows'].liq_t > 0)).sum())) for v in res.values())
    return f"{d} T{t} {w}: term med {r.term.median():.2f} (p10 {np.percentile(r.term,10):.2f}, p90 {np.percentile(r.term,90):.2f}) logg {r.logg.median():+.2f} MDD close {r.mdd.median():.2f} iMDD {r.imdd.median():.2f} kills {r.kills.median():.0f} avg_g {r.avg_g.median():.2f} liq(sc0..){liq}"
for d in ("D00", "NK4", "NK5", "NK6", "K60", "K70"):
    for t in (2, 1):
        for w in ("IS", "OOS"):
            lines.append(row(d, t, w))
lines.append("\nPaired bootstrap vs D00 (ann. log-growth diff, 90% CI)")
for d in ("NK4", "NK5", "K60", "K70", "D18", "D18a", "D18b", "D18c", "D18d", "D06", "D06a", "D06b", "D06c", "D06d", "D00a", "D00b", "D00c", "D00d"):
    for w in ("IS", "OOS"):
        txt = []
        for t in (1, 2):
            if d in ("D18", "D06"):
                A = pickle.load(open(os.path.join(OUT, "out", f"{d}_T{t}_{w}.pkl"), "rb"))["sc0"]["eq"]
                Bq = pickle.load(open(os.path.join(OUT, "out", f"D00_T{t}_{w}.pkl"), "rb"))["sc0"]["eq"]
                lq = pickle.load(open(os.path.join(OUT, "out", f"{d}_T{t}_{w}.pkl"), "rb"))
                nliq = sum(int((v['rows'].liq_f > 0).sum()) for v in lq.values())
            else:
                A = get(d, t, w)["sc0"]["eq"]; Bq = pickle.load(open(os.path.join(OUT, "out", f"D00_T{t}_{w}.pkl"), "rb"))["sc0"]["eq"]
                nliq = sum(int((v['rows'].liq_f > 0).sum()) for v in get(d, t, w).values())
            pt, ci = boot_diff(A, Bq)
            txt.append(f"T{t} {pt:+.2f} [{ci[0]:+.2f},{ci[1]:+.2f}] liq{nliq}")
        lines.append(f"{d} {w}: " + " | ".join(txt))
print("\n".join(lines))
