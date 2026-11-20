# Cross-asset seesaw exploratory screen

- Leaders: BTCUSDT, ETHUSDT, XRPUSDT, LTCUSDT
- Targets: 32
- Signals: 1,118,560
- M2: NOT MEASURED (no source-defined barrier rule)
- All splits are previously exposed; not OOS evidence.
- Spread/slippage are unavailable; costs are fee proxies only.
- Net means use zero returns for eligible no-signal anchors; coverage uses target-hour opportunities.
- Data fingerprint: `cfef7ec135d24a933b8b037bf2c44a2ccbf06f06cf2fc01f140b60f4ced7735e`

| Horizon | Split | Signals | Coverage | Non-overlap market N | M1 | Gross/opportunity | Net base/opportunity | Net stress/opportunity | Base 95% CI | Stress 95% CI |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| 1h | development | 543,936 | 99.994117% | 16,998 | 51.619124% | 0.010370% | -0.089517% | -0.289505% | [-0.00100689146326341, -0.000784332734681509] | [-0.0030067708679342724, -0.002784326851982526] |
| 1h | validation_exposed | 188,160 | 100.000000% | 5,880 | 50.321003% | -0.001851% | -0.101813% | -0.301813% | [-0.0011733791099744703, -0.0008683163153779985] | [-0.0031733791099744697, -0.0028683163153779977] |
| 1h | evaluation_previously_exposed | 162,784 | 100.000000% | 5,087 | 50.084161% | 0.000564% | -0.099349% | -0.299349% | [-0.0011642194764337286, -0.0008120556192869964] | [-0.0031642194764337278, -0.0028120556192869953] |
| 4h | development | 135,968 | 100.000000% | 4,249 | 50.506737% | -0.014344% | -0.113820% | -0.313820% | [-0.0015378536884884492, -0.0007269101638350567] | [-0.0035378536884884486, -0.002726910163835056] |
| 4h | validation_exposed | 47,040 | 100.000000% | 1,470 | 49.866071% | 0.003114% | -0.096651% | -0.296651% | [-0.001621531750719685, -0.00028259489394820105] | [-0.003621531750719684, -0.0022825948939482004] |
| 4h | evaluation_previously_exposed | 40,672 | 100.000000% | 1,271 | 50.386015% | -0.030670% | -0.130296% | -0.330296% | [-0.002070891096254106, -0.0005594789701356646] | [-0.004070891096254105, -0.0025594789701356637] |

## Screening decision

REJECT for progression to M2 design: neither horizon has positive net mean under base and stress costs; the net means are negative and synchronized confidence intervals are below zero. This exploratory result does not establish a universal absence of cross-asset effects.

See `summary.json` and `signal_ledger.csv.gz` for every issued event.
