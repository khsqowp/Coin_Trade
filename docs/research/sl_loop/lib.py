"""Offline data and metric helpers for the preregistered SL study."""
from __future__ import annotations
import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.insert(0, ROOT)
SCRATCH = os.path.join(ROOT, ".rs_cache", "sl_panel")
os.environ.setdefault("RS_FINAL_SCRATCH", SCRATCH)
os.environ.setdefault("NUMBA_CACHE_DIR", os.path.join(ROOT, ".rs_cache", "sl_nbc"))
os.makedirs(SCRATCH, exist_ok=True); os.makedirs(os.environ["NUMBA_CACHE_DIR"], exist_ok=True)
import numpy as np
import pandas as pd

ENVA = dict(rebal=3, K=8, lev=4., deploy=.95, kill=.35, cool=14, cost=.001, fund=1, minn=0., eq0=1.)
IS = ("2022-01-01", "2024-06-30"); OOS = ("2024-07-01", None)

def load_all():
    from app.rs_final_data import load_panel
    P = load_panel()
    for k in ("H", "L", "C", "FD"):
        path = os.path.join(SCRATCH, f"{k}.npy")
        if not os.path.exists(path): np.save(path, P[k])
    cf_path = os.path.join(SCRATCH, "CF.npy")
    if os.path.exists(cf_path): CF = np.load(cf_path)
    else:
        from app.rs_risk_load import load
        from app.rs_risk_engine import build_panel
        from app.rs_final_data import universe
        ohlc, fund = load(); uni = universe()
        R = build_panel({b: ohlc[b] for b in uni if b in ohlc}, {b: fund[b] for b in uni if b in fund})
        assert list(R["names"]) == list(P["names"])
        CF = np.nan_to_num(P["C"] * R["F"]); np.save(cf_path, CF)
    assert np.array_equal(np.nansum(CF, axis=1), P["FD"]), "hourly funding cashflow does not reproduce daily FD"
    return P, CF

def phase_mean(results, a=None, b=None):
    from app.rs_final_engine import window_metrics
    vals = [window_metrics(r, a, b) for r in results]
    out = {}
    for k in ("cagr", "mdd", "imdd", "sharpe", "end"):
        out[k] = float(np.mean([x[k] for x in vals]))
        out[k + "_worst"] = float(max(x[k] for x in vals))
    ci = [x["cagr"] / x["imdd"] if x["imdd"] else 0. for x in vals]
    out["calmar_i"] = float(np.mean(ci)); out["calmar_i_worst"] = float(min(ci))
    return out
