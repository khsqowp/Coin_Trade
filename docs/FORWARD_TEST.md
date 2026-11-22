# PAPER forward tests

The isolated services store Binance public spot klines and synthetic PAPER fills in separate directories: `trading-forward-test/forward.db` for `l5_4h` and `trading-forward-test-12h/forward.db` for `l5_12h`. Neither has credentials, reads `.env`, or contains order code. Each maintains independent `combined`, `long_only`, and `short_only` books for BTCUSDT, ETHUSDT, BNBUSDT, SOLUSDT, and XRPUSDT. Each first run freezes its own forward start at the current UTC interval boundary; older candles warm indicators only. Entries require a signal on a bar at or after that profile's `forward_start`, then fill at the following bar open.

## Frozen configuration

Signal: `bb_depth_pct=0`, `bb_use=close`, `bb_window=4`, `stc_lag=4`, `stc_level=40`, `stc_lookback=5`, `stc_turn_type=1`, `stoch_cross_lag=4`, `stoch_level=30`, `stoch_min_cross_age=0`; all omitted signal knobs use `signal_frame()` defaults. Strict BB + stochastic + STC conjunction; long and short.

Management: 2 adds, 2% spacing, 1x add size, ATR(14) x 4 stop using ATR before entry, 2% target, 48-bar time stop, no BB-mid/opposite exit, 0.04% fee and 0.02% slippage per side, 1,000 notional per fill, 10,000 capital per book. Fills follow next-open and stop-first OHLC ordering. Research reference: 255 test trades over approximately 1.9 years and +20.6% summed across five symbols.

### `l5_12h` profile

Interval: Binance `12h` (`43,200,000` ms), with the same five symbols, indicator periods, books, capital, sizing, fees, and slippage. Signal: `bb_depth_pct=0`, `bb_use=close`, `bb_window=4`, `stc_lag=4`, `stc_level=40`, `stc_lookback=5`, `stc_turn_type=1`, `stoch_cross_lag=4`, `stoch_level=25`, `stoch_min_cross_age=0`. Management: 2 adds, 2% spacing, 1x add size, ATR(14) x 2 stop using ATR before entry, 10% target, 60-bar time stop, no BB-mid/opposite exit. Research reference: train +114.0% (174 trades), test +48.8% (78 trades), walk-forward -10.2%, plateau `FRAGILE`. These are historical research figures; the negative walk-forward result and fragile plateau are material robustness caveats, not evidence of forward profitability.

## Run and inspect

From the repository root, enable only the added profile when bringing up this service:

```sh
docker compose -f docker-compose.trading.yml --profile forward-test up -d --build trading-forward-test
./scripts/forward_test_status.sh
./scripts/forward_test_status.sh --json
./scripts/forward_test_status.sh --book long_only --since 2026-11-20 --trades 20
docker compose -f docker-compose.trading.yml --profile forward-test up -d --build trading-forward-test-12h
./scripts/forward_test_status.sh 12h
./scripts/forward_test_status.sh 12h --json
```

The runtime selects configuration and scheduler cadence with `FORWARD_PROFILE` (default `l5_4h`). Status accepts `--profile l5_12h`, or `FORWARD_PROFILE=l5_12h`; the wrapper's first argument `12h` selects the separate 12h container.

On a fresh Linux checkout, create the bind directory and give it to the image's non-root `app` user before starting the persistent container:

```sh
mkdir -p trading-forward-test
docker compose -f docker-compose.trading.yml --profile forward-test build trading-forward-test
docker compose -f docker-compose.trading.yml --profile forward-test run --rm --user root --entrypoint sh trading-forward-test -c 'chown -R app:app /app/data'
docker compose -f docker-compose.trading.yml --profile forward-test up -d trading-forward-test
```

For a fresh 12h data directory, run the same preparation commands with `trading-forward-test-12h` as service and `trading-forward-test-12h` as directory. Each service runs 20 seconds after its own UTC 4h or 12h boundary. The 12h container name is `ochestration-trading-trading-forward-test-12h-1`.

The loop catches up on startup, then runs 20 seconds after each UTC 4h boundary. Inspect logs with `docker logs -f ochestration-trading-trading-forward-test-1`. A heartbeat older than 5 hours is `STALE`.

### `jbb_1h` profile

`trading-forward-test-jbb-1h` runs the vendored `jesse_simple_bollinger` signal on Binance 1h candles for BTCUSDT, ETHUSDT, BNBUSDT, SOLUSDT, and XRPUSDT. It stores state in `trading-forward-test-jbb-1h/forward.db`, uses a single long-only book (`combined` status is an alias of `long_only`), $10,000 reference capital, fixed $1,000 notional, 0.04% fee and 0.02% slippage per side. The frozen parameters are `bb_len=25`, `bb_k=2.5`, `conv=9`, `base=26`, `span_b=52`, and `disp=26`. Signals use the bar close; entries and signal exits fill at the next bar open. There are no stops, targets, adds, or short positions. Initial download is limited to the latest 60 days, supplying ample history for the 78-bar span-B plus displacement warm-up; the frozen `forward_start` prevents a warm-up signal from opening a position.

Run and inspect it with `docker compose -f docker-compose.trading.yml --profile forward-test up -d --build trading-forward-test-jbb-1h` and `./scripts/forward_test_status.sh jbb [--json]`. It schedules 20 seconds after each UTC 1h boundary. Status remains `INSUFFICIENT DATA` until at least 100 closed trades and 60 elapsed days.

Historical reference: train +35.6% over 1,414 trades; test +13.8% over 885 trades; null percentile 100 and `ROBUST` plateau. This is a candidate, not a proven edge. The test result falls to +3.2% at 2x costs, secondary coins return +1.7%, and this candidate was selected after testing about 149 strategies.

## Verdict and reset

For `l5_4h` and `l5_12h`, `INSUFFICIENT DATA` remains until both 30 closed combined trades and 90 elapsed days. For `jbb_1h`, the threshold is 100 closed long-only trades and 60 elapsed days. After the applicable threshold, negative net return is `NEGATIVE`; otherwise fewer than half the historical-rate expected trades is `UNDERPERFORMING`; remaining cases are `ON TRACK`. The L5 expected count scales 255 trades across 1.9 years by elapsed days; JBB scales 885 test trades across its approximately 1.9-year cached test slice. These are operational gates, not evidence of future profitability.

Stop one service with `docker compose -f docker-compose.trading.yml --profile forward-test stop trading-forward-test` or `... stop trading-forward-test-12h`. To reset a profile, stop it, back up or delete that profile's `forward.db` and `status.json`, then start it again. Reset sets a new forward start and does not alter the other profile or trading service.

## Implementation limits

The forward engine persists candles, signals, positions, trades, equity marks, runs, and heartbeat in SQLite. Full-history signals are recalculated from the stored candle history before advancing each symbol cursor. If a candle gap is found, the loop repairs it by refetching from the earliest gap. `live_ref_price` records the public ticker price at detection, falling back to the latest candle close if that ticker request fails.
