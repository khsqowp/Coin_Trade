# US daily v2: cross-sectional rules on the point-in-time S&P 500 (backtest only, no orders)

**There is still no edge, and I recommend nothing goes to the next stage.**

## Summary

Round 2 extended round 1's single-symbol (SPY) daily-bar research to the full point-in-time S&P 500 universe, testing 9 cross-sectional rule candidates sourced from house strategy archetypes (momentum, mean-reversion, breakout) rather than literal crypto-repo code.

- IS-selected rule: `mom12_1_mkt` (12-month momentum, skip most recent month, with SPY 200-day market filter). IS Sharpe 0.74 (best of 9).
- OOS Sharpe: 0.236 vs SPY buy-and-hold OOS Sharpe 0.724. Rule underperforms the benchmark badly out of sample.
- DSR (deflated Sharpe ratio, corrected for the multiple-testing load across both research rounds): 0.66, below the 0.90 pre-registered acceptance gate.
- Random-portfolio null test: p = 0.66 — indistinguishable from picking 50 random stocks monthly.
- All 9 tested rules failed to beat SPY out of sample. Two (weekly mean-reversion, RSI(2) pullback) showed a real raw signal in-sample but it is fully consumed by realistic 20bp round-trip transaction costs.

## Methodology discipline (round 2 additions)

- Two addenda filed and timestamped BEFORE seeing OOS/gross-null results (A1, A2), per pre-registration rules:
  - A1: excluded 10 tickers found to have ticker-reuse contamination (a different company previously traded under the same symbol — e.g. PARA→"Parabolic Technologies", BBT→"Beacon Financial" — identified via a vendor-identity audit added to `usdata.py`).
  - A2: fixed a double-counted corporate-action adjustment bug that produced fake one-day return spikes (e.g. DHR +61% in a single day in 2016) from spin-off adjustments being applied twice; repaired mechanically and re-ran. The same rule (`mom12_1_mkt`) was re-selected with IS Sharpe moving by <= 0.008 — confirms the bug wasn't driving the result.
- Self-identified and corrected a flaw in its own pre-registered null-test design mid-task: the original random-portfolio null redraws constituents every month (symmetric with monthly-rebalance rules) but is asymmetric with cost structure for rules that hold names longer, inflating apparent significance for monthly rules. Disclosed honestly, added a post-hoc "gross-cost diagnostic" null (selection count = 0, does not change any gate) to re-check — under the gross-cost null, the one rule that looked marginally significant (X9 trend_breadth, p=0.005 net) rose to p=0.025 gross, and after Benjamini-Hochberg correction across all trials, q=0.15 — not significant.
- Quantified survivorship bias directly: point-in-time universe construction (vs current-constituents-only) reduces apparent annual return by roughly 0.7-1.5%/yr, consistent with literature.
- Full point-in-time S&P 500 membership history used (not current constituents), avoiding hindsight bias in universe selection.

## Recommendation

Nothing proceeds to development/shadow-test. Do not continue searching indicator variants on this dataset — two independent research rounds (SPY-only in round 1, full-universe cross-sectional in round 2) have now both found no exploitable edge under honest OOS/DSR/null testing.

If a future round is warranted, it should either:
- use a paid survivorship-free database (CRSP, Norgate, Sharadar) instead of the free Yahoo-chart-endpoint source, or
- use a turnover-matched random-portfolio null from the start (not added post-hoc), or
- pursue a materially different hypothesis class rather than more momentum/mean-reversion variants.

## Files (server, not yet committed to git)

- `src/tp/usdata.py` (extended): Yahoo chart-endpoint client, vendor-identity metadata (company name/instrument type/exchange/currency/first-trade-date) for ticker-reuse auditing, negative-cache for 404/empty/short series.
- `src/tp/fetch_universe.py` (new): pulls full point-in-time S&P 500 membership list.
- `research/us_daily_v2/`: `usbt2.py`, `test_usbt2.py`, `PREREG_us_daily_v2.md`+timestamp, `PREREG_us_daily_v2_addendum_A1.md`+timestamp, `PREREG_us_daily_v2_addendum_A2.md`+timestamp, `coverage.json`, `data_quality_universe.json`, `lookahead_check.json`, `is_selection.json`, `oos_results.json`, `sensitivity.json`, `null_results.json`, `null_gross_diagnostic.json`, `equity_curves.csv`, `uncorrected_run/`, `fetch.log`, `stage_*.log`.
- `runs/research/us_daily_v2/` (gitignored): `trials.sqlite`, `panel.pkl`, `is_selection.json`.
- `data/us_daily/` (gitignored): ~720 symbol caches + `pit/`/`missing/`.
