# Round 6 — Binance public live-feed preflight — 2026-11-19

## Result

**Technical preflight passed; no market capture or strategy evaluation was run.** The repository's read-only preflight completed with `status=ready` using the current public Binance USDⓈ-M feed. It checked DNS for `fstream.binance.com` and `fapi.binance.com`, verified BTCUSDT and ETHUSDT are trading USDT perpetuals, opened public depth and market aggTrade WebSocket connections, and fetched public depth snapshots for both symbols. The script reported `capture_files_created=false`.

The standard sandbox attempt failed at DNS (`gaierror`). The same command succeeded through the approved network-enabled execution path; this indicates an execution-network boundary, not a Binance or collector failure. The default `/usr/bin/python3` lacked `websockets`; `/opt/anaconda3/bin/python3` had `websockets==13.1` and ran the existing code without environment or source modification.

Focused regression validation of `chart_predictor/tests/test_crypto_l2_pilot.py` passed: **41 tests**. This proves the tested local collector behaviors, not live reconnect recovery or strategy performance.

## Scope and limits

- Command: `/opt/anaconda3/bin/python3 scripts/research/crypto_l2_pilot.py --preflight --preflight-timeout-s 8 --symbols BTCUSDT,ETHUSDT`.
- No WebSocket payloads were retained; no capture files, market outcomes, API credentials, signed requests, account data, or orders were used.
- The preflight covers two symbols only. It does not establish 20-symbol performance, hour/day reliability, reconnection recovery, depth-qualified execution, cost/funding-adjusted returns, OOS sample size, M2, or profitability.
- `mount` showed HDD2TB was not mounted and `/Volumes/HDD2TB/Trade` was absent. Local `/private/tmp` filesystem availability was 47 GiB at the check. The user's requested local-plus-Linux duplicate archive was not verified; no Linux server was contacted.
- Tardis terms/sample/trial were not accepted or used. Binance Vision was not downloaded or queried in this run.

The official USDⓈ-M documentation currently routes high-frequency public depth to `/public` and regular market streams such as aggTrade to `/market`; it states connections expire after 24 hours and repeatedly disconnected IPs may be banned. The repository collector's `stream_urls()` uses these routes, and both handshakes passed in this preflight. This is transport readiness only; it does not establish complete historical data or downstream signal rights. See [Binance USDⓈ-M WebSocket Market Streams](https://developers.binance.com/en/docs/products/derivatives-trading-usds-futures/websocket-market-streams/Connect) and [Binance general Terms of Use](https://www.binance.com/en/about-legal/terms).

## Next admissible action

Do not start a long strategy capture until its output destination and replication procedure are available and the candidate rule is frozen. A later bounded recorder/reconnect test may validate collection infrastructure, but it must remain explicitly separate from strategy outcome testing. No strategy is approved and no return claim follows from this preflight.
