# Generation 07 — US abnormal overnight/daytime reversal frequency (AB_NR)

Registered: 2026-11-06 (Asia/Seoul). This is one exploratory US equity hypothesis. No KR result is claimed because the existing KR price-repair path is not cleared for performance testing. No remote server commands, live trading, commit, or push.

## Rationale and boundary

Akbas, Boehmer, Jiang, and Koch, “Overnight returns, daytime reversals, and future stock returns,” *Journal of Financial Economics* 145(3), 2022, report a cross-sectional next-month return association for stocks with frequent positive overnight / negative daytime reversals, with the return effect concentrated in the long leg. DOI: https://doi.org/10.1016/j.jfineco.2021.09.019. This is a literature-derived candidate, not evidence that it will work in this mirror.

## Frozen signal

1. Use the local US PIT S&P 500 membership and daily adjusted OHLC produced by the existing read-only loader (`adjclose/close` factor applied to O/H/L; adjusted close as C). No additional transforms or parameter search.
2. For stock i and session d, define daytime return `RET_OC = C[d]/O[d]-1` and close-to-close return `RET_CC = C[d]/C[d-1]-1`. Infer overnight return as `(1+RET_CC)/(1+RET_OC)-1`. A session is valid only when current O/C and prior C are finite and strictly positive and the derived terms are finite.
3. For calendar month m, `NR[i,m]` is the number of valid sessions with `RET_CO > 0` and `RET_OC < 0` divided by valid sessions. Require at least 15 valid sessions in m.
4. At month-end m, `AB_NR[i,m] = NR[i,m] / mean(NR[i,m-12:m-1])`, using only the prior 12 calendar months; require at least 10 valid prior monthly NR values and a strictly positive prior mean. The current month's value is not included in its denominator.
5. Rank eligible PIT constituents with finite AB_NR descending, deterministic ticker ascending on ties. Require at least 85% of that date's eligible constituents to have a finite score; otherwise target 100% cash for the next month. When coverage passes, hold the top `ceil(10% * scored eligible names)` equally weighted, long-only. No short leg, leverage, sector filter, stop, or alternative parameter.
6. Form signals after month-end close m and execute at the next exchange session's open. Hold the basket until the next month-end order. Use the existing strict OHLC month-end simulator and its frozen US buy/sell cost assumptions (10 bp each side). Missing/invalid OHLC for any held or entering name fails the full attempt; no imputation.

## Evaluation and stop rules

- Exactly one planned new strategy-market test: US AB_NR long leg. The current mirror's historical windows were already repeatedly inspected; report only as exploratory, even if metrics are favorable. Existing IS/later split and SPY comparison may be shown descriptively, not as untouched OOS or proof of edge.
- Benchmark is local SPY adjusted close under the existing benchmark implementation. Record actual data snapshot hashes, all scored monthly coverage, selected holdings, daily net curve, turnover and exposure.
- Fail closed on unavailable data, invalid adjusted bars, insufficient candidate coverage at all decisions, non-finite signal/weights/returns, execution integrity error, or benchmark failure. Preserve the failure event.
- Historical total strategy-trial count remains unresolved. Do not state confirmatory DSR/PSR/BH inference, universal profitability, or absence of an edge. No parameter tuning after seeing this result. Any correction or follow-up requires a dated addendum and preserved original outputs.

