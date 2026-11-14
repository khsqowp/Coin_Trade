# Addendum A1 — KR benchmark and calendar correction

Date: 2026-11-06, before any candidate execution.

## Reason

The mirrored `kr_daily_v2/data/` directory contains 3,236 parquet files but does not contain `069500.parquet`. The initial draft preregistration incorrectly assumed the KODEX 200 benchmark file was part of this mirror. A read-only panel smoke test failed before any candidate strategy was evaluated. The failed loader check is recorded in `attempts.jsonl` as a setup event, not a strategy result.

## Frozen correction

- Use `005930.parquet` only as the available KRX session-calendar source. It is not used as a return benchmark.
- For regime labeling, construct a daily close-to-close equal-weight proxy from available symbols meeting the frozen daily eligibility criteria (252 observed bars, 55 positive-volume sessions in the trailing 60 sessions, median traded value >= KRW 1bn), then compound the daily cross-sectional mean return.
- For comparative portfolio results, simulate a monthly rebalanced equal-weight portfolio of all symbols meeting the same eligibility rule, with the same KR costs and next-open execution as the candidate portfolios.
- Rename all KR benchmark claims to `KR_EW_AVAILABLE_PROXY`; do not call this KODEX 200, KOSPI, or an official market index. The universe snapshot mismatch and this proxy's composition bias remain unresolved. It cannot support a confirmatory or “valid strategy” claim.
- The US benchmark remains SPY adjusted-close buy-and-hold, charged the fixed entry and exit costs described in `PREREG.md`.

This is a prospective addendum: no candidate outputs existed when the correction was made. The updated `PREREG.md` and `run_gen01.py` hashes are captured in `manifest.json` immediately before the first candidate attempt. The original failed loader check will not be erased from the attempt log.
