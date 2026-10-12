"""Independent arithmetic, source reuse and exact cap-boundary fixture."""
import json
from collections import Counter

import numpy as np
import pandas as pd

from app.crypto_round6_research import ROOT, PATH
from app.technical_portfolio_engine import simulate_portfolio


def run():
    d = json.loads(PATH.read_text())
    old = json.loads((ROOT / 'docs/round4-results-2026-10-07.json').read_text())
    champion = json.loads((ROOT / 'docs/round5-champion-results-2026-10-07.json').read_text())
    doc = (ROOT / 'docs/전략-백테스트-종합.md').read_text()
    for row, source in zip(d['strategies'], [champion['champion']] + old['winners']):
        for p, original, b in zip(row['periods'], source['periods'],d['btc']):
            assert p['metrics'] == original['metrics']
            assert p['alpha_pass'] == (p['metrics']['cagr'] > b['cagr'])
            np.testing.assert_allclose(p['alpha'],p['metrics']['cagr']-b['cagr'])
        assert row['alpha_failures'] == sum(not p['alpha_pass'] for p in row['periods'])
    for b in d['btc']:
        expected = ((b['close'] / b['open']) * .9996**2)**(365.25/(pd.Timestamp(b['end'])-pd.Timestamp(b['start'])).days)*100-100
        np.testing.assert_allclose(expected,b['cagr'],atol=1e-12)
    for c in d['caps']:
        records = c['trades']
        np.testing.assert_allclose(sum(t['pnl'] for t in records),c['metrics']['final']-1,atol=1e-9)
        counts = Counter()
        cursor = 0
        ordered = sorted(records,key=lambda t:t['exit_date'])
        for e in c['decisions']:
            while cursor < len(ordered) and ordered[cursor]['exit_date'] < e['date']:
                counts[ordered[cursor]['symbol']] += 1
                cursor += 1
            assert e['completed_total'] == cursor and e['completed_symbol'] == counts[e['symbol']]
            assert e['blocked'] == (cursor > 0 and counts[e['symbol']] > c['cap']*cursor)
        grouped = Counter()
        for t in records:
            grouped[t['symbol']] += t['pnl']
        np.testing.assert_allclose(c['symbols']['net_pct'],sum(sorted(grouped.values(),reverse=True)[:5])/sum(grouped.values())*100)
        assert c['prefix_checks'] == 4
    # A exits, B exits, A at exact 1/2 equality; A at 2/3 blocked,
    # B exit grows denominator; A at exact 2/4 equality resumes.
    dates = pd.date_range('2020-01-01',periods=12,tz='UTC')
    frames = {}
    for symbol, signals in [('A',[0,4,6,8]),('B',[2,6])]:
        frame = pd.DataFrame(dict(Open=100.,High=100.,Low=100.,Close=100.,
                                  SIGNAL=False,VOL_RATIO=2. if symbol=='A' else 1.,
                                  ATR14=0.,STOP_LEVEL=0.),index=dates)
        frame.loc[dates[signals],'SIGNAL'] = True
        frames[symbol] = frame
    result = simulate_portfolio(frames,top_k=1,hold_days=1,symbol_trade_share_cap=.5,return_trace=True)
    entries = [(e['date'],e['symbol']) for e in result['allocations']]
    assert entries == [(str(dates[i]),s) for i,s in [(1,'A'),(3,'B'),(5,'A'),(7,'B'),(9,'A')]]
    decisions = {(e['date'],e['symbol']):e for e in result['symbol_share_log']}
    for day in [1,5,9]:
        assert not decisions[str(dates[day]),'A']['blocked']
    assert decisions[str(dates[7]),'A']['blocked']
    for bad in [0,-.1,1.1,float('nan')]:
        try:
            simulate_portfolio(frames,symbol_trade_share_cap=bad)
        except ValueError:
            pass
        else:
            raise AssertionError('invalid cap accepted')
    assert doc.count('## 18.') == 1
    section = doc.split('## 18.')[1].split('## 결론')[0]
    assert sum(line.startswith('| ') and '알파 있음(통과)' in line or line.startswith('| ') and '알파 없음(실패)' in line for line in section.splitlines()) == 48
    assert not d['candidate']
    for n in range(1,6):
        log = (ROOT / f'docs/round6-round{n}-regression-2026-10-07.txt').read_text()
        assert 'PASS:' in log and 'Traceback' not in log
    print('PASS: 48 exact source cells; independent BTC arithmetic; 3 terminal ledgers and cap decision counts; symbol concentration; zero-count/equality/block/denominator recovery fixture; invalid caps; 12 real prefix/future comparisons; document completeness; Round 1-5 regressions')


if __name__ == '__main__':
    run()
