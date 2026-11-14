# Generation 11 — SPY overnight-only exposure

## Frozen hypothesis and scope

Test one signal-free, fixed-schedule hypothesis: a liquid broad-market ETF may earn a different risk-adjusted return when held only from each session's closing auction to the next session's opening auction, compared with holding the same ETF continuously. This is a single-asset overnight-versus-buy-and-hold comparison, not a cross-sectional stock-selection strategy and not evidence that every overnight interval is predictable.

## Orders and information timing

- Instrument: SPY only; long-only, unlevered, 100% allocation while overnight; 0% allocation during each regular-session daytime interval.
- The schedule is fixed in advance and has no price-triggered signal. Submit a market-on-close (MOC) buy before that session's auction cutoff; submit a market-on-open (MOO) sell before the next session's opening-auction cutoff. Do not use the closing auction price to decide that same auction's order. The strategy does not claim to know or control auction fills; daily OHLC cannot reconstruct queue position, auction imbalance, partial fills, or realized slippage.
- Initial entry is at the first observed session's close; final liquidation is at the last observed session's open. For each complete observed overnight interval, the strategy's gross factor is `adjusted_open[t] / adjusted_close[t-1]`, where `adjusted_open = raw_open * adjclose / raw_close` and `adjusted_close = adjclose`. Thus the scored interval begins at the previous close and ends at the current open. No intraday return is earned.
- Apply a fixed 2 bp cost per executed side (one MOC side and one MOO side per overnight round trip), multiplicatively at the actual boundaries. The benchmark buys SPY at the same initial close, holds through the exact same final open, and pays 2 bp on initial entry and final exit only. No extra sensitivity grid is allowed. This is a declared cost assumption, not a claim that local data measures actual auction slippage.
- Benchmark: continuous long-only SPY buy-and-hold over the identical start/end instants. Its close-to-close intervals are used through the penultimate session, then its last interval ends at the final session's open, matching the strategy's endpoint.

## Data and corporate actions

- Input: local `data_mirror/us_daily/SPY.parquet`; source metadata says Yahoo chart v8 unofficial feed. Use the observed SPY date index only; this is not independently reconciled to an authoritative exchange calendar.
- Compute total-return-consistent adjusted open from same-row raw OHLC and `adjclose`; use `adjclose` for close. The adjustment is a vendor-derived retrospective series. The local `SPY.events.json` may be inventoried for documented dividend/split events, but cannot independently establish event completeness, historical correction status, or auction execution prices. Fail closed for missing/non-finite/non-positive values, duplicate/nonascending dates, invalid OHLC bounds, or invalid adjusted-open/close ratios. Do not repair or forward-fill.
- For dividend ex-dates the adjusted close-to-open ratio is intended to include the distribution component consistently with the vendor's adjusted-close convention. Because the feed's event coverage and adjustment implementation are not independently verified, report this as an exploratory vendor-adjusted estimate only. Do not run if the event/adjustment checks expose an unresolved arithmetic or schema inconsistency.

## Evaluation and decision rule

- One candidate, one run, no rule variants and no post-result changes. Report full-history descriptive CAGR, annualized Sharpe, maximum drawdown, cumulative return, observation count, exposure fraction and turnover, alongside matched-window SPY buy-and-hold. Fixed descriptive partitions: full history, 2001-01-01 through 2016-12-31, and 2017-01-01 onward. The latter and the full SPY history have already been inspected in prior generations; none is untouched OOS.
- Annualization uses 252 observed sessions. Daily risk statistics use the scored close-to-open intervals for the strategy and the endpoint-matched daily total-return intervals for the benchmark. State clearly that differences in interval composition make this a descriptive timing comparison, not a same-risk portfolio comparison.
- Reject this fixed schedule for the stated search objective if its net CAGR and Sharpe do not both exceed matched SPY buy-and-hold in every reported window. Any descriptive pass remains only a lead pending independent licensed corporate-action/auction data, a genuinely untouched prospective holdout, and cumulative trial-count reconciliation. No DSR/PSR or multiplicity-adjusted significance claim is planned.
- Generation gate: unit tests first; freeze preregistration hash; independent reviewer GO; then exactly one read of SPY performance data and one run. Every setup/test/review/data gate/run failure must be written to a persistent JSONL ledger. No live, paper, or remote service access; no commit or push.

## Prior-work overlap audit

- Gen01 includes a five-session gap-reversal candidate; that conditions on an adverse gap and subsequent same-session recovery, unlike the fixed overnight-only exposure here.
- Gen03 includes DCTC_GAP_INTRADAY63, which requires both overnight and intraday trend statistics and changes monthly exposure; it is related to overnight/intraday decomposition but is not this fixed overnight-only schedule.
- Gen07 tests cross-sectional abnormal frequencies of positive overnight returns followed by negative daytime returns; this is related overnight/daytime literature, but uses stock-level event frequencies and next-month selection.
- Gen09 tests first-three-sessions-of-month SPY exposure and Gen10 tests an NR7 breakout; neither is this overnight-only interval schedule.
- This is therefore a distinct execution/exposure definition within an already explored overnight-return research family, not an independent discovery. Prior exposure to the same SPY history is material.

## Hash freeze

This file must be SHA-256 hashed after creation and recorded in `FREEZE.md` before any market-performance inspection. Any subsequent change invalidates the preregistration and requires a dated addendum plus a new candidate/run identifier.
