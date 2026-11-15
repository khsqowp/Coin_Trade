# Current candidate disposition — 2026-11-15

Status: synthesis of existing local research artifacts and four bounded agent reviews. No new market-data query, backtest, strategy grid, or performance claim was generated for this note. The agent reviews were asked for independent disposition rather than more candidate permutations; their workspace access was incomplete, so the figures below are taken from the local source reports and independently checked here, not treated as four independent reproductions.

## Decision in one line

**There is no validated candidate to advance in KR, US, or crypto.** Stop re-running the exposed historical cache. The next work is a single market-data eligibility gate for equities and a fully frozen, prospective target-first signal ledger for crypto. Neither 20% equity CAGR nor 80% crypto precision is currently supported.

## Candidate ledger

| Market | Strongest existing lead | What the local result actually says | Disposition |
|---|---|---|---|
| Korea stocks/ETFs | Current-cohort 60-session monthly top-10 momentum; single-ETF 069500 compression breakout was also tested | Momentum reported 16.71% base CAGR with 50.88% MDD; the 200-session cash gate left CAGR 16.70% and MDD 47.05%. The fixed 069500 compression rule had only 50 completed trades; paired CAGR-difference interval crossed zero and stress CAGR was negative. A separate failed-breakdown study had −0.315% mean net return at base cost and a 95% block interval of −0.625% to −0.011%. | **DATA-GATE.** Do not test another KR rule on this cache. Current symbols are not a point-in-time active/inactive universe; adjustment, distributions, delistings, and rights are not sufficiently established. The risk target is also undefined. |
| US stocks/ETFs | Monthly 12–1 cross-sectional top-quintile momentum | The corrected 22-month diagnostic showed +3.036 percentage points/month vs the eligible-stock cohort and +3.847 points/month vs SPY, but it was post-hoc on a previously viewed period and had an incomplete October boundary. The older daily 126-session top-10 momentum replay showed 22.42% base CAGR / 34.17% MDD, but fell to 2.99% CAGR / 47.98% MDD under stress cost. Downside-beta rotation reduced drawdown but returned only 3.21% base CAGR. | **DATA-GATE.** Monthly 12–1 is the strongest lead, not a selected winner. Require licensed point-in-time active/inactive stock+ETF history, delisting outcomes, corporate actions and ETF distributions/total-return semantics before one preregistered forward evaluation. Define portfolio sizing and maximum drawdown first. |
| Crypto USDT perpetuals | No surviving existing candidate. The L2 liquidity-resilience idea is a new, untested hypothesis only. | The MTF replay's best of 36 post-hoc cells was 35.20% target-first (201/571) with mean net R +0.134 before missing spread/slippage/depth/funding, on exposed development data. The fixed BTC-4h / coin-5m sweep→MSS result was 13.38% target-first, 1.7688% signal coverage, and mean net R −0.294 with fee-only cost. The 1m candle-streak result was 47.67% target-first and −0.1444% mean net return; same-anchor always-long was slightly better on both reported metrics. | **REJECT existing candidates; DATA-GATE the new L2 question.** No post-hoc best cell or altered Pine version should be promoted. No 80% evidence exists. |

## Why the Pine script does not rescue sweep/MSS

The supplied Pine v6 script is not a separate evidence-backed strategy. Its `higherTimeframe` input sets a rolling chart-bar lookback rather than defining a confirmed higher-timeframe directional regime; sweep and MSS may be evaluated on the same bar; a signal confirmed at bar close is displayed as if filled at an intrabar MSS level; entry-bar OHLC can be scored before the entry; same-bar TP/SL is resolved optimistically in favor of TP; the state has no setup/trade timeout; and the fixed 0.3% TP / 0.4% SL is a 0.75 reward-risk ratio, not the separately configured 0.9. It also exposes settings that do not consistently affect execution. These are semantic and execution defects, not parameters to optimize.

The existing fixed BTC-4h / coin-5m sweep→MSS rule already tested the closest causally repaired form on exposed history and failed. Therefore the supplied script should remain **visual reference only** unless a genuinely different hypothesis is identified. Rewriting its timing defects alone would make it testable, not make it novel or profitable.

## Agent deliberation and evidence quality

Four agents were assigned disjoint tasks: KR evidence disposition, US evidence disposition, crypto historical-result disposition, and static Pine implementation audit. All returned a stop-on-grid-search/data-gate conclusion. Most could not read the active checkout in their isolated execution environment and explicitly relied on the supplied dossier; their opinions are not counted as independent numeric verification. The numeric claims above were checked against the corresponding local reports (`equity_kr_compression_breakout_results_20261115.md`, `equity_kr_failed_breakdown_results_20261115.md`, `equity_forward_validation_protocol_20261115.md`, `equity_us_downside_beta_results_20261115.md`, `round5_mtf_dev_results_20261115.md`, `crypto_macro_mtf_sweep_results_20261115.md`, `crypto_round11_streak_results_20261115.json`, and `crypto_pine_macro_to_micro_audit_20261115.md`).

## Next work with decision value

1. **Equities:** no new performance test until a named, licensed source can meet point-in-time universe, inactive/delisted security, corporate-action, distribution/total-return, historical-vintage, and use-rights requirements. If a source cannot meet these, stop equity strategy research on this dataset; do not substitute another current-survivor universe.
2. **Crypto:** do not collect outcome-labeled signals yet. First freeze the forward ledger contract: macro and micro candle close timestamps, signal availability, order-submission/fill model, stop/target/expiry, stop-first ties, cost and funding schedule, abstention/coverage denominator, non-overlap selection, model-fit/calibration/threshold/final chronological splits, purge/embargo, and symbol/day clustered uncertainty. The primary 80% gate must state whether it refers to point precision or a cluster-aware lower confidence bound; the latter is the more defensible claim.
3. **Only after the contract is frozen:** run a bounded L2 collector integrity pilot if (and only if) its numeric sequence-gap, reconnect/restart recovery, timestamp, coverage, disk-rate, and data-loss criteria change the decision to begin a longer prospective capture. The pilot is not a strategy test. If it fails, repair or stop; if it passes, freeze a development period and then a separate future evaluation. Do not tune against the future evaluation.

## Explicitly not done

- No profitability was established for any market.
- No new parameter search or backtest was run for this synthesis.
- No Pine code was ported or executed.
- No L2 prospective data was collected.
- No Oracle action, paid data purchase, exchange credential use, or order routing occurred.

The objective remains active. A future positive result must come from a separately frozen, causal, cost-aware evaluation with the required sample, coverage, and uncertainty—not from another table of best cells.
