"""R2-A smoke/V0-replication: ASSERT-ONLY on control cells whose values are already published (review). No candidate results are inspected."""
import sys, os, numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.dont_write_bytecode = True
from app import rs_lev_r2a_engine as E
REV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../docs/research/lev_loop/review")
sys.path.insert(0, REV)
import indep_sim as S   # independent implementation (reads panel only)

def chk(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else " :: " + detail), flush=True)
    assert ok, name + " " + detail

fin_pub = [14.5027, 18.4064, 15.8459]; kills_pub = [10, 9, 9]
for ph in range(3):
    r = E.run(phase=ph, km="daily")
    ri = S.run(phase=ph)
    f_i = float(ri["eq"][np.isfinite(ri["eq"])][-1])
    chk(f"V0 final published ph{ph}", abs(r["final"] - fin_pub[ph]) < 6e-5, f"{r['final']}")
    chk(f"V0 kills published ph{ph}", r["kills"] == kills_pub[ph], f"{r['kills']}")
    chk(f"V0 engine==indep_sim ph{ph}", abs(r["final"] - f_i) < 1e-9 * max(1, f_i), f"{r['final']} vs {f_i}")
    chk(f"V0 no-trade-cost-cap counters zero ph{ph}", float(np.sum(r["cnt"])) == 0.0)
# review lambda_kill published (control cell, lambda interpolation)
lam_pub = {"hourly": [24.601, 33.023, 29.359], "lam05": [11.916, 16.021, 9.077]}
for km, vals in lam_pub.items():
    for ph in range(3):
        r = E.run(phase=ph, km=km)
        chk(f"lambda-kill {km} ph{ph}", abs(r["final"] - vals[ph]) < 6e-4 * max(1, vals[ph]) , f"{r['final']}")
# min liquidation cushion published: U1 4x tier minbuf .312 (full universe, phase 0, daily kill)
r = E.run(phase=0, km="daily")
chk("U1 4x min cushion .312", abs(r["cmin"] - 0.312) < 1.5e-3, f"{r['cmin']}")
rng = np.random.default_rng(20261030)
subs = [sorted(rng.choice(E.N, size=30, replace=False).tolist()) for _ in range(30)]
r = E.run(cols=subs[23], phase=0, km="daily")
chk("U3_23 4x cushion -0.032", abs(r["cmin"] - (-0.0323)) < 1.5e-3, f"{r['cmin']}")
nb = sum(E.run(cols=c, phase=0, km="daily")["cmin"] <= 0 for c in subs)
chk("4x subsets liquidated == 1/30", nb == 1, f"{nb}")
# cap rules must be inert when thresholds are unreachable (identity)
r0 = E.run(phase=0, km="daily"); r1 = E.run(phase=0, km="daily", gcap=99.0, ncap=0.0, scap=0.0)
chk("inert gcap identity", r0["final"] == r1["final"])
# mechanical invariants of caps (assert only)
rc = E.run(phase=0, km="daily", gcap=4.2)
g = rc["gcl"][np.isfinite(rc["gcl"])]
chk("gross cap enforced at day close (<= cap+tol)", g.max() <= 4.2 + 1e-9, f"{g.max()}")
print("SMOKE_OK")
