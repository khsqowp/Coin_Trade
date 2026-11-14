# PROGRESS (extension task, started 2026-10-25)
Backup before changes: backups/pre-ext-*/  (src, tests, driver.py, run.sh, Dockerfile, README, strategy_library)

## Step 1 - collectors (A, D, derivatives, Hyperliquid)  [DONE, running]
- tp-news (role news, no keys): RSS fed/ecb/coindesk(+cointelegraph fallback)/yonhap(+mk)/bbc(+cnbc), GDELT DOC, Fear&Greed, Binance funding/OI snapshots, Yahoo US daily (18 symbols).
  BLOCKED part: GDELT DOC API answers HTTP 429 from this IP (documented limit 1 req/5s; still 429 at 11s spacing) -> job backs off up to 1h and retries.
- tp-kiscol (role kiscol, KIS paper vars only): 1-min bars for 26 KOSPI large caps; ranking API works on paper server (extra codes added at session start). Waits outside KST 09:00-15:35. Backfilled last session (2026-10-23: 390 bars x 26 symbols).
- tp-deriv (role news): Binance public liquidation stream (new /market/ws path), OI/long-short/taker 5m history (28d backfill) + funding history.
- tp-hl (role hl, no keys): Hyperliquid official public trades WS -> active addresses -> clearinghouseState (liquidationPx).
- Launch: ./svc.sh start|stop|status|logs news|kis|deriv|hl ; health: ./run.sh offline collector-status

## Step 2 - Regime agent (B)  [DONE]
- src/tp/regime.py, regime_cli.py: as-of inputs (price features, BTC flow, news/features, liq summaries), fixed JSON schema, evidence-id check, risk_multiplier<=1, Auditor consistency check, append-only hash-chained runs/regime_log.sqlite.
- Injection defence test (3 malicious fake news samples) PASSED: runs/regime_injection_test.json.
## Step 3 - Strategy pool (C) + protective rules (E)  [DONE]
- strategy_pool/*.py (11 modules), src/tp/{poolkit,pool,allocator,stress,krsurge,liqmap}.py, tp.risk.PROFILES (values == RiskConfig defaults), UNVERIFIABLE gate rule.
- Pool screen: ./run.sh sandbox pool-evaluate (runs/pool_registry.json). Coin strategies all BLOCK numerically (honest; not tuned).
## Step 4 - Survival arena (F)  [DONE - smoke only]
- src/tp/arena.py, ./run.sh sandbox arena-smoke (virtual capital, not scheduled).
## Step 5 - Integration (G)  [IN PROGRESS]
- pytest 147 passing; pool pipeline runs started (runs/ext-pool-*.log).
- [DONE] regime-run crypto/kr/us OK (runs/regime_run_all.json), injection test 3/3 (runs/regime_injection_test.json), regime_log chain verified.
- [DONE] pool pipeline runs: ext-pool-trend-btc1h, ext-pool-btcalt-eth1h, ext-pool-chart-eth1h3 -> all BLOCK (see runs/<id>/05_risk_gate.json).
- [DONE] pytest: 147 passed (79 original + 68 new). Telegram summary sent (1 message).
- [OPEN] KIS 1-minute live collection during a real session cannot be verified before Monday 09:00 KST (today is Sunday). Backfill of 2026-10-23 (390 bars x 26 symbols) is stored.
- [OPEN] LIQ proxy / surge strategies stay UNVERIFIABLE by design.

## Round 2 (2026-10-25)
- R2-1 cost models (spot/futures separate, official-source basis) + futbt (isolated margin, real funding, liquidation) + metrics (PSR/DSR) + tests/test_futbt.py
- R2-2 data: USDT-M klines BTC/ETH 5m-4h, funding history, FOMC calendar; research harness (trials registry, pre-registration file written before results)
- R2-3 studies S1 baseline, S2 sensitivity, S3 adaptive (W15/W5 walk-forward), S4 overlays: results in runs/research/*.json, summary research/RESULTS_round2.md
- R2-4 ops: tp-sched (daily cap 0.30, carry gate), tp-watch (watchdog + 23:00 UTC summary), retention jobs, KR/US whitelists in risk profiles (limits untouched)
- R2-5 forward paper tracker (tp.forward, registry runs/forward_registry.json, criteria in research/FORWARD_CANDIDATES.md), kline updater job in tp-news (30 min)
- R2-6 tests: 173 passed (./pytest.sh); restart recovery verified (docker restart of all 6 tp-* containers: no duplicate scheduler slot, hash chain OK)
- R2-7 one real daily-summary Telegram message sent (13 lines, scrubbed)
Backups of changed files: backups/r2-fwd/ and earlier backups/pre-ext-*.
- R2-8 timezone: host already Asia/Seoul+NTP (before=after); Hermes compose TZ=Asia/Seoul only, recreated, Telegram connected; code: explicit ZoneInfo (Seoul, New_York), budget day = KST midnight, summary header KST; storage unchanged UTC; 176 tests passed. Backups: backups/r2-tz/

## Round 3 (2026-10-25)
- R3-1 PREREG_round3.md written and hashed before any rotation backtest; data: 25 USDT-M perpetuals, 1h klines 730d, funding, exchange filters (public GET only)
- R3-2 rotation simulator (minNotional/stepSize/minQty rejection, isolated-margin liquidation, real funding), 66 selection trials, DSR, gate through new profile crypto_small_rotation, sensitivity (cost, leverage, phase, filters); result: nothing passes (RESULTS_round3.md)
- R3-3 trials registry de-duplicated (20 S4 rows were double counted; backup backups/r2-tz/trials.sqlite.pre-r3)
- R3-4 Hermes: export/hermes (sanitised, leak-scanned, regenerated every 30 min by tp-watch), compose volume :ro, skill pipeline-qa + SOUL pointer, 10 chat tests incl. injection and order refusal
- R3-5 budget incentive policy: tp.budget_policy (proposal only), budget.sh (owner approval on host), regime prompt policy paragraph, tests (203 passed)
- R3-6 watchdog fixes: parquet_export freshness limit key, GDELT 429 tolerance
