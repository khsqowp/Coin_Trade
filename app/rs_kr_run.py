"""KR 포팅 백테스트 실행기: python -m app.rs_kr_run  (trading/ 에서). API 호출 없음, 로컬 캐시만."""
from __future__ import annotations

import itertools
import json
import sys

import numpy as np
import pandas as pd

from app import rs_kr_data as D, rs_kr_engine as E, rs_kr_strats as S

OUT = sys.argv[1] if len(sys.argv) > 1 else "/tmp/rs_kr_results.json"


def windows(P, st):
    T = len(P.dates)
    n = T - st
    w22 = int(P.dates.searchsorted(pd.Timestamp("2022-01-03")))
    cut = st + int(0.6 * n)
    f = [st + int(i * n / 3) for i in range(4)]
    return {"FULL": (st, T - 1), "IS": (st, cut), "OOS": (cut, T - 1), "W22": (w22, T - 1),
            "F1": (f[0], f[1]), "F2": (f[1], f[2]), "F3": (f[2], T - 1)}


def summarize(res, P, W):
    out = {}
    for k, (a, b) in W.items():
        m = E.metrics(res, P, a, b)
        out[k] = {"cagr": m["cagr"], "mdd": m["mdd"], "calmar": m["calmar"]}
        if k in ("FULL", "W22"):
            out[k].update(worst=m["worst_year"], py=m["peryear"], turn=m["turnover_yr"], cost=m["cost_yr"],
                          win=m.get("win"), trades=m.get("trades"), exp=m.get("exposure"))
    return out


def lookahead_test(P, ind, st):
    """미래 가격을 흔들어도 그 이전 자산곡선이 불변이어야 한다."""
    import copy
    cut = len(P.dates) - 300
    t0 = S.momentum_target(P, ind, 20, 5, 3, "crash", start=st)
    base = E.run_weights(P, t0)["eq"].iloc[:cut]
    P2 = copy.copy(P)
    rng = np.random.default_rng(1)
    for name in ("o", "h", "l", "c"):
        a = getattr(P, name).copy(); a[cut + 1:] *= rng.uniform(0.5, 1.5, a[cut + 1:].shape)
        setattr(P2, name, a)
    ind2 = S.prep(P2)
    t1 = S.momentum_target(P2, ind2, 20, 5, 3, "crash", start=st)
    pert = E.run_weights(P2, t1)["eq"].iloc[:cut]
    sw, up, dn = None, None, None
    e1 = E.run_events(P, *S.sig_swing6(P, ind)[:1], S.sig_swing6(P, ind)[1], S.sig_swing6(P, ind)[2], 6, sl=.03, tp=.05)["eq"].iloc[:cut]
    s2 = S.sig_swing6(P2, ind2)
    e2 = E.run_events(P2, s2[0], s2[1], s2[2], 6, sl=.03, tp=.05)["eq"].iloc[:cut]
    return float(np.abs(base - pert).max()), float(np.abs(e1 - e2).max())


def main():
    P = D.load(); ind = S.prep(P)
    st = int(P.dates.searchsorted(pd.Timestamp("2018-11-01")))
    W = windows(P, st)
    R = {"meta": {"dates": [str(P.dates[st].date()), str(P.dates[-1].date())], "n_syms": len(P.syms),
                  "elig_now": int(P.elig[-1].sum()), "windows": {k: [str(P.dates[a].date()), str(P.dates[b].date())] for k, (a, b) in W.items()}}}
    R["meta"]["lookahead_maxdiff"] = lookahead_test(P, ind, st)
    # ---- 벤치마크
    j_sam = P.syms.index("005930")
    bm = {
        "EW_BH": E.run_weights(P, S.ew_target(P, 21, start=st)),
        "BIG10_BH": E.run_weights(P, S.ew_target(P, 21, top_by_value=10, start=st)),
        "SAMSUNG_BH": E.run_weights(P, S.buyhold_target(P, j_sam, st)),
    }
    R["bench"] = {k: summarize(v, P, W) for k, v in bm.items()}
    # ---- S1 그리드(롱온리) + 롱숏 참고
    s1 = {}
    for L, K, Rb, f in itertools.product((14, 20, 60, 120), (3, 5, 10), (3, 5, 21), ("none", "crash", "sma200", "both")):
        res = E.run_weights(P, S.momentum_target(P, ind, L, K, Rb, f, start=st))
        s1[f"L{L}_K{K}_R{Rb}_{f}"] = summarize(res, P, W)
    R["S1"] = s1
    ls = {}
    for L, K, Rb in itertools.product((14, 20, 60, 120), (3, 5, 10), (3, 5, 21)):
        res = E.run_weights(P, S.momentum_target(P, ind, L, K, Rb, "none", short=True, start=st), shorts=True)
        ls[f"LS_L{L}_K{K}_R{Rb}"] = summarize(res, P, W)
    R["S1_LS"] = ls
    # ---- 이벤트 전략들
    ev = {}
    def go(name, sig, slots, sl=None, tp=None):
        ent, ex, sc = sig
        ev[name] = summarize(E.run_events(P, ent, ex, sc, slots, sl=sl, tp=tp), P, W)
    trx = S.sig_trx(P, ind)
    for sl, slots in itertools.product((0.08, 0.12, 0.20), (20, len(P.syms))):
        go(f"S3_trx_sl{int(sl*100)}_slots{slots}", trx, slots, sl=sl)
    sw = S.sig_swing6(P, ind)
    for slots, (tp, sl) in itertools.product((3, 6, 10), ((0.05, 0.03), (0.08, 0.04), (0.10, 0.05))):
        go(f"S4_swing6_slots{slots}_tp{int(tp*100)}_sl{int(sl*100)}", sw, slots, sl=sl, tp=tp)
    m7 = S.sig_mach7(P, ind)
    for n in (3, 5, 8):
        go(f"S5_mach7_top{n}", m7, n, sl=0.08)
    sq = S.sig_squeeze(P, ind)
    for n in (3, 5, 8):
        go(f"S5_squeeze_top{n}", sq, n)
    for ma, n, vf in itertools.product((5, 10), (3, 5, 8), (True, False)):
        go(f"S5_pullback_sma{ma}_top{n}_vf{int(vf)}", S.sig_pullback(P, ind, ma, vf), n, sl=0.03, tp=0.06)
    R["EV"] = ev
    # ---- S6 오버레이: IS 칼마 1위 S1(롱온리, 미리 정한 규칙)
    best = max(s1, key=lambda k: np.nan_to_num(s1[k]["IS"]["calmar"], nan=-9))
    L, K, Rb, f = best.replace("L", "").replace("K", "").replace("R", "").split("_")
    tgt = S.momentum_target(P, ind, int(L), int(K), int(Rb), f, start=st)
    ov = {"BASE": s1[best]}
    ov["VOL15_cap1"] = summarize(E.run_weights(P, tgt, vol_target=0.15, vol_cap=1.0), P, W)
    ov["LOCK20_25_3d"] = summarize(E.run_weights(P, tgt, lock=(0.20, 0.25, 3)), P, W)
    ov["VOL15+LOCK"] = summarize(E.run_weights(P, tgt, vol_target=0.15, vol_cap=1.0, lock=(0.20, 0.25, 3)), P, W)
    R["S6"] = {"best_is": best, **ov}
    json.dump(R, open(OUT, "w"), default=float, ensure_ascii=False)
    print("saved", OUT, "best", best, "lookahead", R["meta"]["lookahead_maxdiff"])


if __name__ == "__main__":
    main()
