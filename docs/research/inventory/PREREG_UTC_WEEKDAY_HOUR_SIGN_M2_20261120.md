# Preregistration — UTC weekday-hour sign persistence, USD-M 1h

Status: **approved for one exploratory evaluation after pre-score data gates**.
Approved by the four-role panel on 2026-11-20. This is not Core approval. Do
not score outcomes until the full input audit and development baseline are
recorded. No parameter variants or post-result changes are allowed.

## Question and mechanism

Does a contract's prior same-UTC-weekday-and-hour return-sign majority predict
the direction and target-first path of its next occurrence? The hypothesized
mechanism is recurring time-conditioned order flow. Published findings support
testing periodic volatility/liquidity and report mixed, localized evidence for
return predictability; they do not establish a tradeable edge.

This candidate is structurally distinct from P8-B funding-session range
breakout, funding-tail contrarian, chart patterns, and prior-hour return
reversal. It remains related to prior UTC-hour features; the full family history
must remain disclosed.

## Fixed market, universe, periods, and inputs

- Market: Binance USD-M USDT linear perpetuals; UTC timestamps; 1-hour bars.
- Fixed symbol cohort: the 36 symbols under
  `2023-03..2026-05` in
  `docs/research/inventory/usdm_archive_coverage_20261120.json`, minus
  `IMXUSDT` for the whole candidate run. This exclusion is data-QA based and
  fixed before scoring; do not replace the symbol based on outcomes.
- Required monthly inputs: `klines_1h`, `mark_price_1h`, and `funding` from
  2024-06 through 2026-09. The historical archive root is supplied at run time;
  do not copy or modify source archives.
- Development interval for the frozen baseline: 2025-06-01 00:00 UTC through
  2026-06-01 00:00 UTC, half-open.
- Exploratory score interval: 2026-06-01 00:00 UTC through 2026-10-01 00:00
  UTC, half-open. This interval is a chronological extension but raw data were
  previously downloaded and audited. It is **not sealed or live-forward OOS**.
- A signal requires the full 52 previous occurrences of that exact UTC
  weekday-hour. Every training bar must be complete and valid; otherwise
  abstain. Do not impute a missing return.
- The monthly mark-price files omit 2026-06-29 for the selected cohort. Rebuild
  mark coverage in memory by overlaying the exact 24 hourly rows from each
  matching daily recovery ZIP; require recovery manifest SHA match and exact
  one-to-one timestamp coverage. Never edit or replace raw ZIP files.
- Exclude all IMXUSDT observations, including its 2026-06 funding-interval
  mismatch, rather than inferring or repairing funding intervals.

## Signal, entry, and exit rules

1. At each current UTC hourly bar open, identify its weekday-hour slot.
2. Read only the 52 immediately preceding completed occurrences of the same
   slot. For each, calculate `close / open - 1`. Count positive and negative
   returns; zero returns are neutral. If positives exceed negatives, issue
   `long`; if negatives exceed positives, issue `short`; otherwise abstain.
3. Enter at the current bar's open. No current-bar close, high, low, or volume
   may affect the signal or entry decision.
4. Calculate true range for each completed bar as
   `max(high-low, abs(high-prev_close), abs(low-prev_close))`. Risk distance is
   the arithmetic mean of the latest 14 completed true ranges, through the bar
   immediately before entry. If any of these 14 bars is missing/invalid or ATR
   is non-positive, abstain.
5. For a long, stop is entry minus 1 ATR and target entry plus 1 ATR. For a
   short, stop is entry plus 1 ATR and target entry minus 1 ATR.
6. Scan contract-price OHLC of the entry bar and next three bars in time order.
   Stop is checked before target on every bar. If both boundaries are touched
   inside one bar, classify as stop. A stop gap fills at the adverse bar open;
   a target gap is credited at the target price. If neither barrier is touched,
   exit at the fourth bar close and score M2 as failure.
7. Only one open position per symbol is allowed. While one is open, suppress
   all new signals for that symbol; the next eligible entry is the bar after
   the recorded exit bar. Report raw directional forecasts separately from
   accepted strategy entries. The strategy's issued M2 events are
   non-overlapping per symbol by construction.
8. A missing/incomplete bar inside a signal's four-bar outcome path invalidates
   that event as a data-quality failure; do not fill or skip the gap.

## M2, M1, costs, and controls

- M2 is target touch before stop within four hourly bars. Timeout, stop,
  invalid ATR, invalid entry, and incomplete outcome paths are not M2 hits;
  disclose data-invalid events separately and do not silently remove an issued
  event.
- M1 is the direction of the entry bar close versus entry open and is reported
  separately from M2.
- Fee scenarios: legacy base 10 bp and stress 30 bp round-trip. These are
  account-independent fee proxies, not measured user fees. Subtract signed
  funding events with timestamp strictly after entry through the recorded exit
  bar close. If an intrabar exit precedes a same-bar funding timestamp, hourly
  OHLC cannot resolve the ordering; conservatively include only funding that
  is a cost to the position and omit same-bar funding credits. Record this
  ambiguity. No spread/slippage is measured, so no result can establish
  executable net profitability or qualify as Core.
- For every candidate entry timestamp, score always-long and always-short
  controls with the same ATR distance, barriers, horizon, path ordering, costs,
  and funding. On development data only, freeze whichever direction has the
  higher all-event M2 rate; exact tie selects always-long. Do not change that
  baseline after observing the score interval.
- Report overall and per-symbol M2, Wilson 95% interval, M1, signal and
  opportunity counts, coverage, symbols, active-position suppressions, all
  exit reasons, gross and net outcome, fees, funding, market-time concentration,
  and synchronized UTC-week block-bootstrap uncertainty. Do not interpret
  simultaneous altcoin signals as independent trials.

## Hard criteria and non-promotion rules

The exploratory score is assessed against the existing crypto gate without
relaxation: M2 point estimate at least 80%, at least 200 non-overlap events,
at least 20 symbols, coverage at least 10%, positive net expectancy in both
fee scenarios after funding, and the 95% Wilson lower bound above the
development-frozen baseline. Report M1 separately. A short sample, insufficient
coverage, data-integrity failure, or cost failure is not a pass.

Even if all numeric criteria pass, this run cannot be labeled a validated Core
or tradable strategy because the interval was source-audited but not kept
sealed, spread/slippage are unmeasured, the selected universe has unresolved
survivorship, and candidate-family multiplicity remains. Further consideration
requires independent ledger/code review, eligible execution-cost evidence, a
point-in-time universe, and one genuinely untouched future evaluation.

## Required pre-score validation and record

Before calculating any signal outcome:

1. Verify SHA-256 for every required archive ZIP against the saved audit
   manifest; record count, missing, mismatch, and malformed rows.
2. Audit exact hourly UTC grids for klines and mark prices, apply and validate
   the daily recovery overlay, and verify funding interval continuity for all
   included symbol-months.
3. Confirm the only exclusion is the predeclared IMXUSDT symbol and preserve
   the original 36-symbol cohort in metadata.
4. Verify the fixed candidate and scorer with synthetic unit tests: 52-bar
   lookback boundary, UTC weekday/hour mapping, ties and neutral returns,
   ATR uses only prior bars, entry-bar path, stop-first same-bar hits, adverse
   stop gaps, target gaps, timeout, missing path bars, no-overlap scheduling,
   funding timing, and prefix/future-mutation invariance.
5. Compute and record the development-selected baseline before opening the
   exploratory score summary. Store the prereg hash, code hash, archive
   fingerprint, exact data exclusions, seed, and reproduction command.

If any pre-score check fails, record `BLOCKED` and do not score. Write outputs
only to a new, unique research run directory. Do not modify old runs, raw data,
or existing registry rows; append one registry record only after the complete
run result is persisted.
