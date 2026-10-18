import json, numpy as np
from dataclasses import replace
import app.rs_risk_run as R
from app.rs_risk_engine import Cfg
R._init()
res = json.load(open("docs/research/risk_results.json"))
def row(m): return (f"CAGR {m['cagr']*100:5.1f}% (ph {m['cagr_min']*100:.0f}..{m['cagr_max']*100:.0f}) iMDD {m['imdd']*100:4.1f} MDD {m['mdd']*100:4.1f} "
                    f"Cal {m['calmar']:.2f} Sh {m['sharpe']:.2f} wd {m['worst_day']*100:.1f} ww {m['worst_week']*100:.1f} uw {m['longest_uw_days']:.0f} buf {m['min_buffer']:.0f} yr " +
                    " ".join(f"{y}:{v*100:.0f}" for y, v in m['yearly'].items()))
for sig, tv, lb, cap in [("base_14_3_8", .15, 60, 1.5), ("live_14_2_12", .2, 60, 1.5)]:
    s = R.SIGS[sig]
    cfg = Cfg(**s, lev=cap, deploy=1.0, vol_target=tv, vol_lb=lb, lev_cap=cap)
    print("=====", sig, "rec vol", tv, lb, cap)
    for w in ("IS", "OOS", "FULL"): print("  ", w, row(R.run_one((cfg, w))))
    # neighbours
    out = []
    for tv2 in (tv - .03, tv, tv + .03):
        for lb2 in (30, 60):
            for cap2 in (1.5, 2):
                c = replace(cfg, vol_target=tv2, vol_lb=lb2, lev_cap=cap2, lev=cap2)
                m = R.run_one((c, "FULL")); o = R.run_one((c, "OOS"))
                out.append((tv2, lb2, cap2, m["cagr"], m["imdd"], o["imdd"], m["calmar"]))
    for t in out: print(f"   nb T{t[0]:.2f} lb{t[1]} cap{t[2]}: FULL CAGR {t[3]*100:.1f} iMDD {t[4]*100:.1f} OOS iMDD {t[5]*100:.1f} Cal {t[6]:.2f}")
    print("   neighbour Calmar min/median", min(t[6] for t in out), float(np.median([t[6] for t in out])), "chosen", [t[6] for t in out if t[:3] == (tv, lb, cap)])
    st = R.stress((cfg,)); print("   stress", st["1y_block10"], st["2y_block10"])
    # small account (142 USDT)
    for mn, nm in [(5., "minN5"), (5., "minN5+BTC100/ETH20"), (20., "minN20")]:
        kw = dict(min_notional=mn, start_equity=142.0)
        if "BTC" in nm: kw["min_names"] = (("BTC", 100.), ("ETH", 20.))
        c = replace(cfg, **kw)
        print("   142USDT", nm, row(R.run_one((c, "FULL"))))
# K12 feasibility for several constant gross
for L in (1.0, 1.5, 2.0, 2.9, 3.2):
    for K in (8, 12):
        print("per-position notional @142 USDT gross", L, "K", K, round(142 * L / (2 * K), 2))
# live variants: current live K12/2d with exact live logic across account sizes (min notional 5)
b = dict(lookback=14, rebal=2, K=12, lev=4, deploy=.8, ladder=((.2, .25),), hyst=0.0, kill_dd=.35, start_equity=142.0, min_notional=5.0)
for nm, c in {"live exact": Cfg(**b), "live, no min-notional (ideal)": replace(Cfg(**b), min_notional=0.0),
              "live K8": replace(Cfg(**b), K=8, rebal=3), "live K8 minN20": replace(Cfg(**b), K=8, rebal=3, min_notional=20.)}.items():
    for w in ("IS", "OOS", "FULL"): print("LIVE", nm, w, row(R.run_one((c, w))), "halted", R.run_one((c, w))["halted"])
