"""Final-integration research: LOCAL-ONLY data layer (no network, no ccxt import).
Builds the hourly day x 24 x n panel from .rs_cache/vision and caches it as npz in a scratch dir."""
from __future__ import annotations
import ast, os, re
import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
SCRATCH = os.environ.get("RS_FINAL_SCRATCH", "/private/tmp/claude-501/-Users-user-Desktop-CODE-Ochestration/20fd8e9e-6d26-4ff1-a6b5-39a3bd8d3e48/scratchpad")


def universe() -> list[str]:
    src = open(os.path.join(_HERE, "momentum_rotation_loop.py"), encoding="utf-8").read()
    m = re.search(r"^UNIVERSE\s*=\s*(\[.*?\])", src, re.S | re.M)
    return list(ast.literal_eval(m.group(1)))


def load_panel(ffill_hours: int = 48):
    cache = os.path.join(SCRATCH, "rs_final_panel.npz")
    if os.path.exists(cache):
        z = np.load(cache, allow_pickle=True)
        return dict(names=list(z["names"]), days=pd.DatetimeIndex(z["days"], tz="UTC"), H=z["H"], L=z["L"], C=z["C"], FD=z["FD"])
    from app.rs_risk_load import load
    from app.rs_risk_engine import build_panel
    ohlc, fund = load()
    uni = universe()
    ohlc = {b: ohlc[b] for b in uni if b in ohlc}
    fund = {b: fund[b] for b in uni if b in fund}
    P = build_panel(ohlc, fund)
    nd, _, n = P["C"].shape
    out = {}
    for k in ("H", "L", "C"):
        a = pd.DataFrame(P[k].reshape(nd * 24, n)).ffill(limit=ffill_hours).to_numpy()
        out[k] = a.reshape(nd, 24, n)
    # daily funding payment per unit qty: sum_h close_h * rate_h (long pays positive)
    FD = np.nansum(out["C"] * P["F"], axis=1)
    days = P["days"]
    np.savez_compressed(cache, names=np.array(P["names"]), days=days.tz_convert(None).values, FD=FD, **out)
    return dict(names=P["names"], days=days, FD=FD, **out)


if __name__ == "__main__":
    P = load_panel()
    print(len(P["names"]), P["days"][0], P["days"][-1], P["C"].shape)
    c = P["C"][:, -1, :]
    print("coins first valid:", {n: str(P["days"][int(np.argmax(np.isfinite(c[:, j])))].date()) for j, n in enumerate(P["names"])})
