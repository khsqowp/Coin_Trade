"""Round 3: preregistered KR hypotheses. Development data only."""
import os, sys, itertools, time, resource, json
for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ[_v] = "1"
from pathlib import Path
import numpy as np
import pandas as pd
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from lib import data, splits, eventstudy as es, baseline as bl, report, features as F, portfolio as pf
from kr import run_kr as R
from kr.hypotheses3 import H3, h_kr24

R1_TRIALS, R2_TRIALS = 12, 12


def run(P, ctx, hid, params, lag=0, fn=None):
    mask, entry, exit = (fn or H3[hid][0])(P, ctx, **params)
    if lag:
        entry, exit = (entry[0], entry[1] + lag), (exit[0], exit[1] + lag)
    P2 = R.panel_for(P, entry)
    ev = es.make_events(P2, mask, entry, exit, cost_model=R.models()["B"], eligible=P2.liquid(2e9))
    return ev, P2, entry, exit, mask


def month_t(ev):
    c = ev.dates.year * 12 + ev.dates.month
    return es.cluster_t(ev.net, c)[1]


def yearly(ev):
    return {str(y): {"n": int((ev.dates.year == y).sum()), "mean": float(ev.net[ev.dates.year == y].mean())}
            for y in np.unique(ev.dates.year)}


def diagnostic(P, ctx, hid, fn, params, split, label=None):
    ev, P2, entry, exit, mask = run(P, ctx, hid, params, fn=fn)
    net = ev.net; years = yearly(ev)
    crash = ~((ev.dates >= "2020-02-15") & (ev.dates <= "2020-04-30"))
    stock_n = np.bincount(ev.ci, minlength=len(P.codes))
    top = np.argsort(stock_n)[-5:][::-1]
    excluded = ~np.isin(ev.ci, top)
    date_n = pd.Series(ev.ti).value_counts()
    maxday = int(date_n.max()) if len(date_n) else 0
    calm = np.array([date_n.get(t, 0) < 15 for t in ev.ti])
    groups = {}
    for g in ("KOSPI", "KOSDAQ"):
        a = P.group[ev.ci] == g
        groups[g] = _substats(ev, a)
    buckets = {}
    val = P.value20[ev.ti, ev.ci]
    for name, a in (("2e9-1e10", (val >= 2e9) & (val < 1e10)), ("1e10-5e10", (val >= 1e10) & (val < 5e10)), (">=5e10", val >= 5e10)):
        buckets[name] = _substats(ev, a)
    lag_ev, _, _, _, _ = run(P, ctx, hid, params, lag=1, fn=fn)
    wins = np.clip(net, *np.nanpercentile(net, [1, 99])) if len(net) else net
    st = R.stats_all(ev, P2, split)
    return {"label": label or hid, "yearly": years, "exclude_crash": {"n_excluded": int((~crash).sum()), "mean_remaining": float(net[crash].mean()) if crash.any() else np.nan},
            "concentration": {"top5": [{"code": str(P.codes[j]), "n": int(stock_n[j])} for j in top], "top5_event_share": float(stock_n[top].sum()/len(ev)) if len(ev) else np.nan,
                              "mean_ex_top5": float(net[excluded].mean()) if excluded.any() else np.nan, "max_events_entry_date": maxday,
                              "mean_without_dates_ge15": float(net[calm].mean()) if calm.any() else np.nan},
            "groups": groups, "liquidity": buckets, "fill_next_close": _substats(lag_ev),
            "winsor1_mean": float(wins.mean()) if len(wins) else np.nan, "median": float(np.median(net)) if len(net) else np.nan,
            "A_mean": st["A"]["mean"], "B_mean": st["B"]["mean"], "events": len(ev), "event_keys": set(zip(ev.ti.tolist(), ev.ci.tolist()))}


def _substats(ev, sel=None):
    sel = np.ones(len(ev), dtype=bool) if sel is None else np.asarray(sel, dtype=bool)
    n = int(sel.sum())
    if n == 0:
        return {"n": 0, "mean": np.nan, "t": np.nan}
    m, t = es.cluster_t(ev.net[sel], ev.dates.asi8[sel])
    return {"n": n, "mean": m, "t": t}


def agreement(diags):
    keys = list(diags); out = {}
    for a in keys:
        out[a] = {}
        for b in keys:
            x, y = diags[a]["event_keys"], diags[b]["event_keys"]
            out[a][b] = {"shared": len(x & y), "jaccard": len(x & y) / len(x | y) if x | y else np.nan}
    return out


def stage2_one(P, ctx, hid, dflt, grid, split, stage1):
    R.N_SLOTS = H3[hid][4]
    keys = list(grid); cells = []
    for vals in itertools.product(*[grid[k] for k in keys]):
        R.resources_ok(); p = dict(dflt); p.update(dict(zip(keys, vals)))
        ev, _, _, _, _ = run(P, ctx, hid, p); s = es.summarize(ev, split)
        cells.append((p, s))
    good = [s["mean"] > 0 and s["t"] >= 2 for _, s in cells]
    neigh = []
    for k in keys:
        vs = list(grid[k]); i = vs.index(dflt[k])
        for j in (i - 1, i + 1):
            if 0 <= j < len(vs):
                q = dict(dflt); q[k] = vs[j]
                neigh.append(next(s for p, s in cells if all(p[x] == q[x] for x in keys)))
    ev, P2, entry, exit, _ = run(P, ctx, hid, dflt)
    netm = es.fwd_returns(P2, entry, exit) - R.models()["B"].roundtrip(P2.value20)
    base = bl.random_entry_baseline(netm, P2.liquid(2e9), ev.ti, float(ev.net.mean()) if len(ev) else np.nan, draws=1000, seed=7)
    lag_ev, _, _, _, _ = run(P, ctx, hid, dflt, lag=1); lag = es.summarize(lag_ev, split)
    two = ev.with_cost(R.models()["B_2x"].roundtrip(P2.value20[ev.ti, ev.ci]))
    s2x = es.summarize(two, split)
    daily = pf.simulate(ev.with_cost(R.models()["B"].roundtrip(P2.value20[ev.ti, ev.ci])), P2.dates, N=H3[hid][4])
    span = [str(daily["daily"].index.min()), str(daily["daily"].index.max())] if len(daily["daily"]) else []
    bh_span = {name: buyhold_sharpe(name, P.dates[(P.dates >= span[0]) & (P.dates <= span[1])]) for name in ("KOSPI", "KOSDAQ")} if span else {}
    return {"cells": [dict(params=p, mean=s["mean"], t=s["t"], p=s["p"], n=s["n"]) for p, s in cells],
            "cell_ps": [s["p"] for _, s in cells], "frac_ok": float(np.mean(good)), "neigh_pos": all(s["mean"] > 0 for s in neigh),
            "plateau": bool(np.mean(good) >= .7 and all(s["mean"] > 0 for s in neigh)), "baseline": base,
            "lag1": {"mean": lag["mean"], "t": lag["t"], "n": lag["n"]}, "B_2x_mean": s2x["mean"],
            "years_pos": stage1["B"]["years_pos"], "portfolio_sharpe_B": daily["sharpe"], "daily_span": span, "buy_hold_sharpe_same_span": bh_span}


def buyhold_sharpe(name, dates):
    d = data.load_index(name)["close"].reindex(dates).ffill().pct_change().dropna()
    return float(d.mean() / d.std() * np.sqrt(252)) if d.std() > 0 else np.nan


def main():
    R.resources_ok(); t0 = time.time()
    P = data.load_panel("kr", include_holdout=False)
    assert P.dates.max() < splits.HOLDOUT_START
    ctx = R.Ctx(P); split = P.dates[len(P.dates)//2]
    prior1 = json.loads((ROOT / "results" / "KR_stage1.json").read_text())
    prior2 = json.loads((ROOT / "results" / "KR_round2.json").read_text())["stage1"]
    oldp = [prior1[k]["B"]["p"] for k in sorted(prior1)] + [prior2[k]["B"]["p"] for k in sorted(prior2)]
    res, events, s2 = {}, {}, {}
    for hid, (fn, dflt, grid, idea, slots, sig) in H3.items():
        R.resources_ok(); R.N_SLOTS = slots
        ev, P2, _, _, _ = run(P, ctx, hid, dflt); events[hid] = ev
        st = R.stats_all(ev, P2, split); st["B"]["t_month"] = month_t(ev); st["verdict"] = R.verdict(st["B"]); res[hid] = st
        s = st["B"]
        print(hid, "n", s["n"], "B mean %.3f%% t %.2f t_month %.2f gross %.3f%% h1 %.3f h2 %.3f Sh %.2f A %.3f%%" % (100*s["mean"],s["t"],s["t_month"],100*s["gross"],100*s["h1"],100*s["h2"],s.get("sharpe",np.nan),100*st["A"]["mean"]), flush=True)
    diag = {}
    funcs = {"KR-24ref": (h_kr24, dict(r=.15,dry=.5,h=3))}
    for hid in ("KR-25", "KR-26", "KR-27", "KR-36"):
        funcs[hid] = (H3[hid][0], H3[hid][1])
    for label, (fn, p) in funcs.items():
        R.resources_ok(); diag[label] = diagnostic(P, ctx, label, fn, p, split, label)
        diag[label].pop("event_keys")
        print("diagnostic", label, json.dumps(diag[label], default=str, ensure_ascii=False), flush=True)
    diag["agreement"] = agreement({k: diagnostic(P, ctx, k, fn, p, split) for k, (fn, p) in funcs.items() if k != "KR-24ref"} | {"KR-24ref": diagnostic(P, ctx, "KR-24", *funcs["KR-24ref"], split)})
    ppool = oldp + [res[h]["B"]["p"] for h in H3]
    for hid in H3:
        if res[hid]["verdict"] == "advance":
            fn, d, grid, _, _, _ = H3[hid]
            s2[hid] = stage2_one(P, ctx, hid, d, grid, split, res[hid]); ppool.extend(s2[hid]["cell_ps"])
    q = es.bh_qvalues(ppool)
    for i, hid in enumerate(H3): res[hid]["B"]["q"] = q[len(oldp) + i]
    bh_n = len(ppool)
    cell_q = {}; qi = len(oldp) + len(H3)
    for hid, result in s2.items():
        cell_q[hid] = q[qi:qi + len(result["cell_ps"])]
        for cell, cq in zip(result["cells"], cell_q[hid]): cell["q"] = cq
        qi += len(result["cell_ps"])
    bh = {"n_trials": bh_n, "prior_trials": len(oldp), "stage1_new_q": {h: res[h]["B"]["q"] for h in H3}, "stage2_cell_q": cell_q}
    for hid, (fn, d, grid, idea, slots, sig) in H3.items():
        ev, P2, _, _, _ = run(P, ctx, hid, d); s = res[hid]["B"]
        portfolio = st_port = res[hid]["B"].get("sharpe", np.nan)
        R.N_SLOTS = slots
        row = report.ledger_row(hid, "KR", idea + f" [n={s['n']} gross={100*s['gross']:.3f}% BE={100*s['break_even']:.3f}% A={100*res[hid]['A']['mean']:.3f}% 2x={100*res[hid]['B_2x']['mean']:.3f}% h1={100*s['h1']:.3f}% h2={100*s['h2']:.3f}% N={slots} t_month={s['t_month']:.2f} q({bh_n})={s['q']:.4f}]",
                                "S2" if hid in s2 else "S1", s["mean"], s["t"], portfolio, "locked", res[hid]["verdict"], "stage3 if advance")
        report.append_ledger(row)
    span = P.dates
    bh_sh = {n: buyhold_sharpe(n, span) for n in ("KOSPI", "KOSDAQ")}
    print("buy_hold_sharpe", bh_sh)
    print("id n mean t t_month q B_sharpe BE 2x years_pos")
    for hid in H3:
        b = res[hid]["B"]
        print(hid, b["n"], b["mean"], b["t"], b["t_month"], b["q"], b.get("sharpe"), b["break_even"], res[hid]["B_2x"]["mean"], b["years_pos"])
    report.dump_json({"stage1": res, "stage2": s2, "diagnostics": diag, "buy_hold_sharpe": bh_sh, "bh": bh,
                      "n_trials": bh_n}, ROOT / "results" / "KR_round3.json")
    print("total trials", bh_n)
    print("done %.0fs peakMB %d" % (time.time()-t0, resource.getrusage(resource.RUSAGE_SELF).ru_maxrss//1024))


if __name__ == "__main__":
    main()
