"""Delever-design comparison on the 142 USDT account (min notional 5 / 20). Kill -35% everywhere."""
from __future__ import annotations
import json
import numpy as np
from app.rs_final_data import load_panel
from app.rs_final_engine import Sim, window_metrics

CFGS = {
    "L1 live 14/2/K12 4x*0.8": dict(lbs=(14,), rebal=2, K=12, lev=4.0, deploy=0.8),
    "L2 14/3/K8 4x*0.8": dict(lbs=(14,), rebal=3, K=8, lev=4.0, deploy=0.8),
    "L3 14/3/K8 2x*1.0": dict(lbs=(14,), rebal=3, K=8, lev=2.0, deploy=1.0),
    "L4 14/3/K12 1x*1.0": dict(lbs=(14,), rebal=3, K=12, lev=1.0, deploy=1.0),
    "L5 14/3/K8 1.5x*1.0 (vol-target cap)": dict(lbs=(14,), rebal=3, K=8, lev=1.5, deploy=1.0),
}
DESIGNS = {
    "n  no delever (kill+14d cooldown)": dict(design=0, kill=0.35, cool=14),
    "a  LIVE int-1x, new entries only, kill permanent": dict(design=1, kill=0.35, cool=0, dlv=0.20, rlv=0.20),
    "a1 int-1x + resize on level change": dict(design=1, resize=1, kill=0.35, cool=0, dlv=0.20, rlv=0.20),
    "a2 live + flat re-arm 5d (hwm reset)": dict(design=1, rearm=5, kill=0.35, cool=0, dlv=0.20, rlv=0.20),
    "b  halve gross + resize + re-arm + kill/cool14": dict(design=2, resize=1, rearm=5, kill=0.35, cool=14, dlv=0.20, rlv=0.15),
    "c  vol-target only T15 cap1.5 + kill/cool14": dict(design=0, vt=0.15, cap=1.5, kill=0.35, cool=14),
    "d  halve gross + K-shrink to keep >=min + re-arm": dict(design=3, resize=1, rearm=5, kill=0.35, cool=14, dlv=0.20, rlv=0.15),
    "e  vol-target T15 cap1.5 + K-shrink (no ladder)": dict(design=3, dlv=9.0, rlv=9.0, vt=0.15, cap=1.5, kill=0.35, cool=14),
}


def evaluate(S, cfg, des, minn):
    N = cfg["rebal"]
    out = []
    for p in range(N):
        r = S.run(phase=p, minn=minn, eq0=142.0, **cfg, **des)
        m = window_metrics(r)
        e = r["expo"].loc[r["eq"].dropna().index]
        last = e.iloc[-365:]
        out.append(dict(cagr=m["cagr"], mdd=m["mdd"], imdd=m["imdd"], calmar=m["calmar"], end_usdt=float(r["eq"].dropna().iloc[-1]),
                        kills=r["kills"], skip=r["skip"], att=r["att"], flat=float((e == 0).mean()),
                        flat_last365=float((last == 0).mean()), liq=r["liq"], worst_day=m["worst_day"]))
    return {k: float(np.mean([o[k] for o in out])) for k in out[0]} | dict(imdd_wp=max(o["imdd"] for o in out),
                                                                           permflat_phases=sum(o["flat_last365"] > 0.9 for o in out), n_ph=N)


def main():
    S = Sim(load_panel())
    res = {}
    for minn in (5.0, 20.0):
        for cn, cfg in CFGS.items():
            print(f"\n=== {cn} | account 142 USDT, min notional {minn:g} ===")
            for dn, des in DESIGNS.items():
                m = evaluate(S, cfg, des, minn)
                res[f"{minn:g}|{cn}|{dn}"] = m
                print(f"  {dn:50s} CAGR {m['cagr']*100:6.1f}% closeMDD {m['mdd']*100:5.1f}% iMDD {m['imdd']*100:5.1f}% (wp {m['imdd_wp']*100:5.1f}) end {m['end_usdt']:8.1f} kills {m['kills']:.1f} flat {m['flat']*100:4.0f}% flat365 {m['flat_last365']*100:4.0f}% permflat {m['permflat_phases']}/{m['n_ph']} skip {m['skip']:.0f}/{m['att']:.0f}")
    json.dump(res, open("docs/research/final_design.json", "w"), default=float, indent=0)


if __name__ == "__main__":
    main()
