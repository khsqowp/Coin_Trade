# Comparable evaluation protocol v1

Frozen: 2026-11-20. This defines the first common comparison pass; it does not
retroactively change any row in `registry.jsonl` and does not grant an approval
to trade or delete data. A result that fails a data gate is `BLOCKED` or
`VALIDATION_REQUIRED`, never silently repaired.

## Scope and decision rule

Evaluate KR equities, US equities, and crypto perpetuals as three independent
leaderboards. Do not compare a crypto target-first hit rate with a stock CAGR,
or rank KR against US. For a candidate to be considered validated, it must meet
the market-specific hard thresholds below on a genuinely untouched OOS sample,
under both named cost scenarios, with the required sample count, and survive
the data, execution, and robustness gates. Historical published outputs are
triage evidence only unless their exact input fingerprint, split, execution
model, and cost scenario can be reproduced.

## First comparable periods and eligibility

| Market | Primary comparison input | Period rule | Current eligibility blocker |
|---|---|---|---|
| KR stocks/ETFs | Local 92-file KIS daily CSV cache; core cohort excludes confirmed inverse ETF `114800` (91 symbols) | Intersection of valid dates across the frozen eligible symbols; use the longest intersection after all symbols pass OHLC, zero-volume, corporate-action, and stale/missing-row checks. Split chronologically into development, validation, and one sealed final segment before candidate selection. | Current-survivor list, not point-in-time membership; 457 zero-volume rows in the original 92-file cache; starts vary by symbol; corporate-action provenance unresolved. Current cache cannot support a validated historical stock result. |
| US stocks/ETFs | Local 92-file KIS daily CSV cache; core cohort excludes confirmed inverse ETF `SH` (91 symbols) | Same intersection rule, independently for US. Freeze benchmark and cohort; use close-only entries/exits until reliable raw OHLC and action history are established. | Current-survivor list, not point-in-time membership; 62 OHLC bound violations and 123 zero-volume rows in the original cache; historical adjustment provenance unresolved. Intraday and bar-stop studies are blocked. |
| Crypto perps | Locally staged Binance USD-M 1h klines, mark-price klines, and funding archives | Candidate-specific intersection of complete symbol-months across required data types; freeze symbols and chronological dev/validation/sealed periods before scoring. Metadata pre-screen finds 36 symbols with a continuous 2023-03–2026-05 span; a timestamp-level audit passed for all 1,404 symbol-months in that cohort. | 919 missing monthly archives and 9 funding interval metadata disagreements remain outside the selected cohort. Mark gaps were recovered (113/113). Inputs are 1h only and cannot support 1m–30m claims. Universe survivorship and historical listing/delisting status remain open. |

The “common period” is not a hand-picked date range. A deterministic preparation
step must emit the exact first/last timestamp, included/excluded symbols, row
counts, gap counts, source fingerprints, and split boundaries for each market.
No OOS interval may be reused for tuning, threshold selection, or choosing among
symbols/strategies. The sealed segment is opened once, after the candidate and
all execution rules are frozen.

## Market-specific scorecards

### KR and US equity / ETF

- Hard gates per market: net CAGR >= 20%, maximum drawdown <= 30%, annualized
  daily Sharpe >= 1.0, and at least 200 independent completed OOS round trips.
- Report portfolio daily NAV statistics separately from trade-level round-trip
  count. A bar observation is not an independent trade. Also report the
  benchmark, exposure, cash, turnover, and symbol/concentration contribution.
- Primary history is close-only, next eligible close execution, with explicit
  terminal liquidation. Do not claim intraday fill realism from daily bars.
- Point-in-time constituents, delisted/merged symbols, corporate actions, and
  price adjustment semantics are required for promotion. Until acquired and
  verified, all current-cache results are exploratory and fail validation.

### Crypto perpetuals

- Primary metric: target-first hit rate M2 >= 80%; report its Wilson 95% interval.
- Also require total issued-signal M2 and separate non-overlap OOS N >= 200,
  coverage >= 10%, at least 20 symbols, positive net expectancy after costs,
  and lower 95% Wilson bound above the strongest valid preregistered baseline.
- Report M1 time-expiry direction accuracy separately; do not substitute it for
  M2. A target must be reached before stop/invalidation; time expiry is a
  failure, and same-bar target/stop ambiguity is stop-first.
- Use confirmed bars only. Report signal count, abstentions, overlap, per-symbol
  results, target/stop/time-expiry frequencies, net expectancy in R and percent,
  funding paid/received, and adverse data coverage.
- Historical strategy CAGR/Sharpe experiments do not satisfy M2 and are not
  convertible to it without a fresh event-path replay.

## Cost scenarios (source-audited, account-independent)

The source audit in `data_quality_findings_20261120.md` is authoritative for
the first comparison pass. Preserve these as scenario labels, not claims about
the user's actual account:

| Market | Base scenario | Stress scenario | Additional treatment |
|---|---|---|---|
| KR shares | 6.5 bp/side commission + 5 bp/side slippage; 20 bp sell tax | 11.5 bp/side commission + 5 bp/side slippage; 20 bp sell tax | Exempt listed ETFs from the share transaction tax only where instrument classification supports it; do not infer exemption from other taxes. |
| US shares/ETFs | 8 bp/side commission + 10 bp/side slippage | 36 bp/side commission + 25 bp/side slippage | Separately identify any taxes/fees not represented by these legacy assumptions. |
| Crypto USD-M perpetuals | 10 bp round-trip legacy fee proxy | 30 bp round-trip legacy fee proxy | Add observed timestamp-aligned funding only when archive coverage and interval semantics validate. Spread/slippage are unknown; tick trades lack bid/ask, so these scenarios cannot establish fill realism. |

Any account-specific fee table or measured spread/slippage may replace a
scenario only in a newly versioned preregistration. Never alter a past result
row or label a legacy fee proxy “actual costs.”

## Robustness gates before promotion

1. Causal execution replay with fees, slippage, taxes/funding, gap handling,
   terminal liquidation, and conservative same-bar ordering.
2. Walk-forward OOS slices plus one untouched sealed period; show each slice,
   not only concatenated aggregate metrics.
3. Parameter neighborhood/plateau report for every tuned parameter; record the
   full grid and trial count. No selecting the best grid cell as a pass.
4. Trade-order Monte Carlo (>=1,000 permutations) and block bootstrap preserving
   loss clustering (>=1,000 paths); report 95th percentile MDD and expectancy
   interval. These quantify path uncertainty; they do not fix biased data.
5. Regime, symbol, and concentration leave-outs; multiple-testing adjustment
   across all candidates tried in the same research family.
6. Independent red-team replay of ledger arithmetic, timing, data leakage,
   universe bias, costs, and sample independence.

## Stop conditions and artifacts

Stop scoring a market if its source/action history, bar integrity, split
provenance, or required costs cannot be established. Store immutable input and
code fingerprints, preregistration, exact command, full per-trade/event ledger,
daily NAV, metrics, robustness outputs, and red-team disposition under a new
run ID. Append registry entries; never rewrite historical verdicts. A market
may proceed to exploration with weaker data only if each output is explicitly
labelled exploratory and cannot pass promotion gates.

The first implementation piece is `scripts/research/run_contract.py`, a pure
validator for a version-1 run envelope. It checks market identity, data and
preregistration fingerprints, chronological non-overlapping dev/validation/
sealed splits, base/stress cost records, execution-rule declarations, and
market-specific OOS counts/metrics. An empty error list means only that the
record is structurally complete; it does not validate data truth, fill
realism, strategy profitability, or acceptance. The validator has no write
path and is not yet wired into legacy backtest runners. That integration is a
gate before common-run execution.

For crypto, the envelope stores M2 Wilson lower and upper bounds, M1 direction
accuracy, and net expectancy as numeric metrics; rates use fractions in
`[0,1]`. Stock CAGR/MDD likewise use fractional units (for example `0.20` =
20%). The validator rejects non-finite numbers, missing market-specific sample
counts, overlapping splits, malformed hashes, and non-timezone timestamps. It
does not impose performance thresholds; those remain a separately reviewed
decision gate rather than a schema side effect.
