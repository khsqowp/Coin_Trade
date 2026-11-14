# Trading research pipeline (test env)
Flow: data store -> Researcher(deepseek-flash) -> Engineer(gpt-5.4-mini, tool calling) -> Auditor(claude-haiku-5-5) -> Risk Engine gate.
Run (all via locked-down containers, image tp-pipeline:local; build: docker build -t tp-pipeline:local .):
  ./run.sh data data-fetch            # Binance public OHLCV -> data/ (parquet + meta.sqlite w/ sha256)
  ./run.sh kis kis-fetch              # KIS PAPER daily candles (005930, 000660)
  ./run.sh data data-verify | data-list | data-get --symbol BTC/USDT --tf 1d
  python3 driver.py pipeline --run-id my-run
  python3 driver.py demo --fixtures B1_shift_neg,B5_weekly_bfill
  python3 driver.py bench --models claude-haiku-5-5,deepseek-flash,gpt-5.4-mini --reps 3
  ./run.sh agent budget               # LLM spend ledger (hard stop at 80% of \$2)
  unit tests: docker run --rm --network none --entrypoint python -v \$PWD/src:/app/src:ro -v \$PWD/tests:/app/tests:ro tp-pipeline:local -m pytest /app/tests
Secrets: secrets/llm.env (4 LLM keys) -> agent role only; secrets/kis.env -> kis role only. TOSS/Binance keys are never copied. Code written by LLMs runs only in the sandbox role (no network, no env).
