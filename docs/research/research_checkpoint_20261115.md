# Research continuation checkpoint — 2026-11-15

## Current conclusion

No tested strategy has demonstrated the requested 80% high-confidence crypto signal quality or the roughly 20% annual equity return goal under the evidence standard in the chart-predictor specification. Do not promote any result to live trading. Development results are not OOS evidence.

The specification's success gate is stricter than a raw hit rate: on a never-viewed sealed set, M4 high-confidence signals must have a Wilson 95% lower bound above momentum-persistence, random, and always-flat baselines; point estimate at least 80%; coverage at least 10%; at least 200 events distributed over 20 symbols; and positive net R-multiple expectancy after costs. The single-coin probes in this checkpoint cannot meet the 20-symbol requirement by design.

## Completed in this continuation

1. Replayed the BTCUSDT 1m three-candle streak probe on the local development database. Fixed a read-only NumPy array mutation error in ATR output. Results are preserved in the Round 11 report and JSON. Target-first was 47.67% over 177,025 trades; 95% Wilson lower bound 47.44%; mean net return −0.1444% at modeled costs. Reject.
2. Reproduced the US ETF downside-beta screen from local cache. Its JSON exactly matched the independent agent output. The strategy returned 3.21% base / 2.20% stress CAGR versus SPY at 13.88% / 13.74%; 84 evaluation months; no return edge. Reject.
3. Audited the prior BTC-ETH lag run and invalidated it: the filter emitted only long trades and admitted missing 5m gaps. Wrote a corrected symmetric, complete-bucket probe with a one-minute execution path and reran it read-only. Corrected lag N=929 (504 long, 425 short), target-first 25.30%, Wilson lower 22.61%, average net −0.1001% at 0.10% cost. Controls also fail. Reject.
4. The corrected BTC-ETH signal code has synthetic checks for complete buckets, bearish short generation, future mutation invariance, and stop-first ambiguous barriers.

Detailed results:

- US: [report](equity_us_downside_beta_results_20261115.md), [JSON](equity_us_downside_beta_20261115.json), [source](../../scripts/research/equity_us_downside_beta_probe.py).
- BTC streak: [report](crypto_round11_streak_results_20261115.md), [JSON](crypto_round11_streak_results_20261115.json), [source](../../scripts/research/crypto_round11_streak_probe.py).
- Corrected BTC-ETH: [definition](crypto_btc_eth_lag_corrected_preregistration_20261115.md), [report](crypto_btc_eth_lag_corrected_results_20261115.md), [JSON](crypto_btc_eth_lag_corrected_20261115.json), [source](../../scripts/research/crypto_btc_eth_lag_corrected_probe.py).
- KR compression breakout: [report](equity_kr_compression_breakout_results_20261115.md); fixed candidate rejected due only 50 trades, non-positive stress CAGR, and benchmark-difference intervals crossing zero.

## Verification

- Focused research tests: 14 passed, including the KR compression and US exclusive-cutoff tests.
- Full chart_predictor test suite: 103 passed, 1 non-fatal loky CPU-count warning.
- BTC streak rerun reproduced the same row/trade counts and reported metrics after the ATR fix; JSON serialization differs only in the last 1e-16 of two mean values.
- US downside-beta JSON rerun was byte-identical to the agent's captured JSON. Pandas emitted non-fatal timezone-to-period warnings.
- Crypto database access used SQLite read-only mode. No exchange calls, credentials, order APIs, or server actions were used.

## Worktree and Git caution

The shared main worktree was in an active merge of P8-C (VWAP band fade) with unresolved conflicts in setup_backtest.py, setups.py, tests/test_setups.py, and docs/chart_predictor/rounds.md. None of those files were edited by this research continuation. A separate worktree based on origin/main was used to isolate the research artifacts. Publish only the research-scoped branch/commit; do not resolve or push the unrelated active merge as part of this checkpoint.

## Next research loop

1. Continue two independent KR/US stock-or-ETF fixed-rule tests using local data, with a preregistered rule, exclusive date cutoff, matched-cost baseline, and point-in-time/data-adjustment caveats.
2. Continue two independent crypto signal tests across the requested bar periods. Report long and short separately, target-first and direction-at-horizon separately, stop/target/expiry outcomes, costs, coverage, Wilson and dependence-aware uncertainty.
3. Use development periods for screening only. Do not repeatedly select the best cell and call it validated. Preserve one genuinely unseen forward/sealed evaluation for a final one-time gate; if no candidate earns that gate, report no deployable strategy rather than tuning it away.
4. Keep all work local. Commit/push only the isolated research changes after final diff/test review. Oracle transfer/build/deploy remains out of scope.
