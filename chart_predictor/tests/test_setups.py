import numpy as np
import pandas as pd
import pytest
from chart_predictor.setups import SETUPS, Signal, generate_signals
from chart_predictor.setup_backtest import DEV_CUTOFF_MS, resolve_trade, wilson, htf_direction_at
from chart_predictor import indicators

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

def _ohlc(o,h,l,c):
    n=len(c)
    return pd.DataFrame({"t_open_ms":1700000000000+np.arange(n)*60000,"o":o,"h":h,"l":l,"c":c,"v":np.ones(n)})

@pytest.mark.parametrize("side",["long","short"])
def test_order_block_impulse_retest_and_invalidation(side):
    o=np.full(18,100.); h=np.full(18,101.); l=np.full(18,99.); c=np.full(18,100.)
    if side=="long":
        o[14],h[14],l[14],c[14]=100,101,98,99
        o[15],h[15],l[15],c[15]=100,105,99,104
        o[16],h[16],l[16],c[16]=100,102,99,101.2
    else:
        o[14],h[14],l[14],c[14]=101,102,100,101.5
        o[15],h[15],l[15],c[15]=101,101.5,95,97
        o[16],h[16],l[16],c[16]=100,101,99,99.5
    sigs=generate_signals(_ohlc(o,h,l,c),"order_block")
    assert any(s.index==16 and s.side==side for s in sigs)
    c[16]=97 if side=="long" else 103
    near=generate_signals(_ohlc(o,h,l,c),"order_block")
    assert not any(s.index==16 and s.side==side for s in near)

@pytest.mark.parametrize("side",["long","short"])
def test_fabio_grab_then_next_bar_mss(side):
    o=np.full(63,100.); h=np.full(63,101.); l=np.full(63,99.); c=np.full(63,100.)
    if side=="short":
        h[60],c[60]=103,102; l[61],c[61]=98,98.5
    else:
        l[60],c[60]=97,98; h[61],c[61]=102,101.5
    sigs=generate_signals(_ohlc(o,h,l,c),"fabio_liquidity_mss")
    assert any(s.index==61 and s.side==side for s in sigs)

def test_fabio_grab_without_mss_does_not_signal():
    o=np.full(63,100.); h=np.full(63,101.); l=np.full(63,99.); c=np.full(63,100.)
    h[60],c[60]=103,102
    assert not generate_signals(_ohlc(o,h,l,c),"fabio_liquidity_mss")

def test_heikin_ashi_reversal_long_flip_uses_recursive_open_stop():
    f=_ohlc([10,12,12],[10,12,12],[0,12,12],[10,12,12])
    sigs=generate_signals(f,"heikin_ashi_reversal")
    assert Signal(1,"long",8.75) in sigs

def test_heikin_ashi_reversal_no_flip_when_bullish_throughout():
    f=_ohlc([10]*8,[20]*8,[10]*8,[10]*8)
    assert generate_signals(f,"heikin_ashi_reversal")==[]

def test_heikin_ashi_reversal_short_flip_is_symmetric_extension():
    f=_ohlc([10,5,5],[20,5,5],[10,5,5],[10,5,5])
    assert Signal(1,"short",11.25) in generate_signals(f,"heikin_ashi_reversal")

def test_heikin_ashi_reversal_wrong_side_stop_is_suppressed():
    f=_ohlc([10,12,12],[10,12,12],[0,12,12],[10,12,12])
    f.loc[1,"c"]=8
    assert not any(s.index==1 for s in generate_signals(f,"heikin_ashi_reversal"))

def test_heikin_ashi_reversal_strict_requires_half_atr_body():
    o=np.full(21,100.); h=np.full(21,101.); l=np.full(21,99.); c=np.full(21,100.)
    # A tiny HA body inside a wide-range flip is below the fixed 0.5 ATR14 conviction threshold.
    h[-2],l[-2],c[-2]=110.,90.,100.5
    f=_ohlc(o,h,l,c)
    assert not any(s.index==19 for s in generate_signals(f,"heikin_ashi_reversal_strict"))
    # A clear close-driven flip with a 5-point HA body clears the same threshold.
    h[-2],l[-2],c[-2]=110.,100.,110.
    f=_ohlc(o,h,l,c)
    assert Signal(19,"long",100.) in generate_signals(f,"heikin_ashi_reversal_strict")

def test_supertrend_direction_matches_inline_rule():
    f=candles(100); h,l,c=(f[k].to_numpy() for k in ("h","l","c")); a=indicators.atr(h,l,c,14)
    expected=np.zeros(len(c),int); upper=(h+l)/2+3*a; lower=(h+l)/2-3*a
    for i in range(1,len(c)):
        if np.isfinite(a[i]):
            expected[i]=1 if c[i]>upper[i-1] else -1 if c[i]<lower[i-1] else expected[i-1]
    assert np.array_equal(indicators.supertrend_direction(h,l,c,a),expected)

def test_htf_alignment_uses_only_fully_closed_bars():
    opens=np.array([0,60,120]); dirs=np.array([-1,1,-1]); width=60
    assert htf_direction_at(opens,dirs,width,60)==-1
    assert htf_direction_at(opens,dirs,width,60)!=1
    assert htf_direction_at(opens,dirs,width,59)==0
    assert htf_direction_at(opens,dirs,width,179)==1
