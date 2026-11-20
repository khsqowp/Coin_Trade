# Preregistration: USD-M 1h chart-setup M2 extension

Status: frozen before scoring the 36-symbol common cohort. This is a historical
re-evaluation of existing rule families, not a novel discovery or live signal.
All earlier P5–P9 trials remain part of the family trial history. This study
adds 38 existing setup implementations × 2 horizons = 76 fixed cells; there is
no parameter search or best-cell promotion.

## Question and scope

Can any already implemented chart setup produce a robust target-before-stop
rate on 1-hour USD-M perpetual data over the next 10 or 20 hours, while retaining
positive net expectancy after the previously audited base/stress fee proxies
and timestamp-aligned funding?

- Market: Binance USD-M perpetuals only.
- Universe: fixed 36-symbol exact archive cohort in
  `usdm_archive_coverage_20261120.json`, whose gap-free common monthly run is
  2023-03–2026-05. Do not replace symbols based on trial performance.
- Exact bar window: common hourly timestamps from 2023-03-23 15:00 UTC through
  the 2026-06-01 00:00 UTC exclusive endpoint. The raw timestamp audit must
  remain `PASS` before scoring.
- Data: `klines_1h`, `mark_price_1h`, and funding archives; all selected ZIPs
  must match the archived SHA-256 manifest. No 1m, 5m, 15m, 30m evidence is
  available in this dataset.
- Existing code: the exact `chart_predictor.setups.SETUPS` list and its current
  `generate_signals` implementation; no copying or modifying setup logic.

## Fixed candidates

All 38 names exported by `chart_predictor.setups.SETUPS` are evaluated as-is:

`supertrend`, `trendline_breakout`, `sr_retest`, `sweep_choch_retest`,
`avwap_hl`, `rsi_divergence`, `candle_reversal`, `fibonacci_pocket`,
`order_block`, `fabio_liquidity_mss`, `fvg_fill`, `frvp_breakout`,
`frvp_breakout_strong`, `heikin_ashi_reversal`,
`heikin_ashi_reversal_strict`, `bb_squeeze_breakout`,
`bb_squeeze_breakout_strict`, `orb_funding_session`,
`orb_funding_session_strong`, `vwap_band_fade`, `vwap_band_fade_stretch`,
`volume_climax_exhaustion`, `volume_climax_exhaustion_strict`,
`engulfing_rsi_extreme`, `engulfing_rsi_extreme_strict`,
`pinbar_stochastic_cross`, `pinbar_stochastic_cross_strict`, `doji_macd_flip`,
`doji_macd_flip_strict`, `star_pattern_volume_climax`,
`star_pattern_volume_climax_strict`, `order_block_engulfing_confirm`,
`order_block_confluence_aggressive`, `order_block_confluence_balanced`,
`order_block_confluence_conservative`, `fvg_fill_confluence_aggressive`,
`fvg_fill_confluence_balanced`, `fvg_fill_confluence_conservative`.

For every candidate, evaluate fixed horizons H=10 and H=20 1-hour candles,
target=2R, setup-defined stop=1R, one-way delayed entry at the next hourly
open, and unit notional/no leverage. The signal uses only the just-closed bar
and earlier data. Each candidate/horizon pair is one of 76 tests; duplicate or
related candidates remain included in the trial count.

## Chronological splits

| Split | UTC interval | Use |
|---|---|---|
| Development | 2023-03-23 15:00 through 2025-02-28 23:00 | Compute metrics and choose one baseline direction per horizon only. No candidate or parameter will be removed or changed. |
| Validation | 2025-03-01 00:00 through 2025-10-31 23:00 | Report fixed candidates; no selection, edits, or threshold tuning. |
| Sealed | 2025-11-01 00:00 through 2026-05-31 23:00 | Run once after code, setup names, metric logic, and this preregistration hash are frozen. No edits based on this result. |

Signals whose full H-candle outcome window crosses a split endpoint are excluded
from that split. No signal's outcome can read across the next split boundary.
Signals at development/validation boundaries may use prior causal bars for
indicator warmup, but the target, stop, and M1 outcome remain within their own
split.

## Signal path and outcome definitions

- Entry: next 1h candle open after the setup's closed-bar signal. If there is
  no complete H-candle future window inside the split, do not score the signal.
- Risk: `abs(entry - setup_stop)`. Discard a malformed stop that is not adverse
  to the entry. Target is entry ± 2×risk in the signal direction.
- M2: scan chronological hourly OHLC from the entry candle through H candles.
  Stop is checked before target within each bar; if both touch, count failure.
  A gap through a stop fills at the adverse bar open for net-return accounting.
  Target gaps are conservatively credited at the target price. Timeout is an
  M2 failure and exits at the Hth candle close.
- Entry-gap handling: the target and R distance are anchored to the next-bar
  entry open. If the setup stop is no longer adverse relative to that open
  (for example, a long stop is at/above entry), classify `INVALID_ENTRY` and
  count as an M2 failure rather than silently dropping the issued signal.
- M1: compare Hth close with signal-bar close. Direction labels use the existing
  scorer convention: flat band = 0.25 × pre-signal ATR(14) × sqrt(H); M1 is
  reported separately and is never substituted for M2.
- Funding: apply signed archived funding events strictly after entry and through
  exit time; positive rate is a long-side payment and a short-side receipt.
  Funding event timestamps and declared intervals must pass the raw-data audit.
- Fees: base 10 bp round trip and stress 30 bp round trip, matching existing
  historical crypto research assumptions. Add observed funding separately.
  These legacy scenarios contain no measured spread or slippage and cannot
  certify execution realism.

## Baselines and decision thresholds

- At every candidate signal timestamp, calculate always-long and always-short
  controls using the same entry time and absolute 1R stop distance, mirrored
  around entry, 2R target, horizon, and stop-first ordering.
- Select the stronger baseline direction per horizon using development data
  only; freeze that direction for validation and sealed reports.
- Report all-issued-signal M2, Wilson 95% interval, per-symbol M2, per-symbol
  non-overlap M2, and market-wide time-deduplicated M2. Do not treat correlated
  simultaneous altcoin signals as independent.
- Report M1, M2 coverage (scored signals / eligible symbol-hour anchors),
  number of symbols with signals, timeout/stop/gap outcomes, net expectancy in
  R and percent after both costs and funding, and benchmark rates.
- Promotion gate on sealed data: M2 point estimate >=80%, >=200 per-symbol
  non-overlap events, signals from >=20 symbols, coverage >=10%, positive net
  expectancy in both fee scenarios after funding, and the strategy's 95% Wilson
  lower bound above the development-selected frozen baseline rate. The market-
  wide time-deduplicated count is separately disclosed; threshold success does
  not erase remaining cross-asset dependence.
- A `PASS` additionally requires the walk-forward, multiple-testing, sensitivity,
  Monte Carlo/block-bootstrap, and independent ledger red-team gates defined in
  `comparable_evaluation_protocol_v1.md`. This preregistration alone cannot
  grant a final pass.

## Reproduction and preservation

The run must record this document's SHA-256, Git HEAD, hashes of the runner,
`setups.py`, and indicator code, aggregate selected archive fingerprint, exact
input paths, execution rules, split boundaries, and command. Write only to a
new research run directory; do not open or write under
`chart_predictor/data/`, modify existing run directories, or alter old registry
rows. Append one new registry row after results are persisted. If any selected
archive, timestamp, indicator causality, or split check fails, stop before
scoring and record the failed gate without fabricating results.
