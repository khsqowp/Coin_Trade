# Phase 8 — USD-M bookDepth archive eligibility audit

Date: 2026-11-21. Read-only NAS Parquet and official Binance daily-archive
comparison. No signal/outcome prices or strategy performance were examined;
no NAS data was modified.

## Decision

**Reject `um_bookDepth` as a current strategy input.** The archive contains
only BTCUSDT and ETHUSDT, does not provide raw price-level L2 or executable
quotes, and includes confirmed stale-band and missing/incomplete-day records.
It cannot satisfy the fixed >=20-symbol gate. This does not reject price-only
cross-crypto research or assert that no other order-flow data exists.

## Local inventory and schema

NAS root: `/Volumes/home/mac/CODE/trading_data/external/crypto/binance/um_bookDepth`.

| Symbol | Monthly Parquet files | Observed filename span |
|---|---:|---|
| BTCUSDT | 47 | 2023-01 through 2026-11 |
| ETHUSDT | 47 | 2023-01 through 2026-11 |

Sampled Parquet schema: `timestamp:string`, `percentage:double`,
`depth:double`, `notional:double`. Sample row counts: BTC 2023-01 has
762,960; BTC/ETH 2026-10 have 1,000,416 each. Binance's public-data
collaborator describes depth as coin-denominated and notional as notional-
denominated cumulative depth at percentage levels from mid; these are
aggregated bands, not raw order-price/quantity levels, BBO, queue position, or
fill records. [Binance public-data issue #447](https://github.com/binance/binance-public-data/issues/447)

## Official daily archive cross-check

Eight official daily ZIP samples were downloaded to `/private/tmp`; each ZIP's
SHA-256 matched its published `.CHECKSUM`. For every sampled day, the local
monthly Parquet rows matched the official daily CSV exactly on timestamp,
percentage, depth, and notional. Thus the observed defects are present in the
published daily inputs and propagated faithfully into the local monthly file.

| Symbol | UTC day | Unique snapshots | Rows | Official ZIP SHA-256 |
|---|---|---:|---:|---|
| BTCUSDT | 2026-09-02 | 2,880 | 34,560 | `facd2e2378191fd59cc944de5b9080e95e40b03911b39f9be29d82f5e42485bb` |
| BTCUSDT | 2026-09-04 | 2,880 | 34,560 | `4663601e7d1230c20a8dc6d05c913e227b93a49811d12b258cb00b980e149a40` |
| BTCUSDT | 2026-10-07 | 339 | 4,068 | `9ff711d9fe81e415708dfcc7703166435dea69e077d720306eaf2e023b419033` |
| BTCUSDT | 2026-10-09 | 2,389 | 28,668 | `0244d5fd7e6936dc4227bdb91946bc255dbde263c07dabfd8de997ff38b00fd6` |
| ETHUSDT | 2026-09-02 | 2,880 | 34,560 | `0649e8f33491560b15ca198117b3ed3fd785279066eeea95184fe6c2539b1852` |
| ETHUSDT | 2026-09-04 | 2,880 | 34,560 | `da1bebe972fe9709036479fa6f70db96e5192b2ac503d9bcc931407c59faf77a` |
| ETHUSDT | 2026-10-07 | 339 | 4,068 | `0575fa1e83e2c0ceca2f03ba640dcee84fb03dc0300851010c9626499658e271` |
| ETHUSDT | 2026-10-09 | 2,389 | 28,668 | `d2817145e8df910c7b7dd33cc38bb8ae147fc2071fded9841b223e0c22ce38c7` |

At the 30-second cadence, a complete UTC day has 2,880 snapshots and 34,560
rows (12 percentage bands per timestamp). The local October files contain 30
calendar dates; October 8 is absent, October 7 has only 339 snapshots, and
October 9 has only 2,389 snapshots for both symbols. Official daily ZIPs and
checksums for October 8 return HTTP 404 for BTCUSDT and ETHUSDT. The October
monthly file therefore preserves the upstream gaps; a valid checksum does not
mean complete coverage. Binance issue #512 independently reports these
specific incompleteness dates and sample counts, including the broader
BTC/ETH/SOL findings added on 2026-11-03.

## Stale-band check

The reported defect concerns reduced variation in the nearest ask-side
percentage bands. We counted distinct rounded `notional / depth` values per
band, matching the method in Binance issue #496:

| Symbol | Date | +0.2% band | +1% band | +2% band |
|---|---|---:|---:|---:|
| BTCUSDT | 2026-09-02 control | 2,880 | 2,880 | 2,880 |
| BTCUSDT | 2026-09-04 | 6 | 242 | 2,164 |
| ETHUSDT | 2026-09-02 control | 2,880 | 2,880 | 2,880 |
| ETHUSDT | 2026-09-04 | 5 | 367 | 1,406 |

This is a pronounced staleness/low-variation signature, but the sampled BTC
and ETH series are not literally constant across every sample of the whole
day; the report therefore records observed counts rather than repeating the
issue's stronger wording as a local fact. The daily and monthly values are
identical on these dates. Issue #496 is an open user report, not a Binance
maintainer confirmation; its failure mode is independently visible in the
sampled local and publisher data.

## Research implications and next gate

- The 2-symbol bookDepth panel cannot provide a 20-symbol target feature.
- Aggregated depth bands cannot establish order flow, spread, or historical
  execution prices. Do not use them to validate fill realism or replace
  measured bid/ask data.
- Exclude the affected 2026-09-03 onward inner ask bands from any later feature
  work unless a complete symbol/date/band audit and documented repair are
  available. Exclude incomplete October 7/9 snapshots and October 8 entirely.
- Before any future depth model, require an immutable input manifest, exact
  UTC-time semantics, completeness checks for every symbol-day-band, and an
  independent >=20-symbol data source. Passing that data gate would not itself
  authorize an M2 score.
- The `/private/tmp/bookdepth-*.zip` samples remain outside Git. The hashes and
  official source pattern above are sufficient to identify the sampled
  publisher files; no NAS file, temporary ZIP, or other original was deleted.

Sources: [Binance issue #496: stale inner ask bands](https://github.com/binance/binance-public-data/issues/496),
[Binance issue #512: incomplete Oct 7/9 and missing Oct 8](https://github.com/binance/binance-public-data/issues/512),
[Binance issue #447: bookDepth field meanings](https://github.com/binance/binance-public-data/issues/447).
