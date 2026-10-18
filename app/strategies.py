"""Comparison strategy archetypes, sourced from a survey of popular open-source
crypto trading bots (freqtrade community strategies, Jesse's example strategies) —
see docs/trading-agent-plan.md history for the research summary. These exist to give
RegimeSwitchStrategy (app/strategy.py) real competition rather than assuming it's the
right approach by default.

All of these are long-only (spot, no shorting) and use the same risk-based fractional
position sizing idea as RegimeSwitchStrategy: risk a fixed fraction of equity per
trade, sized off the distance to the stop-loss.
"""
from __future__ import annotations

from backtesting import Strategy


def _risk_sized_fraction(entry: float, stop: float, risk_per_trade: float, max_fraction: float) -> float | None:
    stop_distance_pct = (entry - stop) / entry
    if stop_distance_pct <= 0:
        return None
    return min(risk_per_trade / stop_distance_pct, max_fraction)


class EmaCrossStrategy(Strategy):
    """EMA9/21 골든크로스 + SMA200 추세 필터 — freqtrade 커뮤니티에서 가장 흔한 아키타입."""

    TIMEFRAME = "4h"
    STOP_PCT = 0.02
    WARMUP_BARS = 200
    RISK_PER_TRADE = 0.0025
    MAX_POSITION_FRACTION = 0.95

    def init(self):
        pass

    def next(self):
        i = len(self.data.Close) - 1
        if i < self.WARMUP_BARS:
            return

        ema9, ema9_prev = self.data.EMA9[-1], self.data.EMA9[-2]
        ema21, ema21_prev = self.data.EMA21[-1], self.data.EMA21[-2]
        close = self.data.Close[-1]
        sma200 = self.data.SMA200[-1]
        crossed_up = ema9_prev <= ema21_prev and ema9 > ema21
        crossed_down = ema9_prev >= ema21_prev and ema9 < ema21

        if self.position:
            if crossed_down or close < sma200:
                self.position.close()
            return

        if crossed_up and close > sma200:
            stop = close * (1 - self.STOP_PCT)
            fraction = _risk_sized_fraction(close, stop, self.RISK_PER_TRADE, self.MAX_POSITION_FRACTION)
            if fraction:
                self.buy(size=fraction, sl=stop)


class Rsi2MeanReversionStrategy(Strategy):
    """Larry Connors RSI(2) 평균회귀 — 장기 추세(SMA200) 방향에서만 단기 과매도 반등을 노림."""

    TIMEFRAME = "4h"
    STOP_ATR_MULT = 1.5
    MAX_HOLD_BARS = 42  # 4시간봉 기준 약 7일
    WARMUP_BARS = 200
    RSI_ENTRY = 10
    RSI_EXIT = 70
    RISK_PER_TRADE = 0.0025
    MAX_POSITION_FRACTION = 0.95

    def init(self):
        self.entry_bar: int | None = None

    def next(self):
        i = len(self.data.Close) - 1
        if i < self.WARMUP_BARS:
            return

        close = self.data.Close[-1]
        sma200 = self.data.SMA200[-1]
        sma5 = self.data.SMA5[-1]
        rsi2 = self.data.RSI2[-1]
        atr = self.data.ATR14[-1]

        if self.position:
            held = i - (self.entry_bar if self.entry_bar is not None else i)
            if close > sma5 or rsi2 > self.RSI_EXIT or held >= self.MAX_HOLD_BARS:
                self.position.close()
                self.entry_bar = None
            return

        if rsi2 < self.RSI_ENTRY and close > sma200:
            stop = close - self.STOP_ATR_MULT * atr
            fraction = _risk_sized_fraction(close, stop, self.RISK_PER_TRADE, self.MAX_POSITION_FRACTION)
            if fraction:
                self.buy(size=fraction, sl=stop)
                self.entry_bar = i


class BollingerMacdStrategy(Strategy):
    """볼린저밴드 + MACD + ADX — freqtrade의 Quickie/SmoothOperator 계열 근사."""

    TIMEFRAME = "4h"
    STOP_ATR_MULT = 2.5
    ADX_ENTRY_MIN = 30
    ADX_EXIT_MAX = 70
    WARMUP_BARS = 40
    RISK_PER_TRADE = 0.0025
    MAX_POSITION_FRACTION = 0.95

    def init(self):
        pass

    def next(self):
        i = len(self.data.Close) - 1
        if i < self.WARMUP_BARS:
            return

        close = self.data.Close[-1]
        adx = self.data.ADX14[-1]
        macd = self.data.MACD[-1]
        macd_signal = self.data.MACD_SIGNAL[-1]
        bb_lower = self.data.BB_LOWER[-1]
        bb_upper = self.data.BB_UPPER[-1]
        atr = self.data.ATR14[-1]

        if self.position:
            if adx > self.ADX_EXIT_MAX or macd < macd_signal or close > bb_upper:
                self.position.close()
            return

        if adx > self.ADX_ENTRY_MIN and macd > macd_signal and close <= bb_lower * 1.02:
            stop = close - self.STOP_ATR_MULT * atr
            fraction = _risk_sized_fraction(close, stop, self.RISK_PER_TRADE, self.MAX_POSITION_FRACTION)
            if fraction:
                self.buy(size=fraction, sl=stop)


class DualThrustStrategy(Strategy):
    """Dual Thrust 변동성 돌파 (Michael Chalek) — 현물이라 롱 방향만 구현."""

    TIMEFRAME = "1h"
    K1 = 0.71
    STOP_ATR_MULT = 2.0
    WARMUP_BARS = 25
    RISK_PER_TRADE = 0.0025
    MAX_POSITION_FRACTION = 0.95

    def init(self):
        pass

    def next(self):
        i = len(self.data.Close) - 1
        if i < self.WARMUP_BARS:
            return

        if self.position:
            return  # 반대 신호 로직은 롱 전용이라 없음 — 스탑으로만 청산

        close = self.data.Close[-1]
        open_ = self.data.Open[-1]
        range_ = self.data.DT_RANGE[-1]
        atr = self.data.ATR14[-1]
        if range_ != range_:  # NaN 가드
            return

        buy_line = open_ + self.K1 * range_
        if close > buy_line:
            stop = close - self.STOP_ATR_MULT * atr
            fraction = _risk_sized_fraction(close, stop, self.RISK_PER_TRADE, self.MAX_POSITION_FRACTION)
            if fraction:
                self.buy(size=fraction, sl=stop)
