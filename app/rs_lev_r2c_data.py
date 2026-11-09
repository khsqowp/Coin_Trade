"""R2-C data layer: old survivor panel loader (read-only npz) + point-in-time (PIT) panel builder from raw public klines."""
from __future__ import annotations
import os
import numpy as np
import pandas as pd

SCR = os.environ.get("RS_FINAL_SCRATCH", "")
LB = 14


def load_old():
    z = np.load(os.path.join(SCR, "rs_final_panel.npz"), allow_pickle=True)
    names = [str(x) for x in z["names"]]
    days = pd.DatetimeIndex(z["days"], tz="UTC")
    n = len(names)
    return dict(names=names, days=days, H=z["H"], L=z["L"], C=z["C"], FD=z["FD"], member=np.ones((len(days), n), bool))


def scores(P, member=None):
    CL = P["C"][:, 23, :]
    s = np.full(CL.shape, np.nan)
    with np.errstate(invalid="ignore", divide="ignore"):
        s[LB:] = CL[LB:] / CL[:-LB] - 1
    m = P.get("member") if member is None else member
    if m is not None:
        s[~m] = np.nan
    s[~np.isfinite(s)] = np.nan
    return s


def crash(P):
    b = P["C"][:, 23, P["names"].index("BTCUSDT" if "BTCUSDT" in P["names"] else "BTC")]
    r = np.full(len(b), np.nan)
    with np.errstate(invalid="ignore", divide="ignore"):
        r[LB:] = b[LB:] / b[:-LB] - 1
    return (np.isfinite(r) & (r < -0.10)).astype(np.float64)


def r1_vec(names):
    return np.array([0.004 if nm in ("BTC", "ETH", "BTCUSDT", "ETHUSDT") else 0.01 for nm in names])


def day_index(P, date):
    return int(P["days"].searchsorted(pd.Timestamp(date, tz="UTC")))


def slice_panel(P, a, b, cols=None, dtype=np.float64):
    """Slice days [a,b) (indices) and optionally columns; returns contiguous arrays (day axis re-based to 0)."""
    cols = list(range(len(P["names"]))) if cols is None else cols
    o = dict(names=[P["names"][j] for j in cols], days=P["days"][a:b])
    for k in ("H", "L", "C"):
        o[k] = np.ascontiguousarray(P[k][a:b][:, :, cols].astype(dtype))
    o["FD"] = np.ascontiguousarray(P["FD"][a:b][:, cols].astype(dtype))
    o["member"] = np.ascontiguousarray(P["member"][a:b][:, cols])
    return o
