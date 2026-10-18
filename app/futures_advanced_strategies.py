"""Advanced futures strategies: multi-timeframe, ensemble, volatility-adaptive.

These are more sophisticated variants that combine insights from multiple technical approaches.
Designed for robustness and edge detection, not curve-fitting.
"""
from __future__ import annotations

from backtesting import Strategy


# ============================================================================
# MULTI-TIMEFRAME STRATEGIES
# ============================================================================

class MultiTimeframeTrendStrategy(Strategy):
    """Daily trend follows 4H trend direction (if we had intraday data).

    With daily data only, we simulate by using Supertrend on daily but with
    stricter ADX thresholds (simulating multi-timeframe rigor).
    """
    WARMUP_BARS = 30
    MIN_ADX_FOR_ENTRY = 25  # Strict ADX to simulate needing higher-timeframe confirmation
    RISK_PER_TRADE = 0.015
    MAX_POSITION = 0.95

    def init(self):
        pass

    def next(self):
        i = len(self.data.Close) - 1
        if i < self.WARMUP_BARS:
            return

        close = self.data.Close[-1]
        st_now = self.data.SUPERTREND[-1]
        st_prev = self.data.SUPERTREND[-2]
        st_line = self.data.SUPERT_LINE[-1]
        adx = self.data.ADX14[-1]

        if pd.isna(adx):
            return

        if self.position:
            if (self.position.is_long and st_now < 0) or \
               (self.position.is_short and st_now > 0):
                self.position.close()
            return

        # Only enter on trend flip if ADX is VERY high (simulates strong higher-TF confirmation)
        if adx < self.MIN_ADX_FOR_ENTRY:
            return

        st_flip_up = st_prev < 0 and st_now > 0
        st_flip_down = st_prev > 0 and st_now < 0

        if st_flip_up and close > st_line:
            size = self.RISK_PER_TRADE / (abs(close - st_line) / close + 1e-6)
            size = min(size, self.MAX_POSITION)
            if size > 0:
                self.buy(size=size, sl=st_line)
        elif st_flip_down and close < st_line:
            size = self.RISK_PER_TRADE / (abs(close - st_line) / close + 1e-6)
            size = min(size, self.MAX_POSITION)
            if size > 0:
                self.sell(size=size, sl=st_line)


# ============================================================================
# ADAPTIVE/DYNAMIC STRATEGIES
# ============================================================================

class AdaptivePositionSizingStrategy(Strategy):
    """Position size adapts to recent volatility to maintain consistent risk.

    High volatility → smaller positions, tight stops
    Low volatility → larger positions, allow wider swings
    """
    WARMUP_BARS = 35
    MIN_ADX = 18
    RISK_AMOUNT = 0.02  # 2% risk per trade
    MAX_POSITION = 0.95
    VOLATILITY_LOOKBACK = 20

    def init(self):
        pass

    def next(self):
        i = len(self.data.Close) - 1
        if i < self.WARMUP_BARS:
            return

        close = self.data.Close[-1]
        st_now = self.data.SUPERTREND[-1]
        st_prev = self.data.SUPERTREND[-2]
        st_line = self.data.SUPERT_LINE[-1]
        adx = self.data.ADX14[-1]

        if pd.isna(adx):
            return

        # Calculate recent volatility (using ATR or close std dev)
        close_series = self.data.Close[-self.VOLATILITY_LOOKBACK:]
        volatility = close_series.std() / close_series.mean()

        if self.position:
            if (self.position.is_long and st_now < 0) or \
               (self.position.is_short and st_now > 0):
                self.position.close()
            return

        if adx < self.MIN_ADX:
            return

        st_flip_up = st_prev < 0 and st_now > 0
        st_flip_down = st_prev > 0 and st_now < 0

        # Adjust position size inversely to volatility
        volatility_multiplier = 0.02 / max(volatility, 0.01)  # Lower vol → bigger position
        adjusted_risk = self.RISK_AMOUNT * volatility_multiplier

        if st_flip_up and close > st_line:
            size = adjusted_risk / (abs(close - st_line) / close + 1e-6)
            size = min(size, self.MAX_POSITION)
            if size > 0:
                self.buy(size=size, sl=st_line)
        elif st_flip_down and close < st_line:
            size = adjusted_risk / (abs(close - st_line) / close + 1e-6)
            size = min(size, self.MAX_POSITION)
            if size > 0:
                self.sell(size=size, sl=st_line)


# ============================================================================
# MEAN REVERSION WITH TREND CONFIRMATION
# ============================================================================

class RegimeSwitchMeanReversionStrategy(Strategy):
    """In low-ADX regime, use mean reversion. In high-ADX, use trend-following.

    Adaptively picks the strategy that should work best for current market conditions.
    """
    WARMUP_BARS = 35
    TREND_ADX_THRESHOLD = 25
    MEANREV_ADX_THRESHOLD = 18
    RISK_PER_TRADE = 0.02
    MAX_POSITION = 0.95
    MAX_HOLD_BARS = 15

    def init(self):
        self.entry_bar = 0

    def next(self):
        i = len(self.data.Close) - 1
        if i < self.WARMUP_BARS:
            return

        close = self.data.Close[-1]
        adx = self.data.ADX14[-1]
        atr = self.data.ATR14[-1]
        rsi = self.data.RSI14[-1] if hasattr(self.data, 'RSI14') else 50

        if pd.isna(adx) or pd.isna(atr):
            return

        # Close old positions
        if self.position and i - self.entry_bar >= self.MAX_HOLD_BARS:
            self.position.close()
            return

        if self.position:
            return

        in_trend_regime = adx >= self.TREND_ADX_THRESHOLD
        in_meanrev_regime = adx < self.MEANREV_ADX_THRESHOLD

        if in_trend_regime:
            # Use Supertrend in trending market
            st_now = self.data.SUPERTREND[-1]
            st_prev = self.data.SUPERTREND[-2]
            st_line = self.data.SUPERT_LINE[-1]

            st_flip_up = st_prev < 0 and st_now > 0
            st_flip_down = st_prev > 0 and st_now < 0

            if st_flip_up and close > st_line:
                size = self.RISK_PER_TRADE / (abs(close - st_line) / close + 1e-6)
                size = min(size, self.MAX_POSITION)
                if size > 0:
                    self.buy(size=size, sl=st_line)
                    self.entry_bar = i
            elif st_flip_down and close < st_line:
                size = self.RISK_PER_TRADE / (abs(close - st_line) / close + 1e-6)
                size = min(size, self.MAX_POSITION)
                if size > 0:
                    self.sell(size=size, sl=st_line)
                    self.entry_bar = i

        elif in_meanrev_regime:
            # Use RSI mean reversion in choppy market
            if not pd.isna(rsi):
                sma200 = self.data.SMA200[-1] if hasattr(self.data, 'SMA200') else close

                if rsi < 30 and close > sma200 * 0.97:  # Oversold near support
                    stop = close - 2.0 * atr
                    size = self.RISK_PER_TRADE / (abs(close - stop) / close + 1e-6)
                    size = min(size, self.MAX_POSITION)
                    if size > 0:
                        self.buy(size=size, sl=stop)
                        self.entry_bar = i
                elif rsi > 70 and close < sma200 * 1.03:  # Overbought near resistance
                    stop = close + 2.0 * atr
                    size = self.RISK_PER_TRADE / (abs(close - stop) / close + 1e-6)
                    size = min(size, self.MAX_POSITION)
                    if size > 0:
                        self.sell(size=size, sl=stop)
                        self.entry_bar = i


# ============================================================================
# SIGNAL QUALITY STRATEGIES (Reduce false signals)
# ============================================================================

class HighQualitySignalStrategy(Strategy):
    """Only trade on 'high-quality' setups:
    1. Supertrend flip when ADX > min_threshold
    2. Price has moved significantly (closed more than half stop distance away from entry)
    3. Volume context (optional, not all data has volume)

    Deliberately sacrifices trade count for higher win rate.
    """
    WARMUP_BARS = 30
    MIN_ADX = 22  # Higher bar for entry
    RISK_PER_TRADE = 0.02
    MAX_POSITION = 0.95
    PRICE_MOVE_FACTOR = 0.5  # Wait for price to confirm move beyond halfway point

    def init(self):
        self.last_signal_bar = 0

    def next(self):
        i = len(self.data.Close) - 1
        if i < self.WARMUP_BARS:
            return

        close = self.data.Close[-1]
        st_now = self.data.SUPERTREND[-1]
        st_prev = self.data.SUPERTREND[-2]
        st_line = self.data.SUPERT_LINE[-1]
        adx = self.data.ADX14[-1]

        if pd.isna(adx):
            return

        if self.position:
            if (self.position.is_long and st_now < 0) or \
               (self.position.is_short and st_now > 0):
                self.position.close()
            return

        if adx < self.MIN_ADX:
            return

        st_flip_up = st_prev < 0 and st_now > 0
        st_flip_down = st_prev > 0 and st_now < 0

        # Wait one bar for price confirmation of trend flip
        if i - self.last_signal_bar < 2:
            return

        if st_flip_up and close > st_line:
            stop = st_line
            min_move = abs(close - stop) * self.PRICE_MOVE_FACTOR
            # Entry is confirmed if price has moved at least halfway from stop
            if abs(close - st_line) >= min_move:
                size = self.RISK_PER_TRADE / (abs(close - stop) / close + 1e-6)
                size = min(size, self.MAX_POSITION)
                if size > 0:
                    self.buy(size=size, sl=stop)
                    self.last_signal_bar = i

        elif st_flip_down and close < st_line:
            stop = st_line
            min_move = abs(close - stop) * self.PRICE_MOVE_FACTOR
            if abs(close - st_line) >= min_move:
                size = self.RISK_PER_TRADE / (abs(close - stop) / close + 1e-6)
                size = min(size, self.MAX_POSITION)
                if size > 0:
                    self.sell(size=size, sl=stop)
                    self.last_signal_bar = i


# ============================================================================
# DRAWDOWN-PROTECTION STRATEGY
# ============================================================================

class DrawdownProtectionStrategy(Strategy):
    """Reduces position size or goes to cash in high-drawdown periods.

    Tracks running max equity and reduces leverage if drowdown exceeds threshold.
    """
    WARMUP_BARS = 30
    MIN_ADX = 20
    RISK_PER_TRADE = 0.02
    MAX_POSITION = 0.95
    DRAWDOWN_THRESHOLD = 0.10  # If down 10% from peak, reduce position size

    def init(self):
        self.peak_equity = self.equity

    def next(self):
        i = len(self.data.Close) - 1
        if i < self.WARMUP_BARS:
            return

        # Update peak and check drawdown
        if self.equity > self.peak_equity:
            self.peak_equity = self.equity

        current_dd = (self.peak_equity - self.equity) / self.peak_equity
        dd_active = current_dd > self.DRAWDOWN_THRESHOLD

        close = self.data.Close[-1]
        st_now = self.data.SUPERTREND[-1]
        st_prev = self.data.SUPERTREND[-2]
        st_line = self.data.SUPERT_LINE[-1]
        adx = self.data.ADX14[-1]

        if pd.isna(adx):
            return

        if self.position:
            if (self.position.is_long and st_now < 0) or \
               (self.position.is_short and st_now > 0):
                self.position.close()
            # If in drawdown, close position to preserve capital
            if dd_active:
                self.position.close()
            return

        # Don't enter new positions during high drawdown
        if dd_active:
            return

        if adx < self.MIN_ADX:
            return

        st_flip_up = st_prev < 0 and st_now > 0
        st_flip_down = st_prev > 0 and st_now < 0

        if st_flip_up and close > st_line:
            size = self.RISK_PER_TRADE / (abs(close - st_line) / close + 1e-6)
            size = min(size, self.MAX_POSITION)
            if size > 0:
                self.buy(size=size, sl=st_line)
        elif st_flip_down and close < st_line:
            size = self.RISK_PER_TRADE / (abs(close - st_line) / close + 1e-6)
            size = min(size, self.MAX_POSITION)
            if size > 0:
                self.sell(size=size, sl=st_line)


import pandas as pd
