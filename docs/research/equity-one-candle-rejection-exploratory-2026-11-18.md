# KR/US single-candle lower-wick rejection (exploratory)

Decision: reject for KR in this exposed diagnostic; US estimates are inconclusive and are not promoted. This is a one-candle morphology association test, not a portfolio strategy. It was run after prior work had already inspected this evaluation history, so it is not confirmatory or sealed OOS evidence.

## Fixed rule and target

Using only the completed signal-session OHLC, emit a bullish rejection signal when all are true:

1. `High > Low` and `abs(Close - Open) > 0`.
2. `Close > Open`.
3. Lower wick `min(Open, Close) - Low >= 2 * abs(Close - Open)`.
4. Upper wick `High - max(Open, Close) <= abs(Close - Open)`.
5. `Close >= Low + 0.5 * (High - Low)`.

The prediction is UP for the next observed session close relative to the signal close. This does not include a prior-trend requirement and is therefore called a lower-wick rejection shape, not a classic hammer pattern. Invalid OHLC in any of prior/signal/target bars excludes the observation.

## Results

Comparison is the event rate minus a ticker-weighted unconditional next-session UP rate: for each ticker, compute its eligible evaluation-period UP rate, then apply that ticker's rate to its signal events. Uncertainty uses 5,000 circular 21-calendar-day moving-block bootstrap replicates over 2021-01-01 through 2024-12-31, sampling the same dates across all tickers within a market, seed 20261118.

| Market / cohort | Signals | Eligible ticker-sessions | Signal coverage | Signal next-close UP | Ticker-baseline UP at signals | Excess | 95% date-block interval |
|---|---:|---:|---:|---:|---:|---:|---:|
| KR ETF | 654 | 25,532 | 2.56% | 46.024% | 49.937% | −3.912 pp | −8.471 to +0.891 pp |
| KR non-ETF | 1,623 | 63,520 | 2.55% | 40.850% | 46.668% | −5.818 pp | −8.570 to −3.002 pp |
| US ETF | 983 | 38,106 | 2.58% | 54.120% | 51.782% | +2.338 pp | −1.737 to +6.324 pp |
| US stocks | 1,258 | 54,072 | 2.33% | 53.339% | 51.814% | +1.524 pp | −1.999 to +4.712 pp |

Per-symbol signal counts ranged 13–42 for KR ETFs, 10–43 for KR non-ETF symbols, 3–41 for US ETFs, and 15–37 for US stocks. US invalid OHLC rows were excluded with adjacent labels; the underlying cache contains 62 OHLC shape violations across four historical dates. Cause is unverified.

## Interpretation

- The candidate underperformed its per-symbol unconditional UP baseline in both KR cohorts. For KR non-ETF symbols, the block interval was wholly below zero; this is evidence against this exact rule on this explored window, not proof that all lower-wick patterns fail.
- US point estimates were positive but both intervals include zero. There is no reliable incremental association demonstrated.
- Only one fixed definition was evaluated here, without selecting thresholds from this result. The price history is already exposed and similar price studies exist, so multiplicity and data-selection uncertainty remain. Do not tune the wick ratios on this same window.
- No entry price, stop, target, time-to-target, fees, taxes, spread, slippage, borrow, portfolio sizing, CAGR, MDD, Sharpe, or 200 completed OOS round trips were tested. The user's stock gate (CAGR ≥20%, MDD ≤30%, Sharpe ≥1, at least 200 OOS round trips) is untouched.
- Next confirmatory step requires verified OHLC adjustment/source provenance and a genuinely unused or forward dataset with the rule frozen before outcomes are observed. Until then the US result remains exploratory; no live or autonomous use is justified.
