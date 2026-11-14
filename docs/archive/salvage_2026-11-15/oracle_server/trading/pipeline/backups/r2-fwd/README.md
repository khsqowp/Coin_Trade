# Trading research pipeline (test env)
Flow: data store -> Researcher(deepseek-flash, + strategy library) -> Engineer(gpt-5.4-mini, tool calling) -> deterministic ablation -> Auditor(claude-haiku-5-5) -> Risk Engine gate -> [candidate export] -> Telegram notice.
Run (all via locked-down containers, image tp-pipeline:local; build: docker build -t tp-pipeline:local .):
  ./run.sh data data-fetch            # Binance public OHLCV -> data/ (parquet + meta.sqlite w/ sha256)
  ./run.sh kis kis-fetch              # KIS PAPER daily candles (005930, 000660)
  ./run.sh data data-verify | data-list | data-get --symbol BTC/USDT --tf 1d
  python3 driver.py pipeline --run-id my-run
  python3 driver.py demo --fixtures B1_shift_neg,B5_weekly_bfill
  python3 driver.py bench --models claude-haiku-5-5,deepseek-flash,gpt-5.4-mini --reps 3
  ./run.sh agent budget               # LLM spend ledger (follow-up task: \$1.5 allowance on top of the \$0.14975 baseline, auto-stop at 80% = \$1.20 new spend)
  unit tests: docker run --rm --network none --entrypoint python -v \$PWD/src:/app/src:ro -v \$PWD/tests:/app/tests:ro tp-pipeline:local -m pytest /app/tests
Secrets: secrets/llm.env (4 LLM keys) -> agent role only; secrets/kis.env -> kis role only. TOSS/Binance keys are never copied. Code written by LLMs runs only in the sandbox role (no network, no env).

## Follow-up additions (2026-10-25)
- Ablation (`src/tp/ablation.py`, CLI `sandbox-ablation`): strategy.py must define `RULES={name: desc}` and `generate_signals(df, disabled=frozenset())`. Each rule is removed in turn; signals/trades/returns are compared. DEAD rule (no effect) => gate BLOCK; weak rule => warning; ablation missing/invalid => BLOCK. Report: `runs/<id>/03b_ablation.json` (also shown to the Auditor). Replay of the old defect on real BTC data: `bench/ablation_run002.py` (sandbox role).
- Strategy library (`strategy_library/`, `src/tp/library.py`): Researcher gets only a compact index (<4.5k chars) and may request <=2 cards. Sources/licenses in `strategy_library/README.md`.
- Telegram (`src/tp/notify.py`, role `notify`, `secrets/notify.env`): one-way sendMessage only, disabled when TP_TELEGRAM_BOT_TOKEN/TP_TELEGRAM_CHAT_ID are absent, scrubs secrets. `./run.sh notify notify-test [--dry]`. Freqtrade's own Telegram: see FREQTRADE_TELEGRAM.md (owner action after token rotation).
- Dry-run candidate path (`src/tp/deploy.py`, role `export`): only when Auditor PASS + no dead rule + Risk gate ALLOW (re-checked from raw evidence, hashes, static code check). Writes `TPC_<symbol>_<hyp>_<sha8>.py` (+ overlay config) into freqtrade/user_data/strategies, registry + compose override in `candidates/`. It NEVER restarts anything; the swap/rollback commands are printed and notified for the owner to run.
- Markets: `python3 driver.py pipeline --market crypto|kr [--hyp-index 0|1] [--no-library] [--no-notify|--notify-dry]`. `kr` (005930, 000660 from KIS paper data) is analysis-only: the gate whitelist excludes it, no export.
- Tests: `docker run --rm --network none --entrypoint python -v $PWD/src:/app/src:ro -v $PWD/tests:/app/tests:ro -v $PWD/strategy_library:/app/strategy_library:ro tp-pipeline:local -m pytest /app/tests`
- Pre-change backup: `backups/pre-followup-20261025/`.

## Extension (2026-10-25): collectors, regime agent, strategy pool, arena
Backup before changes: `backups/pre-ext-20261025-1149/`. Progress log: `PROGRESS.md`. Budget: extension allowance $3.00 on top of ledger total $0.41241 (stop at 80% = $2.40; `TP_BUDGET_*` in config.py).

### Always-on services (no LLM, restart=unless-stopped, 512 MB / 0.5 CPU, read-only rootfs, caps dropped)
`./svc.sh start|stop|status|logs news|kis|deriv|hl` -- `tp-news` (role `news`, no keys), `tp-kiscol` (role `kiscol`, ONLY the 2 KIS paper vars), `tp-deriv` (role `news`), `tp-hl` (role `hl`, no keys).
Health: `./run.sh offline collector-status`. There is NO LLM scheduler; the regime agent runs only when you call `./run.sh agent regime-run` (a scheduler, if ever added, must default to OFF with a daily cap of $0.30).
- News/RSS/GDELT/F&G/funding/OI + Yahoo US daily: `src/tp/news.py` -> `data/news/news.sqlite` (+`parquet/`), US daily -> `data/ohlcv`.
- KIS paper 1-minute bars for 26 KOSPI large caps (+ranking-API movers when the paper server returns them) during KST 09:00-15:35 -> `data/intraday/kr/<day>/<code>.parquet`; token limit 1/min respected; 0.7 s between calls; 8000 calls/day cap.
- Binance PUBLIC derivatives: liquidation stream (`wss://fstream.binance.com/market/ws/!forceOrder@arr`; the old `/ws/` path delivers nothing), OI/long-short/taker 5m history (API keeps ~30 days, we keep accumulating), funding -> `data/deriv/deriv.sqlite`.
- Hyperliquid read-only: official public trades WebSocket (discovers active addresses; docs: users=[buyer,seller]) + `clearinghouseState` (public, gives `liquidationPx`) -> `data/hl/hl.sqlite`. Rate-limited to 300 of the documented 1200 weight/min. No signing, no `exchange` endpoint, no keys.
Every stored row has fetched_at, source URL and a sha256 of the raw item; as-of reads use `fetched_at <= T AND published_at <= T`.

### Regime agent (`src/tp/regime.py`, `./run.sh agent regime-run --market crypto|kr|us|all`)
Inputs: as-of price features (trend, momentum acceleration, volatility, volume change), BTC flow (ETH lead/lag and correlation, ETH/BTC ratio as dominance PROXY), summarized news/features, and the two separate liquidation sources. Output: fixed JSON schema (label, confidence, event_risk, rationale with evidence ids that must exist in the input, strategy_weights over a fixed family list, risk_multiplier in [0,1]). Cheap model (deepseek-flash) + Auditor-class consistency check (claude-haiku-5-5). Every judgement is appended to `runs/regime_log.sqlite` (append-only triggers + hash chain: `./run.sh agent regime-verify`).
**NO BACKTEST USE**: the model may remember what happened after a historical date, so news/regime judgements are never used in historical backtests. They are evaluated forward only (regime_log vs later realized prices). The strategy pool is backtested without the agent.
Prompt-injection controls: no tools in the call, news wrapped in `<<<UNTRUSTED_NEWS_DATA ... UNTRUSTED_NEWS_DATA>>>` (our delimiters are defanged inside the text), schema + id validation, risk can only be reduced, no code path from the output to orders/config/network. Test: `./run.sh agent regime-injection-test`.

### Strategy pool (`strategy_pool/`, deterministic, `./run.sh sandbox pool-evaluate`)
Interface: `RULES`, `generate_signals(df, disabled=frozenset())`, `META`, `PROTECTIVE`, `RULE_KINDS`, optional `NEEDS_BTC`, `verifiable()`.
coin: trend_mtf (15m/1h/4h-style consensus + ATR trail), mean_reversion, breakout_squeeze, momentum_accel, chart_patterns (pivot confirmation delay K=5; S/R breakout+retest, double bottom, ascending triangle, bull flag; no images), btc_regime_alt (ETH with BTC regime filter), liq_cluster (UNVERIFIABLE). stocks: trend_sma200, tsmom (+`pool.rotation_picks`), lowvol_quality. KR: kr_surge_chase (UNVERIFIABLE: needs 1-minute data, simulator `tp.krsurge`, paper only, no order code).
`UNVERIFIABLE` strategies get `backtest.unverifiable` and the gate blocks them (`UNVERIFIABLE_STRATEGY`). Allocator (`tp.allocator`): regime weights -> exposure, clamped by the Risk Engine profile (`tp.risk.PROFILES`: crypto_fast / kr_equity / us_equity, values identical to RiskConfig defaults; frozen).
Pipeline run for one pool strategy: `python3 driver.py pool-run --strategy coin_trend_mtf --symbol BTC/USDT --tf 1h` (Researcher describes -> Engineer writes tests -> sandbox backtest -> ablation -> Auditor -> Risk gate; never exports).
Costs used for coin strategies: 0.10% fee + 0.05% slippage per side (the gate's minimum is lower; not relaxed).

### Protective rules (E)
A rule listed in `PROTECTIVE` is not blocked as dead because history never triggers it. It must FIRE on deterministic synthetic stress (`tp.stress`: gap crash -12/-25%, 10 consecutive -3% bars, halt-like zero-volume gap then -20%), injected at bars where the strategy is long: plain test (rule off lets the strategy stay long) or isolated test (all other exits off). No fire anywhere => dead => BLOCK. Non-protective rules keep the old policy. Tests: `tests/test_protective.py` (reproduces the `hard_catastrophe_stop` case of run fu-crypto-003-h2).

### Liquidation concentration (same format from two sources, `tp.liqmap`, `./run.sh offline liq-maps`)
(2) Binance proxy = ESTIMATE from public OI history + long/short ratio + klines with assumed leverage mix (5/10/20/50/100x), proportional closes, sweep by bar range, mmr 0.5%; positions older than the OI window are invisible; real exchange-wide leverage distribution is unknown. (3) Hyperliquid = MEASURED SAMPLE of positions of addresses seen trading >= $25k (no official full account list exists, we do not scrape indexers) -> coverage vs exchange OI is printed. Both are labelled unverified; `coin_liq_cluster` stays UNVERIFIABLE until >= 90 days of history.

### Survival arena (F) -- virtual capital, smoke only
`src/tp/arena.py`, `./run.sh sandbox arena-smoke`. 2-4 virtual accounts (100,000 virtual USDT), inference cost deducted each epoch (real ledger cost or base x multiplier), bankruptcy line (20%), retire-worst/clone-best, every order through RiskEngine.check_order (agents cannot change the frozen config). Metrics per epoch: pressure, distance to bankruptcy, average position fraction, position changes -> `runs/arena/arena.sqlite`.

### Tests
`./pytest.sh` (offline container) -- all tests incl. the original 79.
