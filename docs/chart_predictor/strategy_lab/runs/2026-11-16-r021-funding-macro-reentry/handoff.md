# R021 handoff

## Current state

- Researcher and red-team agent findings were operationalized as one fixed, historical-only signal hypothesis.
- Corrected replay completed as `2026-11-16-r021b-funding-macro-reentry-boundary-corrected`.
- Candidate is rejected: 10/20-bar target-first 34.1–48.3%, mean net R < 0 for all seven timeframes under base and doubled costs.
- The initial `r021-funding-macro-reentry` output is preserved but invalid because of a split-boundary bug. Never quote its metrics.
- 2025+ data was not opened. The corrected study used R004-exposed development data only.
- No accounts, API keys, trading endpoints, orders, network data pulls, server deployment, or live/manual signals were used.

## Reproduce

From the repository root:

```sh
/opt/anaconda3/bin/python3 -m chart_predictor.run_r021_funding_reentry \
  --db /Users/user/CODE/Coin_Trade/chart_predictor/data/vision_dev_repaired.sqlite \
  --funding-root chart_predictor/data/strategy_lab/2026-11-16-r004-macd-zero-rsi50/funding/screen-through-2025-01-01 \
  --output chart_predictor/data/strategy_lab/2026-11-16-r021b-funding-macro-reentry-boundary-corrected
```

The run directory is immutable by convention; to reproduce, first choose a new output path and update the manifest. Never overwrite the corrected artifact.

## Next work

1. Do not refine R021's thresholds; the full candidate missed both accuracy and net-expectancy gates.
2. Equity agents could only give research/data-gate advice because this checkout contains no licensed KRX/US survivorship-controlled stock+ETF panel. KRX Open API catalogs daily equity and ETF data from 2010 onward, but access requires an account and API-key request. Do not create an account without a separate user instruction.
3. Current public source review found no public itemized KRX purchase quote and no public CRSP stock/ETF subscription quote. KRX price/sample details are exposed after sign-in; CRSP sample materials identify a 25-security historical sample but direct users to request it from subscriptions. No inquiry or purchase was made.
4. Continue only with a materially different, preregistered hypothesis and an eligible dataset. Preserve all null results; do not access a sealed interval for development.

## Agent inputs retained

- Carver (equity hypothesis): daily market direction and relative strength as context, then intraday breakout; no performance evidence.
- Maxwell (equity red team): no admissible test without point-in-time, delisted-inclusive equity/ETF data, corporate actions, costs, and a defined risk gate.
- Zeno (crypto hypothesis): funding crowding + BTC macro direction + pullback/re-entry; this is the fixed mechanism tested here, not a validated edge.
- McClintock (crypto red team): six current survivors cannot support the ≥20-symbol M4 gate; no accuracy qualification.
