# Strategy-methods and candidate review — 2026-11-19

## Objective and constraints

The governing objective is to maximize compounded **net** returns across bullish, bearish, and sideways regimes. Existing acceptance gates remain binding research constraints: stocks/ETFs net CAGR ≥20%, MDD ≤30%, Sharpe ≥1 and at least 200 OOS closed trades; crypto M2 target-first ≥80%, plus its separately fixed outcome-blind OOS sample, coverage, symbol-diversity, uncertainty, and positive net-expectancy gates. These are not competing objectives; they prevent a high raw-return or one-regime result from being accepted as the final strategy.

Regime robustness should be reported, not achieved by peeking at future regimes. The research sequence remains micro-first: establish a causal short-horizon signal, then test whether frozen, lagged higher-timeframe context improves it in new chronological data. No forecast direction, entry, barrier path, PnL, or return claim was produced in this review.

## Validation methods: what transfers and what does not

| Method in the supplied material | Current repository evidence | Correct use / improvement |
|---|---|---|
| Antithetic paths and control variates | The divergence study does not use simulated price paths to price an option or estimate a known model expectation. | These reduce Monte Carlo estimator variance only when paired paths or a valid known-expectation control actually correlate with the payoff. They do not add strategy edge and do not replace trade-order risk tests. Do not apply to historical outcome shuffles. |
| 1,000 Monte Carlo trade-order permutations | `monte_carlo_reorder_mdd()` is implemented with fixed observed net-R outcomes and 1,000 permutations. The prior divergence WFA was interrupted before any output was persisted. | Retain as a sequence-risk check, but label it accurately: it permutes the observed outcome multiset and destroys serial dependence. It does not forecast future returns or model concurrent positions. For a portfolio, calculate daily marked-to-market equity including overlapping exposure, then add a separately preregistered block-resampling risk distribution. |
| Walk-forward, 504 train / 252 test × 5 | The geometry is implemented and frozen in `walk_forward_windows()`. The earlier macro-first RSI/MACD divergence run stopped after 17 symbols and saved no aggregate OOS results; the micro-first gate superseded it. | Require candidate discovery/parameter fitting inside each training window and evaluate only the next chronological test window. Stitch test windows once. Do not resume or relabel the abandoned run. |
| Parameter plateau | `plateau_summary()` checks neighboring grid cells against M2≥80%, N≥30, resolved status, positive net expectancy, ≥80% neighboring passes, and a median-neighbor M2 gap ≤0.10. | Keep the plateau gate. For continuous parameters, explicitly include the preregistered ±10% and ±20% perturbations; one-step categorical/irregular neighbors alone do not prove that tolerance. Do not expand the grid after seeing test results. |
| Block bootstrap | Day-block bootstraps appear in some diagnostics, but the divergence runner has no trade-sequence block-bootstrap MDD output. | Add only as a distinct preregistered risk diagnostic on daily/portfolio returns, with block unit and block-length rule fixed before evaluation. Preserve cross-symbol same-day dependence and overlapping positions. It supplements, not replaces, WFA or the 1,000 trade-order permutation. |
| Triple barrier (target / stop / deadline) | It is the required crypto M2 label in `SPEC.md`; the divergence engine resolves path order conservatively, treats same-bar stop/target ambiguity as stop-first, and returns timeout/unresolved explicitly. | Preserve as the strategy success definition. Report timeouts, unresolved paths, costs, net R, and direction-at-deadline separately. A next-close direction classifier cannot substitute for M2 or return. |

The stated option-pricing example's lower error bars and its reported 7.90/7.97 prices are illustrations from the supplied text, not evidence that any trading rule here has higher expected returns.

## Supplied candidates

### MFI divergence / 80-level cross

**Disposition: reject as currently described; no outcome test.** The codebase has an RSI/MACD divergence mechanism that compares oscillator values at confirmed price pivots and emits at pivot confirmation. Replacing RSI/MACD with MFI while keeping price-divergence structure is not, by itself, an independent mechanism. The proposed “bearish divergence + cross below 80” is also ambiguous between an exit for an existing long and opening a new short. Those are different policies. A short needs its own causal entry confirmation, stop, target, timeout, costs, and gap/fill rules. No MFI implementation was found in the scoped indicator/search pass.

An independent review also found the pivot pairing, MFI calculation period, threshold-cross timing, duplicate suppression, execution contract, and regime-specific failure conditions unspecified. A future proposal is admissible only if it explains what incremental information volume-weighted flow adds beyond the already tested RSI/MACD divergence family and freezes those details before querying outcomes. Merely sweeping MFI periods or thresholds on the exposed archive would be post-hoc tuning.

### “Noise Band” range breakout

**Disposition: reject as currently described; no outcome test.** The submitted description gives no reproducible band formula, fixed session/timezone, breakout confirmation, entry fill, stop, target, end-of-day exit, or friction assumptions. The repository already contains opening-range breakouts, a funding-session opening-range candidate with a 0.25-ATR variant, Bollinger squeeze/breakout logic, and prior range/Donchian exploration. A different name or opening window does not establish a distinct edge.

The claims of $10,000 growing to $150,000, 30% MDD, all-tick testing, and positive blind walk-forward windows were not independently verified and were not used as evidence. The current 1-minute dataset cannot reproduce an “every tick” fill model. Reconsider only if the exact source code or a full, fixed rule specification establishes a genuinely different mechanism and an admissible data/execution contract.

## Decision and next admissible work

1. Do not tune either supplied candidate against the already exposed development period.
2. Keep the validation methods, but correct the risk model: pair trade-order permutations with dependence-preserving block resampling of daily portfolio equity, and explicitly test continuous-parameter ±10%/±20% neighbors.
3. Continue looking for a genuinely distinct, micro-first crypto mechanism; the MFI/Noise Band descriptions do not currently clear novelty and specification gates.
4. For equities, the independent source reviews found no no-signup source presently demonstrated to provide adjusted histories, delisted coverage, point-in-time universes, and Mac/Linux local-storage rights together. Norgate was explicitly declined. No equity outcomes were tested.

This review records research decisions, not a strategy result or approval. The target of maximizing net returns across regimes remains open and unachieved.
