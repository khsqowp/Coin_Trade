# R028 — quarterly OI metrics archive quality sample

**Decision: continue data validation; do not register or score an OI strategy from this sample.** The sampled USD-M metrics archives carry usable OI values on most selected dates, but early exact duplicates, one missing interval, absent objects, field-specific nulls, and unresolved contract identity prevent extrapolating the result to a historical tradeable universe.

## Frozen scope and result

Before downloading, the plan fixed four symbols (BTCUSDT, ETHUSDT, BNBUSDT, XRPUSDT) and the first UTC day of each calendar quarter from 2021-01-01 through 2026-10-01: 96 symbol-days. The 96 public Vision archive and checksum pairs were attempted sequentially without account credentials or REST polling. Eighty-four archives downloaded; 12 returned HTTP 404. All 84 publisher SHA-256 values matched.

The archive validator read 24,767 CSV rows. Two BTCUSDT 2021 archives each duplicated all 288 five-minute rows; a separate full-row comparison found those duplicate rows exactly identical, with no conflicting duplicates. BTCUSDT 2021-10-01 omitted only 10:45 UTC. No off-grid timestamps were found. OI and OI-value columns had zero blank and zero nonnumeric/nonfinite cells across downloaded rows.

The 12 missing objects were the four quarterly sample dates in 2021 for ETHUSDT, BNBUSDT, and XRPUSDT. A 404 on those selected dates does not prove the symbols were unlisted or that all of their OI history is absent. In other fields, top-trader ratios, account long-short ratios, and taker ratios had 4,608, 1,152, and 2,304 blank cells respectively; these fields are not interchangeable with OI and must not be silently imputed.

## Interpretation and limits

- This establishes only sampled archive-object availability and field quality, not a 2021–2026 complete OI panel.
- Exact duplicate OI rows may be collapsed in a later derived table only with a recorded source hash and duplicate count; source ZIPs remain unchanged. Conflicting duplicates must be quarantined.
- The R026 `create_time + 5m` availability alignment remains established only for BTC/ETH over three recent days. R028 does not broaden that timing claim.
- Current survivor symbols are not a point-in-time futures universe. Contract listing, termination, ticker reuse, and exchange symbol semantics remain unverified for the full sample.
- No strategy signal, target-first label, direction score, confidence interval, or return metric was generated. The user's crypto OOS gate remains target-first ≥80% and at least 200 non-overlapping events; qualified count remains zero.

## Next valid step

Create a broader per-symbol/date/field availability manifest for the intended fixed universe and independently check historical contract incarnations before any OI hypothesis is preregistered. If those gates are satisfiable, freeze an OI rule and baseline/ablation set on development data, then use an untouched forward boundary for the final target-first claim. Keep historical Vision strictly within the allowed personal non-production backtest scope.

Reproducibility inputs are described in `plan.md`; 84 downloaded ZIPs and the aggregate audit JSON remain in `/private/tmp/r028-vision-metrics-quarterly-coverage/` and are intentionally not committed.
