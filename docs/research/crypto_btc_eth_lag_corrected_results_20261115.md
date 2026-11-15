# Corrected BTC-to-ETH lag test — 2026-11-15

## Decision

Reject the corrected candidate on this development sample. The trade target was reached first in only 25.30% of 929 events, the 95% Wilson lower bound was 22.61%, and average gross return was effectively zero before costs. The result does not support the 80% accuracy goal or positive cost-adjusted expectancy.

## Invalidated prior run

The earlier agent result reported 500 all-long trades. A source audit found the lag comparison used direction * ETH_return < BTC_return, which fails to reverse the right-hand side when BTC is down. It also aligned shared 5-minute timestamps without rejecting missing intervening 5-minute buckets, allowing multi-interval changes to be treated as 5-minute returns. That output must not be used as an estimate for the symmetric strategy. The old JSON/trade log remain only as an audit record in /tmp; the corrected probe is the reproducible record.

## Corrected test

The fixed definition requires complete five-minute buckets from five one-minute rows, continuous five-minute intervals for the prior-20-return z-score, a signed BTC z-score of at least 2, and ETH movement in the same direction but smaller than BTC's directional return. The next ETH five-minute open is entry; prior completed ETH five-minute range sets 1R stop / 2R target; 50 consecutive one-minute rows resolve barriers stop-first, with adverse stop-gap and final-close expiry. Controls remove the lag condition or use ETH's own signed impulse. All strategies prohibit overlapping positions. Costs are 0.10%, 0.15%, and 0.30% round trip.

The read-only local database supplied 172,799 BTC and 173,150 ETH one-minute rows before the exclusive cutoff, yielding 34,559 and 34,630 complete five-minute bars and 34,559 aligned rows. Corrected lag signals produced 929 trades: 504 long and 425 short. The 7-day moving-block gross-return interval spans zero (−0.0154% to +0.0147%). The strategy's average net return is −0.1001% at 0.10% cost, −0.1501% at 0.15%, and −0.3001% at 0.30%; the mean is gross return minus the modeled round-trip cost. Target-first rate is unchanged by those cost deductions.

| Rule | N | Long / short | Target first | Wilson 95% lower | Mean gross | Mean net at 0.10% | Mean net at 0.30% |
|---|---:|---:|---:|---:|---:|---:|---:|
| Corrected BTC impulse + ETH lag | 929 | 504 / 425 | 25.30% | 22.61% | −0.0001% | −0.1001% | −0.3001% |
| BTC impulse only | 2,472 | 1,307 / 1,165 | 26.94% | 25.23% | −0.0033% | −0.1033% | −0.3033% |
| ETH impulse only | 2,391 | 1,241 / 1,150 | 28.98% | 27.20% | +0.0046% | −0.0954% | −0.2954% |

The corrected lag filter does not beat either control on target-first rate or gross mean. ETH-only has the highest target-first rate, still below 30%, and negative mean net return after base cost. The Wilson intervals account for binomial sampling only; the seven-day moving-block interval is the dependence-aware uncertainty estimate for the mean gross return. Neither corrects for this post-hoc strategy choice or prior experiments on the same period.

## Verification and limits

Synthetic tests cover complete-bucket aggregation, a bearish symmetric short signal, future-row mutation invariance, and stop-first same-minute ambiguity. The full historical run used a read-only SQLite connection and a hash over queried BTC/ETH minute timestamps and OHLC values. This is historical development data already inspected, not OOS. The price path does not model exchange fills, funding, order-book spread, latency, leverage, liquidation, or calibrated probability. Do not promote this result to a live/manual signal.

Reproduce with python3 scripts/research/crypto_btc_eth_lag_corrected_probe.py --db chart_predictor/data/candles.sqlite. The source and machine-readable summary are [the probe](../../scripts/research/crypto_btc_eth_lag_corrected_probe.py) and [the JSON result](crypto_btc_eth_lag_corrected_20261115.json).
