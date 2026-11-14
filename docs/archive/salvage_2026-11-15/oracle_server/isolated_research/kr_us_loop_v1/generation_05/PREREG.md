# Generation 05 — low-MAX cross-sectional avoidance screen

Date: 2026-11-06. Local exploratory research only. No remote commands, live orders, commit, or push.

## Hypothesis and limits

Bali, Cakici & Whitelaw (2011) report a negative cross-sectional relation between a stock's maximum daily return during the prior month and subsequent expected return. This generation tests one constrained adaptation: long-only portfolios that avoid high-MAX stocks. It is not a replication of their low-minus-high decile long-short portfolio and is not presumed profitable. Literature link: https://pages.stern.nyu.edu/~rwhitela/papers/max%20jfe11.pdf

The prior local catalog has 252-session total-return volatility screens, an inverse-volatility portfolio weighting option, and residual momentum, but no explicitly identified MAX/lottery-return signal in the audited text and Python files. This is a bounded source audit, not proof that no equivalent calculation exists anywhere in historical binaries/generated artifacts.

## Frozen design

- Exactly one candidate per market; no parameter grid, alternate thresholds, ranking variants, or post-result modifications.
- At each exchange-calendar month-end close, calculate each security's MAX21 as the maximum of its 21 most recent valid adjusted close-to-close simple daily returns, including the decision-day return. A complete signal requires at least 18 finite daily returns in that 21-session window. Missing prices are not forward-filled. Invalid/nonpositive returns are excluded; if fewer than 18 remain, the security is not eligible for this signal.
- Among the already frozen PIT-eligible names from the local `data_mirror`, choose the 20 lowest-MAX21 names in KR and 50 in US, with ticker as deterministic tie-break. Hold them at equal weight; if fewer qualify, retain the remainder in cash. Signals are computed after close t, become target weights at open t+1, and remain unchanged until the next calendar month-end decision.
- Long-only, unlevered, no shorting, no derivatives. Use the Gen01/Gen03/Gen04 daily open/close execution and frozen transaction-cost assumptions unchanged. Strict OHLC validation applies to all held and entering names; any invalid/missing bar fails that market attempt rather than silently imputing a price.
- Benchmarks, partitions, market calendars, and universe construction are exactly those described in Generation 01 and its addenda; those partitions are previously inspected and contaminated, not virgin OOS. The PIT mirror's missing symbols, corporate actions, delisting treatment, and KR benchmark/universe limitations remain unresolved.
- Record every market attempt, including setup and data-integrity failures, along with input snapshot hash, code/preregistration hashes, metrics, and daily net-return curve when a valid run completes.
- This generation adds two local strategy trials. Historical all-project multiplicity remains unresolved; no global DSR/PSR/BH or confirmatory claim is allowed. Any positive result is only an exploratory lead requiring repaired data and an untouched prospective holdout.

## Stop rules

Stop and record a market attempt as failed on data-loader, benchmark, signal-causality, invalid OHLC, non-finite-return, or portfolio-bound failure. Do not repair inputs or alter the signal after viewing outcomes. A semantic or implementation correction requires a dated addendum, new code/preregistration hashes, and preservation of all previous attempts.

## Pre-run audit

- Data read boundary: local `generation_01/data_mirror` only.
- Planned attempts: 2 (KR, US).
- Candidate key: `LOW_MAX21_LONG_ONLY`.
- No thresholds or variants may be added after this file and runner are hashed.
