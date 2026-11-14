"""Survivorship / selection-bias sensitivity for US-18-T100 (diagnostic only; params frozen). Logged holdout unlock."""
import json, sys, time
from .common import *  # noqa
from .stage2_us18 import build
from .stage3_us18 import World, CAND

HS = splits.HOLDOUT_START


class FrozenWorld(World):
    """Universe frozen at a past date: top-K by value20 on `asof` (known then), constant afterwards; optional min-history filter."""
    def __init__(self, P, asof, K=100, min_hist=None):
        super().__init__(P)
        i = int(np.searchsorted(P.dates, pd.Timestamp(asof), side="right") - 1)
        v = np.nan_to_num(P.value20[i], nan=-1.0)
        top = np.zeros(P.close.shape[1], bool)
        top[np.argsort(-v)[:K]] = True
        m = np.broadcast_to(top[None, :], P.close.shape).copy()
        if min_hist:
            hist = np.cumsum(np.isfinite(P.close), axis=0)
            m &= hist >= min_hist
        self._m = m
        self.frozen_syms = [P.codes[j] for j in np.nonzero(top)[0]]
        self.elig = lambda k, lag=0: self._m


def stats(ev, P):
    out = {}
    for name, e in (("dev", ev.subset((ev.dates < HS) & (ev.xdates < HS))), ("hold", ev.subset(ev.dates >= HS))):
        if len(e) < 5:
            out[name] = dict(n=len(e)); continue
        m, t = es.cluster_t(e.net, e.dates.asi8)
        pr = pf.simulate(e, P.dates, N=10, capital=1.3e6, cost_model=COST)
        out[name] = dict(n=len(e), mean=m, t=t, mean_2x=float((e.net - e.cost).mean()), sharpe_N10=pr["sharpe"], maxdd=pr["maxdd"], median=float(np.median(e.net)))
    return out


def main():
    out = ROOT / "results" / "US-18" / "survivorship.json"
    if out.exists() and "--force" not in sys.argv:
        sys.exit("exists")
    resources_ok()
    print(splits.unlock_holdout("US-18-T100 survivorship sensitivity diagnostic (frozen universes, min history); params frozen, no re-selection"), flush=True)
    P = data.load_panel("us", include_holdout=True)
    res = {}
    for label, asof, mh in (("frozen_2024-11-11", "2024-11-11", None), ("frozen_2024-11-11_hist750", "2024-11-11", 750),
                            ("frozen_2014-12-31", "2014-12-31", None), ("hist750_dynamic_top100", None, 750)):
        if asof is None:
            Wf = World(P)
            base_el = Wf.elig(100)
            hist = np.cumsum(np.isfinite(P.close), axis=0) >= mh
            Wf.elig = lambda k, lag=0, e=base_el & hist: e
            ev = build(Wf, 100, **CAND)
        else:
            Wf = FrozenWorld(P, asof, 100, mh)
            ev = build(Wf, 100, **CAND)
        s = stats(ev, P)
        res[label] = s
        f = lambda x: {k: (round(v * 100, 3) if k in ("mean", "mean_2x", "median", "maxdd") else (round(v, 2) if isinstance(v, float) else v)) for k, v in x.items()}
        print(label, "dev", f(s["dev"]), "hold", f(s["hold"]), flush=True)
    # holdout events by listing-age: names whose first valid bar is within 3y before event
    ev = build(World(P), 100, **CAND)
    first = np.argmax(np.isfinite(P.close), axis=0)
    age = ev.ti - first[ev.ci]
    h = ev.dates >= HS
    for lo, hi, nm in ((0, 750, "age<3y"), (750, 10 ** 6, "age>=3y")):
        m = h & (age >= lo) & (age < hi)
        res[f"hold_{nm}"] = dict(n=int(m.sum()), mean=float(ev.net[m].mean()) if m.any() else None)
        d = (~h) & (age >= lo) & (age < hi)
        res[f"dev_{nm}"] = dict(n=int(d.sum()), mean=float(ev.net[d].mean()) if d.any() else None)
    print({k: v for k, v in res.items() if k.startswith(("hold_age", "dev_age", "hold_age"))})
    report.dump_json(res, out)


if __name__ == "__main__":
    main()
