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
def test_fvg_fill_first_overlap_without_reclaim(side):
    o=np.full(9,100.); h=np.full(9,101.); l=np.full(9,99.); c=np.full(9,100.)
    if side=="long":
        h[0],l[2],c[2]=100,102,101
        o[3],h[3],l[3],c[3]=101,103,100.5,101
        low,high=100,102
    else:
        l[0],h[2],c[2]=102,100,101
        o[3],h[3],l[3],c[3]=101,101.5,99,101
        low,high=100,102
    sigs=generate_signals(_ohlc(o,h,l,c),"fvg_fill")
    assert any(s.index==3 and s.side==side and s.stop==pytest.approx(low if side=="long" else high) for s in sigs)

@pytest.mark.parametrize("side",["long","short"])
def test_fvg_fill_invalidation_and_expiry(side):
    def frame(fill_index=None, invalid_index=None):
        n=66; o=np.full(n,100.); h=np.full(n,101.); l=np.full(n,99.); c=np.full(n,100.)
        if side=="long":
            h[0],l[2],c[2]=100,102,101
            low,high=100,102
            l[3:],h[3:],c[3:]=103,104,103.5
            if invalid_index is not None: c[invalid_index]=99
        else:
            l[0],h[2],c[2]=102,100,101
            low,high=100,102
            l[3:],h[3:],c[3:]=97,98,97.5
            if invalid_index is not None: c[invalid_index]=103
        if fill_index is not None:
            l[fill_index],h[fill_index],c[fill_index]=101,102.5,101.5
        return _ohlc(o,h,l,c),low,high
    f,_,_=frame(invalid_index=4)
    assert not any(s.side==side and s.index==4 for s in generate_signals(f,"fvg_fill"))
    f,_,_=frame(fill_index=63)
    # The 12-bar freshness cap is stricter than the sourced 60-bar expiry.
    assert not any(s.side==side and s.index==63 for s in generate_signals(f,"fvg_fill"))
    f,_,_=frame(fill_index=15)
    assert not any(s.side==side and s.index==15 for s in generate_signals(f,"fvg_fill"))
    f,_,_=frame(fill_index=14)
    assert any(s.side==side and s.index==14 for s in generate_signals(f,"fvg_fill"))

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

def _frvp_frame(side="long", thin_volume=1.0, breakout=True, flat=False):
    """60-bar FRVP lookback window (indices 0..59) plus one breakout bar (index 60).
    A 48-bar dominant cluster at 100 forms the POC; a 5-bar thin cluster (97 for
    long, 103 for short) forms the low-volume node on the breakout's side; the last
    window bar (index 59) sits between that node and the POC."""
    n=62
    o=np.full(n,100.); h=np.full(n,100.1); l=np.full(n,99.9); c=np.full(n,100.)
    v=np.full(n,20.0) if flat else np.zeros(n)
    if not flat:
        for i in range(10,58):
            c[i]=o[i]=100.0; h[i]=100.1; l[i]=99.9; v[i]=20.0
        if side=="long":
            for i in range(0,5):
                c[i]=o[i]=97.0; h[i]=97.1; l[i]=96.9; v[i]=thin_volume
            c[59]=o[59]=98.45; h[59]=98.55; l[59]=98.35; v[59]=thin_volume
        else:
            for i in range(0,5):
                c[i]=o[i]=103.0; h[i]=103.1; l[i]=102.9; v[i]=thin_volume
            c[59]=o[59]=101.55; h[59]=101.65; l[59]=101.45; v[59]=thin_volume
    if side=="long":
        if breakout: o[60],h[60],l[60],c[60]=100.0,103.1,99.9,103.0
        else: o[60],h[60],l[60],c[60]=100.0,99.9,99.5,99.6
    else:
        if breakout: o[60],h[60],l[60],c[60]=100.0,100.1,96.9,97.0
        else: o[60],h[60],l[60],c[60]=100.0,100.5,99.9,100.4
    return pd.DataFrame({"t_open_ms":1700000000000+np.arange(n)*60000,"o":o,"h":h,"l":l,"c":c,"v":v})

@pytest.mark.parametrize("side",["long","short"])
def test_frvp_breakout_from_between_lvn_and_poc(side):
    sigs=generate_signals(_frvp_frame(side),"frvp_breakout")
    assert any(s.index==60 and s.side==side for s in sigs)
    # Stop sits on the far side of the LVN from the POC: below entry for long,
    # above entry for short, matching the "LVN is a natural invalidation" choice.
    hit=[s for s in sigs if s.index==60 and s.side==side][0]
    assert (hit.stop<100.) if side=="long" else (hit.stop>100.)

@pytest.mark.parametrize("side",["long","short"])
def test_frvp_no_breakout_does_not_signal(side):
    sigs=generate_signals(_frvp_frame(side,breakout=False),"frvp_breakout")
    assert not any(s.index==60 for s in sigs)

def test_frvp_flat_profile_has_no_lvn_and_does_not_signal():
    # A single uniform price for the whole lookback window has no secondary price
    # level at all, so no bin can qualify as a below-POC low-volume node; the rule
    # must skip the bar rather than invent an LVN.
    sigs=generate_signals(_frvp_frame("long",flat=True),"frvp_breakout")
    assert not any(s.index==60 for s in sigs)

def test_frvp_strong_rejects_a_marginal_breakout_the_base_rule_accepts():
    # The P7-B refinement requires the breakout close to clear the POC by
    # >=0.25*ATR; a close that clears POC by only a hair should still fire the
    # base rule but must be rejected by the ATR-buffered variant.
    f=_frvp_frame("long")
    f.loc[60,["o","h","l","c"]]=[100.0,100.1,99.9,99.98]  # ~.04 above POC, <0.25*ATR
    base=generate_signals(f,"frvp_breakout")
    strong=generate_signals(f,"frvp_breakout_strong")
    assert any(s.index==60 and s.side=="long" for s in base)
    assert not any(s.index==60 for s in strong)

def _vcx_frame(n=22, climax_volume=50.0, baseline_volume=10.0):
    """n-1 quiet bars (baseline trailing volume = baseline_volume) plus one
    climax bar at index n-2 and a trailing bar at n-1 so emit()'s i+1<n holds."""
    o=np.full(n,100.); h=np.full(n,101.); l=np.full(n,99.); c=np.full(n,100.)
    v=np.full(n,baseline_volume)
    v[-2]=climax_volume
    return o,h,l,c,v

def _vcx_ohlcv(o,h,l,c,v):
    n=len(c)
    return pd.DataFrame({"t_open_ms":1700000000000+np.arange(n)*60000,"o":o,"h":h,"l":l,"c":c,"v":v})

def test_volume_climax_exhaustion_short_on_new_high_climax_rejection_wick():
    o,h,l,c,v=_vcx_frame()
    i=len(c)-2
    o[i],h[i],l[i],c[i]=100,110,95,98  # new 10-bar high, closes in lower half (frac .2)
    sigs=generate_signals(_vcx_ohlcv(o,h,l,c,v),"volume_climax_exhaustion")
    assert Signal(i,"short",110.0) in sigs

def test_volume_climax_exhaustion_long_on_new_low_climax_rejection_wick():
    o,h,l,c,v=_vcx_frame()
    i=len(c)-2
    o[i],h[i],l[i],c[i]=100,105,90,103  # new 10-bar low, closes in upper half
    sigs=generate_signals(_vcx_ohlcv(o,h,l,c,v),"volume_climax_exhaustion")
    assert Signal(i,"long",90.0) in sigs

def test_volume_climax_exhaustion_no_signal_without_volume_spike():
    o,h,l,c,v=_vcx_frame(climax_volume=10.0)  # same as baseline: no spike at all
    i=len(c)-2
    o[i],h[i],l[i],c[i]=100,110,95,98  # same wick geometry as the passing short case
    sigs=generate_signals(_vcx_ohlcv(o,h,l,c,v),"volume_climax_exhaustion")
    assert not any(s.index==i for s in sigs)

def test_volume_climax_exhaustion_no_signal_without_new_extreme():
    o,h,l,c,v=_vcx_frame()
    i=len(c)-2
    o[i],h[i],l[i],c[i]=100,101,95,98  # climax volume but not a fresh 10-bar high
    sigs=generate_signals(_vcx_ohlcv(o,h,l,c,v),"volume_climax_exhaustion")
    assert not any(s.index==i for s in sigs)

def test_volume_climax_exhaustion_no_signal_without_rejection_wick():
    o,h,l,c,v=_vcx_frame()
    i=len(c)-2
    # New high (not a new low: l stays above the trailing 10-bar low of 99),
    # climax volume, but closes near the high instead of back toward the open.
    o[i],h[i],l[i],c[i]=100,110,99.5,109
    sigs=generate_signals(_vcx_ohlcv(o,h,l,c,v),"volume_climax_exhaustion")
    assert not any(s.index==i for s in sigs)

def test_volume_climax_exhaustion_strict_requires_5x_not_4x():
    o,h,l,c,v=_vcx_frame(climax_volume=40.0)  # 4x baseline: fires base rule, not strict
    i=len(c)-2
    o[i],h[i],l[i],c[i]=100,110,95,98
    f=_vcx_ohlcv(o,h,l,c,v)
    assert any(s.index==i and s.side=="short" for s in generate_signals(f,"volume_climax_exhaustion"))
    assert not any(s.index==i for s in generate_signals(f,"volume_climax_exhaustion_strict"))
    f.loc[i,"v"]=55.0  # 5.5x baseline clears the stricter threshold
    assert any(s.index==i and s.side=="short" for s in generate_signals(f,"volume_climax_exhaustion_strict"))

