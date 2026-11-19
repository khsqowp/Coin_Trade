# KODEX 200 volatility-target development result — 2026-11-20

## Decision: REJECT

The fixed 20-session, 10% annualized-volatility target reduced the observed drawdown versus KODEX 200 buy-and-hold, but failed the wealth objective by a wide margin: its after-cost terminal NAV was 1.174 versus 1.773 for buy-and-hold. CAGR was 1.14% versus 4.14%, and Sharpe was 0.16 versus 0.33. The drawdown reduction from 38.07% to 29.32% did not compensate for the lost compounded wealth. No neighbor from the preregistered sensitivity matrix approaches the frozen 20% CAGR / Sharpe 1.0 gates.

## Frozen test and input boundary

- Preregistration: [`prereg_kr_kodex200_vol_target_20261120.md`](../prereg_kr_kodex200_vol_target_20261120.md).
- One instrument: KODEX 200 (`069500`). Monthly signal uses the last 20 close-to-close returns; weight is `min(1, 10% / annualized volatility)`; execution is the next observed session's open; remaining capital earns 0%.
- Development data: 3,513 rows, 2010-08-09 through 2024-11-11 UTC. The loader stopped at the exclusive 2024-11-12 boundary without parsing the later row's OHLCV. No post-cutoff performance data was used.
- Base and stress one-way costs: 0.115% and 0.165%. Costs were charged on absolute exposure changes and terminal liquidation.
- Input-prefix SHA-256: `7def9b2b254cca359c4d43b2d218a6572060b5449410ec1d21a4eacf6e48d503`.
- Runner SHA-256: `d3aa408ff557c47f1be84a1bb436ebaff29310f5a558d4c05c4a4a88bcb4bd84`.
- Unit checks: 4 passed before the single data run, covering volatility sizing, entry/exit cost accounting and NAV reconciliation, the closed cutoff, and duplicate timestamps.

## Net results

| Portfolio | Cost | Terminal NAV | CAGR | MDD | Sharpe | Average exposure |
|---|---:|---:|---:|---:|---:|---:|
| Vol target 20d / 10% | Base | 1.174 | 1.14% | 29.32% | 0.161 | 71.65% |
| Vol target 20d / 10% | Stress | 1.158 | 1.04% | 29.48% | 0.152 | 71.65% |
| KODEX 200 buy-and-hold | Base | 1.773 | 4.14% | 38.07% | 0.328 | 100% |
| KODEX 200 buy-and-hold | Stress | 1.771 | 4.13% | 38.07% | 0.328 | 100% |
| Zero-yield cash | — | 1.000 | 0.00% | 0.00% | 0.000 | 0% |

The strategy recorded 161 exposure-change events over the entire development period; this is not 161 independent completed OOS trades. It cannot satisfy the OOS minimum of 200 completed trades, and the later holdout was not tested.

## Regimes and robustness

The base case returned −0.56% CAGR in 2010–2014, +2.57% in 2015–2019, and +1.19% in 2020–2024 through the cutoff. Calendar-year returns included −17.87% in 2018 and −17.54% in 2022. This is not consistent positive compounding across the observed regimes.

Across the fixed 3×3 sensitivity matrix (lookbacks 16/20/24; targets 8%/10%/12%), base CAGR ranged from 1.03% to 2.03%. The largest CAGR cell, 16 sessions / 12%, had 31.60% MDD and was not selected; it still failed both CAGR and MDD gates. At the frozen primary setting, the 1,000-path paired 20-session bootstrap printed p95 MDD of 55.96% base / 56.25% stress. Only 5.9% / 5.3% of paired paths beat cost-matched KODEX buy-and-hold; the 95% interval for log-wealth difference included zero in both cases. **Post-run code review found that the single terminal liquidation cost is embedded in the final daily return before block resampling; resampled paths can therefore omit or repeat this one-time fee. Treat these bootstrap figures as invalid diagnostics, not evidence for acceptance.** The rejection is based on the directly calculated base/stress returns versus the benchmark and frozen equity gates, not on the bootstrap.

## Limitations

This is a single-ETF, historical development result, not validation of all Korean equities/ETFs. The KIS cache's exact request parameters, adjustment of each OHLC field, dividend/corporate-action treatment, and data-use rights for derived work remain unverified. Cash was assigned zero return. Taxes, tracking error, market impact, and intraday execution were not modeled. Prior related studies have inspected this market window, so this is not untouched OOS. The original cache was read-only and was not copied into Git.

## Reproducibility

The code and compact aggregate output are [`scripts/research/kr_kodex200_vol_target.py`](../../../scripts/research/kr_kodex200_vol_target.py) and [`kr_kodex200_vol_target_20261120_dev.json`](kr_kodex200_vol_target_20261120_dev.json). The single preregistered run was completed once; no parameter was changed and no rerun was made after observing the result.
