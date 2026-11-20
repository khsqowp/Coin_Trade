# Preregistration draft — Pine composite regime trend-transition M2

Status: **Draft; do not score until the four-role panel accepts this exact
contract.** If accepted, authorize one development-only diagnostic on already
exposed history. It is not a sealed test, strategy approval, or Core result.

## 1. Research question and provenance

Question: does entering the Pine Regime Classifier's confirmed `Trend` state,
with direction taken from the just-closed candle, produce a higher target-first
rate than matched always-long/always-short controls on the fixed Binance USD-M
hourly cohort?

Source: WavesUnchained, *Regime Classifier* v1.1.3, build timestamp
2026-10-02, public [Pine source](https://github.com/casoon/pine-scripts/blob/main/indicators/trend_strength/regime_classifier/regime_classifier.pine)
and [MIT license](https://github.com/casoon/pine-scripts/blob/main/LICENSE).
The source content is pinned by its GitHub blob object ID (not a plain file
SHA-1)
`7fa6fe76631305448fa3526bef7bcaa8d56a6441` (retrieved 2026-11-20 through
the GitHub file API); implementation must independently verify downloaded
bytes using Git's `sha1("blob " + decimal_byte_length + NUL + raw_bytes)`
calculation. Retrieved source is 18,896 bytes with raw-byte SHA-256
`a65022e8abcfc38d82a9a8b31ab9abc75ee929e4e641c584a415c6e6b2e6f98b`.
The root MIT license blob ID is `4693362ee10a94d2d8a9a02b55852d2c8f0d4e94`,
1,071 bytes, SHA-256
`a468e9bc5c6a94a69f337a5ef276f065e778cd0170d7a7b8b3b71164a2e29d33`.
Reverify all IDs against fetched bytes before implementation.
Retain the MIT copyright/license notice in any vendored source snapshot. If
exact-byte verification fails, stop before scoring.
The source is a context/regime indicator, explicitly not a trade trigger. This
experiment is a custom strategy adaptation, not a source-reported strategy or
performance replication. The Git blob ID, version, and build timestamp form
the immutable source pin for this trial.

## 2. Frozen universe, data, and split

- Market: Binance USD-M COIN-underlying USDT perpetuals.
- Cohort: the fixed 36-symbol exact cohort
  `2023-03..2026-05` in `usdm_archive_coverage_20261120.json`; no replacement
  or post-result exclusions.
- Required inputs: hourly contract OHLCV, funding archive,
  archived SHA-256 manifest, raw timestamp audit. Existing input root, if its
  required artifacts verify, is `/private/tmp/cointrade-50_50-data`.
- Sole scoring window: development, `[2023-03-23 15:00 UTC,
  2025-03-01 00:00 UTC)`. Do not score validation or sealed rows in this
  experiment. The whole historical input has been exposed to prior research;
  no result from this experiment is independent OOS evidence.
- A signal is eligible only when all 20 outcome bars end strictly before the
  development endpoint. Count incomplete end-window signals as
  `TRUNCATED_AT_SPLIT`, outside M2.
- For causal indicator/state warm-up, use all verified, contiguous hourly
  contract bars available for each fixed symbol before the scoring start,
  beginning at the earliest monthly archive in the contiguous suffix ending
  before the scoring window. Initialize the source state on that symbol's
  first available archived bar exactly as Pine initializes `var` state; record
  each warm-up start. No warm-up outcomes are scored. Include every warm-up
  archive in checksum verification and the data fingerprint. A symbol with no
  pre-window archive starts its source state on its first scoring-window bar;
  disclose this left-boundary limitation.
- Binance Vision archives are restricted here to permitted personal,
  non-commercial, non-production historical backtesting. Do not generate or
  distribute live/manual signals from these archives, use them for production,
  or connect them to orders.
- Interval: native 1h. No HTF, unfinished candles, external features, or
  look-ahead inputs. Contract OHLC drives indicators and barrier fills; this
  is not a mark-price-trigger or liquidation simulation. Funding archives and
  raw timestamp audit must pass before outcomes are computed.
- Trial family: one fixed setup, one 20-bar maximum holding horizon, one
  parameter set. No parameter search, symbol selection, or direction variants.
- Registry reconciliation found no exact prior FDI+ER+CHOP `toTrend` setup.
  It is conceptually adjacent to existing SuperTrend/trend-transition and BB
  squeeze/breakout families; this is a novel fixed combination, not a wholly
  unrelated mechanism. This finding is limited to the current registry search.

## 3. Exact regime calculation

Implement a Python calculation equivalent to the Pine formulas below; use
closed bars only and preserve the source's default inputs:

1. `ER20 = abs(close[t] - close[t-20]) / sum(abs(close[j]-close[j-1]),
   j=t-19..t)` when both operands are available and denominator is positive;
   otherwise use the exact Pine conditional `erVol > 0 ? erChange / erVol : 0`.
   In particular, when the rolling sum is `na` during early history, Pine's
   comparison is false and ER is `0.0`; if the denominator is positive while
   the numerator is unavailable, preserve `na` propagation. Pin `math.sum`
   early-window behavior to the official Pine v6 reference semantics and test
   the branch boundaries before scoring.
2. `FDI30`: `half=15`; `r1=(highest(high[t-14..t])-lowest(low[t-14..t]))/15`;
   `r2=(highest(high[t-29..t-15])-lowest(low[t-29..t-15]))/15`;
   `r3=(highest(high[t-29..t])-lowest(low[t-29..t]))/30`; when `r1+r2>0`
   and `r3>0`, FDI is `(log(r1+r2)-log(r3))/log(2)`, clamped to `[1,2]`;
   otherwise use the source fallback 1.5. Pine `nz(fdiV, 1.5)` also supplies
   1.5 during unavailable FDI history; that fallback participates in the score
   whenever ER is available.
3. `CHOP14 = 100*log10(sum(TR[j], j=t-13..t) /
   (highest(high[t-13..t])-lowest(low[t-13..t]))) / log10(14)`, clamped to
   `[0,100]`; zero range or unavailable result uses the source fallback 50.
   Pine `math.sum` remains unavailable until its full 14 true-range values
   exist; then the result participates in the score.
   `TR=max(high-low, abs(high-prev_close), abs(low-prev_close))`; on the first
   available bar use `high-low`.
4. Map each sensor to a trend score, clamped to `[0,1]`, using
   `(value-range_anchor)/(trend_anchor-range_anchor)`: ER anchors 0.55/0.20,
   FDI 1.35/1.55, CHOP 38.2/61.8. Composite score is their equal-weight mean.
5. At each symbol's first archived bar initialize internal `regimeState=0`
   before calculating that bar's label. On every bar, first update the state:
   score `>=0.62` sets Trend; score `<=0.38` sets Range; otherwise, if state is
   still 0, score `>=0.5` sets Trend and lower scores set Range; otherwise
   retain the prior state. Then calculate Chaos and the displayed label for
   that same bar. This matches the pinned Pine source's `var int ... = 0` and
   statement order. Chaos is true only when all hold:
   `CHOP>=65`, `ER<=0.18`, `FDI>=1.55`; the displayed label is Chaos when true,
   otherwise the internal Trend/Range state. Do not clear the internal state
   during Chaos. FDI and CHOP fallbacks participate exactly as Pine specifies;
   the state machine is updated on every source-equivalent finite-score bar,
   including Pine fallback-driven early bars. For the fixed default inputs,
   record the first finite-score index and first raw-ER index separately for
   each symbol. Do not add a discretionary warm-up.
6. The signal event exactly matches the source's `toTrend` watch condition:
   `label[t] == Trend and label[t-1] != Trend`. No use of the Pine HTF call.

Before outcome scoring, source-equivalence tests must cover each sensor's
boundary/fallback behavior, state initialization/hysteresis, Chaos override,
the `toTrend` event, and prefix invariance/future mutation. Failures block the
run; do not approximate or silently repair source behavior.

## 4. Fixed trade rules

- At the confirmed signal candle `t`, side is LONG if `close[t] > open[t]`,
  SHORT if `close[t] < open[t]`. A doji (`close[t] == open[t]`) creates a
  `NO_DIRECTION` event;
  report it separately, exclude it from issued directional M2 signals and
  count it outside directional coverage.
- Entry is the next candle `t+1` open. Signal time is the signal candle close.
- ATR: Wilder ATR(14) on contract OHLC through the signal close. First ATR is
  the arithmetic mean of the first 14 true ranges (first TR=`high-low`); later
  values use Wilder recursion. Freeze at signal time. Non-finite/non-positive
  ATR is `INVALID_ATR`: record as attempted, not as an issued executable signal
  and not in M2; include the anchor in the coverage denominator and report the
  count/rate.
- Stop distance is exactly `1.0 * ATR14[t]`; target distance is exactly `2R`.
  Long: stop=`entry-risk`, target=`entry+2*risk`; short mirrors these levels.
- Stop and target are anchored at the known next-open entry, so a gap through
  the stop at entry is geometrically impossible under this rule. Entry is the
  next contract-kline open; no limit-order assumption. A missing next bar is
  `MISSING_ENTRY_BAR`, recorded as attempted but not issued executable M2; any
  such case fails the data-completeness gate.
- No re-entry in a symbol while its prior signal is active. Any new signal
  during the active trade is counted as `SUPPRESSED_IN_POSITION`, disclosed,
  and not queued. After exit, the next new `toTrend` event may enter.
- Inspect the entry candle plus the next 19 hourly candles, exactly 20 bars.
  Stop is checked before target on each OHLC bar; if both touch within one bar,
  count a stop failure. A stop gap fills at the adverse open; otherwise stop
  fills at stop. A target gap is credited at target, not improved open. If
  neither barrier hits, expire at the 20th bar close; timeout is M2 failure.
- A missing/nonconsecutive bar in an issued signal's path is `DATA_GAP`: retain
  as M2 failure and in coverage, do not impute a fill, and fail the data gate.
  No outcome may cross the development endpoint.
- Funding uses audited `calc_time` and rate, interpreted as settlement time;
  require the existing archived API cross-check to pass. Fixed notional is entry notional,
  with no compounding or mark-price resizing. For side `s` (+1 long, -1 short),
  funding cost per settlement is `s*rate`. Positive rate is a long cost and
  short credit. Include events strictly after entry and no later than exit-bar
  close. For settlements inside the exit candle, charge only
  `max(side_sign * rate, 0)` because intrabar ordering is unknown; do not count
  ambiguous credits. Report the signed rates and a sensitivity excluding
  exit-candle settlements. Missing expected funding intervals fail data QA;
  they are never treated as zero.
- Fee proxy is a total round-trip charge of 10 bp base / 30 bp stress applied
  once to entry notional, not per side. For entry `E`, exit fill `X`, side
  `s∈{+1,-1}`, total funding cost fraction `F`, fee fraction `c`,
`gross_return=s*(X-E)/E`, `net_return=gross_return-c-F`,
  `risk_fraction=ATR14/E`, and `net_R=net_return/risk_fraction`. Expectancy is
  the arithmetic mean over issued, data-evaluable outcomes. If any outcome is
  a data gap, report evaluable-only expectancy and missing count, but do not
  pass the data gate. Spread and slippage are unmeasured and excluded; these
  are incomplete fee-only scenarios.

- New `toTrend` at a bar close is processed after any stop/target/expiry exit
  that occurred by that bar's close. If no exit occurred and the old position
  remains open at the close, suppress the new event. This permits a next-open
  re-entry after an exit already confirmed on the same candle.

## 5. Outcomes, baselines, and reports

Report every fixed candidate outcome without cherry-picking: attempted
`toTrend`, no-direction, invalid ATR, suppressed-in-position, missing entry,
issued executable signal, target, stop, timeout, truncated-at-split, and data
gap counts. M2 denominator is issued executable directional signals with a
known entry open; `DATA_GAP` remains an M2 failure. Endpoint M1 compares the
20th entry-inclusive bar close with entry, irrespective of an earlier barrier
exit: strictly favorable in the predicted direction is correct; ties and
opposite closes are misses. Report M2 Wilson
95% interval (descriptive only under dependence), M1, coverage, symbols,
per-symbol issued-signal rates, market-wide non-overlap cluster and event counts,
base/stress net expectancy in R and percent, and signed funding contribution.

For each issued candidate timestamp, compute matched always-long and
always-short controls with the same entry, risk distance, mirrored 2R barrier,
20-bar expiry, gap logic, costs, and funding. Select the stronger baseline
direction on development only and report both controls as well as the selected
rate. This is a descriptive development comparison, not an inferential test.
For each arm/horizon/baseline, market-wide non-overlap is constructed by sorting
the unique entry timestamps across all candidate signals before reading any
outcomes. Treat every symbol at one timestamp as one cluster. Retain the
earliest timestamp, then the next timestamp only when it is at least 20 hours
after the previous retained timestamp; repeat. The fixed spacing matches the
maximum scheduled 20-hour horizon and does not use realized exit times. For
the retained sample report signal-bearing timestamp-cluster N, event-row N,
and distinct symbol count. Matched baseline outcomes inherit the candidate's
retained-cluster membership. This deterministic de-overlap does not imply
statistical independence. Report UTC entry-day clusters; Wilson intervals are
descriptive only, and no p-value or confidence claim is based on them. Coverage
denominator is all complete eligible symbol-hours after the first finite
Pine-equivalent score, including no-signal, doji, suppressed, and invalid-ATR
anchors. Coverage numerator is
issued executable directional signals, including outcomes later labeled
`DATA_GAP`; also report every attempted-event exclusion. Signals without a
complete 20-bar path before the split endpoint are separately counted and are
outside M2 and coverage numerator.

Hard Core gate remains as defined in [`SPEC.md`](../../chart_predictor/SPEC.md)
and `comparable_evaluation_protocol_v1.md`; it is **not adjudicated on this
development screen**: all-issued M2 >=80%; market-wide non-overlap
signal-bearing timestamp-cluster N>=200; retained non-overlap events from
>=20 distinct symbols; coverage >=10%; positive base and stress net
expectancy after funding; and Wilson 95% lower bound above the strongest
preregistered baseline. It also requires walk-forward, parameter robustness,
resampling, and independent-ledger red-team checks on genuinely untouched
forward evidence. This historical screen cannot pass or validate a Core gate.

## 6. Execution gate and artifact contract

Before scoring: panel approval of this exact hash; verify source pin/license,
archive checksums, raw timestamp audit, coverage, no-gap cohort, warm-up, and
funding boundary semantics. Implement only in a new research script, a new
output directory, and new tests. Do not edit existing runner outputs, raw
archives, chart_predictor local data, sealed results, or old registry rows.

Record preregistration SHA-256, source version/URL/Git blob ID/raw-byte
SHA-256/license-text hash, code SHA,
Git HEAD, archive manifest/fingerprint, command, all exclusions, and elapsed
time. Persist the complete per-signal ledger before summarizing. Run unit tests,
source-formula fixtures, prefix/future-mutation tests, and an independent
recalculation of up to 100 trades. Select the sample by sorting
`SHA256("pine-regime-audit-v1|" + symbol + "|" + signal_close_ms)` and taking
the first 100 (or all if fewer). Append one registry row only after
the run and ledger verify. If any source/data/causality/ledger gate fails,
record `BLOCKED` with the exact reason and no invented score.
