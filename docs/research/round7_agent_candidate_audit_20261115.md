# Round 7 agent candidate screens: evidence audit

Date: 2026-11-15. Four independent agents were assigned two cash-equity and two crypto research roles. This note preserves their findings and explicitly separates reported outputs from reproducible evidence. No live orders, credentials, Oracle actions, or market-data writes were used.

## Evidence ledger

| Role | Candidate/result | Evidence status | Decision |
|---|---|---|---|
| KR equity agent | Positive-gap next-session intraday long on 069500; reported negative CAGR and event returns across its historical periods | Inline Python only; no saved script, raw rows, event ledger, input hash, or output file. Not independently rerun. | Treat as an unverified negative exploratory lead; do not use its exact metrics as validated facts. |
| US equity agent | 20-session high failure followed by a five-session short; initially reported mean −0.518% | **Withdrawn by the agent.** Code used `entry / exit - 1` as short return instead of `(entry - exit) / entry`; no corrected rerun or saved artifact exists. | All previously reported short P&L, confidence intervals, and conclusions are invalid and excluded. Signal counts/method description are not performance evidence. |
| Crypto agent A | 10-bar volume-climax rejection plus opposite-color completed 1h bar; 15-bar same-timeframe deadline | Summary stdout only; no source script, per-event ledger, raw output, or reproducible artifact. Large signal-to-trade count discrepancy remains unexplained. No future-mutation test or independent matched baseline. | Keep all hit rates and returns as tentative exploratory output only; not a passing signal. |
| Crypto agent B | Did not complete a new strategy simulation | Read-only data/source reconnaissance only. Confirmed the current 1m database has 100 symbols and OHLCV plus quote-volume/trade-count fields, but no event-level quote/depth execution history. | No strategy result. A no-output constraint blocked the old simulator; future local-only runs may write artifacts under `/private/tmp` while keeping source DB read-only. |

## Reported agent details — not promoted as independently verified results

The KR agent described a 069500-only rule that identifies a positive opening gap, confirms it by the session close, buys at the following session open, and exits that next session close. It reported 2,183 positive-gap sessions in 3,999 sessions and a deeply negative long-run account CAGR/MDD under its assumed costs. The code and portfolio accounting were not retained, so those values are a lead rather than a durable reproduced result. A separate, fully reproducible KR common-stock event study is documented in [`equity_kr_failed_breakdown_results_20261115.md`](equity_kr_failed_breakdown_results_20261115.md).

The US agent used a 20-session high breach followed by a close back below the prior high, entered at the next session open, and exited at the fifth session close. It later corrected itself: the saved-in-memory formula was wrong for a short. Its first performance table is not reproduced here and must not be quoted as evidence. Correcting the algebra alone cannot restore its results because the event-level inputs, saved script, output, and input manifest were not retained.

The crypto agent's reported table was:

| Signal timeframe | Reported non-overlapping events | Target-first point rate | Wilson 95% | Reported mean net/event |
|---:|---:|---:|---:|---:|
| 1m | 1,299 | 42.3% | 39.6–45.0% | −0.109% |
| 3m | 373 | 47.2% | 42.2–52.3% | −0.089% |
| 5m | 221 | 43.4% | 37.1–50.0% | −0.113% |
| 15m | 90 | 50.0% | 39.9–60.1% | −0.094% |
| 60m | 19 | 21.1% | 8.5–43.3% | −0.518% |

These are explicitly *reported but unverified*: the agent later said signal counts ranged from 1,013 to 66,859 after the hourly filter, while the scored trade counts were only 19 to 1,299. No raw event ledger exists to reconcile that selection. The underlying development period was `2026-07-17` through the exclusive `2026-10-09` cutoff on 50 selected symbols. It is not an untouched holdout. These numbers do not approach the 80% target and cannot support live/manual signal confidence.

## Data boundary confirmed locally

The current local `candles.sqlite` metadata was independently queried read-only: 100 symbols, 17,142,161 one-minute rows, earliest timestamp `2026-07-16 18:10 UTC`, latest `2026-11-14 00:28 UTC`. The database has OHLCV, quote volume, and trade count, but no synchronized historical bid/ask/depth tape. Repository research notes state that post-`2026-10-09` rows lack a sealed-access registry and access history; their mere presence cannot make them an untouched holdout. They must not be retroactively scored as sealed data.

## Next valid work

1. Use the reproducible KR failed-breakdown study as a negative development result; do not retune it on the same cache.
2. Any agent-produced candidate must save its frozen rule, exact command/source, input hash, event ledger or a deterministic event hash, and output before reporting metrics. Temporary outputs may live under `/private/tmp`; keep source databases read-only.
3. For crypto, require a reconciled event funnel, matched direction/flat baselines, actual eligible-anchor coverage, causal future-mutation tests, stop-first path scoring, and base/stress costs before interpreting a hit rate.
4. New independent evaluation requires genuinely prospective observations with the rule frozen first. Existing post-2026-10-09 rows do not qualify as sealed without historical access proof.

No agent result in this round validates a strategy, reaches 80% crypto target-first accuracy, or justifies a live/automated trading decision.
