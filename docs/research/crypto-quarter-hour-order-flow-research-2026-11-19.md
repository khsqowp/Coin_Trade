# Quarter-hour taker order-flow candidate — literature review

**Status:** reviewed and **rejected for the current strategy mandate**. It is a useful literature reference, not a registered candidate. No local market outcomes, labels, source archives, or new data were opened or downloaded for this note.

## Exact distinction

The source uses `OI` to mean **order imbalance**, not futures open interest. It signs each Binance aggregate trade by aggressor side (`isBuyerMaker=False` means buyer taker), computes signed base quantity, then normalizes by total base quantity in the 10-second interval:

`imbalance = sum(qty * (+1 for buyer-taker, -1 for seller-taker)) / sum(qty)`

The paper's event is the first 10 seconds after each UTC quarter-hour boundary (minute 00, 15, 30, or 45). Signal availability is only after that interval closes. Positive imbalance proposes long; negative proposes short; zero-volume intervals are missing/no signal, never zero-direction trades. A historical execution simulation would enter at the first eligible trade after the 10-second interval and include taker fees, slippage, gaps, and the frozen stop-first rule.

## What the primary paper establishes—and does not

Kim and Hansen's arXiv preprint uses Binance USDT-margined aggregate trades for BTC, ETH, XRP, SOL, DOGE, and ADA, 2021-01-01 through 2024-10-31. It reports positive quarter-hour order-imbalance associations with 4–12-hour forward returns; the 4-hour quarter-hour-only slopes are positive for all six assets, with weaker significance for some assets. Replacing imbalance magnitude by its sign keeps positive estimated effects but leaves several individual 4-hour estimates statistically weak. These are predictive regressions with overlapping horizons and controls, not a 4-hour target-first strategy, calibrated 80% hit rate, or net-of-cost trade result. The six-symbol sample also does not meet this project's ≥20-symbol eligibility rule.

The paper separately predicts the first 10-second opening-window return using a rolling LASSO/logistic model. Its combined model reports mean AUC 0.6011 and 57.12% accuracy on that 10-second label. That is not the same target as the 4-hour order-imbalance regression and is far below the project's 80% M2 target-first requirement. Trading each quarter-hour opening in the paper's direct 10-second direction example earns about 0.5 bp gross per trade, versus a cited standard taker fee of 5 bp per side; that particular 10-second trade is not economically viable at standard taker rates.

The source therefore motivates a narrow, time-phase-specific hypothesis, but does not establish it is profitable, causal, transferable to 20 symbols, or distinct enough from all local taker-flow work. The local source-feasibility review already considered this paper and did not register it, citing material overlap with the existing L2 pilot and mismatch with the target-first study mandate. This note adds exact definitions and outcome interpretation; it is not a new strategy registration.

The user's required horizon is 10–20× the signal bar. For the paper's actual 10-second input interval, that means 100–200 seconds, where the paper reports little predictive association at finer horizons. Its 4-hour result is 1,440× the 10-second event interval. Recasting the event as a 15-minute signal merely because it occurs on a quarter-hour clock would change the signal's actual observation window and is not justified. The separate first-10-second classifier has only 57.12% mean direction accuracy, and its unconditional trade example is fee-negative. Thus the strongest apparent long-horizon result does not fit the user's short-horizon signal requirement, while the fitted short-horizon result does not meet the 80% accuracy gate.

## What a future re-review would have to change

The paper can be reconsidered only under a separately approved multi-hour forecasting objective that does not impose the 10–20× rule relative to the 10-second signal, and only after a novelty review resolves overlap with prior taker-flow/L2 work. Any future test would still require a frozen ≥20-contract universe, timestamped post-window execution, costs, all-issued target-first labels, walk-forward evaluation, 1,000 trade-order Monte Carlo, sensitivity analysis, and the exact-family calibration gate. Those conditions are not met now; no event-history download or M2 backtest should begin under this candidate.

## Current decision

`REJECT — current mandate mismatch and prior overlap decision.` Do not download the full aggregate-trade archive or open target/stop outcomes for this hypothesis. The paper is not evidence of an 80% target-first edge. Prior raw-trade reconciliation on 20 symbols × four UTC dates checked source-field consistency only; it does not establish multi-year archive coverage or this rule's signal performance. Binance Vision data remains historical, personal, non-production research only and must not feed live/manual signals or order execution.

## Independent review and local metadata-only feasibility check

The independent crypto researcher found this is **not an exact duplicate** of R005/R021/R023, but the signed taker-flow input belongs to an already explored family. The new element is the clock-phase event definition and its 4h/8h target-first evaluation—not a novel order-flow feature. The paper's return-regression slope and 10-second direction model cannot be treated as target-first strategy results. The reviewer also identified an execution-anchor mismatch: the paper measures returns from the last trade inside the 10-second signal interval, while an actionable signal becomes available only after the interval closes and must enter later at an executable price. Four- and eight-hour outcomes overlap heavily, requiring event- and cross-symbol dependence-aware inference.

A metadata-only scan of the current worktree's `chart_predictor/data` found 20 files through depth 4, including one SQLite database and no `.zip`, `.csv`, or `.parquet` raw aggregate-trade archive. Among six L2 pilot manifests, the only run with at least 20 symbols captured 120 seconds; its 20-symbol capture interval contained no UTC quarter-hour boundary. This establishes that the current checkout lacks a qualifying local archive/capture for this event; it does not inspect trade rows or prove no copies exist outside this repository. No outcome labels or raw market rows were opened.

The exact first gate, **if this hypothesis is reconsidered under a different horizon mandate**, is manifest/schema-only: freeze ≥20 symbols and dates, verify local trade-level timestamp/quantity/aggressor-side and feature-availability timestamps, then count complete quarter-hour 10-second windows. The independent reviewer proposed ≥99% valid windows per symbol and ≥20 eligible symbols, with zero/missing/late windows separately counted. The current local evidence fails the source/window-coverage prerequisite, and the existing historical rule fails the user's 10–20× signal-bar horizon rule. Do not download or run a market-label screen to work around either failure.

## Source

- Kim, Chan; Hansen, Peter Reinhard. *The Quarter-Hour Effect: Periodic Algorithmic Trading and Return Predictability in Cryptocurrency Futures*, arXiv:2607.09426v2, 2026-07-16: <https://arxiv.org/html/2607.09426>.
- Local duplicate-review context: `docs/research/micro-candle-next-stage-screen-2026-11-19.md`, `docs/research/crypto_oi_candidate_reassessment_2026-11-19.md`, and `docs/research/crypto_microtrial_ledger_2026-11-19.md`.
