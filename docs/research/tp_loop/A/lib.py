"""Shared setup for BACKTESTER-A. Research only, offline."""
import os, sys
SCR = "/private/tmp/claude-501/-Users-user-Desktop-CODE-Ochestration/b40d7700-4bab-493b-9b2c-b8bac464cd8e/scratchpad"
os.environ.setdefault("RS_FINAL_SCRATCH", SCR + "/panel")
os.environ.setdefault("NUMBA_CACHE_DIR", SCR + "/nbc")
sys.dont_write_bytecode = True
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
sys.path.insert(0, ROOT)
import numpy as np, pandas as pd
from app.rs_final_data import load_panel, universe
from app.rs_final_engine import window_metrics
from app.rs_tp_engine import TPSim

def load_all():
    P = load_panel()
    cf_path = os.path.join(os.environ["RS_FINAL_SCRATCH"], "tp_CF.npy")
    if os.path.exists(cf_path):
        CF = np.load(cf_path)
    else:
        from app.rs_risk_load import load
        from app.rs_risk_engine import build_panel
        ohlc, fund = load(); uni = universe()
        ohlc = {b: ohlc[b] for b in uni if b in ohlc}; fund = {b: fund[b] for b in uni if b in fund}
        R = build_panel(ohlc, fund)
        assert list(R["names"]) == list(P["names"])
        CF = np.nan_to_num(P["C"] * R["F"]); np.save(cf_path, CF)
    assert np.array_equal(np.nansum(CF, axis=1), P["FD"]), "CF does not reproduce FD"
    return P, CF

ENVS = {
    "A": dict(rebal=3, K=8, lev=4.0, deploy=0.95, kill=.35, cool=14, cost=.001, fund=1, minn=0., eq0=1.),
    "B": dict(rebal=3, K=8, lev=2.0, deploy=1.0, kill=.35, cool=14, cost=.001, fund=1, minn=0., eq0=1.),
    "C": dict(rebal=3, K=8, lev=4.0, deploy=0.95, kill=.35, cool=14, cost=.001, fund=1, minn=5., eq0=142.),
}
IS = ("2022-01-01", "2024-06-30"); OOS = ("2024-07-01", None)
FOLDS = [("2023-01-01", "2023-12-31"), ("2024-01-01", "2024-12-31"), ("2025-01-01", "2025-06-30"), ("2025-07-01", None)]
