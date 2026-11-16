# R015 decision

Decision: `reject_self_normalized_procedure_under_registered_screen; inference_blocker_retained`.

The corrected run completed 24 scenarios × 1,000 independent datasets (24,000 datasets total), with 250,000 Brownian reference paths and zero failed replications. Runtime was 68.348 seconds. The result payload SHA-256 is `b30f7e4e97a97773d57106652ef6e4f18764016bb3b37b9b0fef576fbd01f345`.

| Quantity | Result |
|---|---:|
| Overall raw one-test rejection rate, averaged over 288 scenario-timeframe cells | 7.27% |
| Raw per-timeframe rates across cells | 4.0%–13.6% |
| Per-timeframe simultaneous upper bounds passing 7.5% | 7 / 288 |
| Holm FWER across 24 scenarios | 5.1%–32.3% |
| Scenario Holm-FWER upper bounds passing 8.5% | 1 / 24 |
| Scenarios passing all per-frame and FWER gates | 0 / 24 |
| Replication errors | 0 |

The worst raw per-frame rate was 13.6% (simultaneous upper bound 18.0%) at 365 days, mean 40 daily opportunities, `rho=0.9`, common shock fraction 0.75, timeframe 1m. The worst Holm-FWER was 32.3% (simultaneous upper bound 37.8%) at 365 days, mean 40, `rho=0.9`, common fraction 0. The procedure fails the frozen screen, with the clearest failure under strong serial persistence.

## Interpretation and limitations

- The evaluated quantity is null rejection under the registered synthetic score DGP only. It is not observed market accuracy, a trading strategy result, or evidence that R005/MACD/other candidates are good or bad.
- The DGP is stationary, uses a fixed probit-normal heterogeneity and AR(1) latent persistence, and is not claimed to reproduce real forecast-label dependence. A pass would not have validated the market process; failure is a warning that this pivot approximation is not robust under these tested finite-sample conditions.
- The Brownian reference is a finite Monte Carlo approximation (250,000 paths × 2,048 increments); its tail resolution is recorded in `results.json`.
- The R014 run is separately preserved with its audit correction. R015's corrected bookkeeping records raw p-value rejections and Holm family decisions independently, preventing the R014 aggregation mistake.
- The KR and US stock/ETF backtests remain blocked by data lineage/rights/PIT/holdout gates. No new distinct crypto signal was supported by the four-track review; R005 liquidity replenishment remains untested, not a validated candidate.

## Gate

Do not use this procedure for confirmatory R012 labels. No market labels, performance cells, strategy pass claims, or order authorization follow from R015. Any further inference-method work must be preregistered as a new iteration and independently reviewed; R013–R015 do not establish a method that qualifies.
