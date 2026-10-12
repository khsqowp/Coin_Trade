"""Decompose the BTC-drawdown reversal-sleeve design: episodes, phase sensitivity (research only)."""
import numpy as np, pandas as pd
import app.rs_regime_extra as X
from app.rs_regime_lib import Engine, load_cache
c, E = X.c, X.E
btc = c["BTC"]; m14 = btc.pct_change(14)
flag = (m14 < -0.1).fillna(False)
idx = c.index
earn_day = flag.shift(1, fill_value=False)  # weights set at t earn on t+1: flag day is t
def ep_table(K=12, R=2, thr=-0.1):
    wm = E.book(14, K, R)[0]; wr = -E.book(5, K, R)[0]
    fl = (m14 < thr).fillna(False).to_numpy()
    mom = X.finish(wm)["daily"]["net"]; rev = X.finish(wr)["daily"]["net"]
    ix = mom.index
    f = pd.Series(fl, index=c.index).shift(1, fill_value=False).reindex(ix)  # state that decided the weights earning today
    ep = (f != f.shift()).cumsum()
    t = pd.DataFrame({"mom": mom, "rev": rev, "f": f, "ep": ep})
    t = t[t.f]
    g = t.groupby("ep").agg(start=("mom", lambda s: s.index[0].date()), days=("mom", "size"),
                            mom=("mom", lambda s: (1 + s).prod() - 1), rev=("rev", lambda s: (1 + s).prod() - 1))
    return g
for K, R in ((12, 2), (12, 3)):
    g = ep_table(K, R)
    print(f"--- episodes K={K} R={R}: n={len(g)} flagged days={g.days.sum()} ; rev beats mom in {(g.rev>g.mom).mean():.0%}; "
          f"sum mom={g.mom.sum():+.2f} sum rev={g.rev.sum():+.2f}; median days {g.days.median()}")
    print(g.round(3).to_string())
print("--- phase sensitivity: start offset days (rev5 @ btc_mom14<-0.1) vs base")
for K in (12, 8):
    for R in (2, 3, 4, 5):
        out = []
        for off in range(R):
            st = (pd.Timestamp("2022-01-01") + pd.Timedelta(days=off)).strftime("%Y-%m-%d")
            e = Engine(c, X.f, start=st)
            fb = X.finish.__globals__  # noqa
            x = m14.to_numpy(); fl = np.isfinite(x) & (x < -0.1)
            wb = e.book(14, K, R)[0]; wr = -e.book(5, K, R)[0]
            def fin(w):
                delta = np.abs(np.diff(w, axis=0, prepend=np.zeros((1, w.shape[1])))).sum(axis=1)
                earned = np.vstack([np.zeros((1, w.shape[1])), w[:-1]]); to = np.r_[0, delta[:-1]]
                net = (earned * e.ret).sum(1) - to * 0.001 - (earned * e.funding.to_numpy()).sum(1)
                s = pd.Series(net, index=c.index).loc["2022-01-04":]
                eq = (1 + s).cumprod(); y = len(s) / 365
                return eq.iloc[-1] ** (1 / y) - 1, (1 - eq / eq.cummax().clip(lower=1)).max()
            b = fin(wb); r = fin(np.where(fl[:, None], wr, wb))
            out.append(f"off{off}: base {b[0]*100:.0f}/{b[1]*100:.0f}  rev {r[0]*100:.0f}/{r[1]*100:.0f}")
        print(f"K={K} R={R}: " + " ; ".join(out))
