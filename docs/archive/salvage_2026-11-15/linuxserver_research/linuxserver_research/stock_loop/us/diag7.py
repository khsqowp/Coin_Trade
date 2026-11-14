"""Round 7 DEV-only diagnostic (not a trial, not used for selection): US-18c cell by period on MEM vs DYN vs frozen."""
from .common import *  # noqa
from .hyp4 import frozen_mask, FREEZE
from .hyp7 import spec_events, mem_elig
from .run_round import World

P, E = load_world()
W = World(P, E)
sets = {"DYN": W.elig(100), "MEM": mem_elig(W), "F14": frozen_mask(P, FREEZE["F14"], 100), "F18": frozen_mask(P, FREEZE["F18"], 100)}
out = {}
for nm, el in sets.items():
    ev = spec_events(W, "18c", el)
    row = {}
    for lab, lo in (("2010+", "2010-01-01"), ("2015+", "2015-01-01"), ("2019+", "2019-01-01")):
        m = ev.dates >= lo
        if m.sum() > 30:
            mu, t = es.cluster_t(ev.net[m], ev.dates[m].asi8)
            row[lab] = (int(m.sum()), round(100 * mu, 3), round(t, 2), round(100 * float((ev.net[m] - ev.cost[m]).mean()), 3))
    y = pd.Series(ev.net).groupby(ev.dates.year).mean() * 100
    row["by_year"] = {int(k): round(float(v), 2) for k, v in y.items()}
    out[nm] = row
    print(nm, {k: v for k, v in row.items() if k != "by_year"}); print("   ", row["by_year"])
report.dump_json(out, ROOT / "results" / "US-35" / "diag_periods.json")
