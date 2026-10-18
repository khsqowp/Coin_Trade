# Crypto futures: 20-strategy parallel paper test

The standalone crypto data collector evaluates 20 independent, order-free USD-M futures simulations on the same BTC/ETH public trade stream. It aggregates one-minute candles from individual trades. A signal derived from a completed candle is entered at the first observed trade of the next candle; stops and targets are checked against every received trade. No Binance account credentials or order endpoints are used.

Each strategy has its own virtual equity ledger, position map, trade history, fees, and funding PnL. The starting value is 142 USDT per strategy, the exposure is capped at 95% of equity divided evenly across configured symbols, and simulated leverage is 1x. The defaults charge 0.05% taker fees and 0.02% adverse slippage per side. These are explicit simulation assumptions, not a guarantee of actual execution costs. Funding is applied at observed settlement boundaries using the last reported funding rate. Strategy 1 alone uses the requested fixed 3% stop and 5% target. The other 19 strategies use the structural exits below, with a four-hour maximum hold unless a shorter limit is specified.

| # | Strategy | Entry hypothesis | Exit design |
|---:|---|---|---|
| 1 | High-volume impulse breakout | Strong one-minute move with at least 1.8x recent volume and close near the candle extreme | Fixed 3% stop / 5% target; no common technical exit |
| 2 | Three-candle Heikin-Ashi trend | Three same-color Heikin-Ashi bars aligned with EMA20 | 2 ATR initial and trailing stop; exit after two opposite Heikin-Ashi bars |
| 3 | Deep trend pullback + volume burst | Established trend, multiple countertrend candles, then a >2x-volume reversal through EMA9/prior extreme | Swing support/resistance stop and target, ATR-capped stop, 1.4 ATR trail, EMA20 invalidation |
| 4 | EMA 9/21 cross | Fast/slow EMA crossover | 1.5 ATR stop, 2 ATR trail, opposite EMA cross exit |
| 5 | EMA 20/50 trend pullback | Pullback through EMA20 while EMA20/50 trend remains aligned | Swing stop and nearby swing target, ATR cap/trail, EMA20 invalidation |
| 6 | MACD 12/26/9 | MACD signal-line crossover | 1.8 ATR stop, 2.2 ATR trail, opposite MACD cross exit |
| 7 | RSI reversal | RSI crosses back out of oversold/overbought | Swing invalidation, target at 20-bar mean (or risk multiple if mean is behind entry), exit at RSI 50, max 60 bars |
| 8 | Bollinger re-entry | Price returns inside the band after closing outside | Swing invalidation, middle-band target, exit at middle band, max 60 bars |
| 9 | Donchian 20 breakout | Close breaks the prior 20-bar high/low | 2 ATR initial stop, 2.5 ATR trailing stop, exit on opposite 10-bar channel breach |
| 10 | Rolling 60-minute VWAP reclaim | Close crosses VWAP in the direction of the move | Swing invalidation, VWAP target, exit on adverse VWAP cross, max 120 bars |
| 11 | ATR trend-band reversal | Close reverses across an ATR-based trend band | 2 ATR initial/trailing stop, exit when the ATR trend signal reverses |
| 12 | Keltner 1.5 ATR breakout | Close breaks the EMA20-centered Keltner envelope | 1.7 ATR stop, 1.8 ATR trail, swing target, exit on EMA20 loss |
| 13 | Bollinger squeeze release | Narrow prior band width followed by an outward close | 1.5 ATR stop, 2.2 ATR trail, exit on failed return through the middle band |
| 14 | Stochastic reversal | Stochastic crosses out of oversold/overbought | Swing invalidation, 20-bar mean target, exit as stochastic momentum crosses 50, max 60 bars |
| 15 | OBV trend confirmation | OBV direction agrees with the EMA20 price trend | 1.8 ATR stop, 2 ATR trail, exit when recent OBV flow reverses |
| 16 | Taker imbalance breakout | Buyer/seller-initiated volume imbalance accompanies a local breakout | 1.2 ATR stop, 1.5 ATR trail, 2R target, exit when taker flow reverses |
| 17 | Extreme-funding reversal | Extreme funding plus price confirmation in the less crowded direction | 1.5 ATR stop, 1.8 ATR trail, swing target, exit when funding normalizes/flips |
| 18 | Funding-aligned momentum | Funding sign and short-term EMA momentum point in the same direction | 1.5 ATR stop, 2 ATR trail, exit when funding sign flips |
| 19 | 1-minute/15-minute alignment | Short-term EMA trend agrees with the sampled 15-minute trend | 2 ATR stop, 2.5 ATR trail, exit when higher-timeframe alignment is lost |
| 20 | ATR range expansion | Large-range candle breaks the recent 10-bar channel | 1.5 ATR stop, 2 ATR trail, 2R target, exit after opposite channel break |

State is written atomically to `/app/data/crypto_paper_strategies.json`, mapped locally to `Ochestration/trading-crypto-paper-state/`, and copied to `/Volumes/HDD2TB/Trade/crypto-paper-state` by the weekly tick-only backup. The state folder is retained locally because the running simulation needs it. Recent trades are capped at 500 per strategy; closed-candle history is capped at 300 minutes for indicator warm-up and recovery.

This is a live forward paper test, not a completed strategy validation. At startup, indicators warm up from available bars; longer lookbacks need more data. With the current BTC/ETH subscription, each strategy observes two symbols. The 3%/5% bracket is not copied to the other strategies. ATR, moving-average, VWAP, rolling-mean, and local swing levels are computed from completed candles, so targets may be absent or fall back to an ATR risk multiple when no valid support/resistance exists. A winning result over a short market regime is not sufficient evidence for deployment. Compare net PnL after all costs, drawdown, trade count, long/short distribution, and performance across distinct market regimes before changing parameters or considering any live execution.
