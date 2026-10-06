"""Round 5 offline audit, reusing Round 4 accounting and fixed criteria.

Run --champion first; the ensemble stage requires its completed artifact.
Weights are initial capital shares, never daily rebalanced target weights.
"""
import argparse
import json
import sys
from collections import defaultdict

import numpy as np
import pandas as pd

from app.crypto_round3_research import ROOT, prep, btc_trend
from app.crypto_round4_robustness import ledger_run, metrics, concentration, flapping
from app.crypto_technical_ict_research import load_data
from app.technical_portfolio_engine import simulate_portfolio
from app.volume_spike_signal_core import find_signals

PATH = ROOT / 'docs/round5-results-2026-10-07.json'
CHAMPION_PATH = ROOT / 'docs/round5-champion-results-2026-10-07.json'
NAMES = ['volume_spike_cap5', 'heikin_ashi', 'frvp']


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str, allow_nan=False))


def pack_curve(dates, curve):
    return [dict(date=str(d), equity=float(v)) for d, v in zip(dates, curve)]


def volume_prep(frames, multiple=3., cap=5.):
    result = {}
    for symbol, frame in frames.items():
        df = find_signals(frame, volume_multiple=multiple, max_price_change_pct=cap)
        df['ATR14'] = 0.
        df['STOP_LEVEL'] = 0.
        result[symbol] = df
    return result


def combine(runs, weights):
    """Pointwise fixed initial-capital sum; reject misaligned calendars.

    A completed bucket starts at NAV 1. No interpolation, backward fill,
    changing weights, shared slots or trading decisions enter this operation.
    """
    weights = np.asarray(weights, dtype=float)
    if len(weights) != len(runs) or not np.isfinite(weights).all() or (weights <= 0).any() or not np.isclose(weights.sum(), 1):
        raise ValueError('positive initial shares must sum to one')
    dates = runs[0][3]
    records, contributions = [], []
    curves = []
    for (result, ledger, contrib, calendar, curve), weight in zip(runs, weights):
        if calendar != dates or not pd.Index(calendar).is_monotonic_increasing or not pd.Index(calendar).is_unique:
            raise ValueError('bucket calendars must be identical, sorted and unique')
        np.testing.assert_allclose(curve[0], 1., atol=1e-12)
        curves.append(curve)
        for trade in ledger:
            item = dict(trade, id=len(records), bucket=len(curves)-1, bucket_trade_id=trade['id'])
            for key in ['qty', 'cost', 'proceeds', 'pnl']:
                item[key] *= weight
            records.append(item)
        contributions.extend(contrib * weight)
    curve = weights @ np.asarray(curves)
    contributions = np.asarray(contributions)
    np.testing.assert_allclose(1 + contributions.sum(axis=0), curve, rtol=1e-10, atol=1e-9)
    return metrics(curve, dates, len(records)), records, contributions, dates, curve


def jumps(points):
    output = []
    for a, b in zip(points, points[1:]):
        delta = {k: float(abs(b['metrics'][k]-a['metrics'][k])) for k in ['cagr', 'mdd', 'sharpe']}
        output.append(dict(left=a['value'], right=b['value'], delta=delta,
                           unstable=delta['cagr'] > 30 or delta['mdd'] > 10 or delta['sharpe'] > .30))
    return output


def run_buckets(prepared, names, weights):
    return combine([ledger_run(prepared[name], {}) for name in names], weights)


def audit(run, prepared, names, weights, periods):
    full, records, contributions, dates, curve = run
    summarized = {k:v for k,v in full.items() if k not in ['trace', 'allocations']}
    summarized.update(metrics(curve, dates, len(records)))
    row = dict(full=summarized,
               trades=records, daily_equity=pack_curve(dates, curve),
               concentration=concentration(records), periods=[], leave_top_out=[])
    for start, end in periods:
        sliced = {name: {s:df.loc[start:end] for s,df in prepared[name].items() if len(df.loc[start:end])} for name in names}
        result = run_buckets(sliced, names, weights)
        m, _, _, calendar, values = result
        assert values[0] == 1 and str(calendar[0].date()) == start and str(calendar[-1].date()) == end
        assert m['trades'] > 0 and -100 < m['cagr'] < 1000 and 0 <= m['mdd'] <= 100
        row['periods'].append(dict(start=start, end=end, metrics=m, initial_equity=float(values[0]),
                                   bucket_initial_equity=[1.] * len(names)))
    ranked = sorted(records, key=lambda t: (-t['pnl'], t['id']))
    for n in [5, 10, 20, 50]:
        removed = [t['id'] for t in ranked[:n]]
        reduced = curve - contributions[removed].sum(axis=0)
        np.testing.assert_allclose(reduced, 1 + np.delete(contributions, removed, axis=0).sum(axis=0), rtol=1e-10, atol=1e-9)
        normalized = np.cumprod(1 + np.diff(reduced, prepend=1.) / np.r_[1., curve[:-1]])
        row['leave_top_out'].append(dict(n=n, removed_ids=removed,
                metrics=metrics(reduced, dates, len(records)-n), daily_equity=pack_curve(dates, reduced),
                normalized_metrics=metrics(normalized, dates, len(records)-n),
                normalized_daily_equity=pack_curve(dates, normalized)))
    grouped = defaultdict(lambda: dict(trades=0, pnl=0.))
    for t in records:
        grouped[t['symbol']]['trades'] += 1
        grouped[t['symbol']]['pnl'] += t['pnl']
    symbols = sorted([dict(symbol=s, **grouped[s]) for s in sorted(prepared[names[0]])], key=lambda t: (-t['pnl'], t['symbol']))
    top = symbols[:5]
    excluded = [t['symbol'] for t in top]
    by_count = sorted(symbols, key=lambda t: (-t['trades'], t['symbol']))[:5]
    sy = dict(rows=symbols, top5=excluded, net_pct=sum(t['pnl'] for t in top)/(curve[-1]-1)*100,
              trades_pct=sum(t['trades'] for t in top)/len(records)*100,
              top5_by_count=by_count, top5_count_pct=sum(t['trades'] for t in by_count)/len(records)*100)
    if sy['net_pct'] >= 50:
        reduced = {name: {s:df for s,df in prepared[name].items() if s not in excluded} for name in names}
        sy['excluded_metrics'] = run_buckets(reduced, names, weights)[0]
    row['symbols'] = sy
    return row


def verdict(row, sensitivity):
    flags = dict(periods=any(r['metrics']['sharpe'] < .5 or r['metrics']['cagr'] < 0 for r in row['periods']),
                 concentration=row['concentration']['10']['net_pct'] >= 50,
                 sensitivity=any(j['unstable'] for j in sensitivity), symbols=row['symbols']['net_pct'] >= 50)
    row.update(flags={k:bool(v) for k,v in flags.items()}, unstable_count=int(sum(flags.values())))
    row['verdict'] = '기각' if row['unstable_count'] >= 2 else ('통과' if row['unstable_count'] == 0 else '조건부 보류')


def context():
    frames, manifest, skipped = load_data()
    old = json.loads((ROOT / 'docs/round4-results-2026-10-07.json').read_text())
    assert manifest == old['manifest'] and len(frames) == 45
    return frames, manifest, skipped, old


def champion():
    frames, manifest, skipped, old = context()
    prepared = {'volume_spike_cap5': volume_prep(frames)}
    original = prep('volume_spike_cap5', frames)
    for s in frames:
        pd.testing.assert_series_equal(prepared['volume_spike_cap5'][s].SIGNAL, original[s].SIGNAL)
        pd.testing.assert_series_equal(prepared['volume_spike_cap5'][s].VOL_RATIO, original[s].VOL_RATIO)
    run = ledger_run(prepared['volume_spike_cap5'], {})
    for k in ['cagr', 'mdd', 'sharpe', 'trades']:
        np.testing.assert_allclose(run[0][k], old['baseline'][k], rtol=0, atol=1e-8)
    row = audit(run, prepared, NAMES[:1], [1.], old['periods'])
    sensitivity = {}
    cache = {(3., 5.): row['full']}
    for parameter, values in [('volume_multiple', [2.5, 2.75, 3., 3.25, 3.5]), ('price_cap', [4., 4.5, 5., 5.5, 6.])]:
        points = []
        for value in values:
            pair = (value, 5.) if parameter == 'volume_multiple' else (3., value)
            if pair not in cache:
                cache[pair] = simulate_portfolio(volume_prep(frames, *pair))
            points.append(dict(value=value, metrics=cache[pair]))
        sensitivity[parameter] = dict(points=points, jumps=jumps(points))
    assert len(cache) == 9
    verdict(row, [j for series in sensitivity.values() for j in series['jumps']])
    row['sensitivity'] = sensitivity
    save(CHAMPION_PATH, dict(manifest=manifest, skipped=skipped, periods=old['periods'], criteria=old['criteria'],
                            runtime=dict(python=sys.version, numpy=np.__version__, pandas=pd.__version__),
                            config=dict(volume_multiple=3., price_cap=5., lookback=20, top_k=8,
                                        hold_days=20, fee_pct_one_way=.04, stop='none', dd_trigger=None,
                                        weight_mode='fixed_initial_capital_no_rebalance'),
                            champion=row, sensitivity_unique_runs=len(cache)))
    print('CHAMPION COMPLETE', row['verdict'], row['flags'], row['full'], flush=True)
    return row


def ensemble():
    if not CHAMPION_PATH.exists():
        raise RuntimeError('complete --champion before ensemble stage')
    completed = json.loads(CHAMPION_PATH.read_text())
    frames, manifest, skipped, old = context()
    assert completed['manifest'] == manifest
    prepared = {name: prep(name, frames) for name in NAMES}
    runs = [ledger_run(prepared[name], {}) for name in NAMES]
    prior = json.loads((ROOT / 'docs/round3-results-2026-10-06.json').read_text())
    for name, run in zip(NAMES, runs):
        baseline = next(r['metrics'] for r in prior['baselines'] if r['name'] == name)
        for k in ['cagr', 'mdd', 'sharpe', 'trades']:
            np.testing.assert_allclose(run[0][k], baseline[k], rtol=0, atol=1e-8)
    daily = pd.DataFrame({name:pd.Series(run[4], index=run[3]).pct_change() for name,run in zip(NAMES,runs)}).dropna()
    output = dict(completed, ensembles=[], buckets={name:{k:v for k,v in run[0].items() if k not in ['trace','allocations']} for name,run in zip(NAMES,runs)},
                  correlation=daily.corr().to_dict(), correlation_days=len(daily))
    baseline = completed['champion']['full']
    # Predeclared symmetric grids; N3 holds HA:FRVP at 1:1 while varying champion.
    for n, grid in [(2, [.3,.4,.5,.6,.7]), (3, [.2,.3,1/3,.4,.5])]:
        def weights(w):
            return [w, 1-w] if n == 2 else [w, (1-w)/2, (1-w)/2]
        row = audit(combine(runs[:n], [1/n]*n), prepared, NAMES[:n], [1/n]*n, old['periods'])
        points = [dict(value=w, weights=weights(w), metrics=combine(runs[:n],weights(w))[0]) for w in grid]
        row.update(n=n, names=NAMES[:n], weights=[1/n]*n, sensitivity=dict(points=points,jumps=jumps(points)))
        verdict(row, row['sensitivity']['jumps'])
        row['robustness_verdict'] = row['verdict']
        m = row['full']
        row['better_axes'] = dict(cagr=bool(m['cagr']>baseline['cagr']), mdd=bool(m['mdd']<baseline['mdd']), sharpe=bool(m['sharpe']>baseline['sharpe']))
        row['verdict'] = '승격후보' if all(row['better_axes'].values()) and row['unstable_count']==0 else ('기각' if not all(row['better_axes'].values()) or row['unstable_count']>=2 else '조건부 보류')
        output['ensembles'].append(row)
        print('ENSEMBLE',n,row['verdict'],row['flags'],row['full'],flush=True)
    trend = pd.Series(btc_trend(frames['BTC']))
    confirmed = trend.rolling(3, min_periods=3).sum().eq(3).to_dict()
    cb = simulate_portfolio(prepared['heikin_ashi'], dd_trigger=.25, resume_mode='btc_sma50', btc_resume=confirmed, return_trace=True)
    dates = [pd.Timestamp(t['date']) for t in cb['trace']]
    for i, e in enumerate(cb['breaker_log']):
        if e['kind'] == 'resume':
            assert confirmed[dates[e['index']-1]]
            p = next(e2 for e2 in reversed(cb['breaker_log'][:i]) if e2['kind']=='pause')
            assert not any(confirmed.get(dates[j-1],False) for j in range(p['index']+1,e['index']))
    output['btc_confirmation'] = dict(full={k:v for k,v in cb.items() if k not in ['trace','allocations']},
            flapping=flapping(cb), original_flapping=old['winners'][2]['flapping'],
            note='채택 재검토용 참고 수치; 새 승자 아님; 기존 피크·재개일 유예 유지')
    save(PATH, output)
    print('BTC CONFIRMATION',output['btc_confirmation']['flapping'],flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--champion', action='store_true')
    args = parser.parse_args()
    champion() if args.champion else ensemble()
