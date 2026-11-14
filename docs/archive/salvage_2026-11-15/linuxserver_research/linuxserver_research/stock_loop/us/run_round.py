"""Generic new-hypothesis round runner: python -m us.run_round <round> (imports us.hyp<round>). DEV ONLY.
Cumulative BH q over all previous round files (results/US_stage1.json, results/US_round*.json)."""
import time, resource, sys, importlib, json
from collections import defaultdict
from .common import *  # noqa
from .hyp import Ctx


class World:
    def __init__(self, P, E):
        self.P, self.E = P, E
        c = Ctx(P, E)
        self.elig, self.sma, self.avgvol, self.spy_ret, self.f = c.elig, c.sma, c.avgvol, c.spy_ret, c.f


def prev_ps():
    ps = {}
    for p in [ROOT / "results" / "US_stage1.json"] + sorted((ROOT / "results").glob("US_round*.json")):
        d = json.loads(p.read_text())
        for k, v in d["res"].items():
            ps[k] = v["p"]
    s2 = ROOT / "results" / "US-18" / "stage2.json"          # Stage 2 grid cells count as trials
    if s2.exists():
        d2 = json.loads(s2.read_text())
        for u in ("T30", "T100"):
            for ck, c in d2[u]["cells"].items():
                ps[f"S2-{u}-{ck}"] = c["pval"]
    return ps


def main():
    rnd = sys.argv[1]
    mod = importlib.import_module(f"us.hyp{rnd}")
    out = ROOT / "results" / f"US_round{rnd}.json"
    if out.exists() and "--force" not in sys.argv:
        sys.exit(f"{out.name} exists; refusing to rerun")
    resources_ok()
    t0 = time.time()
    P, E = load_world()
    split = P.dates[len(P.dates) // 2]
    W = World(P, E)
    res, byh = {}, defaultdict(dict)
    for item in mod.registry():
        rid, h, idea, fn, N, etf = item[:6]
        start = item[6] if len(item) > 6 else None
        resources_ok()
        ev = fn(W)
        PP = E if etf else P
        sp = split if start is None else P.dates[P.dates >= pd.Timestamp(start)][len(P.dates[P.dates >= pd.Timestamp(start)]) // 2]
        s = full_stats(ev, PP, sp, N)
        s.update(extras(ev, PP))
        s["idea"] = idea
        res[rid] = s
        byh[h][rid] = s
        _, s["trades_saved"] = save_trades(ev, PP, ROOT / "results" / h / f"trades_{rid}.parquet")
        print(rid, "n", s["n"], "net %.4f%% t %.2f tblk %.2f gross %.4f%% h1 %.4f%% h2 %.4f%% 2x %.4f%% top5 %.2f Sh %.2f %s %.0fs" % (
            100 * s["mean"], s["t"], s.get("t_block", np.nan), 100 * s["gross"], 100 * s.get("h1", np.nan), 100 * s.get("h2", np.nan),
            100 * s.get("mean_2x", np.nan), s.get("top5_share", np.nan), s.get("sharpe", np.nan), s["verdict"], time.time() - t0), flush=True)
    prev = prev_ps()
    ids = list(prev) + list(res)
    qs = dict(zip(ids, es.bh_qvalues([prev[i] if i in prev else res[i]["p"] for i in ids])))
    for i in res:
        res[i]["q_cum"] = qs[i]
    for h, d in byh.items():
        report.dump_json(d, ROOT / "results" / h / "summary.json")
    report.dump_json(dict(split=str(split.date()), n_trials_round=len(res), n_trials_cum=len(ids), res=res), out)
    for i, s in res.items():
        nxt = "stage2" if s["verdict"] == "advance" else "drop"
        idea = (f"{s['idea']} [n={s['n']}, gross {100*s['gross']:.3f}%, BE cost {100*s['break_even']:.3f}%, 2x {100*s['mean_2x']:.3f}%, "
                f"3x {100*s.get('mean_3x', float('nan')):.3f}%, top5 {s.get('top5_share', float('nan')):.2f}, nextopen {100*s.get('mean_nextopen', float('nan')):.3f}%, halves {100*s['h1']:.3f}/{100*s['h2']:.3f}%, blk-t {s['t_block']:.2f}, yrs+ {s['years_pos']:.2f}, BH q(cum {len(ids)}) {s['q_cum']:.3f}]")
        report.append_ledger(report.ledger_row(i, "US", idea, "S1", s["mean"], s["t"], s["sharpe"], "locked", s["verdict"], nxt))
    print("survivors", [i for i in res if res[i]["verdict"] == "advance"], "cum trials", len(ids))
    print("done %.0fs peakMB %d" % (time.time() - t0, resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024))


if __name__ == "__main__":
    main()
