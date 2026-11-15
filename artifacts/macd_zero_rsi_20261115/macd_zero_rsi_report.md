# MACD zero-cross + RSI(14)>50 backtest

Status: exploratory; no claim of a validated edge.

Selected exit on training segment: `None`.

## Training results

| Exit | Trades | Win rate (Wilson 95%) | Mean net R | Median net R | PF | Avg hold (min) |
|---|---:|---:|---:|---:|---:|---:|
| macd_zero_down | 537 | 27.6% (24.0%–31.5%) | -0.5618740015198925 | -0.9130088742256821 | 0.37157537837835036 | 66.75046554934823 |
| rsi_below_50 | 537 | 20.3% (17.1%–23.9%) | -0.5384029575790684 | -0.7612608513379159 | 0.3426304563783758 | 52.188081936685286 |
| fixed_2R | 537 | 33.7% (29.8%–37.8%) | -0.5191545090379421 | -0.862689072079862 | 0.3939903297366225 | 63.98510242085661 |
| chandelier_3ATR | 537 | 25.7% (22.2%–29.6%) | -0.55307764515031 | -0.8032173557756328 | 0.3398610645260951 | 62.42085661080075 |
| time | 537 | 29.1% (25.4%–33.0%) | -0.570999897411809 | -1.1170112977057982 | 0.3720494408852851 | 73.27746741154563 |

## Conditional holdout

null

## Limitations

- Only two major coins and 84 days; not generalizable or the 80% accuracy gate.
- Existing research window is not an untouched sealed evaluation.
- No spread, slippage, impact, funding or liquidation model; returns may be overstated.
