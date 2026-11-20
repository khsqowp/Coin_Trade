# UTC weekday-hour sign persistence — exploratory M2 result

Run date: 2026-11-20. Candidate preregistration:
[`PREREG_UTC_WEEKDAY_HOUR_SIGN_M2_20261120.md`](../../PREREG_UTC_WEEKDAY_HOUR_SIGN_M2_20261120.md).
The result is exploratory only; it is not a Core strategy or a live-trading
claim.

## Result

| Measure | Result | Fixed gate |
|---|---:|---:|
| Target-first M2 | **37.36%** (14,724 / 39,410) | ≥80% — **fail** |
| Wilson 95% interval | 36.88%–37.84% | lower bound > baseline — **fail** |
| Frozen development baseline | always short, 37.70% | Candidate is 0.34 pp lower |
| Two-week block bootstrap, 2,000 draws | 36.53%–37.91% | no supported baseline outperformance |
| M1 entry-bar direction | 49.59% | separate diagnostic |
| Coverage | 38.50% (39,410 / 102,375 eligible anchors) | ≥10% — pass |
| Symbols | 35 | ≥20 — pass |
| Non-overlap events | 39,410 per-symbol; 821 market-time | ≥200 — pass, dependence remains |
| Gross mean return | -1.394 bp/event | positive economics absent before fees |
| Mean after base fee + modeled funding | -11.424 bp/event | positive — **fail** |
| Mean after stress fee + modeled funding | -31.424 bp/event | positive — **fail** |

Exit reasons: 15,317 stops, 14,724 targets, and 9,369 time expiries. The
candidate failed the primary M2 gate, did not beat the frozen baseline, and had
negative gross and net means. Do not tune this rule on the scored interval.

## Data and execution audit

- Input interval: development 2025-06-01 through 2026-05-31; exploratory score
  interval 2026-06-01 through 2026-09-30, UTC half-open endpoints.
- The raw audit verified 3,024 monthly archive ZIP hashes for 36 symbols across
  2024-06..2026-09. Thirty-six 2026-06-29 daily mark-price recovery archives
  each matched their recovery-manifest hash and contained exactly 24 hourly
  rows. A read-only overlay restored complete mark-to-contract timestamp
  alignment; source ZIPs were not altered.
- IMXUSDT was excluded for the full run under the preregistered data-QA rule
  because its 2026-06 funding timestamps disagreed with adjacent declared
  intervals. The remaining 35 symbols were scored.
- Fees are account-independent legacy proxies: 10 bp base and 30 bp stress
  round trip. The funding calculation treats signed rates relative to entry
  notional. Funding amount basis was not independently validated against
  settlement mark notional. Spread and slippage are unmeasured.
- Six events exit at 2026-10-01 00:00 UTC, while funding input ends in
  2026-09. A settlement at that exact boundary may be absent. Therefore the
  funding-adjusted means above are model estimates, not exact executable PnL.
  Fees-only means remain negative at -11.394 bp base and -31.394 bp stress;
  this audit caveat does not alter the candidate rejection.
- The interval was source-audited but not held sealed from all prior research.
  It is not described as untouched OOS or live-forward evidence. The 36-symbol
  cohort's point-in-time listing/delisting coverage is unresolved.

## Independent checks and disposition

The machine-readable command, runtime, code, preregistration, and data
fingerprints are recorded in [`run.json`](run.json).

The independent ledger verifier passed: 39,410 rows, zero same-symbol overlap,
821 market-time non-overlap events, zero fee arithmetic mismatches, and zero
summary cross-check discrepancies. The scoped Python tests passed (18 tests).
The Red team found no timing or M2 label issue that changes the result; it
flagged the funding-boundary and funding-notional limitations above. Blue and
the final judge rejected this fixed candidate. No robustness promotion run is
warranted after failure of the primary gate.

**Verdict: REJECT this fixed 52-occurrence UTC weekday-hour rule. Phase 8
continues with another structurally distinct, preregistered hypothesis. Phase
9 remains blocked because the validated-Core count is zero.**

Reproduction:

```sh
/opt/anaconda3/bin/python3 scripts/research/weekday_hour_m2_probe.py \
  --stage audit --audit-json /private/tmp/cointrade-50_50-data/audit.json \
  --coverage-json docs/research/inventory/usdm_archive_coverage_20261120.json \
  --recovery-manifest /private/tmp/cointrade-50_50-data/mark_gap_recovery.jsonl \
  --archive-root /private/tmp/cointrade-50_50-data \
  --output docs/research/inventory/runs/weekday_hour_m2_20261120
```

Baseline and score require the same arguments with `--stage baseline` and then
`--stage score`, in that order. The final inputs remain under `/private/tmp`;
the tracked run artifacts contain the audit fingerprints, not raw archives.
