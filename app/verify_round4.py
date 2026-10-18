"""Independent artifact arithmetic, fee fixture, and rendered-report audit."""
import json
import subprocess
import numpy as np
import pandas as pd
from app.crypto_round4_robustness import PATH, ROOT, ledger_run, metrics
from app.render_round4_report import label, row


def run():
    d=json.loads(PATH.read_text());doc=(ROOT/'docs/전략-백테스트-종합.md').read_text()
    prior=json.loads((ROOT/'docs/round3-results-2026-10-06.json').read_text())
    assert d['manifest']==prior['manifest'] and len(d['manifest'])==45
    assert d['verdict']=='기각' and sum(d['flags'].values())==d['unstable_count']==4
    assert '**기각**:' in doc.split('## 16.')[1]
    assert len(d['winners'])==5 and len(d['sensitivity'])==6
    for w,old in zip(d['winners'],prior['winners']):
        assert w['config']==old['config'] and w['name']==old['name']
        records=w['trades'];equity=np.array([r['equity'] for r in w['daily_equity']])
        assert len(records)==w['full']['trades']
        assert [t['id'] for t in records]==list(range(len(records)))
        assert len(equity)==2585 and equity[0]==1
        np.testing.assert_allclose(sum(t['pnl'] for t in records),equity[-1]-1,rtol=1e-10)
        for t in records:
            assert t['entry']<=t['exit']<=t['entry']+20
            np.testing.assert_allclose(t['pnl'],t['proceeds']-t['cost'])
        ranked=sorted(records,key=lambda t:(-t['pnl'],t['id']))
        for n in [10,20]:
            total=sum(t['pnl'] for t in ranked[:n]);positive=sum(max(0,t['pnl']) for t in records)
            np.testing.assert_allclose(w['concentration'][str(n)]['positive_pct'],100*total/positive)
            np.testing.assert_allclose(w['concentration'][str(n)]['net_pct'],100*total/(equity[-1]-1))
        assert len(w['periods'])==8
        for r in w['periods']:
            m=r['metrics'];assert m['trades']>0 and -100<m['cagr']<1000 and 0<=m['mdd']<=100
            assert pd.Timestamp(m['start'])==pd.Timestamp(r['start'],tz='UTC')
            assert pd.Timestamp(m['end'])==pd.Timestamp(r['end'],tz='UTC')
            assert row(label(w)+f" / {r['start']}~{r['end']}",m) in doc
        if 'flapping' in w:
            events=w['full']['breaker_log'];resumes=[(j,e) for j,e in enumerate(events) if e['kind']=='resume']
            assert len(resumes)==w['flapping']['resumes']
            for n in [1,3,5]:
                count=0
                for j,e in resumes:
                    following=next((p for p in events[j+1:] if p['kind']=='pause'),None)
                    count+=int(following is not None and following['index']-e['index']<=n)
                assert count==w['flapping']['within'][str(n)]['count']
    main=d['winners'][2]
    for r in main['leave_top_out']:
        assert len(r['removed_ids'])==r['n'] and len(set(r['removed_ids']))==r['n']
        curve=np.array([p['equity'] for p in r['daily_equity']])
        dates=[pd.Timestamp(p['date']) for p in r['daily_equity']]
        m=metrics(curve,dates,642-r['n'])
        for k in m:
            if isinstance(m[k],(float,np.floating)):
                np.testing.assert_allclose(m[k],r['metrics'][k])
            else:
                assert m[k]==r['metrics'][k]
        assert row(str(r['n']),r['metrics']) in doc
        original=np.array([p['equity'] for p in main['daily_equity']])
        normalized=np.cumprod(1+np.diff(curve,prepend=1.)/np.r_[1.,original[:-1]])
        np.testing.assert_allclose(normalized,[p['equity'] for p in r['normalized_daily_equity']])
        independent=metrics(normalized,dates,642-r['n'])
        for k in ['cagr','mdd','sharpe']:
            np.testing.assert_allclose(independent[k],r['normalized_metrics'][k])
        assert row(str(r['n']),r['normalized_metrics']) in doc

    sy=main['symbols'];assert len(sy['rows'])==45 and sum(s['trades'] for s in sy['rows'])==642
    np.testing.assert_allclose(sum(s['pnl'] for s in sy['rows']),main['full']['final']-1)
    assert sy['top5']==[s['symbol'] for s in sy['rows'][:5]]
    assert row('손익 상위5 제외 40종목',sy['excluded_metrics']) in doc
    # Known single trade: buy at 100, close at 110, fee on both legs.
    index=pd.date_range('2020-01-01',periods=5,tz='UTC')
    fixture=pd.DataFrame(dict(Open=100.,High=110.,Low=100.,Close=110.,SIGNAL=False,
                              VOL_RATIO=1.,ATR14=1.,STOP_LEVEL=0.),index=index)
    fixture.loc[index[0],'SIGNAL']=True
    result,records,contributions,dates,curve=ledger_run({'X':fixture},dict(top_k=1,hold_days=2))
    assert len(records)==1 and records[0]['entry']==1 and records[0]['exit']==3
    np.testing.assert_allclose(result['final'],1.1*(1-.0004)**2)
    np.testing.assert_allclose(curve-contributions[0],np.ones(5))
    for name in ['round1','round2','round3']:
        log=(ROOT/f'docs/round4-{name}-regression-2026-10-07.txt').read_text()
        assert 'PASS:' in log and 'Traceback' not in log
    assert subprocess.check_output(['git','diff','--','README.md'],cwd=ROOT)==b''
    print('PASS: fixed parameters/manifest; 5 trade ledgers; 40 exact period boundaries and document rows; independent concentration/flapping/symbol arithmetic; 4 leave-out curves; two-sided fee and all-trades-removed cash fixture; 3 regression logs; README unchanged')


if __name__=='__main__':
    run()
