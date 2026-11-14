"""KR Round 2: Stage 1 (defaults) + one Stage 2 grid for survivors. DEV DATA ONLY. Run via kr/run_heavy.sh."""
import os, sys, itertools, time, resource, json
for v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ[v] = "1"
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from lib import data, splits, eventstudy as es, baseline as bl, report, features as F
from kr import run_kr as R
from kr.hypotheses2 import H2

R1_TRIALS = 12


def run(P, ctx, hid, params, lag=0):
    fn = H2[hid][0]
    mask, entry, exit = fn(P, ctx, **params)
    if lag:                               # robustness: shift entry and exit by `lag` bars
        entry, exit = (entry[0], entry[1] + lag), (exit[0], exit[1] + lag)
        mask = mask
    P2 = R.panel_for(P, entry)
    ev = es.make_events(P2, mask, entry, exit, cost_model=R.models()["B"], eligible=P2.liquid(2e9))
    return ev, P2, entry, exit


def main():
    R.resources_ok(); t0 = time.time()
    P = data.load_panel("kr", include_holdout=False)
    assert P.dates.max() < splits.HOLDOUT_START
    ctx = R.Ctx(P); split = P.dates[len(P.dates) // 2]
    r1 = json.load(open(ROOT / "results" / "KR_stage1.json"))
    p1 = [r1[k]["B"]["p"] for k in sorted(r1)]
    res = {}
    for hid, (fn, dflt, grid, idea, N, sig) in H2.items():
        R.resources_ok(); R.N_SLOTS = N
        ev, P2, entry, exit = run(P, ctx, hid, dflt)
        st = R.stats_all(ev, P2, split)
        res[hid] = st; s = st["B"]
        print(hid, "n", s["n"], "B mean %.3f%% t %.2f gross %.3f%% h1 %.3f h2 %.3f Sh %.2f | A mean %.3f%% Sh %.2f | 2x %.3f%% | tax18 %.3f%% | maxconc %s" % (
            100 * s["mean"], s["t"], 100 * s["gross"], 100 * s["h1"], 100 * s["h2"], s.get("sharpe", np.nan), 100 * st["A"]["mean"], st["A"].get("sharpe", np.nan),
            100 * st["B_2x"]["mean"], 100 * st["B_tax18"]["mean"], s.get("max_conc")), "%.0fs" % (time.time() - t0), flush=True)
    for hid in H2:
        v = R.verdict(res[hid]["B"]); res[hid]["verdict"] = v
    surv = [h for h in H2 if res[h]["verdict"] == "advance"]
    print("survivors", surv, flush=True)
    s2, all_p = {}, list(p1) + [res[h]["B"]["p"] for h in H2]
    cellrefs = {}
    for hid in surv:
        fn, dflt, grid, idea, N, sig = H2[hid]; R.N_SLOTS = N
        keys = list(grid); cells = []
        for vals in itertools.product(*[grid[k] for k in keys]):
            R.resources_ok()
            p = dict(dflt); p.update(dict(zip(keys, vals)))
            ev, P2, _, _ = run(P, ctx, hid, p)
            s = es.summarize(ev, split); cells.append((p, s)); all_p.append(s["p"])
        ok = [c[1]["mean"] > 0 and c[1]["t"] >= 2 for c in cells]
        neigh = []
        for k in keys:
            vs = list(grid[k]); i = vs.index(dflt[k])
            for j in (i - 1, i + 1):
                if 0 <= j < len(vs):
                    q = dict(dflt); q[k] = vs[j]
                    neigh.append([c for c in cells if all(c[0][kk] == q[kk] for kk in keys)][0][1])
        ev, P2, entry, exit = run(P, ctx, hid, dflt)
        netm = es.fwd_returns(P2, entry, exit) - R.models()["B"].roundtrip(P2.value20)
        b = bl.random_entry_baseline(netm, P2.liquid(2e9), ev.ti, float(ev.net.mean()), draws=1000, seed=7)
        evl, P2l, _, _ = run(P, ctx, hid, dflt, lag=1)
        sl = es.summarize(evl, split)
        s2[hid] = dict(cells=[dict(p=c[0], mean=c[1]["mean"], t=c[1]["t"], n=c[1]["n"]) for c in cells], frac_ok=float(np.mean(ok)),
                       neigh_pos=all(n["mean"] > 0 for n in neigh), baseline=b, lag1=dict(mean=sl["mean"], t=sl["t"], n=sl["n"]),
                       years_pos=res[hid]["B"]["years_pos"])
        s2[hid]["plateau"] = bool(s2[hid]["frac_ok"] >= 0.7 and s2[hid]["neigh_pos"])
    q = es.bh_qvalues(all_p)
    ids = list(H2)
    for i, hid in enumerate(ids):
        res[hid]["B"]["q"] = q[R1_TRIALS + i]
    print("total trials", len(all_p))
    for hid in ids:
        s = res[hid]["B"]; v = res[hid]["verdict"]
        extra = ""
        if hid in s2:
            r = s2[hid]; v = "advance" if (r["plateau"] and s["q"] < 0.10) else "noise"
            extra = f" [S2 {len(r['cells'])} cells ok-frac {r['frac_ok']:.2f}, neigh+ {r['neigh_pos']}, rand pct {r['baseline']['pct']:.3f}, lag1 mean {100*r['lag1']['mean']:.3f}% t {r['lag1']['t']:.2f}, BH q({len(all_p)} trials) {s['q']:.3f}, yrs+ {r['years_pos']:.2f}]"
            res[hid]["verdict_s2"] = v
        row = report.ledger_row(hid, "KR", H2[hid][3] + f" [n={s['n']}, gross {100*s['gross']:.3f}%, BE cost {100*s['break_even']:.3f}%, A mean {100*res[hid]['A']['mean']:.3f}% Sh {res[hid]['A'].get('sharpe', float('nan')):.2f}, 2x {100*res[hid]['B_2x']['mean']:.3f}%, h1 {100*s['h1']:.3f}% h2 {100*s['h2']:.3f}%, N={H2[hid][4]}]" + extra,
                                "S2" if hid in s2 else "S1", s["mean"], s["t"], s.get("sharpe"), "locked", v, "stage3 (holdout) if user ok" if (hid in s2 and v == "advance") else "drop")
        report.append_ledger(row)
    report.dump_json(dict(stage1=res, stage2=s2, n_trials=len(all_p)), ROOT / "results" / "KR_round2.json")
    print("done %.0fs peakMB %d" % (time.time() - t0, resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024))


if __name__ == "__main__":
    main()
