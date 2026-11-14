"""Synthetic checks for bt2 (no real v2 data read). Builds a fake 40-name panel in /tmp, uses real v1 069500 only for the calendar."""
import sys
from pathlib import Path
sys.path.insert(0, "/app/kr")
import numpy as np, pandas as pd
import bt2

SYN = Path("/tmp/syn"); (SYN / "data").mkdir(parents=True, exist_ok=True)
idx = pd.read_parquet(bt2.V1 / "data" / "069500.parquet"); idx.index = idx.index.tz_convert(None).normalize()
cal = idx.index[(idx.index >= "2011-05-01") & (idx.index <= bt2.END)]
rng = np.random.RandomState(7)


def make(seed_shift=0, perturb_after=None):
    for k in range(40):
        r = np.random.RandomState(k).normal(0.0004, 0.02, len(cal))
        c = 10000 * np.cumprod(1 + r)
        o = np.r_[c[0], c[:-1]] * (1 + np.random.RandomState(100 + k).normal(0, 0.003, len(cal)))
        if perturb_after is not None:
            m = cal > perturb_after
            c = np.where(m, c * 1.7, c); o = np.where(m, o * 1.7, o)
        d = pd.DataFrame({"open": o, "high": np.maximum(o, c) * 1.01, "low": np.minimum(o, c) * 0.99, "close": c,
                          "volume": 1e6, "value": 5e9 + k * 1e8}, index=cal)
        if k == 3:                      # delisted 2016-06-30 after a -80% liquidation day
            d = d.loc[:"2016-06-30"].copy(); d.iloc[-1, d.columns.get_loc("close")] *= 0.2
        if k == 5:                      # halted (no rows) 2014-03..2014-09
            d = d.drop(d.loc["2014-03-01":"2014-09-30"].index)
        if k == 12:                     # volume spikes every 60 sessions (V8 must trade and hold 20 sessions)
            d.iloc[::60, d.columns.get_loc("volume")] = 5e6
        if k == 9:                      # unadjusted corporate action: x3 jump on a normal traded day
            d.iloc[1000:, :4] *= 3.0
        if k == 7:                      # locked limit-up day
            t = d.index[1500]; p = d["close"].iloc[1499] * 1.3
            d.loc[t, ["open", "high", "low", "close"]] = [p, p, p, p]
        d.to_parquet(SYN / "data" / ("%06d.parquet" % k))


make()
bt2.KR = SYN
P = bt2.load_panel(); F = bt2.feats(P)
assert P.delisted.sum() == 1 and P.last[3] < len(cal) - 1
assert not P.trad[1500, 7], "locked limit day must be untradable"
j9 = P.syms.index("000009")
assert abs(P.ret[1000, j9]) < 1e-6, ("corporate-action jump must be repaired", P.ret[1000, j9])
assert any(s == "000009" for s, _ in bt2.REPAIRS) and not any(s == "000003" for s, _ in bt2.REPAIRS)
assert not P.elig[cal.get_loc(pd.Timestamp("2014-06-02")), 5], "halted name must be ineligible"
# 1) single-asset buy & hold equals price ratio net of buy cost (no tax until sold)
sig = {P.t0 - 1: {10: 1.0}}
nav, ex = bt2.simulate(P, sig)
slip = bt2.slip_of(P.med60[P.t0 - 1, 10])
exp = (1 / (1 + slip + bt2.COMM)) * P.c[-1, 10] / P.o[P.t0, 10]
assert abs(nav["nav"].iloc[-1] - exp) < 1e-6, (nav["nav"].iloc[-1], exp)
# 2) holding the delisted name: closed at its LAST close (including the -80% day) minus sell costs, then flat
sig = {P.t0 - 1: {3: 1.0}}
nav, ex = bt2.simulate(P, sig)
s3 = bt2.slip_of(P.med60[P.t0 - 1, 3]); s3e = bt2.slip_of(P.med60[P.last[3], 3])
exp = (1 / (1 + s3 + bt2.COMM)) * P.c[P.last[3], 3] / P.o[P.t0, 3] * (1 - s3e - bt2.COMM - bt2.TAX)
assert abs(nav["nav"].iloc[-1] - exp) < 1e-6, (nav["nav"].iloc[-1], exp)
assert nav["expo"].iloc[-1] == 0
# 3) every strategy runs, and NO look-ahead: perturb prices after a cut -> identical NAV up to the cut
s8, _ = bt2.sig_v8(P, F)
ev = sorted((t, a, w) for t, ch in s8.items() for a, w in ch.items())
ent = [t for t, a, w in ev if w > 0]; exi = [t for t, a, w in ev if w == 0]
assert len(ent) > 20 and all(a == P.syms.index("000012") for _, a, _ in ev), "V8 should only fire on the spiking name"
assert all(x - e == 20 for e, x in zip(ent, exi)), "V8 must exit exactly 20 sessions after the signal"
cut = pd.Timestamp("2018-06-29")
T = bt2.trials_build(P, F); T["B4"] = (bt2.sig_ew(P), "full")
base = {k: bt2.simulate(P, s, mode=m)[0] for k, (s, m) in T.items()}
make(perturb_after=cut)
P2 = bt2.load_panel(); F2 = bt2.feats(P2)
T2 = bt2.trials_build(P2, F2); T2["B4"] = (bt2.sig_ew(P2), "full")
for k, (s, m) in T2.items():
    n2 = bt2.simulate(P2, s, mode=m)[0]
    a, b = base[k]["nav"].loc[:cut], n2["nav"].loc[:cut]
    assert np.allclose(a.values, b.values), k
    print("ok", k, "trades", len(bt2.simulate(P, T[k][0], mode=T[k][1])[1]["trades"]))
print("all bt2 synthetic checks passed")
