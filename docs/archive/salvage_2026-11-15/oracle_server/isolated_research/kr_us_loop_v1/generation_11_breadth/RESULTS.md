# Generation 11 sector breadth A2 — result

Status: **fixed candidate rejected for the preregistered objective**. This is an exploratory result on a previously inspected, Yahoo-derived, non-atomic local snapshot. It is not an untouched OOS result and does not establish whether other profitable strategies exist.

## Frozen rule and execution

- Breadth: count of nine SPDR sector ETFs with adjusted close strictly above their inclusive SMA200.
- SPY exposure: 100% when breadth is at least 5; otherwise cash. Close signal applies at the next observed open.
- Accounting: adjusted-open-to-adjusted-open, 10 bp per unit exposure change, including terminal liquidation; benchmark is matched SPY buy-and-hold with the same costs and dates.
- Snapshot: exact intersection of all ten calendars, 7,008 common sessions, 1998-12-22 through 2026-10-30. The first measured interval is 1999-10-08; 6,807 intervals end 2026-10-30.
- One A2 run only. A1's separate calendar-contract failure remains recorded and has no performance result.

## Result

| Window | Strategy CAGR | Strategy Sharpe | Strategy MDD | Matched SPY CAGR | Matched SPY Sharpe | Matched SPY MDD |
|---|---:|---:|---:|---:|---:|---:|
| Full | 2.98% | 0.304 | -46.64% | 8.57% | 0.531 | -55.42% |
| 2001–2016, previously inspected | 2.39% | 0.266 | -28.03% | 5.41% | 0.368 | -55.42% |
| 2017+, previously inspected | 8.01% | 0.685 | -23.34% | 14.96% | 0.893 | -32.05% |

The strategy reduced the displayed full-sample and later-period drawdowns but failed to exceed matched SPY on either primary measure (CAGR and Sharpe) in all reported windows. It is rejected under the frozen rule; no threshold or indicator variants were tested.

## Activity and verification

- 5-of-9 threshold; SMA window 200.
- 141 entries including initial investment, 140 signal-driven exits, one terminal liquidation; turnover 282 exposure units including entry/terminal exit.
- Mean invested exposure: 77.51%.
- A2 synthetic tests: 8/8 passed, including exact calendar intersection, malformed-index rejection, no fill, pending-GO data-read block, and invalid raw price detection outside the common calendar.
- Independently recomputed cumulative returns and MDD from the saved 6,807-row curve; both matched the run output.
- Preregistration, A1/A2/A3 addenda, runners/tests, and ten relevant input content hashes were checked against the freeze before opening price values. A2 was then run exactly once.

## Artifacts

- `manifest_gen11-breadth-20261106-a2.json`
- `attempts_gen11-breadth-20261106-a2.jsonl`
- `curve_gen11-breadth-20261106-a2.csv.gz`
- `FREEZE_A2.json`

## Interpretation boundary

This is evidence against this exact 5-of-9 SMA200 rule on this local snapshot. It is not evidence that algorithmic trading cannot be profitable, and it is not a corrected-significance claim. Global historical trial multiplicity, authoritative corporate actions, execution-price realism, and a genuinely prospective holdout remain unresolved.
