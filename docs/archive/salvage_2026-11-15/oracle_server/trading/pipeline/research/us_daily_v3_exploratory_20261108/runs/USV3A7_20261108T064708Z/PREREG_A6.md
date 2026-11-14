# Addendum A6: RSI calendar gaps and transaction-cost funding
Registered 2026-11-08 KST before any US v3 performance metric is calculated. A6 supersedes conflicting RSI missing-bar and full-investment cost wording in earlier addenda. No market strategy results have been calculated.

## RSI2 missing-bar handling
Compute Wilder RSI(2) on the calendar-aligned total-return adjusted close series without dropping/compressing missing rows. A candidate additionally requires valid closes on t, t-1 and t-2, so the two daily price changes used by RSI(2) are consecutive valid sessions. Invalid bars cannot create a signal or fill. This prevents a missing session from being treated as if adjacent valid prices were one session apart.

## Cost reserve on target-weight orders
The monthly target engine stores per-symbol deltas and charges actual turnover. For a positive target weight w derived from close-time reference NAV, the dollar target is w × reference NAV / (1 + per-side cost), reserving the buy-side fee from cash. A full 100% SPY target or 20 × 5% targets therefore remains affordable and completes without negative cash or repeated orders. Sells, buys and fees are posted as separate actual notional changes. If cash is still insufficient because prices or other pending fills changed, only that symbol's residual order remains pending. Completed symbols are not replayed while another symbol is blocked. This fee-reserve adjustment is part of the frozen executable target semantics.

The gap strategy remains a share/cash/NAV ledger with entry at signal-day close and exit at first valid close after one complete close-to-close interval; fees are charged on actual entry and exit notionals. Its signal threshold uses raw split-adjusted open/close. Indicators and NAV use the vendor total-return adjusted OHLC. Liquidity uses raw split-adjusted close × raw volume.

## Synthetic mechanics checks
Before the market backtest, run deterministic assertions for: one deferred symbol completing once while another is already filled; 10bp fee and turnover arithmetic; a 100% SPY target completing with fee reserve; a fully allocated 20 × 5% target completing with fee reserve; RSI invalid-open deferral and next-open exit; and gap exit deferral across an invalid close with no fictional fee/fill. These are engine checks only and carry no strategy return evidence.

## Freeze and output contract
The study remains 2012-06-01 through 2026-08-18, limited to the last PIT membership snapshot. It reports all 3 rule families × 3 liquidity Top-N universes × 4 per-side costs, all base-cost cells, benchmarks, fill/cost/turnover/exposure/pending state, IS/reused-OOS/full results and descriptive regime slices, plus daily returns/exposure. No strategy is promoted from this contaminated exploratory sample. Final script/input hashes are in INPUT_HASHES_PRECALC_A6.txt; runtime verification must pass before any market calculation. No v3 market metrics have been run.
