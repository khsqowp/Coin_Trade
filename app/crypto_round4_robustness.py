"""Offline fixed-parameter robustness audit; original engine remains unchanged."""
import json
import sys
from collections import defaultdict

import numpy as np
import pandas as pd

from app.crypto_round3_research import ROOT, PATH as PRIOR, prep, btc_trend
from app.crypto_technical_ict_research import load_data
from app.technical_portfolio_engine import simulate_portfolio

PATH = ROOT / 'docs/round4-results-2026-10-07.json'


def metrics(curve, dates, trades):
    equity = pd.Series(curve, index=dates)
    years = (dates[-1] - dates[0]).days / 365.25
    bankrupt = bool((equity <= 0).any())
    daily = equity.pct_change().dropna()
    return dict(cagr=None if bankrupt else (equity.iloc[-1] ** (1 / years) - 1) * 100,
                mdd=None if bankrupt else ((equity.cummax() - equity) / equity.cummax()).max() * 100,
                diagnostic_raw_drawdown=((equity.cummax() - equity) / equity.cummax()).max() * 100,
                minimum_equity=float(equity.min()),
                first_nonpositive_date=str(equity[equity <= 0].index[0]) if bankrupt else None,
                sharpe=None if bankrupt else float(daily.mean() / daily.std() * np.sqrt(365)),
                final=float(equity.iloc[-1]), trades=trades, insolvent=bankrupt)


def ledger_run(prepped, config):
    """Observe sell calls without modifying the common engine or its decisions."""
    records = []
    old_profile = sys.getprofile()

    def observe(frame, event, arg):
        if event == 'call' and frame.f_code.co_name == 'sell' and frame.f_code.co_filename == simulate_portfolio.__code__.co_filename:
            local = frame.f_locals
            k = local['k']
            p = local['positions'][k]
            parent = frame.f_back.f_locals
            entry = p['exit'] - parent['hold_days']
            price = parent['a']['Open'][entry, k]
            cost = p['qty'] * price / (1 - parent['fee'])
            proceeds = p['qty'] * local['price'] * (1 - parent['fee'])
            records.append(dict(id=len(records), symbol=parent['keys'][k], entry=entry,
                                exit=parent['i'], entry_date=str(parent['dates'][entry]),
                                exit_date=str(parent['d']), qty=p['qty'], cost=cost,
                                proceeds=proceeds, pnl=proceeds-cost, return_pct=(proceeds/cost-1)*100))
    try:
        sys.setprofile(observe)
        result = simulate_portfolio(prepped, return_trace=True, **config)
    finally:
        sys.setprofile(old_profile)
    dates = [pd.Timestamp(t['date']) for t in result['trace']]
    contributions = []
    for trade in records:
        close = prepped[trade['symbol']].Close.reindex(dates).ffill().to_numpy()
        contribution = np.zeros(len(dates))
        e, x = trade['entry'], trade['exit']
        contribution[e:x] = trade['qty'] * close[e:x] - trade['cost']
        contribution[x:] = trade['pnl']
        contributions.append(contribution)
    contributions = np.array(contributions)
    curve = np.array([t['closing'] for t in result['trace']])
    assert len(records) == result['trades']
    np.testing.assert_allclose(1 + contributions.sum(axis=0), curve, rtol=1e-10, atol=1e-9)
    assert abs(sum(t['pnl'] for t in records) - (result['final']-1)) < 1e-8
    return result, records, contributions, dates, curve


def concentration(records):
    ranked = sorted(records, key=lambda t: (-t['pnl'], t['id']))
    positive = sum(max(0, t['pnl']) for t in records)
    net = sum(t['pnl'] for t in records)
    return {str(n): dict(pnl=sum(t['pnl'] for t in ranked[:n]),
                        positive_pct=sum(t['pnl'] for t in ranked[:n])/positive*100,
                        net_pct=sum(t['pnl'] for t in ranked[:n])/net*100)
            for n in [10, 20]}


def flapping(result):
    log = result['breaker_log']
    gaps = []
    censored = 0
    last = len(result['trace']) - 1
    for j, event in enumerate(log):
        if event['kind'] != 'resume':
            continue
        following = next((e for e in log[j+1:] if e['kind'] == 'pause'), None)
        gaps.append(None if following is None else following['index']-event['index'])
        censored += int(following is None and last-event['index'] < 5)
    return dict(pauses=result['breaker_events'], resumes=result['breaker_resumes'],
                censored_5d=censored,
                within={str(n): dict(count=sum(g is not None and g <= n for g in gaps),
                                     pct=sum(g is not None and g <= n for g in gaps)/len(gaps)*100)
                        for n in [1, 3, 5]})


def run():
    frames, manifest, skipped = load_data()
    prior = json.loads(PRIOR.read_text())
    assert manifest == prior['manifest'] and len(frames) == 45
    winners = prior['winners']
    assert [(r['name'], r['config']['dd_trigger']) for r in winners] == [('heikin_ashi', x) for x in [.15,.20,.25,.30]] + [('frvp', .20)]
    prepared = {name: prep(name, frames) for name in ['heikin_ashi','frvp','volume_spike_cap5']}
    trend = btc_trend(frames['BTC'])
    periods = [('2019-09-08','2022-12-31'), ('2023-01-01','2026-10-05')]
    periods += [(f'{year}-09-08', f'{year+2}-09-07') for year in range(2019,2024)]
    periods += [('2024-10-06','2026-10-05')]
    output = dict(manifest=manifest, skipped=skipped, periods=periods,
                  methodology='Fixed original cash amounts and executions; removed trades leave principal in cash. No reallocation/CB recomputation in leave-top-N-out. Insolvency makes CAGR/Sharpe undefined.',
                  winners=[], sensitivity=[])
    for num, winner in enumerate(winners, 1):
        name = winner['name']; config = winner['config'].copy()
        if config['resume_mode'] == 'btc_sma50':
            config['btc_resume'] = trend
        full, records, contributions, dates, curve = ledger_run(prepared[name], config)
        for k in ['cagr','mdd','sharpe','trades','final','breaker_events','breaker_resumes']:
            assert abs(full[k]-winner['metrics'][k]) < 1e-8, (num,k)
        row = dict(id=num, name=name, config=winner['config'], full={k:v for k,v in full.items() if k not in ['trace','allocations']},
                   trades=records, concentration=concentration(records), periods=[],
                   daily_equity=[dict(date=str(date),equity=float(value)) for date,value in zip(dates,curve)])
        for start,end in periods:
            sliced = {s:df.loc[start:end] for s,df in prepared[name].items() if len(df.loc[start:end])}
            result = simulate_portfolio(sliced, **config)
            assert result['trades'] > 0 and all(np.isfinite(result[k]) for k in ['cagr','mdd','sharpe','final'])
            assert -100 < result['cagr'] < 1000 and 0 <= result['mdd'] <= 100
            row['periods'].append(dict(start=start,end=end,metrics=result))
        if name == 'heikin_ashi':
            row['flapping'] = flapping(full)
        if num == 3:
            ranked = sorted(records, key=lambda t: (-t['pnl'],t['id']))
            row['leave_top_out'] = []
            for n in [5,10,20,50]:
                removed = [t['id'] for t in ranked[:n]]
                reduced = curve-contributions[removed].sum(axis=0)
                np.testing.assert_allclose(reduced, 1+np.delete(contributions,removed,axis=0).sum(axis=0),rtol=1e-10,atol=1e-9)
                # A separate fixed-relative-exposure replay avoids unfunded fixed
                # dollar positions: subtract removed daily P&L / original prior NAV.
                previous = np.r_[1., curve[:-1]]
                retained_daily = np.diff(reduced, prepend=1.) / previous
                normalized = np.cumprod(1 + retained_daily)
                row['leave_top_out'].append(dict(n=n,removed_ids=removed,
                                                     normalized_metrics=metrics(normalized,dates,len(records)-n),
                                                     normalized_daily_equity=[dict(date=str(date),equity=float(value)) for date,value in zip(dates,normalized)],
                                                     metrics=metrics(reduced,dates,len(records)-n),
                                                     daily_equity=[dict(date=str(date),equity=float(value)) for date,value in zip(dates,reduced)]))
            grouped = defaultdict(lambda: dict(trades=0,pnl=0.))
            for t in records:
                grouped[t['symbol']]['trades'] += 1
                grouped[t['symbol']]['pnl'] += t['pnl']
            symbols = [dict(symbol=s,**grouped[s]) for s in sorted(frames)]
            symbols.sort(key=lambda t: (-t['pnl'],t['symbol']))
            top = symbols[:5]; excluded = [t['symbol'] for t in top]
            by_count = sorted(symbols,key=lambda t:(-t['trades'],t['symbol']))[:5]
            share = sum(t['pnl'] for t in top)/(full['final']-1)*100
            row['symbols'] = dict(rows=symbols,top5=excluded,net_pct=share,
                                  trades_pct=sum(t['trades'] for t in top)/len(records)*100,
                                  top5_by_count=by_count,top5_count_pct=sum(t['trades'] for t in by_count)/len(records)*100)
            if share >= 50:
                row['symbols']['excluded_metrics'] = simulate_portfolio({s:df for s,df in prepared[name].items() if s not in excluded},**config)
        output['winners'].append(row)
        print('winner',num,'reproduced; independent periods',len(periods),'top10',row['concentration']['10'],flush=True)
    for threshold in [.15,.20,.22,.25,.27,.30]:
        m = simulate_portfolio(prepared['heikin_ashi'], dd_trigger=threshold, resume_mode='btc_sma50',cooldown_days=20,btc_resume=trend)
        output['sensitivity'].append(dict(dd_trigger=threshold,metrics=m))
    # Explicit numerical rule set before interpreting the sensitivity results.
    jumps = []
    for a,b in zip(output['sensitivity'],output['sensitivity'][1:]):
        delta = {k:abs(b['metrics'][k]-a['metrics'][k]) for k in ['cagr','mdd','sharpe']}
        jumps.append(dict(left=a['dd_trigger'],right=b['dd_trigger'],delta=delta,
                          unstable=bool(delta['cagr']>30 or delta['mdd']>10 or delta['sharpe']>.30)))
    main = output['winners'][2]
    flags = dict(periods=any(r['metrics']['sharpe']<.5 or r['metrics']['cagr']<0 for r in main['periods']),
                 concentration=main['concentration']['10']['net_pct']>=50,
                 sensitivity=any(j['unstable'] for j in jumps),
                 flapping=main['flapping']['within']['5']['pct']>=30,
                 symbols=main['symbols']['net_pct']>=50)
    flags = {key: bool(value) for key, value in flags.items()}
    count = sum(flags.values())
    output.update(runtime=dict(python=sys.version,numpy=np.__version__,pandas=pd.__version__),
                  criteria=dict(period_sharpe_min=.5,period_cagr_min=0,top10_net_pct_max=50,
                                sensitivity_cagr_delta_max=30,sensitivity_mdd_delta_max=10,
                                sensitivity_sharpe_delta_max=.30,flapping_5d_pct_max=30,top5_symbol_net_pct_max=50),
                  sensitivity_jumps=jumps,flags=flags,unstable_count=count,
                  verdict='기각' if count>=2 else ('승격' if count==0 else '조건부 보류'))
    output['baseline'] = simulate_portfolio(prepared['volume_spike_cap5'])
    for k in ['cagr','mdd','sharpe','trades']:
        assert abs(output['baseline'][k]-prior['reference'][k]) < 1e-8
    # Interval prefix comparisons exclude terminal forced liquidation.
    for name in ['heikin_ashi','frvp']:
        cutoff = pd.Timestamp('2024-06-30',tz='UTC')
        limited_frames = {s:df.loc[:cutoff] for s,df in frames.items() if len(df.loc[:cutoff])>=201}
        limited = prep(name,limited_frames)
        for s,df in limited.items():
            pd.testing.assert_frame_equal(prepared[name][s].loc[:cutoff],df)
    config = dict(main['config'],btc_resume=trend)
    sliced = {s:df.loc['2023-01-01':] for s,df in prepared['heikin_ashi'].items() if len(df.loc['2023-01-01':])}
    full = simulate_portfolio(sliced,return_trace=True,**config)
    short = simulate_portfolio({s:df.loc[:cutoff] for s,df in sliced.items() if len(df.loc[:cutoff])},return_trace=True,**config)
    assert short['trace'][:-1] == full['trace'][:len(short['trace'])-1]
    PATH.write_text(json.dumps(output,ensure_ascii=False,indent=2,default=str,allow_nan=False))
    print('PASS: 5 exact reproductions; 40 independent windows; trade ledger daily reconciliation; leave-out reconciliation; 45-symbol historical indicators; independent-window engine prefix; baseline reproduction',flush=True)
    print('VERDICT',output['verdict'],flags,flush=True)
    return output


if __name__ == '__main__':
    run()
