# R008 plan — Pre-label inference design for overlapping forecasts

Status: `design_proposal_only`; no market data or signal outcomes were inspected.

## Purpose

Specify what a future, separately registered R005 revision must decide if it permits overlapping forecasts to avoid the approximately 5% coverage ceiling documented by R007. This document does not amend R005 and does not authorize signal scoring.

## Proposed design constraints

1. Define a forecast observation as one eligible symbol × timeframe × decision timestamp × direction. Each observation receives exactly one primary 20T label; the 10T checkpoint is secondary and never counted as another sample.
2. Permit overlapping forecasts, but calculate precision and net outcomes from the complete frozen forecast ledger. No random train/test split; calibration and selection remain chronological and use an embargo at least as long as the maximum label horizon.
3. Resample contiguous UTC-time blocks synchronously across all symbols so that common market shocks and cross-symbol dependence are not broken. Recompute precision, paired baseline difference, and net expectancy within each bootstrap replicate. The block-length rule and sensitivity set must be preregistered and must cover at least the 20T label dependence horizon; report results across the frozen sensitivity set.
4. Report raw forecast count and effective temporal information separately. Do not treat the number of symbols or overlapping rows as independent trials. Report symbol-level and UTC-day/block-level contributions; keep each timeframe separate.
5. Set a precision claim rule before the run: report point precision, a dependence-aware interval, and whether its lower bound clears 80% as well as matched baselines. If it clears only the baseline but not 80%, report that distinction without calling the 80% target validated.
6. If the fixed forward period contains too few usable independent time blocks, or a confidence interval is too wide, extend only by a newly preregistered prospective observation period; do not repeatedly inspect interim aggregates.

## Horizon feasibility warning

With a 20T outcome horizon, a 365-day forward set contains at most 18 non-overlapping 20-day windows for a 1-day timeframe. Overlapping forecasts can increase the row count but cannot create additional independent 20-day market histories. The appropriate uncertainty method cannot remove this information limit. A longer prospective horizon may be required for credible daily-timeframe precision claims.

## Evidence basis and limits

The stationary bootstrap was introduced for inference with weakly dependent stationary observations by Politis and Romano (1994), DOI `10.1080/01621459.1994.10476870`. This is methodological background, not proof that a specific block length or stationarity assumption is valid for crypto signals. The future protocol must justify the bootstrap design for the actual estimand and data regime.

## Acceptance boundary

This proposal is not a frozen protocol: exact block construction, length selection, interval statistic, significance family, final dates, eligible symbols, and minimum information criteria remain open. No R005 performance labels may be generated from this document alone.
