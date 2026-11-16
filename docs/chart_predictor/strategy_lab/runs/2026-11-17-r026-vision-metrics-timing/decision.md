# R026 decision

**Decision: CONTINUE data validation; do not register the OI hypothesis for a performance trial yet.**

- On six recent BTC/ETH symbol-days, the Vision OI row matched Binance's 5-minute REST OI observation at `create_time + 5m` exactly. Use that lag for any future replay of comparable data, not the display timestamp.
- On four BTC/ETH dates around 2026-06-25, raw aggTrades indicate the taker ratio corresponds most closely to the same labeled five-minute interval. That interval closes five minutes later, so apply the same conservative availability lag. Outliers remain and no other fields are certified.
- These are same-exchange cross-endpoint diagnostics, not independent data-vendor validation and not evidence of strategy edge. No TP-first outcomes, net expectancy, direction accuracy, or OOS events were computed.
- The conditional OI inventory-shock/unwind hypothesis remains unregistered: exact numerical rules, complete historical OI coverage, PIT contract universe, costs/funding, candidate-specific sealed boundary, and baseline ablations are still missing. The crypto pass gate remains target-first >=80% and at least 200 non-overlapping OOS events per claim; current qualifying count is 0.

Prior domain and red-team reviews plus two follow-up research agents did not alter this decision. The OI candidate may be structurally distinct only if OI shock/unwind is defined separately from R021 funding/countertrend, R023 shock/range-break, and R005 order-book replenishment. Official public stock/ETF pages expose selected holdings and disclosure records, but do not supply a complete reusable PIT price/universe panel; the equity data gate remains closed.
