import json
import numpy as np
import pandas as pd
import run_v4
import nullbench
from data import synthetic
from strategy import signal_frame

def test_e1_params_match_v3_l5_4h_winner():
    row=pd.read_csv(run_v4.ROOT/'results_v3/tune_winners.csv')
    row=row[(row.cohort=='L5')&(row.timeframe=='4h')&(row.variant=='combined')].iloc[0]
    actual_signal=json.loads(row.signal); actual_management=json.loads(row.management)
    assert set(actual_signal)=={'bb_depth_pct','bb_use','bb_window','stc_lag','stc_level','stc_lookback','stc_turn_type','stoch_cross_lag','stoch_level','stoch_min_cross_age'}
    assert actual_signal['bb_depth_pct']==0 and actual_signal['bb_use']=='close'
    assert actual_signal['bb_window']==4 and actual_signal['stc_lag']==4 and actual_signal['stoch_cross_lag']==4
    assert actual_signal['stc_level']==40 and actual_signal['stoch_level']==30
    assert actual_management == dict(add_size_mult=1.0,add_spacing_pct=2,atr_mult=4.0,bb_mid_exit=False,
        max_hold_bars=48,n_adds=2,opp_exit=False,sl_pct=None,stop_mode='atr4',tp_pct=2)

def test_train_test_bounds_do_not_overlap():
    df=synthetic('BTCUSDT','1d',1000); cut=int(len(df)*.6)
    train=df.iloc[:cut]; test=df.iloc[cut:]
    assert train.index[-1] < test.index[0]
    assert len(train)+len(test)==len(df)
    assert train.index[-1] < test.index[0]  # test begins strictly after the last selected train bar

def test_future_mutation_cannot_change_train_signals_or_metrics():
    df=synthetic('PREFIX','1d',900);cut=540;cfg=json.loads(pd.read_csv(run_v4.ROOT/'results_v3/tune_winners.csv').query("cohort == 'L5' and timeframe == '4h' and variant == 'combined'").iloc[0].signal)
    altered=df.copy();altered.iloc[cut:,altered.columns.get_loc('close')]*=3.7
    altered.iloc[cut:,altered.columns.get_loc('high')]*=3.7;altered.iloc[cut:,altered.columns.get_loc('low')]*=3.7;altered.iloc[cut:,altered.columns.get_loc('open')]*=3.7
    left=signal_frame(df,cfg).iloc[:cut];right=signal_frame(altered,cfg).iloc[:cut]
    pd.testing.assert_frame_equal(left,right)
    management=dict(add_size_mult=1.,n_adds=2,add_spacing_pct=2,tp_pct=2,sl_pct=None,atr_mult=4.,max_hold_bars=48,bb_mid_exit=False,opp_exit=False)
    a=__import__('strategy').simulate(df.iloc[:cut],left,management,'combined')
    b=__import__('strategy').simulate(altered.iloc[:cut],right,management,'combined')
    assert (a['trades'],a['total_return'],a['max_dd'])==(b['trades'],b['total_return'],b['max_dd'])

def test_one_sided_null_randomizes_entry_positions_and_direction():
    df=synthetic('ONE-SIDE','1d',700)
    key=('ONE-SIDE','1d'); bounds={key:(100,650)}
    mg=dict(add_size_mult=1.,n_adds=0,add_spacing_pct=2,tp_pct=2,sl_pct=5.,atr_mult=None,
            stop_mode='pct5',max_hold_bars=12,bb_mid_exit=False,opp_exit=False)
    sf=signal_frame(df,{})
    counts={key:dict(trades=8,long=8,short=0,bb_mid=sf.bb_mid.to_numpy(),atr=sf.atr.to_numpy())}
    vals=nullbench.run_null({key:df},bounds,mg,counts,seed=771,repetitions=200,workers=2)
    assert len(np.unique(np.round(vals,10)))>=10
    assert np.std(vals)>1e-10
    assert np.isfinite(vals).all()
