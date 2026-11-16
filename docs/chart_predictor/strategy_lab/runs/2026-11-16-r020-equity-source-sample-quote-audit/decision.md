# R020 decision — no equity performance test is data-ready

**Do not begin the KR/US stock-and-ETF strategy backtest yet.** The public-source check confirms candidate providers, not a usable, licensed, reproducible point-in-time dataset.

- KRX documents daily KOSPI stock history from 2010-01-04, but API use requires account authentication and approval. The official marketplace places product-specific sample and price details behind login.
- CRSP publicly describes active and inactive US securities, corporate actions, permanent identifiers, and delisting information. Its official sample guide directs users to request samples/demo; current pricing is not publicly posted on the sources reviewed.
- No account was created, no sample/license was obtained, no purchase was made, and no vendor was contacted. No market rows or performance metrics were read.
- ETF breadth, point-in-time universe definitions, adjustments, and research-use terms remain open for both providers.

## Next gate

Select one provider only after the user has access to product-level samples and quotes. For KRX, the user must log in to inspect relevant stock and ETF products and their sample/price fields. For CRSP, a sample/quote requires a vendor request; do not send it or provide user contact details without explicit authorization and the user's chosen contact identity. Then inspect the delivered sample under its license and preregister the equity test before reading strategy metrics.

This source audit has no result on whether any strategy beats Buy-and-Hold.
