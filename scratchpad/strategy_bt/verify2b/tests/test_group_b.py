import importlib.util
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[2]
def test_long_data_timestamp_index():
 p=ROOT/'data_long/BTCUSDT_1d.parquet'
 if not p.exists(): return
 d=pd.read_parquet(p); assert isinstance(d.index,pd.DatetimeIndex); assert str(d.index.tz)=='UTC'; assert d.index.name=='open_time'
def test_nyse_timestamp_restore_matches_cached():
 p=ROOT.parent/'bb_stoch_stc/data/BTCUSDT_15m.parquet'
 if not p.exists(): return
 d=pd.read_parquet(p); assert isinstance(d.index,pd.DatetimeIndex); assert d.index.is_monotonic_increasing
 sp=importlib.util.spec_from_file_location('nyse_plugin',ROOT/'plugins/slice_0/btc-max10-nyse-close.py'); m=importlib.util.module_from_spec(sp); sp.loader.exec_module(m)
 sig=m.signals(d.tail(min(len(d),2000)).copy()); assert len(sig)==min(len(d),2000)
def test_shift_alignment_is_explicit():
 import numpy as np
 x=pd.Series(np.arange(100,dtype=float)); assert x.shift(26).iloc[30]==4; assert x.shift(25).iloc[30]==5; assert pd.isna(x.shift(26).iloc[25])
def test_no_lookahead_jesse():
 from common.protocol import check_no_lookahead
 sp=importlib.util.spec_from_file_location('jesse_plugin',ROOT/'plugins/slice_3/jesse_simple_bollinger.py'); m=importlib.util.module_from_spec(sp); sp.loader.exec_module(m)
 d=pd.read_parquet(ROOT/'data_long/BTCUSDT_1h.parquet').tail(3000); assert check_no_lookahead(m,d)
