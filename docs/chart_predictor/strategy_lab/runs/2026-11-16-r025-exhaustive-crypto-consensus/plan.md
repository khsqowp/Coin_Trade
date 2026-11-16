# R025 — Exhaustive subset consensus replay (crypto development only)

## Question

Do strict-majority same-bar combinations of the four pre-registered Round 5 price-action candidates improve target-first rate or net expectancy on the existing long-history Vision development archive?

## Frozen candidate universe

The atomic rules are exactly `bb_squeeze_breakout`, `orb_funding_session`, `vwap_band_fade`, and `volume_climax_exhaustion`, using their existing `chart_predictor/setups.py` definitions without parameter changes. Enumerate every non-empty subset: `2^4 - 1 = 15` (4 singles, 6 pairs, 4 triples, 1 four-way combination). This is exhaustive only within these four fixed atoms; it is not exhaustive over the repository's full strategy catalog or arbitrary parameterizations.

## Combination and execution rules

- A member casts a vote only when it emits a signal at the same fully closed bar. Strict majority of all subset members is required; ties, missing votes, and conflicts abstain.
- If multiple agreeing members emit stops, use the median structural stop. Entry is next timeframe open. Target is 2R; maximum holding is 12 bars. Underlying 1-minute bars resolve barriers chronologically; stop wins a same-minute stop/target tie.
- Charge 0.05% per side (0.10% round trip). Do not claim this captures futures funding, spread, market impact, or liquidation.
- Use UTC-aligned complete bars for 1m, 3m, 5m, 10m, 15m, 30m, 60m, 120m, and 240m. Process every available symbol in the fixed six-symbol input.
- Enforce a non-overlap cooldown independently per symbol, timeframe, and candidate subset through the 12-bar holding horizon.

## Data and inference boundary

Input: local `vision_dev_repaired.sqlite`, read-only. It is a six-current-symbol survivor panel, historical rows already exposed to prior research, and lacks point-in-time contract membership and funding cashflows. This is exploratory development only. No validation/sealed rows are read or claimed. Results do not establish live/manual signal accuracy or trading profitability.

## Completion checks

1. Enumerate 15 unique subsets and report the expected size counts.
2. Produce one result for each subset × timeframe (135 cells), including zero/low-sample cells.
3. Verify combination semantics and subset counts with deterministic unit tests.
4. Report target-first rate, net notional return, net R, event count, and limitations; do not select a “pass” based on retrospective ranking.
