# Phase 8 — Round L four-lane source scan

## Result

**Eligible candidates: 0.** Four independent lanes searched public research,
TradingView/Pine, trading communities, and GitHub/open-source. None yielded a
new, source-complete strategy with causal hourly USD-M inputs, fixed entry,
take-profit, stop, and expiry that was distinct from the tested registry.
No candidate was backtested, downloaded, installed, or executed.

## Lane findings

### 1. Papers and social research

- A public funding-squeeze proposal uses negative realized funding and an
  RSI(14) cross above 30, but only specifies a 2×ATR trailing stop; it has no
  fixed target or expiry. It is incomplete for M2 and overlaps prior funding
  reversal research. [Author research log](https://simplemarkets.io/strategies/research-log/low-timeframe-crypto)
- A funding-carry paper studies cross-asset positions and funding income, not
  a single-contract directional rule with fixed target, stop, and expiry.
  [Paper](https://www.jstage.jst.go.jp/article/jsaisigtwo/2026/FIN-037/2026_168/_pdf/-char/en)
- Perpetual/spot arbitrage requires spot inputs and two-leg execution semantics
  unavailable in this local hourly USD-M panel.
  [Presto Research](https://assets.ctfassets.net/m1hizt3hapq0/2ai7mco2huKGBeWxu9wO8A/25884994fffc3f40d5f9039b44e373c5/Trading_Focus_-3_Optimizing_Funding_Fee_Arbitrage.pdf)
- A BTC funding-fade example shorts after a confirmed funding rate above
  +0.05%, uses a 1% stop and eight-hour hold, but has no fixed profit target;
  it also overlaps previously tested funding contrarian strategies.
  [Rule description](https://stratmill.com/research/en/hypotheses)

### 2. TradingView and custom indicators

- [QZ Trend (Crypto Edition)](https://www.tradingview.com/script/aGjVN33a-QZ-Trend-Crypto-Edition-v1-1a-Donchian-EMA-ATR-Liquidity-F/)
  describes EMA alignment, Donchian breakout, ATR confirmation, ATR stop,
  trailing/breakeven exits, time close, and pyramiding. Exact source defaults
  and a fixed target/stop/expiry could not be established from the inspected
  page; it overlaps Donchian/trend work (registry #76, #98). Excluded.
- [BTC Trading Robot](https://www.tradingview.com/script/Lomcxylm-BTC-Trading-Robot/)
  describes local-high/low stop entries and percentage TP/SL with trailing
  exits, but no fixed expiry. The code and exact parameters were not
  independently verified; breakout overlap and BTC-only scope remain. Excluded.
- Public-script labels did not establish a reusable license or prove the code
  free of repaint/lookahead. No code was copied or executed.

### 3. Community posts

- [Bitcoin Z-score trend system](https://www.reddit.com/r/algotrading/comments/1qgcq2h/sharing_my_bitcoin_systematic_strategy_6592_cagr/)
  describes a 65-period EMA/close-standard-deviation Z-score, entering at an
  upper threshold and moving to cash at a lower threshold. It gives no fixed
  TP, SL, or expiry and is a daily BTC spot trend/state rule. The author's
  performance claims were not independently reproduced. It overlaps existing
  trend/state families (including registry #6). Excluded.
- [MACD BTC/ETH backtest post](https://www.reddit.com/r/algotradingcrypto/comments/1vjkcai/backtest_macd_backtest_on_btceth_across_multiple/)
  discusses 1h MACD-histogram momentum, a zero-axis filter, and 3:1 reward/risk,
  but does not fully specify entry cross, stop formula, expiry, or same-bar
  ordering. It overlaps prior MACD work (registry #18). Author results were
  not independently reproduced. Excluded.

### 4. GitHub and open-source

- [xy3293/crypto-strategy-backtest](https://github.com/xy3293/crypto-strategy-backtest)
  documents Donchian, RSI, Bollinger, Keltner, MACD, and ADX rules and describes
  next-bar entry, stop-first ties, gaps, fees, slippage, and funding. However,
  no distinct, fully fixed M2 candidate emerged; families overlap earlier
  tests, the main examples use 4h, and a usable license was not confirmed.
  Claims in its README were not independently reproduced. Excluded.
- [DitiKrieger/btc-1m-pullback-momentum](https://github.com/DitiKrieger/btc-1m-pullback-momentum)
  appeared in search as a 1m BTC-perpetual ATR-barrier idea, but the repository
  returned 404 during review. Source, rules, license, and hourly compatibility
  are unverified. Ineligible.

## Decision and next gate

There is no Round L candidate to preregister or score. This bounded search does
not establish that no such strategy exists anywhere. Do not fill missing
source rules or attach new exits after the fact. Continue with a distinct
mechanism lane; before scoring any later candidate, require primary-source
rules, registry non-overlap, local input eligibility, and the same frozen M2,
coverage, non-overlap, positive-net, and genuinely unseen-forward gates.
Phase 9 remains blocked because no strategy has passed Core validation.
