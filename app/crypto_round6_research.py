"""Offline BTC-relative reclassification and three causal trade-share caps."""
import json
from collections import Counter, defaultdict

import numpy as np
import pandas as pd

from app.crypto_bucket_ensemble_research import CHAMPION_PATH, volume_prep
from app.crypto_round3_research import ROOT
from app.crypto_round4_robustness import ledger_run, concentration
from app.crypto_technical_ict_research import load_data, benchmark
from app.technical_portfolio_engine import simulate_portfolio

PATH = ROOT / 'docs/round6-results-2026-10-07.json'


def btc_period(btc, start, end):
    bars = btc.loc[start:end]
    assert str(bars.index[0].date()) == start and str(bars.index[-1].date()) == end
    years = (bars.index[-1] - bars.index[0]).days / 365.25
    final = bars.Close.iloc[-1] / bars.Open.iloc[0] * (1 - .04 / 100) ** 2
    return dict(start=start, end=end, open=float(bars.Open.iloc[0]),
                close=float(bars.Close.iloc[-1]), years=years, final=float(final),
                cagr=float(final ** (1 / years) * 100 - 100))


def symbols(records):
    grouped = defaultdict(float)
    for t in records:
        grouped[t['symbol']] += t['pnl']
    ranked = sorted(grouped.items(), key=lambda p: (-p[1], p[0]))
    net = sum(grouped.values())
    assert net > 0
    return dict(top5=[s for s, _ in ranked[:5]],
                net_pct=sum(p for _, p in ranked[:5]) / net * 100,
                rows=[dict(symbol=s, pnl=p) for s, p in ranked])


def audit_decisions(result, records, cap):
    """Independent completed ledger counts, strictly before next-open decisions.

    Champion has no gap stop, so exits on the decision date occur later at close.
    """
    for event in result['symbol_share_log']:
        prior = [t for t in records if t['exit_date'] < event['date']]
        counts = Counter(t['symbol'] for t in prior)
        assert event['completed_total'] == len(prior)
        assert event['completed_symbol'] == counts[event['symbol']]
        assert event['blocked'] == (len(prior) > 0 and counts[event['symbol']] > cap * len(prior))
    decisions = {(e['date'], e['symbol']): e for e in result['symbol_share_log']}
    for entry in result['allocations']:
        assert not decisions[entry['date'], entry['symbol']]['blocked']
    assert any(e['blocked'] for e in result['symbol_share_log'])


def run():
    old = json.loads((ROOT / 'docs/round4-results-2026-10-07.json').read_text())
    champion = json.loads(CHAMPION_PATH.read_text())
    assert champion['periods'] == old['periods']
    frames, manifest, _ = load_data()
    assert manifest == old['manifest'] == champion['manifest']
    # Explicit direct cache read, with the same sorted/deduplicated timestamps.
    btc = pd.read_csv(ROOT / '.screen_cache/binance_usdtm_1d/BTC_1d_20190101T000000Z.csv',
                      index_col='timestamp', parse_dates=True).sort_index()
    btc = btc.loc[~btc.index.duplicated()]
    benchmarks = [btc_period(btc, *p) for p in old['periods']]
    whole = btc_period(btc, '2019-09-08', '2026-10-05')
    np.testing.assert_allclose(whole['cagr'], benchmark(frames), rtol=0, atol=1e-12)
    labels = ['챔피언 cap5%/신엔진'] + [f'하이킨아시/CB{x}%/BTC재개' for x in [15,20,25,30]] + ['FRVP/CB20%/쿨다운60일']
    rows = []
    for label, source in zip(labels, [champion['champion']] + old['winners']):
        cells = []
        for p, b in zip(source['periods'], benchmarks):
            assert [p['start'],p['end']] == [b['start'],b['end']]
            m = p['metrics']; alpha = m['cagr'] - b['cagr']
            absolute = m['cagr'] >= 0 and m['sharpe'] >= .5
            cells.append(dict(start=p['start'],end=p['end'],metrics=m,
                              btc_cagr=b['cagr'],alpha=alpha,absolute_pass=absolute,
                              alpha_pass=alpha > 0))
        rows.append(dict(name=label,periods=cells,
                         absolute_failures=sum(not p['absolute_pass'] for p in cells),
                         alpha_failures=sum(not p['alpha_pass'] for p in cells),
                         converted=sum(not p['absolute_pass'] and p['alpha_pass'] for p in cells),
                         newly_failed=sum(p['absolute_pass'] and not p['alpha_pass'] for p in cells),
                         top10_net_pct=source['concentration']['10']['net_pct'],
                         top5_net_pct=source.get('symbols',{}).get('net_pct',symbols(source['trades'])['net_pct'])))
    prepared = volume_prep(frames)
    base = champion['champion']
    output = dict(manifest=manifest,periods=old['periods'],btc=benchmarks,btc_whole=whole,
                  strategies=rows,baseline=dict(metrics=base['full'],symbols=base['symbols']),caps=[],
                  criteria=dict(top5_reduction_pp_min=10,cagr_loss_pp_max_exclusive=20,
                                sharpe_loss_relative_pct_max_exclusive=20),
                  notes='CAGR difference is BTC-relative excess return, not beta-adjusted regression alpha. Capped variants have no new period backtests; baseline period verdict cannot prove capped period stability.')
    for cap in [.10,.15,.20]:
        result, records, _, _, _ = ledger_run(prepared, dict(symbol_trade_share_cap=cap))
        audit_decisions(result,records,cap)
        prefix_checks = 0
        for cutoff in ['2022-12-31','2024-06-30']:
            short = simulate_portfolio({s:df.loc[:cutoff] for s,df in prepared.items() if len(df.loc[:cutoff])},
                                       symbol_trade_share_cap=cap,return_trace=True)
            assert short['trace'][:-1] == result['trace'][:len(short['trace'])-1]
            assert short['allocations'] == [e for e in result['allocations'] if e['date'] <= str(pd.Timestamp(cutoff,tz='UTC'))]
            assert short['symbol_share_log'] == [e for e in result['symbol_share_log'] if e['date'] <= str(pd.Timestamp(cutoff,tz='UTC'))]
            # Mutate every future bar, including signals: decisions in prefix stay fixed.
            mutated = {s:df.copy() for s,df in prepared.items()}
            for df in mutated.values():
                future = df.index > pd.Timestamp(cutoff,tz='UTC')
                df.loc[future,['Open','High','Low','Close']] *= 3
                df.loc[future,'SIGNAL'] = True
                df.loc[future,'VOL_RATIO'] = 999
            altered = simulate_portfolio(mutated,symbol_trade_share_cap=cap,return_trace=True)
            assert altered['trace'][:len(short['trace'])-1] == short['trace'][:-1]
            assert [e for e in altered['symbol_share_log'] if e['date'] <= str(pd.Timestamp(cutoff,tz='UTC'))] == short['symbol_share_log']
            prefix_checks += 2
        sy = symbols(records)
        losses = dict(top5_reduction_pp=base['symbols']['net_pct']-sy['net_pct'],
                      cagr_loss_pp=base['full']['cagr']-result['cagr'],
                      sharpe_loss_relative_pct=(1-result['sharpe']/base['full']['sharpe'])*100)
        good = losses['top5_reduction_pp'] >= 10 and losses['cagr_loss_pp'] < 20 and losses['sharpe_loss_relative_pct'] < 20
        m = {k:v for k,v in result.items() if k not in ['trace','allocations','symbol_share_log']}
        assert np.isfinite([m[k] for k in ['cagr','mdd','sharpe','final']]).all()
        assert -100 < m['cagr'] < 1000 and 0 <= m['mdd'] <= 100
        output['caps'].append(dict(cap=cap,metrics=m,symbols=sy,losses=losses,mitigation_pass=good,
                                   concentration=concentration(records),trades=records,
                                   decisions=result['symbol_share_log'],prefix_checks=prefix_checks))
        print('CAP',cap,m,sy['net_pct'],losses,'PASS' if good else 'FAIL',flush=True)
    output['candidate'] = rows[0]['alpha_failures'] == 0 and any(c['mitigation_pass'] for c in output['caps'])
    PATH.write_text(json.dumps(output,ensure_ascii=False,indent=2,allow_nan=False,default=str))
    print('ALPHA',[(r['name'],r['absolute_failures'],r['alpha_failures'],r['converted'],r['newly_failed']) for r in rows],flush=True)
    print('PASS: 48 reused cells; 8 BTC periods; original benchmark formula; manifest; 3 ledger reconciliations and independent decision audits; 12 prefix/future-mutation comparisons; finite metrics',flush=True)


if __name__ == '__main__':
    run()
