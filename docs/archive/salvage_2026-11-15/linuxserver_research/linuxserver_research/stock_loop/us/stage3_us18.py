"""US-18 Stage 3 (holdout). ONE unlock for ONE frozen candidate set. Spec: spec/US-18/stage3_prereg.md"""
import json, sys, time
from .common import *  # noqa
from .hyp import Ctx
from .stage2_us18 import build

CAND = dict(rsi=5, lb=126, frac=0.25)
K = 100


class World:
    def __init__(self, P):
        self.P = P
        c = Ctx(P, None)
        self.elig, self.sma, self.avgvol, self.f = c.elig, c.sma, c.avgvol, c.f


def main():
    out = ROOT / "results" / "US-18" / "stage3.json"
    if out.exists() and "--force" not in sys.argv:
        sys.exit("stage3 already run; holdout look is single")
    resources_ok()
    t0 = time.time()
    # dev reproduction (before unlock)
    Pdev = data.load_panel("us")
    Wd = World(Pdev)
    evd = build(Wd, K, **CAND)
    print("dev reproduction n", len(evd), "mean %.4f%%" % (100 * evd.net.mean()), flush=True)
    del Pdev, Wd
    line = splits.unlock_holdout("US-18-T100 rsi5 lb126 frac0.25 Stage 3 single look (Stage 2 cleared: plateau, WF t=3.91, BH q<0.01)")
    print(line, flush=True)
    P = data.load_panel("us", include_holdout=True)
    print("panel with holdout", P.close.shape, P.dates[0].date(), P.dates[-1].date(), flush=True)
    W = World(P)
    ev = build(W, K, **CAND)
    hs = splits.HOLDOUT_START
    dev = ev.subset(ev.dates < hs - pd.Timedelta(days=0))
    dev = dev.subset(dev.xdates < hs)
    hold = ev.subset(ev.dates >= hs)
    print("dev events (full-history features) n", len(dev), "mean %.4f%%" % (100 * dev.net.mean()), "holdout events", len(hold), flush=True)
    split = pd.Timestamp("2017-07-01")
    res = dict(candidate=CAND, universe=K, dev_n=len(dev), dev_mean=float(dev.net.mean()), holdout_n=len(hold))
    yrs_dev = pd.Series(dev.net).groupby(dev.dates.year).mean()
    res["dev_years_pos"] = float((yrs_dev > 0).mean())
    res["dev_year_means"] = {int(k): float(v) for k, v in yrs_dev.items()}
    m, t = es.cluster_t(hold.net, hold.dates.asi8)
    _, tb = block_t(hold)
    res.update(hold_mean=m, hold_t=t, hold_block_t=tb, hold_gross=float(hold.gross.mean()), hold_hit=float((hold.net > 0).mean()),
               hold_worst=float(hold.net.min()), hold_best=float(hold.net.max()))
    h2 = es.summarize(hold.with_cost(hold.cost * 2))
    res["hold_mean_2x"], res["hold_t_2x"] = h2["mean"], h2["t"]
    for N in (5, 10):
        pr = pf.simulate(hold, P.dates, N=N, capital=1.3e6, cost_model=COST)
        res[f"N{N}"] = dict(sharpe=pr["sharpe"], ann=pr["ann"], maxdd=pr["maxdd"], n=pr["n"], worst=pr["worst"], max_conc=pr["max_conc"], trades_month=pr["trades_month"])
        if N == 10:
            d = pr["daily"]
            res["N10"]["daily_days"] = int(len(d))
            res["N10"]["total_return"] = float(d.sum())
    # baseline
    s5 = W.sma(5)
    el = W.elig(K)
    ev_all = var_exit_events(P, el, 5, lambda ti, ci, kk: P.close[ti + kk, ci] > s5[ti + kk, ci], el)
    netm = np.full(P.close.shape, np.nan)
    netm[ev_all.ti, ev_all.ci] = ev_all.net
    res["baseline"] = bl.random_entry_baseline(netm, el, hold.ti, float(hold.net.mean()), draws=2000, seed=21)
    yh = pd.Series(hold.net).groupby(hold.dates.year).agg(["mean", "count"])
    res["hold_year"] = {int(k): dict(mean=float(v["mean"]), n=int(v["count"])) for k, v in yh.iterrows()}
    crit = {
        "1_sharpe_N10>=1.0": bool(res["N10"]["sharpe"] >= 1.0),
        "2_baseline>=0.95": bool(res["baseline"]["pct"] >= 0.95),
        "3_dev_years_pos>=0.7": bool(res["dev_years_pos"] >= 0.7),
        "4_2x_cost_mean>0": bool(res["hold_mean_2x"] > 0),
        "5_n>=200": bool(len(hold) >= 200),
        "6_maxconc<=10": bool(res["N10"]["max_conc"] <= 10),
    }
    res["criteria"] = crit
    res["PASS"] = bool(all(crit.values()))
    save_trades(hold, P, ROOT / "results" / "US-18" / "holdout_trades_US-18-T100.parquet")
    report.dump_json(res, out)
    print(json.dumps({k: v for k, v in res.items() if k not in ("dev_year_means",)}, indent=1, default=str))
    print("done %.0fs" % (time.time() - t0))


if __name__ == "__main__":
    main()
