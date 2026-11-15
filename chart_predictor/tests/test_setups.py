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

def test_rolling_percentile_rank_is_nan_until_a_full_window_then_causal():
    values=np.array([3.,1.,2.,5.,4.,0.,9.,6.,8.,7.])
    out=indicators.rolling_percentile_rank(values,4)
    assert np.all(np.isnan(out[:3]))
    # Window [3,1,2,5] -> count(<=5)=4/4=1.0; window [1,2,5,4] -> count(<=4)=3/4=0.75.
    assert out[3]==pytest.approx(1.0)
    assert out[4]==pytest.approx(0.75)
    # A later value cannot change an earlier bar's already-computed rank.
    changed=values.copy(); changed[6:]=-100.
    assert np.array_equal(indicators.rolling_percentile_rank(changed,4)[:5],out[:5],equal_nan=True)

def _bb_squeeze_frame(side="long", with_squeeze=True, jump_extra=1.0):
    """160 bars of an oscillating close (varied Bollinger width history), then
    either 15 bars of a near-flat squeeze (width collapses toward the bottom
    decile of its own trailing 120-bar history) or 15 more oscillating bars (no
    contraction), then a breakout bar closing jump_extra past the live band,
    plus one trailing bar so emit()'s i+1<n guard does not drop the signal."""
    x=np.arange(160); noisy=100+np.sin(x/3.0)*2.0
    tail=(noisy[-1]+np.linspace(0,0.01,15)*(1 if side=="long" else -1) if with_squeeze
          else 100+np.sin((160+np.arange(15))/3.0)*2.0)
    c=np.concatenate([noisy,tail])
    o=np.empty_like(c); o[0]=c[0]; o[1:]=c[:-1]
    h=np.maximum(o,c)+.01; l=np.minimum(o,c)-.01
    mid,upper,lower=indicators.bollinger(c,20,2)
    band=upper[-1] if side=="long" else lower[-1]
    breakout=band+jump_extra if side=="long" else band-jump_extra
    c2=np.append(c,[breakout,breakout]); o2=np.append(o,[c[-1],breakout])
    h2=np.append(h,[max(c[-1],breakout)+.01,breakout+.01]); l2=np.append(l,[min(c[-1],breakout)-.01,breakout-.01])
    f=pd.DataFrame({"t_open_ms":1700000000000+np.arange(len(c2))*60000,"o":o2,"h":h2,"l":l2,"c":c2,"v":np.ones(len(c2))})
    return f, len(c2)-2

@pytest.mark.parametrize("side",["long","short"])
def test_bb_squeeze_breakout_fires_after_a_genuine_squeeze(side):
    f,i=_bb_squeeze_frame(side,with_squeeze=True)
    sigs=generate_signals(f,"bb_squeeze_breakout")
    assert any(s.index==i and s.side==side for s in sigs)
    # Stop is the opposite band at the signal bar: below entry for long, above for short.
    hit=[s for s in sigs if s.index==i and s.side==side][0]
    assert (hit.stop<f.c.iloc[i]) if side=="long" else (hit.stop>f.c.iloc[i])

@pytest.mark.parametrize("side",["long","short"])
def test_bb_squeeze_breakout_requires_a_prior_squeeze(side):
    # Same breakout magnitude, but the band never contracted into the bottom
    # decile beforehand -- a band-piercing close alone must not be enough.
    f,i=_bb_squeeze_frame(side,with_squeeze=False)
    assert not any(s.index==i for s in generate_signals(f,"bb_squeeze_breakout"))

def test_bb_squeeze_breakout_strict_rejects_a_marginal_breakout_the_base_rule_accepts():
    # The P8-A refinement requires the close to clear the band by >=0.25*ATR14;
    # a close that clears it by only a hair should still fire the base rule but
    # must be rejected by the ATR-buffered variant.
    f,i=_bb_squeeze_frame("long",with_squeeze=True,jump_extra=0.002)
    base=generate_signals(f,"bb_squeeze_breakout")
    strict=generate_signals(f,"bb_squeeze_breakout_strict")
    assert any(s.index==i and s.side=="long" for s in base)
    assert not any(s.index==i for s in strict)

def _orb_frame(times, highs=None, lows=None, closes=None):
    n=len(times); h=np.full(n,105.); l=np.full(n,95.); c=np.full(n,100.)
    if highs is not None:
        for i,x in highs.items(): h[i]=x
    if lows is not None:
        for i,x in lows.items(): l[i]=x
    if closes is not None:
        for i,x in closes.items(): c[i]=x
    o=np.minimum(c,100.)
    return pd.DataFrame({"t_open_ms":times,"o":o,"h":h,"l":l,"c":c,"v":np.ones(n)})

def test_orb_uses_only_window_bars_and_emits_long_at_first_closed_break():
    times=np.arange(32,dtype=np.int64)*60000
    f=_orb_frame(times,{5:110,30:120},{6:90,30:80},{30:111})
    assert Signal(30,"long",90.) in generate_signals(f,"orb_funding_session")

def test_orb_emits_short_with_opening_range_high_as_stop():
    times=np.arange(32,dtype=np.int64)*60000
    f=_orb_frame(times,{5:110,30:120},{6:90,30:80},{30:89})
    assert Signal(30,"short",110.) in generate_signals(f,"orb_funding_session")

def test_orb_inside_close_does_not_signal():
    times=np.arange(32,dtype=np.int64)*60000
    f=_orb_frame(times,{5:110},{6:90},{30:100})
    assert generate_signals(f,"orb_funding_session")==[]

def test_orb_only_first_breakout_per_session_counts():
    times=np.arange(40,dtype=np.int64)*60000
    f=_orb_frame(times,{5:110,30:120,35:80},{6:90,30:95,35:85},{30:111,35:89})
    sigs=generate_signals(f,"orb_funding_session")
    assert [s for s in sigs if s.index>=30]==[Signal(30,"long",90.)]

def test_orb_new_session_resets_range_and_trigger():
    times=np.r_[np.arange(32,dtype=np.int64)*60000,28_800_000+np.arange(32,dtype=np.int64)*60000]
    f=_orb_frame(times,{5:110,30:111,37:120,62:121},{6:90,30:95,38:85,62:95},{30:111,62:121})
    sigs=generate_signals(f,"orb_funding_session")
    assert Signal(30,"long",90.) in sigs
    assert Signal(62,"long",85.) in sigs

def test_orb_strong_uses_signal_bar_atr_and_accepts_exact_clearance():
    times=np.arange(32,dtype=np.int64)*60000
    f=_orb_frame(times,{5:110,30:112},{6:90,30:109},{30:111})
    atr=np.zeros(len(f)); atr[30]=4.0
    assert Signal(30,"long",90.) in generate_signals(f,"orb_funding_session_strong",{"atr":atr})
    f.loc[30,"c"]=110.99
    assert not any(s.index==30 for s in generate_signals(f,"orb_funding_session_strong",{"atr":atr}))

def _vwap_sine_frame(n=50):
    """50-bar baseline with mild oscillation around 100 (sine amplitude 0.5) and a
    constant 0.2-wide high/low wick, uniform volume -- enough warm-up (>=40 bars)
    for the 20-bar rolling VWAP and the 20-bar rolling stdev of (close-VWAP) that
    feeds it to both be fully populated well before index 40."""
    x=np.arange(n); c=100+np.sin(x/3)*0.5; h=c+0.2; l=c-0.2; v=np.ones(n)
    return c,h,l,v

def _vwap_frame(o,h,l,c,v):
    return pd.DataFrame({"t_open_ms":1700000000000+np.arange(len(c))*60000,"o":o,"h":h,"l":l,"c":c,"v":v})

def test_vwap_band_fade_no_pierce_does_not_signal():
    c,h,l,v=_vwap_sine_frame()
    f=_vwap_frame(c.copy(),h,l,c,v)
    assert generate_signals(f,"vwap_band_fade")==[]

@pytest.mark.parametrize("side",["long","short"])
def test_vwap_band_fade_same_bar_pierce_and_reject(side):
    # A single bar's wick pierces 5 points past the band on a quiet baseline while
    # its own close stays near the unperturbed band -- a same-bar rejection.
    c,h,l,v=_vwap_sine_frame(); h=h.copy(); l=l.copy()
    if side=="short": h[40]=c[40]+5.0
    else: l[40]=c[40]-5.0
    f=_vwap_frame(c.copy(),h,l,c,v)
    sigs=generate_signals(f,"vwap_band_fade")
    expected_stop=h[40] if side=="short" else l[40]
    assert any(s.index==40 and s.side==side and s.stop==pytest.approx(expected_stop) for s in sigs)

@pytest.mark.parametrize("side",["long","short"])
def test_vwap_band_fade_multi_bar_extension_tracks_running_extreme(side):
    # Bar 40 pierces and its close stays outside the band (extension continues,
    # no signal yet); bar 41 pierces further but its close finally comes back
    # inside -- the emitted stop is the running extreme across both bars (108 for
    # short / 92 for long), not just the final bar's own high/low.
    n=50; o=np.full(n,100.); h=np.full(n,100.2); l=np.full(n,99.8); c=np.full(n,100.); v=np.full(n,1.0)
    if side=="short":
        h[40],l[40],c[40]=108.,99.8,103.; h[41],l[41],c[41]=104.,99.8,101.
    else:
        l[40],h[40],c[40]=92.,100.2,97.; l[41],h[41],c[41]=96.,100.2,99.
    f=_vwap_frame(o,h,l,c,v)
    sigs=generate_signals(f,"vwap_band_fade")
    assert not any(s.index==40 and s.side==side for s in sigs)
    expected_stop=108. if side=="short" else 92.
    assert any(s.index==41 and s.side==side and s.stop==pytest.approx(expected_stop) for s in sigs)

@pytest.mark.parametrize("side",["long","short"])
def test_vwap_band_fade_stretch_rejects_a_marginal_wick_the_base_rule_accepts(side):
    # The P8-C refinement requires the tracked extreme to clear the band edge
    # recorded at first piercing by >=0.5*ATR14; a wick that barely pokes past the
    # band (and whose own close sits right at the edge) should still fire the base
    # rule but must be rejected by the ATR-buffered "_stretch" variant.
    c,h,l,v=_vwap_sine_frame(); h=h.copy(); l=l.copy()
    if side=="short": h[40]=100.80
    else: l[40]=99.30
    f=_vwap_frame(c.copy(),h,l,c,v)
    base=generate_signals(f,"vwap_band_fade")
    stretch=generate_signals(f,"vwap_band_fade_stretch")
    assert any(s.index==40 and s.side==side for s in base)
    assert not any(s.index==40 for s in stretch)

@pytest.mark.parametrize("side",["long","short"])
def test_vwap_band_fade_stretch_accepts_a_large_stretch(side):
    # The same 5-point wick used for the base-rule same-bar test also clears the
    # 0.5-ATR stretch requirement, so the refinement must not reject every signal.
    c,h,l,v=_vwap_sine_frame(); h=h.copy(); l=l.copy()
    if side=="short": h[40]=c[40]+5.0
    else: l[40]=c[40]-5.0
    f=_vwap_frame(c.copy(),h,l,c,v)
    stretch=generate_signals(f,"vwap_band_fade_stretch")
    assert any(s.index==40 and s.side==side for s in stretch)

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

def test_macd_matches_manual_ema_recursion():
    # Correctness, independent of indicators.ema(): a hand-rolled adjust=False
    # EMA recursion (alpha=2/(period+1), seeded by the first observation) must
    # match indicators.macd()'s fast/slow EMA difference and its signal EMA.
    c=np.array([10.,12.,11.,13.,15.,14.,16.,18.,17.,19.,20.,18.,21.,22.,20.])
    def manual_ema(values,period):
        alpha=2/(period+1); out=np.empty(len(values)); out[0]=values[0]
        for k in range(1,len(values)): out[k]=alpha*values[k]+(1-alpha)*out[k-1]
        return out
    fast,slow=manual_ema(c,3),manual_ema(c,6)
    expected_line=fast-slow; expected_signal=manual_ema(expected_line,4)
    line,signal,hist=indicators.macd(c,fast=3,slow=6,signal=4)
    np.testing.assert_allclose(line,expected_line)
    np.testing.assert_allclose(signal,expected_signal)
    np.testing.assert_allclose(hist,expected_line-expected_signal)

def test_macd_is_causal():
    c=np.array([10.,12.,11.,13.,15.,14.,16.,18.,17.,19.,20.,18.,21.,22.,20.])
    line,signal,hist=indicators.macd(c)
    k=9
    changed=c.copy(); changed[k:]*=5
    line2,signal2,hist2=indicators.macd(changed[:k])
    # A truncated-but-otherwise-identical prefix must reproduce the same
    # trailing value as the full series at the same confirmation index.
    np.testing.assert_allclose(line[k-1],line2[-1])
    np.testing.assert_allclose(signal[k-1],signal2[-1])
    np.testing.assert_allclose(hist[k-1],hist2[-1])

def test_significant_doji_flags_small_body_on_wide_range_only():
    # Fixed small array, hand-checked: bar 0 is a flat non-move (tiny body AND
    # tiny range -- excluded by the ATR floor); bar 1 is a true doji (tiny
    # body, wide range); bar 2 has a wide range but a large body (not a doji).
    o=np.array([100.0,100.0,100.0])
    c=np.array([100.05,100.05,104.0])
    h=np.array([100.1,110.0,110.0])
    l=np.array([99.9,90.0,90.0])
    a=np.array([1.0,1.0,1.0])  # ATR14 fixed at 1.0 so 0.5*ATR14==0.5
    out=indicators.significant_doji(o,h,l,c,a)
    assert list(out)==[False,True,False]

def test_significant_doji_respects_custom_thresholds():
    o,h,l,c=np.array([100.]),np.array([110.]),np.array([90.]),np.array([101.6])
    a=np.array([1.0])
    # body=1.6, range=20 -> body/range=0.08: passes the default 10% body_ratio...
    assert indicators.significant_doji(o,h,l,c,a,body_ratio=0.10)[0]
    # ...but fails a stricter 5% threshold.
    assert not indicators.significant_doji(o,h,l,c,a,body_ratio=0.05)[0]

def test_significant_doji_is_nan_atr_safe_and_causal():
    o=np.array([100.,100.,100.])
    c=np.array([100.,100.,100.])
    h=np.array([100.6,100.6,100.6])
    l=np.array([99.4,99.4,99.4])
    a=np.array([np.nan,1.0,1.0])
    out=indicators.significant_doji(o,h,l,c,a)
    assert out[0]==False  # NaN ATR can never confirm a signal
    assert out[1]==out[2]==True
    # Only the current bar's own OHLC+ATR decide its flag; mutating a later bar
    # cannot change an earlier bar's already-computed value.
    o2,h2,l2,c2,a2=o.copy(),h.copy(),l.copy(),c.copy(),a.copy()
    o2[2],h2[2],l2[2],c2[2],a2[2]=5.,50.,1.,5.,100.
    out2=indicators.significant_doji(o2,h2,l2,c2,a2)
    assert out2[1]==out[1]

def _doji_macd_base(n=120):
    """Oscillating close (period ~37.7 bars) gives a MACD histogram several
    natural zero-crossings; wicks are small and fixed so the un-doctored
    series itself is almost never a doji."""
    x=np.arange(n); c=100+np.sin(x/6.0)*3.0
    o=np.empty_like(c); o[0]=c[0]; o[1:]=c[:-1]
    h=np.maximum(o,c)+.3; l=np.minimum(o,c)-.3
    return o,h,l,c

def _doji_macd_indices(o,h,l,c):
    """Pick (a) the first bar >=20 where the MACD histogram flips sign and the
    un-doctored bar is not already a doji, and (b) the first bar >=20 with no
    flip, both computed from the real indicators rather than hardcoded."""
    hist=indicators.macd(c)[2]; a=indicators.atr(h,l,c,14); base_doji=indicators.significant_doji(o,h,l,c,a)
    flip=next(i for i in range(20,len(c)-1) if np.isfinite(hist[i-1]) and np.isfinite(hist[i])
              and (hist[i-1]<=0<hist[i] or hist[i-1]>=0>hist[i]) and not base_doji[i])
    nonflip=next(i for i in range(20,len(c)-1) if np.isfinite(hist[i-1]) and np.isfinite(hist[i])
                 and not (hist[i-1]<=0<hist[i] or hist[i-1]>=0>hist[i]))
    return flip,nonflip,hist

def _doji_macd_frame(o,h,l,c):
    n=len(c)
    return pd.DataFrame({"t_open_ms":1700000000000+np.arange(n)*60000,"o":o,"h":h,"l":l,"c":c,"v":np.ones(n)})

def test_doji_macd_flip_fires_on_a_doji_bar_with_a_histogram_sign_change():
    o,h,l,c=_doji_macd_base()
    i,_,hist=_doji_macd_indices(o,h,l,c)
    o2,h2,l2,c2=o.copy(),h.copy(),l.copy(),c.copy()
    o2[i]=c2[i]; h2[i]=c2[i]+10; l2[i]=c2[i]-10  # force a wide-range, zero-body doji
    sigs=generate_signals(_doji_macd_frame(o2,h2,l2,c2),"doji_macd_flip")
    side="long" if hist[i]>0 else "short"
    expect_stop=l2[i] if side=="long" else h2[i]
    assert Signal(i,side,expect_stop) in sigs

def test_doji_macd_flip_requires_the_histogram_flip_not_just_the_doji():
    o,h,l,c=_doji_macd_base()
    _,j,_=_doji_macd_indices(o,h,l,c)
    o3,h3,l3,c3=o.copy(),h.copy(),l.copy(),c.copy()
    o3[j]=c3[j]; h3[j]=c3[j]+10; l3[j]=c3[j]-10  # same forced doji, but no flip at j
    sigs=generate_signals(_doji_macd_frame(o3,h3,l3,c3),"doji_macd_flip")
    assert not any(s.index==j for s in sigs)

def test_doji_macd_flip_requires_the_doji_not_just_the_flip():
    o,h,l,c=_doji_macd_base()
    i,_,_=_doji_macd_indices(o,h,l,c)
    # Un-doctored bar i has a histogram flip but (by construction) is not a doji.
    sigs=generate_signals(_doji_macd_frame(o,h,l,c),"doji_macd_flip")
    assert not any(s.index==i for s in sigs)

def test_doji_macd_flip_strict_rejects_a_marginal_doji_the_base_rule_accepts():
    o,h,l,c=_doji_macd_base()
    i,_,_=_doji_macd_indices(o,h,l,c)
    o5,h5,l5,c5=o.copy(),h.copy(),l.copy(),c.copy()
    h5[i]=c5[i]+10; l5[i]=c5[i]-10; rng=h5[i]-l5[i]
    o5[i]=c5[i]-0.08*rng  # body/range=0.08: passes base 10% but fails strict 5%
    f=_doji_macd_frame(o5,h5,l5,c5)
    assert any(s.index==i for s in generate_signals(f,"doji_macd_flip"))
    assert not any(s.index==i for s in generate_signals(f,"doji_macd_flip_strict"))
