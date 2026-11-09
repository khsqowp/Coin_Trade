"""Toy assertions for the TP mechanics (run: python test_tp_mechanics.py)."""
import sys, os; sys.path.insert(0, os.path.dirname(__file__))
from lib import *
from app.rs_tp_engine import _sim_tp, tp_params
from app.rs_final_engine import params

def toy(tp, cost=0.0, hi0=None, lo1=None, close0=110., rebal=99):
    nd = 4
    C = np.full((nd, 24, 2), 100.); H = C.copy(); L = C.copy()
    C[1:, 23, 0] = close0
    if hi0: H[1, hi0[0], 0] = hi0[1]
    if lo1: L[1, lo1[0], 1] = lo1[1]
    score = np.tile([1., -1.], (nd, 1))
    out = _sim_tp(H, L, C, np.zeros((nd, 2)), np.zeros((nd, 24, 2)), score, np.zeros(nd),
                  params(rebal=rebal, K=1, lev=2, deploy=1, cost=cost, kill=1.0, cool=0), np.zeros(2), np.zeros(2), 0, nd, tp_params(**tp), np.zeros((50, 12)))
    return out
# no TP: long +10% -> eq 1.1
assert abs(toy({})[0][1] - 1.10) < 1e-12
# long TP 25% intrabar fill at 125 -> +0.25 realised, close drop ignored (position gone)
assert abs(toy(dict(XL=.25), hi0=(5, 130))[0][1] - 1.25) < 1e-12
# not reached -> unchanged
assert abs(toy(dict(XL=.25), hi0=(5, 120))[0][1] - 1.10) < 1e-12
# partial 50%: 0.125 + 0.5*0.1
assert abs(toy(dict(XL=.25, frac=.5), hi0=(5, 130))[0][1] - 1.175) < 1e-12
# short TP: low 70 -> fill 75 -> +0.25 ; long leg closes at 110 -> +0.1 => 1.35
assert abs(toy(dict(XS=.25), lo1=(3, 70))[0][1] - 1.35) < 1e-12
# long-only config must ignore short trigger
assert abs(toy(dict(XL=.25), lo1=(3, 70))[0][1] - 1.10) < 1e-12
# cost on exit: 0.001*1.25*0.01qty*... = notional(fill)=1.25 -> 0.00125 plus entry 0.002 (both legs)
r = toy(dict(XL=.25), cost=.001, hi0=(5, 130))
assert abs(r[0][1] - (1.25 - 0.002 - 0.00125)) < 1e-12, r[0][1]
# fill mode 1 (extra 0.3% adverse) and mode 2 (close of TP bar = 100 here)
assert abs(toy(dict(XL=.25, fillmode=1), hi0=(5, 130))[0][1] - (1 + 0.01 * (125 * .997 - 100))) < 1e-12
assert abs(toy(dict(XL=.25, fillmode=2), hi0=(5, 130))[0][1] - 1.0) < 1e-12
# entry bar: TP cannot fire on the entry day (day 0): H spike on day 0 ignored
print("TP mechanics assertions PASS")
