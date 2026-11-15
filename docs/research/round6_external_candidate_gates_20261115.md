# Round 6 external candidate research and local-data gates

Status: literature/data-source hypotheses collected from four independent research roles. Only the BTC impulse/altcoin underreaction candidate has been replayed locally; its result is in [`crypto_btc_lead_alt_lag_results_20261115.md`](crypto_btc_lead_alt_lag_results_20261115.md). The remaining candidates below are **not tested and are not established strategies**.

## Korea — domestic ETF NAV discount reversal

**Hypothesis:** among Korea-listed domestic-equity index ETFs, a large discount of market close to same-time NAV/iNAV predicts partial price reversion on the next session. The signal is known only after the close; any entry must occur on the following session. Exclude overseas assets initially to reduce valuation/market-hours mismatch.

**Why it is a distinct candidate:** prior Korean ETF research reports next-day price movement associated with close-to-NAV deviations. This is a mechanism hypothesis, not evidence of current net alpha. KRX explains that intraday estimated NAV and end-of-day NAV have different calculation/publication context; the input series must use the value actually available at each decision time. [KRX NAV and divergence overview](https://www.krx.co.kr/contents/OPN/01/01030203/OPN01030203T1.jsp), [Korean ETF price-efficiency study](https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=ART001644811).

**Local gate:** the last local cache inventory found only daily OHLCV (no intraday timestamps), so it does not establish historical, point-in-time iNAV publication values, ETF listing/delisting history, distribution/creation-unit actions, or next-session executable quote prices. Existing daily OHLC files cannot prove a tradable result. First obtain a versioned, rights-cleared NAV/iNAV vintage plus security-state and corporate-action records; then verify next-session spread/quote execution. Until those inputs exist, no backtest number is admissible. Inventory evidence: [`DATA_AVAILABILITY.md`](equity_transfer_2026-10/DATA_AVAILABILITY.md).

## United States — NYSE opening-auction imbalance reversal

**Hypothesis:** for NYSE Tape A common stocks, an extreme final pre-open auction imbalance predicts a short reversal after the opening auction. A proposed fixed design uses the last public imbalance normalized by paired quantity, compares it with that security's trailing 60-session distribution, and measures the signed change from auction price to 9:35 ET. Any executable strategy evaluation must separately use post-open executable NBBO prices.

The combination of auction imbalance and intraday reversal is a proposed test, not a finding established by either source. NYSE's imbalance specification describes the event feed and its message semantics; a historical feed archive and access rights are still unverified. [NYSE XDP Imbalances Feed specification](https://www.nyse.com/publicdocs/nyse/data/XDP_Imbalances_Feed_Client_Specification_v2.2.pdf), [NYSE auction-dynamics research](https://arxiv.org/abs/1802.01921), [US intraday return-pattern research](https://arxiv.org/abs/1005.3535).

**Local gate:** the local stock cache inventory has no intraday timestamps, and no second-level auction-imbalance/NBBO archive is present in the existing research records. A valid test also needs historical symbol changes, listings/delistings, corporate actions, trading halts, and the contemporaneous universe. A present-day surviving-stock list or daily OHLC cache cannot test this event. Do not substitute daily bars or a different exchange feed and call it equivalent. Inventory evidence: [`DATA_AVAILABILITY.md`](equity_transfer_2026-10/DATA_AVAILABILITY.md).

## Crypto — 1–5 second public order-flow imbalance

**Hypothesis:** issue a selective direction only when best-quote OFI and aggressor-trade imbalance over the preceding two seconds agree, with a pre-fixed extreme-OFI threshold and spread/depth quality limits. Score next 1–5 second midprice direction and signal coverage separately. This is a research candidate, not an established signal; a high hit rate on midprice is not proof of fillable or profitable execution.

Binance USDⓈ-M provides public aggregate-trade, diff-depth, and kline WebSocket stream families. Depth updates are deltas that require correct snapshot synchronization and update-ID gap handling; losing sequence continuity invalidates the reconstructed book until resynchronized. Klines are context bars, not a substitute for the event order needed for sub-minute OFI. [Aggregate Trade Streams](https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams/Aggregate-Trade-Streams), [Diff. Book Depth Streams](https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams/Diff-Book-Depth-Streams), [Kline/Candlestick Streams](https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams/Kline-Candlestick-Streams), [primary OFI study](https://arxiv.org/abs/1011.6402).

**Local gate:** the available research DB stores 1-minute OHLCV only; it has no historical depth deltas, synchronized book snapshots, or individual trade tape. Therefore this candidate cannot be honestly backtested from current local files. A new prospective recorder would need event time, local receive time, trade IDs, depth update IDs, sequence-gap flags, reconnect periods, and queue-lag/clock-health measurements. Archive data loss must be reported as unusable intervals, not silently forward-filled.

## Crypto — perp/index premium and BTC-relative volatility alternatives

The crypto agent also proposed (a) an extreme 15-minute perp/index-premium move confirmed by 1-hour premium direction, with continuation and convergence treated as separate hypotheses, and (b) an altcoin BTC-relative residual trend gated by BTC's high realized-volatility state. Neither has been run. The BTC-relative lag hypothesis was tested separately and rejected in the development replay; do not conflate that result with these distinct premium/volatility rules. The local candle DB lacks a verified point-in-time premium-index and funding-history panel, so test these only after those synchronized features and their publication times are available.

## Next research order

1. Preserve the rejection of the fixed BTC impulse/alt lag candidate; do not retune it on the same historical period.
2. If short-horizon crypto research is prioritized, begin a separate public WebSocket data-quality pilot for trades and depth; no signal backtest is possible until adequate contiguous event history exists.
3. For Korean ETFs, first audit whether KRX historical iNAV values have accessible publication vintages and compatible delisted ETF records.
4. For US auction imbalance, first audit NYSE feed archive rights/cost and independent PIT security-master/NBBO availability.

No market-order APIs, credentials, live positions, server deployments, or trading actions are involved in this research note.
