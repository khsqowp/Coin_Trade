# KR Daily V3 exploratory preregistration

Registered: 2026-11-08 KST, before v3 metrics are calculated. Status: exploratory, contaminated, not untouched OOS, not an investment recommendation. No orders, live configurations, or source-system changes.

## Data and known contamination

Use the completed `research/kr_daily_v2/data` panel (up to 3,236 KRX listed/delisted codes) and KODEX 200 (`research/kr_daily_v1/data/069500.parquet`) with the existing v2 adjustment and execution conventions. These prices have already been analyzed in v2, and prior KR strategy research and market paths were previously observed. The v3 runs are a new exploratory search on reused data; 2020+ is not a fresh holdout. No forward or live claims will be made.

No point-in-time market-cap history is present. “Top 50/100/200” therefore means top N by lagged 60-session median traded value (a liquidity proxy), not largest listed companies by capitalization. At close t, eligibility requires at least 252 sessions of history, traded on t, traded on at least 55 of the prior 60 sessions, and 60-session median traded value >= KRW 1bn, following v2. Rank eligible names by the 60-session median traded value known at close t. A rebalance decided at t uses this membership and fills no earlier than t+1 open.

## Fixed strategy rules

All portfolios are long-only, equal-weight, with no leverage, fractional-share assumption, zero cash yield, and no parameter optimization. Run each rule separately for N=50, 100, and 200. If fewer than N eligible names or signals exist, hold the available set equal-weight; otherwise use all N slots. No pyramiding. Rebalance at the last KRX session of each calendar month except the gap strategy, which is daily.

1. **RSI2 trend-filtered mean reversion (daily signal, next-open fills):** compute Wilder RSI(2) from split-adjusted closes. At close t, a currently unheld name is a candidate when close(t) > SMA200(t), RSI2(t) <= 10, and it belongs to the top-N liquidity universe. Rank candidates by RSI2 ascending; hold up to N equal-weight names. At close t, exit a holding if close(t) > SMA5(t) or its completed holding age is at least 5 sessions. Entries and exits execute at the next available open under the v2 tradability/deferred-order rule. Re-evaluate daily; do not re-enter an exited name until a later signal.
2. **Overnight gap reversal (open-to-close):** use the top-N liquidity universe and close(t) > SMA200(t) as known at the preceding close. At open t+1, candidate if open(t+1)/close(t)-1 <= -2.5%. Buy at that open and sell at the same session close; no overnight holding. Rank by gap return ascending and take up to N names. Skip missing, halted, or locked-limit opens/closes. This is a daily-bar approximation and cannot model intraday path or queue priority.
3. **KODEX200 residual momentum (monthly, next-open fills):** on each month-end t, estimate each stock’s beta to KODEX200 by OLS of daily simple returns over the trailing 252 sessions through t, requiring at least 200 paired observations and positive benchmark return variance. Calculate 126-session residual log return = stock log(C[t]/C[t-126]) - beta(t)*log(I[t]/I[t-126]). Candidate requires valid beta/history and residual log return > 0. Rank by residual log return descending; select top N and equal-weight. Rebalance at month-end and fill at t+1 open. This is one cross-sectional factor, not a claim of market-neutral exposure.

## Costs, benchmarks, diagnostics

Use v2 primary cost assumptions: commission 0.015% each side, sell tax 0.20%, and per-side slippage by lagged 60-session median traded value: 0.05% >= KRW50bn; 0.10% >= KRW10bn; 0.25% >= KRW1bn; 0.50% otherwise. Also report 2x slippage and 0.30% sell-tax sensitivities. Run each strategy at notional KRW10m, KRW100m, and KRW1bn for capacity/participation diagnostics; primary NAV begins at KRW100m. Report fill counts, turnover, cost drag, holding/market exposure, available-universe counts, missing/invalid exclusions, and participation percentiles.

Benchmarks: (a) KODEX200 buy-and-hold net of one initial buy cost, (b) monthly equal-weight buy-and-hold/rebalanced portfolio of the same contemporaneous top-N liquidity universe with v2 costs, and (c) cash. Use v2's IS/OOS date split and bull/bear/chop regime windows for comparability but label the reused OOS path contaminated. Show 2012-06..2019-12 IS, 2020-01..2026-11-03 reused-data OOS, full period, and the predefined regimes.

## Exclusions and limits

No market-cap ranking is possible; no invented capitalization fields. No minute bars are present; gap strategy is limited to open-to-close daily bars. If required data fields or history are unavailable for a family, exclude that family and explain. Do not alter v2 files/results, existing untracked v2 files, source data, order systems, live strategy registries, or forward-paper configurations. Store all v3 code, result files, logs, and report only in this new directory.

## Decision policy

This is exploratory, so no winner will be promoted or described as “successful” from these reused-data results. Report every fixed strategy/universe combination, benchmark comparison, costs, regimes, and limitations. Any follow-up requires a new preregistration and untouched forward-paper period.

## Addendum A1: overlap, executable gap timing, and input fingerprints (2026-11-08T05:30Z, before calculation)

The three trials are **not claimed independent of prior strategy families**. RSI(2) and overnight gap reversal are short-horizon reversal variants and overlap at the economic-family level with v2 V9 weekly reversal; RSI2 adds a long-term trend eligibility condition and a different oversold/holding rule, while the gap trial uses an overnight event and close-to-close holding. Residual momentum overlaps the momentum family represented by v2 V1/V2/V6; its beta-adjusted residual return is a distinct signal definition, not a wholly novel family. Coin_Trade archetype overlap remains possible; the source extensive crypto strategy catalog and earlier KR-port results are known and disclosed as contamination. Results are exploratory and will not be represented as independent discoveries.

Execution correction: at t+1 open, the daily bar reveals the gap but a same-open fill cannot be assumed. Therefore the gap strategy enters at the **t+1 close** after confirming open(t+1)/close(t)-1 <= -2.5%, and exits at **t+2 close**. This is executable from daily OHLC without same-open look-ahead, but exposes the position to the full t+1 open-to-close move before entry and measures only the following close-to-close holding interval. A close execution slippage charge is modeled using the same turnover-tier slippage schedule; same-day gap strategy results from the earlier text are superseded and will not be calculated.

Evaluation dates: 2012-06-01 through 2026-11-03. IS: 2012-06-01..2019-12-31. Reused-data OOS: 2020-01-01..2026-11-03, contaminated by prior observation of the KODEX200 market path. Regimes are the fixed v1 windows, whose JSON SHA-256 is `5c1b7262df33a38ba2d388897161fd1055bf18ca1e4584d38c271fae8649b82d`.

Input fingerprints before calculation: aggregate SHA-256 over sorted `research/kr_daily_v2/data/*.parquet` SHA-256 records is `5d5a5126f203519a7a26b6a219e9dc93ed982bd4f0401dffdc7a3301bc245bd2`; KODEX200 parquet SHA-256 is `70f5c0f4681bd1548404ccb7cbc1ae6cfbdeb6d2a00ab886db7b2b41c06c106d`. Existing engine loads `open/high/low/close/volume/value`; source prices were fetched as adjusted KIS daily chart prices. Corporate-action repair used by v2 modifies OHLC and volume where inferred split-like discontinuities exist; traded-value field remains the fetched traded value and is the sole liquidity-ranking input. No capitalization field is available. The combination is explicit: price indicators and execution use repaired OHLC, while liquidity ranking uses source traded value. No further price-volume adjustment is fabricated.

## Addendum A2: universe-size and signal capacity corrections (2026-11-08T05:45Z, before calculation)

N=50/100/200 are point-in-time **universe sizes**, not holdings counts. To keep strategy exposure and order count comparable across the three eligible universes, strategy holdings cap K=20 is fixed for RSI2, gap reversal, and residual momentum. RSI2 and gap reversal choose at most 20 qualifying names; if fewer qualify, uninvested slots remain in cash. Residual momentum selects at most 20 qualifying names from the top-N universe. The equal-weight universe benchmark is monthly equal-weight of all eligible names in the contemporaneous top-N liquidity universe. RSI2 universe membership is recalculated at each close for daily entry/exit; gap uses previous-close top-N membership observed before the next session; residual momentum and its universe membership are sampled at month-end and filled no earlier than the next open. This supersedes prior text that implied N positions.

Residual signal formula correction: use daily **log returns** for both the stock and KODEX200. For each rebalance close t, fit an OLS regression with intercept of the stock's daily log return on KODEX200 daily log return over the trailing 252 sessions through t (minimum 200 paired rows). Score is the sum of the 126 trailing daily regression residuals through t, equivalently cumulative stock log return minus `126*alpha + beta*benchmark cumulative log return`. Select positive scores in descending order, up to 20. This supersedes the prior mixed simple-beta/log-return definition.

Regime results use the pre-existing v1 bull/bear/chop windows only as retrospective descriptive slices. Those periods were observed in prior research; they are not real-time regime labels and are not used to construct or gate any v3 signal.

Data QC is a required pre-result report condition: v2 recorded 3 fetch errors, 1 zero-row marker, 3,236 loaded symbols (including 651 delisted histories), and 428 names with at least one limit-breaching non-gap jump before repair. These issues must be surfaced per family and by symbol/jump exclusion sensitivity where feasible; they prevent a clean performance claim. This count is inherited from v2 QC and will be independently re-counted on the v3 loaded panel before interpreting outcomes.

## Addendum A3: aligned KR/US comparison window (2026-11-08T06:05Z, before calculation)

In addition to the registered KR full window through 2026-11-03, produce an aligned comparison slice ending 2026-08-18, the latest confirmed PIT snapshot date in the separate US study. Aligned IS remains 2012-06-01..2019-12-31; aligned reused-OOS is 2020-01-01..2026-08-18; aligned FULL is 2012-06-01..2026-08-18. Use identical signal formula, universe definition, holdings cap, costs, and metrics as the full KR run, truncating inputs/outputs at the aligned end. Preserve the longer KR result as a distinct period. This aligned table is for comparison only, remains contaminated, and will not be computed until the US A3 preregistration is finalized. Do not infer any strategy from the cutoff.

## Addendum A4: implementation details fixed by code audit (2026-11-08T06:20Z, before calculation)

RSI uses Wilder smoothing with alpha 1/2 from close-to-close changes; a flat two-session gain/loss state is RSI=50. SMA windows are simple close means over the latest 5 and 200 KRX sessions. The strategy target is maximum 20 positions and weights are updated only when the target membership changes; the existing simulator fills at the next open and applies its registered deferred-order rules (buys cancel after five untradable sessions, sells continue retrying).

For residual momentum, daily log return is computed from repaired adjusted closes and is missing on a date without a traded row. The 252-session OLS uses an intercept and at least 200 paired observations. The 126-session residual score requires all 126 daily stock and benchmark log returns to be present; incomplete candidates are excluded. Score is the sum of the 126 daily residuals `r_stock - alpha - beta*r_KODEX200`.

For gap positions, each signal is triggered by the current session open but filled only at that session close. It exits at the next session close; if the instrument has no executable traded bar then, exit is deferred to its next tradable close. Position target is 5% of marked NAV per open slot, up to 20 slots. A name with an untradeable/locked current bar is not entered. This explicitly supersedes any interpretation as same-open execution.

The equity curve is net of modeled costs; no interest accrues on cash. Position-level daily data cannot model closing-auction priority, market impact beyond fixed slippage tiers, or partial fill queues. These are limitations, not inferred fills.

## Addendum A5: invalid bars and terminal liquidation (2026-11-08T06:40Z, before valid rerun)

Before computing indicators, any source daily row with a nonfinite or nonpositive OHLC price is excluded from the usable panel by marking OHLC missing and volume zero. Each excluded `(symbol, date)` is recorded in a new v3 QC artifact; the source parquet files are read-only and unchanged. Corporate-action repair only divides by a factor when the prior/current close are finite and positive and the resulting factor is finite and positive. Invalid ratios are recorded and skipped, not propagated. Locked-limit and return calculations use guarded division and treat unavailable/zero denominators as unavailable. Report invalid bar counts and symbol/date samples, plus residual post-repair jumps.

Where the time series ends before the evaluation window because an instrument was delisted, use the last observed repaired close as the terminal liquidation proxy and charge sell slippage, commission, and tax. This is a modeling assumption; the last close is not evidence of an executable delisting fill. Report terminal liquidation count and PnL separately where captured. A gap position whose scheduled t+2 close has no tradable row stays held and retries at each subsequent tradable close; it is not silently marked sold.

## Addendum A6: canonical input fingerprint and ticker reuse identity split (2026-11-08T07:10Z, before calculation)

The raw input tree contains 3,236 parquet files. Its canonical aggregate hash is computed as follows: sort relative paths under `research/kr_daily_v2/data/` by UTF-8 byte order; for each file append `<lowercase SHA-256><two spaces><relative path><LF>`; SHA-256 the concatenated UTF-8 bytes. This locale-independent procedure yields `8458fef56e4ec99b960a3194ebc6cf59ecea5f2a23ec633d64603474b3afbc79`. This supersedes the earlier `5d5a...` fingerprint, which reflected host `en_US.UTF-8` locale collation and could not be reproduced by Python's deterministic path ordering. All 3,236 source parquet files remain hash-covered, and no v2 input file is modified.

`036220_old.parquet` is retained as a separate historical instrument identity, not excluded as a stray backup. The source universe lists `오상헬스케어 / 036220` as a delisted spell through 2016-05-09 and a later listed spell from 2024-03-13. The fetch log maps `036220_old` to the delisted spell (1,238 rows, 2011-05-02..2016-05-04) and `036220` to the later listed spell (642 rows, 2024-03-13..2026-11-03). Both files have the same six columns (`open/high/low/close/volume/value`) and zero overlapping dates. They remain separate instrument IDs; no price series is joined across the 2016-2024 gap. The v3 QC report records this mapping, ranges, schema, and overlap count.

## Addendum A7: confirmed delisting versus unresolved data tail (2026-11-08T07:40Z, before calculation)

A time-series end before 2026-11-03 is treated as a confirmed delisting only when the exact instrument ID is present with `status=delisted` in the frozen fetch log/universe provenance. For those confirmed IDs, use the last observed repaired close as a terminal liquidation proxy, charge sell slippage, commission, and tax, and count/report the proxy liquidation and its marked PnL. This is not proof of an executable last-close fill.

A missing data tail, fetch gap, or early end without a confirmed delisted status is **not** force-sold and receives no fictitious exit fill or exit costs. Keep its last valid close as a stale mark in NAV, and separately report unresolved position count, stale marked value, and PnL contribution. Positions still open on the final evaluation date remain marked at that close and are not liquidated. The 036220_old and 036220 histories retain their separately confirmed delisted/listed identities; no continuity is imputed across their non-overlap.

For daily-bar gap reversal, a scheduled close exit that has no tradable row continues to retry at the next tradable close. At period end, only confirmed-delist residual lots receive the documented terminal proxy; unresolved gap lots remain marked and reported separately.
