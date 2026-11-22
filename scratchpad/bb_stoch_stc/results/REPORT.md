# Backtest report

Results directory: `results/`. Data mode: real parquet candles.

## Headline: strict all-three-on long, short, combined

- long: train trades=165, train return sum=0.061%, mean train drawdown=-7.721%; test trades=127, test return sum=-10.417%, mean test drawdown=-4.999%.
- short: train trades=164, train return sum=27.101%, mean train drawdown=-5.464%; test trades=119, test return sum=12.721%, mean test drawdown=-4.403%.
- combined: train trades=325, train return sum=27.955%, mean train drawdown=-9.199%; test trades=242, test return sum=3.182%, mean test drawdown=-7.313%.

### Per-symbol winner results (train and test)

                             train_trades  train_total_return  test_trades  test_total_return
symbol   timeframe side                                                                      
BTCUSDT  1h        combined            41            0.463268         32.0           2.865817
                   long                19            1.557801         15.0           0.927343
                   short               23           -1.409487         17.0           1.938474
         4h        combined            14            4.329045         12.0           1.854221
                   long                 5            3.387514          4.0          -1.254762
                   short                9            0.941532          8.0           3.108983
DOGEUSDT 1h        combined            33           -6.411014         40.0          -5.830704
                   long                14           -4.257524         26.0          -7.362411
                   short               19           -2.153490         14.0           1.531707
         4h        combined            12           -5.546417          9.0           0.078311
                   long                10            0.842444          6.0           3.311763
                   short                3           -5.797408          3.0          -3.233452
ETHUSDT  1h        combined            43           12.004619         29.0          -6.654602
                   long                23           10.580939         14.0          -4.803447
                   short               21            1.292327         16.0          -1.360856
         4h        combined            24            0.203584          7.0           3.494389
                   long                12            1.505651          0.0           0.000000
                   short               13           -2.239832          7.0           3.494389
SOLUSDT  1h        combined            48           13.073942         26.0          10.870120
                   long                24           -1.171971         15.0           3.744782
                   short               24           14.245913         12.0           7.231255
         4h        combined             9            2.603677          8.0           3.333527
                   long                 6           -1.809016          3.0           0.958540
                   short                3            4.412693          5.0           2.374987
TRXUSDT  1h        combined            44           -3.805127         28.0          -1.645207
                   long                25           -5.393949         17.0          -3.449432
                   short               19            1.588823         11.0           1.804224
         4h        combined            11           10.920464          7.0           0.881467
                   long                 5            2.860121          4.0           1.580669
                   short                6            8.060344          3.0          -0.699203
XRPUSDT  1h        combined            39            2.901414         34.0          10.026213
                   long                18           -3.052040         19.0           2.725532
                   short               21            5.953454         17.0           5.826138
         4h        combined             7           -2.782388         10.0         -16.091439
                   long                 4           -4.988734          4.0          -6.795447
                   short                3            2.206347          6.0          -9.295992

## Stage A full signal grid

### long eligible rank (train only)

 signal_config  train_events  mean_10  median_10    win_10  mean_20  median_20    win_20
         21800           166 0.635989   0.542652 59.036145 1.944174   1.790016 66.867470
         21725           155 0.489869   0.452607 59.354839 1.864599   1.790016 67.096774
         21723           153 0.470320   0.452607 58.823529 1.829887   1.790016 66.666667
         21724           154 0.468199   0.452607 59.090909 1.821211   1.790016 66.883117
         21752           162 0.474943   0.542652 58.024691 1.711381   1.790016 66.049383
         21776           162 0.474943   0.542652 58.024691 1.711381   1.790016 66.049383
         21796           150 0.442178   0.416945 59.333333 1.779384   1.790016 67.333333
         21797           150 0.442178   0.416945 59.333333 1.779384   1.790016 67.333333
         21798           160 0.438097   0.416945 58.125000 1.747362   1.790016 66.875000
         21799           161 0.431094   0.416945 57.763975 1.732394   1.790016 66.459627

### short eligible rank (train only)

 signal_config  train_events  mean_10  median_10    win_10  mean_20  median_20    win_20
         53948           303 0.125604   0.312587 55.445545 0.384349   0.799216 60.396040
         53892           261 0.052716   0.298005 53.639847 0.478864   0.799216 60.153257
         53893           261 0.052716   0.298005 53.639847 0.478864   0.799216 60.153257
         53916           261 0.052716   0.298005 53.639847 0.478864   0.799216 60.153257
         53917           261 0.052716   0.298005 53.639847 0.478864   0.799216 60.153257
         53964           261 0.052716   0.298005 53.639847 0.478864   0.799216 60.153257
         53965           261 0.052716   0.298005 53.639847 0.478864   0.799216 60.153257
         53988           261 0.052716   0.298005 53.639847 0.478864   0.799216 60.153257
         53989           261 0.052716   0.298005 53.639847 0.478864   0.799216 60.153257
         53870           263 0.056284   0.266573 53.992395 0.484681   0.799216 60.836502

The deterministic grid keeps all three conditions required. Forward return direction is positive for long and negative price return for short. Eligibility is applied before ranking. Pooled means and win rates are event weighted; pooled median is approximated by an event weighted median of the per-series medians because event-level return arrays are not stored.

Eligibility floor: at least 150 pooled training events per direction and at least 30 per timeframe; 129309 side/configuration candidates pass out of 221184 recorded candidates.
Event-count distribution (pooled train events):
train_events
0            5722
1-29        39651
30-149      44105
150-299     26500
300+       105206

## 2^3 condition ablation: events and forward simulation

Train and test are kept in separate rows; these are post-selection diagnostics for the selected parameters.

                    events  trades  total_return
bb stoch stc split                              
0  0     0   test   128382    3368   -348.769310
             train  192552    5716    247.475668
         1   test    84664    3204     62.668020
             train  124904    4975   -476.802493
   1     0   test    48749    2905   -201.001582
             train   64019    4399   -536.253863
         1   test     5296    1535    -73.253481
             train    6862    2084   -282.802376
1  0     0   test    20175    1707   -136.875334
             train   32577    2853   -335.190697
         1   test     1959     629    -21.259412
             train    2824     923    -18.843261
   1     0   test     9279    1357   -116.911486
             train   13781    2077   -283.397266
         1   test      426     242      3.182111
             train     552     325     27.955067

## Selected winner: train selection and plateau

Eligible common parameter sets: 4896 of 5440; eligibility requires at least 30 pooled train trades across symbols/timeframes.
Selected train-only winner: signal_config=53870, params=`{"add_size_mult": 1.5, "add_spacing_pct": 2, "atr_mult": null, "bb_mid_exit": false, "max_hold_bars": 48, "n_adds": 2, "opp_exit": false, "sl_pct": null, "stop_mode": "off", "tp_pct": 5}`, robust_score=19.9023. It passed the pooled 30-trade Stage B floor; test metrics below use these fixed parameters and were not used for selection.
unconstrained: FRAGILE (42.9% axial neighbors score at least 50% of winner).
with_stop: FRAGILE (36.4% axial neighbors score at least 50% of winner).

## Rolling walk-forward

    side  windows  windows_selected  test_trades  test_return_sum  test_return_mean  windows_positive_pct  test_max_dd_mean
    long      180               180         1516       -12.273296         -0.068185             46.111111         -1.357301
   short      180               180         1886       -25.634918         -0.142416             42.222222         -1.357301
combined      180               180         3402       -32.250179         -0.179168             43.888889         -1.357301

## Winner comparison

| winner | signal_config | signal_knobs | management | train_trades | train_return | test_trades | test_return | test_vs_train_degradation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| unconstrained | 53870 | {"bb_depth_pct": 20, "bb_use": "close", "bb_window": 8, "stc_lag": 0, "stc_level": 10, "stc_lookback": 20, "stc_turn_type": 2, "stoch_cross_lag": 4, "stoch_level": 25, "stoch_min_cross_age": 0} | {"add_size_mult": 1.5, "add_spacing_pct": 2, "atr_mult": null, "bb_mid_exit": false, "max_hold_bars": 48, "n_adds": 2, "opp_exit": false, "sl_pct": null, "stop_mode": "off", "tp_pct": 5} | 325 | 27.955067446521863 | 242 | 3.182110684965052 | -24.77295676155681 |
| with_stop | 53948 | {"bb_depth_pct": 20, "bb_use": "close", "bb_window": 8, "stc_lag": 4, "stc_level": 10, "stc_lookback": 20, "stc_turn_type": 2, "stoch_cross_lag": 4, "stoch_level": 25, "stoch_min_cross_age": 1} | {"add_size_mult": 1, "add_spacing_pct": 0, "atr_mult": null, "bb_mid_exit": false, "max_hold_bars": null, "n_adds": 2, "opp_exit": false, "sl_pct": 8.0, "stop_mode": "pct8", "tp_pct": 5} | 327 | 53.24085220800051 | 232 | -63.111514992843006 | -116.35236720084352 |
| long_only | 53948 | {"bb_depth_pct": 20, "bb_use": "close", "bb_window": 8, "stc_lag": 4, "stc_level": 10, "stc_lookback": 20, "stc_turn_type": 2, "stoch_cross_lag": 4, "stoch_level": 25, "stoch_min_cross_age": 1} | {"add_size_mult": 1.5, "add_spacing_pct": 2, "atr_mult": null, "bb_mid_exit": false, "max_hold_bars": null, "n_adds": 2, "opp_exit": false, "sl_pct": null, "stop_mode": "off", "tp_pct": 5} | 100 | 140.78899150000026 | 74 | -21.141521185832502 | -161.93051268583275 |
| short_only | 53948 | {"bb_depth_pct": 20, "bb_use": "close", "bb_window": 8, "stc_lag": 4, "stc_level": 10, "stc_lookback": 20, "stc_turn_type": 2, "stoch_cross_lag": 4, "stoch_level": 25, "stoch_min_cross_age": 1} | {"add_size_mult": 1.5, "add_spacing_pct": 2, "atr_mult": null, "bb_mid_exit": false, "max_hold_bars": 48, "n_adds": 2, "opp_exit": false, "sl_pct": 7.0, "stop_mode": "pct7", "tp_pct": 5} | 181 | 29.81028469885687 | 133 | -1.6262581690886293 | -31.436542867945498 |
| hybrid_side_signals | -1 | {"long": {"bb_depth_pct": 20, "bb_use": "close", "bb_window": 8, "stc_lag": 4, "stc_level": 10, "stc_lookback": 20, "stc_turn_type": 2, "stoch_cross_lag": 4, "stoch_level": 25, "stoch_min_cross_age": 1}, "short": {"bb_depth_pct": 20, "bb_use": "close", "bb_window": 8, "stc_lag": 4, "stc_level": 10, "stc_lookback": 20, "stc_turn_type": 2, "stoch_cross_lag": 4, "stoch_level": 25, "stoch_min_cross_age": 1}} | {"add_size_mult": 1.5, "add_spacing_pct": 2, "atr_mult": null, "bb_mid_exit": false, "max_hold_bars": 48, "n_adds": 2, "opp_exit": false, "sl_pct": null, "stop_mode": "off", "tp_pct": 5} | 357 | 4.589747292738586 | 267 | -4.43568274509553 | -9.025430037834116 |

## Verdict

Unconstrained selected return changed from 27.955% train to 3.182% untouched test (-24.773 percentage points); the with-stop test return was -63.112%. Treat all selected candidates as FRAGILE under the available neighbor checks.
Walk-forward selection repeats within each train window. Aggregate returns do not model shared capital, funding, borrowing, or portfolio exposure.

## Reproduce

```sh
.venv/bin/python run_all.py --stage all
.venv/bin/python run_all.py --stage all --quick
.venv/bin/python -m pytest
```

## Stage timings

| Stage | Seconds |
|---|---:|
| data | 0.002 |
| B | 249.953 |
| signal_counts | 1.105 |
| wf | 10.307 |
| report | 0.681 |

## Signal counts

| Symbol | Timeframe | Split | All 3 on | Long | Short |
|---|---|---|---:|---:|---:|
| BTCUSDT | 1h | train | 71 | 35 | 36 |
| BTCUSDT | 1h | test | 65 | 21 | 44 |
| BTCUSDT | 4h | train | 23 | 9 | 14 |
| BTCUSDT | 4h | test | 21 | 7 | 14 |
| ETHUSDT | 1h | train | 82 | 42 | 40 |
| ETHUSDT | 1h | test | 51 | 20 | 31 |
| ETHUSDT | 4h | train | 39 | 20 | 19 |
| ETHUSDT | 4h | test | 12 | 0 | 12 |
| SOLUSDT | 1h | train | 74 | 40 | 34 |
| SOLUSDT | 1h | test | 44 | 21 | 23 |
| SOLUSDT | 4h | train | 26 | 21 | 5 |
| SOLUSDT | 4h | test | 16 | 6 | 10 |
| XRPUSDT | 1h | train | 57 | 28 | 29 |
| XRPUSDT | 1h | test | 61 | 28 | 33 |
| XRPUSDT | 4h | train | 13 | 8 | 5 |
| XRPUSDT | 4h | test | 18 | 10 | 8 |
| TRXUSDT | 1h | train | 78 | 42 | 36 |
| TRXUSDT | 1h | test | 46 | 30 | 16 |
| TRXUSDT | 4h | train | 14 | 8 | 6 |
| TRXUSDT | 4h | test | 9 | 5 | 4 |
| DOGEUSDT | 1h | train | 57 | 23 | 34 |
| DOGEUSDT | 1h | test | 71 | 44 | 27 |
| DOGEUSDT | 4h | train | 18 | 13 | 5 |
| DOGEUSDT | 4h | test | 12 | 8 | 4 |
