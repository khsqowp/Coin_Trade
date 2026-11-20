# Preregistration v2: inverse-ETF-excluded KR/US replay

Frozen: 2026-11-20, before scoring this cohort. This is a universe-boundary
correction to the fixed exploratory comparison, not a sealed or independent
OOS experiment. The price histories have already been inspected in earlier
research and in the retained 92-file v1 run.

## Why v2 exists

The main stock/ETF cohort excludes leveraged and inverse ETFs. The original
92-file local cache includes at least KODEX Inverse (`114800`) and ProShares
Short S&P500 (`SH`), both inverse products confirmed by their issuers:
[Samsung Asset Management KODEX Inverse factsheet](https://www.samsungfund.com/sheet/20261002/2ETF20_20260930.pdf),
[ProShares SH product page](https://www.proshares.com/our-etfs/leveraged-and-inverse/sh).
The v1 replay included these two files; it is preserved as a broader-cache
exploratory sensitivity and is not deleted or relabeled retroactively.

## Frozen cohort and rules

- Exclude only `KR:114800` and `US:SH`; retain all other 91 files per market.
  Do not select or remove any other symbol after seeing results. If a later
  instrument-classification audit identifies another inverse/leveraged product,
  report this run as a boundary-limited sensitivity and preregister a new version
  before rerunning.
- The resulting positive-volume, valid-OHLC common panels are expected to be
  KR 832 sessions (2023-01-05–2026-08-06) and US 1,187 sessions
  (2021-07-29–2026-11-12); the runner must assert these counts and endpoints.
- Strategy, timing, cost assumptions, baseline, accounting, metric formulas,
  candidates, and thresholds are identical to v1:
  [`PREREG_STOCK_COMMON_MOMENTUM_EXPLORATORY_20261120.md`](PREREG_STOCK_COMMON_MOMENTUM_EXPLORATORY_20261120.md).
- KR: 60-session monthly top-10 momentum with/without the 069500 SMA200 cash
  gate. US: 126-session daily and monthly top-10 momentum with/without the SPY
  SMA200 cash gate. Run base and stress costs for every candidate and equal-
  weight buy-and-hold comparator.
- No parameter tuning, no best-cell selection, no strategy mix, and no OOS or
  validation claim. The entire price source is known to be exposed.

## Disposition rule

This run can only describe the impact of removing the two confirmed inverse
funds from the already-exposed current-survivor cache. All CAGR/MDD/Sharpe and
round-trip outputs remain exploratory. The stock pass thresholds remain CAGR
≥20%, MDD ≤30%, Sharpe ≥1.0, and at least 200 independent OOS completed round
trips; v2 cannot satisfy the independent OOS requirement by construction.

## Reproduction

```bash
PYTHONPATH=. /opt/anaconda3/bin/python3 scripts/research/common_stock_momentum_probe.py \
  --prereg docs/research/inventory/PREREG_STOCK_COMMON_MOMENTUM_EXPLORATORY_20261120_v2.md \
  --output-dir docs/research/inventory/runs/stock_common_momentum_20261120_inverse_excluded \
  --exclude-inverse
```

The runner refuses to overwrite an existing output directory. It stores hashes
for included CSV inputs only; the manifest separately records excluded tickers.
