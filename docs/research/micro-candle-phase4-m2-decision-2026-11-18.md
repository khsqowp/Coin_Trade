# Micro-candle phase 4 — decision

**Decision: REJECT the fixed one-minute close-location signal as a target-first candidate.** The screen directly misses the user-fixed 80% M2 target, has negative cost-adjusted expectancy, and does not beat same-anchor momentum. No thresholds were tuned after outcomes.

## Result

Frozen rule: completed 1m candle closes in upper/lower 20% of its range; enter next 1m open; stop and target each 1 ATR(14); stop-first OHLC tie; 10m and 20m deadlines assessed separately; base round-trip cost 14 bp and stress 28 bp. The 86-symbol historical Vision archive is already exposed and is not sealed confirmation.

| Horizon | All emitted / resolved | M2 target-first | Deadline direction | Momentum baseline | SHA random baseline | Mean net R (14 / 28 bp) | Non-overlap N / symbols |
|---|---:|---:|---:|---:|---:|---:|---:|
| 10m | 75,349,453 / 75,349,399 | 47.977% | 46.832% | 48.059% | 47.793% | -1.489 / -2.968 | 11,788,232 / 78 |
| 20m | 75,347,346 / 75,347,237 | 49.379% | 47.579% | 49.460% | 49.187% | -1.490 / -2.968 | 6,096,106 / 78 |

Both claims clear the minimum non-overlap count and symbol-dispersion gate, path resolution exceeds 99.999%, and signal coverage is 50.586–57.698% across the five chronological test windows. Those eligibility results do not offset the large M2, net expectancy, and momentum-baseline failures. Each of the five test windows stays near 46.8–48.7% for 10m and 48.4–49.9% for 20m; none approaches 80%.

## Audit and limits

- Input was opened SQLite read-only; source fingerprint is `bb64efa272bab6c5bed258ec7284f9212165c8912cfcd824f51863ae5d88fafa`.
- Entry and outcome windows were constrained to finish inside each fixed test window. Missing first-entry or later path minutes remain unresolved rather than being silently removed. Same-minute target/stop ties resolve as stop-first.
- Eight focused tests passed, including long/short stop-gap fills and same-bar stop-first behavior. An independent scalar replay recalculated ATR, barrier order, and cost-adjusted net R for 100 sampled BTCUSDT paths (45 long, 55 short); target/timeout labels agreed and maximum absolute net-R discrepancy was 0.
- Funding was not modeled: this candle table does not contain settlement-rate history. The 14/28 bp values are assumed round-trip fee-plus-slippage costs, not fills observed from an exchange order book.
- The five test windows are fixed chronological evaluations of a rule with no fitted parameters. This is not a full parameter-selection walk-forward; no train-window selection was needed or performed.
- The large all-issued counts are overlapping and dependent, not independent sample sizes. This exploratory rejection does not claim a statistical significance level or generalization to an unobserved live period.
- Since the frozen primary result is far below M2 80%, below both baselines (except a negligible +0.18–0.19 percentage-point difference versus SHA random), and materially negative after costs, the candidate is rejected before the 1,000 trade-order Monte Carlo and parameter-plateau stage. Those tests cannot convert a failed primary candidate into a pass; running a parameter grid now would invite post-hoc rescue.
- This result does not establish that all one-candle or two-candle structures fail. Three earlier 2/3-bar screens had only 1.059%, 1.511%, and 3.352% issue coverage and were stopped before labels. Do not repeat those rules or optimize their thresholds on this exposed archive.

## Next bounded step

Do not widen into macro/context features. First audit prior-art for untested single-candle anatomy and verify the affected code/data provenance. If a genuinely distinct definition remains, register one bounded two-candle morphology family and run only label-blind coverage and symbol-dispersion screening first. Open outcomes only for candidates meeting frozen coverage eligibility; use a future append-only stream for any confirmatory claim. The current KR sample supports one-ETF candle descriptions but lacks official/action-adjusted provenance and OOS sample capacity; the current US research worktree has no SPY cache, and its separate cache record has OHLC defects and incomplete provenance. Neither market presently supports a defensible strategy-return conclusion.
