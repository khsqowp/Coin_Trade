# Crypto Round 10 — 1m liquidity-sweep rejection + taker-flow confirmation

Status: fixed candidate definition before running this probe. This is a development-only test on already-viewed local history, not a sealed/OOS or live signal. No orders, exchange credentials, network calls, funding data, or leverage simulation.

## Hypothesis and universe

After price briefly sweeps a recent 20-minute extreme but closes back inside the range, a long lower-wick/strong-close plus taker-buy confirmation may predict a reversal. Use only BNBUSDT, BTCUSDT, DOGEUSDT, and ETHUSDT 1-minute candles, the gap-audited cohort already used in prior probes. Database reads must remain read-only and stop at the existing exclusive cutoff `2026-10-09T00:00:00Z` (cache ends 2026-06-30).

## Frozen signal rules

- Prior support/resistance are the minimum low/maximum high of the previous 20 completed 1m candles; the signal candle is excluded from these levels.
- ATR is the simple 14-candle average true range through the just-completed signal candle. Require contiguous minute timestamps across the 20-bar range window and the ATR lookback; missing minutes are never filled.
- Long: current low is below prior support, current close finishes above prior support, lower wick `min(open, close) - low` is at least `0.5 × ATR14`, close is at or above the 60th percentile of the signal candle's high-low range, and taker-buy quote volume / total quote volume is at least 0.65.
- Short: symmetric sweep above prior resistance, close back below resistance, upper wick at least `0.5 × ATR14`, close at or below the 40th percentile of the candle range, and taker-buy quote share at most 0.35.
- Signal is known only after the candle closes. Enter at the next 1m open. Long stop is the signal low; short stop is the signal high. Skip if entry-to-stop distance is nonpositive or invalid. Target is 2R. Expiry is 10 or 20 minutes after entry; the two horizons are separate, non-overlapping experiments per symbol.
- Resolve against raw 1m OHLC: if stop and target are both touched in one minute, stop wins; adverse stop gaps fill at the worse of the open and stop. If neither barrier is hit, exit at expiry close.
- Costs are 0.10% base and 0.30% stress round trip. These are assumed costs; funding, spread, liquidation and actual fills are not modeled.

## Evaluation and falsification

Report all symbol × horizon cells, n, coverage, target-first rate, net-positive rate, mean net return, seven-calendar-day moving-block 95% intervals, and an opposite-side control at identical anchors/risk. A target-first value below 75% fails the existing alert gate; 80% is the aspirational accuracy target, not an achieved result. A candidate also fails if mean net return is not positive at base cost or reverses under stress. No best-cell promotion; no tuning on this cache.

Before the data run, test prefix/future-mutation invariance, deliberate future-peek detection, gap reset, stop-first ties, and adverse stop gaps on synthetic inputs. All output remains development-only because these data have already been used by prior research agents.
