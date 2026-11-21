# Preregistration proposal — adaptive selective classifier to target-first M2

Status: **PROPOSED / NOT APPROVED / NOT SCORED**. This is the single
specification correction after the Round S panel's first HOLD. The candidate
is a new local adaptation of selective prediction, not a reproduction of the
fixed-odds paper cited in Round R. Do not read strategy outcomes or run this
candidate until a fresh Blue/Red/Data-Methods/Judge panel clears this exact
file. A historical pass would remain an exposed rolling diagnostic, not Core
or sealed-OOS evidence.

## Hypothesis and source distinction

Among completed USD-M 1-minute candles, a pooled classifier trained on causal
price/candle/taker-volume features can identify a subset of anchors where the
next 10-minute ATR barrier is more likely to be reached in one direction
before the opposite barrier. A rolling, outcome-blind score quantile selects
the emitted subset. The hypothesis is distinct from tested fixed-rule
momentum, reversal, funding, premium, CVD divergence, candle-pattern, and
indicator-regime candidates: it is a learned three-class, path-first label
with an adaptive score-rank emission rule. Distinction is structural, not
evidence of an edge.

The inspiration is the fixed-odds close-direction selective model in
[Round R](phase8_source_round_r_ml_selective_m2_panel_20261121.md). That paper's
label, asset count, payout, coverage, and results do not transfer to this
candidate. This proposal does not use the paper's unavailable code or
features.

## Frozen scope and input contract

- Venue/instrument: Binance USD-M USDT perpetual contracts; signal and label
  prices use `um_klines_1m` contract OHLC. No spot, mark, index, funding, OI,
  depth, trade tape, cross-symbol inputs, symbol identifier, or order API is a
  model feature.
- Fixed cohort (32, no volume ranking or substitutions):
  `AAVEUSDT`, `ADAUSDT`, `APTUSDT`, `ARBUSDT`, `ATOMUSDT`, `AVAXUSDT`,
  `BCHUSDT`, `BNBUSDT`, `BTCUSDT`, `CRVUSDT`, `DOGEUSDT`, `DOTUSDT`,
  `ENAUSDT`, `ETCUSDT`, `ETHUSDT`, `FILUSDT`, `HBARUSDT`, `INJUSDT`,
  `LINKUSDT`, `LTCUSDT`, `NEARUSDT`, `OPUSDT`, `POLUSDT`, `RUNEUSDT`,
  `SEIUSDT`, `SOLUSDT`, `SUIUSDT`, `TIAUSDT`, `TRXUSDT`, `UNIUSDT`,
  `WLDUSDT`, `XRPUSDT`.
- Evaluation interval: `[2026-07-01T00:00:00Z, 2026-10-01T00:00:00Z)`;
  anchors must also leave a full 10-minute horizon before the interval end.
  This three-month interval was selected from the structural archive audit,
  not candidate outcome scores. It is previously exposed research history.
- The source audit verified the selected 32-symbol price grids for this
  interval in its 2026-11-21 snapshot. Before scoring, rerun data-only
  preflight against current bytes and reject the run if any required contract
  candle is missing, duplicated, off-grid, invalid, or changes during the
  run. The entire archive audit is still FAIL; a passing interval preflight
  does not cure missing files, other timestamp gaps, funding anomalies,
  survivorship, or unknown historical publication/vintage times.
- All times are UTC. Candle `t` is usable only after its one-minute close.
  A causal replay may use rows timestamped no later than the anchor close;
  no claim is made that monthly archive values are byte-for-byte values seen
  live at that time. Store per-input SHA-256, bytes, row count, schema, time
  range, code hash, dependency versions, and run ID before score reads.

## Features — fixed formulas

For each symbol and completed candle `t`, use exactly these 12 features:

1. `r_k = ln(close[t] / close[t-k])`, `k ∈ {1,3,5,10}`.
2. `range_pct = (high[t]-low[t])/close[t]`.
3. `body_ratio = (close[t]-open[t])/(high[t]-low[t])`.
4. `upper_wick_ratio = (high[t]-max(open[t],close[t]))/(high[t]-low[t])`.
5. `lower_wick_ratio = (min(open[t],close[t])-low[t])/(high[t]-low[t])`.
6. `atr14_pct`: arithmetic mean of the 14 true ranges ending at `t`,
   divided by `close[t]`; true range is
   `max(high-low, abs(high-prev_close), abs(low-prev_close))`.
7. `rv20`: sample standard deviation (`ddof=1`) of the 20 one-minute log
   close returns ending at `t`.
8. `volume_z60`: sample z-score of `ln(1+volume)` over the 60 completed
   candles ending at `t`, including `t`.
9. `taker_fraction_5`: arithmetic mean over the five completed candles
   ending at `t` of `taker_buy_volume/volume`.

All windows are right-aligned and include only fully closed candles. A feature
is ready only when every required input row/column is present and the complete
lookback is available. A zero range makes the three candle ratios missing; a
zero volume makes that candle's taker fraction missing; no partial-window
averaging or forward/backfill is allowed. `HistGradientBoostingClassifier`
uses its native missing-value handling; no fitted imputation or scaling is
performed. Missing feature values are allowed only where the formula above
defines them; non-finite OHLCV or missing required columns fail preflight.

## Label, signal, entry, and event ledger

- The classifier's training label for anchor `t` is built using the next
  contiguous minute candle's open `E = open[t+1]` and `R = ATR14[t]`.
  Require `open_time[t+1] = open_time[t] + 60,000 ms`, `E > 0`, and `R > 0`.
- Freeze symmetric barriers at entry: upper `E+R`, lower `E-R`. The first
  complete candle after entry is bar 1; scan bars 1 through 10 inclusive.
- If high first touches upper, label `UP_FIRST`; if low first touches lower,
  label `DOWN_FIRST`; if neither is reached by bar 10 close, label `NO_HIT`.
  If both barriers are touched in one bar, label `NO_HIT` (conservative
  ambiguity). If a bar needed for the label is absent, that training row is
  excluded and separately counted; the evaluation preflight must prevent this
  from occurring in the fixed test interval.
- Do not train on an example unless its full ten-bar label path ends before
  the model's training cutoff. The 10-minute purge is mandatory.
- At each feature-ready anchor, emit `long` when `P(UP_FIRST)` is strictly
  greater than both other class scores and the selective score passes below;
  emit `short` when `P(DOWN_FIRST)` is strictly greater than both. Any exact
  class-score tie emits nothing. The model outputs are uncalibrated class
  scores; do not call them calibrated probabilities or confidence.
- For an emitted forecast, the assumed execution is the next contiguous
  minute open. If that open is missing, keep the forecast in the issued M2
  denominator and coverage numerator, count M2 as failure, and record
  `ENTRY_MISSING`; no fill, fee, or funding is fabricated.
- After entry, long target/stop are `E+R` / `E-R`; short target/stop are
  `E-R` / `E+R`. In each minute, a stop touch takes precedence if both sides
  are touched. A stop gap fills at the worse of the stop and that candle's
  open; a target fills exactly at its barrier with no price improvement.
  If neither barrier is reached, exit at the tenth candle close. Same-minute
  target/stop ambiguity is an M2 failure and stop-first PnL.
- A test event with an absent post-entry candle is an M2 failure; it invalidates
  the interval preflight and the run is **DATA_INVALID / NO PERFORMANCE
  VERDICT**, not silently dropped or assigned a synthetic PnL. Report its
  count. The separate target-first denominator remains every issued
  `long|short` forecast; timeouts, same-bar touches, entry gaps, and missing
  entry are failures.

## Model and chronological schedule

- Model: pooled `sklearn.ensemble.HistGradientBoostingClassifier`, with no
  symbol ID and no class weighting. Fixed parameters:
  `loss=log_loss`, `learning_rate=0.05`, `max_iter=100`,
  `max_leaf_nodes=7`, `max_depth=None`, `min_samples_leaf=20`,
  `l2_regularization=1.0`, `max_bins=255`, `max_features=1.0`,
  `early_stopping=False`, `random_state=20261121`; all other parameters are
  pinned to installed scikit-learn defaults and included in the run manifest.
- Fit rows are all symbols at anchors whose UTC minute number modulo 5 is 0;
  inference is every feature-ready minute. This fixed 5-minute training grid
  controls fit size and is not a parameter search. Sort by anchor time then
  symbol; do not rebalance classes or sample using labels.
- Calibration replay starts at `R0 = 2026-06-03T00:00:00Z`. At each replay
  refit instant `Rk = R0 + k*7 days`, fit a model on
  `[Rk-208d, Rk-28d)` and use it only for anchors in `[Rk,Rk+7d)`. Thus the
  June 3 model trains on `[2025-11-07, 2026-05-06)` and the June 10 model
  trains on `[2025-11-14, 2026-05-13)`; continue every seven days through
  June 24. Generate and append each score at its anchor before reading any
  later outcome. The four replay models produce the full
  `[2026-06-03,2026-07-01)` calibration score ledger; no one fixed model
  scores the entire interval.
- First evaluation model is initialized at `2026-07-01T00:00:00Z`. At each
  weekly refit instant `T = 2026-07-01T00:00:00Z + n*7 days`, train on the
  fixed 180-day interval `[T-208d, T-28d)`. Include a fit row only if its
  full 10-minute outcome path is complete before `T-28d`; require at least
  200,000 fit rows and at least 5,000 examples of each class. If either
  minimum fails, issue no signals for that refit week and report the failure.
- Weekly training cutoff is exactly `T-28d`, not the end of the last observed
  label. For each model refit, use the last 28 days `[T-28d,T)` of stored
  prequential scores generated by the seven-day replay schedule above. Each
  score's generating model has a fixed 180-day fit interval ending exactly
  28 days before its own replay/refit instant. Never regenerate an earlier
  score with a later model.
- Calibration score at each anchor is
  `s = max(P(UP_FIRST), P(DOWN_FIRST)) - P(NO_HIT)`. The threshold is the
  nearest-rank 90th percentile of `s` across **all feature-ready calibration
  anchors**, including negative scores. For `n` scores, sort ascending and
  select the one-based rank `ceil(0.90*n)`; ties are retained. Emit only if
  `s > 0` and `s >= q90`; equality is included. Require at least 1,000
  calibration anchors; otherwise issue none. This ranks/selects scores only;
  no calibration outcomes or target labels enter the threshold.
- Store every forecast score before the subsequent outcome exists. The
  2026-07..09 evaluation is a historical simulated walk-forward, not a
  contemporaneous forecast archive, untouched OOS, or sealed validation.
  No tuning, rule revision, or rerun after opening the test outcome ledger.

## Denominators, baselines, costs, and statistical reporting

- Coverage denominator: every feature-ready symbol-minute anchor in the fixed
  interval with a full 10-minute horizon before the interval end. Eligibility
  is decided from the anchor's past/current feature availability and the
  preregistered calendar boundary only—not from future entry/path success.
  Missing next opens and missing future paths stay in the denominator.
  Coverage numerator: all emitted `long|short` forecasts before execution or
  outcome checks. Report issued, executed, missing-entry, and invalid-path
  counts separately.
- Primary M2 = target-first successes divided by **all issued actionable
  forecasts**, including non-execution, no-hit, same-bar ambiguity, and
  timeout failures. Report Wilson 95% interval. Expiry direction accuracy is
  separate: issued side compared with tenth-bar close versus anchor close;
  missing path is incorrect and separately counted.
- Report per-symbol M2 and coverage. At least 20 symbols must have at least
  one issued signal. Require at least 200 total issued forecasts.
- Non-overlap: report per-symbol and global samples. Each event's scheduled
  entry timestamp is `anchor_close_ms`; if the next candle is missing, retain
  that scheduled timestamp for non-overlap selection. For the strict global
  sample, group forecasts by anchor timestamp; keep the event with largest
  selective score (ties: lexicographically smallest symbol), then suppress
  all later anchors before `scheduled_entry_ms + 10 minutes`. A missing-entry
  event remains selected, counts as M2 failure, has no PnL, and occupies its
  fixed window. Selection uses only forecast-time values and the fixed
  horizon, never actual exit times. The global non-overlap M2 sample must
  contain at least 200 issued events.
- Baselines, scored at the exact same candidate-issued symbol/anchor events
  under the same entry/barriers/costs: (a) side from sign of the preceding
  10-minute close return, zero => baseline failure/no side;
  (b) deterministic random side from SHA-256 of
  `"20261121|symbol|anchor_ms"`, first digest bit; and (c) no-signal. The
  candidate must have its M2 Wilson lower bound strictly above the same-event
  momentum baseline M2 point estimate. Report all baselines; no baseline
  choice after results.
- Gross trade return: `side*(exit-entry)/entry`. Funding is a holding cost,
  never a feature. Freeze settlement mapping to the exact helper in
  `scripts/research/mark_deviation_m2_probe.py`, SHA-256
  `c1c4e2fd8a27a2a2d9ad430855d115682b9ca749bb15d87ce19e9fd736bf7a69`:
  read `calc_time`, `last_funding_rate`, and `funding_interval_hours`; require
  strictly increasing timestamps and positive intervals; each consecutive
  timestamp delta must be within 1,000 ms of either adjacent row's declared
  interval in milliseconds; set `offset_ms = calc_time % 60_000`, require
  `offset_ms <= 1_000`, and map to
  `minute_ms = calc_time - offset_ms`, and require an exact corresponding
  mark-price minute. Any failure invalidates the run. For each funding event
  with
  `entry_ms < calc_time <= exit_candle_close_ms`, signed return is
  `-side * rate * mark_open_at_settlement / entry`. If a funding event shares
  the exit minute with an intrabar barrier, charge it. If funding inputs fail
  their timestamp/interval QA, the entire candidate run is DATA_INVALID.
- Apply the existing total round-trip fee proxies of 10 bp (`0.001`) and
  30 bp (`0.003`) once per executed round trip. Do not add a new slippage estimate; explicitly state
  that neither proxy includes measured spread/slippage. Net expectancy is the
  arithmetic mean net return per issued forecast, with an unexecuted
  `ENTRY_MISSING` event contributing zero and no fee; report per executed
  trade too. Both proxy cases must have positive expectancy.
- Bootstrap exactly 1,000 circular 7-calendar-day blocks with seed
  `20261121`. The sampling unit is the full UTC-day panel containing every
  symbol's issued events, preserving same-day cross-symbol dependence. For
  the 92-day interval, draw 14 start-days uniformly with replacement from
  the 92 UTC dates, concatenate each selected day and its following six days
  circularly, then retain the first 92 dates. Recompute M2 and mean net
  expectancy on each resample. Report 2.5/50/97.5 percentiles. Bootstrap
  intervals describe uncertainty; the Wilson-baseline gate remains the only
  interval-based pass criterion.
- Full unchanged candidate gates: M2 point estimate `>=80%`; issued M2
  `N>=200`; global non-overlap M2 `N>=200`; at least 20 symbols; coverage
  `>=10%`; Wilson 95% lower bound above same-event momentum baseline; positive
  mean net expectancy at both 10bp and 30bp round-trip fee proxies plus
  realized funding. Report expiry direction accuracy separately. No partial
  credit or gate changes.

## Reproducibility and stop conditions

Preflight before outcome access: verify the exact 32-symbol list and frozen
interval; every required Parquet schema/column and dtype; sorted unique
60-second timestamps; valid OHLCV; current per-file state/hash before and
after read; mark/funding alignment for cost accounting; no missing test bars;
Python/scikit-learn/numpy/pandas/pyarrow versions; estimator `get_params()`;
feature prefix-invariance and future-mutation tests; synthetic target/stop,
same-bar, timeout, gap, missing-bar, funding-boundary and fee unit tests.
Freeze the run manifest and code/test hashes before opening candidate
outcomes. Any preflight failure means `DATA_INVALID`, zero outcome scores,
and no parameter change. A failed performance gate rejects this version; no
second optimization round is authorized by this preregistration.

Current environment observed 2026-11-21: Python 3.13.5, scikit-learn 1.7.2,
NumPy 2.2.6, pandas 2.3.3, PyArrow 21.0.0. These are preflight evidence,
not a completed backtest or pinned deployment environment.

## Approval record

Initial exact proposal panel (2026-11-21): Blue HOLD, Red HOLD,
Data/Methods HOLD, Judge HOLD. No data outcomes were opened and no score was
computed. Their corrections are incorporated once in this proposal. A fresh
independent four-role vote on this file is required; do not score without
unanimous `CLEAR_PREREGISTRATION`. Even a historical pass is not Core; a
prospective untouched forward period and execution-cost evidence remain
necessary.
