# R023 — BTC shock, cross-asset beta-residual laggard, and 5m range break

Status: **retrospective exploratory pilot, not preregistered**. The pilot was run before this protocol was written. This record therefore preserves the observed method and result, but does not upgrade the result to confirmatory evidence or validate the hypothesis. No parameter tuning followed the observed result.

## Hypothesis

After an unusually large BTC 4-hour move, an altcoin whose same-period return materially lags its trailing beta-adjusted expectation may catch up in the BTC shock direction after a 5-minute range breakout. A trailing residual filter should improve target-first rate and net expectancy over the same BTC-shock/range-break trigger without that filter.

This mechanism differs from R021's contrarian funding-extreme + BTC macro + pullback/re-entry mechanism. It uses cross-asset relative performance after a shock, not funding crowding. The R023 result is nevertheless exposed development evidence, not an independent replication.

## Observed rule and inputs

- Development window: `2020-10-01T00:00:00Z` inclusive to `2024-01-01T00:00:00Z` exclusive. No 2024-01-01-or-later prices were read by the pilot.
- Instruments: BTCUSDT as the shock series and BNBUSDT, DOGEUSDT, ETHUSDT, SOLUSDT, XRPUSDT as candidate traded contracts. These are six current survivors, not a point-in-time contract universe.
- Shock: the absolute completed BTC 4-hour return is at least the 90th percentile of the previous 180 completed BTC 4-hour absolute returns. The current shock is excluded from its threshold history. Direction is the sign of that return.
- Laggard filter: for each altcoin, estimate a no-intercept beta from its previous 180 completed 4-hour returns against BTC. Calculate the current 4-hour residual and divide by the sample standard deviation of residuals in that prior window. Keep the altcoin only when the shock-direction-adjusted residual is at most `-1.0` standard deviation.
- Entry: after the shock interval closes, inspect at most the next 12 completed 5-minute bars. Enter on the first close outside the preceding 12-bar high/low in the BTC shock direction, at the following 5-minute open. The baseline is the identical shock and range-break rule without the laggard filter.
- Risk and label: 14-bar simple-average true range at the signal bar defines 1R. Stop is 1R adverse; target is 2R favorable. Evaluate at most 20 subsequent 5-minute bars (100 minutes). Minute OHLC is used for barrier ordering; when stop and target both occur within a minute, stop wins. If neither barrier hits, exit at the final minute close.
- Costs: assumed round-trip fee plus adverse slippage is 14 bp of notional. This is an assumption, not an observed fill. No funding settlement occurred during the evaluated positions in this pilot, so measured funding R was zero; this does not establish that funding is immaterial for longer holds.

## Inference and limitations

The pilot resampled whole BTC-shock timestamps as event clusters for 4,000 bootstrap replicates. The candidate and baseline differ in sample composition because the lag filter removes events; the paired interval is a descriptive clustered comparison, not a causal estimate of a randomized filter. Six current contracts, current-contract survivorship, already-exposed data, no separate validation/sealed sample, no registered coverage denominator, and assumed execution costs prohibit M4 qualification.

The originating one-off script was stored temporarily at `/private/tmp/macro_lag_pilot.py` with SHA-256 `6339f52f4697530a40e256f249bddacd8ccb799cd7c58897f41064f2b344cbf6`. It was not added to the repository: it hardcodes machine-local data paths and lacks synthetic causality/boundary tests. The execution is reproduced in the manifest but must not be represented as a production-ready runner.
