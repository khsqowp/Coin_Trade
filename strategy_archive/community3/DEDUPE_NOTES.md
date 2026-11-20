# Dedupe notes

## Prior archive comparison

Read every JSON in `trading/strategy_archive/community/strategies/`, `community/INDEX.csv`, and `community2/INDEX.csv` before collection. Existing strategy IDs and concepts were not recopied as such. Excluded families/concepts included:

- Community rolling BTC 5/10/20/30/40/50-day high/low variants, combined 10-day high/low rule, overnight MAX(10), Monday calendar effect, SPY opening-range breakout, IBS/range rebound, close-near-low dip, and four-lower-high reversal.
- Community2 UTC session allocation and all long/short/reversal/momentum/cash combinations; BTC/ETH daily/session return variants; Donchian/Keltner/Bollinger/EMA/MACD/ADX/Supertrend/Parabolic SAR/ROC and StochRSI configurations; Turtle 1/2; funding/carry/basis families; crypto pair funding, options, whale, and cross-venue variations; QQQ/BTC rotation; Elder Triple Screen; Connors RSI(2); Raschke Holy Grail; RSI(7) reversal; and Upbit-specific rules.

## Merges and duplicate removal within collection

Repeated summary concepts encountered while drafting from the QuantConnect Strategy Library were collapsed to one record; parameterizations or paraphrases were not retained as extra strategies:

- SPY buy-at-close/sell-at-open daily overnight anomaly kept as `qc-overnight-anomaly`; a second draft `qc-overnight-session-repeat` was removed.
- Option-expiration-week exposure kept as `qc-options-expiry-week`; a second calendar draft was removed.
- Cheapest-third country ETF by CAPE kept once; duplicate draft `qc-value-cape-country` was removed.
- January-positive equity / otherwise T-bills filter kept as `qc-january-barometer`; duplicate draft `qc-market-january-filter` was removed.
- Commodity roll-yield plus one-month momentum combination kept once; duplicate draft `qc-commodity-dual-sort` was removed.
- SPY turn-of-month and pre-holiday rules each kept once; second drafts `qc-turn-month-equity` and `qc-preholiday-equity` were removed.
- Several strategies share a broad family label (momentum, calendar, or value) but have different ranking variable, universe, horizon, or position rule; they remain separate hypotheses, not mere indicator parameter variants.

Remaining overlap risk: the QC Strategy Library is a catalog and some descriptions are intentionally short. Records are distinct by the source-stated construction, but a full linked tutorial may reveal shared implementations or additional rules. No backtest/code work was done to resolve this.
