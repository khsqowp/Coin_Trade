"""상한가 따라잡기(급등 모멘텀) 전략 — 일봉 데이터로 근사.

실제 "상한가 따라잡기"는 장중 분봉 단위 진입(급등 초입 분할매수)이지만, 이번 스윕은 일봉
데이터만 있으므로 다음으로 근사한다: 전일 등락률이 ENTRY_GAP_PCT 이상인 종목을 익일 시가에
매수(backtesting.py의 next-bar-open 체결 방식과 정확히 맞아떨어짐), TP_PCT 익절 / SL_PCT
손절, MAX_HOLD_DAYS 초과 보유시 강제청산 — 사용자가 설명한 "급등 종목 올라타서 5% 먹고 익절,
3% 손절" 규칙 그대로.
"""
from __future__ import annotations

from backtesting import Strategy


def _risk_sized_fraction(entry: float, stop: float, risk_per_trade: float, max_fraction: float) -> float | None:
    stop_distance_pct = (entry - stop) / entry
    if stop_distance_pct <= 0:
        return None
    return min(risk_per_trade / stop_distance_pct, max_fraction)


class GapMomentumStrategy(Strategy):
    ENTRY_GAP_PCT = 0.10
    TP_PCT = 0.05
    SL_PCT = 0.03
    MAX_HOLD_DAYS = 5
    WARMUP_BARS = 5
    RISK_PER_TRADE = 0.0025
    MAX_POSITION_FRACTION = 0.95

    def init(self):
        self.entry_bar: int | None = None

    def next(self):
        i = len(self.data.Close) - 1
        if i < self.WARMUP_BARS:
            return

        close = self.data.Close[-1]

        if self.position:
            held = i - (self.entry_bar if self.entry_bar is not None else i)
            if held >= self.MAX_HOLD_DAYS:
                self.position.close()
                self.entry_bar = None
            return

        prev_close = self.data.Close[-2]
        day_return = (close - prev_close) / prev_close
        if day_return >= self.ENTRY_GAP_PCT:
            stop = close * (1 - self.SL_PCT)
            target = close * (1 + self.TP_PCT)
            fraction = _risk_sized_fraction(close, stop, self.RISK_PER_TRADE, self.MAX_POSITION_FRACTION)
            if fraction:
                self.buy(size=fraction, sl=stop, tp=target)
                self.entry_bar = i
