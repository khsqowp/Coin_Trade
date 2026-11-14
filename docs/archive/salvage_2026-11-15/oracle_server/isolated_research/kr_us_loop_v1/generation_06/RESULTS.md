# Generation 06 — low-beta long-only results

Run: `GEN06-20261106T104009-21424`; local snapshot only. The matching manifest records the preregistration, runner, source and input hashes. The attempt ledger, daily curve and selection audit are retained.

## Outcomes

- **US:** completed. IS (2001-01-04 to 2016-12-30): strategy CAGR 10.48%, Sharpe 0.77, MDD -37.67%; SPY CAGR 5.22%, Sharpe 0.36, MDD -55.19%. Later inspected/contaminated partition (2017-01-04 to 2026-11-02): strategy CAGR 9.79%, Sharpe 0.69, MDD -32.75%; SPY CAGR 14.84%, Sharpe 0.86, MDD -33.72%. The strategy beat SPY in the IS partition but materially lagged in the later period. It does not meet the all-period / valid-OOS success condition.
- **KR:** failed the preregistered strict OHLC gate on 2020-07-01 for held ticker `099340` (invalid or missing OHLC). No KR strategy metrics are reported. This is a data-integrity stop, not a pass or alpha result.

## Audit checks

- Seven focused test functions passed by direct invocation under the configured Python environment; `compileall` passed. `pytest` is not installed in that environment, so pytest itself was not run.
- Independent code review found and resolved the KR leave-one-out proxy / paired-history issue before any market run. Review found no remaining blocking beta, causality or execution defect.
- Selection audit contains 18,550 selected US ticker-month records across 371 rebalance dates; every selected record has exactly 252 paired observations and 2% weight. The file hash is in the run manifest.
- The KR selected-name record was not produced because its execution failed before metrics/selection export.

## Interpretation boundary

This is a long-only low-beta adaptation, not a replication of the leveraged long-low-beta / short-high-beta BAB factor. It is adjacent to the previously tested low-total-volatility family and cannot be treated as independent evidence. The US PIT mirror contains local prices for only 688 of 1,209 membership names; corporate actions, delisting proceeds and the full historic trial count remain unresolved. The later partition was already inspected and is not untouched OOS. No global DSR/PSR/BH correction or confirmatory claim is supported. This candidate is not accepted as a valid strategy.
