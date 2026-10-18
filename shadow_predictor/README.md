# Kronos shadow predictor

This is a separate, order-free research sidecar for the six-symbol, 20-strategy paper engine. It reads the existing paper-state JSON through a read-only mount and writes forecasts, later forecast scores, and strategy-position conflict observations into its own Docker volume. It does not change the paper engine, its ledgers, or strategies; it has no exchange credentials, exchange client, or order path.

## Run

From the `Ochestration/trading` directory:

```sh
docker compose -f shadow_predictor/docker-compose.shadow.yml up -d --build
tail -f shadow_predictor/runtime/shadow_predictor.log
docker compose -f shadow_predictor/docker-compose.shadow.yml exec crypto-shadow-predictor python -c 'import json; print(json.dumps(json.load(open("/output/shadow_predictions.json")), ensure_ascii=False, indent=2))'
```

The compose file expects the existing source state at `../trading-crypto-paper-state/crypto_paper_strategies_6symbols.json`. Results persist in the Git-ignored `shadow_predictor/runtime/` host directory, outside Docker Desktop's virtual-disk volume store. Stop only the sidecar with `docker compose -f shadow_predictor/docker-compose.shadow.yml down`; this leaves the results intact.

The image build downloads the public Kronos source and Kronos-mini model/tokenizer from GitHub and Hugging Face. `KRONOS_GIT_REF` defaults to the pinned revision `67b630e67f6a18c9e9be918d9b4337c960db1e9a`. CPU-only PyTorch is installed. After build, the runtime container is offline (`network_mode: none`) and has no host port, exchange key, or exchange client. The build requires outbound access to GitHub and Hugging Face.

## Evaluation semantics

For each newly observed symbol minute, Kronos-mini forecasts five 1-minute candles. The sidecar records the 1-minute and 5-minute close forecasts, then scores them only after those target candles appear in the source state. Metrics report model MAE, no-change (random-walk) MAE, and directional accuracy by symbol/horizon. They are descriptive out-of-sample shadow observations, not evidence of profitability; forecasts do not become trade signals.

The output includes the current 20-strategy summary and flags positions whose side disagrees with a 5-minute forecast. The flag is review-only. No parameter, position, risk limit, or strategy is automatically adjusted. Require a substantial forward sample, fees/funding-aware simulator, baseline comparison, and explicit human review before considering any strategy change.

## Local checks

```sh
python3 -m unittest discover -s shadow_predictor -p 'test_*.py' -v
docker compose -f shadow_predictor/docker-compose.shadow.yml config --quiet
```
