# US ETF downside-beta test — 2026-11-15

## Decision

Reject this fixed candidate. It did not approach the approximately 20% annual-return research objective and materially underperformed cost-matched SPY and the same-universe momentum comparator on CAGR. The result is exploratory, based on a fixed historical cohort, and is not an untouched out-of-sample test.

## Frozen rule and sample

The fixed universe is SPY, QQQ, IEF, GLD, DBC, and SHY; BIL is a cash-like comparison series only. At each monthly rebalance, calculate each fund's beta to SPY using the 60 common daily return observations ending at the prior month-end, restricted to days when SPY's return is negative. Hold the three lowest-beta funds at equal weights for the next complete calendar month. Ties are resolved by ticker name. Comparators are the same-universe top-three 60-session momentum rule, SPY, and BIL.

Prices are read from the local .kis-cache-local/US_*.csv files and truncated at the exclusive cutoff 2024-11-12. The common daily history starts 2017-08-02 because IEF and SHY have the shortest histories. Eighty-eight calendar months preceded the cutoff; one incomplete/missing month and three months without a valid 60-session signal were excluded, leaving 84 evaluation months from 2017-11 through 2024-10. The input cache is not committed. The stored JSON preserves row counts, date ranges, and daily-return fingerprints, not the underlying proprietary/local price files.

Assumed round-trip costs are 0.36% base and 1.22% stress. Monthly turnover costs are applied using half the L1 change in portfolio weights, with initial entry and terminal liquidation also charged. These are assumptions, not measured fills. CAGR uncertainty uses 10,000 circular 12-month block resamples with seed 20261115.

## Results

| Portfolio | Cost | CAGR | MDD | Annual one-way turnover | CAGR 95% CI |
|---|---:|---:|---:|---:|---:|
| Downside-beta top 3 | Base | 3.21% | −14.32% | 1.14× | −1.07% to 8.21% |
| Downside-beta top 3 | Stress | 2.20% | −15.37% | 1.14× | −2.21% to 7.44% |
| Momentum top 3 | Base | 10.39% | −17.84% | 3.24× | 2.52% to 18.91% |
| Momentum top 3 | Stress | 7.35% | −19.71% | 3.24× | −0.47% to 15.96% |
| SPY | Base | 13.88% | −33.72% | 0.14× | 2.65% to 25.70% |
| SPY | Stress | 13.74% | −33.72% | 0.14× | 2.59% to 25.49% |
| BIL | Base | 2.09% | −0.21% | 0.14× | 0.87% to 3.50% |
| BIL | Stress | 1.97% | −0.62% | 0.14× | 0.79% to 3.35% |

The downside-beta portfolio has lower drawdown than SPY in this sample, but only 3.21% base CAGR and 2.20% under stress. Both CAGR confidence intervals include zero. Its base/stress CAGR is below both SPY and the fixed momentum comparator. Lower historical drawdown alone is not evidence of a superior strategy.

## Validation and limitations

The source was run again from the isolated research worktree against the local cache using the --cache override. Its full JSON output was byte-identical to the independent agent's captured result. The run completed with non-fatal Pandas timezone-to-month conversion warnings. The local CSV data were not present in a clean checkout, so exact reproduction requires the private local cache path.

These are price returns; dividend/distribution reinvestment was not established. The listed funds are a fixed modern cohort rather than a point-in-time fund universe, and costs, market impact, tax treatment, and actual fills are not verified. The 2024-11-12 cutoff is historical and already exposed. There was no independent untouched OOS period or selection correction across prior strategy trials. Do not promote this rule to autonomous/paper/live trading.

## Reproduction

From the repository root, with the local price cache present:

    python3 scripts/research/equity_us_downside_beta_probe.py --cache .kis-cache-local
    python3 -m pytest -p no:cacheprovider -q tests/test_equity_kr_compression_breakout.py

The structured result and source are [equity_us_downside_beta_20261115.json](equity_us_downside_beta_20261115.json) and [equity_us_downside_beta_probe.py](../../scripts/research/equity_us_downside_beta_probe.py).
