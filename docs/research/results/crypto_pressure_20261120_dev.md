# 3-minute candle-pressure cross-sectional momentum — development result

**Decision: REJECT. Do not open validation or tune this candidate.** Its target-first M2 was 8.88%, its average signal return after modeled fees/slippage was -0.183%, and the fully reinvested portfolio lost effectively all NAV. It also lagged both the 80% M2 gate and the net-wealth objective by a wide margin.

## Frozen trial and data

- Trial: `crypto_pressure_20261120_01`; one fixed rule, registered before the performance run in [preregistration](../prereg_crypto_pressure_2026-11-20.md).
- Window: 2026-07-17 00:00 UTC through 2026-10-08 23:51 UTC signals; the execution data cutoff was 2026-10-09 00:00 UTC with an eight-minute purge. `validation_opened=false`.
- Universe: first 20 symbols from the 2026-11-13 current-universe snapshot. Survivorship and retrospective-selection bias remain.
- Data: synchronized 1-minute OHLCV + quote volume. Source DB opened read-only. 483,428 actionable signals were fully scoreable; no missing execution paths.
- Selected-row SHA-256: `e5d421f395656422a1bcca38505df54eb9b1da2a6618b57d2c723f4cbddab8c9`.
- Code SHA-256: `72a7f3deceebfddeeff243729822b82e6da990bafb8ecfd770ae87b0ddc616d4`.
- Entry: after the completed three-bar, quote-volume-weighted close-location score; enter at next 1-minute open; cross-sectional top two long and bottom two short. TP +0.45%, SL -0.20%, 8-minute timeout; same-bar dual-touch resolves as stop.
- Costs: 0.05% taker fee and 0.04% slippage each side; stress doubles slippage to 0.08% per side. Funding, spread history, market impact, partial fills and liquidation are unavailable and not modeled.
- Portfolio: eight maximum slots, four per side, 1/8 NAV target notional each, 1.0x entry gross cap. Mark-to-market every minute and compound all net PnL.

## Results

| Rule / control | Signals | M2 all | M2 non-overlap (N) | M1 direction at 8m | Mean net / signal | Final portfolio NAV | MDD | Profit factor |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Pressure momentum | 483,428 | 8.88% (95% Wilson 8.80–8.96%) | 8.67% (169,619; 8.54–8.81%) | 40.37% | -0.1832% | 8.49e-19 | 100.00% | 0.179 |
| Reverse selected sides | 483,428 | 9.10% (9.02–9.19%) | 9.01% (169,619; 8.87–9.14%) | 42.55% | -0.1759% | 1.12e-17 | 100.00% | 0.191 |
| Deterministic random sides | 483,428 | 8.60% (8.53–8.68%) | 8.48% (201,507; 8.36–8.60%) | 41.37% | -0.1785% | 2.37e-18 | 100.00% | 0.179 |
| Cash | — | — | — | — | — | 1.0000 | 0% | — |
| BTC buy-and-hold, same dates/costs | — | — | — | — | — | 1.2786 | — | — |

The pressure candidate's base-cost portfolio completed 180,426 positions. Portfolio-level M2 was 10.73%, positive-net trade rate 17.95%, mean net return/notional -0.1845%, hourly Sharpe -424.82, and development-only annualized CAGR -100.00%. The final NAV is effectively zero (total compounded loss rounds to -100%); it is not a live-account forecast.

Under 2x slippage, candidate M2 fell to 6.78%, non-overlap M2 to 6.61% (N=169,619), mean signal return to -0.2604%, and final NAV to 9.61e-29; CAGR -100%, MDD 100%, and PF 0.089. The one-minute delayed entry did not rescue it: M2 8.94%, non-overlap M2 8.73% (N=169,618), M1 40.97%, and mean net signal return -0.1813%.

Coverage was 19.984% of 2,419,040 eligible symbol-minute opportunities, above the 10% gate. The non-overlap sample exceeded N=200, but this does not compensate for failing accuracy, positive expectancy, stress, and wealth gates. Per-symbol M2 ranged from 0.78% (BTCUSDT) to 19.95% (AKEUSDT); no symbol approached 80%. Long and short M2 were 9.10% and 8.66%; their mean net returns were -0.1825% and -0.1839% respectively.

## Why the candidate is rejected

1. M2 8.88% is 71.12 percentage points below the required 80%; its descriptive Wilson interval is nowhere near the gate. M1 is also below 50%.
2. Both signal-level expectancy and portfolio trade expectancy are negative after the preregistered base costs.
3. Compounded portfolio equity was practically wiped out and BTC buy-and-hold grew to 1.2786 from 1.0; cash also dominated.
4. Reversing the candidate's selections modestly improved M2 and net expectancy, indicating that the proposed directional interpretation is not supported. It did not make the reverse rule profitable.
5. The signal is a close-location proxy, not observed buyer/seller-initiated flow. The data window is only 84 days and the current-symbol snapshot is biased; this trial cannot establish all-regime performance.

No parameter sensitivity grid, Monte Carlo, block bootstrap, walk-forward, or validation run was performed: the candidate failed its preregistered development gates, so further robustness work would not justify promoting it. No observed result was used to alter the candidate's parameters.

## Verification and artifacts

- Full `chart_predictor/tests`: 232 passed, with one non-fatal Joblib CPU-count warning. `git diff --check` and Python byte-compilation passed.
- The compact JSON contains aggregate metrics, controls, per-symbol/per-side results, monthly NAV and provenance: [result JSON](crypto_pressure_20261120_dev.json).
- The raw source candle DB was read-only; its size and mtime matched the pre-run audit. No validation data was read.
- Research code and preregistration were committed and pushed before the run; result/report and final rejection update are recorded separately after review.
