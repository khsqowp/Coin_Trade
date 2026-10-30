"""R2-B step 3b: 2025-10-10 cross-margin liquidation re-test with 1m MARK prices on the review's 30 random 30-symbol subsets (seed 20261030), 4x/5x/6x.
cushion = (W + pnl - MM)/prev_eq, MM tier r1 (BTC/ETH 0.4%, others 1.0%) and flat 3%; min over time. Models: hourly anti-sync LAST (review), hourly anti-sync MARK,
1m MARK close, 1m LAST close, 1m MARK anti-sync (minute low/high). Read-only."""
import json, os, sys
import numpy as np, pandas as pd
HERE = "/Users/user/Desktop/CODE/Ochestration/trading/app"
R2B = os.path.join(HERE, "..", "docs", "research", "lev_loop", "R2B")
sys.path.insert(0, os.path.join(HERE, "..", "docs", "research", "lev_loop", "review"))
import indep_sim as S
DAY = sys.argv[1] if len(sys.argv) > 1 else "2025-10-10"
z = np.load(os.path.join(R2B, "data", DAY + ".npz"))
last, mark = z["last"], z["mark"]                       # [N,1440,4]
N = len(S.NAMES)
rng = np.random.default_rng(20261030)
subs = [sorted(rng.choice(N, size=30, replace=False).tolist()) for _ in range(30)]
r1 = np.array([0.004 if b in ("BTC", "ETH") else 0.01 for b in S.NAMES])
D = int(S.DAYS.searchsorted(pd.Timestamp(DAY, tz="UTC")))
def hr(a):
    o, h, l, c = (a[:, :, k].reshape(N, 24, 60) for k in range(4)); return h.max(2), l.min(2), c[:, :, 59]
Hl, Ll, Cl = hr(last); Hm, Lm, Cm = hr(mark)
def cush(q, e, W, peq, P, mm):
    """P: [N,T] prices; returns min cushion over T."""
    held = q != 0
    pnl = (q[:, None] * (P - e[:, None]) * held[:, None]).sum(0)
    mmv = (np.abs(q)[:, None] * P * held[:, None] * (mm[:, None] if isinstance(mm, np.ndarray) else mm)).sum(0)
    return float(((W + pnl - mmv) / peq).min())
res = {}
for lev in (4.0, 5.0, 6.0):
    agg = {k: [] for k in ("hourly_last_anti_tier", "hourly_mark_anti_tier", "min_mark_close_tier", "min_last_close_tier", "min_mark_anti_tier", "hourly_last_anti_flat3", "min_mark_close_flat3", "min_mark_anti_flat3")}
    for k in range(30):
        r = S.run(cols=subs[k], lev=lev, phase=0, record=True)
        if D not in r["rec"]: continue
        q, e, W = r["rec"][D]; peq = r["eq"][D - 1]
        held = q != 0
        # hourly anti-sync
        for tag, (Hh, Lh) in (("last", (Hl, Ll)), ("mark", (Hm, Lm))):
            P = np.where(q[:, None] > 0, Lh, Hh)
            agg[f"hourly_{tag}_anti_tier"].append(cush(q, e, W, peq, P, r1))
            if tag == "last": agg["hourly_last_anti_flat3"].append(cush(q, e, W, peq, P, 0.03))
        Pm = mark[:, :, 3]; Pl = last[:, :, 3]
        Pm_a = np.where(q[:, None] > 0, mark[:, :, 2], mark[:, :, 1])
        agg["min_mark_close_tier"].append(cush(q, e, W, peq, Pm, r1)); agg["min_last_close_tier"].append(cush(q, e, W, peq, Pl, r1))
        agg["min_mark_anti_tier"].append(cush(q, e, W, peq, Pm_a, r1))
        agg["min_mark_close_flat3"].append(cush(q, e, W, peq, Pm, 0.03)); agg["min_mark_anti_flat3"].append(cush(q, e, W, peq, Pm_a, 0.03))
    res[lev] = {k: dict(n=len(v), n_neg=int(sum(x < 0 for x in v)), min=float(min(v)), med=float(np.median(v))) for k, v in agg.items() if v}
json.dump(res, open("/Users/user/Desktop/CODE/Ochestration/trading/docs/research/lev_loop/review2/rerun/liq_rerun_"+DAY+".json", "w"), indent=1)
print(f"{DAY}: subsets with negative cushion / 30 (min cushion across subsets, median)")
for lev, d in res.items():
    print(f"lev {lev:.0f}x")
    for k, v in d.items(): print(f"   {k:26s} neg {v['n_neg']:2d}/{v['n']}  min {v['min']:+.3f}  med {v['med']:+.3f}")
