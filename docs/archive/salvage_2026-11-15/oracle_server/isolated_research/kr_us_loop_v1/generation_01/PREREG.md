# Generation 01 — exploratory candidate screen (2026-11-06)

## Purpose and evidentiary status

This is a local, exploratory screen of newly specified daily-bar hypotheses. It is not a confirmatory performance test, investment recommendation, or permission to route orders. The local PIT mirrors are snapshots and have known unresolved universe, missing-symbol, corporate-action, and historical-trial-ledger discrepancies described in `../FEASIBILITY.md`. Results must be labeled exploratory. No historical result from this generation may be described as a proven or deployable edge.

The user explicitly authorized further local research and requested that every attempt, including failures, be recorded. Remote server writes/commands, live trading, and commits/pushes remain prohibited. This generation will read only `../data_mirror/` and save research outputs in this directory.

## Fixed execution contract

- Markets: KR and US, evaluated separately; no cross-market pooling.
- Signal decision: after close `t`; order simulation at open `t+1`.
- Portfolio: long-only, unlevered, equal weight among qualifying holdings, maximum 20 KR names and 50 US names; ties by ticker. No shorting.
- Rebalance: indicator/rank/overlay strategies evaluate entry and exit conditions only at the last available trading session of each calendar month. Positions are held until the next month-end decision; any month-end exit executes next open. They do not have intra-month signal exits. `GAP_REVERSAL_5D` is the single exception: it updates its event-slot book daily and exits at the next open after five held sessions.
- KR sample: KODEX 200 (`069500`) is absent from the mirror. Per `ADDENDUM_A1.md`, `005930` supplies the session calendar only; regime labels use a daily equal-weight eligible-stock return proxy; comparative benchmark is a monthly rebalanced equal-weight portfolio of the available eligible mirror stocks. This is not an official index, and the copied universe mismatch means it is not an exact replay of the registered A2 universe.
- US sample: SPY trading calendar; eligibility requires an available local OHLCV file, an active membership spell in the copied PIT membership file, at least 260 observed bars, and equity instrument metadata when present. Known missing/delisted Yahoo coverage remains; the copied PIT source freeze date is not refreshed.
- Prices: US OHLC adjusted by `adjclose/close`; KR split repair follows the copied `bt2.py` rule. Neither operation cures all vendor/corporate-action errors. Missing observations are not forward-filled for signal eligibility.
- Approximate daily portfolio return: prior close-to-open gap is earned by prior holdings; open-to-close return by the newly targeted holdings. Rebalance turnover costs are applied at open. This is a daily-bar approximation; auction fills, limits, liquidity impact, and exact delisting proceeds are not reconstructable from the mirror.
- Costs, per traded notional: KR buy 11.5bp (1.5bp commission + 10bp slippage), KR sell 31.5bp (buy-side components plus 20bp sell tax); US 10bp each side. All tests use these same base costs. Cost stress is not a selection dimension in this screen.
- Cash return: 0%. US benchmark is adjusted-close SPY buy-and-hold with entry/exit cost. KR benchmark is the equal-weight available eligible-stock portfolio under the same next-open engine and costs, as frozen in Addendum A1.
- Partitions (fixed screening partitions, not virgin OOS): KR IS 2012-06-01..2019-12-31; KR later window 2020-01-01..last mirror date. US IS 2001-01-03..2016-12-30; US later window 2017-01-03..last mirror date. Both later windows have previously been inspected in earlier studies and are contaminated for confirmation.
- Primary screen metrics: net CAGR, annualized Sharpe (252 sessions), maximum drawdown, total turnover, number of monthly rebalance decisions, and qualifying exposure. Report both partitions and market buy-and-hold. No candidate is promoted based on rank or IS performance alone.
- Trial ledger: append exactly one row for each candidate × market execution attempt, including load/compute failures. Candidate-family count is 11 per market (22 planned tests). This is only this-generation count; the complete historical trial count is unresolved, so cumulative DSR/PSR and global multiple-testing correction are not estimable. No claim of passing a significance gate is allowed.

## Closed candidate roster — no parameter search

All thresholds below are fixed before execution. A strategy is long when its close-based condition is active at the monthly decision; where described as a breakout, it remains active until its stated exit. The portfolio takes the qualifying candidates with the largest stated score, then equal weights them. No threshold tuning or parameter sweep is allowed in this generation.

1. **KAMA_ER20** — ER20 = abs(C/C[-20]-1) / sum(abs(daily percentage close changes), 20); Kaufman adaptive average uses fast=2, slow=30. Hold at month-end when ER20 >= 0.30, C > KAMA, and KAMA is rising; score by ER20. Exit at month-end when any condition fails.
2. **HMA55_BREAKOUT** — Hold after C breaks the prior 55-session high while HMA55 rises; exit below prior 20-session low or when HMA55 is no longer rising. Score by HMA55 percentage slope over five sessions.
3. **REG60_R2_BREAKOUT** — Enter/hold after C breaks prior 20-session high while trailing 60-session log-price OLS slope is positive and R² >= 0.35; exit below prior 20-session low or when slope is nonpositive. Score by R².
4. **ATR_NORM_SMA100** — Enter/hold when the 20-session percent change in SMA100 divided by ATR20/C is >= 0.75 and C breaks prior 20-session high; exit below prior 20-session low or when normalized slope <= 0, evaluated at month-end. Score by normalized slope.
5. **VHF63_DONCHIAN20** — Enter/hold when C breaks prior 20-session high and VHF63 >= 0.35; exit below prior 10-session low or when VHF63 < 0.20. Score by VHF63.
6. **PERSIST63** — Enter at month-end when trailing 63-session return is positive and at least 60% of daily close changes are positive; remain held at later month-ends until trailing return <= 0 or positive-day share < 50%. Score by trailing return × positive-day share.
7. **ATR_BUFFER55** — Enter/hold after C > prior 55-session high + 0.5×ATR14; exit below prior 20-session low. Score by breakout distance / ATR14.
8. **RESIDUAL_MOM126** — Monthly cross-sectional ranking: cumulative 126-session log return minus 126×OLS beta to the market's daily log return times market cumulative log return; beta is estimated on the same trailing 126 sessions ending at decision t. Select top 20 KR / top 50 US eligible names. This is a separate, high-overlap residual-momentum hypothesis, not independent of momentum.
9. **GAP_REVERSAL_5D** — Enter after an overnight gap <= -1.5×prior ATR14/C and same-session close > open; hold for five sessions, then exit at next open. Active event slots are ranked by gap/ATR; highest standardized gap first; maximum positions are 20 KR / 50 US. This is an exploratory daily-bar proxy, not intraday execution evidence.
10. **MOM12_1_VOL10_OVERLAY** — Base is the already-seen monthly 12-1 momentum top-K basket. Scale exposure to min(1, 10% / prior-20-session annualized portfolio volatility), with no leverage; apply scale from next open. Record as a contaminated risk overlay, not a new standalone alpha signal.
11. **MOM_TO_LOWVOL_200SMA** — At each month-end, if the broad market close is above its 200-session SMA, hold the 12-1 momentum top-K basket; otherwise hold the lowest-252-session-volatility K basket. This is a high-contamination combination of already-tested components; it is a composition hypothesis only.

## Stop and promotion rules

- Any unreadable/corrupt file, zero/missing benchmark, insufficient data, or runtime failure is recorded as `FAILED` with reason; it is not passed to a language model or converted into a performance result.
- Stop this batch if the runner violates the execution clock, cost contract, or causality checks. Fixes require a dated addendum and a fresh code hash before rerun; old attempt rows remain.
- A positive screen is only a candidate for a separately preregistered confirmation stage. Current historical later windows are not virgin holdouts, and all-time historical multiplicity is unknown. Therefore this generation cannot establish a statistically valid strategy even if a backtest looks strong.
- No factorial combinations are permitted. Any next-generation candidate list must be based on new, nonredundant hypotheses and include every attempt in the durable ledger.

## Frozen file hashes

The preregistration file SHA-256 and runner SHA-256 are captured in `manifest.json` immediately before the first execution. A code or rule change after that point requires an addendum and a new run identifier; it must never replace old records.
