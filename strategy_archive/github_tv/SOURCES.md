# Sources searched / opened (retrieved 2026-11-20)

Method: shallow-cloned repos into a scratch directory outside the repo, extracted entry/exit/indicator code with small helper scripts (comment-stripped, regex-filtered), then wrote specs by hand. TradingView source code was fetched through the public `pine-facade` endpoint behind each script page. Extraction is lossy: entries with `mechanical_spec_complete=false` need a read of the source file before coding. Every `source_url` is a file or script page that was actually fetched.

## GitHub (opened)
| Repo | Licence (GitHub API) | Entries |
|---|---|---|
| freqtrade/freqtrade-strategies | GPL-3.0 | ~40 (root, berlinguyinca/, futures/) |
| jesse-ai/example-strategies | MIT | 11 |
| je-suis-tm/quant-trading | Apache-2.0 | 10 |
| mementum/backtrader (samples/) | GPL-3.0 | 2 (most samples are API demos, not strategies) |
| paulcpk/freqtrade-strategies-that-work | MIT | 4 |
| werkkrew/freqtrade-strategies (archived/) | none found (API 404) | 6 |
| i1ya/freqtrade-strategies | none found (API 404) | 2 |

Queries run: `gh search repos "freqtrade strategies"`, `"jesse strategies"`, `"backtrader strategies"` (sorted by stars, top 10 each). The brief also listed vectorbt, quantconnect, zipline, pine-script, crypto-bot, trading-strategy, backtest topics, and `gh search code`: NOT done (time/budget). Awesome-lists (e.g. jesse-ai/awesome-jesse appeared in results) were NOT opened.

Cloned but not extracted (no entries): ysdede/jesse_strategies (CC0-1.0; OttBands, KAMA, fractional, simplema folders - candidates for a later pass), davidzr/freqtrade-strategies (not cloned), keithorange/HUGE_FreqTrade_Strategy_Collection (not opened), ddm-j/NNFX-Backtrader (not opened).
Also in freqtrade-strategies but skipped: `lookahead_bias/` folder (DevilStra, GodStraNew, wtc, Zeus - the folder name signals known lookahead bias), Strategy001_custom_exit, TWAP/AlmgrenChriss execution algos, placeholders.

## TradingView (opened)
- Listing pages fetched: /scripts/strategies/ pages 1-7, /scripts/editors-picks/ (+/strategies/), and tag pages supertrend, breakout, mean-reversion, trend-following, vwap, squeeze, grid, dca, smc, order-block, liquidity, momentum, macd, bollinger-bands, atr, pairs-trading, seasonality, orb, fvg, volume-profile (+ page-2 for several). 611 unique script URLs collected; 42 were `strategy()` scripts, 422 indicators, 132 libraries, 15 unreadable/closed.
- Source retrieved from `https://pine-facade.tradingview.com/pine-facade/get/PUB;<id>/last` for open scripts (`scriptAccess = open_no_auth`).
- 58 TradingView entries: ~30 strategy() scripts + ~28 indicators whose signal rules were inferred; the latter are marked `tradingview_pine_study` and mostly `mechanical_spec_complete=false`.

## Blocked / failed / not reached
- TradingView tag pages returned empty bodies (HTTP success, 0 bytes, possibly rate limited or non-existent tags): ichimoku, ichimoku/page-2, donchian, keltner, rsi, /scripts/strategies/page-8..10. So **no Ichimoku, Keltner or RSI-tag scripts were collected from TV** (only 1 Ichimoku entry from GitHub).
- `?sort=popular` and `editors-picks/strategies/` URLs returned the same generic page (sorting not honoured server-side), so "popular" and "editors' picks" ordering was not actually obtained. The editors-picks main page was fetched but is mostly indicators.
- scripts.tradingview.com: DNS resolution failed.
- TradingView "most popular all-time" strategies (the well-known ones) were NOT reached; the corpus above skews to recent, mostly low-follower scripts, many by a few prolific authors (e.g. blitz_algo), some possibly auto-generated. Quality is uneven; do not assume these are validated.
- Not reached at all: QuantConnect, vectorbt, zipline, Pine-script GitHub repos, academic/community lists (the other agent's area). Seasonality, funding/basis and Ichimoku coverage is therefore thin.
- Count: 138 strategies archived vs the 150+ target. Shortfall is real, not hidden by padding.
