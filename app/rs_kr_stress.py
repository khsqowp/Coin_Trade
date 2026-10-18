"""생존편향/승자의존 스트레스: (a) 사후 최고수익 상위 N종목 제거, (b) 무작위 50% 부분유니버스."""
from __future__ import annotations

import copy
import json
import sys

import numpy as np
import pandas as pd

from app import rs_kr_data as D, rs_kr_engine as E, rs_kr_strats as S

CFG = [("60/3/21 +필터(둘다)", 60, 3, 21, "both"), ("60/5/21 +필터(둘다)", 60, 5, 21, "both"),
       ("120/5/21 급락필터", 120, 5, 21, "crash"), ("60/5/21 필터없음", 60, 5, 21, "none"),
       ("14/5/3 필터없음(코인식)", 14, 5, 3, "none"), ("14/5/3 급락필터", 14, 5, 3, "crash")]


def sub(P, keep):
    Q = copy.copy(P); m = np.zeros(P.elig.shape[1], bool); m[keep] = True
    Q.elig = P.elig & m[None, :]
    return Q


def evalset(Q, st, T):
    ind = S.prep(Q)
    ew = E.metrics(E.run_weights(Q, S.ew_target(Q, 21, start=st)), Q, st, T - 1)
    out = [ew]
    for _, L, K, Rb, f in CFG:
        r = E.run_weights(Q, S.momentum_target(Q, ind, L, K, Rb, f, start=st))
        out.append(E.metrics(r, Q, st, T - 1))
    return out


def main():
    P = D.load(); T = len(P.dates)
    st = int(P.dates.searchsorted(pd.Timestamp("2018-11-01")))
    tot = np.nan_to_num(pd.DataFrame(P.c).ffill().iloc[-1].to_numpy() / pd.DataFrame(P.c).bfill().iloc[st].to_numpy())
    order = np.argsort(-tot)
    res = {}
    for drop in (0, 5, 10):
        keep = [j for j in range(len(P.syms)) if j not in set(order[:drop])]
        res[f"drop{drop}"] = [(m["cagr"], m["mdd"]) for m in evalset(sub(P, keep), st, T)]
    rng = np.random.default_rng(7)
    rs = []
    for _ in range(30):
        keep = rng.choice(len(P.syms), len(P.syms) // 2, replace=False)
        rs.append([(m["cagr"], m["mdd"]) for m in evalset(sub(P, keep), st, T)])
    res["random50"] = rs
    res["top_winners"] = [P.syms[j] for j in order[:10]]
    json.dump(res, open(sys.argv[1], "w"), default=float)
    names = ["EW"] + [c[0] for c in CFG]
    for k in ("drop0", "drop5", "drop10"):
        print(k, [f"{n}:{c*100:.0f}%/{m*100:.0f}" for n, (c, m) in zip(names, res[k])])
    arr = np.array(rs)  # 30 x 7 x 2
    ew = arr[:, 0, 0]
    for i, n in enumerate(names[1:], 1):
        ex = arr[:, i, 0] - ew
        print(f"random50 {n}: median CAGR {np.median(arr[:, i, 0])*100:.0f}% (EW {np.median(ew)*100:.0f}%), 초과 중앙 {np.median(ex)*100:+.0f}%p, 이긴 비율 {np.mean(ex>0):.0%}, 최대낙폭 중앙 {np.median(arr[:, i, 1])*100:.0f}%")
    print("top winners", res["top_winners"])


if __name__ == "__main__":
    main()
