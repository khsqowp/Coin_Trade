"""Binance USDT-M Perpetual Futures long/short directional strategy probe.

Systematic backtesting of multiple strategy candidates across a universe of 50 liquid cryptocurrencies.
Tests long+short strategies (not delta-neutral like funding_arb), uses only price action (no funding rate modeling).

Goal: Find a strategy that backtests to 10%+ annualized return with robust metrics.
Method: Elimination-based testing — broad candidate set, eliminate poor performers each round.

CRITICAL: Excludes funding rate costs (app/futures_data.py limitation) — reported returns are upper bounds.
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
ANNUALIZATION_FACTOR = 252  # Trading days per year

# Core universe: 50 well-known liquid cryptocurrencies
CORE_UNIVERSE = [
    "BTC", "ETH", "BNB", "XRP", "SOL", "TRX", "DOGE", "ZEC", "LINK", "XMR",
    "ADA", "XLM", "BCH", "LTC", "HBAR", "AVAX", "SHIB", "SUI", "UNI", "NEAR",
    "TAO", "AAVE", "ONDO", "THETA", "PEPE", "DOT", "ENA", "WLD", "ICP", "ETC",
    "POL", "QNT", "ALGO", "ATOM", "RENDER", "EOS", "JUP", "ARB", "FIL", "VET",
    "CAKE", "TON", "MKR", "LDO", "CRV", "INJ", "OP", "APT", "IMX", "STX",
]

# First round: test on 10 high-liquidity symbols to validate strategies before full sweep
FIRST_ROUND_UNIVERSE = ["BTC", "ETH", "BNB", "SOL", "XRP", "DOGE", "ADA", "AVAX", "LINK", "UNI"]


# ============================================================================
# INDICATORS & HELPER FUNCTIONS
# ============================================================================

def add_supertrend_indicators(frame: pd.DataFrame, period: int = 10, mult: float = 3.0) -> pd.DataFrame:
    """Supertrend indicator with ATR-based trailing stop."""
    out = frame.copy()
    out["HL2"] = (out["High"] + out["Low"]) / 2.0
    out["ATR"] = ta.atr(out["High"], out["Low"], out["Close"], length=period)
    out["BASIC_UB"] = out["HL2"] + mult * out["ATR"]
    out["BASIC_LB"] = out["HL2"] - mult * out["ATR"]
    out["FINAL_UB"] = out["BASIC_UB"].copy()
    out["FINAL_LB"] = out["BASIC_LB"].copy()

    for i in range(1, len(out)):
        out.loc[out.index[i], "FINAL_UB"] = min(out.loc[out.index[i], "BASIC_UB"], out.loc[out.index[i-1], "FINAL_UB"]) if pd.notna(out.loc[out.index[i-1], "FINAL_UB"]) else out.loc[out.index[i], "BASIC_UB"]
        out.loc[out.index[i], "FINAL_LB"] = max(out.loc[out.index[i], "BASIC_LB"], out.loc[out.index[i-1], "FINAL_LB"]) if pd.notna(out.index[i-1]) else out.loc[out.index[i], "BASIC_LB"]

    out["SUPERTREND"] = 1
    for i in range(1, len(out)):
        if out.loc[out.index[i], "Close"] <= out.loc[out.index[i], "FINAL_UB"]:
            out.loc[out.index[i], "SUPERTREND"] = 1  # Uptrend
        else:
            out.loc[out.index[i], "SUPERTREND"] = -1  # Downtrend

    out["SUPERT_LINE"] = out.apply(
        lambda row: row["FINAL_LB"] if row["SUPERTREND"] == 1 else row["FINAL_UB"],
        axis=1
    )
    out["ADX"] = ta.adx(out["High"], out["Low"], out["Close"], length=14)["ADX_14"]
    return out


def add_ema_cross_indicators(frame: pd.DataFrame, fast: int = 8, slow: int = 21) -> pd.DataFrame:
    """EMA crossover strategy indicators."""
    out = frame.copy()
    out["EMA_FAST"] = ta.ema(out["Close"], length=fast)
    out["EMA_SLOW"] = ta.ema(out["Close"], length=slow)
    out["ATR"] = ta.atr(out["High"], out["Low"], out["Close"], length=14)
    return out


def add_macd_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    """MACD with trend filter (SMA200)."""
    out = frame.copy()
    macd = ta.macd(out["Close"], fast=12, slow=26, signal=9)
    out["MACD"] = macd.iloc[:, 0]
    out["MACD_SIGNAL"] = macd.iloc[:, 1]
    out["MACD_HIST"] = macd.iloc[:, 2]
    out["SMA200"] = ta.sma(out["Close"], length=200)
    out["ATR"] = ta.atr(out["High"], out["Low"], out["Close"], length=14)
    out["ADX"] = ta.adx(out["High"], out["Low"], out["Close"], length=14)["ADX_14"]
    return out


def add_rsi_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    """RSI mean reversion indicators."""
    out = frame.copy()
    out["RSI"] = ta.rsi(out["Close"], length=14)
    out["ATR"] = ta.atr(out["High"], out["Low"], out["Close"], length=14)
    out["SMA200"] = ta.sma(out["Close"], length=200)
    return out


def add_bollinger_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    """Bollinger Bands breakout indicators."""
    out = frame.copy()
    bb = ta.bbands(out["Close"], length=20, std=2.0)
    out["BB_UPPER"] = bb.iloc[:, 2]
    out["BB_LOWER"] = bb.iloc[:, 0]
    out["BB_MID"] = bb.iloc[:, 1]
    out["ATR"] = ta.atr(out["High"], out["Low"], out["Close"], length=14)
    return out


# ============================================================================
# STRATEGY CLASSES
# ============================================================================

class SupertrendLongShortStrategy(Strategy):
    """Supertrend-based long/short with trend-strength filter (ADX)."""
    TIMEFRAME = "1d"
    WARMUP_BARS = 30
    MIN_ADX = 20  # Only trade if ADX > threshold (weak signals filtered)
    RISK_PER_TRADE = 0.02
    MAX_POSITION = 0.95

    def init(self):
        pass

    def next(self):
        i = len(self.data.Close) - 1
        if i < self.WARMUP_BARS:
            return

        close = self.data.Close[-1]
        supertrend_now = self.data.SUPERTREND[-1]
        supertrend_prev = self.data.SUPERTREND[-2]
        st_line = self.data.SUPERT_LINE[-1]
        adx = self.data.ADX[-1]

        if pd.isna(adx) or adx < self.MIN_ADX:
            return

        if self.position:
            # Trailing stop
            if self.position.is_long:
                if st_line > 0:  # Valid stop line
                    for trade in self.trades:
                        if trade.sl is None or st_line > trade.sl:
                            trade.sl = st_line
            elif self.position.is_short:
                if st_line > 0:  # Valid stop line
                    for trade in self.trades:
                        if trade.sl is None or st_line < trade.sl:
                            trade.sl = st_line

            # Reverse if trend flips
            if (self.position.is_long and supertrend_now < 0) or \
               (self.position.is_short and supertrend_now > 0):
                self.position.close()
            return

        # Entry signals
        flip_up = supertrend_prev < 0 and supertrend_now > 0
        flip_down = supertrend_prev > 0 and supertrend_now < 0

        if flip_up and close > st_line:
            stop = st_line
            size = self.RISK_PER_TRADE / (abs(close - stop) / close + 1e-6)
            size = min(size, self.MAX_POSITION)
            if size > 0:
                self.buy(size=size, sl=stop)
        elif flip_down and close < st_line:
            stop = st_line
            size = self.RISK_PER_TRADE / (abs(close - stop) / close + 1e-6)
            size = min(size, self.MAX_POSITION)
            if size > 0:
                self.sell(size=size, sl=stop)


class EmaCrossLongShortStrategy(Strategy):
    """EMA crossover with long/short support."""
    WARMUP_BARS = 25
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
        ema_fast, ema_fast_prev = self.data.EMA_FAST[-1], self.data.EMA_FAST[-2]
        ema_slow, ema_slow_prev = self.data.EMA_SLOW[-1], self.data.EMA_SLOW[-2]
        atr = self.data.ATR[-1]

        if pd.isna(atr) or pd.isna(ema_fast) or pd.isna(ema_slow):
            return

        if self.position:
            cross_down = ema_fast_prev >= ema_slow_prev and ema_fast < ema_slow
            cross_up = ema_fast_prev <= ema_slow_prev and ema_fast > ema_slow

            if (self.position.is_long and cross_down) or \
               (self.position.is_short and cross_up):
                self.position.close()
            return

        cross_up = ema_fast_prev <= ema_slow_prev and ema_fast > ema_slow
        cross_down = ema_fast_prev >= ema_slow_prev and ema_fast < ema_slow

        if cross_up:
            stop = close - self.STOP_ATR_MULT * atr
            size = self.RISK_PER_TRADE / (abs(close - stop) / close + 1e-6)
            size = min(size, self.MAX_POSITION)
            if size > 0:
                self.buy(size=size, sl=stop)
        elif cross_down:
            stop = close + self.STOP_ATR_MULT * atr
            size = self.RISK_PER_TRADE / (abs(close - stop) / close + 1e-6)
            size = min(size, self.MAX_POSITION)
            if size > 0:
                self.sell(size=size, sl=stop)


class MacdLongShortStrategy(Strategy):
    """MACD histogram crossover with trend filter."""
    WARMUP_BARS = 35
    RISK_PER_TRADE = 0.02
    MAX_POSITION = 0.95
    STOP_ATR_MULT = 2.0
    USE_TREND_FILTER = True
    MIN_ADX = 15

    def init(self):
        pass

    def next(self):
        i = len(self.data.Close) - 1
        if i < self.WARMUP_BARS:
            return

        close = self.data.Close[-1]
        macd_hist = self.data.MACD_HIST[-1]
        macd_hist_prev = self.data.MACD_HIST[-2]
        atr = self.data.ATR[-1]
        sma200 = self.data.SMA200[-1]
        adx = self.data.ADX[-1]

        if pd.isna(macd_hist) or pd.isna(atr) or pd.isna(adx):
            return

        if self.position:
            hist_cross_down = macd_hist_prev >= 0 and macd_hist < 0
            hist_cross_up = macd_hist_prev <= 0 and macd_hist > 0

            if (self.position.is_long and hist_cross_down) or \
               (self.position.is_short and hist_cross_up):
                self.position.close()
            return

        hist_cross_up = macd_hist_prev <= 0 and macd_hist > 0
        hist_cross_down = macd_hist_prev >= 0 and macd_hist < 0

        trend_ok = not self.USE_TREND_FILTER or adx >= self.MIN_ADX
        price_above_ma = close > sma200

        if hist_cross_up and trend_ok and price_above_ma:
            stop = close - self.STOP_ATR_MULT * atr
            size = self.RISK_PER_TRADE / (abs(close - stop) / close + 1e-6)
            size = min(size, self.MAX_POSITION)
            if size > 0:
                self.buy(size=size, sl=stop)
        elif hist_cross_down and trend_ok and not price_above_ma:
            stop = close + self.STOP_ATR_MULT * atr
            size = self.RISK_PER_TRADE / (abs(close - stop) / close + 1e-6)
            size = min(size, self.MAX_POSITION)
            if size > 0:
                self.sell(size=size, sl=stop)


class RsiMeanReversionStrategy(Strategy):
    """RSI-based mean reversion with trend context."""
    WARMUP_BARS = 20
    RISK_PER_TRADE = 0.02
    MAX_POSITION = 0.95
    STOP_ATR_MULT = 2.0
    RSI_OVERSOLD = 30
    RSI_OVERBOUGHT = 70
    MAX_HOLD_BARS = 20

    def init(self):
        self.entry_bar = {}

    def next(self):
        i = len(self.data.Close) - 1
        if i < self.WARMUP_BARS:
            return

        close = self.data.Close[-1]
        rsi = self.data.RSI[-1]
        atr = self.data.ATR[-1]
        sma200 = self.data.SMA200[-1]

        if pd.isna(rsi) or pd.isna(atr):
            return

        # Close old positions (max hold)
        if self.position:
            entry_idx = self.entry_bar.get("long" if self.position.is_long else "short", i)
            if i - entry_idx >= self.MAX_HOLD_BARS:
                self.position.close()
                return

        if self.position:
            return

        # Mean reversion signals: buy oversold near support, short overbought near resistance
        if rsi < self.RSI_OVERSOLD and close > sma200 * 0.97:  # Slight pullback
            stop = close - self.STOP_ATR_MULT * atr
            size = self.RISK_PER_TRADE / (abs(close - stop) / close + 1e-6)
            size = min(size, self.MAX_POSITION)
            if size > 0:
                self.buy(size=size, sl=stop)
                self.entry_bar["long"] = i
        elif rsi > self.RSI_OVERBOUGHT and close < sma200 * 1.03:  # Slight rally
            stop = close + self.STOP_ATR_MULT * atr
            size = self.RISK_PER_TRADE / (abs(close - stop) / close + 1e-6)
            size = min(size, self.MAX_POSITION)
            if size > 0:
                self.sell(size=size, sl=stop)
                self.entry_bar["short"] = i


class BollingerBreakoutStrategy(Strategy):
    """Bollinger Bands breakout with long/short."""
    WARMUP_BARS = 25
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
        bb_upper = self.data.BB_UPPER[-1]
        bb_lower = self.data.BB_LOWER[-1]
        atr = self.data.ATR[-1]

        if pd.isna(bb_upper) or pd.isna(bb_lower) or pd.isna(atr):
            return

        if self.position:
            return

        # Breakout above upper band = long
        if close > bb_upper:
            stop = close - self.STOP_ATR_MULT * atr
            size = self.RISK_PER_TRADE / (abs(close - stop) / close + 1e-6)
            size = min(size, self.MAX_POSITION)
            if size > 0:
                self.buy(size=size, sl=stop)
        # Breakout below lower band = short
        elif close < bb_lower:
            stop = close + self.STOP_ATR_MULT * atr
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
        return f"{self.symbol:6} {self.strategy_name:20} | Return {self.return_pct:7.1f}% | Ann. {self.annualized_return_pct:6.1f}% | PF {self.profit_factor:5.2f} | MDD {self.max_drawdown_pct:6.1f}% | Trades {self.trades:4d} | Sharpe {self.sharpe_ratio:5.2f} | Pass {str(self.passes_gate):5} {self.notes}"


def run_backtest_one(
    symbol: str,
    frame: pd.DataFrame,
    strategy_cls: type[Strategy],
    indicator_adder,
    name: str,
) -> BacktestResult | None:
    """Run one backtest and return metrics."""
    if frame.empty or len(frame) < MIN_USABLE_BARS:
        return None

    try:
        enriched = indicator_adder(frame).dropna()
        if len(enriched) < MIN_USABLE_BARS:
            return None

        stats = Backtest(
            enriched,
            strategy_cls,
            cash=10_000.0,
            commission=0.0004,  # Binance maker/taker ~0.02-0.04%
            exclusive_orders=True,
        ).run()

        return_pct = float(stats.get("Return [%]", float("nan")))
        buy_hold_pct = float(stats.get("Buy & Hold Return [%]", float("nan")))
        profit_factor = float(stats.get("Profit Factor", float("nan")))
        max_dd_pct = abs(float(stats.get("Max. Drawdown [%]", float("inf"))))
        trades = int(stats.get("# Trades", 0))
        sharpe = float(stats.get("Sharpe Ratio", float("nan")))

        # Annualized return (assuming 252 trading days/year, daily data)
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

        notes = ""
        if not pd.isna(buy_hold_pct) and buy_hold_pct < return_pct < 0:
            notes = "[WARN: Strategy losing but B&H also losing]"
        elif not pd.isna(buy_hold_pct) and return_pct < buy_hold_pct * 0.5:
            notes = "[WARN: Much worse than B&H]"

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
            notes=notes,
        )
    except Exception as exc:  # noqa: BLE001
        return None


def fetch_one(symbol: str) -> pd.DataFrame | None:
    """Fetch perpetual futures OHLCV data."""
    try:
        # Format: BTC/USDT:USDT for USDT-M perpetual
        perp_symbol = f"{symbol}/USDT:USDT"
        frame = fetch_perp_ohlcv(perp_symbol, "1d", SINCE, None)
        if not frame.empty:
            print(f"  {symbol:6}: {len(frame):5d} bars")
        return frame
    except Exception as exc:  # noqa: BLE001
        print(f"  {symbol:6}: FETCH FAILED ({exc})")
        return None


def process_one_symbol(
    symbol: str,
    frame: pd.DataFrame,
) -> list[BacktestResult]:
    """Test all strategies on one symbol."""
    strategies = [
        (SupertrendLongShortStrategy, add_supertrend_indicators, "Supertrend"),
        (EmaCrossLongShortStrategy, add_ema_cross_indicators, "EMA-Cross"),
        (MacdLongShortStrategy, add_macd_indicators, "MACD"),
        (RsiMeanReversionStrategy, add_rsi_indicators, "RSI-MeanRev"),
        (BollingerBreakoutStrategy, add_bollinger_indicators, "BB-Breakout"),
    ]

    results = []
    for strat_cls, indicator_fn, name in strategies:
        result = run_backtest_one(symbol, frame, strat_cls, indicator_fn, name)
        if result:
            results.append(result)
    return results


def run_first_round(universe: list[str]) -> None:
    """First round: test all strategies on 10 key symbols."""
    print("\n" + "=" * 120)
    print("ROUND 1: Multi-Strategy Probe on High-Liquidity Symbols")
    print("=" * 120)
    print(f"Universe: {len(universe)} symbols")
    print(f"Strategies: 5 candidates (Supertrend, EMA-Cross, MACD, RSI-MeanRev, BB-Breakout)")
    print(f"Gates: Profit Factor >= {MIN_PROFIT_FACTOR}, Max Drawdown <= {MAX_DRAWDOWN_PCT}%, Trades >= {MIN_TRADES}")
    print()

    # Fetch data
    print("[1/3] Fetching perpetual futures daily OHLCV data...")
    frames: dict[str, pd.DataFrame] = {}
    for symbol in universe:
        frame = fetch_one(symbol)
        if frame is not None and not frame.empty:
            frames[symbol] = frame

    available = [s for s in universe if s in frames]
    print(f"  Available: {len(available)}/{len(universe)} symbols\n")

    # Backtest
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
            except Exception as exc:  # noqa: BLE001
                print(f"  [ERROR] {symbol}: {exc}")

    elapsed = time.monotonic() - start_time
    print(f"  Completed in {elapsed:.0f}s\n")

    # Aggregate results
    print("[3/3] Results Summary\n")

    # By strategy
    print("By Strategy (average metrics across passing symbols):")
    print("-" * 120)
    strategies = sorted(set(r.strategy_name for r in all_results))
    for strat in strategies:
        strat_results = [r for r in all_results if r.strategy_name == strat]
        passing = [r for r in strat_results if r.passes_gate]
        if not strat_results:
            continue

        avg_return = sum(r.return_pct for r in strat_results) / len(strat_results)
        avg_ann = sum(r.annualized_return_pct for r in strat_results) / len(strat_results)
        avg_pf = sum(r.profit_factor for r in strat_results if not pd.isna(r.profit_factor)) / max(len([r for r in strat_results if not pd.isna(r.profit_factor)]), 1)
        pass_pct = 100 * len(passing) / len(strat_results) if strat_results else 0

        print(f"  {strat:20} | Symbols {len(strat_results):2d} | Passing {len(passing):2d} ({pass_pct:5.1f}%) | "
              f"Avg Return {avg_return:7.1f}% | Avg Ann. {avg_ann:6.1f}% | Avg PF {avg_pf:5.2f}")

    print("\n" + "-" * 120)
    print("Best Individual Results (sorted by annualized return):")
    print("-" * 120)
    sorted_results = sorted(
        [r for r in all_results if r.passes_gate],
        key=lambda x: x.annualized_return_pct,
        reverse=True,
    )
    for r in sorted_results[:15]:
        print(r)

    print("\n" + "-" * 120)
    print("ELIMINATION DECISIONS:")
    print("-" * 120)
    passing_by_strat = {}
    for strat in strategies:
        strat_results = [r for r in all_results if r.strategy_name == strat]
        passing = len([r for r in strat_results if r.passes_gate])
        passing_by_strat[strat] = passing

    for strat in sorted(strategies):
        passing = passing_by_strat[strat]
        total = len([r for r in all_results if r.strategy_name == strat])
        status = "KEEP" if passing >= 2 else "ELIMINATE"
        print(f"  {strat:20}: {passing}/{total} passing -> {status}")

    # Save detailed results to CSV
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
    csv_path = "/tmp/futures_round1_results.csv"
    df.to_csv(csv_path, index=False)
    print(f"\nDetailed results saved to: {csv_path}")


if __name__ == "__main__":
    run_first_round(FIRST_ROUND_UNIVERSE)
