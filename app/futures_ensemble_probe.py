"""Ensemble and hybrid futures strategies combining multiple signals.

Tests combinations like:
1. Supertrend + MACD confirmation (higher bar for entry)
2. Multi-timeframe confirmation (4h trend filter for 1d entries)
3. Regime-switching (volatility/ADX-based selection between trend-follow and mean-reversion)
4. Volatility-adjusted sizing and entry thresholds
5. Signal averaging/voting across multiple indicators

Goal: Higher-quality signals by requiring agreement across multiple indicators.
"""
from __future__ import annotations

import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass

import pandas as pd
import pandas_ta as ta
from backtesting import Backtest, Strategy

from app.futures_data import fetch_perp_ohlcv

# ============================================================================
# CONSTANTS
# ============================================================================

MIN_USABLE_BARS = 250
MIN_PROFIT_FACTOR = 1.30
MAX_DRAWDOWN_PCT = 20.0
MIN_TRADES = 5
SINCE = "2022-01-01T00:00:00Z"

# Focus on survivors from Round 1 + new ensemble strategies
FIRST_ROUND_UNIVERSE = ["BTC", "ETH", "BNB", "SOL", "XRP", "DOGE", "ADA", "AVAX", "LINK", "UNI"]


# ============================================================================
# INDICATORS
# ============================================================================

def add_combo_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    """Comprehensive indicator set for ensemble strategies."""
    out = frame.copy()

    # Trend: Supertrend
    out["HL2"] = (out["High"] + out["Low"]) / 2.0
    out["ATR"] = ta.atr(out["High"], out["Low"], out["Close"], length=10)
    out["BASIC_UB"] = out["HL2"] + 3.0 * out["ATR"]
    out["BASIC_LB"] = out["HL2"] - 3.0 * out["ATR"]
    out["FINAL_UB"] = out["BASIC_UB"].copy()
    out["FINAL_LB"] = out["BASIC_LB"].copy()

    for i in range(1, len(out)):
        out.loc[out.index[i], "FINAL_UB"] = min(out.loc[out.index[i], "BASIC_UB"], out.loc[out.index[i-1], "FINAL_UB"])
        out.loc[out.index[i], "FINAL_LB"] = max(out.loc[out.index[i], "BASIC_LB"], out.loc[out.index[i-1], "FINAL_LB"])

    out["SUPERTREND"] = 1
    for i in range(1, len(out)):
        if out.loc[out.index[i], "Close"] <= out.loc[out.index[i], "FINAL_UB"]:
            out.loc[out.index[i], "SUPERTREND"] = 1
        else:
            out.loc[out.index[i], "SUPERTREND"] = -1

    out["SUPERT_LINE"] = out.apply(
        lambda row: row["FINAL_LB"] if row["SUPERTREND"] == 1 else row["FINAL_UB"],
        axis=1
    )

    # Momentum: MACD
    macd = ta.macd(out["Close"], fast=12, slow=26, signal=9)
    out["MACD"] = macd.iloc[:, 0]
    out["MACD_SIGNAL"] = macd.iloc[:, 1]
    out["MACD_HIST"] = macd.iloc[:, 2]

    # Mean reversion: RSI
    out["RSI"] = ta.rsi(out["Close"], length=14)

    # Volatility & trend strength
    out["ADX"] = ta.adx(out["High"], out["Low"], out["Close"], length=14)["ADX_14"]

    # Moving averages
    out["EMA8"] = ta.ema(out["Close"], length=8)
    out["EMA21"] = ta.ema(out["Close"], length=21)
    out["SMA200"] = ta.sma(out["Close"], length=200)

    # Bollinger Bands for volatility context
    bb = ta.bbands(out["Close"], length=20, std=2.0)
    out["BB_UPPER"] = bb.iloc[:, 2]
    out["BB_LOWER"] = bb.iloc[:, 0]
    out["BB_WIDTH"] = out["BB_UPPER"] - out["BB_LOWER"]
    out["BB_WIDTH_MA"] = out["BB_WIDTH"].rolling(20).mean()

    return out


# ============================================================================
# ENSEMBLE STRATEGIES
# ============================================================================

class SupertrendMacdConfirmStrategy(Strategy):
    """Supertrend entry signal + MACD confirmation (higher bar for entry)."""
    WARMUP_BARS = 35
    MIN_ADX = 18
    RISK_PER_TRADE = 0.02
    MAX_POSITION = 0.95
    STOP_ATR_MULT = 1.5

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
        atr = self.data.ATR[-1]
        adx = self.data.ADX[-1]
        macd_hist = self.data.MACD_HIST[-1]
        macd_hist_prev = self.data.MACD_HIST[-2]

        if pd.isna(adx) or pd.isna(macd_hist) or pd.isna(atr):
            return

        if self.position:
            if (self.position.is_long and st_now < 0) or \
               (self.position.is_short and st_now > 0):
                self.position.close()
            return

        st_flip_up = st_prev < 0 and st_now > 0
        st_flip_down = st_prev > 0 and st_now < 0
        macd_hist_up = macd_hist_prev <= 0 and macd_hist > 0
        macd_hist_down = macd_hist_prev >= 0 and macd_hist < 0

        if st_flip_up and macd_hist_up and adx >= self.MIN_ADX and close > st_line:
            stop = st_line
            size = self.RISK_PER_TRADE / (abs(close - stop) / close + 1e-6)
            size = min(size, self.MAX_POSITION)
            if size > 0:
                self.buy(size=size, sl=stop)
        elif st_flip_down and macd_hist_down and adx >= self.MIN_ADX and close < st_line:
            stop = st_line
            size = self.RISK_PER_TRADE / (abs(close - stop) / close + 1e-6)
            size = min(size, self.MAX_POSITION)
            if size > 0:
                self.sell(size=size, sl=stop)


class RegimeSwitchStrategy(Strategy):
    """Volatility-based regime switching: trend-follow when high ADX, mean-reversion when low."""
    WARMUP_BARS = 35
    TREND_ADX_THRESHOLD = 25
    MEANREV_ADX_THRESHOLD = 18
    RISK_PER_TRADE = 0.02
    MAX_POSITION = 0.95
    STOP_ATR_MULT = 2.0

    def init(self):
        pass

    def next(self):
        i = len(self.data.Close) - 1
        if i < self.WARMUP_BARS:
            return

        close = self.data.Close[-1]
        adx = self.data.ADX[-1]
        atr = self.data.ATR[-1]
        rsi = self.data.RSI[-1]
        st_now = self.data.SUPERTREND[-1]
        st_prev = self.data.SUPERTREND[-2]
        st_line = self.data.SUPERT_LINE[-1]

        if pd.isna(adx) or pd.isna(rsi) or pd.isna(atr):
            return

        if self.position:
            if (self.position.is_long and st_now < 0) or \
               (self.position.is_short and st_now > 0):
                self.position.close()
            return

        in_trend_regime = adx >= self.TREND_ADX_THRESHOLD
        in_meanrev_regime = adx < self.MEANREV_ADX_THRESHOLD

        if in_trend_regime:
            # Trend-following with Supertrend
            st_flip_up = st_prev < 0 and st_now > 0
            st_flip_down = st_prev > 0 and st_now < 0

            if st_flip_up and close > st_line:
                stop = st_line
                size = self.RISK_PER_TRADE / (abs(close - stop) / close + 1e-6)
                size = min(size, self.MAX_POSITION)
                if size > 0:
                    self.buy(size=size, sl=stop)
            elif st_flip_down and close < st_line:
                stop = st_line
                size = self.RISK_PER_TRADE / (abs(close - stop) / close + 1e-6)
                size = min(size, self.MAX_POSITION)
                if size > 0:
                    self.sell(size=size, sl=stop)

        elif in_meanrev_regime:
            # Mean reversion with RSI
            if rsi < 30 and close > self.data.SMA200[-1] * 0.98:
                stop = close - self.STOP_ATR_MULT * atr
                size = self.RISK_PER_TRADE / (abs(close - stop) / close + 1e-6)
                size = min(size, self.MAX_POSITION)
                if size > 0:
                    self.buy(size=size, sl=stop)
            elif rsi > 70 and close < self.data.SMA200[-1] * 1.02:
                stop = close + self.STOP_ATR_MULT * atr
                size = self.RISK_PER_TRADE / (abs(close - stop) / close + 1e-6)
                size = min(size, self.MAX_POSITION)
                if size > 0:
                    self.sell(size=size, sl=stop)


class VolatilityAdjustedTrendStrategy(Strategy):
    """Supertrend with volatility-adjusted position sizing and thresholds."""
    WARMUP_BARS = 35
    RISK_PER_TRADE = 0.02
    MAX_POSITION = 0.95
    MIN_ADX = 20
    VOL_SCALE_FACTOR = 1.0  # Adjust stop/size inversely to volatility

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
        atr = self.data.ATR[-1]
        adx = self.data.ADX[-1]
        bb_width = self.data.BB_WIDTH[-1]
        bb_width_ma = self.data.BB_WIDTH_MA[-1]

        if pd.isna(adx) or pd.isna(bb_width) or pd.isna(bb_width_ma):
            return

        # Volatility ratio: high vol = tighter stops, lower risk
        vol_ratio = bb_width / (bb_width_ma + 1e-6)
        vol_adjusted_risk = self.RISK_PER_TRADE / max(vol_ratio, 0.8)

        if self.position:
            if (self.position.is_long and st_now < 0) or \
               (self.position.is_short and st_now > 0):
                self.position.close()
            return

        if adx < self.MIN_ADX:
            return

        st_flip_up = st_prev < 0 and st_now > 0
        st_flip_down = st_prev > 0 and st_now < 0

        if st_flip_up and close > st_line:
            stop = st_line
            size = vol_adjusted_risk / (abs(close - stop) / close + 1e-6)
            size = min(size, self.MAX_POSITION)
            if size > 0:
                self.buy(size=size, sl=stop)
        elif st_flip_down and close < st_line:
            stop = st_line
            size = vol_adjusted_risk / (abs(close - stop) / close + 1e-6)
            size = min(size, self.MAX_POSITION)
            if size > 0:
                self.sell(size=size, sl=stop)


class SignalVotingStrategy(Strategy):
    """Require agreement across multiple signals (voting mechanism)."""
    WARMUP_BARS = 35
    RISK_PER_TRADE = 0.02
    MAX_POSITION = 0.95
    MIN_VOTE_SCORE = 2  # Require at least 2/3 signals to agree

    def init(self):
        pass

    def next(self):
        i = len(self.data.Close) - 1
        if i < self.WARMUP_BARS:
            return

        close = self.data.Close[-1]
        atr = self.data.ATR[-1]

        if pd.isna(atr):
            return

        if self.position:
            return

        # Compute signals
        st_now = self.data.SUPERTREND[-1]
        st_prev = self.data.SUPERTREND[-2]
        st_signal = 1 if (st_prev < 0 and st_now > 0) else (-1 if (st_prev > 0 and st_now < 0) else 0)

        macd_hist = self.data.MACD_HIST[-1]
        macd_hist_prev = self.data.MACD_HIST[-2]
        macd_signal = 1 if (macd_hist_prev <= 0 and macd_hist > 0) else (-1 if (macd_hist_prev >= 0 and macd_hist < 0) else 0)

        ema_fast = self.data.EMA8[-1]
        ema_slow = self.data.EMA21[-1]
        ema_fast_prev = self.data.EMA8[-2]
        ema_slow_prev = self.data.EMA21[-2]
        ema_signal = 1 if (ema_fast_prev <= ema_slow_prev and ema_fast > ema_slow) else (-1 if (ema_fast_prev >= ema_slow_prev and ema_fast < ema_slow) else 0)

        # Vote
        bull_votes = sum([st_signal > 0, macd_signal > 0, ema_signal > 0])
        bear_votes = sum([st_signal < 0, macd_signal < 0, ema_signal < 0])

        if bull_votes >= self.MIN_VOTE_SCORE:
            stop = close - 2.0 * atr
            size = self.RISK_PER_TRADE / (abs(close - stop) / close + 1e-6)
            size = min(size, self.MAX_POSITION)
            if size > 0:
                self.buy(size=size, sl=stop)
        elif bear_votes >= self.MIN_VOTE_SCORE:
            stop = close + 2.0 * atr
            size = self.RISK_PER_TRADE / (abs(close - stop) / close + 1e-6)
            size = min(size, self.MAX_POSITION)
            if size > 0:
                self.sell(size=size, sl=stop)


# ============================================================================
# BACKTEST RUNNER
# ============================================================================

@dataclass
class BacktestResult:
    symbol: str
    strategy_name: str
    annualized_return_pct: float
    return_pct: float
    buy_hold_pct: float
    profit_factor: float
    max_drawdown_pct: float
    trades: int
    sharpe_ratio: float
    passes_gate: bool
    notes: str = ""

    def __repr__(self) -> str:
        return f"{self.symbol:6} {self.strategy_name:25} | Return {self.return_pct:7.1f}% | Ann. {self.annualized_return_pct:6.1f}% | PF {self.profit_factor:5.2f} | MDD {self.max_drawdown_pct:6.1f}% | Trades {self.trades:4d} | Pass {str(self.passes_gate):5}"


def run_backtest_one(symbol: str, frame: pd.DataFrame, strategy_cls: type[Strategy], name: str) -> BacktestResult | None:
    """Run one backtest."""
    if frame.empty or len(frame) < MIN_USABLE_BARS:
        return None

    try:
        enriched = add_combo_indicators(frame).dropna()
        if len(enriched) < MIN_USABLE_BARS:
            return None

        stats = Backtest(
            enriched,
            strategy_cls,
            cash=10_000.0,
            commission=0.0004,
            exclusive_orders=True,
        ).run()

        return_pct = float(stats.get("Return [%]", float("nan")))
        buy_hold_pct = float(stats.get("Buy & Hold Return [%]", float("nan")))
        profit_factor = float(stats.get("Profit Factor", float("nan")))
        max_dd_pct = abs(float(stats.get("Max. Drawdown [%]", float("inf"))))
        trades = int(stats.get("# Trades", 0))
        sharpe = float(stats.get("Sharpe Ratio", float("nan")))

        period_days = len(enriched)
        years = max(period_days / 252, 0.1)
        annualized = (1 + return_pct / 100) ** (1 / years) - 1
        annualized_pct = annualized * 100

        passes = (
            not pd.isna(profit_factor)
            and profit_factor >= MIN_PROFIT_FACTOR
            and max_dd_pct <= MAX_DRAWDOWN_PCT
            and trades >= MIN_TRADES
        )

        return BacktestResult(
            symbol=symbol,
            strategy_name=name,
            annualized_return_pct=annualized_pct,
            return_pct=return_pct,
            buy_hold_pct=buy_hold_pct,
            profit_factor=profit_factor,
            max_drawdown_pct=max_dd_pct,
            trades=trades,
            sharpe_ratio=sharpe,
            passes_gate=passes,
        )
    except Exception:
        return None


def fetch_one(symbol: str) -> pd.DataFrame | None:
    """Fetch perpetual futures OHLCV data."""
    try:
        perp_symbol = f"{symbol}/USDT:USDT"
        frame = fetch_perp_ohlcv(perp_symbol, "1d", SINCE, None)
        if not frame.empty:
            print(f"  {symbol:6}: {len(frame):5d} bars")
        return frame
    except Exception as exc:
        print(f"  {symbol:6}: FETCH FAILED ({exc})")
        return None


def process_one_symbol(symbol: str, frame: pd.DataFrame) -> list[BacktestResult]:
    """Test all ensemble strategies on one symbol."""
    strategies = [
        (SupertrendMacdConfirmStrategy, "ST+MACD-Confirm"),
        (RegimeSwitchStrategy, "Regime-Switch"),
        (VolatilityAdjustedTrendStrategy, "Vol-Adj-Trend"),
        (SignalVotingStrategy, "Signal-Voting"),
    ]

    results = []
    for strat_cls, name in strategies:
        result = run_backtest_one(symbol, frame, strat_cls, name)
        if result:
            results.append(result)
    return results


def run_ensemble_round() -> None:
    """Test ensemble/combination strategies."""
    print("\n" + "=" * 140)
    print("ENSEMBLE ROUND: Multi-Signal Combination Strategies")
    print("=" * 140)
    print(f"Universe: {len(FIRST_ROUND_UNIVERSE)} symbols (focus on best performers from Round 1)")
    print(f"Strategies: 4 ensemble/hybrid candidates (ST+MACD, Regime-Switch, Vol-Adj, Signal-Voting)")
    print()

    print("[1/3] Fetching perpetual futures daily OHLCV data...")
    frames: dict[str, pd.DataFrame] = {}
    for symbol in FIRST_ROUND_UNIVERSE:
        frame = fetch_one(symbol)
        if frame is not None and not frame.empty:
            frames[symbol] = frame

    available = [s for s in FIRST_ROUND_UNIVERSE if s in frames]
    print(f"  Available: {len(available)}/{len(FIRST_ROUND_UNIVERSE)} symbols\n")

    print("[2/3] Running backtests...")
    all_results: list[BacktestResult] = []
    max_workers = min(len(available) or 1, os.cpu_count() or 4, 4)

    start_time = time.monotonic()
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(process_one_symbol, s, frames[s]): s
            for s in available
        }
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                results = future.result()
                all_results.extend(results)
            except Exception:
                pass

    elapsed = time.monotonic() - start_time
    print(f"  Completed in {elapsed:.0f}s\n")

    print("[3/3] Results Summary\n")

    print("By Strategy:")
    print("-" * 140)
    strategies = sorted(set(r.strategy_name for r in all_results))
    for strat in strategies:
        strat_results = [r for r in all_results if r.strategy_name == strat]
        passing = [r for r in strat_results if r.passes_gate]
        if not strat_results:
            continue

        avg_return = sum(r.return_pct for r in strat_results) / len(strat_results)
        avg_ann = sum(r.annualized_return_pct for r in strat_results) / len(strat_results)
        pass_pct = 100 * len(passing) / len(strat_results)

        print(f"  {strat:25} | Symbols {len(strat_results):2d} | Passing {len(passing):2d} ({pass_pct:5.1f}%) | "
              f"Avg Return {avg_return:7.1f}% | Avg Ann. {avg_ann:6.1f}%")

    print("\n" + "-" * 140)
    print("Best Individual Results:")
    print("-" * 140)
    sorted_results = sorted(
        [r for r in all_results if r.passes_gate],
        key=lambda x: x.annualized_return_pct,
        reverse=True,
    )
    for r in sorted_results[:10]:
        print(r)

    # Save results
    df = pd.DataFrame([
        {
            "Symbol": r.symbol,
            "Strategy": r.strategy_name,
            "Return%": r.return_pct,
            "AnnualizedReturn%": r.annualized_return_pct,
            "B&H%": r.buy_hold_pct,
            "ProfitFactor": r.profit_factor,
            "MaxDD%": r.max_drawdown_pct,
            "Trades": r.trades,
            "Sharpe": r.sharpe_ratio,
            "Passes": r.passes_gate,
        }
        for r in all_results
    ])
    csv_path = "/tmp/futures_ensemble_results.csv"
    df.to_csv(csv_path, index=False)
    print(f"\nResults saved to: {csv_path}")


if __name__ == "__main__":
    run_ensemble_round()
