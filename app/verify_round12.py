"""Artifact checks and causal synthetic entry tests; no external data fetching."""
import json
import sys
import numpy as np
import pandas as pd
from app.crypto_technical_ict_research import ROOT
from app.round12_signals import FAMILIES, EXTRA_FAMILIES, find_signals
from app.technical_portfolio_engine import simulate_portfolio


def run():
    path = ROOT/'docs/round12-results-2026-10-07.json'
    out = json.loads(path.read_text())
    seen = set()
    for row in out['experiments']:
        key = json.dumps([row['phase'], row['config']], sort_keys=True)
        assert key not in seen
        seen.add(key)
        assert all(row['causal_checks'].values())
        m, b = row['metrics'], out['baseline']
        assert row['dominates'] == (m['cagr'] > b['cagr'] and m['mdd'] < b['mdd'] and m['sharpe'] > b['sharpe'])
        assert np.isfinite(list(m.values())).all()
        if row['dominates']:
            r = row['robustness']
            assert len(r['votes']) == 5 and len(r['monte_carlo']['trials']) >= 300
            assert r['bootstrap']['iterations'] >= 1000 and r['bootstrap']['block_size'] == 20
            assert r['verdict'] == ('통과' if all(r['votes']) else '기각')
            assert abs(sum(t['pnl'] for t in r['records'])-(m['final']-1)) < 1e-8
            from app.crypto_round4_robustness import concentration
            from app.crypto_round6_research import symbols
            actual_conc = concentration(r['records'])
            for count, values in actual_conc.items():
                for field, value in values.items():
                    np.testing.assert_allclose(value, r['concentration'][count][field], rtol=0, atol=1e-10)
            actual_symbols = symbols(r['records'])
            assert actual_symbols['top5'] == r['symbols']['top5']
            np.testing.assert_allclose(actual_symbols['net_pct'], r['symbols']['net_pct'], rtol=0, atol=1e-10)
            assert [x['symbol'] for x in actual_symbols['rows']] == [x['symbol'] for x in r['symbols']['rows']]
            np.testing.assert_allclose([x['pnl'] for x in actual_symbols['rows']], [x['pnl'] for x in r['symbols']['rows']], rtol=0, atol=1e-10)
            for metric in ['cagr', 'sharpe']:
                trials = r['monte_carlo']['trials']
                pvalue = (1+sum(t[metric] >= m[metric] for t in trials))/(len(trials)+1)
                assert pvalue == r['monte_carlo']['tests'][metric]['p']
            np.testing.assert_allclose(np.percentile(r['bootstrap']['samples'], [2.5, 97.5]), r['bootstrap']['ci95'])
            rates = ([r['breaker_5day_pct']] if r['breaker_5day_pct'] is not None else [])
            if r['thrashing'] is not None:
                rates.append(r['thrashing']['within']['5']['pct'])
            expected = [sum(x['alpha'] > 0 for x in r['periods']) >= 7 and sum(x['alpha'] > 0 for x in r['legacy_periods']) >= 7,
                        r['concentration']['10']['net_pct'] <= 103 and r['symbols']['net_pct'] <= 88,
                        all(t['p'] < .05 for t in r['monte_carlo']['tests'].values()),
                        r['bootstrap']['ci95'][0] > 0, all(v <= 50 for v in rates)]
            assert expected == r['votes']
    rng = np.random.default_rng(120012)
    close = 100*np.exp(np.cumsum(rng.normal(.001, .025, 600)))
    frame = pd.DataFrame(dict(Open=close*.999, High=close*1.03, Low=close*.97,
                              Close=close, Volume=rng.uniform(100, 1000, 600)),
                         index=pd.date_range('2020-01-01', periods=600, tz='UTC'))
    for name in FAMILIES+EXTRA_FAMILIES:
        a = find_signals(frame, name)
        b = find_signals(frame.iloc[:400], name)
        for field in ['SIGNAL', 'VOL_RATIO', 'ATR14', 'STOP_LEVEL']:
            np.testing.assert_allclose(a[field].iloc[:400], b[field], equal_nan=True)
        result = simulate_portfolio({'test':a}, return_trace=True)
        assert all(pd.Timestamp(x['known_through']) < pd.Timestamp(x['date']) for x in result['allocations'])
    assert len(out['manifest']) == 45
    if '--replay' in sys.argv:
        from app.crypto_technical_ict_research import load_data
        from app.crypto_round12_research import build, audit
        from app.crypto_bucket_ensemble_research import volume_prep
        from app.crypto_round7_research import summary
        frames, manifest, skipped = load_data()
        assert not skipped and manifest == out['manifest']
        assert summary(simulate_portfolio(volume_prep(frames))) == out['baseline']
        for i, row in enumerate(out['experiments'], 1):
            p, kw, _ = build(frames, row['config'])
            m = simulate_portfolio(p, return_trace=True, **kw)
            for k, v in summary(m).items():
                np.testing.assert_allclose(v, row['metrics'][k], rtol=0, atol=1e-10)
            assert all(audit(frames, row['config'], m).values())
            print(f'REPLAY {i}/{len(out["experiments"])} metrics + full45-universe prefix audit passed', flush=True)
    print(f'PASS Round12 {len(seen)} unique experiments; {len(FAMILIES+EXTRA_FAMILIES)} synthetic prefix tests; artifacts, 5 gates, entry chronology')


if __name__ == '__main__':
    run()
