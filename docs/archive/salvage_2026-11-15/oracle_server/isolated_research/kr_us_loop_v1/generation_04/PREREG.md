# Generation 04 — TEMA trend and CLV event adaptations

Date: 2026-11-06. Local exploratory run only; no remote access, live orders, commits, or pushes.

## Purpose and evidence status

The user is correct that failure to find an edge is a failure of this search, not evidence that profitable systematic strategies do not exist. This generation tests two source-traceable daily OHLC hypotheses on the available local snapshots. It does not claim these ideas are novel: TEMA is registered in historical stock-swing search scripts and CLV appears in the broad strategy screening catalog, while the complete historical result ledger is unavailable. The run is exploratory, not independent confirmation.

## Frozen scope and execution contract

- Four candidate-market attempts: each candidate once for US and once for KR. Stop and log all candidates for a market if market data or benchmark preflight fails.
- Use only the local `data_mirror`. Never access the Oracle server or alter any remote process/container.
- Signals use information known at close `t`; fills occur at open `t+1`. Long-only, unlevered; max 50 US or 20 KR concurrent names; equal weight among active positions; cash for empty slots. Ties resolve by ticker.
- Use the existing Gen01 cost contract and Gen03 strict simulator. Invalid held/entry OHLC rejects the attempt; no fabricated flat marks.
- Report the fixed IS and previously inspected later partitions as exploratory only. Do not use these partitions to claim OOS validity, and do not calculate global DSR/PSR/BH claims because historical trial counts are unresolved.
- No thresholds, holding periods, ranking, or accounting choices may be changed after inspecting results. Any correction requires a dated addendum and a new run/hash; prior rows remain.

## Candidate definitions

1. **TEMA9_21_MONTHLY_SLOPE** — Compute EMA(n) recursively with `alpha=2/(n+1)`, initialized at the first valid close of each uninterrupted valid-close segment; reset after a missing/nonpositive close. `TEMA(n)=3*EMA1-3*EMA2+EMA3`, where EMA2 is the same EMA applied to EMA1 and EMA3 to EMA2. At calendar month-end `t`, enter/hold only when `TEMA9>TEMA21`, `C>TEMA21`, and `TEMA21[t]>TEMA21[t-21]`; exit at the next monthly rebalance if any condition fails or is unavailable. Rank by `(TEMA21[t]/TEMA21[t-21]-1)/(ATR14[t]/C[t])`, with ATR14 the 14-observation rolling mean of true range on uninterrupted valid OHLC. Require 200 uninterrupted valid OHLC bars before eligibility. Top K, equal weight.
2. **CLV_HIGH_CLOSE_5D** — `CLV=((C-L)-(H-C))/(H-L)`. When month-end? No: evaluate every valid daily close. If `CLV>0.8` and the ticker is not already in an active lot, open an event lot at the next session open and hold for exactly five open-to-close sessions, exiting at the open after the fifth session. Do not extend or duplicate a ticker's active lot. Active lots are ranked by current event CLV; hold at most K names, equal weight, cash otherwise. Require valid positive OHLC and `H>L`; no volume input. The same ticker may trigger again only after its prior five-session lot has expired.

## Ledger and stop conditions

Before execution, hash this file and the finalized runner. Log every start, setup failure, completion, exception, and output hash. Save per-attempt metrics and daily net-return curves. A failure is retained and never converted into a performance result. If causality, strict execution, finite-weight, or portfolio-bound checks fail, stop the affected run and preserve the failure record.

Even if either candidate exceeds the benchmark on a displayed historical partition, it remains an exploratory lead. Promotion requires reconciled complete historical trial counts, point-in-time universe/corporate-action data, and a genuinely untouched prospective or otherwise uncontaminated holdout.
