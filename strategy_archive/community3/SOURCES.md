# Sources and collection log

Retrieved date recorded in strategy records: 2026-11-20. Search and page access used the web search/open interface. Strategy URLs in JSON and INDEX point to pages opened directly, except Reddit records where the search result exposed rules but direct open failed; those are flagged in the JSON.

## Sources yielding strategy material

- QuantConnect Strategy Library: https://www.quantconnect.com/docs/v2/writing-algorithms/strategy-library — opened successfully. Its strategy summaries describe portfolio rules for momentum, reversal, factors, calendar effects, futures spreads, and options. The summaries often omit timing, exit, thresholds, and portfolio details; records from this page are consequently marked incomplete and priority 3 unless details are explicit.
- QuantConnect RSI forum post: https://www.quantconnect.com/forum/discussion/15754/an-overview-of-a-simple-rsi-based-trading-strategy/p1 — opened successfully. Explicit SPY daily RSI(2)<15 long and close-over-prior-high exit; author reports a historical backtest, which remains a forum claim.
- QuantConnect forum strategy discussion: https://www.quantconnect.com/forum/discussion/14983/help-with-my-strategy/ — opened successfully. Describes an hourly FX Bollinger lower-band recross concept and proposed prior-low stop / 2R target; it is a user's proposed system, not evidence of tested performance.
- QuantConnect universe RSI post: https://www.quantconnect.com/forum/discussion/1401/universe-based-rsi-selection/p1 — opened successfully. Documents EMA(60) distance bands, RSI(3) confirmation, and S&P 500 universe mean-reversion logic.
- Reddit r/algotrading: https://www.reddit.com/r/algotrading/comments/1lmrjl6/updated_bollinger_band_vwap_breakout_strategy/ — opened successfully. Explicit BTC H1 Bollinger/VWAP/RSI/ADX entry and exit rules.
- Reddit r/Daytrading: https://www.reddit.com/r/Daytrading/comments/1ln0lpm/im_getting_a_lot_of_questions_about_my_strategy/ — opened successfully. 9/19 EMA trend pullback scalp; the author identifies discretionary judgments and does not claim consistent profitability.
- Reddit r/Daytrading: https://www.reddit.com/r/Daytrading/comments/1vj6za8/vwap_with_1st_2nd_bands_trading/ — opened successfully. Session VWAP band bounces with a 21 smoothed EMA directional gate; exits are missing.
- Reddit r/TradingView search results exposed candidate MACD/RSI and RSI-SMA/MACD histogram rules, but direct page opens failed. Those candidates were excluded because the URL-open requirement was not met.
- Elite Trader: https://www.elitetrader.com/et/threads/trading-strategy.23438/ — opened via search result with exact 50 EMA/RSI-band breakout and ATR stop/trailing rules.
- Elite Trader: https://test.elitetrader.com/et/threads/an-effective-swing-trading-strategy.237496/ — opened via search result with hourly EMA(5/12), RSI(14), Force Index(14), 100-pip stop, and 250-pip target.
- Elite Trader search surfaced a five-minute E-mini multi-signal checklist, but direct open returned HTTP 403, so that candidate was excluded.
- YouTube search returned a candidate VWAP+pivot video, https://www.youtube.com/watch?v=IdfLK-sLjsA, whose description states VWAP-side plus pivot crossing, pivot-to-pivot targets, and VWAP-relative stops. It was not added because the description does not give enough precise stop/re-entry/trailing thresholds to create a faithful mechanical record.

## Required source families searched and access/results

- Reddit: `web search` returned usable rules; some opened successfully. Reddit JSON API was not used. Direct opens for the two TradingView subreddit candidates failed with fetch error/cache miss and those candidates were excluded. No other subreddit result with independently explicit rules was accepted from the search batch.
- X/Twitter: searched for public trading-strategy threads with explicit entry/exit rules. Search did not return a directly usable, openable thread; no X-derived strategy was added. This is a coverage gap, not evidence that no such threads exist.
- QuantConnect: Strategy Library and forum posts opened and supplied most records. A separate forum page at https://www.quantconnect.com/forum/discussion/18176/ could not be fetched. The Strategy Library summary is a catalog, not a full specification for every entry.
- Elite Trader: indexed discussion pages returned explicit rule sets and were used. Generic thread index access was unavailable/not useful; collection used individual indexed discussion pages.
- Forex Factory: https://www.forexfactory.com/forum/71-trading-systems?order=desc&sort=replycount returned HTTP 403 Forbidden when opened. Search snippets listed thread titles but did not yield sufficiently complete rules for inclusion.
- BabyPips: https://forums.babypips.com/c/forex-strategies/ was inaccessible to the open tool. Search did not surface an individually usable rules page in the search batch; no strategy added.
- TradingView ideas: https://www.tradingview.com/ideas/ opened, but the landing page was a stream rather than an exact educational post. Its visible example was discretionary market-structure analysis without complete entry/exit mechanics. No item added from that landing page.
- YouTube: a search result provided the VWAP+pivot description noted above, but key execution details were not explicit enough; not included. A second VWAP video result did not provide exact rules in its description. YouTube video transcripts were not retrieved.

## Exclusions and evidence limits

Search result snippets were not treated as opened pages for source claims except where explicitly marked above. No strategy was backtested or independently evaluated. `backtest_shown` means only that the cited poster presented backtest results; it is not a validation finding. `anecdote` covers practitioner/forum/library-summary material without peer-reviewed evidence. QuantConnect library records are deliberately conservative: fields left unknown are null or explicitly described as unspecified, and their completeness is false.
