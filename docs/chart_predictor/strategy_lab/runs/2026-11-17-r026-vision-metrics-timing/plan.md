# R026 — Binance Vision metrics timestamp audit

Status: completed data-semantics diagnostic; **not a strategy trial** and not a performance claim.

## Question and scope

Determine whether two USD-M Vision 5-minute features (`sum_open_interest` and `sum_taker_long_short_vol_ratio`) align to their displayed `create_time` or a neighboring 5-minute interval, and whether a point-in-time replay may use the value at the displayed timestamp.

- OI cross-endpoint comparison: BTCUSDT and ETHUSDT; 2026-10-31 through 2026-11-02 inclusive. Compare each archive value against the public USD-M `openInterestHist` REST observation at `create_time - 5m`, `create_time`, and `create_time + 5m`.
- Taker-flow comparison: BTCUSDT and ETHUSDT; 2026-06-24 and 2026-06-25. Rebuild taker buy/sell base-volume ratio from publisher `aggTrades` (`is_buyer_maker=false` means taker buy); compare the same three 5-minute bins.
- Verify each Vision and aggTrades ZIP against its publisher SHA-256, and check each daily metrics timestamp grid for duplicate, off-grid, and missing slots.
- The Binance REST endpoint and Vision archive are separate publication paths from the same exchange, not independent data vendors. The comparison checks cross-endpoint consistency, not source-origin independence.
- Historical/non-production use only. No orders, live/manual signal generation, strategy outcomes, or sealed data were involved.

## Decision rule and limitations

This audit has no strategy pass threshold. The practical timing rule is conservative: a field whose value matches a completed interval or a period-end REST observation at label +5 minutes is unavailable before that time. Report the full ±5m alignment comparison and row-level error distributions; do not infer other fields or dates from these samples. The date selection extends an earlier 2026-11-01 BTC/ETH check and is therefore a diagnostic follow-up, not a preregistered performance experiment.
