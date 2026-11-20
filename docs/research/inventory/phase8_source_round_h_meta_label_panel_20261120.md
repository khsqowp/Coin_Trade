# Phase 8 Round H — four-source rescan and meta-label panel

Date: 2026-11-20. Scope: identify strategies not yet represented in the
Coin_Trade registry, assess a distinct method-inspired candidate, and decide
whether it may be preregistered or scored. No source comments/posts, code
downloads, data downloads, file changes outside this research worktree, or
backtests were performed during scouting and panel review.

## Workspace and source-change check

- The active research checkout is `/Users/user/Desktop/CODE/trading_bot`,
  branch `research/bat-harmonic-validation-20261120`, HEAD `76f1858` before
  this record; it was clean and matched its configured remote branch.
- Canonical `/Users/user/CODE/Coin_Trade` was clean at `489c538` (`main`,
  `origin/main`). That commit changes one line in
  `plan_execution_status_20261120.md`; it records the already-pushed
  `7bbe07c` backup state. It does not contain the later Phase 8 research
  commits from this separate research branch. No attempt was made to merge,
  move, or overwrite either checkout.
- The one-line canonical update confirms backup status; it does not change the
  latest source-scout findings or strategy data. Existing distinct branch
  history and artifacts are preserved.

## Four-source scout result

| Lane | Closest checked material | Admissibility result |
|---|---|---|
| SNS / public creator material | Reddit CCI/ATR and futures-bot posts. [CCI/ATR post](https://www.reddit.com/r/algotrading/comments/1kg4f00/does_this_look_like_a_good_strategy_part_2/) | No candidate: exact entry parameters and/or exit/expiry rules are missing; self-reported backtests are not independent evidence. |
| TradingView / custom indicators | [Market Regime Engine](https://www.tradingview.com/script/MIEZDvM9-Market-Regime-Engine/); [Crypto Money Flow Tracker](https://www.tradingview.com/script/npr5WIMA-Crypto-Money-Flow-Tracker/) | Indicators/alerts, not complete strategies. No fixed direction, TP, SL and expiry combination; the regime idea overlaps registry #109. “Non-repainting” claims were not treated as code verification. |
| Public communities | [Binance futures trend-following report](https://www.reddit.com/r/algotrading/comments/1vbbolu/would_you_give_this_a_paper_run_trend_following/); [large strategy-search report](https://www.reddit.com/r/Daytrading/comments/1xx3xkr/i_backtested_400000_crypto_strategies_on_6_years/) | No candidate: exact signal/exit rules are absent or self-reported; concrete examples were negative, neutral, or overlap existing trend, sweep and VWAP families. |
| GitHub / skills / papers | [FlintStrats](https://github.com/sohan-shingade/flintstrats) at `b02ac45`; [mlfinlab](https://github.com/hudson-and-thames/mlfinlab); [EdgeProof](https://github.com/intikhab49/edgeproof-crypto-trading-backtest) | FlintStrats has regime/mean-reversion exit logic but no fixed target-first barrier and overlaps tested families; license was not found. mlfinlab is a method library, not a strategy, and the checked repository states all-rights-reserved. EdgeProof is a validation harness, not a new entry mechanism; its README self-reports mostly null results on limited samples. No eligible source-complete strategy. |

**Source-complete, non-duplicate candidates: 0.** Search scope is bounded to
the public materials examined; it is not a claim that all public strategies
were exhausted.

## Candidate for debate: CUSUM event clock + triple barrier + meta-label filter

The candidate was considered because it differs in event sampling and
selective acceptance from the registry’s direct fixed-timeframe signal rules.
The methodological inspiration is a 2025 study comparing information-driven
bars and triple-barrier labels on BTC/ETH data, and a separate meta-labeling
framework. These sources do **not** define the proposed direction classifier,
meta threshold, or a ready-to-run Coin_Trade strategy. [Springer paper](https://link.springer.com/article/10.1186/s40854-025-00866-w),
[meta-labeling framework](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4032018).

The 1m Vision database has OHLCV fields, including taker-buy aggregates, but
the reviewed local history is six symbols through 2026-06-30 and already
exposed to prior research. The 1m DB does not establish 1m mark-price or
funding availability. The 36-symbol USD-M archive is hourly and cannot replace
the missing minute-level execution/barrier sequence. Therefore the existing
1m data cannot qualify as sealed OOS or satisfy the Core universe gate.

### Four-role deliberation

| Role | Position | Main reason |
|---|---|---|
| Blue | HOLD for scoring; permit only a later preregistration draft | The candidate is a new adaptation, not a paper replication. Direction rule, barriers and model remain design choices. |
| Red | HOLD | The proposal is a pipeline, not a fixed alpha rule. Event-overlap leakage, threshold/multiple testing, same-minute TP/SL ordering, coverage inflation and exposed-history reuse can invalidate any result. |
| Data/Methods | HOLD | Six exposed 1m OHLCV symbols do not provide independent OOS, 20-symbol breadth, 1m mark/funding proof or reliable intrabar ordering. |
| Judge | HOLD / NO SCORE / NO PROMOTION | No source-complete fixed M2 candidate and no eligible Core dataset. |

In round two, all four reviewers maintained HOLD. The only difference was
scope: Blue permits a future implementation-only pipeline diagnostic on
exposed six-symbol data; Red, Data/Methods and Judge reject scoring there.
Consensus: no performance backtest now, no Core claim, and no Phase 9 mix.
Triple-barrier labeling itself is already part of the project’s evaluation
contract and is not a novel alpha strategy.

## Ordered continuation and entry gates

1. **Research complete rules, not more marketing claims.** Keep the four
   source lanes independent. Admit a lead only when original code or paper
   defines exact signal timing, direction, entry, TP, SL, maximum holding time,
   required data, and source/license. Registry deduplication precedes any test.
2. **Draft—not score—the CUSUM/meta-label adaptation.** If retained, label it
   explicitly as a new hypothesis. Freeze the CUSUM input/threshold/reset,
   primary direction rule, feature cut-off, triple-barrier distances and
   expiry, next executable entry, tie handling, secondary-model training and
   threshold, full eligible-time coverage denominator, baseline, fees,
   slippage, funding, and trial count.
3. **Red-team the preregistration.** Require event-interval purging and
   embargo at least as long as the maximum label horizon plus feature lookback;
   use only chronological out-of-fold primary predictions to train the
   secondary model. Compare against a random filter with equal acceptance rate
   so reduced turnover is not confused with predictive skill.
4. **Audit a genuinely eligible dataset before execution.** Require at least
   20 point-in-time eligible symbols with complete causal inputs, mark/funding
   alignment and execution resolution adequate for the chosen horizon. The
   current six-symbol exposed 1m cache fails this gate. Do not open an existing
   sealed range; any historical use of it is exploratory only.
5. **Only then run one frozen exploratory study.** Record every attempted
   specification, use no outcome-driven edits, report target-first M2 and
   direction-at-expiry separately, full-issued and non-overlap samples,
   coverage, costs, benchmark, uncertainty, and all failures. A pipeline
   diagnostic on exposed data must not be presented as strategy evidence.
6. **Core gate and Phase 9.** Require M2 ≥80%, full issued M2 plus separate
   non-overlap OOS N≥200 across ≥20 symbols, coverage ≥10%, positive expectancy
   after base/stress costs and funding, frozen-baseline superiority, robustness
   and independent red-team checks, followed by prospective unseen evidence.
   Until every gate passes, Core count stays zero and Phase 9 remains blocked.

## Disposition

Round H did not produce a core strategy and generated no performance score.
This is a research-screen decision, not evidence that the proposed family is
unprofitable. The immediate research order is (1) source-complete candidate
discovery, (2) strategy-vs-method classification and deduplication, (3) data
eligibility, (4) frozen preregistration, (5) adversarial review, and only then
(6) scoring. Current user-approved M2/Core thresholds are unchanged.
