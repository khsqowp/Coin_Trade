# R016 — synthetic event-level target-first inference calibration

Status: method-only calibration; no market data, market labels, strategy signals, or trading results are inputs.

## Question and frozen null

Does a synchronized stationary-block bootstrap max-t lower-bound procedure control family-wise false promotion when the target-first rate is exactly 0.80 and outcomes overlap in time, share common shocks, and are issued in clusters?

The null is marginal target-first probability 0.80 under a Gaussian latent-variable construction. Each replication generates 20 synthetic symbols, 12 timeframe claim ledgers, and separate 10/20-horizon claims (24 claims). Outcomes use overlapping future windows of common, symbol-specific, and timeframe-specific AR(1) latent processes. Forecast issuance is Markov-clustered and independent of the generated outcomes. Target-first labels are synthetic Bernoulli outcomes, not simulated price barriers; this is strictly a first-stage dependence/inference stress test.

## Analysis families

Each claim contributes two outcome-blind samples: all emitted events and a greedy earliest-event non-overlap subset (skip the registered horizon after selection, separately by synthetic symbol and claim). Both denominator interpretations enter one joint family of up to 48 claims; the method may not choose whichever branch looks better. A claim is eligible only if its timeframe's generated raw coverage is at least 10% and its selected denominator has N≥200. Coverage is emitted events divided by every scheduled symbol×timeframe×bar opportunity. No eligible claim means no rejection for that replication.

The candidate one-sided simultaneous lower bound is a synchronized stationary bootstrap over anchor-time rows, carrying all symbols/claims together. The max-t critical value is computed over eligible claims. The type-I outcome is any eligible lower bound strictly above 0.80. Compare mean block lengths 10, 20, 40, 60, 90, and 180 days without selecting a favorable block after results.

## Calibration gates

- Primary diagnostic: replication-level family-wise false-pass proportion and 95% Wilson interval.
- A method/block setting is not qualified if its 95% Wilson upper bound exceeds 6%, any replication errors occur, or sensitivity settings materially disagree.
- Pilot simulations are screening only. A possible qualified method requires a separately fixed, larger simulation count and independent seed, plus empirical confidence-bound coverage, alternative DGPs, unresolved-label and baseline-comparison stress tests. No pilot can authorize market labels.
- Results must retain both denominator branches and eligibility rates. Failure to reach N≥200/coverage≥10% is reported as an ineligible synthetic claim, not silently removed from the DGP summary.

## Known limitations / not covered by this iteration

This DGP does not simulate OHLC paths, same-bar barrier ties, costs, missing/unresolved labels, exchange feed failures, or a baseline policy. It therefore cannot approve the full R012 inference protocol. It calibrates only a narrow candidate CI procedure under this specified synthetic outcome process. Passing would not establish market validity; a failure rejects this candidate under the tested DGP and requires a new preregistered method iteration.

## Diagnostic profile extension

After the persistent-DGP pilot rejected the candidate procedure, a separate diagnostic profile was added before running it: set common, symbol, and frame AR coefficients to zero while retaining shared same-day shocks and overlapping 10/20 future windows. This isolates whether the observed failure is driven by long persistence versus overlap/cross-symbol dependence. It is a diagnosis only; its result cannot replace or erase the persistent-DGP failure. No acceptance rule or metric is relaxed.

An additional implementation sanity profile was specified before running it: zero AR coefficients, no overlapping future windows, independent claim outcomes, and independent issuance. This is an IID Bernoulli(.80) result-label baseline with the same 48-claim family and eligibility gates. Mean block lengths 1, 2, and 5 test the near-independent baseline. A failure here points first to implementation/estimand or multiplicity handling, not difficult temporal dependence. A second diagnostic retains same-day common shocks to isolate cross-sectional dependence.

## Provenance

- Script: `scripts/research/crypto_r016_synthetic_event_calibration.py`
- Tests: `chart_predictor/tests/test_r016_synthetic_event_calibration.py`
- No market data is read or written.
