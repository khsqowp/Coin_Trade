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

## Subsequent public-feed capture — completed

After the sandboxed DNS failure, a separately authorized read-only public-market-data preflight succeeded. The same public endpoints then supported the unchanged R016 pilot; no account credentials, order endpoints, or signal generation were used. This later result supersedes the earlier statement that the real WebSocket/snapshot path remains unverified; the earlier failed preflight remains part of the run history.

- Run: `20261116T025255Z-cc3a1f96`; exact command: `/opt/anaconda3/bin/python3 -u scripts/research/crypto_l2_pilot.py --run --startup-timeout-s 60 --inject-depth-disconnect-after-s 300`.
- Status: `completed`, exit 0; 3,600-second target, 3,605.226 seconds recorded, 121,098 JSONL records, 178,680,760-byte capture. The partial file was finalized as `capture.jsonl`; no `.partial` file remains.
- Controlled client-side depth disconnect fired once. Resynchronization completed in 1.740 seconds for BTCUSDT and 1.801 seconds for ETHUSDT, both within the 30-second criterion.
- Synchronized-book validity was 99.816% for BTCUSDT and 99.809% for ETHUSDT. Both exceed the pilot's 99% criterion.
- Aggregate-trade sockets were connected for the full capture. The observed aggregate trade IDs had zero possible ID jumps; this is not proof of exchange-side event completeness.
- Independent checks: all 121,098 JSONL lines parsed; SHA-256 of `capture.jsonl` was `aff87b771f2494fdc70ccc424e0a383f32670183d9753a83e68a92b9ebb1a991`, matching the manifest.
- Manifest: `chart_predictor/data/crypto_l2_pilots/20261116T025255Z-cc3a1f96/manifest.json`. Capture bytes and manifest are ignored local research artifacts, not committed to Git.

## Decision and next action

The collector passed this one-hour operational pilot's explicit acceptance criteria for one injected client-side depth WebSocket disconnect. This does not test router, ISP, or exchange-side failures; it does not prove complete market-event capture, executable fills, predictive accuracy, or profitability. It is not a strategy result. The previously stated instruction to wait for a successful preflight is satisfied for the tested BTCUSDT/ETHUSDT public endpoints, but further reliability qualification would need additional fault classes and longer/independent runs before production use.
