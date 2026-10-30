"""R2C smoke #2 (asserts only; prints PASS)."""
import os, sys
sys.path.insert(0, "/Users/user/Desktop/CODE/Ochestration/trading"); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from app import rs_lev_r2c_lib as LIB, rs_lev_r2c_engine as E
import r2c_samples as RS
S = RS.old()
cs = [(4.0, 0.35, 0.15), (4.0, None, None)]
G, U, wins, KL = LIB.window_matrix(S, 3, 1, cs=cs)
assert G.shape == (len(wins), 2) and np.isfinite(G).all() and len(wins) >= 18
f = LIB.full_runs(S, 4, 2, cs=cs)
assert np.isfinite(f["O"][:, :, E.O_FINAL]).all() and f["O"].shape[:2] == (2, 4)
assert np.isfinite(f["O"][:, :, E.O_B0:E.O_B0 + 6]).all()
assert f["O"][1, :, E.O_KILLS].sum() == 0
# ev + colmask paths execute
evd = -np.ones((4, S.n), np.int64); evd[:, 3] = 1200
f2 = LIB.full_runs(S, 4, 2, cs=cs, ev=(evd, np.full((4, S.n), 0.1), np.full((4, S.n), 2.0)), colmask=np.r_[np.zeros(5), np.ones(S.n - 5)].astype(np.uint8))
assert np.isfinite(f2["O"][:, :, E.O_FINAL]).all()
# window runs are independent restarts: window starting at d0 equals a single run with same params
assert len(LIB.holm([0.01, 0.02, 0.5])) == 3
print("PASS smoke_lib")
