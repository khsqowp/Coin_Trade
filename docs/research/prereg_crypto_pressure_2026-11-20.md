# Preregistration: 3-minute volume-weighted candle-pressure cross-sectional momentum

- Trial: `crypto_pressure_20261120_01`
- Status: rules fixed before evaluating this feature's development outcomes.
- Objective: maximize after-cost compounded wealth. M2, coverage, sample, and data-integrity thresholds are independent gates, not substitutes for wealth growth.
- This is one candidate and one fixed parameterization. No parameter grid or post-result tuning is allowed in this trial.

## Hypothesis and distinction from prior work

Hypothesis: among a fixed 20-symbol USDT perpetual cohort, the cross-section of the last three completed 1-minute candles' quote-volume-weighted close-location score contains short-horizon directional persistence. The two highest-scoring symbols are long candidates and the two lowest-scoring symbols are short candidates. This tests a short-horizon candle-location proxy, not actual aggressor-side order flow: quote volume is not buyer-initiated or seller-initiated volume.

The signal differs from the previously rejected 60-minute ranking of 24-hour relative returns (cross-sectional mean reversion), and from earlier VWAP fade, price-breakout, and candle-pattern-plus-indicator trials. It is not evidence of a new edge until measured. No derivatives, order-book, liquidation, open-interest, or funding input is used.

## Data and split

- Source: read-only `candles.sqlite` table, fields `symbol,t_open_ms,o,h,l,c,quote_v`; first 20 symbols from the fixed `universe_collect.json` list, in list order.
- The current universe snapshot was collected in November 2026 and is applied retrospectively. Survivorship and selection bias remain. This dataset has only the July–October 2026 development period for the present rule and cannot establish multi-regime performance.
- Development signal anchors: 2026-07-17 00:00 UTC inclusive through 2026-10-08 23:51 UTC; 2026-10-09 00:00 UTC is the exclusive execution-data boundary, with an 8-minute purge.
- The runner queries only rows with `t_open_ms < 2026-10-09 00:00 UTC`. It never opens the previously designated 2026-10-09 onward validation interval. Because the same source dates were inspected in other strategy research, this is a development screen, not an untouched sealed test.
- All 20 symbols must have synchronized, contiguous, valid 1-minute bars over the queried span. Missing/invalid paths fail closed; no interpolation or gap stitching is allowed.
- The source database is not modified. Record exact selected-row SHA-256, code SHA-256, source file size and mtime.

## Frozen signal, fills, barriers, and costs

For each completed minute bar `j`, define close location as `(2*c_j-h_j-l_j)/(h_j-l_j)`; a zero-range bar contributes zero. At each minute close, compute the quote-volume-weighted mean of this quantity across the last three completed bars:

`P = sum(quote_v_j * close_location_j, j=t-2..t) / sum(quote_v_j, j=t-2..t)`.

If any of the 20 scores is missing/non-finite, emit no cross-sectional signal at that anchor. Otherwise rank ascending by `(P, symbol)`, long the top two scores (ties resolved by reverse lexical rank after ascending sort), and short the bottom two (ties by ascending symbol). The signal uses only completed bars through anchor `t`; entry is at the next 1-minute bar open. Existing positions in the same symbol are not duplicated in the portfolio, though signal outcomes remain in the signal-level score.

- Target: `+0.45%` from actual modeled entry price for long, `-0.45%` for short.
- Invalidation/stop: `-0.20%` for long, `+0.20%` for short.
- Vertical barrier: close after eight completed 1-minute bars if neither price barrier is reached.
- Examine the entry bar after entry and then the next seven bars. Stop has priority when both barriers occur within one OHLC bar. A stop gap exits at the adverse observed open; favorable target gaps are conservatively filled at the target. Timeout exits at the eighth bar close. Any missing bar in the eight-bar path is `unscorable`, not a timeout.
- Per side: 0.05% taker fee plus 0.04% slippage; both entry and exit costs apply. Stress: same fee plus 0.08% slippage per side. No funding or market-impact estimate is available, so reported performance omits those costs and must not be represented as live-realistic.
- Approximate barrier-level net returns under base assumptions are +0.27% at target and -0.38% at stop. An 80% M2 hit rate is therefore not itself sufficient; timeouts, actual average net expectancy and compounded portfolio wealth are independently measured.
- Portfolio: initial NAV 1.0, at most eight open positions, at most four per side, no duplicate symbol, each new position targets 1/8 of entry NAV, and total gross exposure is capped at 1.0x NAV. Fees reduce NAV. Open PnL is marked to every minute close. No leverage/liquidation model or funding is implied.

## Comparators, metrics, and decision

Comparators use the same interval, entry/exit accounting, risk cap, and costs: (1) reverse the selected sides, (2) deterministic random two-long/two-short selection at each valid anchor with seed `20261120`, (3) 100% cash, and (4) BTC buy-and-hold after modeled round-trip costs. All comparators are descriptive; the objective comparison is after-cost compounded final NAV, with drawdown and time distribution shown.

Report: all-issued and per-symbol non-overlap target-first M2; Wilson 95% intervals (descriptive because symbols/times are clustered); M1 direction at timeout separately; eligible-anchor coverage; scorable fraction; per-symbol/side results; signal net expectancy; portfolio final NAV, total compounded return, development-only CAGR, minute-marked MDD, hourly Sharpe, profit factor, turnover/position count, and monthly NAV; base and 2x-slippage stress; plus a one-minute extra-entry-delay diagnostic.

Continue to a separately preregistered validation only if all development gates hold: non-overlap N >= 200, M2 point estimate >= 80%, actionable coverage >= 10%, complete-path scoring, positive after-cost signal expectancy at base and stress assumptions, and base/stress compounded final NAV above cash, BTC hold, reverse and random controls. Failure of any gate rejects this candidate; no parameter adjustment is permitted under this trial ID. Even passing does not establish a universal or live edge: point-in-time membership, multi-regime historical data, funding, fills, and a genuinely untouched sealed/forward OOS are still required before approval.

## Causal and implementation checks

- Prefix invariance: appending future bars cannot change any earlier pressure score or signal.
- Entry timestamp is the first bar open after the signal's final completed bar.
- Stop-first same-bar ties, adverse stop gaps, timeout, missing-bar unscorable cases, deterministic tie-breaking, and read-only DB mode have unit tests.
- Compare base with 2x slippage and a one-minute later entry; preserve all attempted trial records and do not inspect the designated validation window.
