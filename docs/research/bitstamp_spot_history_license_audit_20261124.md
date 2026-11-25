# Bitstamp Spot OHLC: History, Symbol Coverage, and Rights Audit

**As of:** 2026-11-24  
**Scope:** Official Bitstamp historical-data/API documentation and published terms only. This is a source-qualification memo, not a data collection or strategy result.

## Decision

Bitstamp's public REST API is a plausible *spot OHLCV candidate*, but the official public materials reviewed do not establish that the 30 common assets have continuous Bitstamp candles for 2018 and 2022, preserve historical/delisted market symbols, or grant non-commercial backtesting/storage rights. Therefore it cannot currently qualify as a replacement data source for the futures R4 test, or as a proven complete spot panel.

## Sourced facts

1. The official API documents `GET /api/v2/ohlc/{market_symbol}/` with supported intervals including 86,400 seconds (daily), OHLC, volume, `start`/`end` Unix timestamps, and a maximum result `limit` of 1,000. The docs show no authentication declaration for that GET operation, while separately stating all private API calls require authentication. The timestamp parameter range accepts old Unix timestamps, but this alone does **not** establish that records are retained or returned back to a specific date. The page's description of supplying both `start` and `end` says `end` is used, so the exact pagination contract should be validated before collection.
   - [Bitstamp API documentation — OHLC section](https://www.bitstamp.net/api/#tag/Market-data/operation/GetOHLC)
2. The public `GET /api/v2/markets/` endpoint is described as the list of all *available* markets. Its market objects include current pair symbols and status fields such as `trading` and `matching`. The documentation contains no dated historical market catalogue, listing start date, delisting date, or stable security ID history.
   - [Bitstamp API documentation — Markets section](https://www.bitstamp.net/api/#tag/Market-info/operation/GetMarkets)
3. The API page states a standard ceiling of 400 requests/second and a default threshold of 10,000 requests per 10 minutes; higher limits require request and a bespoke agreement. These limits describe request rate, not historical coverage or a bulk-data entitlement.
4. The API documentation says companies using Bitstamp exchange data for commercial purposes must contact Bitstamp and sign a commercial-use Data License Agreement. It also says commercial incorporation and redistribution are permitted under that agreement. The same public page does not affirm a non-commercial personal-backtesting or local-retention license. The absence of a stated commercial requirement for personal use is not proof that personal backtesting rights are granted.
   - [Bitstamp API data-use statement](https://www.bitstamp.net/api/#commercial-use-of-bitstamp-s-exchange-data)
5. The Coin_Trade `data_sources/CRYPTO_SOURCES.md` catalog (compiled 2026-11-20) records Bitstamp REST OHLC as a free source, up to 1,000 rows/request, with an estimated 2011+ coverage and a `ToS` note. That catalog does not record a 30-symbol historical coverage check, a historical delisted-pair list, or an explicit grant for non-commercial backtesting. The `2011+` value is catalog metadata, not a current per-symbol coverage proof from this audit.
6. The current checkout contains `scratchpad/strategy_bt/orderblock_loop/universe/CRYPTO_35.csv`, an **untracked** 35-symbol cohort for the futures research loop. Its presence does not establish that these assets were Bitstamp spot markets in 2018/2022, or that this futures cohort is the intended/eligible 30-symbol Bitstamp spot universe. No preregistered Bitstamp-specific spot cohort was identified in the source materials reviewed for this task.

## Gate results

| Requirement | Result | Basis / gap |
|---|---|---|
| Daily OHLCV capability | **Documented** | API schema supports daily `step=86400`, OHLC, and volume. |
| 2018 and 2022 history for a Bitstamp spot cohort | **Unverified; fails qualification** | The endpoint accepts historical timestamps and has a 1,000-candle request limit, but no official per-market start date, retention guarantee, or spot-cohort availability matrix is published. The local untracked `CRYPTO_35.csv` is explicitly a futures cohort and cannot be assumed to represent historical Bitstamp spot listings. A Bitstamp-specific preregistered spot cohort is absent from the reviewed source materials. No API requests were made, as prohibited. |
| Continuous/correct candles around market gaps | **Unverified** | Docs do not promise completeness, outage behavior, zero-trade candle construction, or explicit missing-candle semantics. Must validate against returned history and independently recorded venue status before use. |
| Delisted/renamed symbol history | **Not established** | `/markets/` describes current available markets. No official historical market catalogue, delisting archive, symbol-identity mapping, or endpoint behavior for removed markets was documented in the reviewed materials. |
| Terminal value for a held spot asset after delisting | **Not established** | OHLC returns traded candle prices and volume, not an exchange delisting settlement, forced-conversion amount, withdrawal deadline, or final claim value. A strategy needs a preregistered exchange-specific closeout policy and the necessary dated evidence. |
| Non-commercial backtest/storage rights | **Unclear; do not treat as passed** | Official public API wording describes commercial licensing but does not affirm personal research, archival retention, derived-result, or redistribution rights for non-commercial users. Current applicable Terms of Use were not text-verifiable in this documentation pass. |
| Futures R4 substitution | **Rejected as non-equivalent** | Bitstamp OHLC is spot-market price/volume. It lacks futures contract OHLC, funding, basis, mark/index price, open interest, liquidation, and contract-specific trading constraints. It can only be a separate spot robustness study if its own preregistration and data gates pass. |

## Inference

- Because the official docs expose only current markets and do not guarantee retained history for removed symbols, they cannot support survivorship-free selection among assets that were exchange-listed at each historical date.
- Even if API calls later return older OHLC candles for active pairs, returned candles alone will not establish that every asset was available to trade throughout a sample or define what happens to a position after a pair is removed.
- A 30-symbol spot backtest could become admissible only after the exact symbol set is fixed and all three proofs exist: (a) per-symbol candle coverage and gaps across the preregistered dates, (b) dated listing/delisting and conversion/withdrawal handling for every affected symbol, and (c) explicit permission for private non-commercial backtesting and local retention.
- Passing a spot data gate would create a distinct spot-market experiment. It would not validate, replace, or be pooled as evidence for derivatives/futures R4.

## Next admissible route

1. Define and preregister the precise Bitstamp spot cohort (30 symbols if that is the selected size), including whether the universe is fixed in advance or point-in-time Bitstamp listings. Do not substitute the current futures `CRYPTO_35.csv` without an explicit spot-universe decision and independent eligibility proof.
2. Before any collection, resolve the rights question from current applicable Bitstamp terms or written authorization. No contact was made for this task.
3. If rights permit, make a bounded public-API-only coverage probe for the specified pairs and dates, then verify returned row counts, missing dates, timestamps, and pair identities; do not infer coverage from the API's accepted timestamp range.
4. Collect official dated listing/delisting notices and define a closeout/withdrawal/zero-value convention before testing. If those records cannot be established, exclude affected assets prospectively under preregistered eligibility rules or leave the strategy data-blocked.
5. Keep spot results in a separate preregistration and report. Do not merge them into futures R4 evidence.

## Actions not taken

No API request, download, account login, key creation, paid-data access, support contact, code/data change, backtest, shared-ledger edit, R4 edit, or edit to an existing report was made.
