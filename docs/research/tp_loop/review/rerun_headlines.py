"""REVIEWER: independent re-run of headline numbers of A, B, C (read-only on live code). Output: stdout only."""
import os, sys
sys.dont_write_bytecode = True
import numpy as np, pandas as pd
from math import sqrt
from app.rs_final_data import load_panel
from app.rs_final_engine import window_metrics

P = load_panel()
# ---------------- A (rs_tp_engine)
sys.path.insert(0, "/Users/user/Desktop/CODE/Ochestration/trading/docs/research/tp_loop/A")
import lib
from lib import TPSim as ATP, ENVS, IS, OOS
CF = lib.load_all()[1]
SA = ATP(P, CF)
def awin(rl, a=None, b=None):
    ms = [window_metrics(r, a, b) for r in rl]
    return dict(cagr=np.mean([m["cagr"] for m in ms]), imdd=np.mean([m["imdd"] for m in ms]), mdd=np.mean([m["mdd"] for m in ms]),
                cal=np.mean([m["cagr"]/m["imdd"] for m in ms]), end=np.mean([m["end"] for m in ms]))
def arun(tp):
    return [SA.run(tp=tp, phase=ph, **ENVS["A"]) for ph in range(3)]
cfgs = {"V0": None, "T09": dict(XL=0, XS=.4, frac=1, lockout=0), "T03": dict(XL=.4, XS=.4, frac=1, lockout=0)}
for k, tp in cfgs.items():
    rl = arun(tp)
    for w, (a, b) in (("IS", IS), ("OOS", OOS), ("full", (None, None))):
        m = awin(rl, a, b); print("A", k, w, {x: round(float(v), 3) for x, v in m.items()}, "kills", np.mean([r["kills"] for r in rl]))
# ---------------- B
from app.rs_tp_b_engine import TPSim as BTP, tp_params
SB = BTP(P)
def bsh(r): return r.mean()/r.std(ddof=1)*sqrt(365)
def brun(tp, **kw):
    out = []
    for ph in range(3):
        r = SB.run_tp(tp, phase=ph, **kw); eq = np.nan_to_num(r["eq"].to_numpy()[r["d0"]:]); prev = np.r_[1.0, eq[:-1]]; out.append(eq/prev-1)
    return out
days = SB.days[SB.d_start():]
isn = np.asarray(days <= pd.Timestamp("2024-06-30", tz="UTC"))
v0 = brun(tp_params())
for k, tp in {"V0": tp_params(), "S_8": tp_params(3, 8, 0, 0, 0, 0.0005), "T_atr2": tp_params(1, 2, 0, 0, 0, 0.0005)}.items():
    o = brun(tp)
    f = lambda m: float(np.mean([bsh(x[m]) for x in o]))
    fv = lambda m: float(np.mean([bsh(x[m]) for x in v0]))
    print("B", k, "Sharpe IS/OOS/full", round(f(isn),3), round(f(~isn),3), round(f(np.ones(len(isn),bool)),3),
          "d", round(f(isn)-fv(isn),3), round(f(~isn)-fv(~isn),3), round(f(np.ones(len(isn),bool))-fv(np.ones(len(isn),bool)),3))
# ---------------- C
from app.rs_tp_c_engine import TPSim as CTP, xparams
SC = CTP(P)
def crets(res, d0):
    e = res["eq"].to_numpy().copy(); e[np.isnan(e)] = 0.0; r = np.full(len(e), np.nan); prev = e[:-1]
    with np.errstate(divide="ignore", invalid="ignore"): r[1:] = np.where(prev > 0, e[1:]/prev-1, 0.0)
    r[:d0+1] = np.nan; return r
def cstat(r):
    r = r[np.isfinite(r)]; eq = np.cumprod(1+r); cagr = eq[-1]**(365.0/len(r))-1; hw = np.maximum.accumulate(np.r_[1.0, eq])[1:]; mdd = np.max(1-eq/hw)
    return cagr/mdd, cagr, mdd
for name, base in (("LIVE", dict(lev=4.0, deploy=0.95)), ("RESEARCH", dict(lev=2.0, deploy=1.0))):
    for k, c in {"V0": dict(), "A1": dict(xp=(3,3.0,0,0)), "R2": dict(rebal=2)}.items():
        reb = c.get("rebal", 3)
        runs = [SC.run(rebal=reb, phase=ph, xp=xparams(*c.get("xp", (0,3.0,0,0))), **base) for ph in range(reb)]
        st = np.array([cstat(crets(r, SC.d0)) for r in runs]).mean(0)
        print("C", name, k, "Calmar/CAGR/MDD", np.round(st, 3), "kills", np.mean([r["kills"] for r in runs]))
