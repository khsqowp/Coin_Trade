"""TRX 전용 분할매수 + 추세이탈 손절 + 과열 되돌림 익절 전략 백테스트.

규칙(사용자 확정):
  - 진입: EMA9가 EMA21을 상향돌파(골든크로스)하면 1차 매수(전체 가용자본의 1/5)
  - 분할매수: 마지막 매수가 대비 -3% 빠질 때마다 추가매수, 최대 5분할
  - 손절: EMA9가 EMA21을 하향돌파(데드크로스)하면 즉시 전량 매도(보유 중이면 언제든)
  - 익절: RSI14가 70 이상 과열된 뒤, 그 시점 이후 고점 대비 -3% 되돌리면 절반 매도.
    나머지 절반은 데드크로스가 나올 때까지 들고 가다가 그때 전량 정리(트레일링)
  - 매도로 회수된 현금은 그대로 다음 진입 때 재사용(복리) — 예산은 소진되지 않고 계속 순환

스팟 매매 가정 수수료 0.1%(편도, funding_arb 쪽과 동일 가정) 반영.
"""
from __future__ import annotations

import pandas as pd
import pandas_ta as ta

from app.data import fetch_ohlcv
from app.more_indicators import add_ema_cross_indicators

SYMBOL = "TRX/USDT"
SINCE = "2022-01-01T00:00:00Z"
INITIAL_CAPITAL_USDT = 100.0
N_TRANCHES = 5
DCA_DROP_PCT = 3.0
TAKE_PROFIT_RSI = 70.0
TAKE_PROFIT_RETRACE_PCT = 3.0
FEE_PCT = 0.1


def run() -> None:
    print(f"[1/2] {SYMBOL} 일봉 수집 (since {SINCE})...")
    frame = fetch_ohlcv(SYMBOL, "1d", SINCE, None)
    frame = add_ema_cross_indicators(frame)
    frame["RSI14"] = ta.rsi(frame["Close"], length=14)
    frame = frame.dropna(subset=["EMA9", "EMA21", "RSI14"]).copy()
    print(f"  사용 가능 봉수: {len(frame)} ({frame.index[0].date()} ~ {frame.index[-1].date()})")

    print(f"[2/2] 분할매수/손절/익절 시뮬레이션...")
    cash = INITIAL_CAPITAL_USDT
    qty = 0.0
    tranches_used = 0
    last_buy_price: float | None = None
    overbought_seen = False
    peak_since_overbought: float | None = None
    half_sold = False

    ema9 = frame["EMA9"]
    ema21 = frame["EMA21"]
    rsi = frame["RSI14"]
    close = frame["Close"]

    daily_equity = []
    trade_log = []

    prev_ema9, prev_ema21 = ema9.iloc[0], ema21.iloc[0]

    for i in range(1, len(frame)):
        date = frame.index[i]
        price = close.iloc[i]
        cur_ema9, cur_ema21 = ema9.iloc[i], ema21.iloc[i]
        cur_rsi = rsi.iloc[i]
        crossed_up = prev_ema9 <= prev_ema21 and cur_ema9 > cur_ema21
        crossed_down = prev_ema9 >= prev_ema21 and cur_ema9 < cur_ema21

        if qty > 0:
            if cur_rsi >= TAKE_PROFIT_RSI:
                overbought_seen = True
            if overbought_seen:
                peak_since_overbought = max(peak_since_overbought or price, price)

            if (overbought_seen and not half_sold and peak_since_overbought
                    and price <= peak_since_overbought * (1 - TAKE_PROFIT_RETRACE_PCT / 100)):
                sell_qty = qty / 2
                proceeds = sell_qty * price * (1 - FEE_PCT / 100)
                cash += proceeds
                qty -= sell_qty
                half_sold = True
                trade_log.append((date, "익절(절반)", price, proceeds))

            if crossed_down and qty > 0:
                proceeds = qty * price * (1 - FEE_PCT / 100)
                cash += proceeds
                trade_log.append((date, "손절/추세이탈(전량)", price, proceeds))
                qty = 0.0
                tranches_used = 0
                last_buy_price = None
                overbought_seen = False
                peak_since_overbought = None
                half_sold = False
            elif qty > 0 and tranches_used < N_TRANCHES and last_buy_price is not None \
                    and price <= last_buy_price * (1 - DCA_DROP_PCT / 100):
                total_equity_now = cash + qty * price
                tranche_amount = min(cash, total_equity_now / N_TRANCHES)
                if tranche_amount > 0:
                    buy_qty = tranche_amount * (1 - FEE_PCT / 100) / price
                    qty += buy_qty
                    cash -= tranche_amount
                    tranches_used += 1
                    last_buy_price = price
                    trade_log.append((date, f"분할매수({tranches_used}/{N_TRANCHES})", price, -tranche_amount))
        else:
            if crossed_up:
                tranche_amount = cash / N_TRANCHES
                buy_qty = tranche_amount * (1 - FEE_PCT / 100) / price
                qty += buy_qty
                cash -= tranche_amount
                tranches_used = 1
                last_buy_price = price
                overbought_seen = False
                peak_since_overbought = None
                half_sold = False
                trade_log.append((date, "진입(1/5)", price, -tranche_amount))

        total_equity = cash + qty * price
        daily_equity.append((date, total_equity))
        prev_ema9, prev_ema21 = cur_ema9, cur_ema21

    equity_series = pd.Series({d: e for d, e in daily_equity}).sort_index()

    # --- 분기별 표 ---
    quarterly = equity_series.resample("QE").last()
    quarterly_prev = quarterly.shift(1)
    quarterly_prev.iloc[0] = INITIAL_CAPITAL_USDT
    quarterly_return_pct = (quarterly / quarterly_prev - 1) * 100

    print(f"\n[TRX 분할매수/손절/익절 전략 — 분기별 결과, 시작자본 ${INITIAL_CAPITAL_USDT:.0f}]")
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

    print(f"\n[요약]")
    print(f"  기간: {equity_series.index[0].date()} ~ {equity_series.index[-1].date()} ({years:.1f}년, {len(quarterly)}개 분기)")
    print(f"  총수익률 {total_return_pct:+.1f}%, 연환산 {annualized_pct:+.2f}%, 최대낙폭 {max_dd_pct:.1f}%")
    print(f"  분기 승률 {len(wins)/len(quarterly_return_pct)*100:.1f}% ({len(wins)}/{len(quarterly_return_pct)}), "
          f"평균 상승분기 {wins.mean():+.2f}%" + (f", 평균 하락분기 {losses.mean():+.2f}%" if len(losses) else ""))
    print(f"  분기수익률 표준편차(금액 편차): {quarterly_return_pct.std():.2f}% (${INITIAL_CAPITAL_USDT*quarterly_return_pct.std()/100:.2f})")
    print(f"  최종 자본: ${equity_series.iloc[-1]:,.2f} (매매 {len(trade_log)}건)")

    print(f"\n[매매 로그 최근 15건]")
    for date, action, price, amount in trade_log[-15:]:
        print(f"  {date.date()} {action:<16} @ {price:.5f}  {amount:+.2f}")


if __name__ == "__main__":
    run()
