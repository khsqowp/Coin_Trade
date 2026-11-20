# Preregistration — BTC/ETH-consensus lagging-alt 1h M2 screen (Round K)

Status: fixed exploratory development screen, written before execution. This is
a new adaptation of cross-cryptocurrency return-predictability research, not a
replication of the paper, not an OOS test, and not a Core candidate. The source
paper studies cross-sectional return prediction and does not prescribe these
signals, barriers, or exits. [Source paper](https://www.sciencedirect.com/science/article/pii/S0165188924000551).

## Question

When BTC and ETH have the same sign over the immediately preceding completed
hour, does taking the lagging alt in the leaders' direction improve fixed
10-hour target-first outcomes versus same-event always-long and always-short
controls, with positive modeled net expectancy after the repository's frozen
base/stress costs and observed funding?

This test is a one-time mechanism screen on exposed development history. It
cannot establish independent validation or promote a strategy.

## Frozen rule

- **Market/data:** Binance USD-M perpetual contract klines, mark-price archives
  for the required-input integrity check, and timestamped funding. Use the
  exact frozen 36-symbol 2023-03..2026-05 common cohort in
  `usdm_archive_coverage_20261120.json`; BTCUSDT and ETHUSDT are leaders only,
  leaving at most 34 target alts. Do not add/substitute symbols. The cohort is
  a current-history availability cohort, not a point-in-time universe.
- **Window:** development only, `[2023-03-23 15:00:00 UTC,
  2025-03-01 00:00:00 UTC)`. Only signals with a complete 10-hour outcome
  window wholly inside the development interval are eligible. All candidate
  history is considered exposed; validation/sealed dates are not read by the
  scoring process.
- **Signal returns:** at the close of hour `t`, for each symbol calculate the
  simple close-to-close return `r_x = close_x[t] / close_x[t-1] - 1` on the
  same two UTC hourly close timestamps. Require finite, aligned, fully closed
  bars for both leaders and the target alt.
- **Long:** if `r_BTC > 0`, `r_ETH > 0`, and
  `r_alt < (r_BTC + r_ETH) / 2`, issue a long signal for that alt.
- **Short:** if `r_BTC < 0`, `r_ETH < 0`, and
  `r_alt > (r_BTC + r_ETH) / 2`, issue a short signal for that alt.
- **Otherwise:** no signal. Equality at the leader mean, zero leader returns,
  mixed leader signs, missing bars, or invalid features produce no signal and
  remain in the eligible-opportunity denominator only when all required
  target/leader inputs and 10-hour future bars exist.
- **Execution:** signal is known only after hour `t` is closed. Enter at the
  next hourly contract-kline open (`t+1`). Do not fill at the signal close.
- **Risk/barriers:** risk `R` is the simple mean of the 14 true ranges for the
  14 fully completed contract bars ending at hour `t`, inclusive. True range
  is `max(high-low, abs(high-prev_close), abs(low-prev_close))`. Anchor TP/SL
  to the next-hour entry open: target `entry + side*R`, stop
  `entry - side*R` (1R:1R).
- **Path and expiry:** evaluate the entry bar and the next nine hourly
  contract-OHLC bars, for a 10-bar maximum hold. A stop touch is checked
  before a target touch within a bar; if both touch, record stop-first. A gap
  through the stop exits at the adverse bar open; a target gap is credited at
  the target price. Timeout exits at the tenth bar close and is an M2 failure.
  A missing/discontinuous future bar invalidates the source event, is counted
  as a data failure, and is never silently dropped from the audit.
- **Funding:** include only actual archived settlement events with
  `entry_time < funding_time <= exit_time`. Positive funding is a cost to a
  long and a credit to a short. On an exit-bar settlement whose within-bar
  chronology is unknown, charge a payment but do not credit a receipt. Do not
  prorate funding by elapsed hours.
- **Costs:** frozen legacy 10 bp round-trip base and 30 bp round-trip stress
  fee proxies. No spread or slippage is measured or added in this screen; the
  modeled net result therefore does not establish executable fill realism.
- **Signals/overlap:** score every issued directional signal individually for
  the all-issued M2 metric, including overlapping intervals. Separately report
  the earliest-event outcome-independent per-symbol non-overlap sample: sort
  by signal time; keep the first event and skip subsequent events for that
  symbol whose entry is before the previous kept entry plus 10 hours. Also
  report a stricter market-wide non-overlap sample: sort by entry time then
  symbol; keep the earliest event and skip any event starting before the prior
  kept entry plus 10 hours. These are dependence diagnostics, not separate
  tuning targets.
- **Coverage denominator:** all eligible target-alt × UTC-hour opportunities
  in the fixed 34-alt cohort within the development window, with aligned
  closed BTC, ETH, and alt bars, a valid 14-TR value, and a full 10-bar future
  path. Coverage is issued signals divided by this denominator. Report counts
  separately for every symbol.
- **Baselines:** on every issued signal timestamp, independently replay
  always-long and always-short with the same entry, absolute R, 1R target,
  1R stop, 10-bar horizon, contract-price path, tie/gap policy, costs, and
  funding. Report both; do not select or tune against them after seeing results.

## Metrics and one-run decision

Persist the full issued-signal ledger and report all-issued and both non-overlap
M2 rates with Wilson 95% intervals; M1 direction-at-expiry; eligible
opportunities; coverage; per-symbol signal/target/stop/timeout counts; event
dependence; average gross and net return under base/stress; expectancy in R;
funding; and both frozen baseline rates/net returns. Report all failed or
unevaluable events.

M1 is evaluated separately from entry execution: compare the close after ten
future hourly bars with the signal-bar close. The actual label is `up` or `down`
only when the signed move exceeds `0.25 * (R / signal_close) * sqrt(10)`; moves
inside that fixed volatility band are `flat` and count as not directionally
correct for this directional signal. This definition is fixed before the run.

The exploratory screen is worth a forward-only consideration only if every
fixed Core numerical screen is met on the development run: all-issued M2 >=
80%, per-symbol non-overlap N >= 200 across >=20 target symbols, coverage >=
10%, positive net expectancy in both cost scenarios, and lower Wilson bound
above the stronger same-event baseline. Since this dataset is exposed, meeting
those numbers is **not** validation, OOS, Core acceptance, or permission to
trade. Failure of any screen criterion rejects this exact specification; no
parameter, symbol subset, threshold, timeframe, or exit retuning is permitted.

The user-level Core gates still require a separate genuinely unseen forward
evaluation, independent review, and all data/execution/robustness gates. Phase
9 remains blocked unless a Core is validated.

## Reproduction and preservation

Input archives are read-only under the explicitly supplied `--archive-root`.
Before any outcome scoring, require the existing archive SHA-256 manifest and
raw timestamp/mark/funding cohort audits to pass. Record this preregistration
hash, Git SHA, runner/test SHA, selected data fingerprint, exact command,
cohort, splits, and trial count `1`. Write only to a new output directory.
Never read or write `chart_predictor/data/`. No network download, external
service, trading, or deployment is part of this run.
