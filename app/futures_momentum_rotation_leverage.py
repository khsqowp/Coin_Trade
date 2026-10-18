"""모멘텀 로테이션(14/3/8, 달러중립 롱숏)에 배율을 걸었을 때 위험/수익 곡선.

배율 L 은 일간 포트 수익률과 리밸런스 회전 수수료에 함께 곱해진다.
추가로 배율에 비례하는 펀딩비 드래그(연 FUNDING_DRAG_PCT_PER_X * (L-1))를 뺀다
— 달러중립 북이라 롱/숏 펀딩이 대체로 상쇄되지만 완전하진 않아서 보수적으로 잡는다.

청산 판정: 하루 손실이 1/L (초기증거금 소진)을 넘으면 그 시점에 계좌 전멸로 처리.

실행: docker run --rm --entrypoint python -v .../trading/app:/app/app \
        ochestration-trading-momentum-rotation -m app.futures_momentum_rotation_leverage
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.futures_data import fetch_perp_ohlcv
from app.futures_momentum_rotation_probe import (
    COMMISSION_PCT, MOMENTUM_LOOKBACK_DAYS, REBALANCE_EVERY_DAYS, SINCE, TOP_K, UNIVERSE,
)

LEVERAGES = [1.0, 1.5, 2.0, 2.5, 3.0, 4.0]
FUNDING_DRAG_PCT_PER_X = 4.0  # 배율 1 초과분마다 연 4% 드래그 가정(보수적)
MAINT_MARGIN = 0.005  # 유지증거금 0.5% (바이낸스 선물 대략치) → 청산 문턱 = (1/L - MAINT)


def _daily_port_returns() -> pd.Series:
    series = {}
    for base in UNIVERSE:
        try:
            fr = fetch_perp_ohlcv(f"{base}/USDT:USDT", "1d", SINCE, None)
        except Exception:  # noqa: BLE001
            continue
        if not fr.empty:
            series[base] = fr["Close"]
    closes = pd.DataFrame(series).sort_index()
    returns = closes.pct_change()
    momentum = closes.pct_change(MOMENTUM_LOOKBACK_DAYS)
    dates = closes.index
    start = MOMENTUM_LOOKBACK_DAYS + 1
    weights = pd.Series(0.0, index=closes.columns)
    last_w = weights.copy()
    port, turns = [], []
    for i in range(start, len(dates)):
        d = dates[i]
        port_ret = (weights * returns.loc[d].fillna(0.0)).sum()
        turn = 0.0
        if (i - start) % REBALANCE_EVERY_DAYS == 0:
            mom = momentum.loc[d].dropna()
            mom = mom[closes.loc[d].notna()]
            if len(mom) >= TOP_K * 2:
                ranked = mom.sort_values(ascending=False)
                nw = pd.Series(0.0, index=closes.columns)
                nw[ranked.index[:TOP_K]] = 0.5 / TOP_K
                nw[ranked.index[-TOP_K:]] = -0.5 / TOP_K
                turn = (nw - last_w).abs().sum()
                weights, last_w = nw, nw.copy()
        port.append(port_ret)
        turns.append(turn)
    idx = dates[start:len(dates)]
    return pd.Series(port, index=idx), pd.Series(turns, index=idx)


def _run(port: pd.Series, turns: pd.Series, lev: float) -> dict:
    years = (port.index[-1] - port.index[0]).days / 365.25
    fund_daily = (FUNDING_DRAG_PCT_PER_X / 100 * max(lev - 1, 0)) / 365
    liq_threshold = 1.0 / lev - MAINT_MARGIN

    equity, peak, mdd, worst = 1.0, 1.0, 0.0, 0.0
    liquidated_on = None
    curve = []
    for d in port.index:
        gross = port.loc[d] * lev - turns.loc[d] * COMMISSION_PCT / 100 * lev - fund_daily
        worst = min(worst, gross)
        if gross <= -liq_threshold and liquidated_on is None:
            equity = 0.0
            liquidated_on = d.date()
            curve.append((d, 0.0))
            break
        equity *= (1 + gross)
        peak = max(peak, equity)
        mdd = max(mdd, (peak - equity) / peak)
        curve.append((d, equity))

    eq = pd.Series([v for _, v in curve], index=[t for t, _ in curve])
    cagr = (equity ** (1 / years) - 1) * 100 if equity > 0 else -100.0
    dr = eq.pct_change().dropna()
    sharpe = float(dr.mean() / dr.std() * np.sqrt(365)) if dr.std() > 0 else 0.0
    return {"lev": lev, "cagr": cagr, "mdd": mdd * 100, "sharpe": sharpe,
            "worst_day": worst * 100, "liq": liquidated_on, "final_x": equity}


def run() -> None:
    print("모멘텀 로테이션(14/3/8) 종가 수집 + 일간 포트수익률 계산...")
    port, turns = _daily_port_returns()
    print(f"거래일 {len(port)}일 ({port.index[0].date()} ~ {port.index[-1].date()})\n")
    print(f"{'배율':>5} {'CAGR':>9} {'MDD':>7} {'Sharpe':>7} {'최악일':>8} {'청산':>12} {'$1만→':>10}")
    for lev in LEVERAGES:
        r = _run(port, turns, lev)
        liq = str(r["liq"]) if r["liq"] else "-"
        print(f"{lev:>5.1f} {r['cagr']:>+8.1f}% {r['mdd']:>6.1f}% {r['sharpe']:>7.2f} "
              f"{r['worst_day']:>+7.1f}% {liq:>12} ${10000*r['final_x']:>9,.0f}")
    print(f"\n가정: 배율 초과분당 펀딩드래그 연 {FUNDING_DRAG_PCT_PER_X}%, 유지증거금 {MAINT_MARGIN*100}%, "
          f"슬리피지·부분체결·펀딩 변동 미반영. 실측은 이보다 나쁨.")


if __name__ == "__main__":
    run()
