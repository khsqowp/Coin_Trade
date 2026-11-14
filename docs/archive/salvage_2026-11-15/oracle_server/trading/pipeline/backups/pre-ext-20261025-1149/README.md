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
