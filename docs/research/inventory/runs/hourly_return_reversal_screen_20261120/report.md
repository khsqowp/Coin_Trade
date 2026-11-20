# Hourly return-reversal screen — 2026-11-20

## Decision

**REJECT the source-inspired setup.** Neither preregistered horizon has positive net expectancy at the base or stress cost proxy; both 7-day market-time block-bootstrap 95% intervals are entirely below zero. This is an exploratory historical screen, not a sealed OOS result and not an M2 target-first evaluation.

## Hypothesis and protocol

Xue and Zhou (2026) report a negative association between the prior one-hour return and subsequent 1–4-hour cumulative returns across Binance USDT pairs ([paper abstract](https://www.sciencedirect.com/science/article/abs/pii/S0165188926001612)). This is a narrow source-inspired screen, not a replication of their complete econometric design.

At each completed hourly close, the fixed signal shorts after a positive prior-hour log return and goes long after a negative one; exact zero abstains. Entry is the next hourly open. H=1 exits at that held bar's close. H=4 uses UTC four-hour-aligned signal closes and exits at the fourth held bar's close. No parameter tuning, trend filter, or indicator filter was used. The source does not provide target/stop barriers, so M2 is explicitly `NOT_MEASURED`.

The evaluation used the frozen 36-symbol USD-M cohort and 2023-03 through 2026-05 archive months. These data and all date splits were exposed in earlier studies; the splits below are descriptive only. Costs are the project's fixed 10 bp base and 30 bp stress round-trip legacy fee proxies, plus timestamped archived funding. Spread and slippage are absent, so these are not complete live-execution costs.

## Results

Returns below are per-trade basis points (1 bp = 0.01%); M1 is expiry-close direction relative to the signal close. Confidence intervals are synchronized market-time 7-calendar-day block bootstrap, 1,000 draws. Wilson intervals are not used for promotion because correlated simultaneous symbols violate an independent-trials interpretation.

| Horizon | Period (all previously exposed) | Signals | Coverage | M1 direction | Gross mean | Net base | Base 95% block CI | Net stress | Stress 95% block CI |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1h | Pooled | 993,248 | 98.65% | 51.39% | +0.603 bp | -9.396 bp | [-9.958, -8.889] | -29.396 bp | [-29.956, -28.821] |
| 1h | Development | 604,238 | 98.73% | 51.96% | +1.172 bp | -8.827 bp | [-9.576, -8.161] | -28.827 bp | [-29.525, -28.148] |
| 1h | Validation, exposed | 209,782 | 99.10% | 50.50% | -0.555 bp | -10.555 bp | [-11.723, -9.423] | -30.555 bp | [-31.753, -29.333] |
| 1h | Evaluation, previously exposed | 179,228 | 97.85% | 50.48% | +0.043 bp | -9.957 bp | [-11.198, -8.515] | -29.957 bp | [-31.308, -28.526] |
| 4h | Pooled | 248,130 | 98.58% | 50.50% | -1.119 bp | -11.109 bp | [-13.416, -8.695] | -31.109 bp | [-33.378, -28.798] |
| 4h | Development | 150,953 | 98.66% | 51.01% | +0.352 bp | -9.637 bp | [-12.544, -6.532] | -29.637 bp | [-32.437, -26.830] |
| 4h | Validation, exposed | 52,384 | 98.99% | 49.57% | -3.576 bp | -13.574 bp | [-19.019, -8.673] | -33.574 bp | [-39.253, -28.680] |
| 4h | Evaluation, previously exposed | 44,793 | 97.82% | 49.86% | -3.202 bp | -13.184 bp | [-18.593, -8.020] | -33.184 bp | [-38.284, -28.077] |

At pooled horizons, no symbol had positive mean net return. The largest symbol's share of positive gross winning returns was 3.70% (H1) and 5.19% (H4), below the preregistered 25% concentration limit; this does not offset the failed net-return gates. The flat control is 0 net bp before any opportunity cost. Same-anchor momentum and always-long/short controls are included in `summary.json`; all have negative pooled net means after base and stress fees.

## Gate-by-gate conclusion

- H1: failed positive base/stress net means and failed positive lower bootstrap bounds at both costs; concentration gate passed.
- H4: failed positive base/stress net means and failed positive lower bootstrap bounds at both costs; concentration gate passed.
- Overall preregistered screen: `REJECT_SOURCE_INSPIRED_SETUP`; do not proceed to M2 rule design for this setup.
- Coin core status: no change. M2 target-first rate was not measured, and no result here qualifies as a verified core.

## Reproduction and artifacts

Exact run command:

```sh
/opt/anaconda3/bin/python3 scripts/research/hourly_return_reversal_screen.py --archive-root /private/tmp/cointrade-50_50-data --coverage-json docs/research/inventory/usdm_archive_coverage_20261120.json --prereg docs/research/inventory/PREREG_HOURLY_RETURN_REVERSAL_SCREEN_20261120.md --output-dir docs/research/inventory/runs/hourly_return_reversal_screen_20261120
```

The output directory contains `run.json` (input/code/preregistration hashes and decisions), `summary.json`, `per_symbol.csv`, and compressed `event_ledger.csv.gz`. The run emitted 1,282,253 event rows across both horizons. Targeted tests: 5 passed; compilation, prefix invariance, future-mutation, and `git diff --check` passed. Raw archives were not modified.

## Limitations

1. Prior exposure makes every period exploratory; none is untouched OOS.
2. The fee values are legacy proxies. No spread, slippage, latency, liquidation, or market-impact model is present.
3. M1 is descriptive and close-to-close relative to the signal close; executable gross PnL uses next-open entry. Neither metric is M2.
4. Simultaneous coins are correlated. Block-bootstrap intervals use cross-sectional market-time means; per-event Wilson intervals would overstate independent evidence and are therefore not used for inference.
5. This finding rejects only this frozen contrarian rule at H1/H4 under the stated data and cost assumptions; it does not reject every reversal strategy.
