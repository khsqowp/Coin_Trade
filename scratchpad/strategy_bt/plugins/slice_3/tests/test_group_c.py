import importlib.util
from pathlib import Path
import numpy as np
import pandas as pd
from common.protocol import check_no_lookahead

ROOT=Path(__file__).resolve().parents[1]
IDS=["four-lower-high-break-intraday","crypto-15m-previous-candle-contrarian","c4-upbit-larry-williams-k05-volatility-breakout","jesse_dual_thrust","tv_dca_rsi_martingale","tv_trend_pullback_ema21"]
def load(name):
    p=ROOT/(name+".py"); s=importlib.util.spec_from_file_location("p_"+name.replace("-","_"),p); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
def frame(index,close,high=None,low=None,open_=None):
    c=np.asarray(close,float); n=len(c)
    return pd.DataFrame({"open":c if open_ is None else open_,"high":c+.5 if high is None else high,"low":c-.5 if low is None else low,"close":c,"volume":np.ones(n)},index=index)

def test_no_lookahead_all_plugins_with_partial_final_day():
    ix=pd.date_range("2024-01-01",periods=100,freq="1h",tz="UTC")
    c=100+np.sin(np.arange(len(ix))/4)*4+np.arange(len(ix))*.03
    d=frame(ix,c)
    for name in IDS:
        m=load(name); check_no_lookahead(m,d)

def test_lower_high_setup_and_first_touch():
    ix=pd.date_range("2024-01-01",periods=6*24,freq="1h",tz="UTC")
    highs=np.repeat([112,110,108,106,104,102],24).astype(float); lows=highs-2; closes=highs-1
    opens=closes.copy(); highs[5*24+1]=104.5
    d=frame(ix,closes,highs,lows,opens); s=load(IDS[0]).signals(d)
    assert s.long_entry.iloc[5*24+1]
    assert not s.long_entry.iloc[5*24+2]
    assert s.long_exit.iloc[6*24-1]

def test_larry_williams_previous_day_trigger():
    ix=pd.date_range("2024-01-01",periods=48,freq="1h",tz="UTC")
    hi=np.r_[np.full(24,110.),np.full(24,108.)]; lo=np.r_[np.full(24,100.),np.full(24,98.)]
    op=np.r_[np.full(24,105.),np.full(24,104.)]; cl=np.r_[np.full(24,105.),np.full(24,105.)]
    hi[25]=107.1
    s=load(IDS[2]).signals(frame(ix,cl,hi,lo,op),k=.5)
    # 104 + .5*(110-100) = 109; no trigger at 107.1.
    assert not s.long_entry.iloc[25]
    hi[26]=109.1
    s=load(IDS[2]).signals(frame(ix,cl,hi,lo,op),k=.5)
    assert s.long_entry.iloc[26]

def test_dual_thrust_uses_completed_window_range():
    ix=pd.date_range("2024-01-01",periods=5*24,freq="1h",tz="UTC")
    highs=np.repeat([110,112,111,114,116],24); lows=np.repeat([100,101,99,103,105],24)
    opens=np.repeat([105,106,104,108,110],24); closes=np.repeat([106,107,105,109,111],24)
    closes=closes.astype(float); closes[4*24]=120
    s=load(IDS[3]).signals(frame(ix,closes,highs,lows,opens),n_up=2,n_down=2,up_coeff=.5,down_coeff=.5,atr_len=2)
    # Prior two days: max(H)-min(C)=112-105=7; max(C)-min(L)=107-99=8.
    assert s.long_entry.iloc[4*24]

def test_pullback_rule_conditions_match_hand_formula():
    from common.indicators import ema,atr
    ix=pd.date_range("2024-01-01",periods=240,freq="1h",tz="UTC")
    c=100+np.arange(240)*.2; op=c-.1; hi=c+.4; lo=c-.4
    # Hand-check returned signal is exactly conjunction of extracted trend/pullback gates.
    d=frame(ix,c,hi,lo,op); m=load(IDS[5]); s=m.signals(d,cooldown=0)
    ef=ema(c,21); em=ema(c,50); es=ema(c,200)
    manual=(c>es)&(ef>em)&(lo<=ef)&(c>ef)&(c>op)&(m._rsi(c,14)>50)
    manual &= np.isfinite((c-(lo-.5*atr(hi,lo,c,14)))/c)&((c-(lo-.5*atr(hi,lo,c,14)))/c>0)
    np.testing.assert_array_equal(s.long_entry.to_numpy(),manual)
