"""Causal intersection, online peak, suspension/recovery and full artifact checks."""
import importlib
import json
import numpy as np
import pandas as pd
from app.crypto_hybrid_drawdown_research import NAMES, PATH, signals, target
from app.crypto_technical_ict_research import load_data
from app.technical_portfolio_engine import simulate_portfolio
from app.verify_technical_ict import fixture


def run():
    frames,_,_=load_data(); checks=0
    for name in NAMES[3:]:
        core=importlib.import_module(f'app.{name}_signal_core')
        for symbol,frame in frames.items():
            full=core.find_signals(frame)
            parent=signals(name.replace('_volume_spike',''),{symbol:frame})[symbol]
            volume=signals('volume_spike',{symbol:frame})[symbol]
            pd.testing.assert_series_equal(full.SIGNAL,parent.SIGNAL & volume.SIGNAL)
            boundaries={201,250,len(frame)//2,len(frame)-1}
            boundaries.update(int(i)+1 for i in np.flatnonzero(full.SIGNAL.to_numpy())[::max(1,int(full.SIGNAL.sum())//5)])
            for n in sorted(boundaries):
                if n<201: continue
                prefix=core.find_signals(frame.iloc[:n])
                pd.testing.assert_frame_equal(full[['SIGNAL','VOL_RATIO','STOP_LEVEL','ATR14']].iloc[:n],prefix[['SIGNAL','VOL_RATIO','STOP_LEVEL','ATR14']])
                checks+=1
        print(name,'all 45 symbols intersection/prefix PASS',flush=True)
    # Account drops 20% at close: no further entries; incumbent later recovers to -5%.
    x=fixture().reindex(pd.date_range('2020-01-01',periods=10,tz='UTC')).ffill()
    x['SIGNAL']=False; x.iloc[0,x.columns.get_loc('SIGNAL')]=True
    x[['Open','High','Low','Close']]=100.
    x.loc[x.index[2:5],['Open','High','Low','Close']]=80.
    x.loc[x.index[5:],['Open','High','Low','Close']]=95.
    y=x.copy(); y[['Open','High','Low','Close']]=100.; y['SIGNAL']=True
    full=simulate_portfolio({'X':x,'Y':y},top_k=1,hold_days=6,fee_pct_one_way=0,dd_trigger=.15,return_trace=True)
    t=full['trace']
    assert t[2]['paused'] and t[3]['entry_paused'] and not t[5]['entry_paused']
    assert full['breaker_events']==1 and full['breaker_resumes']==1 and full['trades']==2
    # Truncation's final force sale cannot affect prior decisions; exclude terminal bar.
    for n in range(3,len(x)):
        short=simulate_portfolio({'X':x.iloc[:n],'Y':y.iloc[:n]},top_k=1,hold_days=6,fee_pct_one_way=0,dd_trigger=.15,return_trace=True)
        assert short['trace'][:-1]==t[:n-1]
    future=x.copy(); future.loc[future.index[7:],['Open','High','Low','Close']]=10000.
    changed=simulate_portfolio({'X':future,'Y':y},top_k=1,hold_days=6,fee_pct_one_way=0,dd_trigger=.15,return_trace=True)
    assert changed['trace'][:7]==t[:7]
    # A loss at opening must block that opening's candidates, not wait until close.
    gap=x.copy(); gap.loc[gap.index[2],'Close']=100.
    m=simulate_portfolio({'X':gap,'Y':y},top_k=1,hold_days=6,fee_pct_one_way=0,dd_trigger=.15,return_trace=True)
    assert m['trace'][2]['entry_paused']
    # With no remaining exposure recovery can never occur: verify permanent cash lock.
    m=simulate_portfolio({'X':x,'Y':y},top_k=1,hold_days=2,fee_pct_one_way=0,dd_trigger=.15,return_trace=True)
    assert m['trades']==1 and m['breaker_resumes']==0 and m['breaker_paused_final']
    peak=1.
    for r in t:
        peak=max(peak,r['opening'],r['closing'])
        assert r['peak']==peak
    # All live backtest prefixes preserve nonterminal online traces.
    prepped=signals('volume_spike',frames)
    for trigger in [.15,.20,.25,.30]:
        full=simulate_portfolio(prepped,dd_trigger=trigger,return_trace=True)
        for n in [250,500,1500]:
            cutoff=pd.Timestamp(full['trace'][n-1]['date'])
            short={s:df.loc[:cutoff] for s,df in prepped.items() if len(df.loc[:cutoff])}
            prefix=simulate_portfolio(short,dd_trigger=trigger,return_trace=True)
            assert prefix['trace'][:-1]==full['trace'][:n-1]
    result=json.loads(PATH.read_text())
    assert len(result['baselines'])==5 and len(result['sweep'])==20
    period={(r['metrics']['start'],r['metrics']['end']) for r in result['baselines']+result['sweep']}
    assert len(period)==1
    for r in result['baselines']+result['sweep']+result['supplemental_baselines']:
        m=r['metrics']; assert m['trades']>0 and -100<m['cagr']<1000 and 0<=m['mdd']<=100
        assert all(np.isfinite(m[k]) for k in ['cagr','mdd','sharpe'])
        assert r['target']==target(m)
    print(f'PASS: {checks} hybrid prefix checks; 90 intersection checks; synthetic suspension/recovery/gap/permanent lock; 12 real breaker prefixes; 26 result sanity/period/target checks',flush=True)


if __name__=='__main__':
    run()
