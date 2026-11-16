# R016 decision

## HOLD — live recovery was not tested

The bounded attempt did not reach synchronized streaming. During 171.943 seconds, the collector wrote 20 connection-error records, all reporting `gaierror`. No depth or aggTrade socket connected, no REST snapshot bridged, and the preregistered 300-second disconnect injection did not trigger. Therefore the zero coverage fields have no valid measurement denominator; they are not evidence of a zero-coverage live stream.

The attempt was stopped before the 75-minute wall deadline because repeated DNS failures meant the run could not produce useful capture data. Its 4,309-byte partial file and `incomplete.json` were retained. No prior partial or complete capture was changed. No credentials, account endpoints, or order endpoints were used.

The implementation is locally validated: 84 focused L2 tests passed, and all 288 `chart_predictor/tests` passed with one third-party CPU-count warning. Mock recovery still does not establish live recovery.

## What this does and does not conclude

- The L2 recovery gate remains open/HOLD.
- The network path was unable to resolve Binance hosts during this attempt; the result is an environmental precondition failure, not a collector recovery result.
- No trading strategy, signal accuracy, profitability, or 80% directional-accuracy claim was tested.
- The earlier two completed 60-minute captures remain valid for their recorded collection/integrity facts, but both observed zero reconnects, so they still do not demonstrate recovery.

## Next admissible action

Before another long run, require a short preflight that resolves both `fstream.binance.com` and `fapi.binance.com`, opens the public depth websocket, and completes a REST depth snapshot. If DNS or either public connection fails, stop before creating a 60-minute run. Once preflight succeeds, start a fresh run directory with the same frozen 60-minute/512-MiB/300-second-injection criteria; retain this failed attempt unchanged.
