"""Direct futures long/short strategy probe using Docker.

Simplified version that reuses existing patterns and runs via Docker.
"""
from __future__ import annotations

import json
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

import pandas as pd
from backtesting import Backtest

from app.futures_data import fetch_perp_ohlcv
from app.futures_strategies import LongShortTrendStrategy
from app.indicators import add_supertrend_adx_indicators
from app.more_indicators import add_ema_cross_indicators

MIN_USABLE_BARS = 250
MIN_PROFIT_FACTOR = 1.30
MAX_DRAWDOWN_PCT = 20.0
MIN_TRADES = 5
SINCE = "2022-01-01T00:00:00Z"

# First round: 10 high-liquidity symbols
FIRST_ROUND_UNIVERSE = ["BTC", "ETH", "BNB", "SOL", "XRP", "DOGE", "ADA", "AVAX", "LINK", "UNI"]


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


def process_one(symbol: str, frame: pd.DataFrame) -> dict:
    """Test LongShortTrendStrategy on one symbol."""
    if frame.empty or len(frame) < MIN_USABLE_BARS:
        return None

    try:
        enriched = add_supertrend_adx_indicators(frame).dropna()
        if len(enriched) < MIN_USABLE_BARS:
            return None

        stats = Backtest(
            enriched,
            LongShortTrendStrategy,
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
            "strategy": "Supertrend-LongShort",
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
        print(f"  [ERROR] {symbol}: {exc}")
        return None


def run() -> None:
    """Run first round probe."""
    print("\n" + "=" * 100)
    print("ROUND 1: Futures Long/Short Strategy Probe")
    print("=" * 100)
    print(f"Strategy: LongShortTrendStrategy (Supertrend-based)")
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
    results = []
    max_workers = min(len(available) or 1, os.cpu_count() or 4, 4)

    start_time = time.monotonic()
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_one, s, frames[s]): s for s in available}
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                result = future.result()
                if result:
                    results.append(result)
            except Exception as exc:
                print(f"  [ERROR] {symbol}: {exc}")

    elapsed = time.monotonic() - start_time
    print(f"  Completed in {elapsed:.0f}s\n")

    print("[3/3] Results\n")
    print("-" * 100)

    passing = [r for r in results if r["passes_gate"]]
    print(f"Gate passes: {len(passing)}/{len(results)}")
    print()

    if passing:
        passing.sort(key=lambda r: r["annualized_return_pct"], reverse=True)
        print("Passing Results (sorted by annualized return):")
        for r in passing:
            print(f"  {r['symbol']:6} | Return {r['return_pct']:7.1f}% | Ann. {r['annualized_return_pct']:6.1f}% | "
                  f"PF {r['profit_factor']:5.2f} | MDD {r['max_drawdown_pct']:6.1f}% | Trades {r['trades']:4d} | "
                  f"B&H {r['buy_hold_pct']:7.1f}%")

    print("\nAll Results:")
    results.sort(key=lambda r: r["return_pct"], reverse=True)
    for r in results:
        status = "PASS" if r["passes_gate"] else "FAIL"
        print(f"  {r['symbol']:6} | Return {r['return_pct']:7.1f}% | Ann. {r['annualized_return_pct']:6.1f}% | "
              f"PF {r['profit_factor']:5.2f} | MDD {r['max_drawdown_pct']:6.1f}% | Trades {r['trades']:4d} | [{status}]")

    # Save to CSV
    df = pd.DataFrame(results)
    csv_path = "/app/futures_round1_supertrend_results.csv"
    df.to_csv(csv_path, index=False)
    print(f"\nResults saved to: {csv_path}")


if __name__ == "__main__":
    run()
