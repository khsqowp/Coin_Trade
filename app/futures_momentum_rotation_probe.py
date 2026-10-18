"""코인간 상대모멘텀 로테이션(선물 롱숏) — 개별종목 시계열 추세추종(EMA/MACD/Donchian)과는
전혀 다른 전략 계열. 매 리밸런스 시점에 최근 N일 수익률 기준 상위 K개 롱, 하위 K개 숏,
동일비중, 롱익스포저=숏익스포저(달러중립)로 유지한다.
"""
from __future__ import annotations

import pandas as pd

from app.futures_data import fetch_perp_ohlcv

UNIVERSE = [
    "BTC", "ETH", "BNB", "XRP", "SOL", "TRX", "DOGE", "ZEC", "LINK", "XMR",
    "ADA", "XLM", "BCH", "LTC", "HBAR", "AVAX", "SUI", "UNI", "NEAR",
    "TAO", "AAVE", "ONDO", "THETA", "DOT", "ENA", "WLD", "ICP", "ETC",
    "POL", "QNT", "ALGO", "ATOM", "RENDER", "JUP", "ARB", "FIL", "VET",
    "CAKE", "TON", "MKR", "LDO", "CRV", "INJ", "OP", "APT", "IMX", "STX",
]
SINCE = "2022-01-01T00:00:00Z"
# app/momentum_rotation_loop.py가 실제로 쓰는 값(파라미터 스윕에서 찾은 최적 조합)과 동일하게 맞춘다.
MOMENTUM_LOOKBACK_DAYS = 14
REBALANCE_EVERY_DAYS = 3
TOP_K = 8
COMMISSION_PCT = 0.04  # 왕복 아닌 편도, 리밸런스마다 회전분에 적용
START_CAPITAL_USDT = 10_000.0  # momentum_rotation_loop.py 기본 가상자본과 동일 — 금액 단위 통계 표시용


def _fetch_closes() -> pd.DataFrame:
    series = {}
    for base in UNIVERSE:
        try:
            frame = fetch_perp_ohlcv(f"{base}/USDT:USDT", "1d", SINCE, None)
        except Exception as exc:  # noqa: BLE001
            print(f"  {base:6}: 수집실패 ({exc})")
            continue
        if frame.empty:
            continue
        print(f"  {base:6}: {len(frame):5d}봉")
        series[base] = frame["Close"]
    return pd.DataFrame(series)


def run() -> None:
    print(f"[1/2] {len(UNIVERSE)}개 종목 종가 수집...")
    closes = _fetch_closes()
    closes = closes.sort_index()
    print(f"[2/2] 모멘텀 로테이션 시뮬레이션 (lookback {MOMENTUM_LOOKBACK_DAYS}일, "
          f"리밸런스 {REBALANCE_EVERY_DAYS}일마다, 상위/하위 {TOP_K}개)...")

    returns = closes.pct_change()
    momentum = closes.pct_change(MOMENTUM_LOOKBACK_DAYS)

    dates = closes.index
    start_idx = MOMENTUM_LOOKBACK_DAYS + 1
    weights = pd.Series(0.0, index=closes.columns)
    equity = 1.0
    equity_curve = []
    daily_returns = []
    peak = 1.0
    max_dd = 0.0
    last_rebalance_weights = weights.copy()
    n_rebalances = 0
    rebalance_equities = [1.0]  # 리밸런스 시점마다의 자본(직전 리밸런스 대비 구간수익률 계산용)

    for i in range(start_idx, len(dates)):
        date = dates[i]
        day_ret = returns.loc[date]
        port_ret = (weights * day_ret.fillna(0.0)).sum()
        equity *= (1 + port_ret)
        daily_returns.append(port_ret)
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / peak)
        equity_curve.append((date, equity))

        if (i - start_idx) % REBALANCE_EVERY_DAYS == 0:
            mom_today = momentum.loc[date].dropna()
            mom_today = mom_today[closes.loc[date].notna()]
            if len(mom_today) >= TOP_K * 2:
                ranked = mom_today.sort_values(ascending=False)
                longs = ranked.index[:TOP_K]
                shorts = ranked.index[-TOP_K:]
                new_weights = pd.Series(0.0, index=closes.columns)
                new_weights[longs] = 0.5 / TOP_K
                new_weights[shorts] = -0.5 / TOP_K
                turnover = (new_weights - last_rebalance_weights).abs().sum()
                equity *= (1 - turnover * COMMISSION_PCT / 100)
                weights = new_weights
                last_rebalance_weights = new_weights.copy()
                n_rebalances += 1
                rebalance_equities.append(equity)

    years = (dates[-1] - dates[start_idx]).days / 365.25
    total_return_pct = (equity - 1) * 100
    annualized_pct = ((equity) ** (1 / years) - 1) * 100 if years > 0 else float("nan")

    print(f"\n기간: {dates[start_idx].date()} ~ {dates[-1].date()} ({years:.1f}년), 리밸런스 {n_rebalances}회")
    print(f"총수익률 {total_return_pct:.1f}%, 연환산 {annualized_pct:.2f}%, 최대낙폭 {max_dd*100:.1f}%")

    # --- 승률/손실률/금액 편차 통계 ---
    period_returns = pd.Series(rebalance_equities).pct_change().dropna()
    wins = period_returns[period_returns > 0]
    losses = period_returns[period_returns < 0]
    win_rate = len(wins) / len(period_returns) * 100 if len(period_returns) else float("nan")
    loss_rate = len(losses) / len(period_returns) * 100 if len(period_returns) else float("nan")
    daily_returns_s = pd.Series(daily_returns)
    daily_vol_annualized_pct = daily_returns_s.std() * (365 ** 0.5) * 100

    print(f"\n[리밸런스 구간({REBALANCE_EVERY_DAYS}일) 단위 승/패 통계 — 총 {len(period_returns)}구간]")
    print(f"  승률 {win_rate:.1f}% ({len(wins)}구간) / 손실률 {loss_rate:.1f}% ({len(losses)}구간)")
    if len(wins):
        print(f"  평균 수익 구간: {wins.mean()*100:+.2f}% (금액 ${START_CAPITAL_USDT*wins.mean():+,.0f}), "
              f"최대 {wins.max()*100:+.2f}% (${START_CAPITAL_USDT*wins.max():+,.0f})")
    if len(losses):
        print(f"  평균 손실 구간: {losses.mean()*100:+.2f}% (금액 ${START_CAPITAL_USDT*losses.mean():+,.0f}), "
              f"최대 {losses.min()*100:+.2f}% (${START_CAPITAL_USDT*losses.min():+,.0f})")
    print(f"  구간수익률 표준편차(금액 편차): {period_returns.std()*100:.2f}% (${START_CAPITAL_USDT*period_returns.std():,.0f})")
    print(f"  일간수익률 연환산 변동성: {daily_vol_annualized_pct:.1f}%")
    print(f"  가상 시작자본 ${START_CAPITAL_USDT:,.0f} 기준 현재 자본: ${START_CAPITAL_USDT*equity:,.0f} "
          f"(누적손익 ${START_CAPITAL_USDT*(equity-1):+,.0f})")


if __name__ == "__main__":
    run()
