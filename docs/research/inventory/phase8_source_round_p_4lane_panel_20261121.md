# Phase 8 — Round P: four-lane source scan and adversarial panel

Date: 2026-11-21. Scope: look for source-defined, non-duplicate crypto
perpetual strategies that can be frozen under the repository's existing M2
contract. No candidate outcomes were scored and no strategy backtest ran.

## Source lanes

| Lane | Search scope | Outcome |
|---|---|---|
| SNS | Public posts and video/social strategy references | 0 eligible. The closest Bollinger example lacks an unambiguous executable entry, uses a 1,075-minute expiry rather than the M2 horizon, and overlaps registered breakout/Bollinger families. Other examples were discretionary or lacked fixed exits. |
| TradingView/Pine | Public Pine indicators and scripts | 0 eligible. Leads lacked causal, fixed expiry/exit semantics or relied on delayed pivots, placeholders, or session rules not established for 24/7 crypto; structure/sweep families overlap prior tests. |
| Public communities | Public Reddit and trading-community posts | 0 eligible. Reported H&S, RSI, Bollinger and VWAP/ADX ideas lacked complete source-defined M2 rules or were not distinct from tested families. No comments or private groups were accessed. |
| GitHub/skills | Public repositories and strategy code | 0 eligible. Wick-reversal, funding z-score and taker-flow leads lacked a complete M2 contract and/or duplicated registered families; the OI variant lacked eligible historical inputs. |

The source-specific rounds and references are retained in
[`phase8_source_round_l_20261120.md`](phase8_source_round_l_20261120.md),
[`phase8_source_round_o_cross_crypto_predictability_panel_20261121.md`](phase8_source_round_o_cross_crypto_predictability_panel_20261121.md),
and the agent scout records for this round. “Zero eligible” describes this
bounded search, not all public strategies or all possible hypotheses.

## Independent panel decision

| Role | Verdict | Reason |
|---|---|---|
| Blue | HOLD | No source supplies a causal 10–20-minute perpetual rule with fixed side, entry, target, stop and expiry that also clears registry overlap. |
| Red | HOLD / NO SCORE | Retrofitting missing barriers or shortening a source's horizon after discovery would create a new, outcome-selected strategy. |
| Data/Methods | HOLD | The fixed M2 scorer's anchor/entry semantics differ from the proposed next-candle executable-entry denominator; data defects and source timing remain material gates. |
| Judge | HOLD / NO CORE / NO PHASE 9 | No source-faithful candidate clears the contract and data gates. |

The panel's closest dissent was a cross-venue spot/perpetual basis hypothesis.
The newly inventoried archive may make that input family testable, but no
reviewed source supplied a complete M2 direction, entry, target, invalidation,
and expiry rule. This is a future source/specification question, not a
preregistered candidate. Guo et al. cross-cryptocurrency return predictability
remains a return-forecasting mechanism; converting its output into barrier
hits would be a new adaptation and does not establish M2.

## Binding gates and disposition

1. Keep the M2 primary denominator as all issued actionable long/short
   signals. Pre-entry barrier contact and non-executable entry remain failures
   in that denominator; report executability separately.
2. Freeze causal signal timing, next-bar entry, target/stop/expiry, gaps,
   adverse-first same-bar ties, timeout, fees, slippage, funding, overlap,
   controls, coverage denominator and trial count before opening outcomes.
3. Verify the complete selected data span, OHLC invariants, minute grid,
   mark/funding gaps and funding first-availability semantics. Do not
   interpolate missing observations or treat local SHA-256 as publisher
   authentication.
4. Require all fixed research gates together: all-issued M2 target-first
   point estimate at least 80%, non-overlap N at least 200 across at least 20
   symbols, coverage at least 10%, and positive net expectancy under the
   specified cost scenarios. A historical screen alone is not Core evidence.

Disposition: **HOLD / NO SCORE / NO CORE / PHASE 9 NOT RUN**. No backtest,
outcome scoring, parameter search, data download, or source installation was
performed for this round. The search was bounded to the four assigned source
lanes and registry comparison.
