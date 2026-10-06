"""Prefix invariance, restart event audit and causal inverse-vol allocations."""
import importlib
import json
import numpy as np
import pandas as pd
from app.crypto_round3_research import PATH, NAMES, prep, target, btc_trend
from app.crypto_technical_ict_research import load_data
from app.technical_portfolio_engine import simulate_portfolio


def run():
    frames,manifest,_=load_data(); checks=0
    for name in ['heikin_ashi_volume_spike_loose','frvp_volume_spike_loose']:
        core=importlib.import_module(f'app.{name}_signal_core')
        for symbol,frame in frames.items():
            full=core.find_signals(frame)
            technical=prep(name.split('_volume')[0],{symbol:frame})[symbol].SIGNAL.to_numpy()
            volume=prep('volume_spike',{symbol:frame})[symbol].SIGNAL.to_numpy()
            expected=np.array([(technical[i] and volume[max(0,i-3):i+1].any()) or
                               (volume[i] and technical[max(0,i-3):i+1].any()) for i in range(len(frame))])
            assert np.array_equal(full.SIGNAL.to_numpy(),expected)
            points={201,250,len(frame)//2,len(frame)-1}
            points.update(int(i)+1 for i in np.flatnonzero(expected)[::max(1,int(expected.sum())//5)])
            for n in points:
                if n<201: continue
                prefix=core.find_signals(frame.iloc[:n])
                pd.testing.assert_frame_equal(full.iloc[:n],prefix); checks+=1
        print(name,'45-symbol pair confirmation and prefix PASS',flush=True)
    # Explicit later-date pairing for both signal orders, inclusive distance three.
    # This verifies the Boolean window independently of indicator implementations.
    for t,v in [(2,5),(5,2),(2,6),(4,4)]:
        a=pd.Series(False,index=range(10));b=a.copy();a[t]=True;b[v]=True
        result=(a & b.rolling(4,min_periods=1).max().astype(bool)) | (b & a.rolling(4,min_periods=1).max().astype(bool))
        assert list(np.flatnonzero(result))==([max(t,v)] if abs(t-v)<=3 else [])
    btc=frames['BTC'];trend=btc_trend(btc)
    for n in [100,250,500,1500]:
        assert btc_trend(btc.iloc[:n])=={k:trend[k] for k in btc.index[:n]}
    # Cash cannot recover, but both new modes must resume and permit entries.
    index=pd.date_range('2020-01-01',periods=100,tz='UTC')
    x=pd.DataFrame(dict(Open=100.,High=100.,Low=100.,Close=100.,SIGNAL=True,
                        VOL_RATIO=1.,ATR14=5.,STOP_LEVEL=90.),index=index)
    x.loc[index[3:],['Open','High','Low','Close']]=70.
    for mode in ['cooldown','btc_sma50']:
        config=dict(top_k=1,hold_days=2,fee_pct_one_way=0,dd_trigger=.15,resume_mode=mode,
                    cooldown_days=20,btc_resume={d:i>=25 for i,d in enumerate(index)},return_trace=True)
        m=simulate_portfolio({'X':x},**config)
        assert m['breaker_resumes']>0 and m['trades']>1
        first=next(e for e in m['breaker_log'] if e['kind']=='resume')
        assert first['index']==(23 if mode=='cooldown' else 26)
        assert not m['trace'][first['index']]['entry_paused']
        for n in [30,60,90]:
            short=simulate_portfolio({'X':x.iloc[:n]},**config)
            assert short['trace'][:-1]==m['trace'][:n-1]
    # Actual portfolio prefixes and future mutations cover all strategies/modes.
    for name in NAMES:
        prepped=prep(name,frames)
        for config in [dict(dd_trigger=.20,resume_mode='cooldown',cooldown_days=20),
                       dict(dd_trigger=.20,resume_mode='btc_sma50',btc_resume=trend),
                       dict(sizing='inverse_vol',target_vol=.40,weight_cap=.25)]:
            full=simulate_portfolio(prepped,return_trace=True,**config)
            for n in [250,800,1500]:
                cutoff=pd.Timestamp(full['trace'][n-1]['date'])
                short={s:df.loc[:cutoff] for s,df in prepped.items() if len(df.loc[:cutoff])}
                small=simulate_portfolio(short,return_trace=True,**config)
                assert small['trace'][:-1]==full['trace'][:n-1]
                assert [a for a in small['allocations'] if pd.Timestamp(a['date'])<cutoff]==[a for a in full['allocations'] if pd.Timestamp(a['date'])<cutoff]
                checks+=1
            changed={s:df.copy() for s,df in prepped.items()}
            cutoff=pd.Timestamp(full['trace'][799]['date'])
            for df in changed.values():
                df.loc[df.index>cutoff,['Open','High','Low','Close']]*=10
            new=simulate_portfolio(changed,return_trace=True,**config)
            assert new['trace'][:800]==full['trace'][:800]
            if config.get('sizing'):
                for a in full['allocations']:
                    assert 0<a['weight']<=.25+1e-12 and pd.Timestamp(a['known_through'])<pd.Timestamp(a['date'])
    # Independent sizing fixture: simultaneous entries, inverse sigma ratio,
    # 25% cap, positive-correlation risk <= target, no leverage.
    index=pd.date_range('2020-01-01',periods=50,tz='UTC')
    synthetic={}
    for symbol,scale in [('A',1),('B',2),('C',3),('D',4)]:
        prices=100*np.cumprod(1+scale*np.tile([.01,-.01],25))
        df=pd.DataFrame({f:prices for f in ['Open','High','Low','Close']},index=index)
        df['SIGNAL']=False;df.loc[index[24],'SIGNAL']=True
        df['VOL_RATIO']=1.;df['ATR14']=1.;df['STOP_LEVEL']=0.
        synthetic[symbol]=df
    m=simulate_portfolio(synthetic,top_k=4,sizing='inverse_vol',target_vol=.40,return_trace=True)
    alloc={a['symbol']:a['weight'] for a in m['allocations']}
    assert len(alloc)==4 and sum(alloc.values())<=1 and max(alloc.values())<=.25
    assert abs(alloc['B']/alloc['C']-1.5)<1e-10
    risk=sum(alloc[s]*df.Close.pct_change().iloc[5:25].std()*np.sqrt(365) for s,df in synthetic.items())
    assert risk<=.40+1e-12
    result=json.loads(PATH.read_text());assert manifest==result['manifest']
    assert [len(result[k]) for k in ['baselines','breaker','volatility','loose']]==[3,48,3,2]
    period=set()
    for r in result['baselines']+result['breaker']+result['volatility']+result['loose']:
        m=r['metrics'];assert m['trades']>0 and -100<m['cagr']<1000 and 0<=m['mdd']<=100
        assert all(np.isfinite(m[k]) for k in ['cagr','mdd','sharpe','final'])
        assert r['target']==target(m);period.add((m['start'],m['end']))
    assert len(period)==1
    dates=sorted(set().union(*(f.index for f in frames.values())))
    for r in result['breaker']:
        m=r['metrics'];paused=None;config=r['config']
        assert m['breaker_resumes']>0
        for e in m['breaker_log']:
            if e['kind']=='pause':
                assert paused is None;paused=e['index']
            else:
                assert paused is not None
                if config['resume_mode']=='cooldown': assert e['index']-paused==config['cooldown_days']
                else:
                    assert trend.get(dates[e['index']-1],False)
                    assert not any(trend.get(dates[j-1],False) for j in range(paused+1,e['index']))
                paused=None
        assert (paused is not None)==m['breaker_paused_final']
        if paused is not None:
            if config['resume_mode']=='cooldown':
                assert m['paused_age_final']<config['cooldown_days'];reason='종료 전 쿨다운 미경과'
            else: reason='종료까지 BTC 추세 재개조건 미충족'
            print('FINAL PAUSED:',r['name'],config,'age',m['paused_age_final'],reason,flush=True)
    print(f'PASS: {checks} prefix checks; 90 independent pair checks; synthetic cash restart/exact cooldown/BTC lag; future mutations; sizing inverse ratio/cap/risk; 56 result sanity and 48 restart event audits',flush=True)


if __name__=='__main__':
    run()
