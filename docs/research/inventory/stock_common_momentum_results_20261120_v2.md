# KR/US common-panel momentum replay — inverse-excluded v2, exploratory only

Run date: 2026-11-20. This v2 is a universe-boundary sensitivity on an already
exposed current-survivor cache. It is not independent OOS evidence and cannot
be promoted.

## Frozen change and input

- Preregistration: [`PREREG_STOCK_COMMON_MOMENTUM_EXPLORATORY_20261120_v2.md`](PREREG_STOCK_COMMON_MOMENTUM_EXPLORATORY_20261120_v2.md)
- Canonical run: [`runs/stock_common_momentum_20261120_inverse_excluded/`](runs/stock_common_momentum_20261120_inverse_excluded/)
- Excluded only the issuer-confirmed inverse ETFs KR `114800` and US `SH`; 91
  cache symbols remain in each market. All strategy rules, costs, comparison
  baselines, and execution assumptions are fixed from v1.
- KR common panel: 832 sessions, 2023-01-05–2026-08-06. US common panel: 1,187
  sessions, 2021-07-29–2026-11-12. Current constituents and adjusted-price
  provenance remain unresolved.
- The official product references are linked in the preregistration: Samsung
  Asset Management's KODEX Inverse factsheet and ProShares' SH product page.

## Results

Metrics are full-period historical CAGR / MDD / annualized Sharpe. Round trips
are closed positions over the exposed period, not independent OOS trades.

| Market | Fixed rule | Cost | CAGR | MDD | Sharpe | Round trips |
|---|---|---|---:|---:|---:|---:|
| KR | 60-session monthly top-10 | Base | 67.14% | 46.95% | 1.449 | 182 |
| KR | 60-session monthly top-10 | Stress | 66.19% | 46.96% | 1.435 | 182 |
| KR | Same + SMA200 cash gate | Base | 33.84% | 46.95% | 0.972 | 123 |
| KR | Same + SMA200 cash gate | Stress | 33.33% | 46.96% | 0.961 | 123 |
| KR | Equal-weight buy-and-hold | Base | 41.35% | 35.76% | 1.287 | 91 |
| KR | Equal-weight buy-and-hold | Stress | 41.31% | 35.76% | 1.286 | 91 |
| US | 126-session daily top-10 | Base | 31.03% | 33.74% | 1.044 | 842 |
| US | 126-session daily top-10 | Stress | 11.05% | 38.23% | 0.511 | 842 |
| US | Same + SMA200 cash gate | Base | 19.53% | 33.74% | 0.829 | 641 |
| US | Same + SMA200 cash gate | Stress | 5.39% | 38.23% | 0.350 | 641 |
| US | 126-session monthly top-10 | Base | 33.23% | 42.56% | 1.063 | 187 |
| US | 126-session monthly top-10 | Stress | 28.60% | 43.63% | 0.954 | 187 |
| US | Same + SMA200 cash gate | Base | 18.72% | 42.56% | 0.777 | 145 |
| US | Same + SMA200 cash gate | Stress | 15.52% | 43.63% | 0.678 | 145 |
| US | Equal-weight buy-and-hold | Base | 18.53% | 23.00% | 0.898 | 91 |
| US | Equal-weight buy-and-hold | Stress | 18.32% | 23.00% | 0.890 | 91 |

## Disposition

**No candidate passes.** Every momentum variant exceeds the 30% MDD cap in
both cost scenarios. The US monthly candidates also have fewer than 200
full-period round trips, before requiring independent OOS observations. The
KR equal-weight benchmark also exceeds the drawdown cap. High CAGR does not
override these failures. No robustness promotion run is warranted for this
candidate family.

The difference between v1 and v2 is only the two excluded inverse ETFs and the
resulting common cohort fingerprint. Both versions use exposed data and
current survivors, so neither supports validated historical performance.

## Reproduction and audit

- Summary: 16 candidate/benchmark and base/stress cells; the input fingerprint
  is `ca7c95576d94a52560a74334a6e9c0658c3692e6c54c1d4085d8ebb89a756ca3`.
- Independent audit recomputed each cell's CAGR, MDD, and Sharpe from daily
  NAV; all matched within `1e-10`. Per-cell round trips matched the ledger and
  no rebalance left negative cash.
- Reproduce with the exact command in the v2 preregistration. The runner
  refuses to overwrite an existing run directory.
