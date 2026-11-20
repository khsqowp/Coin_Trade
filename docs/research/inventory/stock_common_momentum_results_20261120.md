# KR/US common-panel momentum replay — v1 broad-cache sensitivity, exploratory only

Run date: 2026-11-20. This replay uses existing, already-inspected rules on the
same internally valid, positive-volume panel per market with a common cost and
NAV accounting model. It is not untouched OOS evidence: the input cohort is a
current-survivor cache, prior results were reviewed, and corporate-action
provenance remains unresolved.

## Frozen scope

- Preregistration: [`PREREG_STOCK_COMMON_MOMENTUM_EXPLORATORY_20261120.md`](PREREG_STOCK_COMMON_MOMENTUM_EXPLORATORY_20261120.md)
- Canonical complete run: [`runs/stock_common_momentum_20261120_retry2/`](runs/stock_common_momentum_20261120_retry2/)
- This v1 run includes KR inverse ETF `114800` and US inverse ETF `SH`. It is
  retained as the original 92-file broad-cache sensitivity, not the core
  stock/ETF cohort. The inverse-excluded 91-symbol v2 result is recorded in
  [`stock_common_momentum_results_20261120_v2.md`](stock_common_momentum_results_20261120_v2.md).
- KR: 92 instruments, 832 common eligible sessions, 2023-01-05 to 2026-08-06;
  60-session momentum, monthly top-10 rebalance, with and without the benchmark
  SMA200 cash gate.
- US: 92 instruments, 1,187 common eligible sessions, 2021-07-29 to 2026-11-12;
  126-session momentum, daily and monthly top-10 rebalance, with and without
  the SPY SMA200 cash gate.
- Close-only signal based on the previous completed session; execute at the
  next eligible close. Shares and cash are accounted explicitly; terminal
  holdings are liquidated with modeled costs.
- Each candidate is run under the source-audited base and stress assumptions.
  Buy-and-hold comparators are included under both scenarios.
- No parameters, symbols, or candidate rules were selected from these results.

## Results

All percentages below are historical CAGR / MDD. Round trips are fully closed
positions over the entire exposed historical interval, not OOS-independent
trades.

| Market | Fixed rule | Cost | CAGR | MDD | Sharpe | Full-period round trips | One-way turnover (initial NAV) |
|---|---|---|---:|---:|---:|---:|---:|
| KR | 60-session monthly top-10 | Base | 66.55% | 46.95% | 1.441 | 183 | 51.44× |
| KR | 60-session monthly top-10 | Stress | 65.60% | 46.96% | 1.427 | 183 | 50.81× |
| KR | Same + SMA200 cash gate | Base | 33.84% | 46.95% | 0.972 | 123 | 21.43× |
| KR | Same + SMA200 cash gate | Stress | 33.33% | 46.96% | 0.961 | 123 | 21.26× |
| KR | Equal-weight buy-and-hold | Base | 40.93% | 35.72% | 1.283 | 92 | 2.08× |
| KR | Equal-weight buy-and-hold | Stress | 40.89% | 35.72% | 1.281 | 92 | 2.08× |
| US | 126-session daily top-10 | Base | 30.44% | 33.74% | 1.036 | 841 | 156.54× |
| US | 126-session daily top-10 | Stress | 10.56% | 38.23% | 0.498 | 841 | 96.96× |
| US | Same + SMA200 cash gate | Base | 19.53% | 33.74% | 0.829 | 641 | 109.76× |
| US | Same + SMA200 cash gate | Stress | 5.39% | 38.23% | 0.350 | 641 | 77.89× |
| US | 126-session monthly top-10 | Base | 32.73% | 42.56% | 1.053 | 188 | 39.32× |
| US | 126-session monthly top-10 | Stress | 28.10% | 43.63% | 0.943 | 188 | 35.22× |
| US | Same + SMA200 cash gate | Base | 18.72% | 42.56% | 0.777 | 145 | 24.73× |
| US | Same + SMA200 cash gate | Stress | 15.52% | 43.63% | 0.678 | 145 | 22.91× |
| US | Equal-weight buy-and-hold | Base | 18.34% | 22.54% | 0.900 | 92 | 1.62× |
| US | Equal-weight buy-and-hold | Stress | 18.13% | 22.54% | 0.891 | 92 | 1.61× |

## Disposition

**No strategy passes the stock gates.** Every momentum candidate exceeds the
30% MDD cap in both costs. The KR ungated result has 183 full-period closes,
and the US monthly result has 188; neither reaches the 200-trade threshold even
before the stricter independent OOS requirement. The US daily base-cost cell
meets the historical CAGR/Sharpe numbers but fails MDD; stress-cost Sharpe and
CAGR also deteriorate materially. The SMA200 overlay lowers exposure but does
not fix the peak-to-trough loss and weakens Sharpe.

The headline KR CAGR is heavily conditioned on the short 2023–2026 common
panel; it is not evidence of “all-regime” performance. Neither market can be
promoted because constituent membership is not point-in-time and split,
delisting, merger, dividend, and adjustment provenance are not certified. The
current report therefore records the candidates as `VALIDATION_REQUIRED`, not
as successful strategies. No robustness/portfolio promotion phase is run on
these cells.

## Audit and reproduction

- Canonical run status is `exploratory_historical_exposed`; the summary records
  the exact command argv, input SHA-256 for each of 184 CSV files, aggregate
  input fingerprint, preregistration hash, and code hash.
- There are 16 cells (12 candidate/cost cells plus 4 benchmark/cost cells),
  15,242 NAV observations, and 4,610 closed-position ledger rows.
- An independent audit recomputed each cell's CAGR, MDD, and Sharpe from its
  daily NAV; all matched the stored summary to 1e-10. Per-cell round-trip counts
  matched the separate ledger. No rebalance event left negative cash.
- Fixed data-panel preflight passed: KR 92/92 files, 832 sessions; US 92/92
  files, 1,187 sessions. These counts describe v1, which includes the two
  inverse funds. The source CSVs were not modified.
- The first attempt failed before artifacts due to a serialization path error;
  the failure is recorded in `runs/stock_common_momentum_20261120/`. An
  intermediate retry is retained but lacks the stress-cost benchmark and is
  marked incomplete. The canonical complete comparison is retry2; earlier
  attempts were not used to tune or choose candidates.
- Reproduce the canonical run:

  ```bash
  PYTHONPATH=. /opt/anaconda3/bin/python3 scripts/research/common_stock_momentum_probe.py \
    --prereg docs/research/inventory/PREREG_STOCK_COMMON_MOMENTUM_EXPLORATORY_20261120.md \
    --output-dir docs/research/inventory/runs/stock_common_momentum_20261120_retry2
  ```

  The command refuses to overwrite an existing output directory. Use a new
  run ID for any future replay; this panel has already been exposed and cannot
  become a sealed test set.
