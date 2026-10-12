"""Independent Round 5 artifact arithmetic and causal-composition checks."""
import json
import subprocess

import numpy as np
import pandas as pd

from app.crypto_bucket_ensemble_research import PATH, ROOT, NAMES, combine, volume_prep, jumps
from app.crypto_round3_research import prep, btc_trend
from app.crypto_round4_robustness import ledger_run, metrics
from app.crypto_technical_ict_research import load_data
from app.render_round4_report import row
from app.technical_portfolio_engine import simulate_portfolio
from app.verify_technical_ict import fixture


def check_metrics(values, dates, count, actual):
    expected = metrics(values, dates, count)
    for k, v in expected.items():
        if isinstance(v, (float, np.floating)):
            np.testing.assert_allclose(v, actual[k], rtol=1e-10, atol=1e-9)
        else:
            assert v == actual[k], (k,v,actual[k])


def run():
    d = json.loads(PATH.read_text())
    old = json.loads((ROOT / 'docs/round4-results-2026-10-07.json').read_text())
    doc = (ROOT / 'docs/전략-백테스트-종합.md').read_text()
    assert d['periods'] == old['periods'] and d['criteria'] == old['criteria']
    assert d['manifest'] == old['manifest'] and len(d['manifest']) == 45
    assert d['sensitivity_unique_runs'] == 9
    frames, manifest, _ = load_data()
    assert manifest == d['manifest']
    rows = [d['champion']] + d['ensembles']
    for r in rows:
        records = r['trades']
        dates = [pd.Timestamp(p['date']) for p in r['daily_equity']]
        values = np.array([p['equity'] for p in r['daily_equity']])
        assert len(values) == 2585 and values[0] == 1
        assert pd.Index(dates).is_unique and pd.Index(dates).is_monotonic_increasing
        assert len(records) == r['full']['trades']
        assert [t['id'] for t in records] == list(range(len(records)))
        check_metrics(values, dates, len(records), r['full'])
        np.testing.assert_allclose(sum(t['pnl'] for t in records),values[-1]-1,atol=1e-9)
        contributions = []
        for t in records:
            np.testing.assert_allclose(t['pnl'],t['proceeds']-t['cost'],atol=1e-10)
            assert t['entry'] < t['exit'] <= t['entry'] + 20
            close = frames[t['symbol']].Close.reindex(dates).ffill().to_numpy()
            part = np.zeros(len(dates))
            part[t['entry']:t['exit']] = t['qty']*close[t['entry']:t['exit']] - t['cost']
            part[t['exit']:] = t['pnl']
            contributions.append(part)
        contributions = np.array(contributions)
        np.testing.assert_allclose(1+contributions.sum(axis=0),values,atol=1e-9)
        ranked = sorted(records,key=lambda t:(-t['pnl'],t['id']))
        positive = sum(max(0,t['pnl']) for t in records)
        for n in [10,20]:
            pnl = sum(t['pnl'] for t in ranked[:n])
            np.testing.assert_allclose(r['concentration'][str(n)]['net_pct'],pnl/(values[-1]-1)*100)
            np.testing.assert_allclose(r['concentration'][str(n)]['positive_pct'],pnl/positive*100)
        for p in r['leave_top_out']:
            assert p['removed_ids'] == [t['id'] for t in ranked[:p['n']]]
            retained = 1+np.delete(contributions,p['removed_ids'],axis=0).sum(axis=0)
            np.testing.assert_allclose(retained,[a['equity'] for a in p['daily_equity']],atol=1e-9)
            check_metrics(retained,dates,len(records)-p['n'],p['metrics'])
            normalized = np.cumprod(1+np.diff(retained,prepend=1.)/np.r_[1.,values[:-1]])
            np.testing.assert_allclose(normalized,[a['equity'] for a in p['normalized_daily_equity']],atol=1e-9)
            check_metrics(normalized,dates,len(records)-p['n'],p['normalized_metrics'])
            assert row(str(p['n']),p['metrics']) in doc
            assert row(str(p['n']),p['normalized_metrics']) in doc
        assert [(p['start'],p['end']) for p in r['periods']] == [tuple(p) for p in old['periods']]
        for p in r['periods']:
            assert p['initial_equity'] == 1 and all(v==1 for v in p['bucket_initial_equity'])
            assert row(f"{p['start']}~{p['end']}",p['metrics']) in doc
            m = p['metrics']
            assert m['trades']>0 and -100<m['cagr']<1000 and 0<=m['mdd']<=100
            assert np.isfinite([m[k] for k in ['cagr','mdd','sharpe']]).all()
        sy = r['symbols']; assert len(sy['rows']) == 45
        assert sum(t['trades'] for t in sy['rows']) == len(records)
        np.testing.assert_allclose(sum(t['pnl'] for t in sy['rows']),values[-1]-1)
        assert sy['top5'] == [t['symbol'] for t in sy['rows'][:5]]
        np.testing.assert_allclose(sy['net_pct'],sum(t['pnl'] for t in sy['rows'][:5])/(values[-1]-1)*100)
        if sy['net_pct'] >= 50:
            assert row('손익 상위5 제외 40종목',sy['excluded_metrics']) in doc
        series = list(r['sensitivity'].values()) if 'n' not in r else [r['sensitivity']]
        for s in series:
            assert s['jumps'] == jumps(s['points'])
            for p in s['points']:
                assert row(f"{p['value']:.6g}",p['metrics']) in doc
        flags = dict(periods=any(p['metrics']['sharpe']<.5 or p['metrics']['cagr']<0 for p in r['periods']),
                     concentration=r['concentration']['10']['net_pct']>=50,
                     sensitivity=any(j['unstable'] for s in series for j in s['jumps']),
                     symbols=sy['net_pct']>=50)
        assert flags == r['flags'] and sum(flags.values()) == r['unstable_count']
        assert r['verdict'] == '기각'
    prepared = {name:prep(name,frames) for name in NAMES}
    full_runs = [ledger_run(prepared[name],{}) for name in NAMES]
    for n in [2,3]:
        full = combine(full_runs[:n],[1/n]*n)
        np.testing.assert_allclose(full[4],[p['equity'] for p in d['ensembles'][n-2]['daily_equity']])
        expected_corr = pd.DataFrame({name:pd.Series(run[4],index=run[3]).pct_change() for name,run in zip(NAMES,full_runs)}).dropna().corr()
        for a in NAMES:
            for b in NAMES:
                np.testing.assert_allclose(d['correlation'][a][b],expected_corr.loc[a,b])
        for cutoff in ['2022-12-31','2024-06-30']:
            limited = {name:{s:df.loc[:cutoff] for s,df in prepared[name].items() if len(df.loc[:cutoff])} for name in NAMES[:n]}
            short = combine([ledger_run(limited[name],{}) for name in NAMES[:n]],[1/n]*n)
            np.testing.assert_allclose(short[4][:-1], full[4][:len(short[4])-1],rtol=0,atol=1e-10)
            for bucket, name in enumerate(NAMES[:n]):
                short_engine = simulate_portfolio(limited[name],return_trace=True)
                assert short_engine['trace'][:-1] == full_runs[bucket][0]['trace'][:len(short_engine['trace'])-1]
        mutated = {name:{s:df.copy() for s,df in prepared[name].items()} for name in NAMES[:n]}
        cutoff = pd.Timestamp('2024-06-30',tz='UTC')
        for bucket in mutated.values():
            for df in bucket.values():
                df.loc[df.index>cutoff,['Open','High','Low','Close']] *= 10
        changed = combine([ledger_run(mutated[name],{}) for name in NAMES[:n]],[1/n]*n)
        end = full[3].index(cutoff)+1
        np.testing.assert_allclose(changed[4][:end],full[4][:end],rtol=0,atol=1e-10)
    for cutoff in ['2022-12-31','2024-06-30']:
        limited = {s:df.loc[:cutoff] for s,df in frames.items() if len(df.loc[:cutoff])}
        for multiple,cap in [(v,5.) for v in [2.5,2.75,3.,3.25,3.5]] + [(3.,c) for c in [4.,4.5,5.5,6.]]:
            full = volume_prep(frames,multiple,cap); short = volume_prep(limited,multiple,cap)
            for s in short:
                pd.testing.assert_frame_equal(full[s].loc[:cutoff],short[s])
        trend = pd.Series(btc_trend(frames['BTC'])).rolling(3,min_periods=3).sum().eq(3)
        short_trend = pd.Series(btc_trend(limited['BTC'])).rolling(3,min_periods=3).sum().eq(3)
        pd.testing.assert_series_equal(trend.loc[:cutoff],short_trend)
    # Known two-bucket accounting, sum versus daily rebalance, calendar validation.
    a = fixture(); b = fixture(); b.loc[b.index[2]:,'Close'] = 120.
    ra = ledger_run({'X':a},dict(top_k=1,hold_days=2))
    rb = ledger_run({'Y':b},dict(top_k=1,hold_days=2))
    joined = combine([ra,rb],[.6,.4])
    np.testing.assert_allclose(joined[4],.6*ra[4]+.4*rb[4])
    np.testing.assert_allclose(ra[0]['final'], (1-.0004)**2)
    np.testing.assert_allclose(rb[0]['final'], 1.2*(1-.0004)**2)
    np.testing.assert_allclose(joined[0]['final'], 1.08*(1-.0004)**2)
    assert joined[4][0] == 1 and joined[0]['trades'] == 2
    invalid = list(rb); invalid[3] = list(reversed(rb[3]))
    for runs,weights in [([ra,tuple(invalid)],[.5,.5]),([ra,rb],[.5,.6]),([ra,rb],[1.,0.])]:
        try:
            combine(runs,weights)
        except ValueError:
            pass
        else:
            raise AssertionError('invalid combination accepted')
    cb = d['btc_confirmation']; log = cb['full']['breaker_log']
    calendar = full_runs[0][3]
    trend = pd.Series(btc_trend(frames['BTC'])).rolling(3,min_periods=3).sum().eq(3)
    config = dict(dd_trigger=.25, resume_mode='btc_sma50', btc_resume=trend.to_dict())
    live = simulate_portfolio(prepared['heikin_ashi'], return_trace=True, **config)
    assert live['breaker_log'] == cb['full']['breaker_log']
    for k in ['cagr','mdd','sharpe','trades']:
        np.testing.assert_allclose(live[k], cb['full'][k])
    for cutoff in ['2022-12-31','2024-06-30']:
        short = {s:df.loc[:cutoff] for s,df in prepared['heikin_ashi'].items() if len(df.loc[:cutoff])}
        prefix = simulate_portfolio(short, return_trace=True, **config)
        assert prefix['trace'][:-1] == live['trace'][:len(prefix['trace'])-1]
    paused = None; gaps=[]
    for i,e in enumerate(log):
        if e['kind']=='pause':
            assert paused is None; paused=e['index']
        else:
            assert paused is not None and trend.loc[calendar[e['index']-1]]
            assert not any(trend.loc[calendar[j-1]] for j in range(paused+1,e['index']))
            following = next((p for p in log[i+1:] if p['kind']=='pause'),None)
            gaps.append(None if following is None else following['index']-e['index'])
            paused=None
    for n in [1,3,5]:
        count = sum(g is not None and g<=n for g in gaps)
        assert count == cb['flapping']['within'][str(n)]['count']
        np.testing.assert_allclose(100*count/len(gaps),cb['flapping']['within'][str(n)]['pct'])
    for name in ['round1','round2','round3','round4']:
        log = (ROOT / f'docs/round5-{name}-regression-2026-10-07.txt').read_text()
        assert 'PASS:' in log and 'Traceback' not in log
    assert subprocess.check_output(['git','diff','--','README.md'],cwd=ROOT) == b''
    assert doc.count('## 17.') == 1
    print('PASS: 3 trade ledgers and daily/terminal cash reconciliation; 24 independent reset windows; 12 absolute/relative leave-out curves; 9 signal variants; correlation and sensitivity arithmetic; real bucket/ensemble prefixes and future mutation; calendar/weight/fee fixture; three-day BTC prefix and 410 restart audits; Round 1-4 regression logs; artifact/document tables; README unchanged')


if __name__ == '__main__':
    run()
