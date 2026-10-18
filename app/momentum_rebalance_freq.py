"""리밸런스 주기 스윕 — 모멘텀 로테이션(달러중립 롱숏)에서 리밸런스를 얼마나
자주 가져갈지 분석. 일봉 데이터라 최단 주기는 1일.

축:
  REBAL        : 리밸런스 간격(거래일)  1,2,3,4,5,7,10
  LOOKBACK     : 모멘텀 룩백(일)         7,10,14,21
  LEV          : 배율                    1x, 2x
  COST_PER_SIDE: 회전분 편도 비용(%)     0.04(수수료만), 0.10(수수료+슬리피지 현실치)

지표: CAGR, MDD, Calmar, Sharpe, 연 회전율, 비용드래그(연), 연도별 수익률.

실행: docker run --rm --entrypoint python -v .../trading/app:/app/app \
        ochestration-trading-momentum-rotation -m app.momentum_rebalance_freq
"""
from __future__ import annotations

import itertools

import numpy as np
import pandas as pd

from app.futures_data import fetch_perp_ohlcv
from app.futures_momentum_rotation_probe import SINCE, TOP_K, UNIVERSE

REBAL = [1, 2, 3, 4, 5, 7, 10]
LOOKBACK = [7, 10, 14, 21]
LEV = [1.0, 2.0]
COST_PER_SIDE = [0.04, 0.10]
MAINT_MARGIN = 0.005


def _load() -> pd.DataFrame:
    series = {}
    for base in UNIVERSE:
        try:
            fr = fetch_perp_ohlcv(f"{base}/USDT:USDT", "1d", SINCE, None)
        except Exception:  # noqa: BLE001
            continue
        if not fr.empty:
            series[base] = fr["Close"]
    return pd.DataFrame(series).sort_index()


def _sim(closes: pd.DataFrame, lookback: int, rebal: int, lev: float, cost_pct: float) -> dict:
    returns = closes.pct_change()
    momentum = closes.pct_change(lookback)
    dates = closes.index
    start = lookback + 1

    w = pd.Series(0.0, index=closes.columns)
    last_w = w.copy()
    equity, peak, mdd = 1.0, 1.0, 0.0
    daily, turnovers = [], []
    yearly: dict[int, float] = {}
    year_start = {}
    liq = None

    for i in range(start, len(dates)):
        d = dates[i]
        yr = d.year
        year_start.setdefault(yr, equity)

        g = (w * returns.loc[d].fillna(0.0)).sum() * lev
        if g <= -(1.0 / lev - MAINT_MARGIN) and liq is None:
            equity, liq = 0.0, d.date()
            break
        equity *= (1 + g)
        daily.append(g)
        peak = max(peak, equity)
        mdd = max(mdd, (peak - equity) / peak)
        yearly[yr] = equity / year_start[yr] - 1

        if (i - start) % rebal == 0:
            mom = momentum.loc[d].dropna()
            mom = mom[closes.loc[d].notna()]
            if len(mom) >= TOP_K * 2:
                ranked = mom.sort_values(ascending=False)
                nw = pd.Series(0.0, index=closes.columns)
                nw[ranked.index[:TOP_K]] = 0.5 / TOP_K
                nw[ranked.index[-TOP_K:]] = -0.5 / TOP_K
                turn = (nw - last_w).abs().sum()
                turnovers.append(turn)
                equity *= (1 - turn * cost_pct / 100 * lev)
                w, last_w = nw, nw.copy()

    years = (dates[-1] - dates[start]).days / 365.25
    cagr = (equity ** (1 / years) - 1) * 100 if equity > 0 else -100.0
    calmar = cagr / (mdd * 100) if mdd > 0 else float("inf")
    dr = pd.Series(daily)
    sharpe = float(dr.mean() / dr.std() * np.sqrt(365)) if dr.std() > 0 else 0.0
    ann_turn = float(np.sum(turnovers)) / years
    cost_drag = ann_turn * cost_pct / 100 * lev * 100
    return {"cagr": cagr, "mdd": mdd * 100, "calmar": calmar, "sharpe": sharpe,
            "ann_turn": ann_turn, "cost_drag": cost_drag, "liq": liq,
            "yearly": {y: round(v * 100, 1) for y, v in sorted(yearly.items())}}


def run() -> None:
    print("종가 수집...")
    closes = _load()
    d = closes.index
    print(f"유효 {closes.shape[1]}종목, {d[0].date()} ~ {d[-1].date()} ({closes.shape[0]}일)\n")

    rows = []
    for lb, rb, lv, c in itertools.product(LOOKBACK, REBAL, LEV, COST_PER_SIDE):
        r = _sim(closes, lb, rb, lv, c)
        r.update(lb=lb, rb=rb, lev=lv, cost=c)
        rows.append(r)

    for lv in LEV:
        for c in COST_PER_SIDE:
            print(f"=== 배율 {lv:.0f}x, 편도비용 {c:.2f}% (룩백 14일 고정) ===")
            print(f"{'리밸런스':>8} {'CAGR':>8} {'MDD':>7} {'Calmar':>7} {'Sharpe':>7} {'연회전율':>8} {'비용드래그':>9} {'청산':>8}")
            for rb in REBAL:
                r = next(x for x in rows if x["lb"] == 14 and x["rb"] == rb and x["lev"] == lv and x["cost"] == c)
                liq = str(r["liq"]) if r["liq"] else "-"
                print(f"{rb:>6}일 {r['cagr']:>+7.1f}% {r['mdd']:>6.1f}% {r['calmar']:>7.2f} "
                      f"{r['sharpe']:>7.2f} {r['ann_turn']:>7.1f}x {r['cost_drag']:>7.1f}%/y {liq:>8}")
            print()

    print("=== 룩백 x 리밸런스 Calmar 그리드 (2x, 편도 0.10%) ===")
    print(f"{'룩백\\리밸':>8} " + " ".join(f"{rb:>6}일" for rb in REBAL))
    for lb in LOOKBACK:
        cells = []
        for rb in REBAL:
            r = next(x for x in rows if x["lb"] == lb and x["rb"] == rb and x["lev"] == 2.0 and x["cost"] == 0.10)
            cells.append(f"{r['calmar']:>6.2f}" if r["liq"] is None else "  LIQ ")
        print(f"{lb:>6}일 " + " ".join(cells))
    print()

    print("=== 상위 8 조합 (2x, 편도 0.10%, Calmar 순, 청산 제외) ===")
    top = sorted([x for x in rows if x["lev"] == 2.0 and x["cost"] == 0.10 and x["liq"] is None],
                 key=lambda x: -x["calmar"])[:8]
    for r in top:
        print(f"  룩백{r['lb']:>2}/리밸{r['rb']:>2}일: CAGR {r['cagr']:>+6.1f}%, MDD {r['mdd']:>5.1f}%, "
              f"Calmar {r['calmar']:.2f}, Sharpe {r['sharpe']:.2f}  연도별 {r['yearly']}")

    cur = next(x for x in rows if x["lb"] == 14 and x["rb"] == 3 and x["lev"] == 2.0 and x["cost"] == 0.10)
    print(f"\n현재 운용(룩백14/리밸3일/2x/0.10%): CAGR {cur['cagr']:+.1f}%, MDD {cur['mdd']:.1f}%, "
          f"Calmar {cur['calmar']:.2f}, Sharpe {cur['sharpe']:.2f}")
    print(f"  연도별 {cur['yearly']}")
    print("\n가정: 펀딩비 무시(달러중립 근사상쇄), 슬리피지는 편도비용에 포함, 부분체결·최소주문 미반영.")


if __name__ == "__main__":
    run()
