"""RegimeSwitchStrategy — backtesting.py implementation of the "15분봉 상태전환형"
strategy agreed in docs/trading-agent-plan.md.

This is a faithful-but-simplified first cut for the backtest validation gate. Known
simplifications versus the plan document, called out explicitly rather than silently:
- No economy-team LLM overlay filter yet — there's no historical time series of past
  regime judgments to backtest against. That filter gets added once the qualitative
  signal has its own historical log to replay.
- No explicit "거래 금지 모드" cost/spread checks — backtesting.py's commission model
  covers trading costs; spread/liquidity-outage conditions aren't observable from
  OHLCV candles alone.
- Only one open position at a time (matches the plan's single-symbol, single-strategy
  scope for the initial validation pass).

Tunable thresholds are class attributes (not module constants) on purpose — that's
what lets app/optimize.py sweep them via Backtest.optimize(TREND_ADX_MIN=[...], ...)
without touching this file. Indicator *periods* (ADX/RSI/ATR length etc.) stay fixed
in app/indicators.py for this round; only thresholds/multipliers are swept.
"""
from __future__ import annotations

from backtesting import Strategy


class RegimeSwitchStrategy(Strategy):
    # backtesting.py class-attribute override convention: Backtest(...).run(USE_REGIME_FILTER=False)
    # or Backtest(...).optimize(TREND_ADX_MIN=[18,20,22]) both work because these are class attrs.
    USE_REGIME_FILTER = True

    RISK_PER_TRADE = 0.0025
    TREND_ADX_MIN = 22
    MEANREV_ADX_MAX = 18
    VOLUME_MULTIPLIER = 1.5
    TREND_STOP_ATR = 1.3
    TREND_TRAIL_ATR = 1.8
    MEANREV_STOP_ATR = 1.0
    MAX_POSITION_FRACTION = 0.95

    MAX_CONSECUTIVE_LOSSES = 3
    COOLDOWN_BARS_AFTER_LOSSES = 24  # 6h of 15m bars
    PEAK_DRAWDOWN_HALT = 0.06

    DEFAULT_HOLD_BARS = 92  # ~23h of 15m bars
    EXTENDED_HOLD_BARS = 288  # ~72h of 15m bars

    WARMUP_BARS = 52  # 1h EMA50 needs ~50 hourly bars' worth of 15m history to stop being NaN

    def init(self):
        self.entry_bar = None
        self.consecutive_losses = 0
        self.cooldown_until_bar = -1
        self.peak_equity = self.equity
        self.last_closed_count = 0

    def next(self):
        i = len(self.data.Close) - 1
        if i < self.WARMUP_BARS:
            return

        self.peak_equity = max(self.peak_equity, self.equity)
        self._track_consecutive_losses(i)

        if self.position:
            self._manage_open_position(i)
            return

        if i < self.cooldown_until_bar:
            return
        if self.equity < self.peak_equity * (1 - self.PEAK_DRAWDOWN_HALT):
            return  # 고점 대비 낙폭 한도 도달 — 재검증 전까지 신규 진입 안 함

        if self.USE_REGIME_FILTER and self.data.REGIME[-1] == "RISK_OFF":
            return  # 경제팀 오버레이 필터(근사치): 리스크오프 구간엔 롱 진입 보류

        adx = self.data.ADX14[-1]
        close = self.data.Close[-1]
        atr = self.data.ATR14[-1]

        if adx >= self.TREND_ADX_MIN and self.data.EMA20_1H[-1] > self.data.EMA50_1H[-1]:
            breakout = close > self.data.HIGHEST20[-2] and self.data.Volume[-1] >= self.data.VOL_MEDIAN20[-1] * self.VOLUME_MULTIPLIER
            if breakout:
                self._enter_long(close, close - self.TREND_STOP_ATR * atr, i)
            return

        if adx < self.MEANREV_ADX_MAX:
            oversold = close < self.data.BB_LOWER[-1] and self.data.RSI3[-1] < 10
            reclaimed = close > self.data.High[-2] and close >= self.data.BB_LOWER[-1]
            if oversold or reclaimed:
                stop = min(self.data.LOWEST5[-1], close - self.MEANREV_STOP_ATR * atr)
                self._enter_long(close, stop, i)

    def _enter_long(self, entry: float, stop: float, bar_index: int):
        stop_distance_pct = (entry - stop) / entry
        if stop_distance_pct <= 0:
            return
        fraction = min(self.RISK_PER_TRADE / stop_distance_pct, self.MAX_POSITION_FRACTION)
        self.buy(size=fraction, sl=stop)
        self.entry_bar = bar_index

    def _manage_open_position(self, i: int):
        held = i - (self.entry_bar or i)
        if held >= self.EXTENDED_HOLD_BARS or (held >= self.DEFAULT_HOLD_BARS and not self._extension_conditions_met()):
            self.position.close()
            self.entry_bar = None
            return

        # +1R 절반 청산 + 잔여 포지션 ATR 추적손절 (계획서 "추세돌파 모드" 스펙)
        atr = self.data.ATR14[-1]
        close = self.data.Close[-1]
        for trade in self.trades:
            r_distance = trade.entry_price - trade.sl if trade.sl else None
            if not r_distance or r_distance <= 0:
                continue
            profit = close - trade.entry_price
            if not getattr(trade, "partial_taken", False) and profit >= r_distance:
                trade.close(portion=0.5)
                trade.partial_taken = True
            if getattr(trade, "partial_taken", False):
                trailing_stop = close - self.TREND_TRAIL_ATR * atr
                if trade.sl is None or trailing_stop > trade.sl:
                    trade.sl = trailing_stop

    def _extension_conditions_met(self) -> bool:
        if not self.trades:
            return False
        trade = self.trades[-1]
        return trade.pl > 0 and self.data.EMA20_1H[-1] > self.data.EMA50_1H[-1]

    def _track_consecutive_losses(self, i: int):
        closed_count = len(self.closed_trades)
        if closed_count <= self.last_closed_count:
            return
        last_trade = self.closed_trades[-1]
        if last_trade.pl < 0:
            self.consecutive_losses += 1
            if self.consecutive_losses >= self.MAX_CONSECUTIVE_LOSSES:
                self.cooldown_until_bar = i + self.COOLDOWN_BARS_AFTER_LOSSES
                self.consecutive_losses = 0
        else:
            self.consecutive_losses = 0
        self.last_closed_count = closed_count
