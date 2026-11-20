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
| 4 — existing strategy mapping | Complete for available registry | Registry reconciliation and 105 append-only rows map prior studies. Historical incomparable, exposed, blocked, and non-evaluable results remain labeled; no missing result was inferred. |
| 5 — evaluation pipeline | Complete for the new comparable runners | Run-contract validator, common KR/US NAV runner, robustness runner, and tests are present. Legacy runners are not all wired to the contract; the contract's structural validity is not market-data validation. |
| 6 — comparable existing-candidate evaluation | Complete for the declared batches | Fixed USD-M 1h M2 batch: 76 cells, sealed best 38.46% (10/26), 23 non-overlap signals, zero 80% cells. KR/US v1 and inverse-excluded v2 each have 16 cells. No stock momentum variant passes the 30% MDD cap; full results are in the linked reports. |
| 7 — robustness/red-team | Complete for the fixed stock candidate family; crypto promotion not triggered | 36 stock parameter-neighborhood cells; 7 non-overlapping 6-month pseudo-OOS folds / 14 cost rows; 1,000 daily-return permutations and 1,000 20-session block-bootstrap paths for each of 12 stock cells. Independent recomputation of the 6 aggregate walk-forward cells and all 12 resampling cells matched. These are not untouched OOS or trade-level permutations. No stock cell clears the hard gates, so no candidate is promoted. |
| 8 — limited new strategy search | **One preregistered crypto exploratory candidate tested; REJECT** | Independent read-only KR/US reviewer found no materially distinct cache-testable equity candidate. Crypto reviewer proposed one funding-tail mean-reversion hypothesis. The first two executions used Wilder ATR instead of the preregistered simple 14-bar mean true range; both are retained and explicitly invalidated. The corrected third execution is the primary result on the same audited 36-symbol hourly archive. Validation plus previously exposed sealed range: M2 25.04% (1,809/7,225; Wilson 24.05–26.05%), symbol non-overlap N=5,060, market-time non-overlap N=695, coverage 14.26%, M1 50.98%; mean net return +0.0058% base and -0.1942% stress per unit notional. Same-event controls: always-long 25.04%, always-short 23.31%. It fails M2>=80% and positive stress expectancy; no robustness promotion. Both validation and sealed dates were previously exposed, so this is exploratory, not untouched OOS. Primary run: `runs/funding_tail_reversal_20261120_v3/`; invalid prior attempts are retained with status markers. |
| 9 — combination/portfolio | **Not run: prerequisite absent** | The protocol allows only individually validated core strategies into a combined portfolio. Current validated-core count is zero. Combining rejected or exposed exploratory candidates would be an invalid portfolio claim. |
| 10 — final record/backup | Local verification complete; commit/push pending | Changed-scope verification: 14 tests pass, ledger independently reproduces M2, run contract passes, all 105 registry doc references resolve, and `git diff --check` passes. Repository-wide pytest collection is blocked by archived duplicate test module names/missing historical files and 7 active tests importing `pandas_ta` from a non-writable nested venv, where Numba cache locator setup fails; no unrelated test/source files were changed to bypass this. Commit, push, and remote-SHA parity remain. No Oracle deployment or orders are in scope. |

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
- Final source inventory: see the snapshot names in this directory's `README.md`.
