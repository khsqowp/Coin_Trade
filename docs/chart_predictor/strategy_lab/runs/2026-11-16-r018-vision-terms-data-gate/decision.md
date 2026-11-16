# R018 decision — historical-use scope clarified; strategy data gate still closed

## Decision

**Continue research, but do not run another futures performance grid yet.** The current official Binance Vision terms permit purely personal, non-production historical backtesting. That resolves one narrow rights question for historical research; it does not authorize live signal use, and it does not make the inspected data adequate for strategy qualification.

## Evidence

- Terms version 1.0 (last updated 2026-08-26) grants a CC BY-NC-SA 4.0 non-commercial license and expressly lists algorithmic historical backtesting for purely personal non-production research as permitted use. Use remains subject to attribution/share-alike conditions.
- The same terms prohibit live proprietary trading execution, automated commercial order generation, and compensated third-party signal distribution. The user explicitly restricted this project to historical backtesting and excluded Vision-derived live/manual signals; those uses will not be pursued here.
- The repaired historical database has 19,790,858 candle rows for six currently traded USD-M contracts, plus archive manifest and repair metadata. It has no funding, mark/premium, or point-in-time contract-membership tables.
- The current development candles database has one OHLCV table and no funding-history table.
- Official documentation lists USD-M premium-index, mark-price, and index-price archives from 2020-01-01 and a public funding-history endpoint. One BTCUSDT 1h premium-index monthly object for January 2025 returned HTTP 200 to a HEAD request; the archive body was not downloaded. One object is not evidence of complete symbol/date coverage.
- Four role reviewers agreed that no performance grid is admissible yet. They did not access the repository or raw databases. One reviewer identified premium/index basis reversion as a mechanically distinct candidate family, conditional on proving inputs and universe coverage.
- A new-data path is documented, not yet verified: official Vision downloader docs list USD-M premium-index, mark-price, and index-price archive families from 2020-01-01; the public funding-history endpoint supports timestamp windows and up to 1,000 rows per request. Actual per-symbol history, delisted-contract coverage, and complete funding pagination remain unverified.
- Therefore a funding-adjusted, survivorship-controlled strategy claim cannot be supported by these files alone. No metrics were computed and no sealed data were opened.

## Gate

No strategy is accepted. The portfolio-strategy count remains **0/2**; the separate selective crypto-signal ≥80% target remains unproven. The current historical data may be considered only for explicitly labeled personal, non-production exploratory backtesting after a preregistered plan; it cannot substitute for point-in-time universe evidence or funding/cost data.

## Next admissible work

1. Identify a distinct strategy mechanism from the prior catalog and reject overlap before any metric access.
2. Verify a lawful historical source for point-in-time contract eligibility, funding, and executable-cost assumptions. The Vision/REST path is a candidate for personal non-production historical backtesting; verify actual per-symbol coverage and preserve independent inputs and hashes before calculating metrics.
3. Preregister the full grid, train/validation boundary, B&H comparison, adverse execution/funding stress, independent-sample treatment, and multiple-comparison correction.
4. Keep Vision-derived historical research separate from live/manual signal workflows; this project's authorized scope is historical backtesting only.
