# Strategy research goal and execution gates — 2026-11-22

Status: active research objective. This document does not promote a strategy,
authorize live orders, or make exploratory stock data valid OOS evidence.

## Target

Research two independently supported candidates in each leaderboard: KR stocks
and ETFs, US stocks and ETFs, and crypto USD-M order-block setups. A candidate
counts toward the target only after the market-specific frozen gates pass.
Candidate ideas, positive development results, and a high-return best cell do
not count as a qualifying strategy.

Hard scorecards remain those in
[`comparable_evaluation_protocol_v1.md`](comparable_evaluation_protocol_v1.md):
stocks require net CAGR >=20%, MDD <=30%, Sharpe >=1.0, and >=200 independent
completed OOS round trips, with a point-in-time universe and corporate-action
history. Crypto requires sealed OOS M2 >=80%, Wilson lower bound above the
frozen baseline, non-overlap OOS N >=200, >=20 symbols, coverage >=10%, and
positive net expectancy under both cost scenarios. M1 is reported separately.

## Starting evidence and constraints

- The 2026-11-20 USD-M 1h replay evaluated 38 setups at H=10/20 (76 cells).
  No cell reached 80% sealed M2; the best was 10/26 (38.46%), with 23
  non-overlap events and 1.43% coverage. Its sealed interval is exposed and
  cannot be used to choose or tune new candidates.
- Existing order-block families include `order_block`,
  `order_block_engulfing_confirm`, and aggressive/balanced/conservative
  confluence variants. Their prior runs were rejected. New hypotheses must
  alter the event mechanism, not just retune confidence thresholds.
- Coin research is only conditionally eligible on the audited 36-symbol,
  2023-03–2026-05 hourly archive cohort. This proves alignment for that cohort,
  not execution realism, point-in-time listing coverage, or price truth.
- KR/US local 92-symbol caches are current-survivor cohorts. KR has 457
  zero-volume rows and unresolved adjustment provenance. US has 62 OHLC bound
  violations and 123 zero-volume rows. Neither cache supports validated OOS
  promotion. Existing prices and evaluation periods have already been exposed.
- Repository index and registry snapshots are stale relative to one another;
  use the append-only `registry.jsonl` and source run artifacts, not the INDEX
  header's row count, as the current experiment source.

## Candidate hypotheses

### Crypto OB-1: breaker retest

Hypothesis: after a mechanically defined order-block zone is invalidated by a
confirmed close through its far boundary, its first retest from the opposite
side may act as support/resistance in the break direction.

Provisional event rule: form a zone from the last opposite-color candle among
the preceding five completed bars when the impulse body exceeds 1.5 x prior
ATR(14) and breaks the prior bar extreme. Within 60 bars, a close through the
far zone boundary changes the zone to breaker state. Emit once on the first
retest and directional recovery close. Expire after 60 bars or opposing
invalidation. Entry is next bar open; stop is the opposing zone boundary plus
the existing fixed ATR buffer; target is 2R; horizon H=10 and H=20 bars. These
exact stop/buffer semantics must be frozen after checking existing scorer
contracts and before any run.

### Crypto OB-2: higher-timeframe zone, first lower-timeframe mitigation

Hypothesis: the first lower-timeframe mitigation of a zone formed on a fully
closed higher-timeframe order block, followed by a directional close back out
of the zone, has better target-first outcomes than same-timeframe OB retests.

Provisional event rule: create the higher-timeframe zone with the same frozen
impulse and opposite-candle definition as OB-1. Use only fully closed higher
timeframe bars. Emit only at the first lower-timeframe touch and recovery close;
one signal per zone. Expire at 60 higher-timeframe bars or opposing close
invalidation. The exact HTF/LTF pair must be selected from data availability
before outcome inspection. Do not grid-search timeframes.

## Preregistration and split rule

1. Treat previously viewed 2023-03–2026-05 data as exposed exploratory data.
   Use its development interval only to debug causal implementation and reject
   hypotheses; do not call any result OOS or sealed.
2. Freeze candidate code, symbol cohort, exact split timestamps, cost model,
   entry/stop/target/expiry ordering, run IDs, and hashes before scoring.
3. A truly untouched final evaluation requires forward-collected data after
   the freeze date, or another independently sourced interval whose outcomes
   have not been inspected. Until then, the final crypto promotion gate is
   unavailable; never reuse the exposed sealed interval.
4. Apply existing 10/30 bp round-trip fee scenarios plus timestamp-validated
   funding. Report separate 2 bp/side base and 5 bp/side stress slippage
   sensitivity as assumptions, not measured fills. If costs cannot be
   reconciled, label the run exploratory.
5. Preserve every signal, including invalid entries, stop-first same-bar
   conflicts, timeout failures, overlapping signals, and no-signal intervals.
   Report all-signal M2, per-symbol and market-time non-overlap M2, Wilson
   interval, M1, coverage, net expectancy, and symbol/regime breakdowns.
6. Before any next variant, write a failure memo covering: signal availability,
   target/stop/time-out mix, gap/invalid-entry rates, cost sensitivity,
   baseline comparison, symbol concentration, regime dependence, and causal
   test results. One bounded change is allowed only when the memo states a
   falsifiable mechanism and a preregistered expected direction.

## Stock data gate

Do not run or promote historical KR/US return backtests on the current survivor
cache as validated strategy evidence. First require (a) PIT membership including
delisted/merged instruments, (b) licensed historical price/actions with
documented adjustment semantics, (c) symbol/date completeness and zero-volume
disposition, and (d) an untouched chronological OOS span. Until these exist,
the two conditional hypotheses per stock market remain blocked. Plausible
event-study ideas (large-holder ownership filings and actual treasury-share
purchase progress in KR; point-in-time earnings-surprise drift in US) are data
requirements, not measured strategy candidates. No data purchase or account
creation is authorized by this document.

## Mandatory per-run failure gate

Every run writes a preregistration, run envelope, full event/trade ledger,
summary, and failure-analysis report. If execution fails, preserve its log and
classify the cause (data, implementation, resource, or hypothesis); do not
silently rerun under the same ID. If performance fails, record the leading
failure mechanism and the next falsifiable test. If a data gate fails, mark
`BLOCKED`/`NOT_EVALUABLE`; do not substitute a synthetic performance number.

## Current state and next actions

- Four delegated roles completed read-only triage: KR, US, crypto OB, and
  independent red team. Reports are in the active Codex task history; they
  have not been copied into repository artifacts yet.
- The 1m local candle DB was opened read-only and has 17,142,161 rows across
  100 symbols from 2026-07-17 through 2026-11-14. It is already exposed
  development history; not an OOS source. The documented 1h archive path was
  absent during this run.
- A development-only diagnostic was run over all 100 stored symbols, four
  hypothesis/horizon cells, 136,064 event rows. The run was not preregistered
  before execution, omitted funding, and did not filter exchange underlying
  types; therefore it is only a preserved pilot and cannot pass any gate.
  Full results and failure analysis are in
  [`runs/order_block_novel_dev_20261122/report.md`](runs/order_block_novel_dev_20261122/report.md).
- The exact breaker-retest and HTF-first-mitigation implementations performed
  poorly in that diagnostic (best M2 24.74% and 9.00% respectively) and had
  negative fee/slippage-proxy mean outcomes. Do not tune these rules on the
  same exposed period. A new mechanism needs a new preregistration and an
  untouched forward cohort.
- Synthetic tests for prefix invariance, future mutation, and signal-index
  mapping pass. The data DB was not changed. The diagnostic's large event
  ledger and JSON summary remain in `/private/tmp/ob-dev-full-20261122/` and
  must be retained in an approved research-data location before cleanup.
- Next: preserve the full run outputs outside Git, reconcile symbol
  underlying types and funding coverage for any future crypto test, secure a
  truly untouched forward window, and resolve stock PIT/action-history data
  gates. Until then the three market targets are not achieved.
- Do not commit this planning artifact by itself as evidence of research
  success. Once implementation and tests are complete, review all scoped
  changes, commit locally, push to `origin`, and verify the remote commit SHA.
