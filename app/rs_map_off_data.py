"""Offline map: LOCAL-ONLY data layer (no network). Builds daily (UTC) and 4h OHLCV arrays for the 45-symbol universe
from .rs_cache/vision/klines_1h, aligned to the engine panel (rs_final_data.load_panel). Cached as npz in scratch."""
from __future__ import annotations
import os
import numpy as np
import pandas as pd
from app.rs_final_data import load_panel, SCRATCH

V = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".rs_cache", "vision")
CACHE = os.path.join(SCRATCH, "mapoff", "rs_map_off_data.npz")


def _hourly_raw(b, t0, nh):
    d = pd.read_csv(f"{V}/klines_1h/{b}USDT.csv.gz", header=None)
    cols = list(d.columns)
    ts = pd.to_datetime(d[cols[0]].astype("int64"), unit="ms", utc=True)
    d = pd.DataFrame({"o": d[cols[1]].astype(float).values, "v": d[cols[7]].astype(float).values}, index=ts)
    d = d[~d.index.duplicated()].sort_index()
    idx = pd.date_range(t0, periods=nh, freq="1h", tz="UTC")
    d = d.reindex(idx)
    return d["o"].to_numpy(), d["v"].to_numpy()


def load_data(use_cache=True) -> dict:
    """returns D: names, days, d{o,h,l,c,v}(nd,n), b4{o,h,l,c,v}(nd*6,n), FD(nd,n), P(engine panel)."""
    P = load_panel()
    names, days = P["names"], P["days"]
    nd, _, n = P["C"].shape
    if use_cache and os.path.exists(CACHE):
        z = np.load(CACHE)
        d = {k: z["d_" + k] for k in "ohlcv"}; b4 = {k: z["b_" + k] for k in "ohlcv"}
        return dict(names=names, days=days, d=d, b4=b4, FD=P["FD"], P=P)
    nh = nd * 24
    HO = np.full((nh, n), np.nan); HV = np.full((nh, n), np.nan)
    for j, b in enumerate(names):
        HO[:, j], HV[:, j] = _hourly_raw(b, days[0], nh)
    HH = P["H"].reshape(nh, n); HL = P["L"].reshape(nh, n); HC = P["C"].reshape(nh, n)

    def agg(step):
        m = nh // step
        o = HO.reshape(m, step, n); h = HH.reshape(m, step, n); l = HL.reshape(m, step, n); c = HC.reshape(m, step, n)
        v = HV.reshape(m, step, n)
        def first(a):
            ok = np.isfinite(a); idx = np.argmax(ok, axis=1)
            r = np.take_along_axis(a, idx[:, None, :], 1)[:, 0, :]
            return np.where(ok.any(1), r, np.nan)
        def last(a):
            ok = np.isfinite(a); idx = step - 1 - np.argmax(ok[:, ::-1, :], axis=1)
            r = np.take_along_axis(a, idx[:, None, :], 1)[:, 0, :]
            return np.where(ok.any(1), r, np.nan)
        with np.errstate(all="ignore"):
            hi = np.nanmax(h, axis=1); lo = np.nanmin(l, axis=1)
            vs = np.nansum(v, axis=1); vs[~np.isfinite(v).any(1)] = np.nan
        cl = last(c); op = first(o)
        op = np.where(np.isfinite(op), op, first(c))
        return dict(o=op, h=hi, l=lo, c=cl, v=vs)
    d = agg(24); b4 = agg(4)
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    np.savez_compressed(CACHE, **{"d_" + k: v for k, v in d.items()}, **{"b_" + k: v for k, v in b4.items()})
    return dict(names=names, days=days, d=d, b4=b4, FD=P["FD"], P=P)


if __name__ == "__main__":
    D = load_data()
    print(D["d"]["c"].shape, D["b4"]["c"].shape, np.isfinite(D["d"]["v"]).mean(), np.nanmedian(D["d"]["v"]))
    j = D["names"].index("BTC"); print(D["d"]["o"][-2:, j], D["d"]["c"][-2:, j], D["d"]["v"][-2:, j])
