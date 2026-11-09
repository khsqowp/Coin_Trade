"""R2C step 3: build the hourly PIT panel (float32 H/L/C, float64 FD) from raw public klines + funding.
Hours missing inside a symbol's life are forward-filled (limit 48h, same as the old panel); `live[d,j]` = at least one REAL bar that day.
member[d,j] = symbol is in that month's PIT top-45 (r2c_pit_universe.py). Outputs (scratch): pit_panel.npz (all dates);
(repo) data/new_panel_2020_2021.npz = days 2020-01-01..2021-12-31, only columns that are members in 2020-03..2021-12."""
import json, os, sys
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.environ["R2C_RAW"]; SCR = os.environ["RS_FINAL_SCRATCH"]
D0, D1 = pd.Timestamp("2020-01-01", tz="UTC"), pd.Timestamp("2026-09-30", tz="UTC")

def main():
    plan = json.load(open(os.path.join(HERE, "data/pit_symbols.json"))); syms = sorted(plan)
    mem = pd.read_csv(os.path.join(HERE, "data/pit_membership.csv.gz"))
    days = pd.date_range(D0, D1, freq="D"); nd = len(days); nh = nd * 24; n = len(syms)
    t0 = int(D0.timestamp() * 1000)
    H = np.full((nh, n), np.nan, np.float32); L = H.copy(); C = H.copy()
    real = np.zeros((nh, n), bool); F = np.zeros((nh, n), np.float32)
    ndata = {}
    for j, s in enumerate(syms):
        a = np.load(f"{RAW}/h/{s}.npz")["a"]; f = np.load(f"{RAW}/f/{s}.npz")["f"]
        ndata[s] = len(a)
        if len(a):
            ts = a[:, 0].copy(); ts[ts > 1e14] /= 1000.0
            k = ((ts - t0) // 3600000).astype(np.int64); ok = (k >= 0) & (k < nh)
            k = k[ok]; aa = a[ok]
            H[k, j] = aa[:, 2]; L[k, j] = aa[:, 3]; C[k, j] = aa[:, 4]; real[k, j] = True
        if len(f):
            ts = f[:, 0].copy(); ts[ts > 1e14] /= 1000.0
            k = np.round((ts - t0) / 3600000.0).astype(np.int64); ok = (k >= 0) & (k < nh)
            F[k[ok], j] = f[ok, 1]
    for arr in (H, L, C):
        df = pd.DataFrame(arr).ffill(limit=48)
        arr[:] = df.to_numpy()
    H = H.reshape(nd, 24, n); L = L.reshape(nd, 24, n); C = C.reshape(nd, 24, n)
    FD = np.nansum(C.astype(np.float64) * F.reshape(nd, 24, n), axis=1)
    live = real.reshape(nd, 24, n).any(axis=1)
    member = np.zeros((nd, n), bool); col = {s: j for j, s in enumerate(syms)}
    for r in mem.itertuples():
        m0 = pd.Timestamp(r.month + "-01", tz="UTC"); m1 = m0 + pd.offsets.MonthBegin(1)
        a, b = int(days.searchsorted(m0)), int(days.searchsorted(m1))
        member[a:b, col[r.sym]] = True
    member &= live
    np.savez_compressed(os.path.join(SCR, "pit_panel.npz"), names=np.array(syms), days=days.tz_convert(None).values, H=H, L=L, C=C, FD=FD, live=live, member=member)
    print("panel", H.shape, "members/day (median)", int(np.median(member.sum(1))), "no-data symbols", [s for s in syms if ndata[s] == 0])
    # NEW sample extract
    e = int(days.searchsorted(pd.Timestamp("2022-01-01", tz="UTC")))
    d_new0 = int(days.searchsorted(pd.Timestamp("2020-03-01", tz="UTC")))
    cols = [j for j in range(n) if member[d_new0:e, j].any()]
    np.savez_compressed(os.path.join(HERE, "data/new_panel_2020_2021.npz"), names=np.array([syms[j] for j in cols]), days=days[:e].tz_convert(None).values,
                        H=H[:e][:, :, cols], L=L[:e][:, :, cols], C=C[:e][:, :, cols], FD=FD[:e][:, cols], live=live[:e][:, cols], member=member[:e][:, cols])
    print("NEW extract columns", len(cols))
if __name__ == "__main__":
    main()
