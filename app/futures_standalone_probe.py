"""Standalone futures backtest probe with minimal dependencies.

Uses only pandas/numpy for indicators to avoid pandas_ta import issues.
Can be run directly: python -u app/futures_standalone_probe.py
"""
from __future__ import annotations

import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np
import pandas as pd
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

FIRST_ROUND_UNIVERSE = ["BTC", "ETH", "BNB", "SOL", "XRP", "DOGE", "ADA", "AVAX", "LINK", "UNI"]


# ============================================================================
# SIMPLE INDICATORS (no pandas_ta)
# ============================================================================

def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Average True Range."""
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """ADX simplified: just return ATR for now (a proxy for trend strength)."""
    # Proper ADX would require +DI/-DI calculation, but for this, high ADR from ATR works
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr_val = tr.rolling(period).mean()

    # ADX proxy: higher volatility swings imply stronger trend
    # Use ratio of recent price range to ATR
    price_range = (high - low).rolling(20).mean()
    adx_proxy = 100 * atr_val / (price_range + 1e-6)
    adx_proxy = adx_proxy.rolling(5).mean()
    return adx_proxy.clip(0, 100)


def ema(series: pd.Series, period: int) -> pd.Series:
    """Exponential moving average."""
    return series.ewm(span=period, adjust=False).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index."""
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = -delta.where(delta < 0, 0).rolling(period).mean()
    rs = gain / (loss + 1e-6)
    rsi_val = 100 - (100 / (1 + rs))
    return rsi_val


def supertrend(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 10, mult: float = 3.0) -> tuple[pd.Series, pd.Series]:
    """Supertrend indicator. Returns (direction, st_line)."""
    hl2 = (high + low) / 2
    atr_val = atr(high, low, close, period)

    basic_ub = hl2 + mult * atr_val
    basic_lb = hl2 - mult * atr_val

    final_ub = basic_ub.copy()
    final_lb = basic_lb.copy()

    for i in range(1, len(basic_ub)):
        final_ub.iloc[i] = min(basic_ub.iloc[i], final_ub.iloc[i-1])
        final_lb.iloc[i] = max(basic_lb.iloc[i], final_lb.iloc[i-1])

    direction = pd.Series(1, index=close.index)
    for i in range(1, len(close)):
        if close.iloc[i] <= final_ub.iloc[i]:
            direction.iloc[i] = 1
        else:
            direction.iloc[i] = -1

    st_line = pd.Series(index=close.index, dtype=float)
    for i in range(len(close)):
        if direction.iloc[i] == 1:
            st_line.iloc[i] = final_lb.iloc[i]
        else:
            st_line.iloc[i] = final_ub.iloc[i]

    return direction, st_line


# ============================================================================
# STRATEGIES
# ============================================================================

class SupertrendLongShort(Strategy):
    """Simple Supertrend long/short strategy."""
    WARMUP_BARS = 30
    MIN_ADX = 20
    RISK_PER_TRADE = 0.02
    MAX_POSITION = 0.95

    def init(self):
        pass

    def next(self):
        i = len(self.data.Close) - 1
        if i < self.WARMUP_BARS:
            return

        close = self.data.Close[-1]
        st_now = self.data.ST_DIR[-1]
        st_prev = self.data.ST_DIR[-2]
        st_line = self.data.ST_LINE[-1]
        adx_val = self.data.ADX_VAL[-1]

        if pd.isna(adx_val) or pd.isna(st_line):
            return

        if self.position:
            if (self.position.is_long and st_now < 0) or \
               (self.position.is_short and st_now > 0):
                self.position.close()
            return

        if adx_val < self.MIN_ADX:
            return

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


class EmaCrossLongShort(Strategy):
    """EMA crossover long/short."""
    WARMUP_BARS = 25
    RISK_PER_TRADE = 0.02
    MAX_POSITION = 0.95

    def init(self):
        pass

    def next(self):
        i = len(self.data.Close) - 1
        if i < self.WARMUP_BARS:
            return

        close = self.data.Close[-1]
        ema_fast = self.data.EMA_FAST[-1]
        ema_fast_prev = self.data.EMA_FAST[-2]
        ema_slow = self.data.EMA_SLOW[-1]
        ema_slow_prev = self.data.EMA_SLOW[-2]
        atr_val = self.data.ATR_VAL[-1]

        if pd.isna(ema_fast) or pd.isna(ema_slow) or pd.isna(atr_val):
            return

        if self.position:
            cross_down = ema_fast_prev >= ema_slow_prev and ema_fast < ema_slow
            cross_up = ema_fast_prev <= ema_slow_prev and ema_fast > ema_slow
            if (self.position.is_long and cross_down) or (self.position.is_short and cross_up):
                self.position.close()
            return

        cross_up = ema_fast_prev <= ema_slow_prev and ema_fast > ema_slow
        cross_down = ema_fast_prev >= ema_slow_prev and ema_fast < ema_slow

        if cross_up:
            stop = close - 2.0 * atr_val
            size = self.RISK_PER_TRADE / (abs(close - stop) / close + 1e-6)
            size = min(size, self.MAX_POSITION)
            if size > 0:
                self.buy(size=size, sl=stop)
        elif cross_down:
            stop = close + 2.0 * atr_val
            size = self.RISK_PER_TRADE / (abs(close - stop) / close + 1e-6)
            size = min(size, self.MAX_POSITION)
            if size > 0:
                self.sell(size=size, sl=stop)


# ============================================================================
# BACKTEST RUNNER
# ============================================================================

def add_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    """Add all required indicators."""
    out = frame.copy()
    out["ATR_VAL"] = atr(out["High"], out["Low"], out["Close"], 14)
    out["ADX_VAL"] = adx(out["High"], out["Low"], out["Close"], 14)
    out["EMA_FAST"] = ema(out["Close"], 8)
    out["EMA_SLOW"] = ema(out["Close"], 21)
    out["RSI_VAL"] = rsi(out["Close"], 14)
    out["ST_DIR"], out["ST_LINE"] = supertrend(out["High"], out["Low"], out["Close"], 10, 3.0)
    return out


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


def backtest_one(symbol: str, frame: pd.DataFrame, strategy_cls: type[Strategy], name: str) -> dict | None:
    """Run one backtest."""
    if frame.empty or len(frame) < MIN_USABLE_BARS:
        return None

    try:
        enriched = add_indicators(frame).dropna()
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

        return {
            "symbol": symbol,
            "strategy": name,
            "return_pct": return_pct,
            "buy_hold_pct": buy_hold_pct,
            "annualized_return_pct": annualized_pct,
            "profit_factor": profit_factor,
            "max_drawdown_pct": max_dd_pct,
            "trades": trades,
            "sharpe_ratio": sharpe,
            "passes_gate": passes,
        }
    except Exception as exc:
        return None


def process_symbol(symbol: str, frame: pd.DataFrame) -> list[dict]:
    """Test multiple strategies on one symbol."""
    strategies = [
        (SupertrendLongShort, "Supertrend"),
        (EmaCrossLongShort, "EMA-Cross"),
    ]

    results = []
    for strat_cls, name in strategies:
        result = backtest_one(symbol, frame, strat_cls, name)
        if result:
            results.append(result)
    return results


def run() -> None:
    """Run first round probe."""
    print("\n" + "=" * 110)
    print("ROUND 1: Crypto Futures Long/Short Strategy Probe (Standalone)")
    print("=" * 110)
    print(f"Strategies: Supertrend, EMA-Cross")
    print(f"Universe: {len(FIRST_ROUND_UNIVERSE)} symbols")
    print()

    print("[1/3] Fetching perpetual futures daily OHLCV...")
    frames: dict[str, pd.DataFrame] = {}
    for symbol in FIRST_ROUND_UNIVERSE:
        frame = fetch_one(symbol)
        if frame is not None and not frame.empty:
            frames[symbol] = frame

    available = [s for s in FIRST_ROUND_UNIVERSE if s in frames]
    print(f"  Available: {len(available)}/{len(FIRST_ROUND_UNIVERSE)}\n")

    print("[2/3] Running backtests...")
    all_results = []
    max_workers = min(len(available) or 1, os.cpu_count() or 4, 4)

    start = time.monotonic()
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_symbol, s, frames[s]): s for s in available}
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                results = future.result()
                all_results.extend(results)
            except Exception:
                pass

    elapsed = time.monotonic() - start
    print(f"  Completed in {elapsed:.0f}s\n")

    print("[3/3] Results & Analysis\n")
    print("=" * 110)

    passing = [r for r in all_results if r["passes_gate"]]
    print(f"GATE PASSES: {len(passing)}/{len(all_results)} ({100*len(passing)/len(all_results):.1f}%)\n")

    # By strategy
    print("Summary by Strategy:")
    print("-" * 110)
    for strat in sorted(set(r["strategy"] for r in all_results)):
        strat_res = [r for r in all_results if r["strategy"] == strat]
        passing_strat = [r for r in strat_res if r["passes_gate"]]
        avg_ann = sum(r["annualized_return_pct"] for r in passing_strat) / len(passing_strat) if passing_strat else float("nan")
        print(f"  {strat:15} | {len(passing_strat):2d}/{len(strat_res):2d} pass | Avg Ann: {avg_ann:6.1f}%")

    print("\n" + "=" * 110)
    print("Individual Results (sorted by annualized return):")
    print("-" * 110)
    sorted_all = sorted(all_results, key=lambda r: r["annualized_return_pct"], reverse=True)
    for r in sorted_all[:15]:
        status = "PASS" if r["passes_gate"] else "FAIL"
        print(f"  {r['symbol']:6} {r['strategy']:15} | Return {r['return_pct']:7.1f}% | Ann {r['annualized_return_pct']:6.1f}% | "
              f"PF {r['profit_factor']:5.2f} | MDD {r['max_drawdown_pct']:6.1f}% | Trades {r['trades']:3d} | [{status}]")

    print("\n" + "=" * 110)
    print("ELIMINATION DECISIONS:")
    print("-" * 110)
    for strat in sorted(set(r["strategy"] for r in all_results)):
        strat_res = [r for r in all_results if r["strategy"] == strat]
        passing_strat = [r for r in strat_res if r["passes_gate"]]
        avg_ann = sum(r["annualized_return_pct"] for r in passing_strat) / len(passing_strat) if passing_strat else float("-inf")
        status = "KEEP" if len(passing_strat) >= 2 else "CONSIDER_ELIMINATE"
        print(f"  {strat:15}: {len(passing_strat)}/{len(strat_res)} pass, avg ann {avg_ann:6.1f}% -> {status}")

    # Save CSV
    df = pd.DataFrame(all_results)
    csv_path = "/tmp/futures_round1_results.csv"
    df.to_csv(csv_path, index=False)
    print(f"\nResults saved to: {csv_path}")


if __name__ == "__main__":
    run()
