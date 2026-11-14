"""US-18 Stage 2 (grid, plateau, walk-forward, baselines). DEV ONLY. Spec: spec/US-18/stage2_prereg.md"""
import itertools, json, sys, time
from .common import *  # noqa
from .hyp import lag
from .run_round import World, prev_ps

GRID = dict(rsi=[5, 10, 15], lb=[63, 126, 252], frac=[0.25, 1 / 3, 0.5])
DEF = dict(rsi=10, lb=126, frac=1 / 3)


def build(W, k, rsi, lb, frac, pool_only=False):
    """pool_only: momentum condition without RSI trigger (baseline pool b); returns bool mask."""
    P = W.P
    el = W.elig(k)
    rl = W.f(("ret", lb), lambda: P.close / lag(P.close, lb) - 1)
    ok = el & np.isfinite(rl)
    r = np.where(ok, -rl, np.inf)
    rank = np.argsort(np.argsort(r, axis=1, kind="stable"), axis=1)
    top = (rank < np.ceil(ok.sum(axis=1) * frac - 1e-9)[:, None]) & ok
    if pool_only:
        return top
    rsi_ = W.f("rsi2", lambda: F.rsi(P.close, 2))
    s5 = W.sma(5)
    mask = top & (rsi_ < rsi)

    def cond(ti, ci, kk):
        return P.close[ti + kk, ci] > s5[ti + kk, ci]
    return var_exit_events(P, mask, 5, cond, el)


def cell_key(p):
    return f"rsi{p['rsi']}_lb{p['lb']}_f{p['frac']:.3f}"


def main():
    out = ROOT / "results" / "US-18" / "stage2.json"
    if out.exists() and "--force" not in sys.argv:
        sys.exit("stage2 exists")
    resources_ok()
    t0 = time.time()
    P, E = load_world()
    split = P.dates[len(P.dates) // 2]
    W = World(P, E)
    prev = prev_ps()
    allp = list(prev.values())
    result = {}
    for k in (30, 100):
        keys = list(GRID)
        cells, evs = {}, {}
        for vals in itertools.product(*[GRID[x] for x in keys]):
            p = dict(zip(keys, vals))
            ev = build(W, k, **p)
            s = es.summarize(ev, split)
            cells[cell_key(p)] = dict(p=p, n=s["n"], mean=s["mean"], t=s["t"], gross=s["gross"], h1=s["h1"], h2=s["h2"], years_pos=s["years_pos"], pval=s["p"])
            evs[cell_key(p)] = ev
            allp.append(s["p"])
        dkey = cell_key(DEF)
        # 1 plateau
        ok = [c["mean"] > 0 and c["t"] >= 2 for c in cells.values()]
        frac_ok = float(np.mean(ok))
        neigh = []
        for a in keys:
            vs = GRID[a]; i = [abs(v - DEF[a]) < 1e-9 for v in vs].index(True)
            for j in (i - 1, i + 1):
                if 0 <= j < 3:
                    q = dict(DEF); q[a] = vs[j]
                    neigh.append(cells[cell_key(q)]["mean"])
        plateau = bool(frac_ok >= 0.7 and all(m > 0 for m in neigh))
        # smoothed candidate
        smooth = {}
        for key, c in cells.items():
            p = c["p"]; ms = [c["mean"]]
            for a in keys:
                vs = GRID[a]; i = [abs(v - p[a]) < 1e-9 for v in vs].index(True)
                for j in (i - 1, i + 1):
                    if 0 <= j < 3:
                        q = dict(p); q[a] = vs[j]; ms.append(cells[cell_key(q)]["mean"])
            smooth[key] = float(np.mean(ms))
        best = max(smooth, key=lambda x: (round(smooth[x], 10), x == dkey))
        # 2 walk-forward
        years = range(2014, 2025)
        pooled_idx = []
        wf_sel = {}
        yr = {key: ev.dates.year.to_numpy() for key, ev in evs.items()}
        sel_parts = []
        for Y in years:
            bestk, bestm = None, -9
            for key, ev in evs.items():
                m = yr[key] < Y
                if m.sum() >= 100:
                    mm = float(ev.net[m].mean())
                    if mm > bestm:
                        bestk, bestm = key, mm
            wf_sel[Y] = bestk
            ev = evs[bestk]
            sel_parts.append(ev.subset(yr[bestk] == Y))
        oos_net = np.concatenate([e.net for e in sel_parts])
        oos_dates = np.concatenate([e.dates.asi8 for e in sel_parts])
        wm, wt = es.cluster_t(oos_net, oos_dates)
        dflt_oos = evs[dkey].subset(np.isin(yr[dkey], list(years)))
        dm, dt = es.cluster_t(dflt_oos.net, dflt_oos.dates.asi8)
        # 4 baselines on default cell
        Pq = P
        ev_all = var_exit_events(Pq, W.elig(k), 5, lambda ti, ci, kk: Pq.close[ti + kk, ci] > W.sma(5)[ti + kk, ci], W.elig(k))
        netm = np.full(P.close.shape, np.nan)
        netm[ev_all.ti, ev_all.ci] = ev_all.net
        evd = evs[dkey]
        actual = float(evd.net.mean())
        b_all = bl.random_entry_baseline(netm, W.elig(k), evd.ti, actual, draws=1000, seed=11)
        poolb = build(W, k, **DEF, pool_only=True)
        b_mom = bl.random_entry_baseline(netm, poolb, evd.ti, actual, draws=1000, seed=12)
        # candidate extra stats
        cand = evs[best]
        extra = {}
        for N in (5, 10):
            pr = pf.simulate(cand, P.dates, N=N, capital=1.3e6, cost_model=COST)
            extra[f"N{N}"] = dict(sharpe=pr["sharpe"], ann=pr["ann"], maxdd=pr["maxdd"], n=pr["n"], worst=pr["worst"], max_conc=pr["max_conc"])
        c2 = es.summarize(cand.with_cost(cand.cost * 2), split)
        _, tb = block_t(cand)
        result[f"T{k}"] = dict(cells=cells, default=dkey, frac_ok=frac_ok, neigh_means=neigh, plateau=plateau, smooth=smooth, best=best,
                               wf_sel={int(a): b for a, b in wf_sel.items()}, wf_oos_mean=wm, wf_oos_t=wt, wf_oos_n=int(len(oos_net)),
                               default_same_years_mean=dm, default_same_years_t=dt, baseline_all=b_all, baseline_mom_pool=b_mom,
                               years_pos_default=cells[dkey]["years_pos"], cand_2x_mean=c2["mean"], cand_2x_t=c2["t"], cand_block_t=tb,
                               cand_stats=extra, cand_n=len(cand), cand_mean=float(cand.net.mean()), cand_gross=float(cand.gross.mean()))
        print(f"T{k}", "frac_ok %.2f plateau %s best %s WF %.4f%% t %.2f (default same yrs %.4f%% t %.2f) base_all %.3f base_mom %.3f 2x %.4f%% %.0fs" % (
            frac_ok, plateau, best, 100 * wm, wt, 100 * dm, dt, b_all["pct"], b_mom["pct"], 100 * c2["mean"], time.time() - t0), flush=True)
    ids = list(prev) + [f"T{k}:{c}" for k in (30, 100) for c in result[f"T{k}"]["cells"]]
    qs = es.bh_qvalues(allp)
    for k in (30, 100):
        r = result[f"T{k}"]
        r["bh_q_default"] = qs[len(prev) + (0 if k == 30 else 27) + list(r["cells"]).index(r["default"])]
        r["bh_q_best"] = qs[len(prev) + (0 if k == 30 else 27) + list(r["cells"]).index(r["best"])]
        print(f"T{k} BH q default {r['bh_q_default']:.4f} best {r['bh_q_best']:.4f} (cum trials {len(allp)})")
    result["n_trials_cum"] = len(allp)
    report.dump_json(result, out)
    print("done %.0fs" % (time.time() - t0))


if __name__ == "__main__":
    main()
