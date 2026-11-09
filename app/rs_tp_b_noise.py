"""EXPLORATORY (not in prereg, excluded from conclusions): path-chaos noise floor of V0 itself under negligible perturbations."""
import os, numpy as np
from math import sqrt
from app.rs_final_data import load_panel
from app.rs_tp_b_engine import TPSim, tp_params

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "research", "tp_loop", "B", "tables_exploratory.md")
S = TPSim(load_panel())
def sh(r): return r.mean() / r.std(ddof=1) * sqrt(365)
def run(**kw):
    out = []
    for ph in range(3):
        r = S.run_tp(tp_params(), phase=ph, **kw)
        eq = np.nan_to_num(r["eq"].to_numpy()[r["d0"]:]); prev = np.r_[1.0, eq[:-1]]
        out.append(eq / prev - 1)
    return np.mean([sh(x) for x in out]), np.mean(out, axis=0)
base, rb = run()
L = ["# EXPLORATORY: V0 잡음 바닥 (사전등록 외, 결론 제외)\n", "V0 에 무시할 수준의 교란(비용 +-5/10%, kill 임계 +-0.01, d0 +1..3일)을 줄 때의 위상평균 전구간 Sharpe 변화. 익절 변형의 dSharpe 크기와 비교용.\n",
     "| 교란 | Sharpe | 변화 |", "|---|---|---|", f"| 기준 | {base:.3f} | 0 |"]
vals = []
for nm, kw in (("cost x0.90", dict(cost=0.0009)), ("cost x0.95", dict(cost=0.00095)), ("cost x1.05", dict(cost=0.00105)), ("cost x1.10", dict(cost=0.0011)),
               ("kill 0.34", dict(kill=0.34)), ("kill 0.36", dict(kill=0.36)), ("kill 0.33", dict(kill=0.33)), ("kill 0.37", dict(kill=0.37)),
               ("start +1d", dict(d0=S.d_start() + 1)), ("start +2d", dict(d0=S.d_start() + 2)), ("start +3d", dict(d0=S.d_start() + 3))):
    s_, _ = run(**kw); vals.append(s_ - base); L.append(f"| {nm} | {s_:.3f} | {s_-base:+.3f} |")
L.append(f"\n교란 변화의 표준편차 {np.std(vals, ddof=1):.3f}, 최대 절대 {np.max(np.abs(vals)):.3f}.")
open(OUT, "w").write("\n".join(L) + "\n"); print("\n".join(L))
