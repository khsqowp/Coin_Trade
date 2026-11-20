# Cross-asset seesaw exploratory screen

- Leaders: BTCUSDT, ETHUSDT, XRPUSDT, LTCUSDT
- Targets: 32
- Signals: 1,118,560
- M2: NOT MEASURED (no source-defined barrier rule)
- All splits are previously exposed; not OOS evidence.
- Spread/slippage are unavailable; costs are fee proxies only.
- Data fingerprint: `cfef7ec135d24a933b8b037bf2c44a2ccbf06f06cf2fc01f140b60f4ced7735e`

| Horizon | Split | Signals | M1 | Gross mean | Net base | Net stress | Base block 95% CI | Stress block 95% CI |
|---:|---|---:|---:|---:|---:|---:|---|---|
| 1h | development | 543,936 | 51.619124% | 0.010370% | -0.089522% | -0.289522% | [-0.0010065052886765174, -0.0007836313654247614] | [-0.0030065052886765167, -0.002783631365424761] |
| 1h | validation_exposed | 188,160 | 50.321003% | -0.001851% | -0.101813% | -0.301813% | [-0.0011733791099744703, -0.0008683163153779982] | [-0.0031733791099744697, -0.0028683163153779977] |
| 1h | evaluation_previously_exposed | 162,784 | 50.084161% | 0.000564% | -0.099349% | -0.299349% | [-0.0011642194764337286, -0.000812055619286996] | [-0.0031642194764337278, -0.0028120556192869953] |
| 4h | development | 135,968 | 50.506737% | -0.014344% | -0.113820% | -0.313820% | [-0.001585973467157357, -0.0007331432380474529] | [-0.0035859734671573563, -0.0027331432380474524] |
| 4h | validation_exposed | 47,040 | 49.866071% | 0.003114% | -0.096651% | -0.296651% | [-0.0015621063073941199, -0.0002797364887961918] | [-0.00356210630739412, -0.002279736488796191] |
| 4h | evaluation_previously_exposed | 40,672 | 50.386015% | -0.030670% | -0.130296% | -0.330296% | [-0.00204873351568481, -0.0004365909170491179] | [-0.004048733515684809, -0.002436590917049117] |

## Screening decision

REJECT for progression to M2 design: neither horizon has positive net mean under base and stress costs; the net means are negative and synchronized confidence intervals are below zero. This exploratory result does not establish a universal absence of cross-asset effects.

See `summary.json` and `signal_ledger.csv.gz` for every issued event.
