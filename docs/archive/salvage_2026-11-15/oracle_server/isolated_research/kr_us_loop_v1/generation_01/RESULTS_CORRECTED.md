# Generation 01 — corrected monthly-state rerun

Run: `GEN01-20261106T092112-99213` · 2026-11-06 UTC  
Preregistration: `PREREG.md` + `ADDENDUM_A1.md` through `ADDENDUM_A4.md`  
Ledger: `attempts_GEN01-20261106T092112-99213.jsonl` · Curves: `equity_curves_GEN01-20261106T092112-99213.csv.gz`

## Outcome

All 22 planned executions completed: 11 US and 11 KR, with 22 start and 22 finish events, 22 unique attempt IDs, and no runtime-failed attempts. All are `COMPLETED_EXPLORATORY`. No valid strategy was found. The later window is contaminated by prior inspection; prior cumulative trial count is unresolved; the KR universe, adjustment and comparison series are not authoritative. These results cannot establish independent out-of-sample validity.

**KR figures below are retained as execution records but are invalid for even exploratory performance comparison.** A red-team reproduction found that the shared KR loader can create zero prices and infinite/NaN volumes when a traded row has a zero close. The same loader was used for Gen01 and Gen02 KR. Do not interpret any KR CAGR, rank or benchmark-relative result until this loader and the underlying series are rebuilt and audited. US results are not affected by that specific KR adjustment defect, but remain exploratory and coverage-limited.

Annualized net CAGR (%). `IS` / `later` are the already-used screening partitions, not clean confirmation. US benchmark is SPY (5.22 / 14.84). KR benchmark is a local available-universe monthly equal-weight proxy (0.13 / 1.99), not KOSPI/KODEX.

| Candidate | US IS | US later | KR IS | KR later |
|---|---:|---:|---:|---:|
| KAMA_ER20 | 2.96 | 12.61 | 0.21 | -1.12 |
| HMA55_BREAKOUT | 1.65 | 10.79 | -1.38 | 5.00 |
| REG60_R2_BREAKOUT | 7.82 | 10.39 | -0.55 | -9.93 |
| ATR_NORM_SMA100 | 8.24 | 12.02 | -2.34 | -8.25 |
| VHF63_DONCHIAN20 | 10.43 | 11.00 | 0.74 | -2.74 |
| PERSIST63 | 5.84 | 12.87 | -10.92 | 1.02 |
| ATR_BUFFER55 | 9.02 | 8.95 | -4.33 | -8.44 |
| RESIDUAL_MOM126 | 8.90 | 15.02 | -16.31 | -21.85 |
| GAP_REVERSAL_5D | -1.07 | -2.79 | -52.60 | -56.05 |
| MOM12_1_VOL10_OVERLAY | 5.32 | 5.97 | -5.31 | -6.02 |
| MOM_TO_LOWVOL_200SMA | 12.88 | 7.16 | -7.70 | -3.18 |

`RESIDUAL_MOM126` exceeded SPY's rounded later-window CAGR by 0.18 percentage points (15.016% vs 14.838%), so the prior sentence claiming no US candidate exceeded SPY was incorrect. This is not a pass: its later-window Sharpe was lower (0.789 vs 0.856) and maximum drawdown was worse (-36.85% vs -33.72%); the later window was already inspected, US price coverage is incomplete, and historical multiplicity is unresolved. HMA was the only KR candidate above the provisional KR proxy in the later partition, but that is not a valid result: the KR universe is unresolved, the proxy is not a market index, and price adjustment/delisting handling still needs audit. `GAP_REVERSAL_5D` had extreme KR losses that should not be interpreted until that audit is resolved.

## Integrity notes

- Independent review found the initial run allowed stateful entries/exits to change during a month even though decisions were preregistered at month-end. The initial run is preserved; the corrected run uses month-end-only state transitions for all candidates and was rerun in full.
- Synthetic checks passed for all 11 candidate paths, monthly-only state, scale invariance, drawdown initialization and true-range warm-up. This validates mechanics on synthetic inputs only, not economic correctness.
- KR loading emitted NumPy divide-by-zero and invalid-value warnings at `run_gen01.py:55` while splitting adjusted volume around price-adjustment factors. A concrete `008080.parquet` reproduction shows 22 traded rows with zero close leading, under the current repair, to 575 zero closes, 451 infinite volumes and 56 NaN volumes. This makes the whole current KR run unusable until fixed and audited.
- The local KR panel has 3,233 priced symbols, lacks KODEX 200, uses 005930 only for the calendar, and has unresolved PIT/universe mismatch. US has local prices for 688 of roughly 1,209 PIT tickers. Both are coverage limits.
- No DSR/PSR or global multiplicity correction is claimed because the historical trials database/count is unavailable.
