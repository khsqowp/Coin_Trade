# Generation 11 — volatility-expansion / positive-momentum event (US SPY)

Frozen: 2026-11-06 Asia/Seoul, before performance calculations. One rule, one instrument, one holding horizon, no parameter sweep.

## Source and non-duplication

The signal is source-derived from `trading/app/new_strategy_screening.py::volatility_breakout` (source file SHA-256 `27cfd55ff2d6158e6b3002be1652a5279f53371e7c5b517fb3ca99ccf0efdb8f`). The source defines `ATR(20)/Close`, a volatility burst when that ratio exceeds the preceding 100-observation rolling 80th percentile, and positive five-session close momentum for the long direction. Its source universe/execution is crypto screening, not an equity portfolio, so this is an explicitly specified SPY-only transfer hypothesis; no crypto code or costs are reused.

This is not the generation-10 NR7 rule: there is no narrow-range ranking or prior-day high breakout. It is also not the generation-3 compression-release breakout: there is no range compression, 55-session price breakout, or trailing channel exit. It remains adjacent to volatility-expansion and momentum families and prior historical research; this is not an independent-family claim.

## Fixed signal and execution

- Instrument: local SPY daily OHLCV series only; long-only, 100% of available equity while a position is held, otherwise cash at 0%. No leverage, shorting, fractional exposure scaling, or concurrent positions.
- Technical features use consistently adjusted OHLC: multiply each raw OHLC field by `adjclose/close` for that session. This reduces dividend/split discontinuities in the indicator; the vendor adjustment convention is not independently verified.
- At close of observed session `t`, calculate true range as `max(H_t-L_t, abs(H_t-C_(t-1)), abs(L_t-C_(t-1)))`, using skip-missing maximum semantics so the first observed true range is `H_0-L_0` (matching `strategy_screen_core.atr`). ATR20 is the simple mean of current and preceding 19 observed-session true ranges. Let `v_t=ATR20_t/C_t`.
- Define the threshold as the linear-interpolated 80th percentile of the 100 prior observed `v` values `v_(t-100)..v_(t-1)`; the current `v_t` is excluded. Signal long if `v_t` is strictly greater than that threshold and adjusted close `C_t/C_(t-5)-1` is strictly positive. This is evaluated once at each observed close after all required values are finite and positive.
- Enter at the next observed session's adjusted open. Hold for exactly five open-to-open return intervals, then liquidate at the sixth observed session's open after the signal close (entry open is `t+1`; exit open is `t+6`). No stop or profit target.
- At most one position. A signal at close `t` is suppressed when `t` is earlier than the scheduled exit-open date index `t+6`; the close at index `t+6` occurs after that morning's liquidation and is eligible to schedule a new entry for the following open. Incomplete end-of-file trades are censored and not entered.
- Charge 10 basis points on entry and 10 basis points on exit, applied multiplicatively at the respective execution events. Benchmark: SPY adjusted-open buy-and-hold over the same curve dates, with 10bp entry and terminal liquidation costs.
- Report full sample, 2001-01-02 through 2016-12-30, and 2017-01-03 through last available date. These are descriptive slices only; all source-history is contaminated by previous inspection. Each window's drawdown is recomputed from a fresh within-window baseline. No OOS, statistical-significance, or investability claim.

## Data / stop gates

The only permitted market input is `../data_mirror/us_daily/SPY.parquet`. Before metrics, require unique strictly increasing dates; finite positive raw OHLC and adjusted close; valid raw and adjusted OHLC ordering; adjusted-open validity; and finite feature/return values whenever used. Any integrity failure fails the attempt before reporting performance. The local snapshot has 8,498 rows from 1993-01-29 through 2026-11-02 according to metadata; exchange-calendar and corporate-action provenance remain unverified.

## Accounting and interpretation

Daily returns are measured adjusted-open to adjusted-open. Entry cost is charged in the first invested interval; exit cost is charged in the final invested interval ending at the scheduled exit open. Cash intervals earn zero. The benchmark starts and ends on the strategy's common curve interval. Metrics are descriptive: CAGR, annualized Sharpe (252), maximum drawdown, exposure, completed trades, suppressed signals, and censored terminal signals. The global historical trial count remains unresolved and no DSR/PSR/BH significance gate can be asserted. A negative or mixed result rejects only this fixed transfer on this snapshot; it is not evidence that profitable automated strategies do not exist.

## Frozen artifact hashes

This document's hash and the finalized runner/test/data hashes must be written to an immutable `FREEZE.json` before the single performance run. The attempt ledger and manifest must persist a `STARTED` record before loading performance values and must persist `FAILED` on every exception or gate rejection. Tests were written before implementation; independent review is required before any performance calculation. No reruns or post-result variants are permitted in this generation.
