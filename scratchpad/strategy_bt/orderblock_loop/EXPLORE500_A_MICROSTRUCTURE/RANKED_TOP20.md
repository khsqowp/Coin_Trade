# EXPLORATORY SCREEN ONLY -- not part of the 13-round preregistered G-gate track, not added to TRAIN_TRIALS.csv, no promotion without separate formal preregistration + synthetic tests + resource-gated TRAIN run.

This is an exploratory screen only: no look-ahead-bias audit, no multiple-testing correction, no walk-forward validation. Not G-eligible, not added to any real ledger, no promotion without separate formal preregistration + synthetic tests + resource-gated TRAIN run.

Backtested on 12 symbols (BTCUSDT, ETHUSDT, BNBUSDT, SOLUSDT, XRPUSDT, ADAUSDT, DOGEUSDT, AVAXUSDT, DOTUSDT, LINKUSDT, LTCUSDT, ATOMUSDT), timeframe=1h, up to 12000 most-recent bars/symbol. Exit convention: 1.5x ATR14 stop, 2.0R target, 48-bar max hold, 12.0bp round-trip cost.

## Top 20 by composite_score

### 1. M149 -- RSI rare-extreme (<10) oversold exhaustion long

- composite_score: 1623.32
- n_trades: 47, win_rate: 0.787234, profit_factor: 9.28953, expectancy_bps: 419.332, rough_sharpe: 0.921253
- mechanism: RSI(14) below 10, go long
- rationale: Symmetric rare-extreme oversold exhaustion
- prior rank note: medium-low: symmetric to short, same rarity caveat
- post-hoc note: Scored well on this cheap screen (47 trades across the 12-symbol subset); see caveats above before drawing any conclusion.

### 2. M015 -- Funding-rate extreme-positive fade short

- composite_score: 429.225
- n_trades: 44, win_rate: 0.545455, profit_factor: 2.0473, expectancy_bps: 112.756, rough_sharpe: 0.333974
- mechanism: Latest settled funding rate > +0.05% (annualized ~55%), fade short expecting funding-driven long crowding to unwind
- rationale: Extremely positive funding means longs are paying a heavy premium; historically this crowding precedes mean-reverting pullbacks
- prior rank note: high: funding-extreme mean-reversion is one of the better-documented crypto-specific edges, distinct from R13's breakdown-short design
- post-hoc note: Scored well on this cheap screen (44 trades across the 12-symbol subset); see caveats above before drawing any conclusion.

### 3. M016 -- Funding-rate extreme-negative fade long

- composite_score: 129.918
- n_trades: 1821, win_rate: 0.378913, profit_factor: 1.09327, expectancy_bps: 17.3047, rough_sharpe: 0.0266048
- mechanism: Latest settled funding rate < -0.05%, go long expecting short-crowding unwind
- rationale: Symmetric negative-funding crowding unwind
- prior rank note: high: symmetric to short version
- post-hoc note: Scored well on this cheap screen (1821 trades across the 12-symbol subset); see caveats above before drawing any conclusion.

### 4. M147 -- Parabolic-SAR flip after extended downtrend, exhaustion long

- composite_score: 100.769
- n_trades: 202, win_rate: 0.316832, profit_factor: 1.17505, expectancy_bps: 18.9659, rough_sharpe: 0.0524128
- mechanism: SAR flips from above-price to below-price after a downtrend lasting >= 30 bars, go long
- rationale: Symmetric extended-downtrend exhaustion bet
- prior rank note: medium-low: symmetric to short, same caveat
- post-hoc note: Scored well on this cheap screen (202 trades across the 12-symbol subset); see caveats above before drawing any conclusion.

### 5. M064 -- Price-volume bearish divergence short

- composite_score: 76.9018
- n_trades: 5787, win_rate: 0.379126, profit_factor: 1.0893, expectancy_bps: 8.87648, rough_sharpe: 0.0360078
- mechanism: Price makes a new 20-bar closing high while 10-bar average volume is declining versus the prior 10-bar average, go short
- rationale: A new high on thinning volume suggests fewer participants are willing to pay up, a classic distribution warning
- prior rank note: medium-high: volume-divergence-at-extremes is a long-standing, intuitive technical heuristic
- post-hoc note: Scored well on this cheap screen (5787 trades across the 12-symbol subset); see caveats above before drawing any conclusion.

### 6. M007 -- Volume-spike continuation long

- composite_score: 70.5188
- n_trades: 1285, win_rate: 0.382101, profit_factor: 1.09649, expectancy_bps: 9.84996, rough_sharpe: 0.0388648
- mechanism: Bar volume > 3x its trailing 20-bar average AND close in top third of the bar's range, enter in direction of the bar
- rationale: A volume surge with strong directional close signals fresh aggressive flow (informed order flow), which tends to persist short-term
- prior rank note: high: volume-confirmed breakout bars are a classic, robust momentum continuation signal
- post-hoc note: Scored well on this cheap screen (1285 trades across the 12-symbol subset); see caveats above before drawing any conclusion.

### 7. M017 -- Funding-rate z-score extreme fade short

- composite_score: 60.3242
- n_trades: 1028, win_rate: 0.389105, profit_factor: 1.07743, expectancy_bps: 8.69684, rough_sharpe: 0.0309153
- mechanism: Funding rate z-score (vs its trailing ~90-settlement mean/stdev) > 2, fade short
- rationale: A statistically standardized funding extreme adapts the fade threshold to each symbol's own regime, unlike a fixed absolute cutoff
- prior rank note: high: z-score normalization should generalize the funding-fade edge better across symbols with different typical funding ranges
- post-hoc note: Scored well on this cheap screen (1028 trades across the 12-symbol subset); see caveats above before drawing any conclusion.

### 8. M113 -- Weekend low-liquidity mean reversion short

- composite_score: 57.144
- n_trades: 4558, win_rate: 0.368802, profit_factor: 1.06654, expectancy_bps: 6.78278, rough_sharpe: 0.0270669
- mechanism: Same weekend stretch condition on the downside, go short expecting reversion
- rationale: Symmetric weekend reversion short
- prior rank note: medium: symmetric to long
- post-hoc note: Scored well on this cheap screen (4558 trades across the 12-symbol subset); see caveats above before drawing any conclusion.

### 9. M150 -- Decorrelation-spike idiosyncratic-move fade short

- composite_score: 56.575
- n_trades: 15135, win_rate: 0.378064, profit_factor: 1.05438, expectancy_bps: 5.87803, rough_sharpe: 0.0227182
- mechanism: Rolling 50-bar correlation of altcoin returns to BTC returns drops below its own 20th percentile AND the altcoin outperformed BTC over the same window, fade the altcoin short
- rationale: A sudden decoupling plus idiosyncratic outperformance is often a short-lived, flow-driven anomaly that re-correlates (and gives back the excess move) once the idiosyncratic flow fades
- prior rank note: medium-low: decorrelation-based fades are a more exotic, thinly-evidenced construct relative to the direct relative-strength family
- post-hoc note: Scored well on this cheap screen (15135 trades across the 12-symbol subset); see caveats above before drawing any conclusion.

### 10. M027 -- TTM-style squeeze breakout long

- composite_score: 31.3005
- n_trades: 2543, win_rate: 0.36335, profit_factor: 1.04228, expectancy_bps: 3.99165, rough_sharpe: 0.0176885
- mechanism: Bollinger(20,2) bands fully inside Keltner(20,1.5*ATR) channel (classic 'squeeze on'), then release with close above BB upper
- rationale: Combining two independent vol measures reduces false squeeze signals versus either alone
- prior rank note: medium-high: popular retail indicator, confluence of two measures should filter some noise
- post-hoc note: Scored well on this cheap screen (2543 trades across the 12-symbol subset); see caveats above before drawing any conclusion.

### 11. M018 -- Funding-rate z-score extreme fade long

- composite_score: 11.3097
- n_trades: 7350, win_rate: 0.365306, profit_factor: 1.00976, expectancy_bps: 1.27038, rough_sharpe: 0.00321348
- mechanism: Funding rate z-score < -2, go long
- rationale: Symmetric z-score funding fade long
- prior rank note: high: symmetric to short
- post-hoc note: Scored well on this cheap screen (7350 trades across the 12-symbol subset); see caveats above before drawing any conclusion.

### 12. M002 -- Bollinger squeeze breakout short

- composite_score: 4.62232
- n_trades: 2556, win_rate: 0.370892, profit_factor: 1.00596, expectancy_bps: 0.589087, rough_sharpe: 0.00252829
- mechanism: BB(20,2) bandwidth in bottom 20th pct of its own 100-bar history, then close breaks below lower band
- rationale: Symmetric to the long case; squeeze-release breakouts work both directions in trending/ranging regime shifts
- prior rank note: high: same structural edge as long version, no directional bias assumed
- post-hoc note: Scored well on this cheap screen (2556 trades across the 12-symbol subset); see caveats above before drawing any conclusion.

### 13. M028 -- TTM-style squeeze breakout short

- composite_score: -4.253
- n_trades: 2931, win_rate: 0.379393, profit_factor: 0.994643, expectancy_bps: -0.535596, rough_sharpe: -0.00224612
- mechanism: BB inside KC squeeze, release with close below BB lower band
- rationale: Symmetric TTM squeeze short
- prior rank note: medium-high: symmetric to long
- post-hoc note: Scored poorly/near-zero on this cheap screen (2931 trades across the 12-symbol subset); see caveats above before drawing any conclusion.

### 14. M032 -- Up/down volume pressure extreme short

- composite_score: -8.09361
- n_trades: 15511, win_rate: 0.379988, profit_factor: 0.992434, expectancy_bps: -0.845166, rough_sharpe: -0.00310335
- mechanism: Rolling 20-bar up/down volume ratio < 10th percentile of its own 200-bar history, go short
- rationale: Symmetric sell-pressure proxy
- prior rank note: medium-high: symmetric to long
- post-hoc note: Scored poorly/near-zero on this cheap screen (15511 trades across the 12-symbol subset); see caveats above before drawing any conclusion.

### 15. M049 -- OBV new-low breakdown confirmation short

- composite_score: -12.67
- n_trades: 5149, win_rate: 0.370557, profit_factor: 0.986776, expectancy_bps: -1.5023, rough_sharpe: -0.00537163
- mechanism: OBV makes a new 20-bar low at/before price, go short on price's subsequent new low
- rationale: Symmetric OBV-led breakdown confirmation
- prior rank note: medium-high: symmetric to long
- post-hoc note: Scored poorly/near-zero on this cheap screen (5149 trades across the 12-symbol subset); see caveats above before drawing any conclusion.

### 16. M006 -- Keltner channel squeeze breakout short

- composite_score: -25.0059
- n_trades: 3718, win_rate: 0.374933, profit_factor: 0.971032, expectancy_bps: -3.13237, rough_sharpe: -0.0123984
- mechanism: Price exits Keltner channel to the downside after 10+ bars inside the channel
- rationale: Symmetric Keltner breakout short
- prior rank note: high: symmetric to long
- post-hoc note: Scored poorly/near-zero on this cheap screen (3718 trades across the 12-symbol subset); see caveats above before drawing any conclusion.

### 17. M090 -- Stochastic bearish regular divergence short

- composite_score: -25.4793
- n_trades: 5393, win_rate: 0.355275, profit_factor: 0.97204, expectancy_bps: -3.0504, rough_sharpe: -0.0120908
- mechanism: Price new 20-bar closing high while Stochastic %K is lower than at the prior high; enter short
- rationale: Symmetric stochastic divergence short
- prior rank note: medium: symmetric to long
- post-hoc note: Scored poorly/near-zero on this cheap screen (5393 trades across the 12-symbol subset); see caveats above before drawing any conclusion.

### 18. M008 -- Volume-spike continuation short

- composite_score: -28.5482
- n_trades: 1140, win_rate: 0.369298, profit_factor: 0.960716, expectancy_bps: -4.22116, rough_sharpe: -0.0166961
- mechanism: Bar volume > 3x 20-bar average AND close in bottom third of range, enter short
- rationale: Symmetric volume-confirmed continuation short
- prior rank note: high: symmetric to long
- post-hoc note: Scored poorly/near-zero on this cheap screen (1140 trades across the 12-symbol subset); see caveats above before drawing any conclusion.

### 19. M038 -- RSI bearish regular divergence short

- composite_score: -32.9527
- n_trades: 2902, win_rate: 0.352171, profit_factor: 0.961714, expectancy_bps: -4.2973, rough_sharpe: -0.0167467
- mechanism: Price makes a new trailing-20-bar closing high while RSI(14) is lower than at the prior high; enter short once confirmed
- rationale: Symmetric bearish regular divergence
- prior rank note: medium-high: symmetric to long
- post-hoc note: Scored poorly/near-zero on this cheap screen (2902 trades across the 12-symbol subset); see caveats above before drawing any conclusion.

### 20. M040 -- RSI bearish hidden divergence short

- composite_score: -33.7764
- n_trades: 294, win_rate: 0.360544, profit_factor: 0.938262, expectancy_bps: -6.33006, rough_sharpe: -0.0267056
- mechanism: Price makes a lower high while RSI makes a higher high; enter short (downtrend continuation)
- rationale: Symmetric hidden divergence short
- prior rank note: medium-high: symmetric to long
- post-hoc note: Scored poorly/near-zero on this cheap screen (294 trades across the 12-symbol subset); see caveats above before drawing any conclusion.

