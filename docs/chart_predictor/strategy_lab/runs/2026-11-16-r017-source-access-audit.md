# R017: KR/US/crypto market-data access audit

Date: 2026-11-16  
Type: source, access, and rights gate only; no strategy performance test.

## Decision

Do not start a new KR/US performance grid or claim a qualifying strategy yet. No source reviewed here simultaneously proves (a) usable permission for the intended research, (b) complete historical prices and corporate actions, and (c) a point-in-time eligible universe including securities that later delisted. The next useful step is a human-selected, user-controlled source path, followed by a sample integrity/provenance audit before any strategy outcomes are examined.

## Findings

| Market/source | What official material establishes | Remaining limitation / gate |
|---|---|---|
| Korea — KRX OPEN API | KRX lists ETF daily trading information from 2010-01-04 and stock issue information from 2010-01-04. Use requires an application, agreement to the terms, and an individually issued authentication key; the term is one year and the stated cap is 10,000 requests per key per day. The English terms restrict use to non-commercial purposes, prohibit providing KRX data to third parties, and prohibit continued use after the data-use agreement ends. | The reviewed API pages do not state the fee, guarantee complete/delisted history, or establish a historical point-in-time listing universe or adjusted-price/corporate-action completeness. Do not call this a free, survivorship-free feed until those points are independently verified. No key was requested and no data was called. |
| US — Alpaca Basic | Provider documentation lists a $0 Basic market-data plan for US stocks and ETFs, data since 2016, 30 WebSocket symbols, and 200 historical API requests/minute. Free real-time equities coverage is IEX only; SIP is the consolidated all-exchange feed and recent SIP data requires a paid plan. | IEX is one venue, so volume, bars, and intraday signals are not consolidated-market observations. A provider support reply dated 2025-12-18 said it had no historical-assets endpoint; this must be rechecked before use and means the current active-assets list cannot be assumed to be a point-in-time universe. A user account/API key is needed. Neither an account nor a key was created. |
| US — Nasdaq Daily List / CRSP | Nasdaq Data Link describes its Daily List as premium daily listing/de-listing, name/ticker change, and corporate-action data for Nasdaq-listed securities, with history from 1998. CRSP documentation describes daily stock and delisting-return data reaching 1925. | Nasdaq's list is not a complete US OHLCV dataset and its listing is premium. CRSP is a licensed product; no license or price was established. Neither route was acquired. |
| Crypto — Binance USDⓈ-M public streams | Current USDⓈ-M docs describe separate `/public` and `/market` WebSocket routes. The local L2 pilot already routes depth through `/public` and aggregate trades through `/market`; this is a technical feed path, not an authorization finding. | The local tree has no eligible candle database for a fresh broad MTF performance run. Binance Vision's historical-data terms and intended private/manual signal use remain unresolved in R003/R006. No data was downloaded and no new capture was started. |

## Evidence and scope

- KRX service listing: [ETF daily trading information](https://openapi.krx.co.kr/contents/OPP/INFO/service/OPPINFO004.cmd), including the stated 2010 start date.
- KRX API terms: [English terms](https://openapi.krx.co.kr/contents/OPP/INFO/OPPINFO005.jsp), effective 2025-12-26; authentication, duration, non-commercial use, request cap, third-party data restrictions, and termination clauses.
- Alpaca: [market-data plan comparison](https://docs.alpaca.markets/us/v1.1/docs/about-market-data-api) and [market-data FAQ](https://docs.alpaca.markets/us/docs/market-data-faq). The free IEX vs consolidated SIP distinction is material for any intraday/volume strategy.
- Alpaca historical-asset gap: [provider support discussion](https://forum.alpaca.markets/t/delisted-tickers/18227), where an Alpaca representative stated in December 2025 that a historical assets endpoint was not then available. Recheck if this provider is later selected.
- US listing histories: [Nasdaq Daily List](https://data.nasdaq.com/databases/NDL); [CRSP stock data definitions](https://www.crsp.org/crsp_pdf/crsp-us-stock-indexes-databases-data-descriptions-guide-crspaccess/).
- Binance technical stream routes: [USDⓈ-M market-stream documentation](https://developers.binance.info/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/ws-streams/market).

This audit only read public documentation and local repository reports. It did not register accounts, accept terms, issue provider inquiries, download market data, run backtests, or evaluate returns. It was not an independent multi-agent review; a subagent spawn attempt returned `agent thread limit reached`.

## Next gate

1. Korea: the user decides whether to personally apply for a KRX key and accept its current terms. Before any strategy test, verify fee status, data rights for private research, historical symbol/delisting coverage, price adjustment semantics, and a small sample's completeness.
2. US: choose either an explicitly exploratory IEX-only Alpaca sample (not eligible for a full-market strategy claim and still requiring a user account/key), or a user-approved licensed point-in-time price/universe source. No account, purchase, or API credential action is authorized by this audit.
3. Crypto: resolve whether the user's intended manual decisions based on derived signals are permitted for the proposed historical source. Keep the prospective signal protocol frozen; after approval, validate the feed and forward recorder before collecting labeled outcomes.

No strategy qualifies from this audit. The overall portfolio count remains 0/2, and the separate crypto selective-signal objective of at least 80% remains unproven.
