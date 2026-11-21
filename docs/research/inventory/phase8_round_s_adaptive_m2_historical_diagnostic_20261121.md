# Phase 8 / Round S — adaptive selective M2 historical diagnostic

Date: 2026-11-21. Candidate: one frozen pooled three-class HistGradientBoosting
model with 1-minute candle/taker-flow features, ATR(14) × 1 target and stop,
10-minute maximum horizon, weekly refits, and rolling score-quantile selection.
This is a custom adaptation of a selective direction-prediction paper, not a
replication of its fixed-odds target or a source-validated trading system.

## Fixed scope and run identity

- Instrument set: 32 fixed Binance USD-M USDT perpetual symbols.
- Historical evaluation: 2026-07-01 through 2026-09-30 UTC; 92 calendar days.
- Training/calibration: 180-day windows, 28-day embargo, 5-minute training
  anchors, weekly refits; 4 weekly prequential calibration refits from June 3.
- Execution proxy: next-minute open; target/stop at ±1 ATR; scan 10 candles;
  stop-first on same-bar ambiguity and worse-open fill on stop gaps; timeout at
  tenth-candle close.
- Costs: realized funding plus 10 bp and 30 bp total round-trip fee proxies.
  These do not include measured spread or slippage.
- Run folder: `runs/adaptive_selective_m2_20261121_v6/`.
- Frozen preregistration SHA-256:
  `e8cf770edacc024da36cc07e04b3cbe3eed11cf668e3c9cd7c5475d2121d13bc`.
- Forecast ledger SHA-256:
  `f73c9e50831f4e55f96fe8a48e9cf025528865fe20a5dee8c5a644e4455626f5`.
- Prequential score ledger SHA-256:
  `c9ef23949f2f9c5a033ae422bb56a90a3d920fd73fb80d0ae2545dd319289440`.
- Candidate score ledger SHA-256:
  `8d9144d968cc1ecb172d03c52f9a55ed97e9ede7afda5635e9e8b7d0c537bf9f`.

The full 5,529,248-row prequential ledger stores each finite class score,
selective score, threshold, refit time, calibration/evaluation period, and
whether an actionable forecast was emitted. The separate forecast ledger has
426,337 issued forecasts. The score phase verified ledger hashes and counts
before reading evaluation paths. A separate recount of `scores.jsonl` matched
all 426,337 events, 210,679 target-first hits, all four termination counts,
and both net-return means.

## Results

| Metric | Observed | Frozen gate | Result |
|---|---:|---:|---|
| Target-first M2 | 49.4161% (210,679 / 426,337) | ≥80% | **Fail** |
| Wilson 95% interval | 49.2660–49.5662% | lower bound > same-event momentum | Passes comparison only |
| Expiry direction accuracy | 48.6563% | Report separately | — |
| Coverage | 10.0575% (426,337 / 4,239,008) | ≥10% | Pass, narrowly |
| Active symbols | 32 | ≥20 | Pass |
| Global non-overlap sample | 12,639; M2 49.3947% | N≥200 | Passes sample gate only |
| Mean net per issued event, 10 bp | −0.09981% | >0 | **Fail** |
| Mean net per issued event, 30 bp | −0.29981% | >0 | **Fail** |

Termination counts: 210,679 target-first, 202,554 stop-first, 8,016 timeout,
and 5,088 same-bar ambiguous stop/target events. No entries were missing.

Same-event baselines: preceding-10-minute momentum M2 47.1681% (201,095 /
426,337); deterministic random-side M2 48.3397% (206,090 / 426,337). The
candidate's Wilson lower bound exceeds the momentum point estimate, but that
relative edge does not approach the required 80% M2 or overcome costs.

The preregistered 1,000-draw circular 7-calendar-day panel bootstrap gives M2
2.5/50/97.5 percentiles of 48.9681% / 49.4222% / 49.7273%. Net expectancy
remains negative across the bootstrap interval under both fee proxies.

## Final verdict

**REJECT this candidate.** Five of eight numeric gates passed; three failed:
M2 ≥80%, positive net expectancy at 10 bp, and positive net expectancy at
30 bp. The isolated improvement over the momentum baseline is not sufficient
evidence of a tradable core.

The evaluation dates were already exposed during prior research selection.
This is a historical simulated walk-forward diagnostic, not a sealed OOS
validation or contemporaneous prediction archive. The fixed 32-symbol cohort
does not establish point-in-time tradability or delisted-contract coverage;
the broader archive audit remains FAIL for gaps/anomalies outside this selected
slice. The fee inputs are proxies, not observed fills, and the 92-day interval
does not cover enough market regimes to establish robustness.

No post-result parameter tuning or second run was performed. **Phase 9 was not
run; no Core strategy was accepted.** Continue with other frozen hypotheses or
prospective paper/live-feed shadow observation; do not deploy this candidate.

## Artifacts

- `PREREG_ADAPTIVE_SELECTIVE_M2_20261121.md`
- `phase8_round_s_adaptive_m2_prereg_approval_20261121.md`
- `runs/adaptive_selective_m2_20261121_v6/preflight.json`
- `runs/adaptive_selective_m2_20261121_v6/forecast_manifest.json`
- `runs/adaptive_selective_m2_20261121_v6/forecasts.jsonl`
- `runs/adaptive_selective_m2_20261121_v6/prequential_scores.jsonl.gz`
- `runs/adaptive_selective_m2_20261121_v6/scores.jsonl`
- `runs/adaptive_selective_m2_20261121_v6/summary.json`
- `runs/adaptive_selective_m2_20261121_v6/by_symbol.csv`
- `runs/adaptive_selective_m2_20261121_v6/report.md`

Reproduce preflight, forecast, and score with the three CLI phases in that
order using the frozen archive root and run directory. A new run directory is
required; existing artifacts are never overwritten.

Earlier preflight-only snapshots in `runs/adaptive_selective_m2_20261121/`,
`runs/adaptive_selective_m2_20261121_final/`,
`runs/adaptive_selective_m2_20261121_final_v2/`,
`runs/adaptive_selective_m2_20261121_v3/`, and
`runs/adaptive_selective_m2_20261121_v5/` were generated while the code/tests
were being corrected. They contain no forecasts or scored outcomes and have
different implementation fingerprints. They are retained as audit history;
only the `v6` artifacts above are the final preregistered run.
