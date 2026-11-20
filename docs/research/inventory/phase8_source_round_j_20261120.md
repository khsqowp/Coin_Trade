# Phase 8 — Round J source scan and lead-lag panel

## Scope and verdict

Four separate source lanes were reviewed: social/news research, TradingView
and custom indicators, public trading communities, and GitHub/skills/papers.
**No source-complete, non-duplicate candidate met the frozen M2 requirements.**
One source-inspired BTC/ETH-leader versus lagging-alt idea was eligible only
for a single exposed development falsification screen after review; it was
not eligible for Core consideration.

## Source-lane findings

1. **SNS / academic-social lane:** no complete candidate. A study of abnormal
   spot turnover and disagreement reports weaker future returns, but the
   reported effect disappears in margin-active assets and the work does not
   define target-first M2 barriers. A forced-liquidation-cascade working paper
   requires liquidation/open-interest inputs absent from the eligible local
   historical panel. Sources:
   [Wiley paper](https://onlinelibrary.wiley.com/doi/10.1111/fima.12491),
   [author PDF](https://www.biz.uiowa.edu/faculty/jgarfinkel/pubs/crypto_divop.pdf),
   [liquidation working paper](https://paulfaulkner.com/working-papers/forced-liquidation-cascades/).
2. **TradingView / Pine lane:** no candidate with verifiable source, causal
   signal timing, fixed target/stop/expiry, and reproducible license. The
   nearest quantile-band idea lacked source-complete execution rules and
   overlapped tested breakout/reversal families. PineStats is a framework,
   not a signal. References:
   [strategy FAQ](https://www.tradingview.com/pine-script-docs/faq/strategies/),
   [repainting guidance](https://www.tradingview.com/pine-script-docs/concepts/repainting/).
3. **Community lane:** a grid-trading post was the closest lead, but its
   author-reported results include severe drawdowns and regime failure. The
   post reports a range-month gain of 12.7%, a 27% drawdown, and a 77% maximum
   drawdown in another test; the rule omits adequate funding, reset/anchor, and
   reproducible fill details. It is not eligible for scoring.
   [Original Reddit post](https://www.reddit.com/r/quantfinance/comments/1unu4ib/research_note_2_the_grid_backtest_that_made_me/).
4. **GitHub / skills / papers lane:** no independently reproducible candidate
   with public code/data and fixed M2 barriers. The closest ProSP material
   lacked public reproducible artifacts; a cross-crypto rank strategy lacked
   target-first barriers and overlapped existing registry families.

## Panel decision

The four roles reviewed one fixed adaptation:

- **Blue:** one development-only falsification screen may test whether BTC
  and ETH same-sign prior-hour moves precede a lagging alt's continuation.
- **Red:** no Core progression; this overlaps cross-sectional momentum and
  relative-reversal families, has survival bias, and needs fixed gap, funding,
  costs, overlap, and baseline semantics.
- **Data/Methods:** only exposed hourly contract/mark/funding data are locally
  usable for this question; contract OHLC is the barrier basis, mark is an
  integrity/risk reference, and the fee proxies do not measure slippage.
- **Judge:** conditionally allow one exact development screen only; no tuning,
  no promotion, and no Phase 9.

The resulting fixed rule, debate caveats, and numerical decision are recorded
in [`PREREG_LEAD_LAG_1H_M2_ROUNDK_20261120.md`](PREREG_LEAD_LAG_1H_M2_ROUNDK_20261120.md)
and [`runs/lead_lag_1h_m2_round_k_20261120_v2/report.md`](runs/lead_lag_1h_m2_round_k_20261120_v2/report.md).
It was rejected: target-first M2 was 45.98%, below the stronger same-event
always-short control at 48.46%; net expectation was negative at base and stress
costs. This is a rejection of this one fixed rule, not evidence that all
possible public or custom strategies have been exhausted.

## Data boundary

The inspected archive is a 36-symbol current-availability cohort through
2026-05, but this screen opened only 2023-03 through 2025-02 for scoring. The
cohort is not point-in-time and is already exposed by prior work. The local
archive is hourly, so it cannot validate minute-scale barrier order or claims.
No archive was downloaded or modified. No orders, service changes, or
deployment occurred.
