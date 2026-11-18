# Four-agent research review synthesis — 2026-11-19

## Scope and checkout identity

- Research checkout: `/private/tmp/cointrade-round5-ready`, branch `research/round5-readiness-20261115`, HEAD `aa0313b` at review time.
- Primary local checkout: `/Users/user/CODE/Coin_Trade`, branch `main`, HEAD `b8b03f5` at review time.
- The current Codex workspace path `/Users/user/Desktop/CODE/trading_bot` is empty and is not a Git checkout. Results in this document describe the temporary research branch, not files already present on main. The two checkouts must not be represented as identical.
- Four independent read-only agent reviews completed: Korea equities, US equities, crypto micro-first, and cross-market/red-team implementation audit. Their tasks prohibited new raw-price reads, new backtests, edits, and external network use.

## Frozen evaluation goals

- KR/US: cash stocks and ETFs only; net CAGR ≥20%, MDD ≤30%, annualized Sharpe ≥1, and ≥200 closed OOS round trips per market.
- Crypto manual long/short research: all-issued target-first M2 ≥80%; separately establish outcome-blind non-overlapping N≥200 across ≥20 symbols. Report deadline-direction accuracy separately. No agent places orders.
- Required strategy robustness, only after a strategy clears its primary research/data gates: 1,000 trade-order Monte Carlo, 5×(504-day train/252-day test) walk-forward, and a preregistered adjacent-parameter plateau. A random-entry baseline is not the required Monte Carlo.

## Korea stocks and ETFs — agent verdict

No saved KR research establishes that the frozen portfolio gates passed. The archived stock loop evaluated KR-01–36, with no Stage 2 survivor; prior random-entry diagnostics do not equal the required Monte Carlo, and the required five-window walk-forward was not run.

The agent proposed one untested, falsifiable daily-data hypothesis for future registration: weekly rotation among non-leveraged/non-inverse Korean equity ETFs, ranking 126-session total return, requiring positive 126-session return and close above the 200-session moving average, holding the top two equally weighted, entering next-session open, and rebalancing/exiting at the next week-end close. This is a proposal, not a result or approved candidate.

Do not test until the date-specific ETF universe, listing/delisting/trading-halt history, distribution-reinvested total-return data, ETF-specific taxes/fees, slippage assumptions, initial capital, lot/tick rounding, and benchmark are documented and frozen. The current stock-loop KR universe is current-member/survivor-biased and excludes ETF/ETN categories from its main universe.

## US stocks and ETFs — agent verdict

No saved US candidate satisfies the frozen gates. US-01–52 and ETF/VIX/event probes are exploratory, not qualifying OOS portfolio evidence. R036 and R037 did not pass source-rights/data-quality gates. Required Monte Carlo, the full five-window walk-forward, and plateau evidence were not found.

The agent proposed (not tested) a monthly 12–1 momentum portfolio: at month-end rank point-in-time US common stocks by 126-session total return excluding the most recent 21 sessions, equal-weight the top decile, enter next-session open, and exit at the next month-end rebalance if no longer selected. ETF/ADR/preferred/leveraged securities are excluded from the first specification. This remains a proposal pending duplicate review against US-01–52.

No performance run is authorized until source rights, stable security IDs, point-in-time membership, delisted/merged names and proceeds, splits/corporate actions, dividend total returns, costs/slippage, benchmark, and risk-free-rate convention are fixed. Current-member survivor caches cannot support the required historical universe claim.

## Crypto smallest-first review — agent verdict

There is no approved new OHLC-only micro-pattern candidate. The repository already covers next-candle direction baselines, one/two/three-bar screens, close-location, body dominance, sweep/reclaim, and scale repetitions through 15-minute bars. The fixed M2 cells either failed outcome-blind frequency or produced target-first rates near 46–49% with negative cost-adjusted expectancy; none passed the user's 80% gate. Existing broader P4 classifiers also do not establish M2. Adding more thresholds, mixing failed candle patterns, or moving to macro/HTF now would repeat the search without a new mechanism.

The reviewed local L2 captures are feasibility pilots, not adequate M2 samples: the 20-symbol capture is only 120 seconds; the one-hour captures cover BTC/ETH only. Neither can satisfy N≥200 across ≥20 symbols. The next in-scope crypto task is data-only: determine whether a legally usable, integrity-auditable event-level `trades` or `aggTrades` panel can be assembled; select exactly one format; verify rights, source/version/hash, timestamps, IDs/gaps, and reconciliation to minute aggregates before opening outcomes. This is not permission to download, collect new external data, or generate a live signal.

## Micro-magnitude diagnostic — red-team disposition

The one-step absolute-return persistence run's raw metrics are retained only as exploratory output. The runner interleaved per-symbol data-quality counters with outcome scoring, rather than persisting a complete outcome-blind preflight before scores. It also compared target `open_ms` against a preregistered target-close interval and did not query stored `close_ms`; exact boundary compliance is therefore unverified. The numerical output has not received an independent scalar/raw-database audit. JSON, report, and audit note now identify the run as invalid for preregistration-compliant inference.

No long historical rerun is initiated in this review. Before any later full-file scan, first generate and persist a quality/eligibility preflight, use `close_ms` for the preregistered endpoint semantics, pass synthetic boundary/chunk/gap tests, and show progress/cancellation status at bounded intervals. Since the historical outcomes were already exposed, any repeat on this same interval remains exploratory, not confirmation.

## Research disposition

1. Do not widen crypto into macro/HTF or invent another OHLC candle combination until a genuinely distinct micro hypothesis or eligible event-level dataset clears prior-art and data gates.
2. Do not start KR/US return backtests from current survivor caches. Pursue source-rights/PIT/universe/corporate-action and ETF total-return data gates first.
3. Keep the proposed KR and US rules labelled `unregistered proposal`; freeze the cohort, data source, costs, benchmark, portfolio sizing, and trial family before any score access.
4. No strategy is approved, no 80% crypto claim is established, no real order/paper broker action occurred, no Oracle deployment occurred, and no code/result from this temporary branch has been committed or pushed by this synthesis.

## Agent work records

- Korea: `Hooke`; read-only document/source review; no raw prices or runs.
- US: `Mencius`; read-only document/source review; no raw prices or runs.
- Crypto micro-first: `Harvey`; read-only document/source review; no raw prices or runs.
- Cross-market red team: `Erdos`; static code/prereg/report review; no raw-price recomputation or run.
