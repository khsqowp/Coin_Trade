# Phase 8 — NAS 1-minute spot/perpetual archive correction

Audit date: 2026-11-21. Scope: read-only inventory and timestamp-integrity
checks; no signal features, price outcomes, or strategy scores were calculated.

## Repository state checked

- Active checkout: `/Users/user/Desktop/CODE/trading_bot`,
  branch `research/bat-harmonic-validation-20261120`, clean at `6fe4446` before
  this correction.
- Canonical checkout: `/Users/user/CODE/Coin_Trade`, branch `main`, clean at
  `489c538`. The active research branch descends from that commit; no merge or
  overwrite is needed. The canonical checkout's latest commit changes the
  backup-status line in `plan_execution_status_20261120.md`.
- The latest attempted `git fetch origin --dry-run` failed because this Mac
  could not resolve `github.com`. Local remote-tracking refs showed the active
  branch at `6fe4446`; this is not a fresh live-server confirmation.

## Corrected data finding

The previous source screen stated that the checked data root had no spot
OHLCV. That statement described the then-checked `/private/tmp` scoring panel,
not the subsequently organized NAS archive. The read-only path
`/Volumes/home/mac/CODE/trading_data/external/crypto/binance` now contains:

| Dataset | Symbol directories |
|---|---:|
| `spot_klines_1m` | 33 |
| `um_klines_1m` | 35 |
| `um_premiumIndexKlines_1m` | 35 |
| `um_fundingRate` | 35 |

The intersection is 33 symbol directories. TONUSDT has no spot, premium-index,
or funding files in July–September 2026, leaving 32 symbols with all four
monthly series for each of those months. Counts describe the observed paths,
not a point-in-time or survivorship-safe instrument universe.

For those 32 symbols and July, August, and September 2026, 384 monthly Parquet
files were opened read-only. All 288 spot, perpetual-contract, and
premium-index price files had the expected calendar row count, strict
60,000-millisecond increments, and identical per-symbol/per-month open-time
arrays after converting spot timestamps from microseconds to milliseconds.
There were zero price-grid or cross-source timestamp mismatches. The spot
files use microsecond `open_time`; the other two price datasets use
millisecond `open_time`.

The 96 funding files had strictly increasing `calc_time`. Twenty-nine symbols
used 8-hour intervals (93 rows in July/August and 90 in September); three used
4-hour intervals (186/186/180 rows). Funding timestamps show millisecond-scale
offsets from ideal interval boundaries. The local schema names this field
`calc_time`; this audit does not establish its first-publication time or
independently prove how a historical rate becomes chargeable. Funding must not
be used as a signal feature until that temporal meaning is established.

These checks validate only the selected three-month historic price grids.
They do not verify publisher ZIP checksums, all source-file hashes, order-book
fills, bid/ask spread, slippage, point-in-time symbol membership, funding
publication semantics, or an untouched forward interval. July–September 2026
is exposed research history and cannot serve as Core validation.

## Strategy and panel disposition

The new spot archive removes one old data obstacle for studying spot/perpetual
basis. It does not supply a complete source-defined 10–20-minute directional
M2 strategy. The previously reviewed basis-convergence proposals are
two-leg/stat-arbitrage rules without a complete fixed barrier and execution
contract. A custom basis-direction rule would need a new causal mechanism and
pre-registered entry, target, stop, expiry, fill proxy, funding treatment,
baseline, non-overlap rule, and evaluation window. Merely substituting spot
basis for the rejected contract/mark deviation signal is not evidence of a
structurally independent strategy.

The four-role panel's binding disposition is **HOLD / NO SCORE / NO CORE**.
The data QA is useful, but no candidate currently has frozen rules and a
demonstrated mechanism that justifies a historical screen without arbitrary
barrier choices. The next in-scope work is to document a genuinely distinct
candidate and prepare an untouched forward paper evaluation; do not inspect
its forward outcomes before preregistration. Resolve funding-time semantics
separately. The existing OI/positioning route remains blocked by unresolved
historical first-availability timing.

## Reproduction outline

Use PyArrow to read only `open_time` from the three price datasets and
`calc_time,funding_interval_hours` from funding. For each selected symbol and
month, compare the three UTC minute arrays after unit normalization; require
calendar-exact row count, strict 60-second spacing, and exact cross-source
equality. Check funding timestamps for strict ordering and report the observed
intervals without inferring publication semantics. The inspected root and
selection are recorded above; no generated dataset or source file was changed.
