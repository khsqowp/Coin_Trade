"""R2C data validation (asserts + descriptive universe stats only; no strategy results)."""
import os, sys
sys.path.insert(0, "/Users/user/Desktop/CODE/Ochestration/trading"); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from app import rs_lev_r2c_data as D, rs_lev_r2c_lib as LIB
import r2c_samples as RS
old = D.load_old(); z = np.load(os.path.join(os.environ["RS_FINAL_SCRATCH"], "pit_panel.npz"), allow_pickle=True)
pn = [str(x) for x in z["names"]]; pdays = pd.DatetimeIndex(z["days"], tz="UTC")
bad = []; checked = 0
for j, nm in enumerate(old["names"]):
    s = nm + "USDT"
    if s not in pn: bad.append(("missing", nm)); continue
    k = pn.index(s)
    a0 = int(pdays.searchsorted(old["days"][0])); a1 = int(pdays.searchsorted(pd.Timestamp("2026-09-30", tz="UTC")))
    o0 = 0; o1 = a1 - a0 + 1
    pc = z["C"][a0:a1 + 1, :, k].astype(float); oc = old["C"][o0:o1, :, j]
    lv = np.repeat(z['live'][a0:a1 + 1, k], 24).reshape(-1, 24)
    m = np.isfinite(pc) & np.isfinite(oc) & lv
    if m.sum() == 0: continue
    rel = np.percentile(np.abs(pc[m] / oc[m] - 1), 99.99); checked += 1
    fd = np.abs(z["FD"][a0:a1 + 1, k] - old["FD"][o0:o1, j]); fm = np.isfinite(fd) & z['live'][a0:a1 + 1, k]
    print(f"{nm:7s} hourly-C common bars {m.sum():6d} max rel diff {rel:.2e} | share of old-finite bars missing in PIT {(np.isfinite(oc)&~np.isfinite(pc)).mean():.4f} | FD max abs diff {(fd[fm].max() if fm.any() else 0):.2e}")
    if rel > 1e-5: bad.append(("C", nm, rel))
print("symbols compared", checked, "problems", bad)
mem = z["member"]; live = z["live"]
for y in (2020, 2021, 2022, 2023, 2024, 2025, 2026):
    a = int(pdays.searchsorted(pd.Timestamp(f"{y}-01-01", tz="UTC"))); b = min(int(pdays.searchsorted(pd.Timestamp(f"{y}-12-31", tz="UTC"))), len(pdays) - 1)
    cnt = mem[a:b + 1].sum(1)
    dead = [pn[j] for j in range(len(pn)) if mem[a:b + 1, j].any() and not live[b, j]]
    print(y, "members/day min/med/max", cnt.min(), int(np.median(cnt)), cnt.max(), "| members ever in year", int(mem[a:b+1].any(0).sum()), "| of which not live at year end (dead/delisted/renamed)", len(dead))
S = RS.new(); st = LIB.first_active_day(S)
print("NEW: panel", S.P["C"].shape, S.P["C"].dtype, "first active", S.P["days"][st].date(), "last", S.P["days"][-1].date(), "active days", S.b - st, "windows", len(S.windows(st)))
print("NEW eligible (score finite) per day min/med/max after start:", np.isfinite(S.sc[st:]).sum(1).min(), int(np.median(np.isfinite(S.sc[st:]).sum(1))), np.isfinite(S.sc[st:]).sum(1).max())
dead_new = [S.P["names"][j] for j in range(S.n) if not np.isfinite(S.P["C"][-1, 23, j])]
print("NEW columns", S.n, "| columns with no bar at 2021-12-31 (dead/not yet listed):", len(dead_new), dead_new[:40])
S2 = RS.old_pit(); print("OLD-PIT cols", S2.n, "windows", len(S2.windows(LIB.first_active_day(S2))), "last", S2.P["days"][-1].date())
assert not [b for b in bad if b[0] != "missing"]
print("PASS data")
