# Crypto market-data rights update — 2026-11-19

## Decision

**A plausible licensed historical BBO path is now identified, but no data has been acquired and the live Binance feed's use rights remain unresolved.** Binance Vision archives and Binance live public API are distinct interfaces. Tardis's current terms, last modified 2026-10-28, expressly define an individual customer as a Customer User and include systems operated by the customer or its users. They list personal research/trading as a Permitted Use and allow internal model development and confidential service-provider processing, subject to applicable exchange licensor restrictions. This makes Tardis a materially stronger historical-data route than was recorded in earlier dated notes. No account, trial, purchase, provider contact, sample download, or market-data download was initiated.

## Binance Vision historical archives

The official Vision Dataset Terms currently identify themselves as version 1.0, last updated 2026-08-26. They apply to accessing and using the datasets and derived data, including charts, models, and analytical indicators. The terms grant a CC BY-NC-SA 4.0 license subject to additional conditions; permitted non-commercial uses include purely personal non-production historical backtesting. They expressly exclude commercial licensing and prohibit use for live proprietary trading execution, automated commercial order generation, and compensated third-party signal distribution. They also require compliance with published access limits and prohibit scripts designed to circumvent restrictions.

The existing user-approved scope for Vision is **historical backtesting only**. Do not use Vision data or outputs to produce live/manual trading signals, orders, or a feed. Historical data must not be newly downloaded under this task without a source-specific reason and the already-defined storage/provenance gates.

Primary source: [Binance Public Data — Vision Dataset Terms](https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md).

## Binance live public API

Official Binance developer documentation distinguishes public market-data endpoints and WebSocket streams from authenticated account endpoints. The Spot `Market Data Only` FAQ says the `data-api.binance.vision` REST endpoints and `data-stream.binance.vision` market streams require no authentication and serve public market data. This establishes that a key is not required for those documented transports; it does **not** itself grant a data-retention, model-training, or derived-signal license. The official Spot API repository's production-terms page points users to Binance's general Product Terms of Use rather than providing a market-data-specific grant. The API Key Product Terms apply to API keys; they do not, by their own scope, settle rights for keyless public market-data access. Conversely, none of these reviewed sources expressly prohibits the intended personal-use pipeline.

The current Binance Terms of Use grant a limited license to use Binance IP as necessary to receive Binance Services for non-commercial personal/internal use, while incorporating other product, exchange, and policy terms. The reviewed text does not clearly define whether persistent storage of public market feeds or sending derived alerts to the same individual for discretionary manual trading is covered by that limited license. Therefore this general clause is not treated as a definitive authorization for the intended capture-and-alert use.

Primary sources: [Binance Spot REST API — general information](https://developers.binance.com/en/docs/products/spot/rest-api), [Binance Spot Market Data Only FAQ](https://github.com/binance/binance-spot-api-docs/blob/master/faqs/market_data_only.md), [Binance Spot API production terms pointer](https://github.com/binance/binance-spot-api-docs/blob/master/PROD-TERMS-OF-USE.md), [Binance Terms of Use](https://bin.bnbstatic.com/static/cms/cg08ou2ak0tn7mcplvfg/file/47a848de135d5747a84c1f66307920fe3d23eca2f500accc64e136f1499ba387.pdf), and [API Keys Product Terms](https://bin.bnbstatic.com/static/cms/cg08ou2ak0tn7mcplvfg/file/826cc99cc3847cd017dc7b82525896f01ac211d9c177573d8ea958402766d965.pdf). [Binance API Product Page Guidance](https://www.binance.com/en/support/faq/detail/865f0fe3cb6a4d73a21609b3b7326f31) identifies applicable agreement families but is itself an FAQ, not the controlling legal agreement.

**Status: rights unresolved for the intended live/manual-signal pipeline.** The strongest current evidence is keyless technical availability plus a general non-commercial personal/internal-use license, but neither source expressly resolves persistent market-data capture or derived discretionary alerts. This review does not claim Binance prohibits that use. Do not start persistent capture or use resulting data for signals until controlling product terms for the user's jurisdiction and intended use are identified and reviewed.

## Tardis historical order-book data

The current Terms of Service page says “Last modification date: 2026-10-28.” It defines the individual Customer as a Customer User, defines Customer System to include systems owned or operated by the Customer or its Customer Users, and describes personal purposes (including research and trading) as Permitted Use. Clause 9.1 allows storing data on the Customer System; clause 9.5 permits developing the customer's own models for the Permitted Use; and clause 9.6 permits service providers such as cloud hosting and data processors to process it on the customer's behalf if they keep it confidential and do not use it for themselves. Clause 9.7 says data independently obtained from exchanges remains subject to the relevant provider's terms, and clauses 9.4/10.4 preserve applicable licensor restrictions.

The official Binance USDT Futures historical-data documentation lists native `bookTicker` among captured channels and states historical coverage begins 2019-11-17, with a collection-quality caveat before 2020-05-14. Tardis's `book_ticker` documentation defines it as the native exchange BBO feed, distinct from a quote derived from L2. These documents identify a promising source for historical executable-price research; they do not guarantee complete symbol/date coverage or remove Binance/licensor constraints.

**Status: contract text supports a historical personal-research route in principle, subject to plan-specific terms, data availability, applicable exchange/licensor restrictions, and compliance with the agreement.** This is not an account, purchase, or dataset approval. Before use, the exact dataset coverage, price/plan, and applicable restrictions must be reviewed; no paid or trial access was initiated.

Primary sources: [Tardis.dev Terms of Service](https://docs.tardis.dev/legal/terms-of-service), [Binance USDT Futures historical-data details](https://docs.tardis.dev/historical-data-details/binance-futures), and [Tardis data types](https://docs.tardis.dev/downloadable-csv-files/data-types).

## Published access cost and storage screen

The official pricing page currently lists the **Solo Derivatives** plan at **USD 700/month**. It lists CSV downloads for Solo, while raw replay API and Tardis Machine are unavailable on Solo. The billing FAQ says Solo subscriptions include 4 years of historical data with yearly billing, 12 months with quarterly billing, or 4 months with monthly billing. The lower Academic price is not assumed applicable; that plan requires eligibility confirmation. Prices and access terms can change, and no checkout was opened.

Earlier metadata-only work in `crypto-microdata-readiness-2026-11-19.md` measured the advertised compressed size of a single 2026-11-01 `book_ticker` sample for the frozen 20-symbol cohort at 520.6 MiB; no body was downloaded. This gives an order-of-magnitude storage screen only. Daily volume is variable, so multiplying that one-day figure by a month is not a verified monthly estimate. The current live check also found `/Volumes/HDD2TB` absent. Therefore the existing local+NAS archive requirement is unsatisfied, and no sample/history batch should be acquired until storage is restored and capacity is explicitly estimated from authorized metadata.

Primary sources: [Tardis pricing](https://tardis.dev/), [Tardis billing and subscriptions](https://docs.tardis.dev/faq/billing-and-subscriptions).

## Research consequence

1. Keep Binance Vision historical work isolated to approved offline, non-production backtests.
2. Keep public Binance live WebSocket feasibility separate from rights approval; transport feasibility is not data-use authorization.
3. Treat Tardis historical Binance Futures BBO as a viable source candidate for a separately approved and preregistered historical study; first verify exact symbol/date availability, total cost, current applicable terms/licensor restrictions, and the user's existing local+NAS storage requirement. Do not create an account, begin a trial, purchase, or download without authorization.
4. Do not open the live-feed market-label gate or start a long prospective capture until Binance live API storage/derived-signal rights are separately established and the archive destination is present and verified.
5. No change is made to strategy acceptance criteria, frozen candidate rules, or prior results. Existing exposed-history experiments remain development evidence only.

## Review boundary

This is a source-document review, not legal advice or a jurisdiction-specific legal opinion. The Tardis terms are public contract text, but the exact subscription, exchange-data restrictions, jurisdictional application, and product coverage must still be checked before acquiring/using data. No Binance product contract beyond the cited developer/FAQ pages was established as controlling for live data use. The current project rule remains: record the exact source, terms version, permitted storage/derived-use scope, and system locations before ingestion.
