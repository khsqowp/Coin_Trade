# Round K — BTC/ETH-consensus lagging-alt M2 screen

**Decision: REJECT this fixed specification.** This was one exposed-history
development screen, not independent OOS evidence and not a Core candidate.

## Frozen experiment

- 1-hour Binance USD-M contract klines, 36-symbol common historical cohort;
  BTC and ETH are leaders and 34 alts are targets.
- Development window: `[2023-03-23 15:00 UTC, 2025-03-01 00:00 UTC)`.
- Long when BTC and ETH's prior completed-hour returns are both positive and
  the alt return is below their mean; short on the symmetric negative case.
- Entry at the next hour's open. Risk is the simple mean of 14 completed true
  ranges. Target and stop are each 1R. Stop-first intrabar tie; ten-hour limit.
- Funding uses actual settlement timestamps. Fees are fixed 10 bp base / 30 bp
  stress round-trip proxies. Spread and slippage were not measured.
- Full issued-signal sample is scored; per-symbol and market-time non-overlap
  samples are separately reported. Two same-event directional controls are
  evaluated with the same entry, risk, barriers, funding, and horizon.

## Results

| Sample / metric | Result |
|---|---:|
| Eligible alt-hour opportunities | 577,218 |
| Issued signals / coverage | 201,648 / 34.93% |
| All-issued target-first M2 | 92,723 / 201,648 = **45.98%** (95% Wilson 45.77–46.20%) |
| Per-symbol non-overlap M2 | 21,973 / 47,877 = **45.89%**; 34 symbols |
| Market-time non-overlap M2 | 786 / 1,663 = **47.26%**; 30 symbols |
| M1 direction-at-expiry | **31.13%** (flat band counts as not correct) |
| Exit counts | 92,723 target; 97,916 stop; 2 stop-gap; 11,007 timeout |
| Mean net return, base / stress | **−0.1295% / −0.3295% per signal** |
| Mean net R, base / stress | **−0.1354R / −0.3504R** |
| Always-long M2 / mean base net | 45.28% / −0.1416% |
| Always-short M2 / mean base net | 48.46% / −0.0786% |

The candidate's Wilson lower bound (45.77%) does not exceed the stronger
same-event control (always-short, 48.46%). Net expectancy is negative at both
cost levels. The directional prediction does not approach the fixed 80% M2
gate. The exact frozen rule is rejected; no parameter, symbol, barrier, or
timeframe retuning was performed.

## Integrity and limitations

- Raw archive timestamp/mark/funding audit: PASS, 864/864 symbol-months.
- SHA-256 archive audit: PASS, 2,592/2,592 selected files.
- Independent ledger recount: 201,648 rows and 92,723 target-first hits,
  matching the persisted summary.
- The source cohort is exposed and based on currently available symbols; it
  has survivorship risk and is not point-in-time membership.
- Hourly OHLC cannot reveal the within-hour sequence when both barriers touch;
  the test applies conservative stop-first ordering.
- Cost proxies omit measured spread, slippage, and account-specific fees.
- This development history cannot qualify as untouched OOS or support live
  trading. Phase 9 portfolio construction remains blocked because no Core has
  passed validation.

## Reproduction and artifacts

Preregistration: `docs/research/inventory/PREREG_LEAD_LAG_1H_M2_ROUNDK_20261120.md`.
Run summary and event ledger are in this directory. The original first attempt
is preserved separately and marked invalid for canonical per-symbol coverage
reporting in `../lead_lag_1h_m2_round_k_20261120/attempt_status.json`.

```sh
/opt/anaconda3/bin/python3 -m pytest -q tests/test_lead_lag_1h_m2_probe.py
/opt/anaconda3/bin/python3 scripts/research/lead_lag_1h_m2_probe.py \
  --archive-root /private/tmp/cointrade-50_50-data \
  --audit-json /private/tmp/cointrade-50_50-data/audit.json \
  --coverage-json docs/research/inventory/usdm_archive_coverage_20261120.json \
  --output-dir docs/research/inventory/runs/lead_lag_1h_m2_round_k_20261120_v2
```
