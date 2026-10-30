"""REVIEWER independent re-implementation of V0 (daily-close kill) + hourly cross-margin liquidation checks.
Written from the documented semantics (not importing any rs_* engine), only reading the saved panel npz.
Pure numpy, no numba."""
import numpy as np, pandas as pd, os

SCR = os.environ["RS_FINAL_SCRATCH"]
Z = np.load(os.path.join(SCR, "rs_final_panel.npz"), allow_pickle=True)
NAMES = [str(x) for x in Z["names"]]
DAYS = pd.DatetimeIndex(Z["days"], tz="UTC")
H, L, C, FD = Z["H"], Z["L"], Z["C"], Z["FD"]
ND, _, N = C.shape
CL = C[:, 23, :]

def btc_crash():
    b = CL[:, NAMES.index("BTC")]
    r = np.full(ND, np.nan); r[14:] = b[14:] / b[:-14] - 1
    return np.isfinite(r) & (r < -0.10)

CRASH = btc_crash()

def scores(cols):
    s = np.full((ND, N), np.nan)
    m = np.full((ND, len(cols)), np.nan)
    sub = CL[:, cols]
    m[14:] = sub[14:] / sub[:-14] - 1
    s[:, cols] = m
    return s  # raw 14d return (rank-equivalent to the z-score)

def run(cols=None, lev=4.0, dep=0.95, phase=0, kill=0.35, cool=14, cost=0.001, d0=None, d1=None, record=False, K=8, rebal=3):
    cols = list(range(N)) if cols is None else list(cols)
    sc = scores(cols)
    d0 = int(DAYS.searchsorted(pd.Timestamp("2022-01-01", tz="UTC"))) if d0 is None else d0
    d1 = ND if d1 is None else d1
    q = np.zeros(N); e = np.zeros(N); W = 1.0; hwm = 1.0
    halted = False; halt_day = -1; last_reb = -10**9; prev_flag = False
    kills = 0; eqs = np.full(ND, np.nan); rec = {}
    for i in range(d0, d1):
        held = np.any(q != 0)
        if held:
            fund = -np.sum(np.where(q != 0, q * np.nan_to_num(FD[i]), 0.0))
            W += fund
            if record:
                rec[i] = (q.copy(), e.copy(), W)
            # legacy-style daily check (reproduce V0 liq condition 0.5% of day-max-high notional)
            adv = np.where(q > 0, L[i], H[i])                       # 24 x N
            pnl_h = np.nansum(np.where(q != 0, q * (adv - e), 0.0), axis=1)
            worst = W + pnl_h.min()
            mx = np.nanmax(np.where(np.isfinite(H[i]), H[i], 0.0), axis=0)
            maint = np.sum(np.abs(q) * np.maximum(mx, e) * 0.005 * (q != 0))
            if worst <= maint:
                return dict(liq=True, day=i, eq=eqs, kills=kills, rec=rec)
        px = np.where(np.isfinite(CL[i]), CL[i], np.where(e > 0, e, np.nan))
        eq = W + np.nansum(np.where(q != 0, q * (px - e), 0.0))
        eqs[i] = eq
        hwm = max(hwm, eq)
        dd = 1 - eq / hwm
        if (not halted) and dd >= kill:
            W += np.nansum(np.where(q != 0, q * (px - e), 0.0)) - np.sum(np.where(q != 0, np.abs(q) * px * cost, 0.0))
            q[:] = 0; e[:] = 0; halted = True; halt_day = i; kills += 1
            continue
        if halted:
            if cool > 0 and i - halt_day >= cool:
                halted = False; hwm = eq; last_reb = -10**9
            else:
                continue
        flag = bool(CRASH[i]); force = flag != prev_flag; prev_flag = flag
        due = (i >= d0 + phase) and (i - last_reb >= rebal)
        if not (due or force) or i >= d1 - 1:
            continue
        ok = np.isfinite(sc[i]); cnt = ok.sum()
        side = np.zeros(N)
        if cnt >= 2 * K and not flag:
            idx = np.where(ok)[0]
            order = idx[np.argsort(-sc[i, idx], kind="stable")]
            side[order[:K]] = 1.0
            for j in order[::-1]:
                if (side == -1).sum() >= K: break
                if side[j] == 0: side[j] = -1.0
        elif cnt < 2 * K and not flag:
            continue
        tgt = eq * dep * lev / (2.0 * K)
        c_ = 0.0
        for j in range(N):
            s = side[j]; cs = np.sign(q[j])
            if q[j] != 0 and s == cs:
                continue
            if q[j] != 0:
                W += q[j] * (px[j] - e[j]); c_ += abs(q[j]) * px[j] * cost; q[j] = 0; e[j] = 0
            if s != 0 and np.isfinite(px[j]) and px[j] > 0:
                qty = tgt / px[j]
                q[j] = s * qty; e[j] = px[j]; c_ += qty * px[j] * cost
        W -= c_
        if due: last_reb = i
    return dict(liq=False, day=None, eq=eqs, kills=kills, rec=rec, q=q, e=e, W=W)

if __name__ == "__main__":
    for ph in range(3):
        r = run(phase=ph)
        print("phase", ph, "final", round(float(r["eq"][~np.isnan(r["eq"])][-1]), 4), "kills", r["kills"], "liq", r["liq"])
