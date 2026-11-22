# Backtest report

Results directory: `results_quick/`. Data mode: synthetic candles (quick smoke run).

## Headline: strict all-three-on long, short, combined

- long: train trades=50, train return sum=1.681%, mean train drawdown=-0.745%; test trades=29, test return sum=2.250%, mean test drawdown=-0.422%.
- short: train trades=66, train return sum=-4.216%, mean train drawdown=-2.777%; test trades=42, test return sum=-1.537%, mean test drawdown=-1.135%.
- combined: train trades=102, train return sum=-3.246%, mean train drawdown=-2.519%; test trades=62, test return sum=0.281%, mean test drawdown=-0.933%.

### Per-symbol winner results (train and test)

                            train_trades  train_total_return  test_trades  test_total_return
symbol  timeframe side                                                                      
SYNTH_A 1h        combined            52           -1.028837         31.0           0.211507
                  long                29            0.482260         15.0           1.497067
                  short               29           -0.890829         22.0          -1.417872
SYNTH_B 1h        combined            50           -2.217117         31.0           0.069712
                  long                21            1.199190         14.0           0.753013
                  short               37           -3.324912         20.0          -0.119119

## Stage A full signal grid

### long eligible rank (train only)

 signal_config  train_events  mean_10  median_10   win_10  mean_20  median_20    win_20
         68237           197 0.275639  -0.064243 48.22335  0.49901  -0.283932 55.837563

### short eligible rank (train only)

 signal_config  train_events   mean_10  median_10   win_10   mean_20  median_20    win_20
         68237           235 -0.282683  -0.423222 42.12766 -0.282103  -0.401486 43.829787

The deterministic grid keeps all three conditions required. Forward return direction is positive for long and negative price return for short. Eligibility is applied before ranking. Pooled means and win rates are event weighted; pooled median is approximated by an event weighted median of the per-series medians because event-level return arrays are not stored.

Eligibility floor: at least 150 pooled training events per direction and at least 30 per timeframe; 2 side/configuration candidates pass out of 221184 recorded candidates.
Event-count distribution (pooled train events):
train_events
0          221111
1-29           54
30-149         17
150-299         2
300+            0

## 2^3 condition ablation: events and forward simulation

Train and test are kept in separate rows; these are post-selection diagnostics for the selected parameters.

                    events  trades  total_return
bb stoch stc split                              
0  0     0   test     2000     131      1.224008
             train    3000     203      1.211132
         1   test     1675     129      4.043141
             train    2690     193     -3.230719
   1     0   test     1087     125      0.989007
             train    1576     163     -4.892327
         1   test      522      77     -0.182577
             train     814     130     -3.761330
1  0     0   test     1386     127     -0.328304
             train    1999     177      3.477523
         1   test      500      83      0.057001
             train     737     118     -2.576791
   1     0   test      753     108      0.713079
             train    1049     149     -1.199976
         1   test      311      62      0.281220
             train     431     102     -3.245953

## Selected winner: train selection and plateau

Eligible common parameter sets: 5 of 6; eligibility requires at least 30 pooled train trades across symbols/timeframes.
Selected train-only winner: signal_config=68237, params=`{"add_size_mult": 1, "add_spacing_pct": 3, "atr_mult": 2.0, "bb_mid_exit": false, "max_hold_bars": 48, "n_adds": 0, "opp_exit": false, "sl_pct": null, "stop_mode": "atr2", "tp_pct": 3}`, robust_score=-5.5809. It passed the pooled 30-trade Stage B floor; test metrics below use these fixed parameters and were not used for selection.
unconstrained: FRAGILE (0.0% axial neighbors score at least 50% of winner).
with_stop: FRAGILE (10.5% axial neighbors score at least 50% of winner).

## Rolling walk-forward

    side  windows  windows_selected  test_trades  test_return_sum  test_return_mean  windows_positive_pct  test_max_dd_mean
    long        0                 0            0                0                 0                     0                 0
   short        0                 0            0                0                 0                     0                 0
combined        0                 0            0                0                 0                     0                 0

## Winner comparison

| winner | signal_config | signal_knobs | management | train_trades | train_return | test_trades | test_return | test_vs_train_degradation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| unconstrained | 68237 | {"bb_depth_pct": 0, "bb_use": "low", "bb_window": 8, "stc_lag": 2, "stc_level": 40, "stc_lookback": 20, "stc_turn_type": 1, "stoch_cross_lag": 8, "stoch_level": 25, "stoch_min_cross_age": 3} | {"add_size_mult": 1, "add_spacing_pct": 3, "atr_mult": 2.0, "bb_mid_exit": false, "max_hold_bars": 48, "n_adds": 0, "opp_exit": false, "sl_pct": null, "stop_mode": "atr2", "tp_pct": 3} | 102 | -3.2459533400850447 | 62 | 0.2812195565606136 | 3.5271728966456584 |
| with_stop | 68237 | {"bb_depth_pct": 0, "bb_use": "low", "bb_window": 8, "stc_lag": 2, "stc_level": 40, "stc_lookback": 20, "stc_turn_type": 1, "stoch_cross_lag": 8, "stoch_level": 25, "stoch_min_cross_age": 3} | {"add_size_mult": 1, "add_spacing_pct": 0, "atr_mult": 2.0, "bb_mid_exit": false, "max_hold_bars": 48, "n_adds": 0, "opp_exit": false, "sl_pct": null, "stop_mode": "atr2", "tp_pct": 2} | 123 | -0.9316455236679335 | 71 | 0.45701867019474 | 1.3886641938626736 |
| long_only | 68237 | {"bb_depth_pct": 0, "bb_use": "low", "bb_window": 8, "stc_lag": 2, "stc_level": 40, "stc_lookback": 20, "stc_turn_type": 1, "stoch_cross_lag": 8, "stoch_level": 25, "stoch_min_cross_age": 3} | {"add_size_mult": 1, "add_spacing_pct": 3, "atr_mult": 2.0, "bb_mid_exit": false, "max_hold_bars": null, "n_adds": 0, "opp_exit": false, "sl_pct": null, "stop_mode": "atr2", "tp_pct": 3} | 50 | 2.0042118934676485 | 27 | 2.525059315842485 | 0.5208474223748367 |
| short_only | 68237 | {"bb_depth_pct": 0, "bb_use": "low", "bb_window": 8, "stc_lag": 2, "stc_level": 40, "stc_lookback": 20, "stc_turn_type": 1, "stoch_cross_lag": 8, "stoch_level": 25, "stoch_min_cross_age": 3} | {"add_size_mult": 1, "add_spacing_pct": 3, "atr_mult": 2.0, "bb_mid_exit": false, "max_hold_bars": 48, "n_adds": 0, "opp_exit": false, "sl_pct": null, "stop_mode": "atr2", "tp_pct": 3} | 66 | -4.2157411219687235 | 42 | -1.5369909067913823 | 2.6787502151773412 |
| hybrid_side_signals | -1 | {"long": {"bb_depth_pct": 0, "bb_use": "low", "bb_window": 8, "stc_lag": 2, "stc_level": 40, "stc_lookback": 20, "stc_turn_type": 1, "stoch_cross_lag": 8, "stoch_level": 25, "stoch_min_cross_age": 3}, "short": {"bb_depth_pct": 0, "bb_use": "low", "bb_window": 8, "stc_lag": 2, "stc_level": 40, "stc_lookback": 20, "stc_turn_type": 1, "stoch_cross_lag": 8, "stoch_level": 25, "stoch_min_cross_age": 3}} | {"add_size_mult": 1, "add_spacing_pct": 3, "atr_mult": 2.0, "bb_mid_exit": false, "max_hold_bars": 48, "n_adds": 0, "opp_exit": false, "sl_pct": null, "stop_mode": "atr2", "tp_pct": 3} | 102 | -3.2459533400850447 | 62 | 0.2812195565606136 | 3.5271728966456584 |

## Verdict

Unconstrained selected return changed from -3.246% train to 0.281% untouched test (+3.527 percentage points); the with-stop test return was 0.457%. Treat all selected candidates as FRAGILE under the available neighbor checks.
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
| data | 0.001 |
| B | 0.964 |
| signal_counts | 0.020 |
| wf | 0.007 |
| report | 0.043 |

## Signal counts

| Symbol | Timeframe | Split | All 3 on | Long | Short |
|---|---|---|---:|---:|---:|
| SYNTH_A | 1h | train | 209 | 121 | 88 |
| SYNTH_A | 1h | test | 166 | 67 | 99 |
| SYNTH_B | 1h | train | 222 | 76 | 147 |
| SYNTH_B | 1h | test | 145 | 59 | 87 |
