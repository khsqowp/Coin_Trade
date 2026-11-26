# RANKED TOP 10 - EXPLORATORY SCREEN ONLY

Ranking formula: excess total return over SPY buy-and-hold on each idea's matching date window; ties favor smaller drawdown (less negative MDD). This is a descriptive screen, not an inferential score.

| rank | idea_id | name | excess vs SPY | total return | MDD | switches/year |
|---:|---|---|---:|---:|---:|---:|
| 1 | D001 | SCHD_vs_QQQ_126d | 173.46% | 865.91% | -37.03% | 7.42 |
| 2 | D005 | VYM_rate_gate | -256.03% | 417.76% | -62.27% | 7.60 |
| 3 | D004 | SCHD_rate_gate | -265.89% | 426.56% | -33.52% | 9.89 |
| 4 | D002 | VYM_vs_SPY_126d | -275.21% | 398.58% | -63.35% | 10.16 |
| 5 | D003 | DVY_vs_SPY_252d | -284.88% | 695.85% | -57.11% | 7.02 |
| 6 | D008 | Sell_May | -767.80% | 421.66% | -34.09% | 2.10 |
| 7 | D012 | Anti200DMA_10pct | -1047.81% | 141.64% | -40.76% | 2.44 |
| 8 | D009 | Dip10_5pct_hold5 | -1107.57% | 81.89% | -30.03% | 4.46 |
| 9 | D010 | Dip10_7pct_hold10 | -1109.24% | 80.21% | -30.69% | 2.27 |
| 10 | D011 | Dip20_8pct_hold10 | -1127.59% | 61.86% | -40.35% | 2.02 |

## Why-notes

1. **SCHD_vs_QQQ_126d**: screened for its stated relative mechanism; observed ranking is based only on train-window excess return and drawdown.
2. **VYM_rate_gate**: screened for its stated rate mechanism; observed ranking is based only on train-window excess return and drawdown.
3. **SCHD_rate_gate**: screened for its stated rate mechanism; observed ranking is based only on train-window excess return and drawdown.
4. **VYM_vs_SPY_126d**: screened for its stated relative mechanism; observed ranking is based only on train-window excess return and drawdown.
5. **DVY_vs_SPY_252d**: screened for its stated relative mechanism; observed ranking is based only on train-window excess return and drawdown.
6. **Sell_May**: screened for its stated may mechanism; observed ranking is based only on train-window excess return and drawdown.
7. **Anti200DMA_10pct**: screened for its stated ma mechanism; observed ranking is based only on train-window excess return and drawdown.
8. **Dip10_5pct_hold5**: screened for its stated dip mechanism; observed ranking is based only on train-window excess return and drawdown.
9. **Dip10_7pct_hold10**: screened for its stated dip mechanism; observed ranking is based only on train-window excess return and drawdown.
10. **Dip20_8pct_hold10**: screened for its stated dip mechanism; observed ranking is based only on train-window excess return and drawdown.

## Caveats

- EXPLORATORY SCREEN ONLY; no preregistration, no multiple-testing correction, and no promotion without separate formal preregistration and full validation.
- All parquet queries filter strictly to dates before 2026-06-01; no test rows are read. Results are train-only and selected from 14 variants.
- Daily adjusted-open sequential portfolio approximation; 6 bp one-way turnover cost, charged on initial entry, allocation changes by L1 turnover, and final exit. A direct switch between fully invested ETFs incurs 12 bp.
- Each rotation starts on the first common listed session; no missing history is backfilled or interpolated. SPY buy-and-hold comparison uses the same date window and entry/exit cost.
- Synthetic causality self-test checks that future OHLC-derived values zeroed from a cutoff do not alter earlier 20-session momentum values. Every actual rebalance asserts signal_date < execution_date.
- No walk-forward selection, random-entry null, multiplicity correction, cost stress, or prospective paper test was performed.
