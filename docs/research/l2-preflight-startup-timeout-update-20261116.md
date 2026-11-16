# L2 capture preflight and synchronized-start timeout — 2026-11-16

## Scope

This is a collector reliability change, not a strategy or signal-performance experiment. No archive data, strategy outcomes, exchange account endpoints, credentials, or order endpoints were used.

## Change

- Added `--preflight` to check DNS for `fstream.binance.com` and `fapi.binance.com`, open the exact public depth and aggTrade WebSocket endpoints, and fetch depth snapshots for BTCUSDT and ETHUSDT. The preflight runs before `Pilot` construction and does not create capture directories or files.
- Added a per-check timeout (`--preflight-timeout-s`, default 8 seconds).
- Added `--startup-timeout-s` (default 60 seconds) to stop a real pilot and write an incomplete manifest if synchronized books do not become valid before capture starts. The timeout is preserved in the manifest.
- Existing full-capture duration, maximum wall-clock limit, data-size cap, recovery criteria, and deliberate disconnect injection remain unchanged.

## Verification

- RED: focused tests failed collection because the specified `preflight` function did not yet exist.
- GREEN: all 32 tests in `chart_predictor/tests/test_crypto_l2_pilot.py` passed.
- Full suite: `292 passed`; one third-party joblib warning reported an empty physical-core count and fell back to logical cores.
- Live preflight invocation: `/opt/anaconda3/bin/python3 -u scripts/research/crypto_l2_pilot.py --preflight --preflight-timeout-s 2 --output-root chart_predictor/data/crypto_l2_pilots/preflight-must-not-create` returned exit 10 with `gaierror`.
- Confirmed the failed live preflight did not create the requested output directory. Therefore the collector's real WebSocket/snapshot path remains unverified; no capture or signal result was produced.

## Decision and next action

The fail-fast behavior is verified locally; Binance public connectivity is still unavailable from this environment because required DNS resolution failed. Do not start a long capture until `--preflight` returns `status: ready`. When it passes, run the unchanged R016 60-minute capture with the existing 300-second disconnect injection, using the new 60-second synchronized-start timeout. A successful preflight is only a connection check, not evidence of stream completeness, recovery, predictive accuracy, or profitability.
