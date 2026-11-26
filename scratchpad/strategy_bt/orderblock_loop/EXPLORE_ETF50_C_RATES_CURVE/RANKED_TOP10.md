# Lane C (rates/curve regime) — RANKED TOP 10

EXPLORATORY SCREEN ONLY — not part of the 13-round preregistered G-gate track, not added to TRAIN_TRIALS.csv, no promotion without separate formal preregistration + synthetic tests + resource-gated TRAIN run.

Sessions scored: 5998 (2002-07-30..2026-06-01, TRAIN only). SPY buy-hold baseline over same window: total_return=12.0541, mdd=-0.5542, 2018=-0.0530, 2022=-0.1867.

PIT cross-check (DGS10/DGS2/DGS3MO vs official Treasury par curve, this run): {"DGS10": {"max_abs_diff": 0.0, "mismatches_gt_1bp": 0, "overlap_days": 9109}, "DGS2": {"max_abs_diff": 0.0, "mismatches_gt_1bp": 0, "overlap_days": 9109}, "DGS3MO": {"max_abs_diff": 0.0, "mismatches_gt_1bp": 0, "overlap_days": 9106}}

Scored 14/14 ideas (>=3 regime switches); 0 marked insufficient_switches.

## Top 10 by composite_score

| rank | idea_id | name | theme | switches | switches/yr | total_return | excess_vs_spy | mdd | mdd_improvement | 2018 | 2022 | sharpe | score | note |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | RC012 | Fed funds (DFF) 126d hiking trend -> SHY | theme6_ffr_trend | 78 | 3.27 | 7.6009 | -4.4532 | -0.5552 | -0.0010 | 0.0086 | -0.0953 | 0.628 | 0.628 | ok |
| 2 | RC001 | 10y-2y invert -> SHY (binary) | theme1_curve_level_2y10y | 34 | 1.43 | 6.9289 | -5.1251 | -0.5542 | 0.0000 | -0.0530 | -0.1848 | 0.584 | 0.584 | ok |
| 3 | RC003 | 10y-3m invert -> SHY (binary) | theme2_curve_level_10y3m | 68 | 2.85 | 6.4918 | -5.5623 | -0.5542 | 0.0000 | -0.0530 | -0.1833 | 0.578 | 0.578 | ok |
| 4 | RC013 | Fed funds (DFF) 252d hiking trend -> SHY (slower) | theme6_ffr_trend | 52 | 2.18 | 6.1995 | -5.8545 | -0.5542 | 0.0000 | -0.0209 | -0.1420 | 0.573 | 0.573 | ok |
| 5 | RC004 | 10y-3m invert -> TLT (duration) | theme2_curve_level_10y3m | 68 | 2.85 | 5.7328 | -6.3213 | -0.5542 | 0.0000 | -0.0530 | -0.1594 | 0.533 | 0.533 | ok |
| 6 | RC002 | 10y-2y invert -> TLT (duration) | theme1_curve_level_2y10y | 34 | 1.43 | 5.1978 | -6.8563 | -0.5542 | 0.0000 | -0.0530 | -0.3054 | 0.510 | 0.510 | ok |
| 7 | RC008 | 10y-3m un-invert event -> SHY for 120d | theme4_uninvert_event | 6 | 0.25 | 12.5199 | 0.4658 | -0.5402 | 0.0140 | -0.0530 | -0.1867 | 0.708 | 0.317 | ok |
| 8 | RC007 | 10y-2y un-invert (steepening) event -> SHY for 180d | theme4_uninvert_event | 6 | 0.25 | 10.5361 | -1.5180 | -0.5402 | 0.0140 | -0.0530 | -0.1867 | 0.673 | 0.301 | ok |
| 9 | RC005 | 10y-3m sustained invert (20d) -> SHY | theme3_persistence | 8 | 0.34 | 6.4807 | -5.5733 | -0.5542 | 0.0000 | -0.0530 | -0.1466 | 0.565 | 0.292 | ok |
| 10 | RC014 | 10y-3m sustained invert (20d) -> TLT | theme3_persistence | 8 | 0.34 | 5.4171 | -6.6370 | -0.5578 | -0.0036 | -0.0530 | -0.1661 | 0.516 | 0.266 | ok |
