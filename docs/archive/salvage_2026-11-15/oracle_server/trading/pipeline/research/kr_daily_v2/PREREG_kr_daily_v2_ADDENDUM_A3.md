# Addendum A3 to PREREG_kr_daily_v2: post-hoc random-portfolio null diagnostic

Written 2026-11-05, after the v2 pre-registration and after reviewing the completed US-daily-v2 house-standard analysis. This diagnostic is explicitly post-hoc: the main KR v2 pre-registration omitted a random-portfolio null and per-trial Bonferroni/BH correction, while the US v2 report used them. No v2 strategy result has been inspected as of this addendum.

## Fixed diagnostic

- Applies to all nine V-trials; B1 is the comparison benchmark. For each strategy, compute annualized Sharpe of daily active returns `strategy_return - B1_return`, separately over the registered IS and OOS windows. This is the observed statistic and the corresponding statistic for each null portfolio.
- Null portfolios use the same point-in-time eligible pool, signal/rebalance dates, number of constituents and weights, market-filter cash decisions, 21-session cadence, and exact entry/exit event dates for the daily-slot strategies. V3 samples from its registered eligible universe; other trials sample from U500. V7/V8 retain each observed slot's entry/exit timing and 5% weight while randomizing entry identities from the latest-month-end U500 membership in force at that signal date, excluding names already held. Exit counts and dates match the observed signal, while the null closes randomly held names.
- The same `bt2.simulate` execution, deferred-order behavior, slippage, commission, sell tax, and cash rules are applied to each null portfolio.
- Draw 200 independent portfolios for each non-slot trial and 100 for V7/V8, using deterministic NumPy seeds `20261105 + trial_index`. The p-value is `(1 + count(null_active_sharpe >= observed_active_sharpe)) / (1 + draws)`. Report IS p-values for context. Apply Bonferroni and Benjamini-Hochberg (q) across the nine OOS p-values.
- Report null medians and 95th percentiles for IS and OOS. Store output only in `results_null.json`.

## Interpretation and boundary

This is a post-hoc diagnostic with selection count = 0. It does not alter or override any registered hypothesis, selection rule, multiple-testing DSR value, gate criterion (a)-(g), or the final gate outcome. It is reported alongside those pre-registered results and cannot promote a strategy. The diagnostic addresses whether randomized constituents with the same registered trading schedule outperform the selected rule; it does not cure market-path contamination, missing data, or any design limitation already disclosed in the main registration.
