# Synthetic future-peek control expansion — 2026-11-19

## Scope

Expanded the deliberate future-peeking negative control in `chart_predictor/tests/test_crypto_divergence_causality.py`. The existing positive prefix-invariance and connected signal-to-execution checks already covered the registered timeframe/horizon grid; this change extends the negative control from 1-minute-only to every registered timeframe and horizon.

## Frozen synthetic check

- Timeframes: 1, 5, 15, 30, and 60 minutes.
- Horizons: 10 and 20 native bars.
- Test cells: 10.
- The synthetic OHLC suffix after the 1,000th native bar is shifted down by a fixed 60 price units, preserving positive prices and internally consistent OHLC bars in the fixture.
- A deliberately invalid macro feature reads the full-sample first and last close and applies that future-derived direction to earlier bars. The test requires the injected suffix to flip the feature before the cutoff and to change the emitted pre-cutoff divergence signatures. This is a negative control, not a candidate strategy.

## Verification

- New negative-control cells: **10 passed**.
- Full focused suite covering divergence causality, engine, backtest, robustness, R019 block calibration, and R019 missingness: **254 passed**.
- No market data, exchange response, strategy outcome labels, or performance results were read or generated.

## Interpretation and remaining gates

This strengthens the causal test harness only. It does not validate a trading signal, open M2 outcomes, or cure R019-P's zero-eligibility missingness diagnostics. The independent agent novelty review found no admissible new candle-only 1-minute candidate among the already exposed Phase 0–8 families. Market outcome testing therefore remains closed until a genuinely distinct preregistered input/mechanism and all data, inference, and source-provenance gates are cleared.
