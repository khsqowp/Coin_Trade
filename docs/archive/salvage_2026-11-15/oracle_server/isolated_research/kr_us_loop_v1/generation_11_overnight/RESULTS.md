# Generation 11 — SPY overnight-only exposure

## Decision

**Reject the fixed overnight-only schedule for this search objective.** Under the preregistered 2 bp per-side execution-cost assumption, it substantially underperformed matched-endpoint SPY buy-and-hold in the full history and both reported partitions. This is a rejection of this one fixed rule, not evidence that profitable automated strategies do not exist.

## Frozen procedure and review

- Preregistration: [`PREREG.md`](PREREG.md), SHA-256 `afbf5d9dc49ba368638fa1d30e7a6ceba2eaf7827e278dd17f039a612efc0ce6`.
- Independent review: root reviewer returned **GO** before performance-data read and reran all seven synthetic tests.
- Tests: 7/7 passed; `compileall` passed. No market data was used by the unit tests.
- Run ID: `GEN11-20261106T124221`. Exactly one performance run; no rule changes or rerun.
- Rule: scheduled MOC buy before auction cutoff and MOO sale next session, every observed session; no signal based on that same close. Strategy interval is previous adjusted close to next adjusted open; it is flat for the daytime interval.
- Costs: 2 bp per executed side, two sides per overnight. Benchmark uses the same initial close and final open, and pays only initial and terminal 2 bp costs.

## Net descriptive results

| Window | Overnight-only CAGR | Sharpe | Max drawdown | Matched-endpoint SPY buy-and-hold CAGR | Sharpe | Max drawdown |
|---|---:|---:|---:|---:|---:|---:|
| Full, 1993-02-01–2026-11-02 | -0.53% | 0.002 | -72.04% | 10.78% | 0.646 | -55.19% |
| 2001-01-02–2016-12-30 | -6.14% | -0.528 | -65.30% | 5.40% | 0.367 | -55.19% |
| 2017-01-03–2026-11-02 (previously inspected) | 0.19% | 0.075 | -30.14% | 15.04% | 0.866 | -33.72% |

The fixed rule failed the preregistered net-CAGR-and-Sharpe comparison in all three windows. The later window and full history are previously inspected and are not OOS. The strategy and benchmark have matched initial/end instants, but the return intervals differ by design: close-to-open only versus continuous exposure. These figures therefore compare the declared timing portfolios; they do not isolate an equal-risk premium.

## Corporate-action and execution-data checks

The local source metadata identifies the input as an unofficial Yahoo chart v8 snapshot with 8,498 rows (1993-01-29–2026-11-02). The attached event file contains 136 dividend events and zero split events. All 136 dividend event dates occur in the observed price index. For each event, the observed day-to-day adjusted-factor ratio `(adjclose/close)[ex-date] / (adjclose/close)[prior session]` agrees with the factor implied by `prior raw close / (prior raw close - dividend amount)`: median absolute relative difference `1.57e-7`, 95th percentile `5.95e-7`, maximum `9.72e-7`. This is an internal consistency check on two fields from the same vendor, not independent proof of event completeness or adjusted-price correctness. See [`CORPORATE_ACTION_AUDIT.md`](CORPORATE_ACTION_AUDIT.md).

Daily bars do not contain MOC/MOO auction fills, auction imbalance, partial-fill behavior, or realized slippage. The 2 bp/side cost is an explicit assumption, not measured execution. SPY dates were not independently reconciled with an authoritative exchange calendar. These limits prevent a confirmatory or live-performance claim even if the descriptive result had passed.

## Interpretation and prior-work overlap

The hypothesis was motivated by published evidence that U.S. equity-index returns differ across overnight and regular trading periods; the New York Fed's *The Overnight Drift* reports positive average overnight drift concentrated in a subset of overnight hours and discusses asymmetric reversal behavior ([staff report](https://www.newyorkfed.org/research/staff_reports/sr917), [Liberty Street summary](https://libertystreeteconomics.newyorkfed.org/2021/05/the-overnight-drift-in-us-equity-returns/)). Those results do not imply that a daily MOC/MOO SPY schedule will beat buy-and-hold after costs.

This candidate is distinct in exact portfolio construction from Gen01's conditional gap-reversal, Gen03's joint overnight/intraday trend timing, and Gen07's cross-sectional reversal-frequency sorting, but it belongs to the already explored overnight-return family and reuses the same previously inspected SPY history. No DSR/PSR, multiplicity-adjusted significance, untouched-OOS, or universal no-edge conclusion is claimed.

## Artifacts

- Freeze: [`FREEZE.json`](FREEZE.json)
- Preflight/review/test ledger: [`attempts_preflight.jsonl`](attempts_preflight.jsonl)
- Run ledger: [`attempts_GEN11-20261106T124221.jsonl`](attempts_GEN11-20261106T124221.jsonl)
- Manifest and input hashes: [`manifest_GEN11-20261106T124221.json`](manifest_GEN11-20261106T124221.json)
- Daily equity/return series: [`equity_curves_GEN11-20261106T124221.csv.gz`](equity_curves_GEN11-20261106T124221.csv.gz)
- Runner/tests: [`run_gen11.py`](run_gen11.py), [`test_gen11.py`](test_gen11.py)
