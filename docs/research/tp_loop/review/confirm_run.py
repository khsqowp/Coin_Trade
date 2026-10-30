"""REVIEWER confirmatory run (prereg_confirm.md). Also V0 leverage ladder (exploratory). stdout + json in review/."""
import sys, json, os; sys.dont_write_bytecode = True
sys.path.insert(0, "/Users/user/Desktop/CODE/Ochestration/trading/docs/research/tp_loop/A")
sys.path.insert(0, "/Users/user/Desktop/CODE/Ochestration/trading/docs/research/tp_loop/review")
import numpy as np, pandas as pd, lib
from lib import ENVS, IS, OOS
from rs_tp_review_engine import TPSim
from app.rs_tp_engine import TPSim as ASim
from app.rs_final_data import load_panel
from app.rs_final_engine import window_metrics
OUT = "/Users/user/Desktop/CODE/Ochestration/trading/docs/research/tp_loop/review/"
P = load_panel(); CF = lib.load_all()[1]; S = TPSim(P, CF); SA = ASim(P, CF)
T09 = dict(XL=0, XS=.4, frac=1, lockout=0)
BASE = dict(rebal=3, K=8, kill=.35, cool=14, cost=.001, fund=1, minn=0., eq0=1.)
# mask-all-ones identity check vs A's engine
for ph in range(3):
    a = SA.run(tp=T09, phase=ph, lev=4.0, deploy=.95, **BASE); b = S.run(tp=T09, phase=ph, lev=4.0, deploy=.95, **BASE)
    assert np.array_equal(a["eq"].to_numpy(), b["eq"].to_numpy(), equal_nan=True)
print("review engine == A engine (mask all ones): OK")

def runs(tp, lev, dep, kill=.35, tpday=None):
    kw = dict(BASE); kw["kill"] = kill
    return [S.run(tp=tp, phase=ph, lev=lev, deploy=dep, tpday=tpday, **kw) for ph in range(3)]
def wm(rl, a=None, b=None):
    ms = [window_metrics(r, a, b) for r in rl]
    return dict(cagr=np.mean([m["cagr"] for m in ms]), imdd=np.mean([m["imdd"] for m in ms]), mdd=np.mean([m["mdd"] for m in ms]),
                sh=np.mean([m["sharpe"] for m in ms]), cal=np.mean([m["cagr"] / m["imdd"] if m["imdd"] > 0 else 0 for m in ms]), end=np.mean([m["end"] for m in ms]))
W = {"IS": IS, "OOS": OOS, "full": (None, None)}
def cmp(rb, rt):
    liq = any(r["liq"] for r in rb) or any(r["liq"] for r in rt)
    res = {}
    for w, (a, b) in W.items():
        x, y = wm(rb, a, b), wm(rt, a, b); res[w] = dict(v0=x, tp=y)
    f = res["full"]
    d = dict(dSh=f["tp"]["sh"] - f["v0"]["sh"], dCal=f["tp"]["cal"] - f["v0"]["cal"], cagr_ratio=f["tp"]["cagr"] / f["v0"]["cagr"] if f["v0"]["cagr"] > 0 else np.nan,
             dCalIS=res["IS"]["tp"]["cal"] - res["IS"]["v0"]["cal"], dCalOOS=res["OOS"]["tp"]["cal"] - res["OOS"]["v0"]["cal"],
             liq_v0=any(r["liq"] for r in rb), liq_tp=any(r["liq"] for r in rt),
             kills_v0=np.mean([r["kills"] for r in rb]), kills_tp=np.mean([r["kills"] for r in rt]), ntp=np.mean([r["ntp"] for r in rt]),
             expo_v0=float(np.nanmean([r["expo"].to_numpy() for r in rb])), expo_tp=float(np.nanmean([r["expo"].to_numpy() for r in rt])))
    d["informative"] = not liq
    d["PASS"] = bool((not liq) and d["dSh"] >= .20 and d["dCal"] > 0 and d["cagr_ratio"] >= .9 and d["dCalIS"] > 0 and d["dCalOOS"] > 0)
    return d, res
CELLS = {"K33": (4.0, .95, .33), "K37": (4.0, .95, .37), "KOFF": (4.0, .95, 1.0), "L15": (1.5, .95, .35), "L20": (2.0, .95, .35), "L30": (3.0, .95, .35)}
OUTJ = {"cells": {}}
for k, (lev, dep, kill) in CELLS.items():
    rb = runs(None, lev, dep, kill); rt = runs(T09, lev, dep, kill)
    d, res = cmp(rb, rt); OUTJ["cells"][k] = dict(summary=d, detail=res)
    print(k, {x: (round(float(v), 3) if not isinstance(v, (bool, np.bool_)) else bool(v)) for x, v in d.items()})
    for w in W: print("   ", w, "V0 cagr %.3f imdd %.3f sh %.2f cal %.2f | T09 cagr %.3f imdd %.3f sh %.2f cal %.2f" % tuple(res[w][s][m] for s in ("v0", "tp") for m in ("cagr", "imdd", "sh", "cal")))
inf = [k for k, v in OUTJ["cells"].items() if v["summary"]["informative"]]; ps = [k for k in inf if OUTJ["cells"][k]["summary"]["PASS"]]
low = [k for k in ("L15", "L20", "L30") if OUTJ["cells"][k]["summary"]["PASS"]]
print("INFORMATIVE", inf, "PASS", ps, "low-chaos pass", low)
OUTJ["decision"] = dict(informative=inf, passed=ps, low_chaos_passed=low)

# ---- D1/D2 diagnostics
r0 = S.run(tp=T09, phase=0, lev=4.0, deploy=.95, **BASE); tr = r0["trades"]; ev = tr[tr[:, 4] == 1]
dd = pd.Series([int(x) for x in ev[:, 3]]).value_counts(); cl = sorted(dd[dd >= 3].index)
print("D1 events", len(ev), "distinct dates", len(dd), "cluster days(>=3)", [str(S.days[d].date()) for d in cl], "share of events on cluster days", round(dd[dd >= 3].sum() / len(ev), 3))
mask = np.ones(S.nd); mask[cl] = 0
OUTJ["D1"] = dict(events=len(ev), dates=len(dd), cluster_days=[str(S.days[d].date()) for d in cl], share=float(dd[dd >= 3].sum() / len(ev)))
for k in ("K35", "L20"):
    lev, dep, kill = (4.0, .95, .35) if k == "K35" else (2.0, .95, .35)
    rb = runs(None, lev, dep, kill); rt = runs(T09, lev, dep, kill); rm = runs(T09, lev, dep, kill, tpday=mask)
    for nm, rr in (("T09 full", rt), ("T09 minus cluster days", rm)):
        d, res = cmp(rb, rr); print("D2", k, nm, {x: round(float(v), 3) for x, v in d.items() if x in ("dSh", "dCal", "cagr_ratio", "dCalIS", "dCalOOS", "ntp", "kills_tp", "expo_v0", "expo_tp")})
        OUTJ.setdefault("D2", {})[f"{k}|{nm}"] = {x: float(v) for x, v in d.items() if x in ("dSh", "dCal", "cagr_ratio", "dCalIS", "dCalOOS", "ntp", "kills_tp", "expo_v0", "expo_tp")}

# ---- noise / MDE: paired block bootstrap of dSharpe (LIVE kill .35) and 'path chaos' of V0
def sleeve(rl):
    return np.mean([r["eq"].dropna().pct_change().dropna().to_numpy()[:min(len(x["eq"].dropna()) for x in rl) - 1] for r in rl], axis=0)
rb = runs(None, 4.0, .95); rt = runs(T09, 4.0, .95)
n = min(len(r["eq"].dropna()) for r in rb + rt) - 1
a = np.mean([r["eq"].dropna().pct_change().dropna().to_numpy()[-n:] for r in rb], 0); b = np.mean([r["eq"].dropna().pct_change().dropna().to_numpy()[-n:] for r in rt], 0)
rng = np.random.default_rng(1); bl = 15; ds = []
sh = lambda x: x.mean() / x.std(ddof=1) * np.sqrt(365)
for _ in range(2000):
    idx = np.concatenate([np.arange(s, s + bl) % n for s in rng.integers(0, n, n // bl + 1)])[:n]; ds.append(sh(b[idx]) - sh(a[idx]))
ds = np.array(ds); se = ds.std()
print("paired bootstrap dSharpe(T09-V0) LIVE: point %.3f  SE %.3f  90%%CI [%.2f,%.2f]  => MDE(80%% power, 5%% two-sided) ~ %.2f" % (sh(b) - sh(a), se, *np.percentile(ds, [5, 95]), 2.8 * se))
OUTJ["mde"] = dict(point=float(sh(b) - sh(a)), se=float(se), mde80=float(2.8 * se))
# generic: SE of Sharpe of V0 itself
print("V0 sleeve Sharpe %.2f ; analytic SE of an annualised Sharpe over %.1f y: %.2f" % (sh(a), n / 365, np.sqrt((1 + .5 * (sh(a) / np.sqrt(365)) ** 2 * 365 / 365 * 0 + .5 * (sh(a)) ** 2) / (n / 365))))

# ---- exploratory leverage ladder (V0 only)
print("LEVERAGE LADDER (V0, kill .35 cool 14)")
lad = {}
for lev, dep in [(2.0, .95), (2.0, 1.0), (2.5, .95), (2.5, 1.0), (3.0, .95), (3.0, 1.0), (3.8, 1.0), (4.0, .95), (4.0, 1.0)]:
    rl = runs(None, lev, dep)
    row = {w: wm(rl, *W[w]) for w in W}; row["kills"] = float(np.mean([r["kills"] for r in rl])); row["liq"] = any(r["liq"] for r in rl)
    row["worst_phase_end"] = float(min(window_metrics(r)["end"] for r in rl))
    lad[f"{lev}x{dep}"] = row
    print("lev %.1f dep %.2f gross %.2f | full CAGR %.3f MDD %.3f iMDD %.3f Cal_i %.2f Sh %.2f kills %.1f end %.1f worst-phase-end %.1f | IS Cal_i %.2f OOS Cal_i %.2f | liq %s" % (
        lev, dep, lev * dep, row["full"]["cagr"], row["full"]["mdd"], row["full"]["imdd"], row["full"]["cal"], row["full"]["sh"], row["kills"], row["full"]["end"], row["worst_phase_end"], row["IS"]["cal"], row["OOS"]["cal"], row["liq"]))
OUTJ["ladder"] = lad
json.dump(OUTJ, open(OUT + "confirm_results.json", "w"), indent=1, default=float)
