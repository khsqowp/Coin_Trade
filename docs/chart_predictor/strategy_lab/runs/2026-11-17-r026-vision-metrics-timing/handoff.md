# R026 handoff

1. R026 establishes only sampled timestamp alignment: six recent BTC/ETH OI symbol-days point to `create_time + 5m`; four June taker-flow symbol-days align to the same labeled 5-minute trades interval, which is complete at label +5m.
2. Apply a conservative +5-minute availability lag to these two fields in any future pipeline, but do not generalize to top-trader/account ratios, other symbols, or older history.
3. The OI inventory-shock/unwind candidate remains conditional and unregistered. First gather/quality-audit the eligible metrics series, freeze numeric shock/unwind rules and its R021/R023/R005 ablations, and establish PIT universe, cost/funding data, and a fresh untouched OOS boundary.
4. Cross-market result remains 0/2 equities and 0 crypto target-first-qualified signals. Do not describe the data timing check as strategy success.

Reproduction instructions and limits are in `report.md`; per-input aggregate hashes are in `results.json`. Public source data inputs were not committed.
