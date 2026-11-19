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

## Repeated DNS failure and recovery retest — 2026-11-20

The earlier successful preflight did not guarantee that a later pilot could resolve the hosts. Run `20261119T142815Z-36775338` ended `incomplete` with `synchronized startup timeout`; its allowed connection-state records show six paired depth/aggTrade `gaierror` failures, no connected sockets, and no bridged books. The requested fault injection was not triggered. This is a DNS precondition failure, not evidence of failed reconnect recovery.

A fresh read-only preflight then returned `ready` for both DNS hosts, the public `depth@500ms` and `aggTrade` streams, and BTCUSDT/ETHUSDT public depth snapshots; it created no capture files. The same preregistered R016 configuration was run in a new directory:

```sh
/opt/anaconda3/bin/python3 -u scripts/research/crypto_l2_pilot.py --run --capture-seconds 3600 --max-wall-seconds 4500 --max-bytes 536870912 --inject-depth-disconnect-after-s 300 --symbols BTCUSDT,ETHUSDT
```

- Run `20261119T143507Z-d6705e44`: `completed`, exit 0; synchronized capture 3,605.436 seconds against a 3,600-second target.
- The controlled client-side depth disconnect triggered once at the registered 300-second point. Both books bridged after reconnect: BTCUSDT 1.611 seconds, ETHUSDT 1.790 seconds.
- Valid-book coverage: BTCUSDT 99.8151% (3,593.344 seconds); ETHUSDT 99.8082% (3,593.094 seconds). Both exceed the registered 99% threshold.
- aggTrade sockets were connected for 100% of the capture window. This is socket-time coverage only, not proof of complete event delivery. Aggregate-trade ID diagnostics found zero possible jumps; this also does not prove exchange-side completeness.
- All registered acceptance flags are true: complete requested capture, one injection, recovery of both symbols within 30 seconds, and ≥99% coverage. Total output was 361,604,823 bytes, below the 536,870,912-byte cap.
- Independent integrity check: actual `capture.jsonl` SHA-256 `c3f3c6a6fb2097a2baf61031923c6fe6de5d45fe3d8c668f21c72dc01bb3a960`, size 361,597,591 bytes, and 329,585 newline-terminated records match the manifest. The recorded collector script SHA-256 also matches the current script: `2fa9a294272b2dce79d81f576ca5d6f768441dc08f5dba7d373e3885d35b3dad`.
- The raw capture and manifests remain ignored local research artifacts and were not added to Git. They were not mirrored to Linux/NAS in this run; `/Volumes/HDD2TB/Trade` was not available. No credentials, orders, trading signals, or strategy outcomes were used.

### Decision

R016 passes its one-hour, two-symbol controlled client-side reconnect/recovery gate on this run. This establishes only that this collector restored these two books after one injected client-side depth-socket close under the tested network conditions. It does not cover ISP/router/server failures, prove full market-event completeness or executable fills, validate the requested local+Linux archive, or demonstrate predictive accuracy or profitability. Keep the result out of the strategy-performance scorecard.
