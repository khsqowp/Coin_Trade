import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parent))
import reimpl as R

DATA=Path(__file__).resolve().parents[2]/'bb_stoch_stc'/'data'

@pytest.mark.parametrize('sid',R.IDS)
def test_signal_prefix_invariance_on_real_data(sid):
    tf=R.TF.get(sid,'1d'); d=pd.read_parquet(DATA/f'BTCUSDT_{tf}.parquet').iloc[:1800].copy(); p=R.PARAMS[sid]
    full=R.SIGNALS[sid](d,**p)
    cols=['long_entry','short_entry','long_exit','short_exit']
    for end in sorted(set([17, max(20,len(d)//3),max(30,len(d)//2),len(d)-1])):
        prefix=R.SIGNALS[sid](d.iloc[:end],**p)
        pd.testing.assert_frame_equal(full[cols].iloc[:end].reset_index(drop=True),prefix[cols].reset_index(drop=True),check_dtype=False)

def test_next_bar_open_fill_and_cost_arithmetic():
    idx=pd.date_range('2024-01-01',periods=4,freq='D',tz='UTC')
    d=pd.DataFrame({'open':[100.,110.,120.,130.],'high':[101.,111.,121.,131.],'low':[99.,109.,119.,129.],'close':[100.,110.,120.,130.]},index=idx)
    sig=pd.DataFrame({'long_entry':[True,False,False,False],'short_entry':False,'long_exit':[False,True,False,False],'short_exit':False},index=idx)
    t=R.simulate(d,sig,side='long')[0]
    entry=110*(1+R.SLIPPAGE); exit_=120*(1-R.SLIPPAGE); qty=1000/entry
    expect=(exit_-entry)*qty-entry*qty*R.FEE-exit_*qty*R.FEE
    assert t['entry']==1 and t['exit']==2
    assert t['net']==pytest.approx(expect)

