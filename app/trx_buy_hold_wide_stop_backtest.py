"""TRX '그냥 매수 + 느슨한 손절선 하나'만 있는 단순 전략 백테스트.

trx_dca_swing_backtest.py(분할매수+데드크로스손절+RSI익절)가 매수&보유(+342%)보다 훨씬
나쁘게 나온(+10.6%) 이유가 잦은 손절/익절이라고 판단해서, 변수를 하나만 바꿔 테스트한다:
  - 진입: EMA9/EMA21 골든크로스에서 전액 매수(분할매수 없음, 익절 없음)
  - 청산: 오직 매수가 대비 -STOP_LOSS_PCT% 하락 시에만 전량 손절(추세지표 기반 잦은 손절 제거)
  - 손절 이후에는 다음 골든크로스에서 재진입(복리)
"""
from __future__ import annotations

import pandas as pd

from app.data import fetch_ohlcv
from app.more_indicators import add_ema_cross_indicators

SYMBOL = "TRX/USDT"
SINCE = "2022-01-01T00:00:00Z"
INITIAL_CAPITAL_USDT = 100.0
STOP_LOSS_PCT = 12.0
FEE_PCT = 0.1


def run() -> None:
    print(f"[1/2] {SYMBOL} 일봉 수집 (since {SINCE})...")
    frame = fetch_ohlcv(SYMBOL, "1d", SINCE, None)
    frame = add_ema_cross_indicators(frame).dropna(subset=["EMA9", "EMA21"]).copy()
    print(f"  사용 가능 봉수: {len(frame)} ({frame.index[0].date()} ~ {frame.index[-1].date()})")

    print(f"[2/2] 매수+손절선(-{STOP_LOSS_PCT:.0f}%)만 있는 단순 전략 시뮬레이션...")
    cash = INITIAL_CAPITAL_USDT
    qty = 0.0
    entry_price: float | None = None

    ema9, ema21, close = frame["EMA9"], frame["EMA21"], frame["Close"]
    daily_equity = []
    trade_log = []
    prev_ema9, prev_ema21 = ema9.iloc[0], ema21.iloc[0]

    for i in range(1, len(frame)):
        date = frame.index[i]
        price = close.iloc[i]
        cur_ema9, cur_ema21 = ema9.iloc[i], ema21.iloc[i]
        crossed_up = prev_ema9 <= prev_ema21 and cur_ema9 > cur_ema21

        if qty > 0:
            if price <= entry_price * (1 - STOP_LOSS_PCT / 100):
                proceeds = qty * price * (1 - FEE_PCT / 100)
                cash += proceeds
                trade_log.append((date, f"손절(-{STOP_LOSS_PCT:.0f}%)", price, proceeds))
                qty = 0.0
                entry_price = None
        else:
            if crossed_up:
                buy_qty = cash * (1 - FEE_PCT / 100) / price
                qty = buy_qty
                entry_price = price
                trade_log.append((date, "매수(전액)", price, -cash))
                cash = 0.0

        total_equity = cash + qty * price
        daily_equity.append((date, total_equity))
        prev_ema9, prev_ema21 = cur_ema9, cur_ema21

    equity_series = pd.Series({d: e for d, e in daily_equity}).sort_index()

    quarterly = equity_series.resample("QE").last()
    quarterly_prev = quarterly.shift(1)
    quarterly_prev.iloc[0] = INITIAL_CAPITAL_USDT
    quarterly_return_pct = (quarterly / quarterly_prev - 1) * 100

    print(f"\n[TRX 매수+느슨한손절(-{STOP_LOSS_PCT:.0f}%) 전략 — 분기별 결과, 시작자본 ${INITIAL_CAPITAL_USDT:.0f}]")
    print(f"{'분기':<8} {'분기말 자본($)':>14} {'분기 수익률(%)':>14}")
    for q, eq in quarterly.items():
        ret = quarterly_return_pct[q]
        print(f"{str(q.to_period('Q')):<8} {eq:>14,.2f} {ret:>+13.2f}%")

    total_return_pct = (equity_series.iloc[-1] / INITIAL_CAPITAL_USDT - 1) * 100
    years = (equity_series.index[-1] - equity_series.index[0]).days / 365.25
    annualized_pct = ((equity_series.iloc[-1] / INITIAL_CAPITAL_USDT) ** (1 / years) - 1) * 100 if years > 0 else float("nan")
    peak = equity_series.cummax()
    dd = (peak - equity_series) / peak
    max_dd_pct = dd.max() * 100

    wins = quarterly_return_pct[quarterly_return_pct > 0]
    losses = quarterly_return_pct[quarterly_return_pct < 0]
    n_stops = sum(1 for _, a, _, _ in trade_log if a.startswith("손절"))

    print(f"\n[요약]")
    print(f"  기간: {equity_series.index[0].date()} ~ {equity_series.index[-1].date()} ({years:.1f}년, {len(quarterly)}개 분기)")
    print(f"  총수익률 {total_return_pct:+.1f}%, 연환산 {annualized_pct:+.2f}%, 최대낙폭 {max_dd_pct:.1f}%")
    print(f"  분기 승률 {len(wins)/len(quarterly_return_pct)*100:.1f}% ({len(wins)}/{len(quarterly_return_pct)}), "
          f"평균 상승분기 {wins.mean():+.2f}%" + (f", 평균 하락분기 {losses.mean():+.2f}%" if len(losses) else ""))
    print(f"  분기수익률 표준편차(금액 편차): {quarterly_return_pct.std():.2f}%")
    print(f"  최종 자본: ${equity_series.iloc[-1]:,.2f} (매매 {len(trade_log)}건, 그중 손절 {n_stops}건)")
    print(f"\n  참고 — 순수 매수&보유(무손절): +342.0% 총수익률, 최대낙폭 51.1%")

    print(f"\n[매매 로그 전체]")
    for date, action, price, amount in trade_log:
        print(f"  {date.date()} {action:<12} @ {price:.5f}  {amount:+.2f}")


if __name__ == "__main__":
    run()
