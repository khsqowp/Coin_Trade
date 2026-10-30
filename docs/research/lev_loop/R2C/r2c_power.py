"""R2C POWER STAGE (pre-results). Prints ONLY dispersion quantities (SE, MDE, counts, unique trajectories). No means/point estimates are printed or stored."""
import os, sys, time
sys.path.insert(0, "/Users/user/Desktop/CODE/Ochestration/trading"); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from app import rs_lev_r2c_lib as LIB, rs_lev_r2c_engine as E
import r2c_samples as RS
cs = LIB.combos(); idx = {c: i for i, c in enumerate(cs)}
CAND = [(lev, k) for lev in (3.5, 4.0, 5.0) for k in LIB.KILLS if (lev, k) != LIB.BASE]
def col(lev, k, lam):
    return idx[(lev, k, None)] if k is None else idx[(lev, k, lam)]
def unit_returns(S):
    st = LIB.first_active_day(S); R = 1
    jc = np.zeros((1, E.MAXK), np.int64); jp = np.zeros((1, E.MAXK), np.int64)
    O, KD, EQ, PS = LIB.run_grid(S, [(1.0 / LIB.DEP, None, None)], np.array([st]), np.array([S.b]), np.array([0]), jc, jp, want_eq=True)
    x = EQ[0, 0, st:S.b]; x = x[np.isfinite(x)]
    return np.diff(x) / x[:-1], len(x)
out = {}
for name in ("OLD", "NEW"):
    t0 = time.time(); S = getattr(RS, name.lower())()
    st = LIB.first_active_day(S); days = S.b - st
    print(f"\n=== {name}: active days {days} ({days/365:.2f} y), first active {S.P['days'][st].date()} .. {S.P['days'][S.b-1].date()}, columns {S.n}")
    r, nu = unit_returns(S)
    pairs = [(3.8, 4.75), (3.8, 3.325), (3.325, 4.75), (2.85, 3.8)]
    se = LIB.block_boot_unit(r, pairs)
    print(f"[A] ideal fixed-fraction (kill-free unit series, 15d blocks, {len(r)} days, ~{len(r)//15} blocks): daily-return vol(ann) {r.std()*np.sqrt(365):.3f}")
    for (a, b), v in se.items():
        print(f"    g(G={b})-g(G={a}): SE {v:.3f}  MDE(80%/5%) {2.8*v:.2f}/yr")
    G, U, wins, KL = LIB.window_matrix(S, 24, 20261101 + (0 if name == "OLD" else 1))
    nw = len(wins); print(f"[B] windows: {nw} x {LIB.WIN}d (R=24 reps each); mean unique finals per window per rep-set: base {U[:, idx[(4.0,0.35,0.15)]].mean():.1f}/24, none-kill 4x {U[:, idx[(4.0,None,None)]].mean():.1f}/24")
    full = LIB.full_runs(S, 48, 20261105 + (0 if name == "OLD" else 1))
    uq = LIB.unique_traj(full["O"]); ep = LIB.kill_epochs(full["KD"])
    print(f"    full-sample unique finals /48: base(4,.35,l.15) {uq[idx[(4.0,0.35,0.15)]]}  (4,.35,l0) {uq[idx[(4.0,0.35,0.0)]]}  (4,none) {uq[idx[(4.0,None,None)]]}  (5,none) {uq[idx[(5.0,None,None)]]}")
    print(f"    kill epochs (7d-merged distinct kill dates across 48 reps) base l.15: {ep[idx[(4.0,0.35,0.15)]]}  mean kills/path {full['O'][idx[(4.0,0.35,0.15)],:,E.O_KILLS].mean():.1f}")
    print("[C] candidate contrasts vs base (same lambda): window-level SE, MDE_t, target delta, MDE/delta, years needed for MDE_t<=delta (same design)")
    print("    cell(lev,kill) lam | n | SE    MDE_t  delta  ratio  Y_req(y)")
    for (lev, k) in CAND:
        for lam in (0.15, 0.3):
            d = G[:, col(lev, k, lam)] - G[:, col(4.0, 0.35, lam)]
            ts = LIB.t_stats(d); delta = LIB.delta_for((lev, k)); ratio = ts["mde"] / delta
            yreq = (days / 365.0) * ratio ** 2
            print(f"    ({lev},{k}) {lam:4.2f} | {nw} | {ts['se']:.3f} {ts['mde']:.3f} {delta:.2f} {ratio:6.1f} {yreq:8.0f}")
            out[(name, lev, k, lam)] = (ts["se"], ts["mde"], delta)
    print(f"    [{name} done in {time.time()-t0:.0f}s]", flush=True)
