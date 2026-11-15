# R001 handoff

## Completed

- Compared the attached strategy-lab target with `SPEC.md`, the P5–P9 research history, the data-quality audit, and the already-registered MACD-zero/RSI-50 run.
- Recorded that the MACD test had 537 trades per exit in its development segment; all five exit variants had negative mean net R and PF below 1. Selection was empty, so the later conditional segment was not opened.
- Determined that current audited history is six current USDⓈ-M symbols with no funding cashflows in the dataset and no point-in-time universe, while `candles.sqlite` is only a short 2026 window.
- Read current official Binance Vision archive documentation and dataset terms, plus the USDⓈ-M funding endpoint documentation. Spot archive history is a plausible alternative; it does not establish delisted-universe completeness. The terms limit data and derivatives to specified non-commercial uses and prohibit live proprietary execution and compensated third-party signal distribution.
- Ran no performance grid, accessed no credential, downloaded no data, and modified no database.

## Resume from here

1. Confirm the intended research/output use fits the official data terms; verify official availability for historical spot klines, delisted symbols, and payable perpetual funding settlements before choosing an instrument path.
2. Prefer a point-in-time spot universe if credible delisting/listing history can be assembled; otherwise assess a complete funding cashflow series before using perpetuals.
3. Record exact data provenance, terms, content hash, symbols, dates, and coverage in a new immutable input snapshot.
4. Ask the four research roles to propose genuinely distinct portfolio hypotheses against the existing catalog, then let the central plan deduplicate and preregister one coarse grid. The independent reviewer should challenge B&H comparability, leakage, universe bias, and costs.
5. Do not open sealed data or calculate strategy performance before that plan is frozen.

Overall objective remains active: 0/2 qualifying strategies.
