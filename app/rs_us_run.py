"""US 주식 전략 이식 백테스트 러너. 실행: /opt/homebrew/bin/python3.12 -m app.rs_us_run
출력: 표(stdout) + 요약 JSON(스크래치 경로, env US_OUT). 로컬 KIS 캐시만 사용.
"""
from __future__ import annotations

import json
import os
import sys
import time

import numpy as np
import pandas as pd

from app.rs_us_engine import ANN, load_panel, metrics, rebase, run_slots, run_weights

FEE_KIS = 0.0036   # 편도: 수수료0.25 + 슬리피지0.03 + 환전(왕복0.15의 절반)0.075 + SEC/TAF 등 ~0.003
FEE_CHEAP = 0.0008  # 편도: 수수료0.05 + 슬리피지0.03 (USD 계좌, 환전 없음)
BORROW = 0.01       # 공매도 차입료 연 1% 가정
START_EVAL = "2019-01-02"
START_22 = "2022-01-03"

P = load_panel()
C = P["Close"]
DATES = C.index
Cv = C.values
R = C.pct_change().values
R0 = np.nan_to_num(R)
T, N = Cv.shape
AVAIL = ~np.isnan(R)

# 동일비중 지수(매일 재조정) — S&P500 대용 (SPY 로컬 없음)
idx_r = np.nanmean(np.where(AVAIL, R, np.nan), axis=0 if False else 1)
idx_r = np.nan_to_num(idx_r)
IDX = pd.Series(np.cumprod(1 + idx_r), index=DATES)
IDX_SMA200 = IDX.rolling(200).mean().values
IDX_RET14 = (IDX / IDX.shift(14) - 1).values

N_VARIANTS = 0


def series(eq: np.ndarray) -> pd.Series:
    return pd.Series(eq, index=DATES)


def mk(eq: pd.Series, tover=None, cost=None, start=START_EVAL) -> dict:
    s = rebase(eq, start)
    yrs = (s.index[-1] - s.index[0]).days / 365.25
    return metrics(s, None if tover is None else tover / yrs, None if cost is None else cost / yrs)


# ---------------------------------------------------------------- S1
def score_matrix(lb) -> np.ndarray:
    if lb == "12-1":
        return (C.shift(21) / C.shift(252) - 1).values
    return (C / C.shift(int(lb)) - 1).values


SCORES = {lb: score_matrix(lb) for lb in [14, 20, 60, 120, "12-1"]}


def s1_targets(score, cad, off, K, mode, flt=None, topn_weight=1.0):
    tgt = np.full((T, N), np.nan)
    base = np.zeros(N)
    prev_off = False
    for t in range(T):
        reb = (t % cad) == off
        if reb:
            sc = score[t]
            ok = ~np.isnan(sc)
            w = np.zeros(N)
            if ok.sum() >= 2 * K:
                order = np.argsort(np.where(ok, sc, -np.inf))[::-1]
                top = order[:K]
                if mode == "ls":
                    bot = np.argsort(np.where(ok, sc, np.inf))[:K]
                    w[top] = 0.5 / K
                    w[bot] = -0.5 / K
                else:
                    w[top] = 1.0 / K
            base = w
        offnow = False
        if flt == "idx200":
            offnow = bool(not np.isnan(IDX_SMA200[t]) and IDX.values[t] < IDX_SMA200[t])
        elif flt == "crash":
            offnow = bool(not np.isnan(IDX_RET14[t]) and IDX_RET14[t] <= -0.10)
        if reb or offnow != prev_off:
            tgt[t] = base * (0.0 if offnow else 1.0)
        prev_off = offnow
    return tgt


def run_s1(lb, cad, K, mode, flt, fee, elig=None):
    global N_VARIANTS
    N_VARIANTS += 1
    offs = sorted({0, cad // 3, (2 * cad) // 3})
    rets, tovs, costs = [], [], []
    for off in offs:
        sc = SCORES[lb] if elig is None else np.where(elig, SCORES[lb], np.nan)
        tgt = s1_targets(sc, cad, off, K, mode, flt)
        eq, tv, cs = run_weights(R0, tgt, fee, BORROW if mode == "ls" else 0.0)
        rets.append(np.diff(eq, prepend=1.0) / np.concatenate([[1.0], eq[:-1]]))
        tovs.append(tv)
        costs.append(cs)
    r = np.mean(rets, axis=0)
    return series(np.cumprod(1 + r)), float(np.mean(tovs)), float(np.mean(costs))


# ---------------------------------------------------------------- S3 / S4 / S5 support
def emas(span):
    return pd.DataFrame(Cv).ewm(span=span, adjust=False).mean().values


E9, E21 = emas(9), emas(21)
SMA200 = C.rolling(200).mean().values
SMA20 = C.rolling(20).mean().values
SMA5 = C.rolling(5).mean().values


def run_s3(fee, stop=0.12):
    """EMA9/21 골든크로스 진입, -12% 손절 또는 데드크로스 청산. 종목별 슬리브 동일비중."""
    sl_ret = np.zeros((T, N))
    ntr = 0
    for i in range(N):
        pos = False
        pend_in = pend_out = False
        ent = 0.0
        e = 1.0
        for t in range(1, T):
            c = Cv[t, i]
            if np.isnan(c):
                continue
            if pos:
                sl_ret[t, i] = R0[t, i]
            if pend_in and not pos:
                pos, ent, pend_in = True, c, False
                sl_ret[t, i] = -fee
                ntr += 1
            elif pend_out and pos:
                pos, pend_out = False, False
                sl_ret[t, i] = (sl_ret[t, i] or 0) - fee
            if np.isnan(E9[t - 1, i]) or np.isnan(E21[t - 1, i]):
                continue
            up = E9[t - 1, i] <= E21[t - 1, i] and E9[t, i] > E21[t, i]
            dn = E9[t, i] < E21[t, i]
            if pos and not pend_out and (dn or c <= ent * (1 - stop)):
                pend_out = True
            elif not pos and not pend_in and up and t - 1 >= 0:
                pend_in = True
    port = np.where(AVAIL.sum(axis=1) > 0, np.sum(np.where(AVAIL, sl_ret, 0), axis=1) / np.maximum(AVAIL.sum(axis=1), 1), 0)
    return series(np.cumprod(1 + port)), ntr


def cross_up(a, b):
    prev = np.vstack([np.full((1, N), np.nan), a[:-1]]), np.vstack([np.full((1, N), np.nan), b[:-1]])
    return (prev[0] <= prev[1]) & (a > b)


def run_s4(fee, slots=6, tp=0.05, sl=0.03, short=False):
    up = cross_up(E9, E21) & (Cv > SMA200)
    dn = cross_up(E21, E9) & (Cv < SMA200)
    score = np.abs(Cv - SMA200) / SMA200
    exit_long = (E9 < E21) & (np.vstack([np.full((1, N), np.nan), E9[:-1]]) >= np.vstack([np.full((1, N), np.nan), E21[:-1]]))
    exit_short = up if False else cross_up(E9, E21)
    eq, tr, tv, cs = run_slots(P, up, score, exit_long, slots, fee, sl_pct=sl, tp_pct=tp,
                               short=short, short_entry=dn if short else None,
                               short_exit=exit_short if short else None, borrow=BORROW)
    return series(eq), tr, tv, cs


def run_mach7(fee, slots, rs_lb=90):
    close = C
    f, m, s = emas(20), emas(50), emas(100)
    ex = emas(50)
    aligned = (f > m) & (m > s)
    dipped = (P["Low"].values <= f)
    dr = pd.DataFrame(dipped).rolling(5, min_periods=1).max().values.astype(bool)
    prevhigh = np.vstack([np.full((1, N), np.nan), P["High"].values[:-1]])
    reclaim = (Cv > f) & (Cv > prevhigh)
    entry = aligned & dr & reclaim
    stop = P["Low"].rolling(5, min_periods=1).min().values
    score = (C / C.shift(rs_lb) - 1).values
    eq, tr, tv, cs = run_slots(P, entry, score, Cv < ex, slots, fee, stop_px=stop, tp_rr=1.5)
    return series(eq), tr, tv, cs


def run_squeeze(fee, slots, rs_lb=90):
    gap = np.abs(SMA20 - SMA200) / SMA200 * 100
    sq = gap <= 3.0
    sqr = pd.DataFrame(sq).rolling(10, min_periods=1).max().values.astype(bool)
    a = SMA20 > SMA200
    crossed = a != np.vstack([np.full((1, N), False), a[:-1]])
    whip = pd.DataFrame(crossed).rolling(20, min_periods=1).sum().values > 3
    above20 = Cv > SMA20
    prev_a20 = np.vstack([np.full((1, N), False), above20[:-1]])
    entry = above20 & ~prev_a20 & (Cv > SMA200) & sqr & ~whip
    score = (C / C.shift(rs_lb) - 1).values
    eq, tr, tv, cs = run_slots(P, entry, score, ~above20, slots, fee)
    return series(eq), tr, tv, cs


def run_pullback(fee, slots, rs_lb=90):
    above = Cv > SMA5
    prev = np.vstack([np.full((1, N), False), above[:-1]])
    entry = above & ~prev & ~np.isnan(SMA5)
    score = (C / C.shift(rs_lb) - 1).values
    eq, tr, tv, cs = run_slots(P, entry, score, ~above, slots, fee, sl_pct=0.03, tp_pct=0.06)
    return series(eq), tr, tv, cs


# ---------------------------------------------------------------- overlays (S6)
def vol_target(eq: pd.Series, fee: float, target=0.15, cap=1.0, win=20):
    r = eq.pct_change().fillna(0)
    vol = r.rolling(win).std() * np.sqrt(ANN)
    sc = (target / vol).clip(upper=cap).fillna(cap)
    s = sc.shift(2).fillna(cap)  # t 종가 결정 → t+1 종가 체결 → t+2 수익부터 적용
    rr = s * r - fee * s.diff().abs().fillna(0)
    return (1 + rr).cumprod(), float(s.mean())


def profit_lock(eq: pd.Series, fee: float, gain=0.20, dd=0.25, pause=3):
    r = eq.pct_change().fillna(0).values
    shadow = 1.0
    base = peak = 1.0
    armed = False
    pause_left = 0
    out = np.zeros(len(r))
    prev_flat = False
    for t in range(len(r)):
        flat = pause_left > 0
        out[t] = (0.0 if flat else r[t]) - (fee if flat != prev_flat else 0.0)
        prev_flat = flat
        shadow *= 1 + r[t]
        if flat:
            pause_left -= 1
            if pause_left == 0:
                base = peak = shadow
                armed = False
            continue
        peak = max(peak, shadow)
        if not armed and shadow >= base * (1 + gain):
            armed = True
        if armed and shadow <= peak * (1 - dd):
            pause_left = pause
    return pd.Series(np.cumprod(1 + out), index=eq.index)


# ---------------------------------------------------------------- main
def fmt(m):
    return f"{m['cagr']*100:6.1f}% {m['mdd']*100:5.1f}% {m['calmar']:5.2f}"


def main():
    t0 = time.time()
    res: dict = {}
    # 벤치마크
    ew = IDX
    bh0 = (C.iloc[C.index.get_indexer([pd.Timestamp(START_EVAL)], method="bfill")[0]].notna())
    cols0 = list(C.columns[bh0.values])
    sub = C[cols0].loc[START_EVAL:]
    bh = (sub / sub.iloc[0]).mean(axis=1)  # 시작시점 종목 바이앤홀드(재조정 없음)
    bench = {"EW_daily_rebal": ew, "BH_noRebal": bh}
    for k, v in bench.items():
        res[f"BENCH {k}"] = {"full": mk(v), "y22": mk(v, start=START_22)}
        print(f"BENCH {k:16s} full {fmt(res[f'BENCH {k}']['full'])} | 2022+ {fmt(res[f'BENCH {k}']['y22'])}")
    print("data:", len(cols0), "symbols at start;", N, "total;", DATES[0].date(), "~", DATES[-1].date())

    # ---- S1 grid
    grid = []
    for lb in [14, 20, 60, 120, "12-1"]:
        for cad in [3, 5, 21]:
            for K in [5, 10]:
                for mode, flt in [("long", None), ("long", "idx200"), ("long", "crash"), ("ls", None)]:
                    grid.append((lb, cad, K, mode, flt))
    S1 = {}
    for g in grid:
        for fn, fee in [("kis", FEE_KIS), ("cheap", FEE_CHEAP)]:
            eq, tv, cs = run_s1(*g, fee)
            S1[(g, fn)] = (eq, tv, cs)
    print(f"S1 grid done {len(S1)} runs {time.time()-t0:.0f}s")

    split = DATES[int(len(DATES) * 0.0)]  # placeholder
    ev = DATES[DATES >= pd.Timestamp(START_EVAL)]
    cut = ev[int(len(ev) * 0.6)]
    print("IS/OOS cut:", cut.date())

    rows = []
    for (g, fn), (eq, tv, cs) in S1.items():
        full = mk(eq, tv, cs)
        is_ = mk(eq, start=START_EVAL, ) if False else metrics(rebase(eq, START_EVAL, str(cut.date())))
        oos = metrics(rebase(eq, str(cut.date())))
        y22 = mk(eq, tv, cs, START_22)
        rows.append({"g": g, "fee": fn, "full": full, "is": is_, "oos": oos, "y22": y22})
    res["S1_rows"] = [{"g": [str(x) for x in r["g"]], "fee": r["fee"], "full": {k: r["full"][k] for k in ("cagr", "mdd", "calmar", "turnover_x", "cost_drag")},
                       "is_calmar": r["is"]["calmar"], "oos": {k: r["oos"][k] for k in ("cagr", "mdd", "calmar")},
                       "y22": {k: r["y22"][k] for k in ("cagr", "mdd", "calmar")}} for r in rows]
    # 모드별 최고 (IS Calmar 기준 선택 → OOS 보고)
    print("\n== S1 선택(IS Calmar 1위, kis 비용) → OOS/전체/2022+ ==")
    picks = {}
    for tag, cond in [("long", lambda g: g[3] == "long" and g[4] is None), ("long+idx200", lambda g: g[4] == "idx200"),
                      ("long+crash", lambda g: g[4] == "crash"), ("long-short", lambda g: g[3] == "ls")]:
        for fn in ["kis", "cheap"]:
            cand = [r for r in rows if r["fee"] == fn and cond(r["g"])]
            best = max(cand, key=lambda r: r["is"].get("calmar", -9))
            picks[(tag, fn)] = best
            print(f"{tag:12s} {fn:5s} pick={best['g']} IS cal {best['is']['calmar']:.2f} | OOS {fmt(best['oos'])} | full {fmt(best['full'])} "
                  f"sh {best['full']['sharpe']:.2f} turn {best['full']['turnover_x']:.0f}x cost {best['full']['cost_drag']*100:.1f}%/y | 2022+ {fmt(best['y22'])}")
    res["S1_picks"] = {f"{k[0]}|{k[1]}": {"g": [str(x) for x in v["g"]], "full": {a: v["full"][a] for a in ("cagr", "mdd", "calmar", "turnover_x", "cost_drag", "worst_year", "worst_year_n", "months_up", "yearly")},
                                          "oos": {a: v["oos"][a] for a in ("cagr", "mdd", "calmar")},
                                          "y22": {a: v["y22"][a] for a in ("cagr", "mdd", "calmar")}} for k, v in picks.items()}
    # 전체 분포 (이웃 견고성)
    print("\n== S1 분포 (kis, long only no filter): CAGR 범위 ==")
    for lb in [14, 20, 60, 120, "12-1"]:
        v = [r for r in rows if r["fee"] == "kis" and r["g"][0] == lb and r["g"][3] == "long" and r["g"][4] is None]
        print(f"lb {lb:>5}: " + " ".join(f"c{r['g'][1]}K{r['g'][2]}={r['full']['cagr']*100:.0f}%" for r in v))
    posn = sum(1 for r in rows if r["fee"] == "kis" and r["full"]["cagr"] > mk(bh)["cagr"])
    print(f"S1 kis 변형 중 B&H(start-set) CAGR 초과: {posn}/{sum(1 for r in rows if r['fee']=='kis')}")

    # ---- 생존편향 점검: (a) 시점별 거래대금 상위30만 허용 (b) 사후 상위10 승자 제외
    print("\n== 생존편향 점검 (kis 비용, long-only K5, 월간/주간) ==")
    dv = (P["Close"] * P["Volume"]).rolling(60, min_periods=30).median()
    rk = dv.rank(axis=1, ascending=False)
    elig_a = (rk <= 30).values
    tot = (C.iloc[-1] / C.bfill().iloc[0]).sort_values(ascending=False)
    winners = list(tot.index[:10])
    elig_b = np.tile(~C.columns.isin(winners), (T, 1))
    bias = {}
    for nm, el in [("전체54", None), ("(a)시점별유동성상위30", elig_a), ("(b)사후승자10제외", elig_b)]:
        e = np.ones((T, N), bool) if el is None else el
        rr = np.where(AVAIL & e, R, np.nan)
        cnt = (AVAIL & e).sum(axis=1)
        br = np.where(cnt > 0, np.nansum(np.where(AVAIL & e, R, 0), axis=1) / np.maximum(cnt, 1), 0)
        bq = pd.Series(np.cumprod(1 + br), index=DATES)
        line = f"{nm:22s} EW벤치 {fmt(mk(bq))} |"
        bias[nm] = {"bench": mk(bq)["cagr"]}
        for lb, cad in [(120, 21), (60, 5), ("12-1", 21)]:
            eq, tv, cs = run_s1(lb, cad, 5, "long", None, FEE_KIS, el)
            m = mk(eq, tv, cs)
            line += f" {lb}/{cad}d:{m['cagr']*100:.0f}%/{m['mdd']*100:.0f}%"
            bias[nm][f"{lb}/{cad}"] = (m["cagr"], m["mdd"])
        print(line)
    res["bias"] = bias

    # ---- S2 crash filter alone on EW basket
    print("\n== S2 크래시필터 (동일비중 지수) ==")
    off = (IDX_RET14 <= -0.10)
    sig = pd.Series(off, index=DATES).shift(2).fillna(False).values  # 지연 체결
    rr = np.where(sig, 0.0, idx_r)
    s2 = pd.Series(np.cumprod(1 + rr), index=DATES)
    fl = np.abs(np.diff(np.concatenate([[0], sig.astype(float)]))).sum()
    res["S2_basket"] = {"full": mk(s2), "y22": mk(s2, start=START_22), "switches": float(fl), "off_days": int(sig.sum())}
    print("S2 on EW basket full", fmt(mk(s2)), "| 2022+", fmt(mk(s2, start=START_22)), "| off days", int(sig.sum()), "switches", fl)

    # ---- S3/S4/S5
    others = {}
    for fn, fee in [("kis", FEE_KIS), ("cheap", FEE_CHEAP)]:
        e, ntr = run_s3(fee)
        others[("S3 EMA9/21 -12%", fn)] = (e, None, None, ntr)
        e, tr, tv, cs = run_s4(fee)
        others[("S4 swing6 long", fn)] = (e, tr, tv, cs)
        e, tr, tv, cs = run_s4(fee, short=True)
        others[("S4 swing6 long+short", fn)] = (e, tr, tv, cs)
        for n in (5, 10):
            e, tr, tv, cs = run_mach7(fee, n)
            others[(f"S5 mach7 top{n}", fn)] = (e, tr, tv, cs)
            e, tr, tv, cs = run_squeeze(fee, n)
            others[(f"S5 squeeze top{n}", fn)] = (e, tr, tv, cs)
            e, tr, tv, cs = run_pullback(fee, n)
            others[(f"S5 pullback top{n}", fn)] = (e, tr, tv, cs)
    print("\n== S3/S4/S5 ==")
    res["others"] = {}
    for (name, fn), (e, tr, tv, cs) in others.items():
        yrs = (e.index[-1] - pd.Timestamp(START_EVAL)).days / 365.25
        tvx = tv / yrs if tv is not None and not isinstance(cs, int) else None
        csx = cs / yrs if tv is not None and not isinstance(cs, int) else None
        full, y22 = mk(e, tvx, csx), mk(e, tvx, csx, START_22)
        wr = float((tr > 0).mean()) if isinstance(tr, np.ndarray) and len(tr) else None
        ntr = len(tr) if isinstance(tr, np.ndarray) else cs
        print(f"{name:22s} {fn:5s} full {fmt(full)} | 2022+ {fmt(y22)} | trades {ntr} win {wr if wr is None else round(wr*100)}% "
              f"turn {tvx if tvx is None else round(tvx)}x cost {csx if csx is None else round(csx*100,1)}%/y worst {full['worst_year']*100:.0f}%({full['worst_year_n']})")
        res["others"][f"{name}|{fn}"] = {"full": {a: full[a] for a in ("cagr", "mdd", "calmar", "worst_year", "worst_year_n", "yearly")}, "y22": {a: y22[a] for a in ("cagr", "mdd", "calmar")},
                                          "trades": ntr, "win": wr, "turn": tvx, "cost": csx}

    # ---- S6 on best long-only S1 (IS pick, kis)
    print("\n== S6 오버레이 (S1 long-only IS 1위 위에) ==")
    for fn, fee in [("kis", FEE_KIS), ("cheap", FEE_CHEAP)]:
        base = picks[("long", fn)]
        eq = S1[(base["g"], fn)][0]
        vt, avg = vol_target(eq, fee)
        pl = profit_lock(eq, fee)
        both = profit_lock(vt, fee)
        for nm, e in [("base", eq), ("voltarget15", vt), ("profitlock", pl), ("vt+lock", both)]:
            m, m22 = mk(e), mk(e, start=START_22)
            print(f"{fn:5s} {nm:12s} full {fmt(m)} | 2022+ {fmt(m22)} | OOS {fmt(metrics(rebase(e, str(cut.date()))))}")
            res[f"S6|{fn}|{nm}"] = {"full": {a: m[a] for a in ("cagr", "mdd", "calmar")}, "y22": {a: m22[a] for a in ("cagr", "mdd", "calmar")}}

    # ---- folds for key strategies (kis)
    print("\n== 3 폴드 (연수익/최대낙폭) ==")
    edges = [ev[0]] + [ev[int(len(ev) * q)] for q in (1 / 3, 2 / 3)] + [ev[-1]]
    key = {"S1 long pick": S1[(picks[("long", "kis")]["g"], "kis")][0],
           "S1 long+idx200": S1[(picks[("long+idx200", "kis")]["g"], "kis")][0],
           "EW daily rebal": IDX, "B&H start-set": bh}
    for nm, e in key.items():
        out = []
        for a, b in zip(edges[:-1], edges[1:]):
            m = metrics(rebase(e, str(a.date()), str(b.date())))
            out.append(f"{m['cagr']*100:5.1f}%/{m['mdd']*100:4.1f}%")
        print(f"{nm:18s} " + " | ".join(out))
    print("folds:", [str(d.date()) for d in edges])

    # ---- yearly for key
    print("\n== 연도별 ==")
    for nm, e in {**key}.items():
        y = mk(e)["yearly"]
        print(f"{nm:18s} " + " ".join(f"{k}:{v*100:+.0f}%" for k, v in y.items()))

    # ---- 다중검정 보정
    nv = len(grid) * 1 + len(others) // 2 + 4
    yrs = (DATES[-1] - pd.Timestamp(START_EVAL)).days / 365.25
    hair = np.sqrt(2 * np.log(nv)) / np.sqrt(yrs)
    print(f"\n시도한 변형 수 ~{nv}, 샤프 보정치(무작위 최대 샤프 기대) ≈ {hair:.2f}")
    res["n_variants"] = nv
    res["sharpe_haircut"] = float(hair)
    out = os.environ.get("US_OUT", "/tmp/rs_us_results.json")
    json.dump(res, open(out, "w"), default=lambda o: float(o) if isinstance(o, (np.floating, np.integer)) else str(o), ensure_ascii=False)
    print("saved", out, f"{time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
