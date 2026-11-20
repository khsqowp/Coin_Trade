# Cross-asset seesaw exploratory screen

- Leaders: BTCUSDT, ETHUSDT, XRPUSDT, LTCUSDT
- Targets: 32
- Signals: 1,118,560
- M2: NOT MEASURED (no source-defined barrier rule)
- All splits are previously exposed; not OOS evidence.
- Spread/slippage are unavailable; costs are fee proxies only.
- Funding at the exit timestamp is ambiguous; both inclusive and exclusive results are reported.
- Net means use zero returns for eligible no-signal anchors; coverage uses target-hour opportunities.
- Data fingerprint: `cfef7ec135d24a933b8b037bf2c44a2ccbf06f06cf2fc01f140b60f4ced7735e`

| Horizon | Split | Signals | Coverage | Non-overlap market N | M1 | Gross/opportunity | Net base (exit in) | Net stress (exit in) | Net base (exit out) | Base 95% CI | Stress 95% CI |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| 1h | development | 543,936 | 99.994117% | 16,998 | 51.619124% | 0.010370% | -0.089517% | -0.289505% | -0.089611% | [-0.0009996863116897609, -0.0007722100653308122] | [-0.002999565716360623, -0.0027722100653308113] |
| 1h | validation_exposed | 188,160 | 100.000000% | 5,880 | 50.321003% | -0.001851% | -0.101813% | -0.301813% | -0.101829% | [-0.0011780992478982032, -0.0008788561122252363] | [-0.0031780992478982017, -0.002878856112225236] |
| 1h | evaluation_previously_exposed | 162,784 | 100.000000% | 5,087 | 50.084161% | 0.000564% | -0.099349% | -0.299349% | -0.099368% | [-0.001174285540989649, -0.0008226388691460262] | [-0.003174285540989648, -0.0028226388691460257] |
| 4h | development | 135,968 | 100.000000% | 4,249 | 50.506737% | -0.014344% | -0.113820% | -0.313820% | -0.114288% | [-0.0015590492739704065, -0.0006981818866740663] | [-0.0035590492739704057, -0.0026981818866740662] |
| 4h | validation_exposed | 47,040 | 100.000000% | 1,470 | 49.866071% | 0.003114% | -0.096651% | -0.296651% | -0.096797% | [-0.0015254038621070089, -0.00025768151323792265] | [-0.003525403862107009, -0.002257681513237922] |
| 4h | evaluation_previously_exposed | 40,672 | 100.000000% | 1,271 | 50.386015% | -0.030670% | -0.130296% | -0.330296% | -0.130398% | [-0.002083171108382701, -0.0007659411788190229] | [-0.0040831711083827, -0.002765941178819022] |

## Screening decision

REJECT for progression to M2 design: neither horizon has positive net mean under base and stress costs; the net means are negative and synchronized confidence intervals are below zero. This exploratory result does not establish a universal absence of cross-asset effects.

See `summary.json` and `signal_ledger.csv.gz` for every issued event.
