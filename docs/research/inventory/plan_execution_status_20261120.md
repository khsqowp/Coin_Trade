# Coin_Trade research/data plan execution status

Snapshot date: 2026-11-20. This is a factual status ledger for the approved
10-phase plan. “Complete” means the phase's defined work and gate were handled;
it does not mean a profitable strategy was found.

## Phase status

| Phase | Status | Evidence / disposition |
|---|---|---|
| 0 — repository and work state | Complete | Canonical Coin_Trade root `/Users/user/CODE/Coin_Trade`, branch `main`; current metadata snapshot records 26 registered worktrees. Existing worktrees and raw data remain untouched. |
| 1 — data and artifact inventory | Complete | Metadata file manifest plus registry/worktree snapshots; market/data quality and source limitations in `data_quality_findings_20261120.md`. Latest listed snapshot is linked from `README.md`. |
| 2 — preserve/cleanup decision | Complete as a decision | No data or worktree deletion/move was performed or approved. Candidate removal is not proven safe; retain originals. |
| 3 — common evaluation rules | Complete | `comparable_evaluation_protocol_v1.md` fixes separate KR/US/crypto metrics, audited legacy base/stress assumptions, and promotion gates. These are scenario assumptions, not account-specific actual fills. |
| 4 — existing strategy mapping | Complete for available registry | Registry reconciliation and 107 append-only rows map prior studies. Historical incomparable, exposed, blocked, and non-evaluable results remain labeled; no missing result was inferred. |
| 5 — evaluation pipeline | Complete for the new comparable runners | Run-contract validator, common KR/US NAV runner, robustness runner, and tests are present. Legacy runners are not all wired to the contract; the contract's structural validity is not market-data validation. |
| 6 — comparable existing-candidate evaluation | Complete for the declared batches | Fixed USD-M 1h M2 batch: 76 cells, sealed best 38.46% (10/26), 23 non-overlap signals, zero 80% cells. KR/US v1 and inverse-excluded v2 each have 16 cells. No stock momentum variant passes the 30% MDD cap; full results are in the linked reports. |
| 7 — robustness/red-team | Complete for the fixed stock candidate family; crypto promotion not triggered | 36 stock parameter-neighborhood cells; 7 non-overlapping 6-month pseudo-OOS folds / 14 cost rows; 1,000 daily-return permutations and 1,000 20-session block-bootstrap paths for each of 12 stock cells. Independent recomputation of the 6 aggregate walk-forward cells and all 12 resampling cells matched. These are not untouched OOS or trade-level permutations. No stock cell clears the hard gates, so no candidate is promoted. |
| 8 — limited new strategy search | **Three crypto exploratory candidates rejected; cross-asset v4 is final screen, rejected before M2** | Independent read-only KR/US reviewer found no materially distinct cache-testable equity candidate. The four-source scout and four-role panel found no immediately eligible candidate; OI lead remains timing-ineligible. Prior-hour return contrarian screen: H1 M1 51.39%, gross +0.603 bp, net -9.396/-29.396 bp; H4 M1 50.50%, gross -1.119 bp, net -11.109/-31.109 bp. Cross-asset proxy uses BTC/ETH/XRP/LTC one-hour equal-weight leader return, fades it on 32 targets, H1/H4. Final v4 has 1,118,560 event rows; M1 49.87–51.62%; H1 base/stress opportunity net -8.95/-28.95 bp development, -10.18/-30.18 bp exposed validation, -9.93/-29.93 bp prior-exposed evaluation; H4 -11.38/-31.38, -9.67/-29.67, -13.03/-33.03 bp. Funding endpoint-exclusive base results are also negative (-8.96 to -13.04 bp). Coverage is 99.994–100%; market-wide non-overlap counts are 1,271–16,998, not independent events. Non-circular synchronized 7-day bootstrap intervals remain below zero. M2 was not measured. All dates were previously exposed; no core qualifies. Four-role final panel voted 4/4 to reject this fixed proxy for M2 progression, while limiting the conclusion to the proxy. A distinct asymmetric positive-shock follow-up was suggested for genuinely new forward data only; it is not registered or tested. v2's H4 block length was 28 days and lacked coverage, and v3 used circular block joins; all are preserved as superseded. Canonical artifacts: `runs/cross_asset_seesaw_screen_20261120_v4/`; frozen rule: `PREREG_CROSS_ASSET_SEESAW_SCREEN_20261120.md`.
| 9 — combination/portfolio | **Not run: prerequisite absent** | The protocol allows only individually validated core strategies into a combined portfolio. Current validated-core count is zero. Combining rejected or exposed exploratory candidates would be an invalid portfolio claim. |
| 10 — final record/backup | Complete for this continuation | Prior batch commit `7bbe07cb72dba8cbf941202b2467c58ad97d9a71` remains on `origin/main`. This continuation commit `7d97ff98371cd81bb6c9a0d7bce44a90013999a3` is present on `origin/research/bat-harmonic-validation-20261120`; `git ls-remote` matched, both signal ledgers resolve to the same uploaded LFS object, and the worktree was clean before this status-line update. Changed-scope tests: 13 pass, all 1,118,560 ledger rows, 4,212 source hashes, source-manifest digest, code digest, and `git diff --check` were verified. No Oracle deployment or orders are in scope. |

### Phase 8 continuation: OI metrics data gate

The four-source review's OI-stop-hunt lead remains unscored. A preregistered 268-file sample across the 36-symbol cohort passed checksums and structural 5-minute-grid checks; two nulls occurred in the taker-ratio field, not OI. A separate BTCUSDT 2026-11-19 archive/REST comparison matched both OI fields exactly at the same timestamp for 288 rows; the preregistered +5-minute timing screen failed. Current files for 2026-06-24/25 have start-of-day labels, conflicting with public Issue #491's earlier observations. Historical observation time and first-availability remain unresolved, so OI is still ineligible for strategy scoring. See `usdm_metrics_sample_audit_20261120.md`; no raw samples were added to Git.

## Robustness result in one view

- The 36 lookback/cadence/gate/cost cells had **0/36** meet the simultaneous
  numeric CAGR, MDD, and Sharpe thresholds; every cell exceeded MDD 30%.
- The combined pseudo-OOS US daily-top-10 path had CAGR 35.7% / MDD 33.7% /
  Sharpe 1.381 at base cost and CAGR 18.5% / MDD 36.9% / Sharpe 0.844 at
  stress cost. Its 286 closed-position records are not proven independent.
- The best-looking pseudo-OOS numbers are exposed-history diagnostics and
  cannot turn the input into an untouched test set. Raw round-trip counts do
  not override data defects or drawdown failure.
- Across the path simulations, worst-cell p95 MDD was 53.7%/60.9% under daily
  return permutation and 59.6%/70.4% under block bootstrap for KR/US,
  respectively. These resample daily portfolio returns, not individual trades.

## Remaining evidence needed to resume strategy validation

1. Point-in-time KR/US security membership including delisted/merged symbols,
   with licensed historical prices and verified corporate-action semantics.
2. For minute-scale crypto signal claims, causal minute-or-finer OHLCV and
   execution/funding inputs with source and coverage validation. The local
   exchange archive evaluated in Phase 6 is 1-hour only.
3. Account-specific fee/tax schedules and measured spread/slippage if results
   are to support an account-level execution claim.
4. A preregistered hypothesis materially distinct from the recorded strategy
   families, followed by the same comparable pipeline and untouched future
   evidence. Until then, no Core designation and no Phase 9 mix.

## Reproduction anchors

- Stock core results: `stock_common_momentum_results_20261120_v2.md`.
- Robustness preregistration: `PREREG_STOCK_MOMENTUM_ROBUSTNESS_20261120.md`.
- Canonical stock robustness run: `runs/stock_momentum_robustness_20261120_v5/`.
- Crypto M2 results: `usdm_1h_setup_m2_results_20261120.md`.
- Crypto funding-tail exploratory result: `runs/funding_tail_reversal_20261120_v3/report.md` and its event ledger; the two invalid earlier attempts are retained with explicit status markers.
- Additional source-inspired crypto screen: `runs/hourly_return_reversal_screen_20261120/report.md`; frozen H1/H4 prior-hour contrarian rule rejected after base/stress costs. It does not measure M2 and all periods were previously exposed.
- Final source inventory: see the snapshot names in this directory's `README.md`.
