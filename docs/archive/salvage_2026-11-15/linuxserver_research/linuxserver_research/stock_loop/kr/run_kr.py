"""KR Stage 1 (defaults) and Stage 2 (survivors, one round). DEV DATA ONLY. Run via kr/run_heavy.sh."""
import os, sys, itertools, time, dataclasses, resource
for v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ[v] = "1"
from pathlib import Path
import numpy as np
import pandas as pd
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from lib import data, splits, costs, eventstudy as es, portfolio as pf, baseline as bl, report, features as F
from kr.hypotheses import H

N_SLOTS, CAPITAL = 5, 1.3e6
POOL_GROUP = {"KR-03": "KOSPI", "KR-04": "KOSDAQ", "KR-12": "KOSDAQ"}


def resources_ok():
    la = os.getloadavg()[0]
    avail = [int(l.split()[1]) for l in open("/proc/meminfo") if l.startswith("MemAvailable")][0] / 1048576
    if la > 4 or avail < 2:
        sys.exit(f"ABORT load={la:.2f} availGiB={avail:.1f}")


class Ctx:
    def __init__(self, P):
        self.P = P; self._c = {}
    def sma(self, n):
        return self._c.setdefault(("sma", n), F.sma(self.P.close, n))
    def rsi(self, n):
        return self._c.setdefault(("rsi", n), F.rsi(self.P.close, n))
    def avgvol20(self):
        return self._c.setdefault("v20", F.sma(self.P.volume, 20))
    def index(self, name):
        if name not in self._c:
            self._c[name] = data.load_index(name)["close"]
        return self._c[name]


def panel_for(P, entry):
    """Open-same-day entries must use liquidity known BEFORE the open (lag one bar)."""
    if entry == ("open", 0):
        return dataclasses.replace(P, _v20=F.lag(P.value20, 1))
    return P


def models():
    B = costs.KRCost("B"); A = costs.KRCost("A")
    return {"A": A, "B": B, "B_tax18": B.with_(sell_tax=0.0018), "B_2x": B.with_(mult=2), "A_2x": A.with_(mult=2)}


def run_events(P, ctx, hid, params):
    fn = H[hid][0]
    mask, entry, exit, _ = fn(P, ctx, **params)
    P2 = panel_for(P, entry)
    elig = P2.liquid(params.get("thr", params.get("minv", 2e9)) if hid not in ("KR-03", "KR-04", "KR-08") else 2e9)
    ev = es.make_events(P2, mask, entry, exit, cost_model=models()["B"], eligible=elig)
    return ev, P2, entry, exit


def stats_all(ev, P2, split, full=True):
    out = {}
    for name, m in models().items():
        if not full and name not in ("B",):
            continue
        e2 = ev.with_cost(m.roundtrip(P2.value20[ev.ti, ev.ci]))
        s = es.summarize(e2, split)
        if full and name in ("A", "B"):
            pr = pf.simulate(e2, P2.dates, N=N_SLOTS, capital=CAPITAL, cost_model=m)
            s.update(sharpe=pr["sharpe"], ann=pr["ann"], maxdd=pr["maxdd"], port_n=pr["n"], trades_month=pr["trades_month"],
                     turnover_month=pr["turnover_month"], cap_ratio=pr.get("turnover_cap_ratio", np.nan), worst=pr["worst"], max_conc=pr["max_conc"])
        out[name] = s
    return out


def verdict(s):
    if s["n"] < 30:
        return "noise"
    if s["mean"] > 0 and s["t"] >= 3 and s["h1"] > 0 and s["h2"] > 0:
        return "advance"
    if s["mean"] < 0 and s["t"] <= -3:
        return "hurts"
    return "noise"


def main():
    resources_ok()
    t0 = time.time()
    P = data.load_panel("kr", include_holdout=False)
    assert P.dates.max() < splits.HOLDOUT_START
    print("panel", P.close.shape, P.dates[0].date(), P.dates[-1].date(), "mem MB", resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024, flush=True)
    ctx = Ctx(P)
    split = P.dates[len(P.dates) // 2]
    res, rows = {}, []
    for hid, (fn, dflt, grid, idea) in H.items():
        resources_ok()
        ev, P2, entry, exit = run_events(P, ctx, hid, dflt)
        st = stats_all(ev, P2, split)
        res[hid] = st
        s = st["B"]
        print(hid, "n", s["n"], "B mean %.4f%% t %.2f gross %.4f%%" % (100 * s["mean"], s["t"], 100 * s["gross"]), "Sh", s.get("sharpe"), "A mean %.4f%%" % (100 * st["A"]["mean"]), "%.0fs" % (time.time() - t0), flush=True)
    qs = es.bh_qvalues([res[h]["B"]["p"] for h in H])
    for h, q in zip(H, qs):
        res[h]["B"]["q"] = q
    report.dump_json(res, ROOT / "results" / "KR_stage1.json")
    surv = [h for h in H if verdict(res[h]["B"]) == "advance"]
    for h in H:
        v = verdict(res[h]["B"]); s = res[h]["B"]
        res[h]["verdict"] = v
        nxt = "stage2" if v == "advance" else "drop"
        report.append_ledger(report.ledger_row(h, "KR", H[h][3] + f" [n={s['n']}, gross {100*s['gross']:.3f}%, BE cost {100*s['break_even']:.3f}%, A mean {100*res[h]['A']['mean']:.3f}%, 2x {100*res[h]['B_2x']['mean']:.3f}%]",
                                                    "S1", s["mean"], s["t"], s.get("sharpe"), "locked", v, nxt))
    print("survivors", surv, flush=True)
    # ---- Stage 2
    s2 = {}
    all_p = [res[h]["B"]["p"] for h in H]
    for hid in surv:
        resources_ok()
        fn, dflt, grid, idea = H[hid]
        keys = list(grid)
        cells = []
        for vals in itertools.product(*[grid[k] for k in keys]):
            p = dict(dflt); p.update(dict(zip(keys, vals)))
            ev, P2, _, _ = run_events(P, ctx, hid, p)
            s = es.summarize(ev, split)
            cells.append((p, s)); all_p.append(s["p"])
        dm = {k: dflt[k] for k in keys}
        ok = [c[1]["mean"] > 0 and c[1]["t"] >= 2 for c in cells]
        frac = float(np.mean(ok))
        neigh = []
        for k in keys:
            vs = list(grid[k]); i = vs.index(dflt[k])
            for j in (i - 1, i + 1):
                if 0 <= j < len(vs):
                    q = dict(dflt); q[k] = vs[j]
                    neigh.append([c for c in cells if all(c[0][kk] == q[kk] for kk in keys)][0][1])
        neigh_pos = all(n["mean"] > 0 for n in neigh)
        # baseline for default
        ev, P2, entry, exit = run_events(P, ctx, hid, dflt)
        netm = es.fwd_returns(P2, entry, exit) - models()["B"].roundtrip(P2.value20)
        pool = P2.liquid(2e9)
        if hid in POOL_GROUP:
            pool = pool & (P2.group == POOL_GROUP[hid])[None, :]
        b = bl.random_entry_baseline(netm, pool, ev.ti, float(ev.net.mean()), draws=1000, seed=7)
        s2[hid] = dict(cells=[dict(p=c[0], mean=c[1]["mean"], t=c[1]["t"], n=c[1]["n"], years_pos=c[1]["years_pos"]) for c in cells],
                       frac_ok=frac, neigh_pos=neigh_pos, plateau=bool(frac >= 0.7 and neigh_pos), baseline=b,
                       years_pos_default=res[hid]["B"]["years_pos"])
    qall = es.bh_qvalues(all_p)
    nS1 = len(H)
    report.dump_json(dict(stage2=s2, bh_all_q_stage1=qall[:nS1], n_trials=len(all_p)), ROOT / "results" / "KR_stage2.json")
    for hid in surv:
        r = s2[hid]; s = res[hid]["B"]
        v = "advance" if (r["plateau"] and qall[list(H).index(hid)] < 0.10) else "noise"
        s2[hid]["verdict"] = v
        report.append_ledger(report.ledger_row(hid, "KR", H[hid][3] + f" [S2 grid {len(r['cells'])} cells: ok-frac {r['frac_ok']:.2f}, neighbours+ {r['neigh_pos']}, rand-baseline pct {r['baseline']['pct']:.3f}, BH q(all {len(all_p)} trials) {qall[list(H).index(hid)]:.3f}, yrs+ {r['years_pos_default']:.2f}]",
                                                    "S2", s["mean"], s["t"], s.get("sharpe"), "locked", v, "stage3 (holdout) if user ok" if v == "advance" else "drop"))
    report.dump_json(dict(stage1=res, stage2=s2), ROOT / "results" / "KR_all.json")
    print("done %.0fs peakMB %d" % (time.time() - t0, resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024))


if __name__ == "__main__":
    main()
