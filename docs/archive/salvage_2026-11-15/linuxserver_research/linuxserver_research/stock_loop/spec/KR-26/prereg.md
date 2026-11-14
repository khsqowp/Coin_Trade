# KR-26 - Crash10 rebound with own-volume rolling percentile filter (Round 3 prereg)
Written 2026-11-13T18:21:35 before Round-3 runs.

## Signal
10-bar return<=-r; volume_t<=q percentile of prior 250 bars (minimum 120); ret_t>-3%; buy close t, sell close t+h.

## Portfolio slots N
5

## Defaults (fixed)
{'r': 0.2, 'q': 0.3, 'h': 3}

## Stage-2 grid
{'r': (0.15, 0.2, 0.25), 'q': (0.2, 0.3, 0.4), 'h': (2, 3, 5)}

## Common rules
- Development data only; holdout remains locked. Universe and survivorship limits inherit Round 1.
- All entries are at close t; exits are close t+h. Costs use the existing A (Prime) and B (no Prime) models.
- Event hypotheses use eligible=P.liquid(2e9), require finite close at t and t+h, and apply per-stock cooldown after accepted signal bars. Cooldown bars are h; rebalance hypotheses signal every h-th bar.
- Signals use information through t only. Stage 1 defaults are fixed before results are observed.
- Verdict gate: B net mean>0, date-clustered t>=3, both dev halves positive, n>=30. Survivors receive one Stage-2 grid; plateau requires at least 70% cells with mean>0 and t>=2 and every default-axis neighbor mean>0. Final advance additionally requires BH q<0.10.
- Report n, gross/net means, date-clustered and month-clustered t, portfolio Sharpe, break-even cost (=gross mean), A/B, 2x costs, lag-1 robustness, yearly consistency and random-entry baseline.
- Stage-1 BH family: 24 prior hypotheses + 12 new hypotheses = 36; append every Stage-2 cell p-value to this same family before computing q-values.
- Round-3 diagnostics: yearly count/mean; exclusion of 2020-02-15 through 2020-04-30; concentration by stock and entry date; KOSPI/KOSDAQ splits; signal-time liquidity buckets; next-close fill realism; winsorized mean and median; Prime A versus B; pairwise agreement among KR-24 reference and KR-25..27.
- Part A includes KR-24 as a labeled reference diagnostic only; it is not a new trial.
- Random baseline uses 1,000 draws and seed 7. Holdout is not used for any selection, ranking, or decision.
