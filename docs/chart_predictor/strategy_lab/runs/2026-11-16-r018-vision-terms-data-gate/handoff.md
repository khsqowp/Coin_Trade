# R018 handoff

## Completed

- Read the current official Binance Vision terms and README.
- Opened the repaired long-history database and current development candles database read-only; inspected their schemas and aggregate metadata.
- Clarified that private, non-production historical backtesting is expressly listed as permitted, while live proprietary trading execution and compensated signal distribution are prohibited.
- Verified one official Vision premium-index archive object with HTTP HEAD (200, 16,691-byte archive advertised); no archive body was fetched. This establishes a reachable example, not complete coverage.
- Received four independent role reviews from the same supplied evidence snapshot. The reviewers agreed there is no eligible performance test yet; premium/index basis mean reversion may be a distinct family after coverage and overlap gates pass.
- Found an official documented path for historical premium/mark/index candles and funding-rate history. This is only source documentation; actual per-symbol coverage, full pagination, delisted-contract membership, and integrity remain untested.
- Preserved the distinction between a rights-cleared historical research use and the still-unresolved intended live/manual signal use.
- The user then explicitly limited Vision use to historical backtesting only. No Vision-derived signal may be used for live or manual trading in this project.
- The user authorized research of official KRX/CRSP sample and pricing information only, without creating accounts or purchasing data.
- Ran zero strategy performance cells and opened no sealed evaluation data.

## Current state

- Historical Vision data: permitted for purely personal, non-production historical backtesting under the current terms, subject to CC BY-NC-SA 4.0 obligations.
- Available repaired candle data: six currently traded USD-M contracts; no funding, mark/premium, or point-in-time contract membership in the inspected database.
- A public source path for premium/mark/index candles and funding history is documented, but not yet verified comprehensively per symbol/date; contract listing/delisting history remains unresolved.
- Current-capture candles DB: OHLCV table only; no embedded funding history.
- KR/US equity research remains blocked on eligible historical prices and point-in-time inactive-security coverage as recorded in R017.
- Agent review for this round was not validly independent: four agents failed to access the requested worktree and their answers are excluded from evidence.

## Next work

Do not rerun MACD-zero/RSI-50 or exposed P5-P9 grids. First use the existing strategy catalog and prior rejection reports to nominate a genuinely different mechanism. In parallel, define a minimal data-eligibility specification for that mechanism, including source rights, historical universe membership, funding, fees, slippage, and a sealed boundary. Only then write the performance-trial plan and run its preregistered full grid.

## Reproduction

The read-only inspection was performed against the two paths recorded in `plan.md`; no data files or database rows were changed. The official terms were reviewed online on 2026-11-16. This audit report is not a legal opinion or a strategy-performance finding.
