# Stock momentum robustness diagnostics — exploratory only

This is a post-exposure diagnostic on a current-survivor cache. It is not
untouched OOS evidence, a live readiness assessment, or a strategy approval.
The initial overlapping-window attempt is retained separately and excluded;
the canonical analysis is the non-overlapping v4 run.

## Parameter neighborhood

Frozen lookback neighbors were KR 48/60/72 and US 101/126/151, with
the predeclared cadence, SMA200 on/off, and base/stress costs.

| Market | Cadence | Cells | CAGR min / median / max | MDD min / max | All numeric hard gates |
|---|---|---:|---:|---:|---:|
| KR | monthly | 12 | 29.4% / 44.6% / 72.0% | 46.5% / 47.0% | 0/12 |
| US | daily | 12 | 0.5% / 12.4% / 31.0% | 32.3% / 48.9% | 0/12 |
| US | monthly | 12 | 15.5% / 23.4% / 36.0% | 32.9% / 43.6% | 0/12 |

All 36 cells fail the MDD <=30% gate; no parameter plateau meets the
numeric stock thresholds. Each cell remains exposed exploratory history.

## Non-overlapping walk-forward pseudo-OOS

Each fold trains on 504 sessions, chooses lookback/gate by training
Sharpe, then tests on the next six calendar months from fresh cash.
Tests advance by six months and do not overlap. The input and strategy
family were already inspected, so these are pseudo-OOS only.

| Market | Cadence | Fold tests | Combined cost | CAGR | MDD | Sharpe | Raw round trips | Sessions |
|---|---|---:|---|---:|---:|---:|---:|---:|
| KR | monthly | 1 | base | 32.6% | 46.9% | 0.805 | 29 | 107 |
| KR | monthly | 1 | stress | 31.8% | 47.0% | 0.797 | 29 | 107 |
| US | daily | 3 | base | 35.7% | 33.7% | 1.381 | 286 | 357 |
| US | daily | 3 | stress | 18.5% | 36.9% | 0.844 | 286 | 357 |
| US | monthly | 3 | base | 42.5% | 31.3% | 1.513 | 76 | 357 |
| US | monthly | 3 | stress | 37.7% | 31.7% | 1.383 | 76 | 357 |

Raw round trips are counts, not proof of independent trades. No combined
walk-forward cell establishes the required 200 independent OOS trades
together with CAGR/MDD/Sharpe gates.

## Path resampling

Daily portfolio returns were permuted 1,000 times and moving-block
bootstrapped 1,000 times with 20-session blocks. Permutation is not
trade-level Monte Carlo because the strategy has overlapping holdings.

| Market | Worst cell permutation MDD p95 | Worst cell block MDD p95 | Lowest block CAGR p05 |
|---|---:|---:|---:|
| KR | 53.7% | 59.6% | -2.0% |
| US | 60.9% | 70.4% | -16.4% |

## Decision

**No strategy passes.** The parameter neighborhood has zero numeric-gate
passes, all sampled paths are high drawdown, and the walk-forward slices
are too short and too exposed to establish independent OOS validation.
The current cache still lacks point-in-time constituents and certified
corporate-action/price provenance. Do not combine these candidates in a
Phase 9 portfolio; none is an individually validated core strategy.

Reproduction command:

```bash
PYTHONPATH=. /opt/anaconda3/bin/python3 scripts/research/stock_momentum_robustness.py \
  --output-dir docs/research/inventory/runs/stock_momentum_robustness_20261120_v4
```
