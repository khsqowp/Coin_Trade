# Generation 01 — results and decision

> **Superseded for preregistration parity.** This file describes run `GEN01-20261106T090344-73306`. The six stateful candidates were later found to permit intra-month state transitions and are invalid for the month-end-only rule. See [RESULTS_CORRECTED.md](RESULTS_CORRECTED.md) for the full corrected rerun; the original ledger and curves are retained unchanged.

Run: `GEN01-20261106T090344-73306` · 2026-11-06 UTC

## Result

All 22 planned candidate-market executions completed and were recorded; there were no runtime failures. No strategy qualifies as valid. The later windows were already examined in prior work and are contaminated, cumulative historical trial counts are still unavailable, and the KR comparison portfolio is a proxy built from a mismatched local universe snapshot. This screen is exploratory only.

Annualized net CAGR (%). `IS` and `later` are both historical screening partitions, not clean independent confirmation. Benchmarks: US SPY = 5.22% IS / 14.84% later; KR available-universe equal-weight proxy = 0.13% / 1.99%.

| Candidate | US IS | US later | KR IS | KR later |
|---|---:|---:|---:|---:|
| KAMA_ER20 | 2.96 | 12.61 | 0.21 | -1.12 |
| HMA55_BREAKOUT | 6.06 | 6.30 | -21.90 | -13.47 |
| REG60_R2_BREAKOUT | 5.97 | 9.91 | 1.51 | -4.09 |
| ATR_NORM_SMA100 | 8.28 | 11.64 | -10.26 | -10.69 |
| VHF63_DONCHIAN20 | 18.71 | 7.69 | 2.64 | 0.46 |
| PERSIST63 | 5.36 | 12.99 | -11.91 | -9.06 |
| ATR_BUFFER55 | 6.70 | 7.94 | -0.77 | -9.17 |
| RESIDUAL_MOM126 | 8.90 | 15.02 | -16.31 | -21.85 |
| GAP_REVERSAL_5D | -1.07 | -2.79 | -52.60 | -56.05 |
| MOM12_1_VOL10_OVERLAY | 5.32 | 5.97 | -5.31 | -6.02 |
| MOM_TO_LOWVOL_200SMA | 12.88 | 7.16 | -7.70 | -3.18 |

US momentum-to-low-vol switching led the US IS by CAGR, but returned 7.16% later versus SPY 14.84%. VHF had 18.71% IS CAGR but a -60.95% IS maximum drawdown and 7.69% later CAGR. Neither passes. All KR candidates trailed the proxy in the later partition; the extreme KR losses require a separate price-adjustment/delisting audit before even exploratory interpretation.

## Audit limits and next action

- The KR benchmark is not KOSPI/KODEX; it is a monthly equal-weight local-mirror portfolio. The raw universe manifest and registered universe disagree, so the KR return comparison is not authoritative.
- US price coverage is 688 symbols with local prices from a PIT list of about 1,209 tickers; absent/delisted coverage is a known optimistic bias.
- Prior historical trial database counts were not available. Do not report DSR/PSR or multiplicity-adjusted significance from this run.
- The preregistration requests a monthly decision count, but the runner's metric objects do not currently emit that count. This reporting omission does not change the returns, but it must be corrected in the next runner revision.
- The ledger contains all attempt start/finish events; complete per-attempt metrics are in `attempts_GEN01-20261106T090344-73306.jsonl`; the run manifest pins hashes. `equity_curves_GEN01-20261106T090344-73306.csv.gz` holds daily returns/turnover/exposure for all attempts.
- Before interpreting KR further, audit corporate-action adjustment, stale/delisted holdings and daily-return distributions. Generation 02 hypotheses must be preregistered with an addendum and treated as exploratory on these already-seen windows.
