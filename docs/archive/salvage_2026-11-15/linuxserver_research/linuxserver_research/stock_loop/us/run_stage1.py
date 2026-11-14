"""US Stage 1: all preregistered hypotheses at fixed defaults, DEV DATA ONLY. Run via us/run_heavy.sh -m us.run_stage1"""
import time, resource, sys
from collections import defaultdict
from .common import *  # noqa
from .hyp import Ctx, registry


class World:
    def __init__(self, P, E):
        self.P, self.E = P, E
        self.ctx = Ctx(P, E)
        self.elig = self.ctx.elig
        self.sma = self.ctx.sma
        self.avgvol = self.ctx.avgvol
        self.spy_ret = self.ctx.spy_ret
        self.f = self.ctx.f


def main():
    out = ROOT / "results" / "US_stage1.json"
    if out.exists() and "--force" not in sys.argv:
        sys.exit("US_stage1.json exists; refusing to rerun (ledger would duplicate)")
    resources_ok()
    t0 = time.time()
    P, E = load_world()
    print("panel", P.close.shape, P.dates[0].date(), P.dates[-1].date(), "ETF", E.codes, flush=True)
    split = P.dates[len(P.dates) // 2]
    W = World(P, E)
    res, byh = {}, defaultdict(dict)
    for rid, h, idea, fn, N in registry():
        resources_ok()
        ev = fn(W)
        PP = E if h in ("US-08", "US-10") or rid.startswith(("US-03-SPY", "US-03-QQQ", "US-09-SPY")) else P
        s = full_stats(ev, PP, split, N)
        s["idea"] = idea
        res[rid] = s
        byh[h][rid] = s
        n_all, n_saved = save_trades(ev, PP, ROOT / "results" / h / f"trades_{rid}.parquet")
        s["trades_saved"] = n_saved
        print(rid, "n", s["n"], "net %.4f%% t %.2f tblk %.2f gross %.4f%% h1 %.4f%% h2 %.4f%% Sh %s %s %.0fs" % (
            100 * s["mean"], s["t"], s.get("t_block", np.nan), 100 * s["gross"], 100 * s.get("h1", np.nan), 100 * s.get("h2", np.nan),
            "%.2f" % s["sharpe"] if np.isfinite(s.get("sharpe", np.nan)) else "nan", s["verdict"], time.time() - t0), flush=True)
    ids = list(res)
    qs = es.bh_qvalues([res[i]["p"] for i in ids])
    for i, q in zip(ids, qs):
        res[i]["q"] = q
    for h, d in byh.items():
        report.dump_json(d, ROOT / "results" / h / "summary.json")
    report.dump_json(dict(split=str(split.date()), n_trials=len(ids), res=res), out)
    for i in ids:
        s = res[i]
        nxt = "stage2" if s["verdict"] == "advance" else "drop"
        idea = (f"{s['idea']} [n={s['n']}, gross {100*s['gross']:.3f}%, BE cost {100*s['break_even']:.3f}%, 2x {100*s['mean_2x']:.3f}%, "
                f"halves {100*s['h1']:.3f}/{100*s['h2']:.3f}%, blk-t {s['t_block']:.2f}, yrs+ {s['years_pos']:.2f}]")
        report.append_ledger(report.ledger_row(i, "US", idea, "S1", s["mean"], s["t"], s["sharpe"], "locked", s["verdict"], nxt))
    print("survivors", [i for i in ids if res[i]["verdict"] == "advance"], "trials", len(ids))
    print("done %.0fs peakMB %d" % (time.time() - t0, resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024))


if __name__ == "__main__":
    main()
