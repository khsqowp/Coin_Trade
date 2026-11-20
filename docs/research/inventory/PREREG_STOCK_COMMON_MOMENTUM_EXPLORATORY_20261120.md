# Preregistration: common-cost stock momentum replay (exploratory)

Frozen before this replay: 2026-11-20. This is not a new OOS experiment: the
92-symbol current-survivor price histories and earlier momentum results have
already been inspected. The purpose is a same-accounting, same-period
comparison of a small set of already-tested fixed rules, not tuning or
promotion.

## Fixed scope and candidates

- Markets are separate: 92 KR cache instruments and 92 US cache instruments.
  Use the full cache cohort as present; do not choose symbols using this replay.
  Leveraged/inverse instruments are not added. Instruments whose identity or
  ETF classification cannot be confirmed remain flagged rather than inferred.
- Candidate A: monthly rebalance, long-only equal-weight top 10 by 60-session
  close-to-close momentum (KR) or 126-session momentum (US), unchanged from the
  prior recorded candidate definition.
- Candidate B: the same rule with the existing benchmark SMA200 cash gate
  (069500 for KR; SPY for US); signal uses only the last completed close.
- US-only cadence comparison: apply 126-session top-10 momentum at daily versus
  monthly rebalances, with and without the same SMA200 gate.
- No parameter, symbol, timing, or candidate selection based on this replay.

## Data, evaluation period, and fills

- Read only `.kis-cache-local/KR_*.csv` and `US_*.csv`; source data remains
  immutable. For each market independently, require a valid OHLC row and
  positive volume for all 92 instruments on every selected session. The
  inventory audit's fixed eligible panels are 832 KR sessions
  (2023-01-05–2026-08-06) and 1,187 US sessions (2021-07-29–2026-11-12).
- Earlier rows in each fixed panel are warm-up only; the strategy uses 60 or
  126 completed closes as specified. Metrics cover the remainder of each
  panel. Do not call any slice sealed or independent OOS.
- Signal is formed from data through the prior session close. Rebalance trades
  execute at the next eligible session close. Holdings are shares plus cash;
  NAV is marked daily; end-of-window holdings are liquidated with sell costs.
- Baseline: equal-weight buy-and-hold of the same 92-instrument cohort from the
  first evaluation close through the final close, with initial and terminal
  transaction costs. It is not a point-in-time universe correction.
- Report total completed close-out round trips separately from daily bars. A
  partial reduction is not a completed round trip; terminal liquidation closes
  all remaining names. This count is descriptive, not the required independent
  OOS count.

## Frozen costs

- KR base: 6.5 bp/side commission + 5 bp/side slippage; 20 bp sell tax on
  taxable shares only. KR stress: 11.5 bp/side commission + 5 bp/side
  slippage; same sell-tax treatment. ETF tax exclusion applies only to verified
  listed ETF classifications.
- US base: 8 bp/side commission + 10 bp/side slippage. US stress: 36 bp/side
  commission + 25 bp/side slippage. Other taxes/fees are not modeled.
- These are previously audited, account-independent legacy scenarios, not
  measured user-account costs. Both are run for every fixed candidate.

## Metrics and decision rules

- For every market × strategy × cost: CAGR, MDD including initial NAV, daily
  Sharpe (sample standard deviation, annualized by sqrt(252), zero risk-free),
  annual returns, exposure, terminal cash, turnover, round trips, and benchmark
  comparison.
- The aspirational stock thresholds remain CAGR ≥20%, MDD ≤30%, Sharpe ≥1.0,
  and ≥200 independent completed OOS round trips. Since this replay reuses
  exposed survivor-cache data and has no valid PIT universe/corporate-action
  proof, it cannot pass those thresholds regardless of headline metrics.
- Verdict for any high-looking cell is at most `VALIDATION_REQUIRED`; a weak
  fixed candidate may be `REJECT` for this exploratory scope. This run cannot
  select or tune parameters, establish investability, or replace the need for
  delisted constituents, verified corporate actions, clean price histories,
  and a genuinely untouched OOS interval.

## Reproduction and preservation

The runner, exact command, SHA-256 hashes for each input file, code hash,
preregistration hash, complete daily NAV and rebalance/round-trip ledger, and
summary must be stored under a new unique run directory. Do not overwrite
existing files or modify the local cache. Any mismatch with the predeclared
period/cohort or any missing field aborts the run before metrics are emitted.
