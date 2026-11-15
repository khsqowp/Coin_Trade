# Corrected BTC-impulse / ETH-lag probe — preregistered after invalid-run audit

Status: exploratory only. This definition is recorded after the prior run's result was viewed, so it is not prospective preregistration or untouched OOS evidence. The prior run is invalidated because its lag comparison was asymmetric and its 5-minute aggregation did not exclude gaps.

## Frozen hypothesis

For BTCUSDT and ETHUSDT, aggregate UTC 5-minute bars only when all five expected one-minute candles exist. Require a continuous 5-minute history across both symbols for feature returns and outcomes. Let BTC's current 5-minute log return be standardized against the preceding 20 valid 5-minute BTC returns using their population standard deviation (ddof=0); signal only when the signed z-score is at least 2 in absolute magnitude. Let direction be the sign of the BTC return. ETH must have moved in the same direction, but by less than BTC: 0 <= direction * ETH_return < direction * BTC_return. This symmetric condition must permit both long and short signals.

Enter at the next ETH 5-minute open. Risk R is the preceding fully completed ETH 5-minute high-low range divided by entry price. Set stop at 1R and target at 2R; evaluate the next 50 consecutive ETH one-minute candles. Resolve same-minute stop/target touches stop-first, use the adverse one-minute open for stop gaps, target price for target gaps, and the final one-minute close at expiry. Do not overlap trades within each strategy. Invalid/incomplete feature or outcome windows are skipped without interpolation.

Compare with two independently non-overlapping controls: BTC impulse without the ETH lag condition, and an ETH-only signed 20-return z-score impulse at the same threshold. Apply round-trip cost cases of 0.10%, 0.30%, and 0.15% (base plus 0.05 percentage-point slippage stress) as simple return deductions. Report direction at expiry, target-first rate, Wilson lower bound, net-positive rate, mean net return, and a seven-calendar-day circular moving-block 95% interval. The accuracy threshold is a Wilson 95% lower bound of 80% with at least 200 events; this is a research gate, not evidence of profitability.

## Data boundary

Use only the local read-only candle database, with exclusive cutoff 2026-11-14 00:00 UTC. The selected historical sample has already been viewed in prior work. No exchange/API calls, orders, live deployment, or database writes are allowed. Fingerprint the queried rows only; do not hash or claim to identify the entire database as the exact trial input.
