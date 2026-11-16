# R013 post-run inference audit — correction 1

## Finding

The per-test Wilson intervals in `results.json` were calculated using `12 × simulations` Bernoulli indicators as though timeframe rejections within one Monte Carlo replication were independent. They are dependent in the common-shock scenarios because timeframe score paths share a latent shock. Since the registered grid includes those dependent scenarios, the `12 × simulations` denominator does not provide a valid general Monte Carlo interval for this study. The correct Monte Carlo unit for uncertainty in the average per-test rejection rate is one complete 12-timeframe replication vector, with a cluster-aware interval over independent replications. The existing JSON does not retain per-replication vectors, so those cluster-aware intervals cannot be reconstructed from its aggregates.

The original JSON fields `per_test_95pct_wilson`, `screen_qualified`, and the derived 40/144 scenario-method pass count are therefore withdrawn. They remain in the immutable original artifact for auditability and must not be used as valid confidence intervals or pass evidence. The per-test point rates are descriptive only.

## Conclusion preserved on independent evidence

The preregistered screen required **both** the per-test interval criterion and the familywise error-rate criterion. For each of the six methods, at least one scenario has a family-level Holm-FWER Wilson lower 95% bound above the allowed FWER upper tolerance 8.5%; thus each method fails even without using the invalid per-test interval. The scenario-level FWER indicators are one per independent Monte Carlo replication, so the corresponding Wilson interval denominator is 1,000 independent replications, not 12,000 timeframe tests.

Largest lower FWER bounds by method (recomputed directly from the frozen results JSON): HAC lag 7, 71.40%; HAC lag 14, 63.01%; HAC lag 30, 58.14%; MBB block 7, 41.45%; MBB block 14, 21.65%; MBB block 30, 14.61%. Every value exceeds 8.5% by a wide margin. The conclusion “none of these six procedures qualifies under R013's registered joint screen” remains valid. R013 does not establish that all possible inference methods are invalid.

## Scope and next action

No raw market data, signal labels, or backtest outcomes were opened. No R013 code, manifest, or result JSON was rewritten. R014 uses replication-level uncertainty for per-test rejection rates so this mistake is not repeated. This audit is a dated correction to interpretation, not a replacement R013 result file.
