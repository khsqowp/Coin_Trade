"""R2C smoke: V0 replication asserts on the OLD sample (asserts only; prints PASS lines, no result series)."""
import os, sys
sys.path.insert(0, "/Users/user/Desktop/CODE/Ochestration/trading")
sys.path.insert(0, "/Users/user/Desktop/CODE/Ochestration/trading/docs/research/lev_loop/review")
import numpy as np
from app import rs_lev_r2c_engine as E, rs_lev_r2c_data as D
import indep_sim as s, lambda_kill as lk
P = D.load_old(); n = len(P["names"]); nd = len(P["days"])
sc = D.scores(P); cr = D.crash(P); r1 = D.r1_vec(P["names"])
d0 = D.day_index(P, "2022-01-01")
def mine(**kw):
    ph = kw.pop("phase", 0)
    par = E.make_par(phase=ph, d0=d0, d1=nd, **kw)[None, :]
    jc = np.zeros((1, E.MAXK), np.int64); jp = np.zeros((1, E.MAXK), np.int64)
    O, KD, EQ, PS = E.run_batch(P["H"], P["L"], P["C"], P["FD"], sc, cr, r1, np.ones((1, n), np.uint8), par, jc, jp,
                            -np.ones((1, n), np.int64), np.ones((1, n)), np.ones((1, n)), False)
    return O[0]
# 1) V0 daily-close kill .35 : 14.5027 / 18.4064 / 15.8459
for ph, ref in enumerate((14.5027, 18.4064, 15.8459)):
    o = mine(hourly=0, kill=0.35, phase=ph)
    assert abs(o[E.O_FINAL] - ref) < 6e-5, (ph, o[E.O_FINAL], ref)
    assert o[E.O_KILLS] in (9, 10), o[E.O_KILLS]
    r = s.run(phase=ph); assert abs(r["eq"][~np.isnan(r["eq"])][-1] - o[E.O_FINAL]) < 1e-9
print("PASS V0 daily-close (3 phases) vs published 14.5027/18.4064/15.8459 and indep_sim bit-level")
# 2) lambda hourly kill vs lambda_kill.py
for lam in (0.0, 0.3, 1.0):
    for ph in (0, 1):
        f, k = lk.run(lam, phase=ph)
        o = mine(hourly=1, lam=lam, kill=0.35, phase=ph)
        assert abs(o[E.O_FINAL] - f) < 1e-9 * max(1, abs(f)) and o[E.O_KILLS] == k, (lam, ph, o[E.O_FINAL], f, o[E.O_KILLS], k)
print("PASS lambda-kill (0,0.3,1.0 x phases 0,1) bit-level vs lambda_kill.py")
f, k = lk.run(0.0, phase=2, nokill=True)
o = mine(hourly=1, lam=0.0, kill=9.0, phase=2); assert abs(o[E.O_FINAL] - f) < 1e-9 * f and o[E.O_KILLS] == 0
print("PASS kill-none vs lambda_kill nokill")
print("settle events on old panel (must be 0):", mine(hourly=1, lam=0.15)[E.O_SETTLE])
assert mine(hourly=1, lam=0.15)[E.O_SETTLE] == 0
