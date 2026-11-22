# Phase 8 — four-agent candidate scout (2026-11-22)

Status: discovery and red-team review only. No new strategy passed a market
scorecard in this round. No candidate below is approved for live use.

## Goal and frozen scorecards

Find two defensible, independently validated strategies for each separate
leaderboard: Korean stocks/ETFs, US stocks/ETFs, and crypto USD-M order-block
signals. KR/US require net CAGR >=20%, MDD <=30%, annualized Sharpe >=1.0, and
at least 200 independent completed OOS round trips with point-in-time universe
and corporate-action coverage. Crypto requires sealed OOS M2 >=80%, issued and
non-overlap sample thresholds, >=20 eligible symbols, >=10% coverage, positive
net expectancy under both cost cases, and the frozen-baseline comparison.
Candidate ideas and exposed historical results do not count as validated
strategies.

## Agent assignments and findings

| Role | Finding | Decision |
|---|---|---|
| KR equities/ETFs researcher | Existing momentum, stress-day reversal, ETF rotation, and compression/breakout work is either below risk/return gates or compromised by survivor-cohort and adjustment-history gaps. No distinct candidate can be defended with the present inputs. | 0 qualifying candidates; do not tune the exposed panel. |
| US equities/ETFs researcher | Existing momentum/ETF/gap families are rejected or blocked. The 92-symbol current-survivor cache has OHLC violations, zero-volume rows, unresolved corporate actions and no PIT membership. An earnings-surprise idea cannot be reconstructed from the available OHLCV alone. | 0 qualifying candidates; no new price backtest until data eligibility is fixed. |
| Crypto order-block researcher | Proposed one new mechanism: funding-settlement-linked failed-auction recovery at an existing OB zone. It conditions on information before a settlement, then requires a zone sweep and close reclaim within a fixed five-minute window. This is materially different from merely changing OB confidence thresholds, but it is not yet preregistered or measured. | One unvalidated hypothesis; no performance claim. |
| Independent red team | Confirmed the frozen M2 gate and rejected Core promotion. Found a comparison-contract mismatch: the shared protocol requires beating the strongest valid preregistered baseline, while the Round S implementation checks only same-event momentum. Also found a run ID `v1` versus output directory `v6` mismatch. | Keep Round S rejected; reconcile contracts and identifiers before any new score run. |

## Crypto hypothesis lead — not a registered experiment

The proposed event is: on a USDT-margined perpetual with verified COIN
underlying, select the most recent still-valid opposite-candle OB created by a
completed one-minute impulse. Use only a funding rate whose availability before
settlement is proven. Positive funding selects the latest bullish OB; negative
funding selects the latest bearish OB. In the first five completed one-minute
bars after settlement, require a wick through the near zone boundary and a
close fully back beyond the far boundary. Enter at the next one-minute open;
put the stop beyond the signal-bar extreme; use a fixed 2R target and a
20-completed-bar vertical barrier. Stop-first resolves same-bar stop/target
touches; timeout, invalid entry, missing path, and no-signal settlement events
remain in the denominator/report.

This is a hypothesis about absorption/reversal, not proof of liquidation or
institutional order flow. Before any outcome scoring, a new versioned
preregistration must freeze the exact zone definition, funding availability
and payment timestamp semantics, eligible symbols, event denominator, cost
model, funding debit/credit treatment, split dates, baseline set, trial count,
and code/data hashes. Do not reuse the exposed July–October 2026 pilot or the
already-open July–September interval as OOS. The available local one-minute
database ends on 2026-11-14; this round did not verify a post-freeze forward
dataset.

Required gates remain those in `comparable_evaluation_protocol_v1.md` and
`chart_predictor/SPEC.md`. Specifically, aggregate symbol rows are not assumed
independent: report per-symbol non-overlap events and market-time block
uncertainty as well as all-signal M2, M1, Wilson interval, coverage, stop/target/
timeout rates and net expectancy after fees, slippage assumptions and observed
holding-period funding.

## Existing evidence that prevents false promotion

- Round S adaptive selective M2 historical diagnostic: M2 49.4161%, Wilson
  95% 49.2660–49.5662%; global non-overlap 12,639 at 49.3947%; coverage
  10.0575%. The 80% target and both net-expectancy gates failed. Its 2026-07 to
  2026-09 interval was already exposed and is not sealed OOS.
- The 2026-11-22 OB development pilot separately reported best M2 24.74% for
  breaker retest and 9.00% for five-minute-OB/one-minute mitigation. It was
  unregistered before scoring, included an unverified underlying universe,
  omitted funding, and used exposed data. It is a diagnostic, not validation.
- Current stock research records do not repair the missing point-in-time
  membership, delisted history, corporate actions, adjustment semantics or
  integrity issues. Reported historical returns remain triage evidence.

## Official data-source leads checked

- KRX Data Marketplace exposes separate menus for delisted-issue price and
  current all-issue daily prices. This establishes a source lead, not bulk
  historical coverage, reuse rights, export completeness or PIT index
  constituents; those remain to be confirmed before a stock run.
- CRSP states its US stock database covers more than 32,000 active and inactive
  securities and includes delisting/corporate-action information. Local access,
  license, quote and sample availability were not confirmed in this round; no
  account was created and no purchase was made.
- SEC EDGAR provides filing acceptance timestamps, useful for timestamping
  event inputs, but does not supply the missing stock-price panel or PIT
  constituent history by itself.

## Run record and next gates

- Four agents completed independent read-only market/reviewer tasks. The
  bounded crypto follow-up proposed sweep/reclaim/BOS as a possible second OB
  hypothesis; the red team rejected it as structurally overlapping P5
  `sweep_choch_retest`, P6 `fabio_liquidity_mss`, Round 10 sweep+taker-flow,
  and the existing OB zone-retest family. A second distinct crypto candidate
  did not survive the overlap screen.
- Verification run in the active checkout:
  `python3 -m pytest -q -p no:cacheprovider tests/test_adaptive_selective_m2_probe.py`
  — 23 passed, 1 environment warning about physical-core detection.
- The main-branch exploratory OB probe's focused tests were also verified in
  the canonical checkout: 3 passed. Its input candle DB remained unchanged at
  SHA-256 `cac23a3d18be66e226bdf8c3dbc0d08f5c6c185d4f18ed2a8687f08d2b6f67b1`.
- No new backtest was run in this round. The unresolved stock price/PIT gates
  and absent untouched crypto forward period are evidence constraints, not a
  reason to fabricate results. Phase 9 portfolio combination remains blocked
  until individually validated cores exist.
- Next actions: (1) obtain two independent KR/US data-eligibility proofs,
  including permitted sample coverage and price quote only; (2) fix the
  baseline comparator and run-ID versioning in a newly versioned experiment
  rather than modifying Round S history; (3) source a second non-overlapping
  OB mechanism with fixed source rules before preregistration; (4) preregister
  only surviving crypto hypotheses; (5) collect a fresh post-freeze forward
  sample before any one-time score.

## Source links

- KRX all-issue daily price: <https://data.krx.co.kr/contents/MDC/MDI/outerLoader/index.cmd?screenId=MDCSTAT015>
- KRX Data Marketplace (menu includes delisted-issue price): <https://data.krx.co.kr/>
- CRSP US Stock Databases: <https://www.crsp.org/research/crsp-us-stock-databases/>
- SEC EDGAR timestamp explanation: <https://www.sec.gov/about/webmaster-frequently-asked-questions>
