# US-only status: crypto research Rounds 7, 8, 9, 15

This document reports the bounded US work in this task. It does not claim those crypto rounds are fully transferred.

## Inputs and execution assumptions

- Local KIS daily panel: 54 US names; no network calls. The established US cost cases are `KIS_0.36pct` and `USD_0.08pct`; execution uses the existing next-open portfolio engine.
- Round 7 source: `app/crypto_round7_research.py`; baseline signal family is the volume-spike champion. US random controls keep the observed trade-frequency rate and use independent per-symbol/day draws.
- US symbol leave-out names are selected as the five largest realized-PnL contributors. This differs from crypto's fixed ZEC/ARB/VET/XLM/WLD removal and is explicitly not name-equivalent.
- The Round 7 trade-block bootstrap resamples realized net trade returns, not crypto ledger-equivalent daily portfolio returns. Its Sharpe interval is a proxy statistic, not an equivalent transfer.

## Work completed and omissions

- `round7_us.json` records the 500 controls per cost case, symbol/year leave-outs, and 1,000 block-size-20 bootstrap replicates. The runner explicitly records that causal prefix/future-mutation tests were not performed; those checks are therefore incomplete.
- The source-selected Round 8 top ten representatives and all outputs of the original `variants()` function are inventoried in `round8_9_15_us.json`: 151 declared filter/config combinations. They were not evaluated. The original crypto signal/portfolio semantics have no validated US equivalents across all ten families; reporting made-up reduced-grid results would be invalid.
- Round 9 has eight source period cells, but the checked-in Round 8 result has only three experiments and does not contain the source-selected TOP_K12 candidate. Its source artifact declares zero variants. Therefore no US full/period/no-breaker replay is claimed.
- Round 15's original audit counts are preserved as inventory, but no US hypothesis test is recomputed. The source artifact does not include the 300-control trial vector or a full per-hypothesis p-value table. Crypto p-values are not equity evidence.

## Verification boundary

Run the Round 7 runner and Round 8/9/15 inventory runner with `/opt/homebrew/bin/python3.12`. The latter checks the actual source-selected representatives and `variants()` counts. Results are kept separate from shared plan, report, audit, and KR files. These artifacts are uncommitted. Round 8 evaluation, Round 9 reproduction, Round 7 causal checks, and Round 15 US inference remain incomplete.
