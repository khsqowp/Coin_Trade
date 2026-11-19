# Cross-market data-path update — 2026-11-19

## Purpose and decision

This memo records a read-only source and terms review prompted by four independent strategy/data reviews. It does not contain a market-data download, account creation, purchase, provider contact, or strategy-performance result. The research objective remains maximum compounded net returns across regimes; the existing per-market acceptance gates remain unchanged.

**A lower-cost US EOD source and a no-key crypto historical sample route now merit a bounded eligibility check. Neither is yet an approved backtest input.** Korean equities remain blocked on an authorized, reproducible PIT/delisted/corporate-action dataset. No strategy candidate is promoted by source availability alone.

## United States stocks and ETFs

EOD Historical Data's official personal-plan page lists an EOD All-World plan at USD 19.99/month (or USD 199/year), with 30+ years of EOD history, delisted tickers, and splits/dividends. Its free tier is limited to 20 API calls/day and one year of EOD history; the documented `demo` key covers only selected symbols, including AAPL, MSFT, TSLA and VTI. [Pricing](https://eodhd.com/pricing), [plan details](https://eodhd.com/help/plans)

Material limitations prevent treating that catalog claim as full PIT qualification:

- EODHD says historical series are not point-in-time versioned; corrections overwrite prior records. Dated snapshots are needed to reproduce provider vintages.
- Delisted ticker history is explicitly “as is”; coverage can contain gaps or end before the last trading day, with no completeness guarantee.
- Historical S&P 500 membership is documented, but reliability begins in April 2012; pre-April-2012 exits are missing. PIT membership for other indices requires a separate Marketplace product.
- The provider says plan access does not guarantee any ticker, field, interval, or date range will be complete or available.

These limitations are stated in EODHD's [data methodology](https://eodhd.com/help/methodology), [Fundamentals API index-constituent documentation](https://eodhd.com/financial-apis/stock-etfs-fundamental-data-feeds), and [plan FAQ](https://eodhd.com/help/plans). The free demo/free plan can support a schema or endpoint smoke test only; it cannot validate broad-universe OOS CAGR, MDD, Sharpe, or 200 OOS round trips. A paid EOD plan is a candidate for a fixed ETF-universe feasibility audit, not a proven replacement for a survivorship-free US-equity dataset.

## Korea stocks and ETFs

KRX's official Open API lists daily KOSPI, KOSDAQ and ETF data from 2010-01-04, but access requires registration, identity verification, an API-key application and approval; the documented request cap is 10,000 per key per day. The available public service listing does not establish complete point-in-time membership, delisted-security return coverage, full corporate-action treatment, or permission for the requested Mac+Linux mirrored archive. [KRX service list](https://openapi.krx.co.kr/contents/OPP/INFO/service/OPPINFO004.cmd), [KRX terms](https://openapi.krx.co.kr/contents/OPP/INFO/OPPINFO002.jsp)

No KRX account, key request, data download, or provider inquiry was made. The existing free-library/scraping options remain unqualified for PIT survivorship-safe performance claims. The two KR strategy ideas from the independent review are research hypotheses only: the weekly 126-day ETF momentum proposal overlaps a previously recorded unregistered proposal; earnings-surprise drift lacks timestamped, historical-vintage consensus and filing data.

## Crypto futures

Binance Vision remains authorized here only for personal, non-commercial historical backtesting; it is not a source for live/manual discretionary signal delivery. Its raw-trades sample had eight severe row-level `quote_qty` anomalies despite valid publisher checksums; primary quote-field reconciliation therefore failed the preregistered sample gate. The separately derived `price × qty` totals matched the native minute quote aggregates in the sampled minutes, but this is exploratory evidence, not universal certification or a strategy feature. See the [integrity report](binance-trades-kline-integrity-results-2026-11-19.md) and [Binance Vision terms](https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md).

Tardis currently offers first-day-of-month historical CSV samples for each exchange/data type without an API key, plus a one-month trial covering days 1–10 of the prior UTC month with 20 GB of data transfer. The trial requires an account; no trial was started. Its current terms define personal research/trading as permitted use, permit storing/copying on a Customer System, permit own-model development for Customer Users, and permit service providers to store/process on the customer's behalf under confidentiality conditions. They also preserve exchange/licensor restrictions and prohibit redistributing raw data outside Customer Users. This is a materially stronger personal-use route for historical BBO research, subject to exact symbol/date coverage, current plan/data restrictions, and applicable licensor terms. [Trial/sample terms](https://docs.tardis.dev/faq/billing-and-subscriptions), [Tardis Terms of Service](https://docs.tardis.dev/legal/terms-of-service)

An earlier metadata-only check estimated 520.6 MiB compressed for a one-day `book_ticker` sample across the frozen 20-symbol cohort. This is only a single-day storage estimate, not a verified period total. The required `/Volumes/HDD2TB` destination was absent at the last check. Therefore no Tardis sample or historical batch was downloaded. Free sample availability does not waive the project's verified local+NAS storage requirement.

## Strategy research implication and next gate

The four read-only reviewers found no strategy result that meets the fixed adoption gates. They proposed distinct candidate families for future review, but no candidate has OOS performance evidence:

- US: 20-day market-residual oversold reversal and absolute-trend filtered ETF momentum. Both require a duplicate check against prior momentum/reversal records and valid corporate-action/universe histories.
- KR: ETF relative-strength rotation duplicates a prior unregistered candidate; earnings-surprise drift requires point-in-time filings and consensus vintages.
- Crypto: no new candidate cleared novelty and executable-path review. A 1-minute OHLC/taker-flow micro experiment is not M2 or portfolio return evidence; the M2 ≥80% gate remains unmet by prior exposed cells.

The highest-value next action is source eligibility, not a strategy sweep: (1) restore and verify the authorized local+NAS archive, (2) use no-key published metadata/sample information to validate data schemas and selected-symbol coverage without starting an account or downloading a large dataset, (3) resolve one frozen, nonduplicate candidate per market, and (4) only then decide whether the permitted free sample suffices for a narrowly defined, outcome-blind pilot. No paid subscription, account, trial, or strategy run is authorized by this memo.

## Objective and accounting

Optimize compound net wealth across bull, bear, and sideways regimes. Do not maximize hit rate at the expense of cost-adjusted expectancy or compounding. Keep the user's stock/ETF gates (net CAGR ≥20%, MDD ≤30%, Sharpe ≥1, OOS ≥200 closed trades) and crypto M2 ≥80% plus all sample, coverage, diversity, uncertainty, and positive-net-expectancy gates as acceptance constraints. Report regime-specific return and risk; do not claim one strategy succeeds in all regimes without chronological evidence.
