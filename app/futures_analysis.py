"""Analysis and elimination framework for futures strategy backtesting results.

Systematically analyzes results to:
1. Identify which strategies and symbols show promise
2. Flag overfitting patterns and warning signs
3. Document elimination decisions with reasoning
4. Rank survivors for next iteration
5. Detect whether gains are due to strategy edge or just riding bull/bear markets
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd


def analyze_results(csv_path: str) -> None:
    """Load backtest results CSV and perform systematic analysis."""
    df = pd.read_csv(csv_path)

    print("\n" + "=" * 140)
    print("STRATEGY ANALYSIS & ELIMINATION FRAMEWORK")
    print("=" * 140)

    # Basic stats
    print(f"\nDataset: {len(df)} results from {df['Symbol'].nunique()} symbols x {df['Strategy'].nunique()} strategies")
    passing = df[df["Passes"] == True]
    print(f"Gate passes: {len(passing)}/{len(df)} ({100*len(passing)/len(df):.1f}%)")

    # ========================================================================
    # RED FLAGS & OVERFITTING DETECTION
    # ========================================================================
    print("\n" + "=" * 140)
    print("RED FLAGS & OVERFITTING DETECTION")
    print("=" * 140)

    print("\n1. Low Trade Count (< 10 trades) — Unreliable Statistics:")
    low_trades = df[(df["Passes"] == True) & (df["Trades"] < 10)]
    if len(low_trades) > 0:
        for _, row in low_trades.iterrows():
            print(f"  WARN: {row['Symbol']:6} {row['Strategy']:20} | {row['Trades']:3d} trades | "
                  f"Return {row['Return%']:7.1f}% | PF {row['ProfitFactor']:5.2f}")
    else:
        print("  PASS: No low-trade-count issues")

    print("\n2. Strategy Returns Much Lower Than Buy&Hold (Returns < 50% of B&H) — Likely No Edge:")
    underperform = df[(df["Passes"] == True) & (df["B&H%"] > 0)]
    underperform = underperform[underperform["Return%"] < underperform["B&H%"] * 0.5]
    if len(underperform) > 0:
        for _, row in underperform.iterrows():
            print(f"  WARN: {row['Symbol']:6} {row['Strategy']:20} | Strategy {row['Return%']:7.1f}% "
                  f"vs B&H {row['B&H%']:7.1f}%")
    else:
        print("  PASS: No significant underperformance vs B&H")

    print("\n3. Negative Returns But Passing Gate (Due to High Profit Factor on Few Trades):")
    negative_passing = df[(df["Passes"] == True) & (df["Return%"] < 0)]
    if len(negative_passing) > 0:
        for _, row in negative_passing.iterrows():
            print(f"  WARN: {row['Symbol']:6} {row['Strategy']:20} | Return {row['Return%']:7.1f}% "
                  f"PF {row['ProfitFactor']:5.2f} Trades {row['Trades']:3d}")
    else:
        print("  PASS: No negative-return passers")

    print("\n4. Extreme Sharpe Ratios (>3 or <-1) — Likely Curve-Fit:")
    extreme_sharpe = df[(df["Sharpe"].notna()) & ((df["Sharpe"] > 3) | (df["Sharpe"] < -1))]
    if len(extreme_sharpe) > 0:
        for _, row in extreme_sharpe.iterrows():
            print(f"  WARN: {row['Symbol']:6} {row['Strategy']:20} | Sharpe {row['Sharpe']:6.2f} "
                  f"Return {row['Return%']:7.1f}% Trades {row['Trades']:3d}")
    else:
        print("  PASS: No extreme Sharpe ratios")

    # ========================================================================
    # STRATEGY-LEVEL ANALYSIS
    # ========================================================================
    print("\n" + "=" * 140)
    print("STRATEGY-LEVEL ANALYSIS (Ranked by Avg Annualized Return on Passing Symbols)")
    print("=" * 140)

    for strat in sorted(df["Strategy"].unique()):
        strat_df = df[df["Strategy"] == strat]
        passing_strat = strat_df[strat_df["Passes"] == True]

        if len(strat_df) == 0:
            continue

        pass_pct = 100 * len(passing_strat) / len(strat_df)
        avg_return = strat_df["Return%"].mean()
        avg_ann = passing_strat["AnnualizedReturn%"].mean() if len(passing_strat) > 0 else float("nan")
        avg_pf = passing_strat["ProfitFactor"].mean() if len(passing_strat) > 0 else float("nan")
        avg_dd = passing_strat["MaxDD%"].mean() if len(passing_strat) > 0 else float("nan")
        avg_trades = passing_strat["Trades"].mean() if len(passing_strat) > 0 else float("nan")

        status = "KEEP" if len(passing_strat) >= 2 else "CONSIDER_ELIMINATE"
        print(f"\n{strat:25} [{status}]")
        print(f"  Symbols tested: {len(strat_df)} | Passing: {len(passing_strat)} ({pass_pct:.1f}%)")
        print(f"  Avg Return: {avg_return:7.1f}% | Avg Ann (passing): {avg_ann:6.1f}% | Avg PF: {avg_pf:5.2f} | Avg MDD: {avg_dd:6.1f}%")
        print(f"  Avg Trades (passing): {avg_trades:5.1f}")

        if len(passing_strat) > 0:
            print(f"  Best: {passing_strat.loc[passing_strat['Return%'].idxmax(), 'Symbol']} "
                  f"({passing_strat['Return%'].max():.1f}%)")

    # ========================================================================
    # SYMBOL-LEVEL ANALYSIS
    # ========================================================================
    print("\n" + "=" * 140)
    print("SYMBOL-LEVEL SUMMARY (Best & Worst Performers)")
    print("=" * 140)

    symbol_summary = []
    for sym in sorted(df["Symbol"].unique()):
        sym_df = df[df["Symbol"] == sym]
        passing_sym = sym_df[sym_df["Passes"] == True]

        best_return = sym_df["Return%"].max()
        best_strategy = sym_df.loc[sym_df["Return%"].idxmax(), "Strategy"]
        best_ann = passing_sym["AnnualizedReturn%"].max() if len(passing_sym) > 0 else float("nan")

        symbol_summary.append({
            "Symbol": sym,
            "BestReturn%": best_return,
            "BestStrategy": best_strategy,
            "PassingCount": len(passing_sym),
            "BestAnn%": best_ann,
        })

    summary_df = pd.DataFrame(symbol_summary)
    summary_df = summary_df.sort_values("BestReturn%", ascending=False)

    print("\nBest Performers (by max return across strategies):")
    print("-" * 140)
    for _, row in summary_df.head(10).iterrows():
        print(f"  {row['Symbol']:6} | Best: {row['BestReturn%']:7.1f}% ({row['BestStrategy']:20}) | "
              f"Ann: {row['BestAnn%']:6.1f}% | Passing: {row['PassingCount']:2d}")

    print("\nWorst Performers:")
    print("-" * 140)
    for _, row in summary_df.tail(5).iterrows():
        print(f"  {row['Symbol']:6} | Best: {row['BestReturn%']:7.1f}% ({row['BestStrategy']:20}) | "
              f"Passing: {row['PassingCount']:2d}")

    # ========================================================================
    # SURVIVORS FOR NEXT ROUND
    # ========================================================================
    print("\n" + "=" * 140)
    print("SURVIVORS FOR NEXT ROUND (Strategies & Symbols to Keep Testing)")
    print("=" * 140)

    # Strategies to keep: those with 2+ passing symbols AND avg annualized return > 5%
    survivor_strategies = []
    for strat in sorted(df["Strategy"].unique()):
        strat_df = df[df["Strategy"] == strat]
        passing_strat = strat_df[strat_df["Passes"] == True]
        avg_ann = passing_strat["AnnualizedReturn%"].mean() if len(passing_strat) > 0 else float("-inf")

        if len(passing_strat) >= 2 and avg_ann > 5.0:
            survivor_strategies.append(strat)
            print(f"  KEEP: {strat:25} ({len(passing_strat)} symbols, avg ann {avg_ann:.1f}%)")

    # Symbols to focus on: those with multiple passing strategies
    symbol_pass_counts = df[df["Passes"] == True].groupby("Symbol").size()
    survivor_symbols = symbol_pass_counts[symbol_pass_counts >= 2].index.tolist()
    print(f"\n  Symbols with 2+ passing strategies: {', '.join(sorted(survivor_symbols))}")

    # ========================================================================
    # ELIMINATION SUMMARY
    # ========================================================================
    print("\n" + "=" * 140)
    print("ELIMINATION SUMMARY")
    print("=" * 140)

    all_strategies = sorted(df["Strategy"].unique())
    for strat in all_strategies:
        strat_df = df[df["Strategy"] == strat]
        passing_strat = strat_df[strat_df["Passes"] == True]
        avg_ann = passing_strat["AnnualizedReturn%"].mean() if len(passing_strat) > 0 else float("-inf")

        if strat in survivor_strategies:
            reason = f"KEEP (avg ann {avg_ann:.1f}%, {len(passing_strat)} symbols)"
        elif len(passing_strat) < 2:
            reason = f"ELIMINATE: Only {len(passing_strat)} passing symbol(s)"
        elif avg_ann <= 5.0:
            reason = f"ELIMINATE: Avg annualized {avg_ann:.1f}% too low (target 10%+)"
        else:
            reason = "CONDITIONAL: Review metrics"

        print(f"  {strat:25} [{reason}]")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m app.futures_analysis <csv_file>")
        sys.exit(1)

    analyze_results(sys.argv[1])
