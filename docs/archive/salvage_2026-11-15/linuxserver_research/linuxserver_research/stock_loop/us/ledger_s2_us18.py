import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from lib import report

d = json.load(open(ROOT / "results/US-18/stage2.json"))
for k, name in (("T30", "US-18"), ("T100", "US-18-T100")):
    r = d[k]
    df = r["cells"][r["default"]]
    ok = r["plateau"] and r["bh_q_default"] < 0.10 and r["wf_oos_t"] >= 2 and r["wf_oos_mean"] > 0
    idea = (f"momentum-leader dip (126d top third, RSI2<10, exit>SMA5/5d) S2 grid 27 cells: ok-frac {r['frac_ok']:.2f}, plateau {r['plateau']}, "
            f"WF OOS 2014-24 {100*r['wf_oos_mean']:.3f}% t={r['wf_oos_t']:.2f} (n={r['wf_oos_n']}), rand-baseline pct {r['baseline_all']['pct']:.3f} (mom-pool {r['baseline_mom_pool']['pct']:.3f}), "
            f"BH q(cum {d['n_trials_cum']}) {r['bh_q_default']:.4f}, yrs+ {r['years_pos_default']:.2f}, best cell {r['best']} net {100*r['cand_mean']:.3f}% 2x {100*r['cand_2x_mean']:.3f}% N10 Sh {r['cand_stats']['N10']['sharpe']:.2f}")
    report.append_ledger(report.ledger_row(name, "US", idea, "S2", df["mean"], df["t"], r["cand_stats"]["N5"]["sharpe"], "locked",
                                           "advance" if ok else "noise (WF t<2)", "stage3 (holdout)" if ok else "drop; T100 carries"))
