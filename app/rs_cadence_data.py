"""LOCAL-ONLY loader (no network). Reads .rs_cache/vision (data.binance.vision dump) and builds daily bars.
load(offset_hours=0) -> dict open/high/low/close/funding. Daily bar d starts at d 00:00 UTC + offset_hours
(timestamped by bar start date; for offset>0 the label is the date of bar start)."""
from __future__ import annotations
import os
import pandas as pd
from app.momentum_rotation_loop import UNIVERSE

ROOT = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".rs_cache", "vision")
_COLS = ["ot", "o", "h", "l", "c", "v", "ct", "qv", "n", "tb", "tq", "ig"]

def load(offset_hours: int = 0, bases=None):
    O, H, L, C, F = {}, {}, {}, {}, {}
    for b in (bases or UNIVERSE):
        kp = os.path.join(ROOT, "klines_1h", f"{b}USDT.csv.gz")
        if not os.path.exists(kp):
            continue
        k = pd.read_csv(kp, header=None, names=_COLS, compression="gzip")
        k = k[pd.to_numeric(k.ot, errors="coerce").notna()]
        k.index = pd.to_datetime(k.ot.astype("int64"), unit="ms", utc=True)
        k = k[~k.index.duplicated()].sort_index()
        rs = k.resample("1D", offset=pd.Timedelta(hours=offset_hours))
        o, h, l, c = rs.o.first(), rs.h.max(), rs.l.min(), rs.c.last()
        cnt = rs.o.count()
        ok = cnt >= 24  # drop partial bars
        O[b], H[b], L[b], C[b] = o[ok], h[ok], l[ok], c[ok]
        fp = os.path.join(ROOT, "funding", f"{b}USDT.csv.gz")
        if os.path.exists(fp):
            f = pd.read_csv(fp, header=None, names=["t", "iv", "r"], compression="gzip")
            f = f[pd.to_numeric(f.t, errors="coerce").notna()]
            f.index = pd.to_datetime(f.t.astype("int64"), unit="ms", utc=True)
            F[b] = f.r.astype(float)[~f.index.duplicated()].sort_index()
    return {"open": pd.DataFrame(O), "high": pd.DataFrame(H), "low": pd.DataFrame(L),
            "close": pd.DataFrame(C), "funding": pd.DataFrame(F)}
