# EXPLORATORY SCREEN ONLY -- not part of the 13-round preregistered G-gate track, not added to TRAIN_TRIALS.csv, no promotion without separate formal preregistration + synthetic tests + resource-gated TRAIN run.

# EXPLORE1000 Lane G (multi-timeframe alignment / divergence) -- TOP 20

EXPLORATORY SCREEN ONLY. No multiple-testing correction, no walk-forward, no full lookahead audit. Not G-eligible. Nothing here is a validated candidate.

Data: TRAIN window only (data_access.iter_train_bars), 15m / 1h / 4h bars; 1d derived from complete 4h bars. Signals use close-time-available higher-tf bars; entry at next trigger-bar open; 12bp round trip; one position per symbol.

Scored: 248 of 260 proposed. Insufficient (<30 trades): 0. Data-blocked (5m bars absent): 12.

composite_score = EV * ln(1+n) * min(1,n/30) * min(1,PF); same formula as EXPLORE500 lane A, but exit rules differ, so cross-lane comparison is not valid.

## Top 20

### 1. G123 -- Multi-tf RSI alignment + 1h RSI cross [combo=1h+4h+1d, thr=55, H=48, k=0]

- composite_score: 735.8; n_trades: 3272, win_rate: 0.5189, PF: 1.3609, EV_bps: 90.9134, rough_sharpe: 0.0979
- halves EV: 124.0699 / 57.7163; symbols traded: 26, share of symbols with positive EV: 0.885; causal_check: True
- side split (same signal, pooled): long-only n=1583, EV=145.72 bps, PF=1.597; short-only n=1689, EV=39.54 bps, PF=1.152
- rationale: Higher-tf RSI above threshold (all tfs) and 1h RSI crossing back through 45 (55 for shorts).

### 2. G113 -- Multi-tf RSI alignment + 1h RSI cross [combo=1h+4h, thr=55, H=48, k=0]

- composite_score: 604.3; n_trades: 4518, win_rate: 0.5215, PF: 1.2808, EV_bps: 71.7997, rough_sharpe: 0.0795
- halves EV: 101.3392 / 42.2078; symbols traded: 26, share of symbols with positive EV: 0.885; causal_check: True
- side split (same signal, pooled): long-only n=2279, EV=114.5 bps, PF=1.468; short-only n=2269, EV=27.12 bps, PF=1.102
- rationale: Higher-tf RSI above threshold (all tfs) and 1h RSI crossing back through 45 (55 for shorts).

### 3. G118 -- Multi-tf RSI alignment + 1h RSI cross [combo=1h+4h+1d, thr=50, H=48, k=0]

- composite_score: 473.4; n_trades: 6517, win_rate: 0.5067, PF: 1.2118, EV_bps: 53.9057, rough_sharpe: 0.0615
- halves EV: 81.2843 / 26.4514; symbols traded: 26, share of symbols with positive EV: 0.885; causal_check: True
- side split (same signal, pooled): long-only n=3045, EV=105.07 bps, PF=1.414; short-only n=3554, EV=10.02 bps, PF=1.039
- rationale: Higher-tf RSI above threshold (all tfs) and 1h RSI crossing back through 45 (55 for shorts).

### 4. G124 -- Multi-tf RSI alignment + 1h RSI cross [combo=1h+4h+1d, thr=55, H=48, k=2.5]

- composite_score: 446.4; n_trades: 3487, win_rate: 0.3983, PF: 1.2348, EV_bps: 54.7302, rough_sharpe: 0.0679
- halves EV: 85.0494 / 24.3936; symbols traded: 26, share of symbols with positive EV: 0.846; causal_check: True
- side split (same signal, pooled): long-only n=1683, EV=76.1 bps, PF=1.303; short-only n=1804, EV=34.79 bps, PF=1.161
- rationale: Higher-tf RSI above threshold (all tfs) and 1h RSI crossing back through 45 (55 for shorts).

### 5. G112 -- Multi-tf RSI alignment + 1h RSI cross [combo=1h+4h, thr=55, H=24, k=0]

- composite_score: 436.1; n_trades: 5408, win_rate: 0.5118, PF: 1.2918, EV_bps: 50.7328, rough_sharpe: 0.0838
- halves EV: 72.185 / 29.2806; symbols traded: 26, share of symbols with positive EV: 0.923; causal_check: True
- side split (same signal, pooled): long-only n=2728, EV=71.85 bps, PF=1.423; short-only n=2686, EV=29.63 bps, PF=1.166
- rationale: Higher-tf RSI above threshold (all tfs) and 1h RSI crossing back through 45 (55 for shorts).

### 6. G114 -- Multi-tf RSI alignment + 1h RSI cross [combo=1h+4h, thr=55, H=48, k=2.5]

- composite_score: 402.1; n_trades: 4811, win_rate: 0.3964, PF: 1.2084, EV_bps: 47.4184, rough_sharpe: 0.0618
- halves EV: 68.7883 / 26.004; symbols traded: 26, share of symbols with positive EV: 0.885; causal_check: True
- side split (same signal, pooled): long-only n=2402, EV=62.27 bps, PF=1.257; short-only n=2409, EV=32.61 bps, PF=1.153
- rationale: Higher-tf RSI above threshold (all tfs) and 1h RSI crossing back through 45 (55 for shorts).

### 7. G108 -- Multi-tf RSI alignment + 1h RSI cross [combo=1h+4h, thr=50, H=48, k=0]

- composite_score: 384.1; n_trades: 8115, win_rate: 0.5035, PF: 1.1646, EV_bps: 42.6706, rough_sharpe: 0.0494
- halves EV: 52.0093 / 33.3296; symbols traded: 26, share of symbols with positive EV: 0.731; causal_check: True
- side split (same signal, pooled): long-only n=4206, EV=85.19 bps, PF=1.342; short-only n=4407, EV=-1.41 bps, PF=0.995
- rationale: Higher-tf RSI above threshold (all tfs) and 1h RSI crossing back through 45 (55 for shorts).

### 8. G223 -- Price extreme vs HTF RSI non-confirmation (divergence) [N=24, delta=8, htf=1d, H=24, k=2.5]

- composite_score: 362.4; n_trades: 1202, win_rate: 0.5324, PF: 1.2786, EV_bps: 51.0983, rough_sharpe: 0.0884
- halves EV: 91.4826 / 10.5794; symbols traded: 26, share of symbols with positive EV: 0.769; causal_check: True
- side split (same signal, pooled): long-only n=501, EV=69.64 bps, PF=1.392; short-only n=724, EV=38.02 bps, PF=1.204
- rationale: 1h close at an N-bar extreme while higher-tf RSI sits well inside its own N-bar range: divergence fade.

### 9. G119 -- Multi-tf RSI alignment + 1h RSI cross [combo=1h+4h+1d, thr=50, H=48, k=2.5]

- composite_score: 350.3; n_trades: 7505, win_rate: 0.3832, PF: 1.1771, EV_bps: 39.2596, rough_sharpe: 0.0528
- halves EV: 63.6624 / 14.8504; symbols traded: 26, share of symbols with positive EV: 0.885; causal_check: True
- side split (same signal, pooled): long-only n=3456, EV=67.01 bps, PF=1.278; short-only n=4057, EV=16.38 bps, PF=1.08
- rationale: Higher-tf RSI above threshold (all tfs) and 1h RSI crossing back through 45 (55 for shorts).

### 10. G109 -- Multi-tf RSI alignment + 1h RSI cross [combo=1h+4h, thr=50, H=48, k=2.5]

- composite_score: 310.0; n_trades: 9516, win_rate: 0.3838, PF: 1.1537, EV_bps: 33.8368, rough_sharpe: 0.0469
- halves EV: 41.1479 / 26.5194; symbols traded: 26, share of symbols with positive EV: 0.846; causal_check: True
- side split (same signal, pooled): long-only n=4703, EV=53.37 bps, PF=1.23; short-only n=5001, EV=13.24 bps, PF=1.064
- rationale: Higher-tf RSI above threshold (all tfs) and 1h RSI crossing back through 45 (55 for shorts).

### 11. G102 -- HTF prior-N high/low zone test + reclaim [lev=1d, N=40, band=0.002, H=24, k=0] [halves disagree]

- composite_score: 303.9; n_trades: 515, win_rate: 0.5301, PF: 1.1957, EV_bps: 48.6497, rough_sharpe: 0.0581
- halves EV: 118.5148 / -21.4873; symbols traded: 26, share of symbols with positive EV: 0.538; causal_check: True
- side split (same signal, pooled): long-only n=187, EV=279.48 bps, PF=2.298; short-only n=328, EV=-82.95 bps, PF=0.69
- rationale: Higher-tf prior-N low (support) in an uptrend tested by 1h lows and reclaimed; mirror at resistance.

### 12. G222 -- Price extreme vs HTF RSI non-confirmation (divergence) [N=24, delta=8, htf=1d, H=12, k=0]

- composite_score: 291.1; n_trades: 1109, win_rate: 0.5573, PF: 1.3453, EV_bps: 41.514, rough_sharpe: 0.096
- halves EV: 59.1429 / 23.7895; symbols traded: 26, share of symbols with positive EV: 0.731; causal_check: True
- side split (same signal, pooled): long-only n=454, EV=80.54 bps, PF=1.754; short-only n=657, EV=13.69 bps, PF=1.105
- rationale: 1h close at an N-bar extreme while higher-tf RSI sits well inside its own N-bar range: divergence fade.

### 13. G122 -- Multi-tf RSI alignment + 1h RSI cross [combo=1h+4h+1d, thr=55, H=24, k=2.5]

- composite_score: 274.9; n_trades: 4097, win_rate: 0.4511, PF: 1.1817, EV_bps: 33.0465, rough_sharpe: 0.0573
- halves EV: 45.1662 / 20.9209; symbols traded: 26, share of symbols with positive EV: 0.808; causal_check: True
- side split (same signal, pooled): long-only n=1994, EV=38.91 bps, PF=1.2; short-only n=2103, EV=27.48 bps, PF=1.161
- rationale: Higher-tf RSI above threshold (all tfs) and 1h RSI crossing back through 45 (55 for shorts).

### 14. G051 -- Multi-tf momentum alignment (edge trigger) [align=1h+4h, scale=mid, H=48, k=2.5] [halves disagree]

- composite_score: 205.9; n_trades: 10721, win_rate: 0.3874, PF: 1.1062, EV_bps: 22.1839, rough_sharpe: 0.034
- halves EV: 46.2622 / -1.908; symbols traded: 26, share of symbols with positive EV: 0.808; causal_check: True
- side split (same signal, pooled): long-only n=7856, EV=36.99 bps, PF=1.178; short-only n=7807, EV=-10.83 bps, PF=0.95
- rationale: All listed timeframes show same-sign trailing return; enter on the bar the alignment first forms.

### 15. G060 -- Multi-tf momentum alignment (edge trigger) [align=1h+4h+1d, scale=mid, H=48, k=0]

- composite_score: 191.9; n_trades: 8101, win_rate: 0.4993, PF: 1.0841, EV_bps: 21.3196, rough_sharpe: 0.0265
- halves EV: 37.6871 / 4.9481; symbols traded: 26, share of symbols with positive EV: 0.615; causal_check: True
- side split (same signal, pooled): long-only n=5576, EV=35.88 bps, PF=1.148; short-only n=5626, EV=-25.94 bps, PF=0.906
- rationale: All listed timeframes show same-sign trailing return; enter on the bar the alignment first forms.

### 16. G107 -- Multi-tf RSI alignment + 1h RSI cross [combo=1h+4h, thr=50, H=24, k=0]

- composite_score: 177.8; n_trades: 10954, win_rate: 0.4987, PF: 1.1049, EV_bps: 19.1183, rough_sharpe: 0.0333
- halves EV: 28.1941 / 10.0424; symbols traded: 26, share of symbols with positive EV: 0.808; causal_check: True
- side split (same signal, pooled): long-only n=5452, EV=36.82 bps, PF=1.204; short-only n=5722, EV=2.88 bps, PF=1.016
- rationale: Higher-tf RSI above threshold (all tfs) and 1h RSI crossing back through 45 (55 for shorts).

### 17. G101 -- HTF prior-N high/low zone test + reclaim [lev=1d, N=40, band=0.002, H=12, k=0] [halves disagree]

- composite_score: 157.0; n_trades: 647, win_rate: 0.5394, PF: 1.1454, EV_bps: 24.2582, rough_sharpe: 0.0457
- halves EV: 53.1408 / -4.7138; symbols traded: 26, share of symbols with positive EV: 0.615; causal_check: True
- side split (same signal, pooled): long-only n=219, EV=106.46 bps, PF=1.644; short-only n=428, EV=-17.8 bps, PF=0.894
- rationale: Higher-tf prior-N low (support) in an uptrend tested by 1h lows and reclaimed; mirror at resistance.

### 18. G117 -- Multi-tf RSI alignment + 1h RSI cross [combo=1h+4h+1d, thr=50, H=24, k=2.5]

- composite_score: 145.1; n_trades: 9311, win_rate: 0.4374, PF: 1.0902, EV_bps: 15.8716, rough_sharpe: 0.0299
- halves EV: 27.8523 / 3.8883; symbols traded: 26, share of symbols with positive EV: 0.692; causal_check: True
- side split (same signal, pooled): long-only n=4345, EV=27.2 bps, PF=1.144; short-only n=4971, EV=6.09 bps, PF=1.037
- rationale: Higher-tf RSI above threshold (all tfs) and 1h RSI crossing back through 45 (55 for shorts).

### 19. G139 -- MACD histogram sign alignment across tfs (edge) [set=B, macd=12_26, H=16, k=0]

- composite_score: 143.2; n_trades: 12530, win_rate: 0.4652, PF: 1.094, EV_bps: 15.1775, rough_sharpe: 0.0288
- halves EV: 6.9403 / 23.4147; symbols traded: 26, share of symbols with positive EV: 0.692; causal_check: True
- side split (same signal, pooled): long-only n=7036, EV=38.2 bps, PF=1.261; short-only n=5564, EV=-13.91 bps, PF=0.923
- rationale: All tfs in set share MACD-histogram sign; A trades on 15m (15m,1h,4h), B on 1h (1h,4h,1d).

### 20. G145 -- MACD histogram sign alignment across tfs (edge) [set=B, macd=8_21, H=16, k=0]

- composite_score: 136.9; n_trades: 14216, win_rate: 0.4632, PF: 1.0875, EV_bps: 14.3139, rough_sharpe: 0.027
- halves EV: 1.0847 / 27.5432; symbols traded: 26, share of symbols with positive EV: 0.654; causal_check: True
- side split (same signal, pooled): long-only n=7900, EV=31.22 bps, PF=1.205; short-only n=6425, EV=-6.79 bps, PF=0.962
- rationale: All tfs in set share MACD-histogram sign; A trades on 15m (15m,1h,4h), B on 1h (1h,4h,1d).

## Caveats

- Regime dependence: TRAIN spans a predominantly bullish stretch; trend-following HTF filters look better in that regime than they would in chop or bear markets.
- Overfitting: ~250 ideas screened with no multiple-testing correction; expect a sizeable false-positive share among the top ranks. Parameter neighbors were not checked for plateaus.
- Sample size: pooled trades across symbols are highly correlated (BTC/ETH/alts move together), so effective sample is far smaller than n_trades.
- Lookahead: higher-tf bars are used only after their close; features are trailing. A truncation self-check on BTCUSDT (causal_check column) confirms signals on the common prefix are identical after truncation at 70% of the series. This is necessary, not sufficient.
- Execution: next-bar-open entry, ATR-stop gap fills at bar open, close exits, flat 12bp. No funding, no slippage beyond the convention, no capacity model.
- Ideas with composite driven by tiny |EV| and large n can rank high; check halves_agree and pct_symbols_pos_ev before reading anything into them.
- Blocked ideas (F13, 5m) were proposed for completeness and are not screened.

## Engine sanity (null test)

Periodic every-24-bar long and short entries (48-bar hold, no stop, 12bp) on 12 symbols of 1h TRAIN bars gave long EV +29.0 bps and short EV -53.0 bps; their sum is about -24 bps, i.e. the two sides carry exactly one round-trip cost each. This confirms the engine does not add a directional or cost bias.

## Reading the top of the list

- The top ranks are almost entirely the F6 family (1h RSI cross of 45/55 gated by 4h and 1d RSI thresholds, 48-bar hold, no stop). Both long-only and short-only legs are positive in the pooled screen, which is unusual for a single signal and is the main reason to distrust it before any formal work: check it on a regime-split and on the 40% TEST window only after a separate prereg.
- Stops (k=2.5) reduce n-weighted EV versus no stop for most of the F6 family; the no-stop variants are not a robustness argument.
- F11 (1h new extreme vs 1d RSI non-confirmation) and F5 (1d prior-40-bar low reclaim) are the next two clusters; F5 is one-sided (long side carries it in G102).
- Families F2, F8, F9, F10 and F12 are negative across almost all parameter sets; they are reported as screened negatives, not as failed hypotheses.
