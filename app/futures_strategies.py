"""롱/숏 양방향 전략 — 지금까지 테스트한 모든 현물(스팟) 전략은 롱 온리였기 때문에 하락장을
"피하기만" 했지 실제로 숏으로 수익을 낼 수는 없었다. 이 전략은 무기한 스왑(perpetual futures)
데이터로 Supertrend 방향 전환마다 롱/숏을 오가는 stop-and-reverse 방식이라, 하락 추세에서도
실제로 포지션을 잡아 수익을 시도한다.

정직하게 명시할 한계: 펀딩비가 반영되지 않았다(app/futures_data.py 참고). 방향성 포지션을
오래 들고 있을 때 펀딩비가 수익을 상당히 갉아먹을 수 있어, 여기 나온 수익률은 실제보다
낙관적인 상한선으로 봐야 한다.
"""
from __future__ import annotations

from backtesting import Strategy


def _risk_sized_fraction(entry: float, stop: float, risk_per_trade: float, max_fraction: float) -> float | None:
    stop_distance_pct = abs(entry - stop) / entry
    if stop_distance_pct <= 0:
        return None
    return min(risk_per_trade / stop_distance_pct, max_fraction)


class LongShortTrendStrategy(Strategy):
    """Supertrend 방향 전환마다 롱/숏 전환 (stop-and-reverse) — Supertrend 라인이 트레일링 스톱 겸용.

    MIN_ADX_ENTRY: 방향 전환 시점의 추세 강도(ADX)가 이 값 미만이면 진입하지 않는다 — 약한/
    횡보성 상승장에서 숏에 걸렸다가 휩쏘 손실을 보는 것을 줄이기 위한 필터(1차 테스트에서
    XRP/HYPE처럼 강한 상승장에 숏이 걸려 손실 또는 큰 기회비용이 난 사례를 보고 추가)."""

    TIMEFRAME = "4h"
    RISK_PER_TRADE = 0.0025
    MAX_POSITION_FRACTION = 0.95
    WARMUP_BARS = 30
    MIN_ADX_ENTRY = 0  # 0이면 필터 비활성 (기존 동작과 동일)

    def init(self):
        pass

    def next(self):
        i = len(self.data.Close) - 1
        if i < self.WARMUP_BARS:
            return

        close = self.data.Close[-1]
        direction = self.data.SUPERTD[-1]
        direction_prev = self.data.SUPERTD[-2]
        supert_line = self.data.SUPERT[-1]
        adx = self.data.ADX14[-1]

        if self.position:
            for trade in self.trades:
                if self.position.is_long and (trade.sl is None or supert_line > trade.sl):
                    trade.sl = supert_line
                elif self.position.is_short and (trade.sl is None or supert_line < trade.sl):
                    trade.sl = supert_line

            flipped_against = (self.position.is_long and direction < 0) or (self.position.is_short and direction > 0)
            if flipped_against:
                self.position.close()
            else:
                return

        if adx < self.MIN_ADX_ENTRY:
            return

        flipped_bullish = direction_prev < 0 and direction > 0
        flipped_bearish = direction_prev > 0 and direction < 0

        if flipped_bullish and close > supert_line:
            fraction = _risk_sized_fraction(close, supert_line, self.RISK_PER_TRADE, self.MAX_POSITION_FRACTION)
            if fraction:
                self.buy(size=fraction, sl=supert_line)
        elif flipped_bearish and close < supert_line:
            fraction = _risk_sized_fraction(close, supert_line, self.RISK_PER_TRADE, self.MAX_POSITION_FRACTION)
            if fraction:
                self.sell(size=fraction, sl=supert_line)
