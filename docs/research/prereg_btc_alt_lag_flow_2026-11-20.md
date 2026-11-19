# Preregistration — BTC shock / altcoin lag with taker-flow confirmation

- Trial: `btc_alt_lag_flow_20261120_01` (registry ID 99)
- Status: preregistered; no candidate outcome has been computed at registration time.
- Goal: maximize after-cost compounded wealth across market regimes. M2 target-first >=80% remains a separate user-set signal-quality gate, not a substitute for wealth growth.
- Scope: one exploratory historical screen on Binance Vision USDⓈ-M 1-minute klines. No orders, live signals, or production use.

## Hypothesis and distinctness

When BTC has a directional 5-minute price shock confirmed by taker-buy/sell imbalance and aligned with its completed 4-hour trend, the two eligible altcoins that lag BTC's prior 30-minute return but show aligned local taker flow will continue in the BTC direction before the catch-up is fully priced. A lagger selection should outperform selecting the leading eligible altcoin under identical triggers and execution. This is distinct from per-symbol breakout/taker-imbalance trial 31, 3-minute quote-volume close-location trial 98, and cross-sectional 60-minute mean reversion: it uses cross-asset lag ranking, multi-timeframe trend alignment, and aggressor-side taker flow jointly.

The mechanism can fail when alts move synchronously, BTC shocks reverse, lag reflects adverse information or illiquidity, or costs overwhelm short-horizon continuation. This is a testable hypothesis, not a claimed edge.

## Immutable data and time split

- Input: read-only `vision_dev_repaired.sqlite`, table `candles`, columns `symbol,open_ms,open,high,low,close,quote_volume,trade_count,taker_buy_quote`.
- Symbols: BTCUSDT, ETHUSDT, BNBUSDT, DOGEUSDT, SOLUSDT, XRPUSDT; no symbol additions or exclusions after seeing results.
- Full observed range: 2020-01-01 through 2026-06-30 UTC. Each symbol's actual available start is retained; no pre-listing rows are synthesized.
- Development: 2020-04-01 00:00 UTC to 2023-12-31 23:59 UTC. The first 90 days are warmup only. Development results may reject the hypothesis but may not tune parameters.
- Chronological confirmation: 2024-01-01 00:00 UTC to 2026-07-01 00:00 UTC, run once only if every development continuation gate passes. This period is not sealed from previous repository-wide research and cannot support final approval. Until that gate passes, code must not read it for candidate scoring.
- Current universe has six symbols, so even a passing result is only a screening signal and cannot satisfy the project's final >=20-symbol rule. No result from this file is live or forward evidence.
- Binance Vision terms permit personal, non-production historical backtesting, govern derived metrics, and require attribution plus CC BY-NC-SA 4.0 for redistributed derivative work. This report must carry that attribution/license notice. Do not use Vision-derived outputs for live trading signals or commercial distribution.

## Frozen signal and execution rules

All features use only completed bars. Five-minute bars are UTC-aligned aggregations of exactly five contiguous 1-minute rows; any incomplete aggregation invalidates the affected feature. Four-hour bars require 240 contiguous rows. No gap is filled or interpolated.

1. At each completed 5-minute BTC bar close `t`, define direction `d=+1` if the close-to-previous-5m-close return is >= +0.30%, `d=-1` if <= -0.30%; otherwise no event.
2. Require BTC 5-minute taker imbalance `2*taker_buy_quote/quote_volume-1` to satisfy `d*imbalance >= 0.15`.
3. Require the latest completed BTC 4-hour close and EMA20/EMA50 to align: for `d=+1`, close > EMA20 > EMA50; for `d=-1`, close < EMA20 < EMA50. EMAs use completed 4-hour closes only, with `adjust=False`; at least 50 contiguous complete 4-hour bars must exist.
4. For each of ETH, BNB, DOGE, SOL, XRP, compute completed 30-minute return as-of `t`. Candidate eligibility requires a complete contiguous 30-minute path, aligned 5-minute taker imbalance `d*imbalance >= 0.10`, and positive lag score `d*(BTC_30m_return - alt_30m_return) >= 0.10%`.
5. Rank eligible alts by lag score descending, then symbol ascending. Emit exactly one candidate signal for the top-ranked alt. The matched leader control uses the same event and eligible list but picks the smallest lag score (symbol ascending tie-break). If no eligible alt exists, emit no signal.
6. Signal becomes actionable at `t`; skip the entire next 1-minute bar and enter at the open of the exact 1-minute bar at `t+60,000 ms`. Missing entry bar makes the signal unscorable; do not shift it later.
7. Long/short direction equals `d`. Fixed barriers from entry: target 0.60%, stop 0.30%, vertical barrier 15 completed 1-minute bars starting with the entry bar. If stop and target are both touched in one bar, stop wins. A stop gap through the barrier fills at the worse bar open; a target is filled at its limit, never improved by a gap. At vertical expiry, close at the final bar close. Missing any required 1-minute bar makes the trade unscorable.
8. Base cost: 0.05% taker fee + 0.04% slippage per side. Stress: 0.05% taker fee + 0.08% slippage per side. Net return is `d*(exit/entry-1) - side_cost*(1 + exit/entry)`. No funding is charged because the maximum holding time is 15 minutes; market impact and liquidation are not modeled.
9. For the compounding path, take the first eligible chronological signal only when the previous position has closed; one position at a time, 1.0x gross exposure, all NAV allocated. Compound each accepted trade by its net return. Compare the lag strategy with the matched leader control, 100% cash, and BTC buy-and-hold over identical dates and base/stress transaction costs.

## Frozen evaluation and stop rule

Report signal count, unscorable count, coverage, M2 target-first rate with Wilson 95% CI, non-overlap N and M2, M1 direction at expiry, net expectancy, compounded final NAV/total return/CAGR, trade-close and intratrade-marked MDD, Sharpe, profit factor, year-by-year results, and results by BTC 4-hour trend regime. Report candidate and leader-control figures side by side; also give cash and BTC buy-and-hold NAV.

Development may continue to one chronological confirmation only if all are true: (a) scorable development non-overlap N>=200; (b) M2 point estimate >=80%; (c) base and stress after-cost expectancy >0; (d) candidate final compounded NAV exceeds cash, BTC buy-and-hold, and the leader control under both cost models; (e) no causal, data-integrity, or execution test fails. Any failure rejects the candidate; no parameter change, threshold scan, or post-result rule patch is allowed. Even if all pass, the six-symbol/current-survivor sample is insufficient for final approval; a >=20-symbol independent forward evaluation remains mandatory.

Controls: prefix-invariance; synthetic stop/target collision and adverse gap tests; incomplete-bar and missing-minute rejection; explicit comparison with matched leader selection; source DB `PRAGMA integrity_check`; data SHA-256 and code SHA-256 recorded. No raw Vision rows are copied into Git.

## Source attribution and redistribution

Source: Binance Vision USDⓈ-M Futures 1-minute klines, retrieved from the local repaired archive. Binance Public Data README documents the kline taker-buy quote-volume field. This report and its derived results are attributed to Binance Vision and licensed CC BY-NC-SA 4.0 for redistribution, per Binance Vision Dataset Terms v1.0, last updated 2026-08-26. The source archive remains local and is not committed.
