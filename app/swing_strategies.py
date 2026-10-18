"""포지션/스윙 트레이딩 전략 — 보유기간 최소 며칠, 길면 수개월 목표로 재설계.

기존 app/strategy.py(15분봉), app/strategies.py(1h~4h)는 전부 보유기간이 시간~하루 단위로
캡핑되어 있어 "며칠~수개월" 요구에는 맞지 않는다. 여기 두 전략은 일봉(1d) 기준으로, 추세가
살아있는 한 트레일링 스톱으로 계속 들고 가는 구조라 자연스럽게 며칠~수개월 보유가 나온다.

- DonchianTrendStrategy: 터틀 트레이딩 시스템1 변형 (55일 고점 돌파 진입, 20일 저점 이탈 +
  ATR 샹들리에 트레일링 스톱). 추세추종 — 며칠 만에 손절될 수도, 수개월간 추세를 탈 수도 있음.
- MaPullbackSwingStrategy: SMA50>SMA200 상승 추세에서 RSI 눌림목 매수, SMA50 이탈 시 청산.
  추세 추종형 눌림목 매수 — 마찬가지로 보유기간이 추세 지속 기간에 따라 가변적.

둘 다 스팟 롱 전용, 기존 전략들과 동일한 리스크 기반 포지션 사이징을 쓴다.
"""
from __future__ import annotations

from backtesting import Strategy


def _risk_sized_fraction(entry: float, stop: float, risk_per_trade: float, max_fraction: float) -> float | None:
    stop_distance_pct = (entry - stop) / entry
    if stop_distance_pct <= 0:
        return None
    return min(risk_per_trade / stop_distance_pct, max_fraction)


class DonchianTrendStrategy(Strategy):
    """터틀 시스템1 변형 — 55일 고점 돌파 진입, 20일 저점 이탈 또는 ATR 트레일링 스톱 청산."""

    TIMEFRAME = "1d"
    USE_REGIME_FILTER = True
    STOP_ATR_MULT = 2.0
    TRAIL_ATR_MULT = 3.0
    RISK_PER_TRADE = 0.0025
    MAX_POSITION_FRACTION = 0.95
    WARMUP_BARS = 210  # SMA200 + 여유

    def init(self):
        self.highest_close_since_entry: float | None = None

    def next(self):
        i = len(self.data.Close) - 1
        if i < self.WARMUP_BARS:
            return

        close = self.data.Close[-1]
        atr = self.data.ATR14[-1]

        if self.position:
            self.highest_close_since_entry = max(self.highest_close_since_entry or close, close)
            trailing_stop = self.highest_close_since_entry - self.TRAIL_ATR_MULT * atr
            for trade in self.trades:
                if trade.sl is None or trailing_stop > trade.sl:
                    trade.sl = trailing_stop
            if close < self.data.DONCHIAN_LOW[-2]:
                self.position.close()
                self.highest_close_since_entry = None
            return

        if self.USE_REGIME_FILTER and close < self.data.SMA200[-1]:
            return  # 200일선 아래에서는 신규 진입 보류

        if close > self.data.DONCHIAN_HIGH[-2]:
            stop = close - self.STOP_ATR_MULT * atr
            fraction = _risk_sized_fraction(close, stop, self.RISK_PER_TRADE, self.MAX_POSITION_FRACTION)
            if fraction:
                self.buy(size=fraction, sl=stop)
                self.highest_close_since_entry = close


class MaPullbackSwingStrategy(Strategy):
    """SMA50>SMA200 상승 추세에서 RSI 눌림목 매수 — 추세 유지되는 한 계속 보유."""

    TIMEFRAME = "1d"
    RSI_ENTRY = 35
    STOP_ATR_MULT = 2.5
    RISK_PER_TRADE = 0.0025
    MAX_POSITION_FRACTION = 0.95
    WARMUP_BARS = 210

    def init(self):
        pass

    def next(self):
        i = len(self.data.Close) - 1
        if i < self.WARMUP_BARS:
            return

        close = self.data.Close[-1]
        sma50 = self.data.SMA50[-1]
        sma200 = self.data.SMA200[-1]
        rsi14 = self.data.RSI14[-1]
        atr = self.data.ATR14[-1]

        if self.position:
            if close < sma50:
                self.position.close()
            return

        if close > sma50 > sma200 and rsi14 < self.RSI_ENTRY:
            stop = close - self.STOP_ATR_MULT * atr
            fraction = _risk_sized_fraction(close, stop, self.RISK_PER_TRADE, self.MAX_POSITION_FRACTION)
            if fraction:
                self.buy(size=fraction, sl=stop)


class MaPullbackFastSwingStrategy(MaPullbackSwingStrategy):
    """거래빈도를 높인 변형 — 200일선 필터를 빼고(50일선만 확인) RSI(7)로 더 잦은 눌림목을 잡는다."""

    RSI_ENTRY = 45

    def next(self):
        i = len(self.data.Close) - 1
        if i < self.WARMUP_BARS:
            return

        close = self.data.Close[-1]
        sma50 = self.data.SMA50[-1]
        rsi7 = self.data.RSI7[-1]
        atr = self.data.ATR14[-1]

        if self.position:
            if close < sma50:
                self.position.close()
            return

        if close > sma50 and rsi7 < self.RSI_ENTRY:
            stop = close - self.STOP_ATR_MULT * atr
            fraction = _risk_sized_fraction(close, stop, self.RISK_PER_TRADE, self.MAX_POSITION_FRACTION)
            if fraction:
                self.buy(size=fraction, sl=stop)
