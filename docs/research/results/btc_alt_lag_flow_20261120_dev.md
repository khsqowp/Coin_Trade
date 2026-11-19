# BTC shock → altcoin lag + taker-flow confirmation — development result

**Decision: REJECT.** The single frozen candidate failed the target-first, expectancy, compounded-wealth and benchmark gates. The chronological confirmation window was not opened, and no parameter change or follow-up optimization was performed.

## Trial identity and scope

- Trial ID: `btc_alt_lag_flow_20261120_01`; registry ID 99.
- Preregistration: [`prereg_btc_alt_lag_flow_2026-11-20.md`](../prereg_btc_alt_lag_flow_2026-11-20.md).
- Development interval: 2020-04-01 00:00 UTC inclusive to 2024-01-01 00:00 UTC exclusive; fixed six-symbol USDⓈ-M Futures set: BTC, ETH, BNB, DOGE, SOL, XRP.
- Input: `vision_dev_repaired.sqlite`, read-only. SQLite integrity check: `ok`. Source SHA-256: `7780d5d4e174db4a55ccf7ecc81240e4138ce915a10f164dd22b35778d629914`.
- Code SHA-256: `d2bc81784fcf77edf2e04a99eed4b0736648b4540139929538789c9b2f77a2f6`.
- One candidate rule and one matched leader-selection control. No grid search, no walk-forward tuning, no Monte Carlo/bootstrap, no validation/sealed read.
- Same command rerun produced a byte-identical JSON result (SHA-256 `b6f3b91a4eaf90ca8f8f4861ac5de699c8ccc8712aaa54da6c7ef67ebf8dc220`).

## Main result

| Metric | Lag candidate | Matched leader control |
|---|---:|---:|
| Issued / scorable | 5,071 / 5,071 | 5,071 / 5,071 |
| Target-first M2 | 20.86% | 20.90% |
| M2 Wilson 95% CI | 19.77–22.00% | 19.81–22.04% |
| Non-overlap N / M2 | 4,865 / 20.82% | 4,874 / 20.87% |
| Non-overlap M2 Wilson 95% CI | 19.70–21.99% | 19.75–22.03% |
| M1 direction at 15-minute expiry | 48.47% | 48.02% |
| Mean net return / signal, base costs | −0.1795% | −0.1791% |
| Mean net return / signal, 2× slippage stress | −0.2595% | −0.2591% |
| Final NAV, base costs | 0.0001472 | 0.0001524 |
| Final NAV, stress costs | 0.00000298 | 0.00000306 |
| Base portfolio MDD | 99.9854% | 99.9849% |

Candidate baseline NAVs over the same dates: **cash 1.0**, BTC buy-and-hold **6.5974** at base costs and **6.5944** under stress costs. The candidate ended near zero and lagged its matched control. The lag-ranking mechanism added no measured edge.

The candidate emitted signals on 5,071 of 7,967 eligible BTC shock anchors (63.65% coverage). All 5,071 had complete scoring paths. Long M2 was 17.89% (N=2,901); short M2 was 24.84% (N=2,170). Per-alt M2 ranged from 16.94% (BNB) to 23.92% (SOL); none approached 80%.

Non-overlap candidate trades lost compounded NAV in each calendar-year segment: 2020 `0.1786`, 2021 `0.0208`, 2022 `0.1055`, 2023 `0.3762` (each segment starts at NAV 1 and uses base costs). These are segment NAV multipliers, not annualized returns. The sample spans a pandemic-era bull market, 2022 bear market and 2023 recovery, but the six-name present-day universe is not point-in-time and cannot prove performance across all regimes.

## Red-team and execution checks

The independent read-only reviewer found no result-reversing error in feature timing, completed-bar aggregation, entry delay, barrier ordering, adverse stop gaps, costs, compounding, or benchmark alignment. The reviewer also noted that the tests cover representative synthetic cases, not every possible execution boundary. Local verification: six candidate-specific tests passed; full `chart_predictor/tests` passed 238 tests with one non-fatal Joblib physical-core detection warning. `py_compile` and `git diff --check` passed.

## Interpretation and next action

The frozen development continuation gate required M2 >=80%, positive net expectancy under base and stress costs, and final NAV above cash, BTC buy-and-hold and leader control. The candidate failed all three performance gates by a wide margin. It is therefore rejected without opening the 2024–2026 confirmation interval. Do not tune or repackage this candidate. This test is not evidence that no profitable crypto strategy exists; the six-symbol development screen cannot establish final project success or failure.

No orders or live signals were generated. The source database was not modified. No raw candle rows are included in this report or JSON.

## Source attribution and license

Source: Binance Vision USDⓈ-M Futures historical klines. This report and the aggregate results JSON are attributed to Binance Vision and licensed under **CC BY-NC-SA 4.0**, per [Binance Vision Dataset Terms v1.0](https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md) (last updated 2026-08-26). This screen is for personal, non-production historical research only; it must not be used to generate live trading signals or redistributed commercially. Kline field definitions are documented in the [Binance Public Data README](https://github.com/binance/binance-public-data/blob/master/README.md).
