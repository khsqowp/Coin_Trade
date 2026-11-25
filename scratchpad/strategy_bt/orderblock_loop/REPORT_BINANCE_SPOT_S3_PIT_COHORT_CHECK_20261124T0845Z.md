# Binance Spot S3 index and 2018-start cohort check

**Date:** 2026-11-24 08:45 UTC  
**Scope:** Bounded read-only requests to Binance's official public S3 ListObjectsV2 index, plus local catalog context. Inspected only listing XML metadata (object keys and pagination structure); did not GET archive objects or inspect row contents. No post-cutoff observations were queried. No code, existing report, ledger, or R4 changes; no backtest.

## Finding

**The official S3 listing is useful for confirming individual archive objects, but this bounded audit cannot establish a non-survivor-selected cohort of at least 30 spot base assets present at the preregistered 2018 start and covered in both 2018 and 2022.** The blocking proof is an exhaustive dated 2018 spot-market universe and its mapping from pair symbols to distinct base assets. The object index is organized by symbol before interval and date, so a single bounded year-prefix listing cannot enumerate all 2018 files across symbols.

## What the official index confirmed

1. A first-page request to `data/spot/monthly/klines/` with `delimiter=/` and `max-keys=20` returned HTTP 200 and symbol directories in lexical order, along with a continuation token. This index is paginated; that first page is not a complete symbol directory.
2. Two targeted `ListObjectsV2` requests used exact prefixes for BTCUSDT 1-minute spot archives in 2018 and 2022, each with `max-keys=26`. Both returned HTTP 200 and were not truncated. Each listed 12 monthly zip objects (January through December) plus associated checksum objects. The listed zip-object sizes summed to 25,281,048 bytes for 2018 and 26,608,406 bytes for 2022. This confirms BTC full-year *archive-object* coverage in both years, not row continuity or a 30-asset universe.
3. The object key layout is `data/spot/monthly/klines/<PAIR>/1m/<PAIR>-1m-<YYYY>-<MM>.zip`. Because year/month occurs after the pair directory, there is no single year-prefix request at the archive root that isolates all 2018 object keys. Exhaustively validating each pair's 2018 and 2022 monthly keys would require more enumeration than this bounded check permits.

Example official listing endpoint used (read-only S3 ListObjectsV2 metadata):

`https://s3-ap-northeast-1.amazonaws.com/data.binance.vision?list-type=2&max-keys=26&prefix=data%2Fspot%2Fmonthly%2Fklines%2FBTCUSDT%2F1m%2FBTCUSDT-1m-2018-`

The 2022 request used the same prefix with `2018` replaced by `2022`; both year-specific listings returned complete 12-month object-name sets for BTCUSDT. The top-level symbol-directory request returned a continuation token; the token is not reproduced here.

## Cohort definition and exact missing proof

To avoid survivor selection, the defensible preregistration definition would be: **all Binance spot base assets with at least one Binance spot market trading at the preregistered start instant (2018-01-01 UTC), fixed before strategy evaluation; then require full-year monthly archive coverage in both 2018 and 2022 under a predeclared base-asset/pair mapping.** It must not filter by later survival, returns, or current listing status.

The S3 object index alone does not document exchange listing/trading activation timestamps. A January 2018 kline object would be evidence of activity during that month, but it does not prove the exact start-date universe or prove an absent object means an unlisted asset rather than an archive gap. A set of pair-specific listing notices can establish individual activation events, but the completeness of a reconstructed all-market list was not established. Pair names also do not by themselves resolve distinct base assets, quote-market duplication, redenominations, or ticker changes.

Therefore the following are still unproven:

- the complete list of spot markets open at 2018-01-01 UTC;
- whether at least 30 distinct base assets in that fixed universe have all required 2018 and 2022 monthly archives;
- full candle continuity and archive-version consistency (object listing metadata cannot prove either).

Do not use current survivors as the eligible set, infer absent-history assets away, or treat this result as approval for a 30-symbol pilot. Existing local metadata remains a selected subset (four symbols with all 12 local 2018 month files), not the complete official archive.

## Research-use terms

The current Binance Vision Dataset Terms state that purely personal, non-production algorithmic historical backtesting is permitted under CC BY-NC-SA 4.0. Commercial use, live execution, and compensated signal distribution are excluded. This finding concerns stated terms only; it does not cure the universe and coverage gaps above. [Official terms](https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md)

## Next valid gate

Before a spot pilot can be preregistered, obtain a complete authoritative historical market-activation record for the exact start instant, define pair-to-base-asset identity/rename rules, and verify all qualifying symbol-month object names for both calendar years. Only then, separately, inspect file contents and test candle-level continuity under the existing quality rules. If the complete PIT universe cannot be sourced, this route cannot substantiate the required non-survivor-selected 30-asset cohort; keep the existing gate unchanged.
