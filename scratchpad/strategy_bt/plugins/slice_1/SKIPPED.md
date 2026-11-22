# Slice 1 - SKIPPED specs (no plugin written)

| spec_id | reason |
|---|---|
| btc-max10-overnight-selected | Needs NYSE close/open data and the NYSE holiday calendar (signal is a 10-day max of NYSE-close BTC prices, exit "next NYSE morning open"). No NYSE-timed BTC series is cached; mapping to UTC session boundaries would be an invented proxy. |
| spx-close-near-low-nextday | Needs S&P 500 index daily OHLC (range > 10 index points). No equity-index data cached; crypto bars would change the instrument and the 10-point filter is index-specific. |
| upbit-low-volatility-top5 | Cross-sectional monthly portfolio of the 5 lowest-vol assets from the Upbit UTHI Top-30 (excl. stable/flagged assets), KRW/BTC Upbit data. Needs Upbit universe + index membership data, and the harness is single-symbol/one-position with no portfolio construction. |
| c4-beam-dca-strategy-monthly | Monthly DCA with multiple stacked lots (pyramiding 500), variable lot sizes by risk band (1x..5x), and partial scale-out exits (qty_percent 6.67/14.28/25/44.44/100) at 'risk' bands of an SMA-of-all-history regression. Harness has one position, fixed notional, no partial exits; initial_capital=0 accounting not representable. |
| c4-pro-trading-art-open-range-breakout-strategy | Opening-range breakout keyed to an exchange clock (09:15 start, 14:xx last entry, 15:00 close in the chart/exchange timezone, NSE-style) with breakeven-lock logic and 'Point' vs 'Percent' modes. Crypto trades 24/7 and the session timezone is not defined by the spec, so any implementation would invent the session mapping. |
| c4-supertrend-with-tp-by-furkan-sancu | Supertrend flip entries are simple, but the archived exit rule is a three-stage scale-out (25% at +2%, 50% at +5%, 25% at +10%, remaining qty reversed on opposite flip). The harness supports one position with a single tp_pct and cannot partially close; collapsing it to a single TP would materially change the strategy. |
