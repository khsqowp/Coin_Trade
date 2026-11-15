# Crypto candidate preregistration: BTC impulse and altcoin underreaction

Status: fixed exploratory development test; this does not create an untouched holdout. The six-symbol development database and its historical interval have been used in earlier research. No result from this test can establish an 80% validated signal or forward performance.

## Hypothesis

After a BTCUSDT five-minute return exceeds the trailing 30-day 95th percentile of absolute five-minute BTC returns, an altcoin that underreacted relative to a lagged BTC/alt beta is more likely to continue in BTC's direction if the alt's prior 15- and 60-minute returns already agree with that direction. The rule emits no signal otherwise.

This tests one fixed BTC-lead/alt-lag hypothesis. It is not a parameter grid and is not a claim that the cited literature establishes profitability on Binance USDⓈ-M.

## Frozen signal and execution

- Universe: `BNBUSDT`, `BTCUSDT`, `DOGEUSDT`, `ETHUSDT`, `SOLUSDT`, `XRPUSDT`; BTC is the driver and is not a traded target. These are the complete symbols in `vision_dev.sqlite`, not a point-in-time or delisting-complete universe.
- Data: completed 1-minute OHLC from the existing `vision_dev.sqlite`; evaluation anchors are strictly before `2026-07-01T00:00:00Z`. The test must not read `candles.sqlite` or any anchor at/after the cutoff.
- For signal minute `i`, BTC's five-minute log return is `log(BTC.close[i] / BTC.close[i-5])`. The impulse threshold is the 95th percentile of absolute BTC five-minute returns from the preceding 30 complete UTC calendar days, calculated once per UTC day and excluding that day. Require at least 20,000 valid prior-minute observations; do not interpolate gaps.
- Estimate each alt's beta to BTC from the preceding 60 one-minute log returns ending before the BTC impulse window begins. Use the ordinary least-squares slope with an intercept. Require all 60 paired returns and positive BTC return variance.
- Alt residual is its five-minute log return minus lagged beta times BTC's five-minute log return. A long signal requires BTC return above the positive threshold, negative alt residual, and positive alt returns over the preceding completed 15- and 60-minute windows. A short signal is the exact sign-symmetric condition.
- Evaluate only at 1-minute anchors. Enter at the next 1-minute open. Stop distance is the simple mean of the last 14 completed 1-minute true ranges, including the signal minute; target is 2R. No overlapping candidate forecasts per alt: after a signal, suppress further signals for that symbol for 20 minutes.
- Resolve barriers against the original 1-minute OHLC path with stop-first same-minute ties and adverse stop-gap fills, using the existing deterministic `score_forecast` implementation. Score separate 10- and 20-minute deadlines. Deduct 0.10% round-trip fee in the base case and 0.30% in stress. Slippage, spread, depth, funding, and actual liquidation are not available in this price-only probe and must not be described as modeled.

## Baselines and reporting

At each accepted candidate anchor, compare against (1) the sign of the alt's preceding five-minute return and (2) a deterministic SHA-256 direction keyed by the fixed seed, symbol, and entry timestamp. Baseline forecasts use the same entry, absolute stop distance, 2R target, outcome path, and horizon. Also report always-flat as zero signal coverage, not as a directional accuracy score.

Report every symbol and each horizon, event counts, target/stop/timeout counts, target-first precision, Wilson 95% interval, event coverage over eligible symbol-minute anchors, net-positive fraction, mean net R under base/stress costs, and matched-baseline differences. Report the fixed trial count as one hypothesis; 10/20-minute horizons and two baselines are dependent diagnostics, not independent replications.

## Decision gates

This historical diagnostic is development evidence only. A `forward-test` decision requires no glaring causal/data-quality failure and a result worth prospectively collecting; it is not promotion. No current result can pass the user's complete research objective because the source contains only six symbols, the universe is not point-in-time, and the period is already exposed. The eventual 80% gate remains at least 80% target-first precision, at least 10% coverage, at least 200 non-overlapping events across at least 20 symbols, a clustered uncertainty lower bound above both directional baselines, positive net expectancy, and independent genuinely future data.

## Required causal checks

Use only closed bars; lag beta and threshold inputs so the impulse minute is excluded from their estimation; verify exact minute continuity through every feature and outcome; mutate all post-anchor OHLC values and assert the anchor signal is unchanged; include a deliberate future-peeking negative control; preserve signal rules and both horizons exactly as written.
