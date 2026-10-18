"""추가 전략 아키타입 — "다른 트레이딩 봇은 왜 수익률이 좋아 보이는가" 논의에 대응해 비교군을
넓힌다. 두 가지 다 스팟 롱 전용, 기존과 동일한 리스크 기반 포지션 사이징을 쓴다.

- SupertrendStrategy: 프리트레이드(freqtrade)·트레이딩뷰 커뮤니티에서 가장 흔히 쓰이는
  추세추종 지표 중 하나. Supertrend 라인 자체가 트레일링 스톱 역할을 겸한다.
- RangeReversionStrategy: 바이낸스/바이빗이 기본 제공하는 "그리드봇"의 단순화된 근사치.
  실제 그리드봇은 채널을 N개 레벨로 나눠 여러 포지션을 동시에 들고 각 레벨마다 사고팔지만,
  여기서는 한 번에 하나의 포지션만 들고 채널 하단에서 사서 중단에서 파는 것으로 단순화했다.
  이 단순화 때문에 실제 그리드봇 대비 회전율(거래 빈도)은 낮게 나올 것이다 — 정직하게 명시.
"""
from __future__ import annotations

from backtesting import Strategy


def _risk_sized_fraction(entry: float, stop: float, risk_per_trade: float, max_fraction: float) -> float | None:
    stop_distance_pct = (entry - stop) / entry
    if stop_distance_pct <= 0:
        return None
    return min(risk_per_trade / stop_distance_pct, max_fraction)


class SupertrendStrategy(Strategy):
    """Supertrend 상승 전환 시 진입, 하락 전환 또는 라인 이탈 시 청산 (라인 자체가 트레일링 스톱)."""

    TIMEFRAME = "4h"
    VOLUME_CONFIRM_MULTIPLIER = 0.0  # 0이면 거래량 필터 사실상 비활성
    RISK_PER_TRADE = 0.0025
    MAX_POSITION_FRACTION = 0.95
    WARMUP_BARS = 30

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

        if self.position:
            for trade in self.trades:
                if trade.sl is None or supert_line > trade.sl:
                    trade.sl = supert_line
            if direction < 0:
                self.position.close()
            return

        flipped_bullish = direction_prev < 0 and direction > 0
        if not flipped_bullish:
            return
        if self.VOLUME_CONFIRM_MULTIPLIER > 0 and self.data.Volume[-1] < self.data.VOL_MEDIAN20[-1] * self.VOLUME_CONFIRM_MULTIPLIER:
            return

        if close <= supert_line:
            return  # 방향은 전환됐는데 라인이 아직 종가보다 위 — 스톱 거리가 역전된 예외 케이스
        fraction = _risk_sized_fraction(close, supert_line, self.RISK_PER_TRADE, self.MAX_POSITION_FRACTION)
        if fraction:
            self.buy(size=fraction, sl=supert_line)


class RangeReversionStrategy(Strategy):
    """그리드봇 근사(단일 포지션 버전) — 채널 하단 근처에서 매수, 중단 근처에서 매도."""

    TIMEFRAME = "4h"
    ENTRY_BAND_PCT = 0.2   # 채널 하단에서 이 비율 안쪽이면 매수
    EXIT_BAND_PCT = 0.5    # 채널 중단(0.5)에서 매도
    STOP_ATR_MULT = 1.5    # 채널 하단을 이탈하면 손절
    RISK_PER_TRADE = 0.0025
    MAX_POSITION_FRACTION = 0.95
    WARMUP_BARS = 35

    def init(self):
        pass

    def next(self):
        i = len(self.data.Close) - 1
        if i < self.WARMUP_BARS:
            return

        close = self.data.Close[-1]
        upper = self.data.RANGE_UPPER[-1]
        lower = self.data.RANGE_LOWER[-1]
        atr = self.data.ATR14[-1]
        channel_width = upper - lower
        if channel_width <= 0:
            return
        exit_level = lower + self.EXIT_BAND_PCT * channel_width

        if self.position:
            if close >= exit_level:
                self.position.close()
            return

        entry_ceiling = lower + self.ENTRY_BAND_PCT * channel_width
        if close <= entry_ceiling:
            stop = lower - self.STOP_ATR_MULT * atr
            fraction = _risk_sized_fraction(close, stop, self.RISK_PER_TRADE, self.MAX_POSITION_FRACTION)
            if fraction:
                self.buy(size=fraction, sl=stop)
