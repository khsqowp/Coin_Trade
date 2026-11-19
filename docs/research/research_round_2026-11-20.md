# Research round — 2026-11-20

## Objective and decision rules

The sole optimization objective is maximum after-cost compounded wealth across bull, bear, and sideways regimes. For KR/US equities, CAGR ≥20%, MDD ≤30%, Sharpe ≥1.0, and OOS completed trades N≥200 are candidate gates, not the optimization objective. For crypto signals, target-first M2 ≥80% is a required accuracy gate, not a profitability proxy; fee/slippage-adjusted expectancy must also be positive. A candidate does not pass without non-overlap OOS N≥200, at least 20 symbols, at least 10% signal coverage, and a sealed evaluation.

## Four independent research roles

| Domain/role | Finding | Status |
|---|---|---|
| KR equities | Point-in-time PEAD/SUE is distinct from tested price-only candidates. Requires timestamped as-reported EPS, revisions, delisted-security history, and corporate-action-adjusted prices. | Conditional candidate; no backtest. |
| US equities | Monthly ETF dual momentum (12–1 month ranking, top two, absolute 12-month T-bill filter, next-session open rebalance) is a distinct hypothesis. Requires point-in-time ETF universe, delisted products, total-return prices and cash-rate history. | Candidate; no backtest. Low-frequency trade-count gate is a material concern. |
| Crypto candidate | Cross-sectional 60m relative-return mean reversion: among a fixed 20-symbol universe, long bottom four and short top four by prior 24h return less cross-sectional median; next-60m open entry; 0.5 ATR target, 2 ATR invalidation, 12h vertical barrier. | One fixed development test is worth preregistering only after data/engine gates. No result yet. Reward/risk is 1:4 before fees, so 80% M2 alone cannot imply positive expectancy. |
| Crypto red team | Found optimistic gap fills and missing-bar omissions in setup backtests; M2 coverage denominator excluded unscorable actionable predictions; fee-only runs falsely reported slippage tested. | Corrected in this branch; full test suite passes. |

These are research proposals, not verified market edges. Equity data eligibility and point-in-time rights remain unverified; no equity performance test was run.

## Read-only rescoring of stored crypto forecasts

The two local prediction databases were evaluated in memory with `target-first-v2`, reading `chart_predictor/data/candles.sqlite` read-only. Neither the prediction databases nor candle data were changed. The source is a historical stored-forecast sample, not a preregistered sealed OOS experiment. Its constituent predictions overlap; no non-overlap count or portfolio compounding result is asserted.

| Forecast database | Actionable issued | Scorable actionable | Target first | Wilson 95% CI | Scored / issued |
|---|---:|---:|---:|---:|---:|
| `pred_llm.sqlite` | 172 | 87 | 74/87 = 85.1% | 76.1–91.1% | 50.6% |
| `pred_llm_r2.sqlite` | 1,220 | 351 | 280/351 = 79.8% | 75.3–83.6% | 28.8% |

The first sample's point estimate exceeds 80%, but its 95% lower bound is 76.1% and it has only 87 scorable actionable cases. The second misses the 80% point estimate and its interval includes materially lower accuracy. Most rescoring exclusions were invalid directional target/invalidation geometry: all 739 unscorable Codex records in `pred_llm_r2.sqlite` failed the new level-bracketing rule; 130 Claude records also failed it. These old forecasts cannot establish present strategy performance.

Cost-adjusted trade returns were negative for each model/side subgroup in both historical databases. Mean net return per scored signal, calculated using the stored leverage suggestion, was:

| Database | Model / side | N | Mean net return on suggested leverage |
|---|---|---:|---:|
| `pred_llm.sqlite` | Claude long / short | 11 / 27 | −0.13% / −0.80% |
| `pred_llm.sqlite` | Codex long / short | 22 / 27 | −0.80% / −0.39% |
| `pred_llm_r2.sqlite` | Claude long / short | 137 / 144 | −0.39% / −0.45% |
| `pred_llm_r2.sqlite` | Codex long / short | 41 / 29 | −0.81% / −0.69% |

These returns use the stored leverage suggestion and scorer assumptions of 0.05% taker fee plus 0.02% slippage per side. They are per-signal diagnostics, not portfolio CAGR: simultaneous positions, capital allocation, and overlap were not simulated. This directly demonstrates why M2 hit rate cannot stand in for wealth growth.

## Engine corrections in this branch

- Require a contiguous 1m execution path; trades crossing missing minutes become explicitly unscorable instead of being resolved from incomplete observations.
- Model stop gaps at the 1m open and preserve adverse stop-first handling when barriers collide in the same minute.
- Make P5 evaluator output say slippage was not tested when only fee costs were included; support a user-level skill installation when the ignored repository-local copy is absent.
- Report M2 coverage against all issued actionable long/short signals, separately from the actionable signal rate.

Verification: `chart_predictor/tests` — 217 passed, one non-fatal Joblib CPU-detection warning; `git diff --check` passed. This patch is on local branch `research/scorer-fixes-20261120`, based on commit `069cbc6`; the original `main` checkout and databases remain unchanged. No push or deploy has occurred for this patch.

## Next research steps

1. Merge these engine corrections only after final diff review and remote-state verification.
2. Preregister the single fixed 60m cross-sectional candidate on development-only data, with point-in-time universe, chronological target/stop ordering, fees and conservative slippage, coverage, overlapping-signal controls, and net wealth metrics fixed before running.
3. Audit current equity data entitlements, point-in-time company/ETF universes, and price/corporate-action coverage. Do not backtest PEAD or monthly ETF momentum until their required data exists.
4. Keep all validation and sealed results untouched until candidate rules are frozen; no success claim from this research round.
