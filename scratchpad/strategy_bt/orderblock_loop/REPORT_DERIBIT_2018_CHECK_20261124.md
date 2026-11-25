# Deribit 2018 BTC Perpetual Availability Check

**Checked:** 2026-11-24  
**Purpose:** Determine whether Deribit can add a 2018 BTC-only stress input. This check does not change the 30-symbol, PIT, or G gates.

## Local inventory checked

The source catalog says Deribit funding data begins in 2019 and points to existing files under TRADING_DATA_DIR/external/crypto/misc/. Filename/stat-only inspection found deribit_funding_BTC-PERPETUAL.json (10,333,830 bytes), deribit_funding_ETH-PERPETUAL.json (10,239,122 bytes), and BTC/ETH DVOL JSON files. Existing JSON contents were not opened or re-downloaded.

## Official documentation and terms

- Deribit announced its perpetual product on 2018-08-14. The launch article describes a BTC perpetual product; it does not establish a broad 2018 multi-coin panel. [Deribit launch announcement](https://insights.deribit.com/exchange-updates/introducing-the-deribit-perpetual/)
- The public funding endpoint returns hourly history for a named perpetual over a caller-supplied timestamp range. The public chart endpoint documents OHLCV chart data for a named instrument and interval. Neither page states the earliest retained timestamp. [Funding history API](https://docs.deribit.com/api-reference/market-data/public-get_funding_rate_history), [chart data API](https://docs.deribit.com/api-reference/market-data/public-get_tradingview_chart_data)
- Current Deribit membership terms restrict market-data use to personal use; processing/redistribution beyond personal use requires prior written approval. Deribit’s API guidance describes unauthenticated access to public information but warns that unauthenticated clients are subject to stricter rate controls. [Membership terms](https://support.deribit.com/hc/en-us/articles/25944532191645-Deribit-Exchange-Membership-Terms-Deribit-FZE), [API usage policy](https://deribit1692970334.zendesk.com/hc/en-us/articles/33675340208925-API-Usage-Policy)

## One-point public API check

After checking the personal-use terms, two unauthenticated, one-hour requests were made for BTC-PERPETUAL, 2018-08-15 00:00–01:00 UTC. The script held responses in memory and printed only status/count/timestamp metadata; no price or funding values were printed or saved.

| Endpoint | HTTP/API result | Returned record count | First timestamp |
|---|---|---:|---|
| public/get_funding_rate_history | HTTP 200, API result present | 0 | None |
| public/get_tradingview_chart_data | Python HTTPError; the wrapper did not capture the numeric HTTP status or body | Unknown | Unknown |

The funding request did not return a record for this selected hour. The OHLC request failure is inconclusive: it may reflect unavailable history or request rejection. No retry was made, so this audit does not claim that Deribit’s entire 2018 OHLC history is absent.

## Relevance to the strategy gates

No additional eligible 2018 contract was confirmed. Even if BTC 2018 OHLC becomes available, one BTC series cannot replace the existing 30-symbol, PIT, untouched-universe, cost, or funding requirements. At most it could serve as a separately preregistered BTC stress supplement if full OHLC/funding coverage, fee assumptions, and data-use eligibility are established. The empty funding result prevents treating this selected hour as validated funding coverage.

No account, API key, paid service, access bypass, bulk request, TEST/OOS input, post-2026-05-31 data, or shared trial ledger was used. No code or market-data file was changed.
