"""Offline map: 'old docs vs fair harness' table for named legacy configurations (selection window only)."""
from __future__ import annotations
import json, os, sys
import pandas as pd, numpy as np
from app.rs_map_off_data import SCRATCH
OUT = os.path.join(SCRATCH, "mapoff")
DOCS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "research")
# (label, family, params subset (all must match), old-doc claim "cagr/mdd", old conditions)
LEG = [
    ("Donchian70/25 +BTC히스테리시스(R14)", "a_donchian_btc_hysteresis", dict(lookback=70, hold_days=25, btc_hysteresis=0.03), "68.6/35.9", "롱전용 0.04% 그로스"),
    ("거래량폭증 챔피언 3x/무반응/20일", "c_volume_surge", dict(volume_multiple=3.0, hold_days=20), "62.4/53.4", "롱전용 0.04%"),
    ("하이킨아시 기본(20일보유)", "b_heikin_ashi", dict(hold_days=20, stop="none", tp=0.0, confirmation=0), "71.3/72.2", "롱전용 0.04%"),
    ("FRVP 기본(20일보유)", "b_frvp", dict(hold_days=20, stop="none", tp=0.0, confirmation=0), "67.5/73.1", "롱전용 0.04%"),
    ("VWAP 기본(20일보유)", "b_vwap", dict(hold_days=20, stop="none", tp=0.0, confirmation=0), "108/87", "롱전용 0.04%"),
    ("TRX 골든크로스+와이드스탑 9/21/12%", "c_trx_ema_wide", dict(fast=9, slow=21, stop_pct=12.0), "37.9/51.1(TRX 단일)", "단일종목 0.05%"),
]


def reconcile():
    """closest-to-original construction (long-only top-8 slots, daily, NO BTC gate) for the named configs, two windows x two cost models"""
    import numpy as np
    from app.rs_map_off_data import load_data
    from app.rs_map_off_core import Ctx, w_topn_gate, w_longonly_ew, run_w, rets, mets
    from app.rs_map_off_run import registry
    D = load_data(); cx = Ctx(D); reg = registry()
    i_a = int(cx.days.searchsorted(pd.Timestamp("2021-07-01", tz="UTC")))
    out = []
    for label, fam, pm, claim, cond in LEG:
        pos, st = reg[fam]["fn"](D, "1d", **pm)
        pos = np.asarray(pos, float); st = np.asarray(st, float)
        for cons, W in (("top8_nogate", w_topn_gate(cx, pos, st, 8, False, False)), ("EW", w_longonly_ew(cx, pos, False))):
            for cname, cost, fund in (("0.04%", 0.0004, 0), ("0.10%+fund", 0.001, 1)):
                row = dict(label=label, claim=claim, cons=cons, cost=cname)
                for wn, d0 in (("2021-07~2026-06", i_a), ("2022-01~2026-06", cx.d0)):
                    cx.d0 = d0
                    r = rets(run_w(cx, W, 1, 0, cost, fund, 0.0, 1.5, None, cx.d_hold))
                    m = mets(r, d0, cx.d_hold)
                    row[wn] = None if m is None else (round(100 * m["cagr"], 1), round(100 * m["mdd"], 1))
                out.append(row)
    json.dump(out, open(os.path.join(DOCS, "map_off_legacy_recon.json"), "w"), ensure_ascii=False, indent=1)
    for r in out:
        print(r)


def main():
    df = pd.read_csv(os.path.join(OUT, "cases.csv.gz"), usecols=["family", "tf", "params", "cons", "K", "cad", "wt", "mode", "cs", "cagr", "mdd", "calmar", "f1_calmar", "f2_calmar", "f3_calmar"])
    df["mode"] = df["mode"].fillna("")
    rows = []
    for label, fam, pm, claim, cond in LEG:
        g = df[(df.family == fam) & (df.tf == "1d")]
        g = g[g.params.map(lambda s: all(json.loads(s).get(k) == v for k, v in pm.items()))]
        if g.empty:
            rows.append(dict(label=label, note="params not in grid")); continue
        def pick(**q):
            h = g
            for k, v in q.items():
                h = h[h[k] == v]
            return h.iloc[0] if len(h) else None
        ew04 = pick(cons="LO_EW", cad=1, wt="ew", cs="c04|x1"); ew10 = pick(cons="LO_EW", cad=1, wt="ew", cs="c10F|x1")
        ls = pick(cons="LS", K=8, cad=3, cs="c10F|x1"); top = pick(cons="LO_TOPN", K=8, cad=1, wt="ew", cs="c10F|x1")
        f = lambda r: None if r is None else (round(100 * r.cagr, 1), round(100 * r.mdd, 1), round(r.calmar, 2))
        rows.append(dict(label=label, claim=claim, cond=cond, ew04=f(ew04), ew10F=f(ew10), top8_gate_10F=f(top), ls_k8_3d_10F=f(ls)))
    json.dump(rows, open(os.path.join(DOCS, "map_off_legacy.json"), "w"), ensure_ascii=False, indent=1)
    for r in rows:
        print(r)


if __name__ == "__main__":
    main()
    reconcile()
