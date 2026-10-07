"""Round9: fixed TOP_K12 diagnosis using unchanged Round4/8 methods."""
import json
import hashlib
import numpy as np
import pandas as pd
from app.crypto_technical_ict_research import ROOT, load_data
from app.crypto_round8_research import core, filtered, resolved
from app.crypto_round4_robustness import flapping
from app.crypto_round6_research import btc_period
from app.crypto_round7_research import summary
from app.technical_portfolio_engine import simulate_portfolio

PATH = ROOT / 'docs/round9-results-2026-10-07.json'


def run():
    prior = json.loads((ROOT/'docs/round8-results-2026-10-07.json').read_text())
    old = json.loads((ROOT/'docs/round4-results-2026-10-07.json').read_text())
    candidate = next(r for r in prior['experiments'] if r['config'].get('top_k') == 12)
    frames, manifest, skipped = load_data()
    assert manifest == prior['manifest'] == old['manifest'] and not skipped
    p = filtered(core(candidate['family'], frames), frames, candidate['filter'])
    cb = resolved(candidate['config'], frames)
    no_cb = dict(cb, dd_trigger=None)
    full = simulate_portfolio(p, return_trace=True, **cb)
    assert summary(full) == candidate['metrics']
    flap = flapping(full)
    # Independent event arithmetic verifies the imported Round4 definition.
    log = full['breaker_log']
    gaps = [next((e['index']-r['index'] for e in log[j+1:] if e['kind']=='pause'), None)
            for j,r in enumerate(log) if r['kind']=='resume']
    assert len(gaps) == flap['resumes']
    for n in [1,3,5]:
        assert flap['within'][str(n)]['count'] == sum(g is not None and g<=n for g in gaps)
    from app.round_period_standard import assert_standard
    assert_standard(candidate['robustness']['periods'])
    cells = []
    for cell in candidate['robustness']['periods']:
        start,end = cell['start'],cell['end']
        sub = {s:df.loc[start:end] for s,df in p.items() if len(df.loc[start:end])}
        a = summary(simulate_portfolio(sub, **cb))
        b = summary(simulate_portfolio(sub, **no_cb))
        btc = btc_period(frames['BTC'], start, end)['cagr']
        assert a == cell['metrics'] and btc == cell['btc_cagr']
        cells.append(dict(start=start,end=end,cb=a,no_cb=b,btc_cagr=btc,
                          cb_alpha=a['cagr']-btc,no_cb_alpha=b['cagr']-btc,
                          cause=('실패 없음' if a['cagr']>btc else
                                 'CB/재개 수익훼손' if b['cagr']>btc else '순수 신호 엣지 약화')))
    pure = simulate_portfolio(p, return_trace=True, **no_cb)
    cutoff = pd.Timestamp('2024-06-30', tz='UTC')
    sub = {s:df.loc[:cutoff] for s,df in p.items() if len(df.loc[:cutoff])}
    short = simulate_portfolio(sub, return_trace=True, **no_cb)
    assert short['trace'][:-1] == pure['trace'][:len(short['trace'])-1]
    changed = {s:df.copy() for s,df in p.items()}
    for df in changed.values():
        future = df.index>cutoff
        df.loc[future,['Open','High','Low','Close']] *= 3
        df.loc[future,'SIGNAL'] = True
        df.loc[future,'VOL_RATIO'] = 999
    altered = simulate_portfolio(changed, return_trace=True, **no_cb)
    assert altered['trace'][:len(short['trace'])-1] == short['trace'][:-1]
    assert all(pd.Timestamp(a['known_through'])<pd.Timestamp(a['date']) for a in pure['allocations'])
    assert pure['breaker_events'] == pure['breaker_resumes'] == 0
    for c in cells:
        for m in [c['cb'],c['no_cb']]:
            assert np.isfinite(list(m.values())).all() and -100<m['cagr']<1000 and 0<=m['mdd']<=100 and m['trades']>0
    votes = [flap['within']['5']['pct']<=50, sum(c['cb_alpha']>0 for c in cells)>=7]
    d = dict(manifest=manifest, config=candidate['config'], full=summary(full),
             no_cb_full=summary(pure), flapping=flap, breaker_log=log, resume_to_pause_gaps=gaps,
             round4_flapping=old['winners'][2]['flapping'], periods=cells,
             cb_positive=sum(c['cb_alpha']>0 for c in cells),
             no_cb_positive=sum(c['no_cb_alpha']>0 for c in cells),
             thresholds=dict(flapping_5d_max_pct=50,alpha_positive_min=7),votes=votes,
             verdict='통과' if all(votes) else '기각', variants=[],
             verification='Round8 full/8 windows exact; Round4 flapping helper and independent gaps; no-CB prefix/future mutation/timestamps; finite metrics',
             source_hashes={f:hashlib.sha256((ROOT/'docs'/f).read_bytes()).hexdigest() for f in ['round4-results-2026-10-07.json','round8-results-2026-10-07.json']})
    PATH.write_text(json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False))
    print(json.dumps({k:d[k] for k in ['full','no_cb_full','flapping','cb_positive','no_cb_positive','votes','verdict','periods']},ensure_ascii=False,indent=2))
    print('PASS: exact Round4/8 methods; causal no-CB comparison; sane metrics')
    return d


if __name__ == '__main__':
    run()
