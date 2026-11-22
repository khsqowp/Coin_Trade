# AWS credit sprint (2026-11-20 → 2026-12-03)

Budget: ~$90 credit, expires ~2026-12-04. Region ap-northeast-2. Spot only, auto-shutdown, all resources
torn down by 12-03. Funding-rate strategies excluded (user: failed).

## Rules (apply to every item)
1. Pre-register each item's hypothesis, params grid, pass rule in `sprint/<id>/PREREG.md` BEFORE running.
2. One shared trial ledger `sprint/ledger.csv` (every tested variant counts). Final step applies one
   Reality Check / Deflated Sharpe over the whole sprint pool.
3. Chronological holdout: data after 2026-06-01 is NEVER touched until the final freeze run (item Z).
4. Pass = beats matched null (>=95 pctl), positive in >=60% of untouched symbols, survives 2018/2022
   windows, adjusted for total sprint trial count. Anything else = no edge.
5. Cost caps per item below. Stop item if cap hit.

## Items
| ID | Work | Data | Compute | Cap |
|----|------|------|---------|-----|
| D1 | Download Binance public data (data.binance.vision): 1m/15m/1h klines, 30+ USDT perps, 2019+, to S3 parquet | public | small | $3 |
| D2 | Re-run regime study rows dropped for no 15m history; add `btc-max10-nyse-close` on alts | D1 | small | $2 |
| D3 | Re-run TIMEOUT null (`crypto-15m-previous-candle-contrarian`) split across workers | D1 | medium | $3 |
| S1 | Implement remaining spec-complete archive strategies not yet in harness (priority 3, ~100) and mass backtest on 30-coin universe | D1 | large | $12 |
| S2 | Cross-sectional family: momentum/reversal/low-vol/volume-shock rank long-short and long-only, daily+4h, 30+ coins, shared-capital | D1 | medium | $8 |
| S3 | Pairs / stat-arb: cointegration & z-score spread among majors and sector baskets, rolling hedge ratio, walk-forward | D1 | medium | $5 |
| S4 | Calendar/time-of-day effects on 1m-1h: hour-of-day, day-of-week, NYSE/Asia/London open, month turn; circular-shift null | D1 | medium | $4 |
| S5 | Volatility structure: vol-breakout, compression→expansion, vol-targeted long baskets, realized-vol timing of B&H | D1 | medium | $4 |
| S6 | ML baseline: gradient boosting on price/vol features, purged walk-forward CV, label = next-N-bar return sign; must beat linear baseline and null | D1 | large | $12 |
| S7 | Plateau stress for finalists: wide param grids (x4 range) for 6 finalists + regime K=3 combo | D1 | large | $6 |
| S8 | Execution realism: re-cost all sprint winners at 2x fees, 1-bar delay, spread by volume rank | all | small | $2 |
| S9 | Tick research (only if Codex tick triage finds >=2 weeks continuous trades): microstructure signals, order-flow imbalance, 1s bars | tick parquet | large mem | $10 |
| Z  | Final freeze: pool all trials, RC/SPA/DSR, single touch of post-2026-06-01 holdout for survivors, report | all | small | $2 |

Total cap ~$73; ~$17 reserve.

## Schedule
- 11-20..11-23: D1 data to S3, harness portable runner (job = one param/symbol shard → one csv row set to S3).
- 11-23..11-27: D2, D3, S1, S2 in parallel shards.
- 11-27..12-01: S3..S7, S9 if eligible.
- 12-01..12-03: S8, Z, teardown, report. Verify no instances/volumes/snapshots/EIPs/NAT remain.

## Infra
- S3 bucket `ochestration-sprint-302263081555-apne2` (private, block public access).
- EC2 spot (c7i/c7g big, r7 for memory-heavy), user-data runs shard then `shutdown -h now`
  with instance-initiated-shutdown-behavior=terminate.
- No NAT gateway, no ELB, no RDS (avoid idle charges).
