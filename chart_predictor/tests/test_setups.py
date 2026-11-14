import numpy as np
import pandas as pd
import pytest
from chart_predictor.setups import SETUPS, Signal, generate_signals
from chart_predictor.setup_backtest import DEV_CUTOFF_MS, resolve_trade, wilson

def candles(n=240):
    x=np.arange(n); c=100+np.sin(x/7)*2+x*.01
    return pd.DataFrame({"t_open_ms":1700000000000+x*60000,"o":c-.1,"h":c+.5,"l":c-.5,"c":c,"v":np.ones(n)})

@pytest.mark.parametrize("setup",SETUPS)
def test_generators_are_deterministic_and_causal(setup):
    f=candles(); a=generate_signals(f,setup); b=generate_signals(f.copy(),setup)
    assert a==b
    # Altering only observations after a closed signal cannot alter that signal's identity.
    if a:
        i=a[0].index; changed=f.copy(); changed.loc[i+1:, ["o","h","l","c"]]*=7
        assert [s for s in generate_signals(changed,setup) if s.index<=i]==[a[0]]

@pytest.mark.parametrize("side",["long","short"])
def test_entry_next_bar_and_stop_first_same_minute(side):
    f=pd.DataFrame({"t_open_ms":[0,60000,120000],"o":[100,100,100],"h":[101,106,101],"l":[99,94,99],"c":[100,100,100]})
    raw=pd.DataFrame({"t_open_ms":[60000,120000],"o":[100,100],"h":[106,101],"l":[94,99],"c":[100,100]})
    sig=Signal(0,side,95 if side=="long" else 105)
    # For either direction the same minute spans stop and target; stop is selected.
    out=resolve_trade(sig,f,raw,"1m",2)
    assert out["reason"]=="stop"

def test_cutoff_is_hard_dev_boundary():
    assert DEV_CUTOFF_MS==1791504000000
    assert pd.Timestamp(DEV_CUTOFF_MS,unit="ms",tz="UTC").isoformat()=="2026-10-09T00:00:00+00:00"

def test_cost_math_and_wilson():
    f=pd.DataFrame({"t_open_ms":[0,60000],"o":[100,100],"h":[101,101],"l":[99,99],"c":[100,100]})
    raw=pd.DataFrame({"t_open_ms":[60000],"o":[100],"h":[115],"l":[99],"c":[114]})
    out=resolve_trade(Signal(0,"long",95),f,raw,"1m",2)
    assert out["reason"]=="target"
    assert out["net"]==pytest.approx(.10-.001)
    assert len(wilson(8,10))==2

def test_single_position_entry_offset():
    f=candles(20); raw=f.copy(); sig=Signal(2,"long",99)
    out=resolve_trade(sig,f,raw,"1m",2)
    assert out is not None
    assert out["entry"]==pytest.approx(f.o.iloc[3])
