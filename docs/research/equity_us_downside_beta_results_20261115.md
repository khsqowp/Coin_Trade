# US ETF downside-beta rotation: exploratory replay

**Decision: do not promote this candidate.** Its lower drawdown came with materially lower return than SPY and the fixed momentum comparator; block-bootstrap CAGR intervals include zero under both costs. This is an exploratory replay on an already inspected development cache, not independent out-of-sample evidence.

## Frozen rule and execution

The existing script `scripts/research/equity_us_downside_beta_probe.py` was run without changing its rule or parameters. Universe: SPY, QQQ, IEF, GLD, DBC, and SHY; BIL is a cash-like benchmark. At each eligible month, use the preceding 60 complete common daily-return observations. Estimate each asset's downside beta to SPY using only sessions where SPY's return is negative; hold the three lowest estimated betas equally for the next month. Rebalance on the monthly schedule. The matched momentum comparator holds the three assets with the highest total returns over the same 60-session lookback. SPY and BIL buy-and-hold are also reported.

The script defines base and stress round-trip costs of 0.36% and 1.22%, respectively. These are assumed scenarios, not measured fills. It applies turnover costs to candidate and benchmark portfolios. The strategy is long-only and ETF-only; it does not test individual stocks.

## Data and reproducibility

- Local KIS CSV cache: `/Users/user/CODE/Coin_Trade/.kis-cache-local/US_{SPY,QQQ,IEF,GLD,DBC,SHY,BIL}.csv`, opened read-only.
- Exclusive cutoff: `2024-11-12T00:00:00Z`. The reader stops when it reaches the cutoff timestamp before parsing later OHLC fields.
- Evaluation: 84 monthly return observations, `2017-10-31` through `2024-10-31`. One month was incomplete/missing; three eligible months lacked the required 60-session signal history.
- Script Git blob SHA-1: `0bf4156a6e59dea3232eeac2f720cd3797a3a17a`.
- SHA-256 of exact CSV header plus rows strictly before cutoff:

| Symbol | SHA-256 |
|---|---|
| BIL | `3db16c6b6e71a85a9407b46a1b50db3abd4e4aa4341318661928556d23d63282` |
| DBC | `0fdc1aa73e3f2b8d7adf15eaa9ee9e507288a27e8a75ad77e9217301eecb0026` |
| GLD | `fcdb05f29c8daa6e0eba7c4a57b4dd4282c1cc7a1dff4a5beb39bab8080d7365` |
| IEF | `17a72d1cc98f5377f029986955e22de85b00e988515acdcd8d536c9a119c7191` |
| QQQ | `db69f80dc680dad53353cc20d684fe097bbdb3090eb9968fbf80df396b5e1a2c` |
| SHY | `7ac08e889a36c0ecbc101979acc6f8ef6d34fa1688960881661f4b1ede4b6bce` |
| SPY | `266fee4c0a4467984eee57d4f29b37a00505906b4c74c9f163ac57fe0fc91536` |

Reproduction command from the research worktree (the wrapper redirects the script's cache constant to the local read-only cache):

```sh
PYTHONDONTWRITEBYTECODE=1 /opt/anaconda3/bin/python3 -B -W ignore -c 'import importlib.util; from pathlib import Path; p=Path("scripts/research/equity_us_downside_beta_probe.py"); s=importlib.util.spec_from_file_location("probe",p); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); m.CACHE=Path("/Users/user/CODE/Coin_Trade/.kis-cache-local"); print(m.run())'
```

The script uses trailing information only for each rebalance and reads only rows before the stated cutoff. No external data, network, orders, or cache writes were used. The existing script has no dedicated unit-test file; this replay is not a substitute for such tests or a full independent trade-ledger audit.

An independent agent separately recomputed all seven CSV daily-return series and the 10,000-draw, 12-month circular-block CAGR bootstrap with seed `20261115`; the 8 reported CAGR intervals matched exactly. It also checked the turnover-cost identity `round_trip_cost / 2 × L1 weight change` and the code's daily-NAV drawdown formula. It did **not** independently rebuild the full daily NAV path, so the MDD point estimates remain script outputs rather than independently reproduced figures. The agent confirmed all seven source CSVs ended at 2024-11-11 and that their contents and the research script were unchanged during its review.

## Results

Returns are annualized NAV CAGR and peak-to-trough maximum drawdown, both in percent. Confidence intervals are 95% circular moving-block bootstrap intervals using 12-month blocks and 10,000 resamples with the fixed script seed. Turnover is annual one-way turnover.

| Portfolio | Round-trip cost | CAGR | MDD | CAGR 95% interval | Annual turnover |
|---|---:|---:|---:|---:|---:|
| Downside-beta, equal-weight lowest 3 | 0.36% | 3.21% | −14.32% | −1.07% to +8.21% | 1.14× |
| 60-session momentum, top 3 | 0.36% | 10.39% | −17.84% | +2.52% to +18.91% | 3.24× |
| SPY buy-and-hold | 0.36% | 13.88% | −33.72% | +2.65% to +25.70% | 0.14× |
| BIL buy-and-hold | 0.36% | 2.09% | −0.21% | +0.87% to +3.50% | 0.14× |
| Downside-beta, equal-weight lowest 3 | 1.22% | 2.20% | −15.37% | −2.21% to +7.44% | 1.14× |
| 60-session momentum, top 3 | 1.22% | 7.35% | −19.71% | −0.47% to +15.96% | 3.24× |
| SPY buy-and-hold | 1.22% | 13.74% | −33.72% | +2.59% to +25.49% | 0.14× |
| BIL buy-and-hold | 1.22% | 1.97% | −0.62% | +0.79% to +3.35% | 0.14× |

Downside-beta reduced drawdown by about 19.39 percentage points versus SPY at base costs, but its CAGR was 10.67 points lower. Versus the 60-session momentum comparator, it reduced drawdown by about 3.51 points while losing 7.18 CAGR points. At stress costs its CAGR confidence interval also includes zero. The test did not calculate paired block-bootstrap differences between portfolio returns, so the table is descriptive and does not establish statistically significant relative performance.

## Limitations and next action

The cache is a selected, current ETF set, not a point-in-time universe; historical membership, delistings, corporate-action/distribution provenance, and actual execution costs are not established. The 2017–2024 interval has already been inspected in prior US research, and the rule was selected from an exploratory candidate file. The bootstrap interval does not correct multiple testing or strategy-selection bias. The annual target of about 20% is not met. Maximum drawdown tolerance and portfolio sizing remain undefined.

Keep this candidate rejected for now. A useful next test requires point-in-time total-return data with distributions and a genuinely prospective rule freeze; do not tune this cache after seeing these results.
