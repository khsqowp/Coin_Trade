# Phase 8 — Round M mechanism-specific source review

## Result

Four independent lanes examined funding cross-sectional carry, volatility and
regime mechanisms, calendar/settlement microstructure, and cross-market or
cross-venue signals. **Eligible new candidate count: 0.** No data were
downloaded, no code was run, and no performance was estimated.

## Candidate-class decisions

### Funding cross-sectional carry — mechanism exists, M2 rule does not

A 2026 study describes dollar-neutral long-low-funding / short-high-funding
cross-sectional carry with periodic rebalancing on Hyperliquid. It reports
that relative price losses can dominate funding income and that its taker-cost
scenario is negative. This is a portfolio rebalancing strategy on another
venue, not a single-contract directional signal with fixed target, stop, and
expiry. Adding those barriers would create a new strategy rather than
reproduce the paper. [Paper](https://www.jstage.jst.go.jp/article/jsaisigtwo/2026/FIN-037/2026_168/_pdf/-char/en)

Registry #104–105 already tested per-symbol funding-tail contrarian rules.
Cross-sectional funding dispersion differs in signal construction, but the
available source does not meet the fixed-barrier M2 contract, so no variant was
invented.

### Volatility management / regime — risk overlay, not directional M2

Moreira–Muir's volatility-managed portfolio scales exposure inversely to
lagged realized variance. It does not specify a directional entry or fixed
target/stop/expiry. [NBER paper](https://www.nber.org/papers/w22208)

Reviewed volatility-risk-premium and regime-switching material either depends
on options, VIX, variance swaps, or other unavailable inputs, or describes
risk/exposure management without the required fixed target-first exits.
[Regime-switching paper](https://jornadaseconometria2018.wordpress.com/wp-content/uploads/2018/09/measuring-and-trading-volatility-a-regime-switching-approach.pdf)
Existing squeeze, breakout, ATR-trend, and Pine-regime families were excluded
as overlap.

### Funding-time / calendar microstructure — required signals are unavailable or overlap

Ruan and Streltsov report funding-cycle effects in market quality and
spreads, not a directional entry/exit strategy.
[Paper](https://qihongruan.github.io/papers/Perpetuals_Nov2024.pdf)

Kim and Hansen's quarter-hour effect uses minute-level order imbalance and
reports return association; hourly OHLC cannot reconstruct the signal. The
paper also reports that excluding funding settlement times does not remove the
effect, so it does not support a funding-timestamp strategy.
[Paper](https://arxiv.org/abs/2607.09426)

Cryptocurrency volatility/liquidity periodicity reports calendar patterns,
not complete directional M2 rules; weekday/hour work also overlaps prior
tests (#106 and #108). [Paper](https://arxiv.org/abs/2109.12142)

### Cross-venue / spot-perpetual signals — local inputs absent or overlap

Cross-venue price-discovery research relies on synchronized quotes/order-book
updates and subsecond timing, absent from this hourly single-venue panel.
[Thesis](https://eprints.soton.ac.uk/504578/1/Final_Thesis_for_archive.pdf)

Spot-perpetual basis research requires spot observations; the available
scoring panel is USD-M contract OHLC, mark, and funding. Basis was already
reviewed in prior rounds. [Futures risk-factor study](https://onlinelibrary.wiley.com/doi/10.1002/fut.22425)
BTC/ETH lead-lag, market breadth, and cross-sectional price signals were also
excluded as previous-round/registry overlap.

## Decision

No Round M candidate may be preregistered without adding unsupported barriers
or obtaining unavailable inputs. The correct next step is another distinct
mechanism review or a data-eligibility improvement; do not relabel a portfolio
overlay or a statistical market-quality finding as a directional strategy.
This bounded literature review does not prove universal strategy exhaustion.
No Core has passed; Phase 9 remains blocked.
