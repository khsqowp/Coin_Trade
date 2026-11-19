# Cross-market research continuation audit — 2026-11-19

## Scope and status

Four independent read-only roles were assigned for Korea equities, US equities, crypto next-candle microstructure, and crypto multi-timeframe/red-team review. The parent inspected only the collector and feature-builder source needed to verify taker-field availability, SQLite table schema, tracked research summaries, and official public product/terms pages. No credentials, raw untracked outcome panels, or new market labels were read. No backtest, download, account creation, provider contact, or file modification was performed by the reviewers.

This record synthesizes existing tracked reports and current official public product/terms pages. It is not new strategy performance evidence. Binance Vision-derived findings below remain historical, personal, non-commercial, non-production research and are not authorized for live/manual signal generation or order use. Applicable terms and attribution: [Binance Public Data terms](https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md).

## Crypto status

### Existing evidence

- The micro-candle ledger documents 22 primary target-first M2 cells from Phases 4–8. None reached the frozen 80% M2 point-estimate threshold; the cells are exposed development history, not sealed OOS evidence. Phase 7–8 repeat earlier candle rules at wider intervals and are not independent mechanisms. See [`crypto_microtrial_ledger_2026-11-19.md`](crypto_microtrial_ledger_2026-11-19.md).
- Phase 0 already tested one completed 1-minute candle to the next completed 1-minute close as UP/DOWN/FLAT on six symbols and 777,594 labels. The per-symbol train-majority accuracy was 48.166%, reversal 47.983%, and persistence 45.441%. This was a direction diagnostic, not M2 or PnL. See [Phase 0 preregistration](micro-candle-phase0-preregistration-2026-11-18.md) and [results](micro-candle-phase0-results-2026-11-18.md).
- The RSI/MACD divergence WFA stopped during training after 17 symbols and has no persisted aggregate, OOS, Monte Carlo, or parameter-plateau result. Do not describe it as passed or resume it under its old identity. See [interruption record](crypto_m4_runs/2026-11-18-crypto-divergence-wfa-v1/INTERRUPTED.md).
- The published MTF development screen's best selected cell was 240-minute long, 20-bar M2 35.20%; this was an exposed, post-selection development result without the frozen coverage, uncertainty, cost, and multiplicity gates. A separate BTC macro/sweep probe had 1.7688% coverage, 13.38% M2, negative net R, and did not demonstrate incremental value beyond momentum. See [MTF development summary](round5_mtf_dev_results_20261115.md) and [BTC probe](crypto_macro_mtf_sweep_results_20261115.md).
- R018 paired-inference is a synthetic-method test, not a market strategy; one profile was rejected for excessive FWER. Separate R018 strategy-lab work is a data-readiness gate with zero performance cells. R021's exposed development M2 ranged 34.08–48.31% with negative base/stress net R and only six surviving symbols. See [R018 status](crypto_m4_runs/2026-11-17-r018-paired-baseline-inference/execution_status_20261117.md) and [R021 decision](../chart_predictor/strategy_lab/runs/2026-11-16-r021-funding-macro-reentry/decision.md).

The current crypto SPEC's target-first M2 is distinct from direction-at-deadline accuracy. A successful sealed-period claim also requires the frozen sample, coverage, symbol dispersion, baseline/inference, cost, and single sealed-evaluation rules in the SPEC. Do not treat development WFA or a high raw accuracy as a pass.

### Bottom-up OHLC + buy/sell-flow idea

The defensible question is a single incremental diagnostic: on identical completed 1-minute anchors, does adding one predeclared taker-buy-volume imbalance feature improve next-candle classification versus an OHLC-only model? It is not yet a trading strategy, M2 claim, absorption detector, or live signal.

The historical Vision database schema contains `taker_buy_base` and `taker_buy_quote`; the live collector schema and feature stream do not persist taker-buy fields. Historical results therefore cannot establish live feature availability. The local Vision panel is already exposed to prior research, and the exact feature-by-next-candle comparison has not been preregistered and reviewed. No new classification labels or performance outcomes were opened in this round. The review recommendation is: freeze the estimand/model/baselines, audit same-row feature validity and provenance, and use only an untouched prospective source/period for any confirmatory claim. If a development-only diagnostic is later authorized, label it as exploratory and never use it to assert sealed OOS or M2 success. See [micro-data readiness](crypto-microdata-readiness-2026-11-19.md), [next-stage screen](micro-candle-next-stage-screen-2026-11-19.md), [collector](../../chart_predictor/collector.py), and [features](../../chart_predictor/features.py).

The raw `vision_pit_dev_sample.sqlite` is large and its research history is exposed. The data readiness audit also records that only 67 of 86 symbols have all 70 manifest months; aggregate manifest row counts do not verify per-file contents or point-in-time contract membership. It is not fresh confirmatory OOS.

## Korea stock/ETF status

Existing exploratory tests have not demonstrated the required net CAGR ≥20%, MDD ≤30%, annualized Sharpe ≥1.0, and ≥200 completed OOS round trips. The October transfer generated many symbol/rule/parameter rows, not independent strategy discoveries, and used a current-survivor-focused panel with incomplete delisting/corporate-action lineage. Later KR compression-breakout had 50 trades and negative CAGR; failed-breakdown event returns were negative; top-three ETF momentum missed the required CAGR/MDD/Sharpe. See [transfer report](equity_transfer_2026-10/FULL_TRANSFER_REPORT.md), [compression breakout](equity_kr_compression_breakout_results_20261115.md), [failed breakdown](equity_kr_failed_breakdown_results_20261115.md), and [cross-market inventory](cross-market-strategy-inventory-2026-11-19.md).

The current local panel does not establish a point-in-time stock/ETF universe, complete inactive/delisted population, adjustment/dividend treatment, source lineage, or permitted long-term storage/use. Strategy tuning on it cannot cure those defects.

## US stock/ETF status

No historical US strategy has been proven to meet the same portfolio gates. The October transfer relied on a current-survivor-focused sample and unresolved corporate actions and execution assumptions. US-18's stored `ann` is not compound CAGR, its drawdown is not a compounded NAV MDD, and its holdout is already exposed. Recent downside-beta rotation and one-candle rejection screens did not meet portfolio-level OOS acceptance. See [US-18 archive audit](us18-archive-audit-2026-11-19.md), [US downside beta](equity_us_downside_beta_results_20261115.md), and [one-candle rejection](equity-one-candle-rejection-exploratory-2026-11-18.md).

### Public data-source evidence checked on 2026-11-19

- KRX lists KOSPI, KOSDAQ, and ETF daily-trading APIs from 2010-01-04. Its Open API requires individual sign-in/identity verification or social sign-in, key application, and administrator approval. The current Korean terms restrict Open API use to non-commercial purposes, prohibit providing its information to third parties, and limit each key to 10,000 requests per day. The page does not establish that the API provides a survivorship-free point-in-time security universe, delisting returns, complete corporate actions, or data that may be mirrored to a separate server. Source: [KRX service list](https://openapi.krx.co.kr/contents/OPP/INFO/service/OPPINFO004.cmd), [KRX usage process](https://openapi.krx.co.kr/contents/OPP/INFO/OPPINFO003.jsp), and [KRX Korean terms](https://openapi.krx.co.kr/contents/OPP/INFO/OPPINFO002.jsp).
- CRSP's current product page describes daily/monthly data and corporate actions for more than 36,000 active and inactive securities, with permanent identifiers. Its sample guide says promotional samples are for internal preview/evaluation and are available by request; it does not publish a current price or establish that the sample alone is licensed for backtesting. Source: [CRSP US Stock Databases](https://indexes.morningstar.com/research-data-products/crsp-us-stock-databases) and [CRSP sample data guide](https://www.crsp.org/wp-content/uploads/2023/09/CRSP_Sample_Data_and_Software_Guide.pdf).
- A provider inquiry, sample request, account/key application, purchase, or download was **not** performed. The available tools in this run do not include an email-sending/contact action. The user's prior authorization covered no-purchase sample/quote inquiry only, not account creation or purchase. Public evidence did not surface a direct CRSP quote or a KRX Open API no-account sample containing the required PIT/delisted/corporate-action fields.

## Four-agent decisions and next actions

| Track | Current decision | Next valid action |
|---|---|---|
| Korea equities | No valid performance backtest on current evidence | Resolve licensed daily data access and verify permanent identifiers, historical inactive universe, corporate-action/return semantics, storage rights, and costs before preregistering one new strategy on a sealed interval. |
| US equities | No valid performance backtest on current evidence | Obtain an authorized CRSP/product sample specification and price/rights quote; verify daily stock+ETF fields, delisting and distributions, identifiers, and two-host storage rights. Do not reuse US-18's exposed holdout. |
| Crypto next-candle | Narrow OHLC-vs-OHLC+flow diagnostic is conceptually separable but not confirmatory-ready | Write and red-team a preregistration; audit input-quality and exact shared rows first. The current collector cannot serve live taker inputs. Confirmation requires newly collected untouched data with lawful source terms and verified archive storage. |
| Crypto MTF/red team | No strategy currently demonstrates the user's crypto success gate | Do not reopen interrupted divergence or exposed M2 panels. Candidate discovery must first identify a nonduplicative information source and pass outcome-blind data, frequency, and executable-path gates; then freeze all M2/direction/cost/inference rules before one sealed test. |

## Current workspace boundary

This audit proposes one scoped research-synthesis file; it does not touch the many user-owned untracked research panels in this checkout. The latest prior approved result commit is `b8dde820e17069b185a3781a1ad92ffe26180caf` on `research/round5-readiness-20261115`. This audit record is not yet committed or pushed until its content and citations are rechecked.
