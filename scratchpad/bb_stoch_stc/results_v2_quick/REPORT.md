# V2 research report

Mode: synthetic quick smoke

## Headline results

Configurations were selected on train data only.

### A2 frozen comparison

Unavailable.

### A3 variants

| variant | split | trades | return_pct | median_pf | summed_mdd_pct |
|---|---|---|---|---|---|
| long_only | train | 4 | 2.2785697920000065 | inf | -1.4650095281776712 |
| long_only | test | 1 | -1.6083688817214965 | 0.0 | -2.931943628058743 |
| short_only | train | 6 | 1.1407152960000024 | inf | -1.2259256677101038 |
| short_only | test | 1 | -0.296682184715523 | 0.0 | -1.3350530080087628 |
| unconstrained | train | 9 | 5.1310732320000145 | inf | -3.6327640049873855 |
| unconstrained | test | 2 | -2.4818108199559052 | 0.0 | -6.918822889851853 |
| with_stop | train | 9 | 5.1310732320000145 | inf | -3.6327640049873855 |
| with_stop | test | 3 | -4.480238751999994 | 0.07818665737562153 | -5.391898605247825 |

### Part B variants

| variant | split | trades | return_pct | median_score | median_pf | summed_mdd_pct |
|---|---|---|---|---|---|---|
| long_only | train | 12 | 1.0599075743029798 | 1.1165461626741793 | nan | nan |
| long_only | test | 25 | -0.16605749170151907 | nan | 3.873950974579688 | -2.2312158531952635 |
| short_only | train | 0 | 0.0 | 0.0 | nan | nan |
| short_only | test | 0 | 0.0 | nan | 0.0 | 0.0 |
| winner | train | 2 | 0.22472862908708194 | 0.6332397247922351 | nan | nan |
| winner | test | 3 | 0.14551206025998 | nan | 1.4184446032847913 | -0.20824917950261163 |

## Null percentiles

| variant | repetitions | strategy_test_return | test_trades | null_p50 | null_p90 | percentile | fragile | verdict | gates |
|---|---|---|---|---|---|---|---|---|---|
| A3_unconstrained | 4 | -2.4818108199559052 | 2 | -1.0884040486229285 | -1.0884040486229285 | 0.0 | True | NO EDGE | beats_p90=False; not_fragile=False; at_least_30_trades=False |
| A3_with_stop | 4 | -4.480238751999994 | 3 | -1.4820385120000008 | -1.4820385120000008 | 0.0 | True | NO EDGE | beats_p90=False; not_fragile=False; at_least_30_trades=False |
| part_b | 4 | -0.07921656882710194 | 1 | -0.3101808239999991 | -0.3101808239999991 | 100.0 | False | NO EDGE | beats_p90=True; not_fragile=True; at_least_30_trades=False |

## Frozen OOS cohort comparison

Unavailable.

## Frozen OOS per-symbol results on old coins

Unavailable.

## A2 per-symbol test table

Unavailable.

## Plateau verdicts

| winner | neighbors | robust_neighbor_pct | verdict | train_score |
|---|---|---|---|---|
| unconstrained | 7 | 42.857142857142854 | FRAGILE | 1.9991546135063145 |
| with_stop | 7 | 42.857142857142854 | FRAGILE | 1.9991546135063145 |

| axis | config | management | score | ratio | robust_neighbor_pct | verdict |
|---|---|---|---|---|---|---|
| signal | {"filters": ["F_bb", "F_regime", "F_stc", "F_stoch", "F_vol"], "trigger": "T3", "trigger_param": {"level": 40}, "window": 3} | {"add_size_mult": 1.5, "add_spacing_pct": 0, "atr_mult": null, "max_hold_bars": 24, "n_adds": 0, "sl_pct": 3, "tp_pct": 2} | 0.0 | 0.0 | 75.0 | ROBUST |
| signal | {"filters": ["F_stc", "F_vol", "F_regime"], "trigger": "T3", "trigger_param": {"level": 40}, "window": 3} | {"add_size_mult": 1.5, "add_spacing_pct": 0, "atr_mult": null, "max_hold_bars": 24, "n_adds": 0, "sl_pct": 3, "tp_pct": 2} | -0.15505990725535118 | -0.24486762466809245 | 75.0 | ROBUST |
| signal | {"filters": ["F_stoch", "F_vol", "F_regime"], "trigger": "T3", "trigger_param": {"level": 40}, "window": 3} | {"add_size_mult": 1.5, "add_spacing_pct": 0, "atr_mult": null, "max_hold_bars": 24, "n_adds": 0, "sl_pct": 3, "tp_pct": 2} | 0.6332397247922351 | 1.0 | 75.0 | ROBUST |
| signal | {"filters": ["F_stoch", "F_stc", "F_regime"], "trigger": "T3", "trigger_param": {"level": 40}, "window": 3} | {"add_size_mult": 1.5, "add_spacing_pct": 0, "atr_mult": null, "max_hold_bars": 24, "n_adds": 0, "sl_pct": 3, "tp_pct": 2} | 0.48314892654625485 | 0.7629794967534218 | 75.0 | ROBUST |
| signal | {"filters": ["F_stoch", "F_stc", "F_vol"], "trigger": "T3", "trigger_param": {"level": 40}, "window": 3} | {"add_size_mult": 1.5, "add_spacing_pct": 0, "atr_mult": null, "max_hold_bars": 24, "n_adds": 0, "sl_pct": 3, "tp_pct": 2} | 0.7284963287542037 | 1.1504273977650756 | 75.0 | ROBUST |
| signal | {"filters": ["F_stoch", "F_stc", "F_vol", "F_regime"], "trigger": "T3", "trigger_param": {"level": 25}, "window": 3} | {"add_size_mult": 1.5, "add_spacing_pct": 0, "atr_mult": null, "max_hold_bars": 24, "n_adds": 0, "sl_pct": 3, "tp_pct": 2} | 0.538101821027368 | 0.8497600513042961 | 75.0 | ROBUST |
| signal | {"filters": ["F_stoch", "F_stc", "F_vol", "F_regime"], "trigger": "T3", "trigger_param": {"level": 40}, "window": 8} | {"add_size_mult": 1.5, "add_spacing_pct": 0, "atr_mult": null, "max_hold_bars": 24, "n_adds": 0, "sl_pct": 3, "tp_pct": 2} | -0.15505990725535118 | -0.24486762466809245 | 75.0 | ROBUST |
| management | {"filters": ["F_stoch", "F_stc", "F_vol", "F_regime"], "trigger": "T3", "trigger_param": {"level": 40}, "window": 3} | {"add_size_mult": 1.5, "add_spacing_pct": 0, "atr_mult": null, "max_hold_bars": 24, "n_adds": 0, "sl_pct": 8, "tp_pct": 2} | 0.6332397247922351 | 1.0 | 75.0 | ROBUST |
| management | {"filters": ["F_stoch", "F_stc", "F_vol", "F_regime"], "trigger": "T3", "trigger_param": {"level": 40}, "window": 3} | {"add_size_mult": 1.5, "add_spacing_pct": 0, "atr_mult": null, "max_hold_bars": 24, "n_adds": 0, "sl_pct": 3, "tp_pct": 6} | 0.8335330980843692 | 1.3162994446658411 | 75.0 | ROBUST |
| management | {"filters": ["F_stoch", "F_stc", "F_vol", "F_regime"], "trigger": "T3", "trigger_param": {"level": 40}, "window": 3} | {"add_size_mult": 1.5, "add_spacing_pct": 0, "atr_mult": null, "max_hold_bars": 96, "n_adds": 0, "sl_pct": 3, "tp_pct": 2} | 0.6441256716595392 | 1.0171908780215513 | 75.0 | ROBUST |
| management | {"filters": ["F_stoch", "F_stc", "F_vol", "F_regime"], "trigger": "T3", "trigger_param": {"level": 40}, "window": 3} | {"add_size_mult": 1.5, "add_spacing_pct": 0, "atr_mult": null, "max_hold_bars": 24, "n_adds": 2, "sl_pct": 3, "tp_pct": 2} | 0.5341343884707743 | 0.843494758080793 | 75.0 | ROBUST |
| management | {"filters": ["F_stoch", "F_stc", "F_vol", "F_regime"], "trigger": "T3", "trigger_param": {"level": 40}, "window": 3} | {"add_size_mult": 1.5, "add_spacing_pct": 4, "atr_mult": null, "max_hold_bars": 24, "n_adds": 0, "sl_pct": 3, "tp_pct": 2} | 0.6332397247922351 | 1.0 | 75.0 | ROBUST |

## Walk-forward summaries

Unavailable.

Unavailable.

## Latest winner per-symbol tables

| variant | symbol | timeframe | config_id | signal_knobs | management | side | train_trades | train_return | train_pf | train_mdd | train_score | test_return | test_mdd | test_trades | test_win_rate | test_avg_win | test_avg_loss | test_pf | test_total_return | test_max_dd | test_closed_trade_max_dd | test_sharpe | test_avg_hold | test_worst | test_dca_fills | test_stopouts | test_long | test_short |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| unconstrained | SYNTH_A | 1h | 7 | {"bb_depth_pct": 0, "bb_use": "close", "bb_window": 8, "stc_lag": 0, "stc_level": 10, "stc_lookback": 5, "stc_turn_type": 1, "stoch_cross_lag": 4, "stoch_level": 15, "stoch_min_cross_age": 0} | {"add_size_mult": 1.0, "add_spacing_pct": 0, "atr_mult": null, "bb_mid_exit": false, "max_hold_bars": null, "n_adds": 2, "opp_exit": false, "sl_pct": null, "stop_mode": "off", "tp_pct": 2} | combined | 5 | 2.8503578400000054 | inf | -1.9786794047274352 | 1.9991546135063145 | -1.6083688817214965 | -2.931943628058743 | 1 | 0.0 | 0.0 | -160.83688817214966 | 0.0 | -1.6083688817214965 | -2.931943628058743 | -1.6083688817214898 | 0.0 | 145.0 | -160.83688817214966 | 2 | 0 | 1 | 0 |
| unconstrained | SYNTH_B | 1h | 7 | {"bb_depth_pct": 0, "bb_use": "close", "bb_window": 8, "stc_lag": 0, "stc_level": 10, "stc_lookback": 5, "stc_turn_type": 1, "stoch_cross_lag": 4, "stoch_level": 15, "stoch_min_cross_age": 0} | {"add_size_mult": 1.0, "add_spacing_pct": 0, "atr_mult": null, "bb_mid_exit": false, "max_hold_bars": null, "n_adds": 2, "opp_exit": false, "sl_pct": null, "stop_mode": "off", "tp_pct": 2} | combined | 4 | 2.280715392000009 | inf | -1.6540846002599503 | 1.9991546135063145 | -0.8734419382344085 | -3.9868792617931104 | 1 | 0.0 | 0.0 | -87.34419382344085 | 0.0 | -0.8734419382344085 | -3.9868792617931104 | -0.8734419382344094 | 0.0 | 264.0 | -87.34419382344085 | 2 | 0 | 0 | 1 |
| with_stop | SYNTH_A | 1h | 7 | {"bb_depth_pct": 0, "bb_use": "close", "bb_window": 8, "stc_lag": 0, "stc_level": 10, "stc_lookback": 5, "stc_turn_type": 1, "stoch_cross_lag": 4, "stoch_level": 15, "stoch_min_cross_age": 0} | {"add_size_mult": 1.0, "add_spacing_pct": 0, "atr_mult": null, "bb_mid_exit": false, "max_hold_bars": null, "n_adds": 2, "opp_exit": false, "sl_pct": 8.0, "stop_mode": "pct8", "tp_pct": 2} | combined | 5 | 2.8503578400000054 | inf | -1.9786794047274352 | 1.9991546135063145 | -2.048796159999998 | -2.610461914135849 | 2 | 50.0 | 37.976163199999945 | -242.85577919999974 | 0.15637331475124305 | -2.048796159999998 | -2.610461914135849 | -2.4285577919999923 | -1.0317328190120862 | 58.5 | -242.85577919999974 | 3 | 1 | 2 | 0 |
| with_stop | SYNTH_B | 1h | 7 | {"bb_depth_pct": 0, "bb_use": "close", "bb_window": 8, "stc_lag": 0, "stc_level": 10, "stc_lookback": 5, "stc_turn_type": 1, "stoch_cross_lag": 4, "stoch_level": 15, "stoch_min_cross_age": 0} | {"add_size_mult": 1.0, "add_spacing_pct": 0, "atr_mult": null, "bb_mid_exit": false, "max_hold_bars": null, "n_adds": 2, "opp_exit": false, "sl_pct": 8.0, "stop_mode": "pct8", "tp_pct": 2} | combined | 4 | 2.280715392000009 | inf | -1.6540846002599503 | 1.9991546135063145 | -2.431442591999996 | -2.781436691111976 | 1 | 0.0 | 0.0 | -243.1442591999996 | 0.0 | -2.431442591999996 | -2.781436691111976 | -2.4314425920000033 | 0.0 | 103.0 | -243.1442591999996 | 2 | 1 | 0 | 1 |
| long_only | SYNTH_A | 1h | 7 | {"bb_depth_pct": 0, "bb_use": "close", "bb_window": 8, "stc_lag": 0, "stc_level": 10, "stc_lookback": 5, "stc_turn_type": 1, "stoch_cross_lag": 4, "stoch_level": 15, "stoch_min_cross_age": 0} | {"add_size_mult": 1.0, "add_spacing_pct": 0, "atr_mult": null, "bb_mid_exit": false, "max_hold_bars": null, "n_adds": 2, "opp_exit": false, "sl_pct": null, "stop_mode": "off", "tp_pct": 2} | long | 2 | 1.139284896000003 | inf | -0.4497571824180048 | 1.6567801319111677 | -1.6083688817214965 | -2.931943628058743 | 1 | 0.0 | 0.0 | -160.83688817214966 | 0.0 | -1.6083688817214965 | -2.931943628058743 | -1.6083688817214898 | 0.0 | 145.0 | -160.83688817214966 | 2 | 0 | 1 | 0 |
| long_only | SYNTH_B | 1h | 7 | {"bb_depth_pct": 0, "bb_use": "close", "bb_window": 8, "stc_lag": 0, "stc_level": 10, "stc_lookback": 5, "stc_turn_type": 1, "stoch_cross_lag": 4, "stoch_level": 15, "stoch_min_cross_age": 0} | {"add_size_mult": 1.0, "add_spacing_pct": 0, "atr_mult": null, "bb_mid_exit": false, "max_hold_bars": null, "n_adds": 2, "opp_exit": false, "sl_pct": null, "stop_mode": "off", "tp_pct": 2} | long | 2 | 1.1392848960000035 | inf | -1.0152523457596665 | 1.6567801319111677 | 0.0 | 0.0 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0 | 0 | 0 | 0 |
| short_only | SYNTH_A | 1h | 7 | {"bb_depth_pct": 0, "bb_use": "close", "bb_window": 8, "stc_lag": 0, "stc_level": 10, "stc_lookback": 5, "stc_turn_type": 1, "stoch_cross_lag": 4, "stoch_level": 15, "stoch_min_cross_age": 0} | {"add_size_mult": 1.0, "add_spacing_pct": 0, "atr_mult": null, "bb_mid_exit": false, "max_hold_bars": null, "n_adds": 0, "opp_exit": false, "sl_pct": null, "stop_mode": "off", "tp_pct": 2} | short | 3 | 0.5703576480000012 | inf | -0.6683410028712751 | 1.2073948141449493 | 0.0 | 0.0 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0 | 0 | 0 | 0 |
| short_only | SYNTH_B | 1h | 7 | {"bb_depth_pct": 0, "bb_use": "close", "bb_window": 8, "stc_lag": 0, "stc_level": 10, "stc_lookback": 5, "stc_turn_type": 1, "stoch_cross_lag": 4, "stoch_level": 15, "stoch_min_cross_age": 0} | {"add_size_mult": 1.0, "add_spacing_pct": 0, "atr_mult": null, "bb_mid_exit": false, "max_hold_bars": null, "n_adds": 0, "opp_exit": false, "sl_pct": null, "stop_mode": "off", "tp_pct": 2} | short | 3 | 0.5703576480000011 | inf | -0.5575846648388286 | 1.2073948141449493 | -0.296682184715523 | -1.3350530080087628 | 1 | 0.0 | 0.0 | -29.668218471552297 | 0.0 | -0.296682184715523 | -1.3350530080087628 | -0.2966821847155188 | 0.0 | 264.0 | -29.668218471552297 | 0 | 0 | 0 | 1 |

| symbol | timeframe | test_trades | test_return | long | short | config | management |
|---|---|---|---|---|---|---|---|
| SYNTH_A | 1h | 0 | 0.0 | 0 | 0 | {"filters": ["F_stoch", "F_stc", "F_vol", "F_regime"], "trigger": "T3", "trigger_param": {"level": 40}, "window": 3} | {"add_size_mult": 1.5, "add_spacing_pct": 0, "atr_mult": null, "max_hold_bars": 24, "n_adds": 0, "sl_pct": 3, "tp_pct": 2} |
| SYNTH_B | 1h | 3 | 0.14551206025998 | 2 | 1 | {"filters": ["F_stoch", "F_stc", "F_vol", "F_regime"], "trigger": "T3", "trigger_param": {"level": 40}, "window": 3} | {"add_size_mult": 1.5, "add_spacing_pct": 0, "atr_mult": null, "max_hold_bars": 24, "n_adds": 0, "sl_pct": 3, "tp_pct": 2} |

## Mechanical verdicts

Counts: COUNTING=0, NO EDGE=3.
- **A3_unconstrained: NO EDGE.** beats_p90=False; not_fragile=False; at_least_30_trades=False; test return -2.482% versus null p90 -1.088%.
- **A3_with_stop: NO EDGE.** beats_p90=False; not_fragile=False; at_least_30_trades=False; test return -4.480% versus null p90 -1.482%.
- **part_b: NO EDGE.** beats_p90=True; not_fragile=True; at_least_30_trades=False; test return -0.079% versus null p90 -0.310%.

## Stage timings

| stage | seconds |
|---|---|
| data-report | 0.007 |
| A2 | 0.001 |
| data-report | 0.006 |
| A2 | 0.001 |
| A3 | 0.28 |
| B | 0.121 |
| wf | 0.007 |
| data-report | 0.004 |
| A2 | 0.001 |
| A3 | 0.27 |
| B | 0.123 |
| wf | 0.007 |
| null | 0.359 |
| data-report | 0.004 |
| A2 | 0.001 |
| A3 | 0.274 |
| B | 0.121 |
| wf | 0.008 |
| null | 0.359 |
| data-report | 0.004 |
| A2 | 0.001 |
| A3 | 0.274 |
| B | 0.119 |
| wf | 0.007 |
| null | 0.358 |
| report | 0.003 |
| data-report | 0.004 |
| A2 | 0.001 |
| A3 | 0.274 |
| B | 0.124 |
| wf | 0.007 |
| data-report | 0.003 |
| A2 | 0.001 |
| A3 | 0.27 |
| B | 0.12 |
| wf | 0.007 |
| data-report | 0.004 |
| A2 | 0.001 |
| A3 | 0.274 |
| B | 0.124 |
| wf | 0.007 |
| null | 1.017 |
| report | 0.003 |
| B | 0.223 |
| B | 0.251 |
| B | 0.237 |
| B | 0.23 |
| B | 0.235 |
| data-report | 0.004 |
| A2 | 0.001 |
| A3 | 0.238 |
| B | 0.234 |
| data-report | 0.003 |
| A2 | 0.001 |
| A3 | 0.224 |
| B | 0.228 |
| wf | 0.001 |
| null | 1.024 |
| report | 0.007 |
| report | 0.01 |

## Deviations

- Frozen hybrid is omitted because its exact historical configuration is not recoverable from the winner comparison source.
- A3 uses 27 deterministic configurations: bb_window {0,4,8}, stoch_cross_lag {0,4,8}, stc_lag {0,4,8}; remaining signal knobs use canonical first-axis values. Eligibility required at least 150 pooled train events and 30 events for each of the 12 symbols.
- A3 WF ranks the selected train signal set and three fixed management finalists inside each rolling 12m/3m window.
- A3 needed interrupted/error recovery attempts; all elapsed time is listed, with cumulative active time 1,365.263 seconds. The signal-score CSV was reused on the final attempt.
- Part B winner selection was preserved. A test-split index bug in the completed Part B output was corrected by re-evaluating the frozen winners on bars 60%-100%; Part B was not searched or reselected again.
- Nulls use seed 20261120, 200 repetitions and exact per-series direction quotas. The single-trade random executor matches the production simulator on return and exit bar for four checked test cases.

## Reproduce

```sh
.venv/bin/python run_v2.py --stage all
.venv/bin/python run_v2.py --stage all --max-minutes 55
.venv/bin/python run_v2.py --stage all --quick
.venv/bin/python -m pytest -q
```
