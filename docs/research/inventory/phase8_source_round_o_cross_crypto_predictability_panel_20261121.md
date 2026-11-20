# Phase 8 — Round O cross-crypto return-prediction panel

Date: 2026-11-21. Scope: source/registry review and a four-role pre-score
decision. No market outcomes were inspected, no backtest was run, and no raw
archive was changed.

## Repository and data state rechecked

- Active research checkout: `/Users/user/Desktop/CODE/trading_bot`, branch
  `research/bat-harmonic-validation-20261120`, HEAD `420ef165`;
  `git status --short --branch` was clean and showed the configured remote
  tracking branch.
- Canonical checkout: `/Users/user/CODE/Coin_Trade`, branch `main`, HEAD
  `489c538`; clean at inspection. It is the common base of the active research
  branch, not a newer source of uncommitted cleanup changes.
- NAS `/Volumes/home` was mounted and the Binance archive root was present.
  This check confirmed the mount and top-level data directories only; it did
  not rerun full-archive integrity checks. The preceding correction validates
  selected 32-symbol July–September 2026 price grids only.
- Existing Claude worktrees and external research checkouts were left
  untouched. No worktree cleanup or deletion was attempted.

## Candidate and source

Guo, Sang, Tu, and Wang (2024), *Cross-cryptocurrency return predictability*,
reports minute-frequency Binance cross-coin return predictability, out-of-
sample cross-sectional long-short portfolios, and tests using adaptive LASSO
and PCA. The published sample uses a top-30 universe chosen by dollar volume
on 2020-05-09 and spans 2019-03-25 through 2021-04-30. The article describes
portfolio rebalancing at 10-minute frequency and a futures-market result.
These are source-reported findings, not locally reproduced results.

The study's target is forecast return and cross-sectional portfolio return.
It does not define per-trade target/invalidation barriers or a target-first
M2 success rule. Transforming its forecasts into M2 requires a new strategy
specification. Existing registry entries #112–113 already cover closely
related crypto lead-lag/return-spillover adaptations; #65 and #78 are adjacent
cross-sectional ranking or momentum research. The candidate is therefore not
registered as a structurally independent mechanism.

## Four-role decision

| Role | Decision | Decisive point |
|---|---|---|
| Blue | HOLD | Return-forecast portfolio can be researched, but the source has no M2 barrier contract; adding ATR or symmetric barriers creates a new adaptation. |
| Red | HOLD / NO SCORE | Barrier choices can manufacture hit-rate gains; overlapping lead-lag family, exposed history, and unverified execution/funding undermine an M2 screen. |
| Data / Methods | HOLD before scoring | Only a three-month subset's price grids were cross-validated; the universe is not proven point-in-time, funding `calc_time` availability is unresolved, and the current scorer's anchor differs from next-minute execution. |
| Judge | HOLD | No source-faithful 10–20-minute target-first M2 specification exists; do not score or call this a Core candidate. |

Panel result: **4/4 HOLD — NO SCORE — NO CORE — PHASE 9 REMAINS BLOCKED.**
No target/stop values were selected and no score was inferred from the paper.

## Gates before any test

1. Audit the full intended spot/perpetual minute archive by symbol-month:
   file identity, UTC units, expected minute grid, gaps/duplicates, and spot /
   perpetual alignment. Keep this read-only and separate from outcome fields.
2. Extract and freeze the source's exact forecasting and portfolio rules,
   including rolling estimation, adaptive-LASSO/PCA choices, training window,
   rebalancing, universe membership, and portfolio accounting. If the full
   recipe or data cannot be reproduced, label the work a new adaptation rather
   than a paper replication.
3. If the return-prediction mechanism remains worth pursuing, run one
   preregistered, development-only return-forecast falsification screen before
   designing barriers. Report forecast/rank performance and net portfolio
   returns separately; this screen cannot satisfy M2 or grant Core status.
4. Only if that screen supports a stable, positive after-cost mechanism, write
   a separate M2 hypothesis whose target, invalidation, expiry, and entry are
   justified independently of the desired 80% hit rate. Freeze next-executable
   entry, stop-first ties, time-expiry failure, 10/30 bp scenarios, funding
   treatment, baselines, signal coverage, and overlap before accessing M2
   outcomes.
5. Use genuinely future append-only signals for final promotion. Existing
   historical intervals are exposed research data, not untouched forward
   evidence. No live order placement is in scope.

## Evidence limits

The publisher and institutional research listings describe the paper's
abstract and sample, but the publisher PDF endpoint returned 403 in this
research session. No author code or complete model specification was
verified. The source paper's reported performance cannot be transferred to
the local archive, current contracts, current fee assumptions, or M2 hit rate.
The July–September 2026 NAS price-grid audit does not establish full-history
integrity, point-in-time listing membership, actual fill quality, or funding
publication semantics.

## Sources

- [Published article and methods summary](https://www.sciencedirect.com/science/article/pii/S0165188924000551)
- [Singapore Management University research record](https://ink.library.smu.edu.sg/lkcsb_research/6901/)
- [Author's publication page](https://guoli0618.github.io/publication/paper4_JEDC_crypto)
