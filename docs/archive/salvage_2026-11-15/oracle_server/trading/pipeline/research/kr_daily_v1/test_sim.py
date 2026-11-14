"""Synthetic checks of bt.simulate (no real data)."""
import sys
sys.path.insert(0, "/app/kr")
import numpy as np, pandas as pd
import bt

cal = pd.bdate_range("2011-01-03", "2013-12-31")
rng = np.random.RandomState(1)
C = pd.DataFrame({"069500": 100 * np.cumprod(1 + rng.normal(0.0003, 0.01, len(cal))),
                  "005930": 50 * np.cumprod(1 + rng.normal(0.0003, 0.02, len(cal)))}, index=cal)
O = C.shift(1).mul(1 + rng.normal(0, 0.003, len(cal)), axis=0)
O.iloc[0] = C.iloc[0]
cm = {"069500": (0.001, 0.001), "005930": (0.001, 0.003)}
# 1) buy & hold
tg = pd.DataFrame({"069500": [1.0]}, index=[cal[0]])
nav, ex = bt.simulate(tg, O, C, cm, start="2012-06-01")
d0 = cal[cal < "2012-06-01"][-1]; d1 = cal[cal > d0][0]
exp = (1 / 1.001) * C["069500"].iloc[-1] / O.loc[d1, "069500"]
assert abs(nav["nav"].iloc[-1] - exp) < 1e-9, (nav["nav"].iloc[-1], exp)
# 2) round trip: enter on decision day X, exit on decision day Y -> nav = (1/(1+b)) * O[Y+1]/O[X+1] * (1-s)
X, Y = cal[400], cal[450]
tg = pd.DataFrame({"005930": [1.0, 0.0]}, index=[X, Y])
nav, ex = bt.simulate(tg, O, C, cm, start="2012-06-01")
nx, ny = cal[cal.get_loc(X) + 1], cal[cal.get_loc(Y) + 1]
exp = (1 / 1.001) * O.loc[ny, "005930"] / O.loc[nx, "005930"] * (1 - 0.003)
assert abs(nav["nav"].iloc[-1] - exp) < 1e-9, (nav["nav"].iloc[-1], exp)
assert len(ex["trades"]) == 1 and abs(ex["trades"][0] - (exp - 1)) < 1e-9, ex["trades"]
# 3) no look-ahead: perturbing prices AFTER day k must not change nav up to day k
k = cal[500]
C2, O2 = C.copy(), O.copy(); C2.loc[cal > k] *= 1.5; O2.loc[cal > k] *= 1.5
tg = bt.sig_t1(C.rename(columns={})) if False else pd.DataFrame({"069500": (C["069500"] > C["069500"].rolling(50).mean()).astype(float)})
n1, _ = bt.simulate(tg, O, C, cm, start="2012-06-01")
tg2 = pd.DataFrame({"069500": (C2["069500"] > C2["069500"].rolling(50).mean()).astype(float)})
n2, _ = bt.simulate(tg2, O2, C2, cm, start="2012-06-01")
assert np.allclose(n1.loc[:k, "nav"], n2.loc[:k, "nav"])
# 4) signal-level look-ahead for every pre-registered signal on synthetic panel
for f in (bt.sig_t1, bt.sig_t2, bt.sig_t3, bt.sig_t4):
    a, b = f(C), f(C2)
    assert a.loc[:k].equals(b.loc[:k]), f.__name__
print("all simulator checks passed")
