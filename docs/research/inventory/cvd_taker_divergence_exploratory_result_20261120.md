# 1h taker-CVD divergence: exploratory result

**Decision: reject this candidate as a demonstrated edge; do not proceed to Phase 9.** The single preregistered historical development run scored 4,356 CVD signals across 36 symbols. Target-first rate was 23.44% at 10h and 34.32% at 20h, far below the frozen 80% threshold. Mean net return was negative under both base and stress costs. No tuning or repeat scoring was performed after seeing the result.

## Research sequence and review

1. Four bounded public-source scouts reviewed SNS/videos, TradingView/Pine indicators, public trading communities, and GitHub strategies/skills. Their candidate pool and overlap review are recorded in [the Phase 8 external research panel](../phase8_external_research_panel_20261120.md). Frameworks and skills were not counted as strategies; incomplete claims were not promoted to backtests.
2. Blue, Red, Methods, and Judge debated the fixed pool. The existing review selected only a CVD-divergence hypothesis for one historical development screen; it did not approve Phase 9 or a core. OI shock followed by event-range breakout remains an input-quality audit lead, not a scored strategy.
3. The CVD rules and gates were frozen in preregistration v1-v8 before outcome scoring. The final code review approved exactly one exploratory run after the input audits passed and hashes matched. Four role approvals are bound to commit `cf759393dc3c70ff574859fa6f5b966be0a46516`; review-gate SHA-256: `daf8a8cc51a202cdb8e42f5a888435dc0165921d2c688a53cdecbd41617bf1dc`.
4. Pre-score QA passed 1,728/1,728 kline/funding archives, 864/864 monthly funding UTC-grid and boundary checks, 828 cross-month continuity checks, and 108/108 independent REST funding timestamp/rate sample cases. No archive errors were reported. The official funding schedule supports UTC 8h/4h cycles and interval changes; the audit rejects unsupported intervals and restricts the partial first-month exception to ARBUSDT 2023-03. [Binance schedule notice](https://www.binance.com/en/support/announcement/detail/98d6b24d3e5c4f84a8ed04087997d8d0)
5. The scorer and tests are committed. Targeted verification: 38 tests passed; Python compilation passed. The score was run once with a clean tree and no outcome-based tuning.

## Frozen strategy

At 1h, construct signed taker-volume delta `2*taker_buy_base - total_base_volume`, reset its cumulative sum at UTC midnight, and compare same-day strict 3-left/3-right price pivots with their CVD values. Require a lower price low/higher CVD low for long, or higher price high/lower CVD high for short. After pivot confirmation, enter only after the fixed price-break confirmation and at the next hourly open. The pivot/ATR stop, 1R target, 10h and 20h barriers, and 10bp base/30bp stress fees were fixed before scoring. A stop wins ties against a target in the same candle. Funding is charged from timestamped settlements under the frozen conservative exit-candle rule.

## Results

All rates below are event-level. Net returns are mean return per issued signal, not compounded account growth. The simultaneous lower bounds are from the preregistered synchronized seven-day block bootstrap; “PASS” in the inference engine means the calculation was evaluable, not that the strategy passed.

| Horizon | CVD target-first | 95% Wilson interval* | Coverage | Non-overlap events / time clusters | M1 direction | Net mean base / stress | Strongest direction control |
|---|---:|---:|---:|---:|---:|---:|---:|
| 10h | 1,021/4,356 = **23.44%** | 22.20–24.72% | 0.712% | 556 / 350 | 47.64% | -0.1589% / -0.3586% | Always short 23.88% |
| 20h | 1,495/4,356 = **34.32%** | 32.92–35.74% | 0.712% | 556 / 350 | 51.31% | -0.0768% / -0.2765% | Always short 34.80% |

\*The Wilson interval assumes independent events and is descriptive only; clustered bootstrap inference is more conservative.

| Comparison | 10h | 20h |
|---|---:|---:|
| CVD minus price-only target-first rate | +1.26 percentage points | +1.22 percentage points |
| Simultaneous 95% lower bound for that difference | -0.86 pp | -1.24 pp |
| CVD block-bootstrap 5th percentile lower bound | 21.53% | 32.15% |

Neither horizon clears the 80% target-first gate, 10% coverage gate, positive base/stress expectancy gate, or improvement-over-controls gate. Both do clear the numerical total sample, non-overlap sample and symbol-count minimums, but those counts do not offset the failures. The strongest fixed control (always short) exceeds CVD at both horizons. Price-only target-first rates were 22.17% at 10h and 33.10% at 20h.

Exit outcomes: at 10h, 2,323 timeouts, 1,006 stops, 1,021 targets, and 6 invalid entries. At 20h, 1,395 timeouts, 1,460 stops, 1,495 targets, and 6 invalid entries. Every issued path had complete hourly data under the frozen audit; this does not establish mark-price liquidation fills.

## Interpretation and next research order

- CVD divergence added no statistically supported improvement over price-only divergence and underperformed the strongest direction control. Freeze this exact hypothesis as **rejected**; do not try parameter tweaks on the same exposed interval.
- Keep Phase 9 blocked: there is no individually validated core strategy. These historical bars have already been exposed in earlier research and cannot become untouched OOS by relabeling them.
- Next priority: audit the point-in-time availability, interval semantics, missingness, and provenance of the archived open-interest metrics. If that audit fails, stop that branch. If it passes, preregister one distinct OI-shock + event-range hypothesis with fixed entry/stop/target/expiry before any scoring.
- Keep liquidation-pressure/maker-queue ideas parked until liquidation records and order-book/fill data exist. Exclude Donchian and cross-coin variants that duplicate already screened families unless a genuinely distinct mechanism is specified first.
- After a future-only candidate passes its frozen outcome gate, test walk-forward and parameter neighborhoods, realistic cost stress, block-resampled risk, and independent ledger accounting. Historical Binance Vision material remains for permitted historical, non-production research only; this result is not a live or manual trading signal.

## Reproducibility artifacts

- Source and preregistration: commit `cf759393dc3c70ff574859fa6f5b966be0a46516`; the worktree was clean at scoring.
- Input audit: `/private/tmp/cvd-taker-input-audit-v4-20261120.json`, SHA-256 `90d3332f67a493fb4ca140401b973a43ebd6ddfb1916375c746d7a7830fdb448`.
- Funding timestamp sample audit: `/private/tmp/cvd-funding-timestamp-audit-v2-20261120.json`, SHA-256 `fe34ae86ad1a80e448ef88419794f5d1b19ee918dcc402844b09902e7323c034`.
- Review gate: `/private/tmp/cvd-taker-review-gate-v1-20261120.json`, SHA-256 `daf8a8cc51a202cdb8e42f5a888435dc0165921d2c688a53cdecbd41617bf1dc`.
- One-shot result: `/private/tmp/cvd-taker-divergence-score-20261120-v1/result.json`, SHA-256 `ce9e55c3eda4d352f16b435fc0192ce14dd1b3dd9b77c47a9468364e8d8e61a6`.
- Event-level rows: `/private/tmp/cvd-taker-divergence-score-20261120-v1/event_results.jsonl` (68,426 rows; SHA-256 is recorded in `result.json`). The detailed artifacts remain outside Git; no raw market archives were added to the repository.
- Reproduction command: `/opt/anaconda3/bin/python3 scripts/research/cvd_taker_divergence_probe.py --archive-root /private/tmp/cointrade-50_50-data --coverage docs/research/inventory/usdm_archive_coverage_20261120.json --manifest /private/tmp/cointrade-50_50-data/manifest.jsonl --input-audit /private/tmp/cvd-taker-input-audit-v4-20261120.json --funding-audit /private/tmp/cvd-funding-timestamp-audit-v2-20261120.json --review-gate /private/tmp/cvd-taker-review-gate-v1-20261120.json --output-dir /private/tmp/cvd-taker-divergence-score-20261120-v1`
