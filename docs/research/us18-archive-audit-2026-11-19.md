# Archived US-18 Stage 3 audit — 2026-11-19

## Decision

US-18 is a promising archived near-miss, not an approved US stock/ETF strategy and not proof that the user-set equity gates were met. The displayed Stage 3 point estimates look attractive, but their definitions, universe, execution assumption, and incomplete preserved artifacts prevent a valid pass. Two independent reviewers reached the same disposition.

## Candidate and preregistration

- Candidate: RSI(2) < 5 among the top quartile by 126-session momentum within a top-100 liquid-name universe; signal at close, buy that close, exit at first close above SMA(5) within five sessions or at close on day five.
- The Stage 3 preregistration freezes one candidate before the stated single holdout unlock. The holdout starts 2024-11-12. The candidate was selected from a 54-cell Stage 2 grid after a cumulative 99 development trials; that is not itself holdout leakage, but makes preservation of the single holdout look essential.
- The archived data addendum says the panel uses 503 *current* S&P 500 constituents and explicitly acknowledges that removed/delisted companies are absent. “Point-in-time top-100” ranks the available survivors; it does not repair the survivorship-biased source universe.

## What the archive reports

`results/US-18/stage3.json` reports 410 holdout event rows, of which the N=10 portfolio accepts 332; its N=10 statistics are `ann=0.259316`, `maxdd=-0.128229`, and `sharpe=2.01016`. The event-level mean is 1.984% and the recorded 2×-cost mean is 1.581%. These are archived outputs, not rerun results.

The user's pass criteria are net portfolio CAGR ≥20%, MDD ≤30%, Sharpe ≥1.0, and at least 200 closed OOS round trips. The archive does **not** establish a CAGR: `lib/portfolio.py` defines `ann` as arithmetic mean daily return ×252. It defines drawdown from the cumulative sum of daily returns, not a compounded equity curve. Therefore `ann=25.93%` and `maxdd=−12.82%` cannot be substituted for the user's CAGR and compounded-equity MDD. The 332 accepted events exceed the numeric sample floor, but do not remedy the missing comparable return metrics.

The salvage manifest states that per-trade parquet exports were not copied. The archived Stage 3 JSON also omits the daily portfolio series. Consequently, the archived values cannot be independently converted into the user's requested compounded CAGR/MDD from this checkout.

## Robustness and execution failures

- `survivorship.json` reports holdout Sharpe 0.810 for a frozen-2014 universe, below the user's ≥1.0 gate. A frozen-2024 universe reports 1.105, but the archive does not remove the source panel's explicit survivor limitation.
- The same-close execution assumes the close-derived signal can be filled at that same close. A separate next-open sensitivity reports a positive holdout but a negative DEV mean at 2× costs (−0.019%); it is a post-unlock diagnostic, not a fresh independent OOS validation.
- The Stage 3 prereg's `PASS=true` covers its own six criteria (including Sharpe, random baseline, cost sensitivity and event count); it does not assert the user's CAGR criterion. Later robustness and universe comparisons reuse the opened holdout and must not be represented as fresh blind tests.
- The recorded top five names account for about 34.7% of event P&L, and the holdout is disproportionately strong in recent high-momentum symbols. This is a concentration/regime warning, not a standalone reason to reject.

## Reconciliation outcome and next admissible step

The current cross-market inventory's “no qualifying strategy” conclusion remains correct, but it now records US-18 as the strongest historical near-miss. Do not rerun or retune on the opened 2024-11-12 onward holdout. Any further US-18 work must first use an authorized, reproducible, point-in-time universe including delisted constituents and corporate actions; freeze a feasible next-bar execution rule; retain trade-level and daily equity outputs; and evaluate CAGR and compounded MDD on a genuinely fresh chronological OOS period. If those inputs cannot be obtained, keep US-18 explicitly unverified rather than calling it a winner.

## Evidence files

- `docs/archive/salvage_2026-11-15/linuxserver_research/linuxserver_research/stock_loop/spec/US-18/stage3_prereg.md`
- `docs/archive/salvage_2026-11-15/linuxserver_research/linuxserver_research/stock_loop/results/US-18/stage3.json`
- `docs/archive/salvage_2026-11-15/linuxserver_research/linuxserver_research/stock_loop/results/US-18/robustness.json`
- `docs/archive/salvage_2026-11-15/linuxserver_research/linuxserver_research/stock_loop/results/US-18/survivorship.json`
- `docs/archive/salvage_2026-11-15/linuxserver_research/linuxserver_research/stock_loop/us/stage3_us18.py`
- `docs/archive/salvage_2026-11-15/linuxserver_research/linuxserver_research/stock_loop/lib/portfolio.py`
- `docs/archive/salvage_2026-11-15/linuxserver_research/MANIFEST_forward.md`
