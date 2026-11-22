import importlib.util
from pathlib import Path
import numpy as np, pandas as pd, pytest
from common.protocol import check_no_lookahead
ROOT=Path(__file__).resolve().parents[2]/'plugins'/'slice_4'
DATA=Path(__file__).resolve().parents[3]/'bb_stoch_stc'/'data'
IDS=['c5-bb-percent-b-21-meanrev-1.2-lines','c5-ema-rainbow-10-20-50-100-150-200-stack','c5-nick-radge-bollinger-blast-unholy-grail','c5-raschke-turtle-soup-20d-false-break','c5-sc-percent-b-mfi-bollinger']
def load(sid):
 s=importlib.util.spec_from_file_location('plugin_'+sid.replace('-','_'),ROOT/(sid+'.py')); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
@pytest.mark.parametrize('sid',IDS)
def test_no_lookahead(sid):
 m=load(sid); tf=m.TIMEFRAMES[0]; df=pd.read_parquet(DATA/f'BTCUSDT_{tf}.parquet'); assert check_no_lookahead(m,df,m.PARAMS)
def test_bb_percent_b_hand_signal():
 m=load(IDS[0]); c=np.r_[np.full(21,100.),70.,100.,130.,100.]; df=pd.DataFrame({'close':c}); out=m.signals(df,length=21,stdev=2); assert out.long_entry.iloc[21] and out.long_exit.iloc[22] and out.short_entry.iloc[23] and out.short_exit.iloc[24]
def test_nick_cross_signal_hand():
 m=load(IDS[2]); c=np.array([100,100,100,100,100,100,100,100,100,100,100,130,100.],float); df=pd.DataFrame({'close':c}); out=m.signals(df,length=10,entry_sd=1,exit_sd=1); assert out.long_entry.iloc[11]
def test_signals_return_aligned_boolean_frames():
 for sid in IDS:
  m=load(sid); df=pd.read_parquet(DATA/f'BTCUSDT_{m.TIMEFRAMES[0]}.parquet').tail(800); out=m.signals(df,**m.PARAMS); assert len(out)==len(df); assert {'long_entry','short_entry','long_exit','short_exit'}<=set(out); assert all(pd.api.types.is_bool_dtype(out[c]) for c in ('long_entry','short_entry','long_exit','short_exit'))
def test_ema_rainbow_stack_reclaim_hand_signal():
 m=load(IDS[1]); c=np.r_[np.full(220,100.),110.,100.]; df=pd.DataFrame({'close':c}); out=m.signals(df,trail=.08); assert out.long_entry.iloc[220]
def test_nick_loss_stop_is_signal_not_per_bar_stop_column():
 m=load(IDS[2]); c=np.array([100]*10+[260,230,230.],float); df=pd.DataFrame({'close':c}); out=m.signals(df,entry_sd=1); assert out.long_entry.iloc[10] and out.long_exit.iloc[11] and 'stop_pct' not in out
def test_sc_percent_b_mfi_thrust_hand_signal():
 m=load(IDS[4]); c=np.r_[np.full(20,100.),120.]; df=pd.DataFrame({'close':c,'high':c,'low':c,'volume':np.full(len(c),100.)}); out=m.signals(df); assert out.long_entry.iloc[20]
def test_turtle_soup_old_low_break_then_reentry_hand_signal():
 m=load(IDS[3]); days=pd.date_range('2024-01-01',periods=22,freq='D',tz='UTC'); idx=days; lows=np.full(22,100.); highs=np.full(22,120.); closes=np.full(22,110.); lows[0]=90.; lows[20]=80.; closes[21]=100.; df=pd.DataFrame({'open':closes,'high':highs,'low':lows,'close':closes},index=idx); out=m.signals(df); assert out.long_entry.iloc[21]
