"""US-18-T100 strict robustness after Stage 3 PASS. Diagnostics only; nothing is selected on these numbers.
Holdout is unlocked again (logged) because breadth variants need new events; candidate params are NOT changed."""
import json, sys, time
from .common import *  # noqa
from .stage2_us18 import build
from .stage3_us18 import World, CAND

HS = splits.HOLDOUT_START


def split_stats(ev, P, N=10):
    out = {}
    for name, e in (("dev", ev.subset((ev.dates < HS) & (ev.xdates < HS))), ("hold", ev.subset(ev.dates >= HS))):
        if len(e) == 0:
            out[name] = dict(n=0); continue
        m, t = es.cluster_t(e.net, e.dates.asi8)
        m2, t2 = es.cluster_t(e.net - e.cost, e.dates.asi8)           # 2x cost
        m3 = float((e.net - 2 * e.cost).mean())                       # 3x cost
        pr = pf.simulate(e, P.dates, N=N, capital=1.3e6, cost_model=COST)
        out[name] = dict(n=len(e), mean=m, t=t, gross=float(e.gross.mean()), median=float(np.median(e.net)), mean_2x=m2, t_2x=t2, mean_3x=m3,
                         sharpe_N10=pr["sharpe"], maxdd_N10=pr["maxdd"], worst=float(e.net.min()),
                         years_pos=float((pd.Series(e.net).groupby(e.dates.year).mean() > 0).mean()))
    return out


def main():
    out = ROOT / "results" / "US-18" / "robustness.json"
    if out.exists() and "--force" not in sys.argv:
        sys.exit("exists")
    resources_ok()
    t0 = time.time()
    line = splits.unlock_holdout("US-18-T100 robustness diagnostics for a Stage-3-passed candidate (breadth/outliers/next-open entry); no re-selection")
    print(line, flush=True)
    P = data.load_panel("us", include_holdout=True)
    W = World(P)
    res = {}
    base = build(W, 100, **CAND)
    res["breadth"] = {}
    for K in (30, 50, 100, 200, 400):
        ev = build(W, K, **CAND)
        res["breadth"][f"T{K}"] = split_stats(ev, P)
        b = res["breadth"][f"T{K}"]
        print(f"T{K}", {k: (round(v["mean"] * 100, 3), round(v["t"], 2), v["n"], round(v["sharpe_N10"], 2)) for k, v in b.items() if v["n"]}, flush=True)
    # year by year, full sample, T100
    y = pd.DataFrame({"y": base.dates.year, "net": base.net}).groupby("y").net.agg(["mean", "count", "median"])
    res["year_by_year"] = {int(k): dict(mean=float(r["mean"]), n=int(r["count"]), median=float(r["median"])) for k, r in y.iterrows()}
    # outliers / concentration (holdout, T100)
    h = base.subset(base.dates >= HS)
    nets = np.sort(h.net)[::-1]
    res["hold_outliers"] = dict(mean=float(h.net.mean()), median=float(np.median(h.net)), mean_ex_top5=float(nets[5:].mean()), mean_ex_top10pct=float(nets[int(0.1 * len(nets)):].mean()),
                                top5=[float(x) for x in nets[:5]], trimmed_mean_5pct=float(np.sort(h.net)[int(.05 * len(nets)):int(.95 * len(nets))].mean()))
    syms = np.array(P.codes, dtype=object)[h.ci]
    s = pd.Series(h.net, index=syms).groupby(level=0).agg(["sum", "count"]).sort_values("sum", ascending=False)
    res["hold_symbol_concentration"] = dict(n_symbols=int(len(s)), top5_share_of_total=float(s["sum"].head(5).sum() / s["sum"].sum()), top5=s.head(5).to_dict("index"))
    a = (h.dates >= "2025-03-25") & (h.dates <= "2025-05-15")
    res["hold_ex_apr2025_window"] = dict(n=int((~a).sum()), mean=float(h.net[~a].mean()), t=es.cluster_t(h.net[~a], h.dates[~a].asi8)[1], n_in_window=int(a.sum()), mean_in_window=float(h.net[a].mean()))
    # dev same diagnostics
    d = base.subset((base.dates < HS) & (base.xdates < HS))
    dn = np.sort(d.net)[::-1]
    res["dev_outliers"] = dict(mean=float(d.net.mean()), median=float(np.median(d.net)), mean_ex_top5pct=float(dn[int(.05 * len(dn)):].mean()))
    # next-open entry variant (realism: signal uses the close; Korean-time user cannot trade the exact close)
    ti, ci = base.ti, base.ci
    xi = (base.x_slot - 1) // 2
    entry = P.open[ti + 1, ci]
    ex = P.close[xi, ci]
    g = ex / entry - 1
    ok = np.isfinite(g) & (xi >= ti + 1)
    nb = base.subset(ok)
    nb = es.Events(nb.ti, nb.ci, 2 * nb.ti + 2, nb.x_slot, g[ok], nb.cost, nb.dates, nb.xdates)
    res["next_open_entry"] = split_stats(nb, P)
    print("next-open", {k: (round(v["mean"] * 100, 3), round(v["t"], 2), v["n"]) for k, v in res["next_open_entry"].items()})
    print(json.dumps({k: res[k] for k in ("hold_outliers", "hold_symbol_concentration", "hold_ex_apr2025_window", "dev_outliers", "year_by_year")}, indent=1, default=str))
    report.dump_json(res, out)
    print("done %.0fs" % (time.time() - t0))


if __name__ == "__main__":
    main()
