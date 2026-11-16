# R016 handoff

1. Preserve `chart_predictor/data/crypto_l2_pilots/20261116T022419Z-e6b6faed/` unchanged. It is an incomplete DNS-failure record, not a capture to resume.
2. On a later attempt, first run a short DNS and public-connectivity preflight for both Binance hosts, including a real depth websocket open and unauthenticated REST snapshot. A simple HTTP response from another endpoint is insufficient.
3. If all preflight checks pass, use a new run directory and the preregistered command:

   ```sh
   /opt/anaconda3/bin/python3 -u scripts/research/crypto_l2_pilot.py --run --inject-depth-disconnect-after-s 300
   ```

4. Keep the frozen limits: 60 minutes synchronized capture, 75 minutes maximum wall time, 512 MiB hard total output, one depth-socket client close at 300 seconds, both books recover within 30 seconds, and at least 99% book coverage for each symbol.
5. Do not interpret mocked recovery as a live pass. Do not read archived OHLCV or this event stream to claim directional accuracy or profitability.
