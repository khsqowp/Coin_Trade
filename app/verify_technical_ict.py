"""Research checks: prefix invariance and synthetic execution accounting."""
import importlib
import numpy as np
import pandas as pd
from app.crypto_technical_ict_research import load_data
from app.technical_signal_common import NAMES
from app.technical_portfolio_engine import simulate_portfolio


def fixture():
    dates=pd.date_range('2020-01-01',periods=5,tz='UTC')
    df=pd.DataFrame(dict(Open=[100]*5,High=[100]*5,Low=[100]*5,Close=[100]*5,
                         SIGNAL=[True,False,False,False,False],VOL_RATIO=[1]*5,
                         ATR14=[5]*5,STOP_LEVEL=[90]*5),index=dates)
    return df


def run():
    frames,_,_=load_data(); checks=0
    for name in NAMES:
        core=importlib.import_module(f'app.{name}_signal_core')
        for symbol in ['BTC','ETH','SOL']:
            frame=frames[symbol]; full=core.find_signals(frame)
            # Prefix boundaries cover warmup, recent history, and actual signal dates.
            boundaries={250,500,len(frame)-1,len(frame)//2}
            boundaries.update(int(i)+1 for i in np.flatnonzero(full.SIGNAL.to_numpy())[::max(1,int(full.SIGNAL.sum())//10)])
            for n in sorted(boundaries):
                if n<201: continue
                prefix=core.find_signals(frame.iloc[:n])
                pd.testing.assert_frame_equal(full[['SIGNAL','VOL_RATIO','STOP_LEVEL','ATR14']].iloc[:n],
                                              prefix[['SIGNAL','VOL_RATIO','STOP_LEVEL','ATR14']])
                checks+=1
        print(f'{name}: prefix invariance PASS',flush=True)
    df=fixture(); m=simulate_portfolio({'X':df},top_k=1,hold_days=1)
    assert abs(m['final']-(1-.0004)**2)<1e-12 and m['trades']==1
    # Entry-bar stop wins if both stop and target occur.
    df.loc[df.index[1],['High','Low']]=[130,80]
    m=simulate_portfolio({'X':df},top_k=1,hold_days=1,stop='pct10',tp='pct20')
    assert abs(m['final']-.9*(1-.0004)**2)<1e-12 and m['stopped']==1
    # Overnight gap exits at open, not stale stop.
    df=fixture(); df.loc[df.index[2],['Open','High','Low','Close']]=[70,75,65,70]
    m=simulate_portfolio({'X':df},top_k=1,hold_days=3,stop='pct10')
    assert abs(m['final']-.7*(1-.0004)**2)<1e-12
    # Same-open sizing cannot depend on today's close of an incumbent position.
    first=fixture(); first['Close']=100.; second=fixture(); second['SIGNAL']=[False,True,False,False,False]
    base=simulate_portfolio({'X':first,'Y':second},top_k=2,hold_days=10)
    first.loc[first.index[2],'Close']=10000
    changed=simulate_portfolio({'X':first,'Y':second},top_k=2,hold_days=10)
    assert base['final']==changed['final']
    # All mode must permit >8 positions without ranking or leverage.
    all_frames={str(k):fixture() for k in range(12)}
    m=simulate_portfolio(all_frames,selection='all',hold_days=1)
    assert m['trades']==12 and abs(m['final']-(1-.0004)**2)<1e-12
    # Confirmation requires day s+1 to finish, then enters at s+2 open.
    df=fixture()
    m=simulate_portfolio({'X':df},top_k=1,timing='confirm_open',hold_days=1)
    assert m['trades']==0
    df.loc[df.index[1],'Close']=110
    df.loc[df.index[2],'Open']=120
    m=simulate_portfolio({'X':df},top_k=1,timing='confirm_open',hold_days=1)
    assert abs(m['final']-(100/120)*(1-.0004)**2)<1e-12
    # FVG can be tapped only after the three-candle gap is confirmed.
    dates=pd.date_range('2020-01-01',periods=20,tz='UTC')
    frame=pd.DataFrame(dict(Open=100.,High=101.,Low=99.,Close=100.,Volume=1000.),index=dates)
    frame.loc[dates[14],['Open','High','Low','Close']]=[106,108,105,107]
    frame.loc[dates[15],['Open','High','Low','Close']]=[106,108,103,107]
    from app.fvg_signal_core import find_signals
    signals=find_signals(frame)
    assert not signals.SIGNAL.iloc[14] and signals.SIGNAL.iloc[15]
    assert signals.STOP_LEVEL.iloc[15]==101
    print(f'PASS: {checks} prefix checks + 7 behavioral/accounting checks',flush=True)


if __name__=='__main__':
    run()
