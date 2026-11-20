# verify2a — Group A results (pre-registered in ../verify2/SCENARIOS.md)

All numbers are TEST window (last 40% of each symbol file), frozen params from `results/slice_*/summary.csv`, real plugin `signals()` run through `common.engine.simulate` (read-only import). Re-run of all 132 DONE rows reproduces summary `test_return` exactly (`a1_rows_reproduction.csv`, max abs diff 0). Units: percent of 10k capital, 1000 notional/trade, summed over the 5 symbols (harness convention).

## Final tags

| Candidate | TF | Tag | Failed rules |
|---|---|---|---|
| jesse_simple_bollinger | 1h | **DOWNGRADED(A1)** | A1 |
| btc-max10-nyse-close | 15m | **DOWNGRADED(A1)** | A1 |
| btc-macd-15-41-12 | 1d | **DOWNGRADED(A1)** | A1 |
| turtle-system-2 | 1d | **DOWNGRADED(A1)** | A1 |
| btc-bollinger-37-16 | 1d | **DOWNGRADED(A1)** | A1 |
| btc-roc-36-9pct | 1d | **DOWNGRADED(A1,A2)** | A1, A2 |

Tag convention (mine; SCENARIOS.md defines only 'downgraded' for any failure): FAIL = candidate loses money under A3 or A4 (no profit after realistic costs/funding); DOWNGRADED(ids) = fails only statistical/benchmark/portfolio rules; PASS_ALL = none.

## Scenario x candidate

| Candidate | Scen | Result | Key numbers | Rule |
|---|---|---|---|---|
| jesse_simple_bollinger | A1 | FAIL | RC adj p=1.000, SPA adj p=1.000, daily SR=0.031, SR0=0.220, DSR=1.1e-09 | adj p<=0.10 and DSR>=0.95 |
| jesse_simple_bollinger | A2 | PASS | model ret 12.4 vs circ-shift null p95 -0.4 (pctl 98.7); long leg 13.8 vs long B&H x time-in-mkt -4.8 | ret >= null p95 and long leg >= scaled B&H |
| jesse_simple_bollinger | A3 | PASS | base 13.8; delay+1 6.6; slip.05% 8.5; slip.10% -0.4; fee.06% 10.2 | delay1>0 and slip.05%>0 |
| jesse_simple_bollinger | A4 | PASS | gross 13.8, funding cost 1.03 (long 1.03, short 0.00), net 12.8 | net > 0 |
| jesse_simple_bollinger | A5 | PASS | return 13.8%, CAGR-like 6.8%, maxDD -10.5%, Sharpe 0.62, exposure 40%, DD/ret 0.76 | DD/ret <= 1.0 |
| btc-max10-nyse-close | A1 | FAIL | RC adj p=1.000, SPA adj p=1.000, daily SR=0.046, SR0=0.220, DSR=2.2e-07 | adj p<=0.10 and DSR>=0.95 |
| btc-max10-nyse-close | A2 | PASS | model ret 13.1 vs circ-shift null p95 4.3 (pctl 98.8); long leg 12.7 vs long B&H x time-in-mkt -3.1 | ret >= null p95 and long leg >= scaled B&H |
| btc-max10-nyse-close | A3 | PASS | base 12.7; delay+1 10.8; slip.05% 10.3; slip.10% 6.1; fee.06% 11.1 | delay1>0 and slip.05%>0 |
| btc-max10-nyse-close | A4 | PASS | gross 12.7, funding cost 0.57 (long 0.57, short 0.00), net 12.2 | net > 0 |
| btc-max10-nyse-close | A5 | PASS | return 12.7%, CAGR-like 6.3%, maxDD -8.4%, Sharpe 0.93, exposure 26%, DD/ret 0.66 | DD/ret <= 1.0 |
| btc-macd-15-41-12 | A1 | FAIL | RC adj p=0.644, SPA adj p=0.975, daily SR=0.049, SR0=0.220, DSR=1.2e-22 | adj p<=0.10 and DSR>=0.95 |
| btc-macd-15-41-12 | A2 | PASS | model ret 60.9 vs circ-shift null p95 47.8 (pctl 97.5); long leg 70.7 vs long B&H x time-in-mkt 14.2 | ret >= null p95 and long leg >= scaled B&H |
| btc-macd-15-41-12 | A3 | PASS | base 80.3; delay+1 68.6; slip.05% 78.8; slip.10% 76.3; fee.06% 79.3 | delay1>0 and slip.05%>0 |
| btc-macd-15-41-12 | A4 | PASS | gross 80.3, funding cost 1.41 (long 4.14, short -2.73), net 78.9 | net > 0 |
| btc-macd-15-41-12 | A5 | PASS | return 80.3%, CAGR-like 17.2%, maxDD -19.6%, Sharpe 1.07, exposure 94%, DD/ret 0.24 | DD/ret <= 1.0 |
| turtle-system-2 | A1 | FAIL | RC adj p=0.912, SPA adj p=0.869, daily SR=0.047, SR0=0.220, DSR=3.6e-24 | adj p<=0.10 and DSR>=0.95 |
| turtle-system-2 | A2 | PASS | model ret 61.6 vs circ-shift null p95 50.7 (pctl 98.2); long leg 51.0 vs long B&H x time-in-mkt 11.8 | ret >= null p95 and long leg >= scaled B&H |
| turtle-system-2 | A3 | PASS | base 55.7; delay+1 45.2; slip.05% 55.2; slip.10% 54.4; fee.06% 55.3 | delay1>0 and slip.05%>0 |
| turtle-system-2 | A4 | PASS | gross 55.7, funding cost 3.73 (long 4.04, short -0.31), net 51.9 | net > 0 |
| turtle-system-2 | A5 | PASS | return 55.7%, CAGR-like 12.7%, maxDD -18.9%, Sharpe 0.82, exposure 84%, DD/ret 0.34 | DD/ret <= 1.0 |
| btc-bollinger-37-16 | A1 | FAIL | RC adj p=0.770, SPA adj p=0.875, daily SR=0.052, SR0=0.220, DSR=3.4e-41 | adj p<=0.10 and DSR>=0.95 |
| btc-bollinger-37-16 | A2 | PASS | model ret 49.6 vs circ-shift null p95 43.4 (pctl 97.4); long leg 67.7 vs long B&H x time-in-mkt 11.9 | ret >= null p95 and long leg >= scaled B&H |
| btc-bollinger-37-16 | A3 | PASS | base 67.7; delay+1 62.4; slip.05% 67.2; slip.10% 66.4; fee.06% 67.4 | delay1>0 and slip.05%>0 |
| btc-bollinger-37-16 | A4 | PASS | gross 67.7, funding cost 4.90 (long 4.90, short 0.00), net 62.8 | net > 0 |
| btc-bollinger-37-16 | A5 | PASS | return 67.7%, CAGR-like 15.0%, maxDD -12.6%, Sharpe 1.13, exposure 56%, DD/ret 0.19 | DD/ret <= 1.0 |
| btc-roc-36-9pct | A1 | FAIL | RC adj p=0.895, SPA adj p=0.970, daily SR=0.044, SR0=0.220, DSR=6.2e-38 | adj p<=0.10 and DSR>=0.95 |
| btc-roc-36-9pct | A2 | FAIL | model ret 41.3 vs circ-shift null p95 42.5 (pctl 94.4); long leg 57.6 vs long B&H x time-in-mkt 10.3 | ret >= null p95 and long leg >= scaled B&H |
| btc-roc-36-9pct | A3 | PASS | base 57.6; delay+1 45.7; slip.05% 56.4; slip.10% 54.5; fee.06% 56.8 | delay1>0 and slip.05%>0 |
| btc-roc-36-9pct | A4 | PASS | gross 57.6, funding cost 4.77 (long 4.77, short 0.00), net 52.8 | net > 0 |
| btc-roc-36-9pct | A5 | PASS | return 57.6%, CAGR-like 13.1%, maxDD -14.0%, Sharpe 1.04, exposure 58%, DD/ret 0.24 | DD/ret <= 1.0 |

## Method notes and honest caveats

### A1
- Matrix: 132 DONE rows x 1351 UTC calendar days (`a1_daily_pnl_matrix.csv`). Each row's series = sum over symbols of trade `pct` bucketed on the trade's exit date (realised PnL, not mark-to-market); days outside a row's TEST window are 0. Benchmark = zero return.
- Stationary bootstrap, 2000 draws, mean block 10 days, seed 20261120. RC: max_k sqrt(T)*mean_k, null recentred at the sample mean. SPA: studentised statistic with Hansen (2005) consistent recentring (mu_c = mean if mean <= -sqrt(2 loglogT/T)*omega, else 0), omega from the bootstrap.
- Family-level (best row = btc-macd-15-41-12|1d): RC p = 0.644, SPA p = 0.053. So at family level SPA alone would pass 0.10 while RC does not.
- Interpretation choice: the rule says 'p > 0.10 for the best row'. Only macd is the best row; to apply it to every candidate I used each candidate's own single-step adjusted p-value (fraction of bootstrap family maxima >= that row's statistic). This is stricter than the family p for non-best rows and is my interpretation, not literal pre-registered text. Note the family SPA statistic is the max studentised t over all rows, which is attained by a different row than macd (the best raw mean); macd's own studentised t is low because its daily series is very heavy-tailed (kurtosis ~411), hence its own adjusted SPA p (0.975) is far above the family SPA p (0.054). Both are reported; neither rescues any candidate under the per-candidate rule.
- DSR (Bailey and Lopez de Prado): daily SR over each candidate's own TEST window, SR0 from variance of SR across the 132 rows (0.0047) and N = 858. Count of N: sum of `n_candidates_tested` (grid points per row) over rows with an implemented plugin (132 DONE + 4 INELIGIBLE = 858; 846 from DONE rows alone). 45 NO_PLUGIN rows excluded; the TIMEOUT row has no recorded count (not added). The ledger (`results/ledger.csv`) has 146 rows. The pre-registered text said 'N = ledger candidate count'; I used grid points x rows as the task instruction said. SR0 = 0.22 daily is far above every candidate's daily SR (0.03-0.05), so DSR ~ 0 is not sensitive to the exact N; information-only DSR using N = the candidate's own grid (9) is still < 0.36 for all (column `dsr_info_only_own_grid_N`).
- Daily SR is computed on realised-PnL-by-exit-day with huge kurtosis (skew/kurt in `a1_results.csv`); DSR's non-normality adjustment is applied but such tails make asymptotics unreliable.
### A2
- Position series built from the harness trades (held bars entry..exit, bar-return = open-to-next-open). Null: 1000 independent circular shifts per symbol of that position series (preserves trade count/durations; computed exactly via FFT), same per-transition cost (fee+slippage), summed over symbols. The candidate is compared via the same position-based model return (differs from harness return by a few points, both shown in `a2_results.csv`), not the harness figure.
- Long-leg check: sum of long-trade pct vs per-symbol (buy at TEST open, hold to end) B&H x fraction of bars the candidate is long, summed over symbols. B&H is gross of costs. Short-leg figures are reported but the rule only tests the long leg.
- btc-roc-36-9pct fails the null only narrowly (percentile 94.4, model 41.3 vs p95 42.5). Seed fixed (20261120); a different seed could flip it; reported as pre-registered, not rescued.
### A3
- Delay = every signal column shifted one more bar (fill at open t+2 instead of t+1). Slippage/fee passed as arguments to `simulate`. jesse_simple_bollinger is at about -0.4 at 0.10% slippage (not a failing condition by the rule, noted for context).
### A4
- Binance USDT-M `/fapi/v1/fundingRate` was reachable; full history cached to `funding/{BTC,ETH,BNB,SOL,XRP}USDT.csv`. No constant-funding fallback was needed (`assumed_constant_syms` empty).
- Charge: every funding timestamp in [entry-bar open, exit time) x rate x 1000 notional (long pays, short receives). Exit time = exit-bar open, except time/end_mark exits (bar close). Intrabar stop exits are approximated at the exit bar open. Notional is the entry notional, not marked to price. Funding is applied to a spot-data backtest as an overlay; basis and perp/spot price differences are not modelled. The cached BNB and SOL averages are near zero (about 0.000000/0.000003 per stamp); I did not independently verify these against another source.
### A5
- Chronological cash-account sim: trade notional = min(1000, free cash), free cash = 10k + realised PnL - notional of open trades; pnl scaled with notional. With at most one position per symbol (max 5 x 1000 vs 10k) the cap never bound (0 trades skipped), so portfolio total return equals the pooled sum, as a consistency check. Equity is marked at bar closes on the union time grid (adverse excursions inside a bar are not captured, so max DD is optimistic versus the harness's low/high-based MTM). Sharpe = daily equity returns x sqrt(365). CAGR-like = total growth annualised over the grid span (spans differ per timeframe/symbol).
- DD/return ratio uses total (not annualised) TEST return as the denominator.
### Could not run / not done
- Nothing in Group A was skipped. Scenario B* is out of scope. No re-tuning was done. common/, plugins/, results/ untouched; nothing committed.

## Files
`lib.py`, `a1_build.py`, `a1_stats.py`, `a4_fetch.py`, `a2345.py`, `test_verify2a.py` (pytest, 5 pass); outputs `a1_*.csv/json`, `a2..a5_results.csv`, `funding/*.csv`.
Run order: `a1_build.py`, `a1_stats.py`, `a4_fetch.py`, `a2345.py` (python from `../bb_stoch_stc/.venv`, cwd `strategy_bt`).
