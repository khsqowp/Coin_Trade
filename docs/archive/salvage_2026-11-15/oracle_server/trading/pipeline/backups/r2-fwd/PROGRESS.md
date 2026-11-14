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
