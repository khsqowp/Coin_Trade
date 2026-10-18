"""Reconcile baseline 14/3/8: quantity-keeping (live-like) vs constant-weight (cadence engine) vs rs_risk_engine.
Toggles one modelling choice at a time. Prints a table; small JSON dump."""
from __future__ import annotations
import json, sys
import numpy as np, pandas as pd
from app.rs_final_data import load_panel, universe
from app.rs_final_engine import Sim, window_metrics

OUT = "docs/research/final_recon.json"


def mean_over_phases(S, N=3, **kw):
    rs = [S.run(phase=p, **dict(kw)) for p in range(N)]
    ms = [window_metrics(r, kw.get("a"), kw.get("b")) for r in rs]
    mean_over_phases.expo = float(np.mean([r["expo"].loc[r["eq"].dropna().index].mean() for r in rs]))
    return {k: float(np.mean([m[k] for m in ms])) for k in ("cagr", "mdd", "imdd", "sharpe", "calmar", "worst_day")}, [m["cagr"] for m in ms]


def fmt(m):
    return f"CAGR {m['cagr']*100:5.1f}% MDDclose {m['mdd']*100:4.1f}% MDDintra {m['imdd']*100:4.1f}% Calmar(intra) {m['calmar']:.2f} worstday {m['worst_day']*100:5.1f}%"


def main():
    P = load_panel(); S = Sim(P)
    res = {}
    def row(name, **kw):
        m, per = mean_over_phases(S, 3, **kw)
        res[name] = dict(m, per_phase_cagr=per, mean_gross=mean_over_phases.expo)
        print(f"{name:52s} {fmt(m)} gross {mean_over_phases.expo:.2f} | ph {[round(x*100,1) for x in per]}", flush=True)
    base = dict(lbs=(14,), rebal=3, K=8)
    print("== 14/3/8, 1x, phases 0..2 averaged, sim start 2022-01-01 ==")
    row("A quantity-keeping, fee .10%, funding", **base)
    row("B constant-weight (resize all each rebalance)", cw=1, **base)
    row("A fee 0.04% no funding (doc-style costs)", cost=0.0004, fund=0, **base)
    row("B fee 0.04% no funding", cw=1, cost=0.0004, fund=0, **base)
    row("A no funding", fund=0, **base)
    row("A fee 0 (gross edge)", cost=0.0, **base)
    row("B fee 0 (gross edge)", cw=1, cost=0.0, **base)
    row("C quantity-keeping + gross-normalised entries", gn=1, **base)
    row("C fee 0", gn=1, cost=0.0, **base)
    d21 = S.d_start("2021-07-01")
    row("A start 2021-07 (risk-engine FULL window), metrics 2021-07+", d0=d21, a="2021-07-01", **base)
    row("A start 2021-07, metrics only 2022-01+", d0=d21, a="2022-01-01", **base)
    for y0, y1 in (("2022-01-01", "2022-12-31"), ("2023-01-01", "2023-12-31"), ("2024-01-01", "2024-12-31"), ("2025-01-01", "2025-12-31")):
        row(f"A  window {y0[:4]}", a=y0, b=y1, **base)
        row(f"B  window {y0[:4]}", cw=1, a=y0, b=y1, **base)
    # cadence engine reference (import numba engine only; no ccxt)
    from app.rs_cadence_engine import Engine, Cfg
    c = pd.DataFrame(P["C"][:, -1, :], index=P["days"], columns=P["names"])
    c.index = c.index
    # funding daily frame (sum of rates) from 8h rates: reconstruct from FD / close is lossy -> use zeros
    f = pd.DataFrame(0.0, index=c.index, columns=c.columns)
    E = Engine({"close": c, "funding": f})
    ms = []
    for o in range(3):
        r = E.run(Cfg(lbs=(14,), k=8, cadence=3, offset=o), funding=False)
        ms.append(E.metrics(r))
    print("cadence engine (const-weight, no funding, fee .10%) per offset CAGR", [round(m["CAGR"]*100, 1) for m in ms],
          "mean", round(np.mean([m["CAGR"] for m in ms])*100, 1), "MDD", [round(m["MDD"]*100, 1) for m in ms])
    res["cadence_engine_nofund"] = dict(cagr=[m["CAGR"] for m in ms], mdd=[m["MDD"] for m in ms])
    row("B no funding (to compare with cadence engine)", cw=1, fund=0, **base)
    json.dump(res, open(OUT, "w"), indent=1)


if __name__ == "__main__":
    main()
