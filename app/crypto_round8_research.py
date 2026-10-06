"""Round 8 offline family ranking, causal variants and conditional robustness."""
import hashlib
import importlib
import json
import subprocess

import numpy as np
import pandas as pd

from app.crypto_technical_ict_research import ROOT, load_data
from app.crypto_bucket_ensemble_research import volume_prep, combine
from app.crypto_round4_robustness import ledger_run, concentration, metrics
from app.crypto_round6_research import btc_period, symbols
from app.crypto_round7_research import random_data, block_bootstrap, summary
from app.technical_portfolio_engine import prepare, simulate_portfolio
from app.technical_signal_common import ta

PATH = ROOT / 'docs/round8-results-2026-10-07.json'
DOC = ROOT / 'docs/전략-백테스트-종합.md'
SOURCES = ['technical-ict-results-2026-10-06.json', 'hybrid-drawdown-results-2026-10-06.json',
           'round3-results-2026-10-06.json', 'round4-results-2026-10-07.json',
           'round5-champion-results-2026-10-07.json', 'round5-results-2026-10-07.json',
           'round6-results-2026-10-07.json', 'round7-results-2026-10-07.json']
LABELS = dict(volume='거래량폭증', heikin_ashi='하이킨아시', frvp='FRVP', vwap='VWAP',
              ensemble='분리자본 앙상블', fvg='FVG', fibonacci='피보나치', ema_cross='EMA크로스',
              liquidity_sweep='리퀴디티스윕', elliott_wave='엘리엇', rsi='RSI',
              order_block='오더블록', hybrid='하이브리드')


def save(d):
    PATH.write_text(json.dumps(d, ensure_ascii=False, indent=2, allow_nan=False, default=str))


def aggregate():
    sources = {f: json.loads((ROOT / 'docs' / f).read_text()) for f in SOURCES}
    rows = []
    def add(name, config, m, source, status='미검증'):
        family = ('hybrid' if 'volume_spike' in name and name.startswith(('heikin','frvp')) else
                  'volume' if name.startswith('volume_spike') else name)
        rows.append(dict(family=family, name=name, config=config, metrics=summary(m),
                         source=source, status=status))
    f=SOURCES[0]
    for s in sources[f]['strategies']:
        add(s['name'],s['baseline_config'],s['baseline'],f)
        for r in s['sweep']: add(s['name'],r['config'],r['metrics'],f)
    f=SOURCES[1]
    for r in sources[f]['baselines']+sources[f]['sweep']+sources[f]['supplemental_baselines']:
        add(r['name'],dict(dd_trigger=r.get('dd_trigger')),r['metrics'],f)
    f=SOURCES[2]
    for group in ['baselines','breaker','volatility','loose']:
        for r in sources[f][group]: add(r['name'],r['config'],r['metrics'],f)
    f=SOURCES[3]
    for r in sources[f]['winners']:
        add(r['name'],r['config'],r['full'],f,'§16 기각' if r['name']=='heikin_ashi' else '§16 일부검증; 신규 4항목 미검증')
    for r in sources[f]['sensitivity']:
        add('heikin_ashi',dict(dd_trigger=r['dd_trigger'],resume_mode='btc_sma50'),r['metrics'],f,'§16 기각 계열')
    for f in SOURCES[4:6]:
        d=sources[f]; c=d['champion']
        add('volume_spike_cap5',{},c['full'],f,'§17 기존강건성 기각 / §18 알파 통과 / §19 통계검증 통과')
        for par, series in c['sensitivity'].items():
            for r in series['points']: add('volume_spike_cap5',{par:r['value']},r['metrics'],f)
        for r in d.get('ensembles',[]):
            add('ensemble',dict(names=r['names'],weights=r['weights']),r['full'],f,'§17 기각')
            for p in r['sensitivity']['points']:
                add('ensemble',dict(names=r['names'],weights=p['weights']),p['metrics'],f,'§17 기각 계열; 해당 변형 4항목 미검증')
        if 'btc_confirmation' in d:
            add('heikin_ashi',dict(dd_trigger=.25,resume_mode='btc_sma50',btc_confirmation=3),d['btc_confirmation']['full'],f,'§17 재개검증만; 4항목 미검증')
    f=SOURCES[6]
    for r in sources[f]['caps']:
        add('volume_spike_cap5',dict(symbol_trade_share_cap=r['cap']),r['metrics'],f,'§18 쏠림완화 실패')
    add('volume_spike_cap5',{},sources[SOURCES[7]]['baseline'],SOURCES[7],
        '§17 기존강건성 기각 / §18 알파 통과 / §19 통계검증 통과')
    # Collapse repeated artifacts, retaining all provenance and all status evidence.
    unique={}
    for r in rows:
        key=json.dumps([r['family'],r['name'],r['config'],r['metrics']],sort_keys=True)
        if key not in unique: unique[key]=dict(r, sources=[r['source']], statuses=[r['status']])
        else:
            unique[key]['sources'].append(r['source']); unique[key]['statuses'].append(r['status'])
    best=[]
    for family in sorted({r['family'] for r in rows}):
        candidates=[r for r in unique.values() if r['family']==family]
        b=max(candidates,key=lambda r:(r['metrics']['sharpe'],r['metrics']['cagr'],r['status']!='미검증'))
        # Robustness of another parameter variant must never transfer automatically.
        if family=='heikin_ashi' and b['config'].get('dd_trigger')==.25:
            b['status']='§16 하이킨아시 CB25%+BTC재개 기각 (동일 변형)'
        if family=='frvp' and b['config'].get('dd_trigger')==.2 and b['config'].get('cooldown_days')==60:
            b['status']='미검증 (최종 4항목); §16 기간·집중도 일부검증 / §18 알파 6/8'
        best.append(b)
    best.sort(key=lambda r:(-r['metrics']['sharpe'],-r['metrics']['cagr']))
    return sources, list(unique.values()), best[:10], best


def core(family, frames):
    if family=='volume': return volume_prep(frames)
    return {s:importlib.import_module(f'app.{family}_signal_core').find_signals(df) for s,df in frames.items()}


def filtered(prepped, frames, kind):
    out={}
    for s, p in prepped.items():
        df=p.copy(); f=frames[s]; c=f.Close
        if kind=='none': mask=pd.Series(True,index=c.index)
        elif kind=='sma50': mask=c>c.rolling(50).mean()
        elif kind=='sma200': mask=c>c.rolling(200).mean()
        elif kind=='rsi70': mask=ta.rsi(c,length=14)<70
        elif kind=='atr10': mask=ta.atr(f.High,f.Low,c,length=14)/c<.10
        elif kind=='trend7': mask=(c.rolling(7).mean()>c.rolling(28).mean())
        else: raise ValueError(kind)
        df['SIGNAL']=df.SIGNAL & mask.fillna(False)
        out[s]=df
    return out


def variants(rep):
    cfg={k:v for k,v in rep['config'].items() if k in ['timing','stop','tp','hold_days','selection','dd_trigger','resume_mode','cooldown_days','sizing','target_vol','weight_cap'] and v is not None}
    # New variations around each historical family representative; no unchanged control counts.
    configs=[]
    for k in [4,6,12,16]: configs.append(('none',dict(cfg,top_k=k)))
    for days in [7,14,30,60]: configs.append(('none',dict(cfg,hold_days=days)))
    for kind in ['sma50','sma200','rsi70','atr10','trend7']: configs.append((kind,cfg.copy()))
    configs.append(('none',dict(cfg,timing='confirm_open' if cfg.get('timing','next_open')=='next_open' else 'next_open')))
    for target in [.6,.8]: configs.append(('none',dict(cfg,sizing='inverse_vol',target_vol=target,weight_cap=.35)))
    # Unique operational definitions only: all selection ignores top_k unless inverse sizing.
    seen=set(); result=[]
    for kind, c in configs:
        if c.get('selection')=='all' and c.get('sizing','equal')=='equal': c.pop('top_k',None)
        token=json.dumps([kind,c],sort_keys=True)
        if token not in seen: result.append((kind,c)); seen.add(token)
    return result


def resolved(config, frames):
    c=config.copy()
    if c.get('resume_mode')=='btc_sma50': c['btc_resume']=(frames['BTC'].Close>frames['BTC'].Close.rolling(50).mean()).to_dict()
    return c


def dominates(m):
    return m['cagr']>62.35 and m['mdd']<53.38 and m['sharpe']>1.165


def robustness(p, config, frames):
    full, records, _, _, _=ledger_run(p,config)
    # Eight actual two-year windows: earlier audits used 2 broad splits + 6 two-year windows.
    periods=[(f'{y}-09-08',f'{y+2}-09-07') for y in range(2019,2024)]
    periods += [('2020-10-06','2022-10-05'),('2023-10-06','2025-10-05'),('2024-10-06','2026-10-05')]
    cells=[]
    for start,end in periods:
        sub={s:df.loc[start:end] for s,df in p.items() if len(df.loc[start:end])}
        m=simulate_portfolio(sub,**config); b=btc_period(frames['BTC'],start,end)
        cells.append(dict(start=start,end=end,metrics=summary(m),btc_cagr=b['cagr'],alpha=m['cagr']-b['cagr']))
    alpha_pass=sum(r['alpha']>0 for r in cells)>=7
    conc=concentration(records); sy=symbols(records)
    concentration_pass=conc['10']['net_pct']<=103 and sy['net_pct']<=88
    data=prepare(p); eligible=np.isfinite(data[2]['Open'][:-1]) & np.isfinite(data[2]['Open'][1:])
    probability=len(records)/eligible.sum(); trials=[]
    for seed in range(820000,820300):
        trials.append(dict(seed=seed,**summary(simulate_portfolio(p,prepared=random_data(data,seed,probability),**config))))
        if len(trials)%50==0: print('ROBUST MC',len(trials),flush=True)
    tests={}
    for k in ['cagr','sharpe']:
        values=np.array([t[k] for t in trials]); tests[k]=dict(p=float((1+(values>=full[k]).sum())/301),q95=float(np.percentile(values,95)))
    mc_pass=all(t['p']<.05 for t in tests.values())
    boot=block_bootstrap(records,full); votes=[bool(alpha_pass),bool(concentration_pass),bool(mc_pass),bool(boot['significant'])]
    return dict(periods=cells,alpha_positive=sum(r['alpha']>0 for r in cells),concentration=conc,symbols=sy,
                monte_carlo=dict(probability=probability,trials=trials,tests=tests),bootstrap=boot,votes=votes,
                verdict='통과' if sum(votes)>=3 else '기각',trades=records)


def causal_audit(family, rep, frames):
    full=core(family,frames)
    checks=0
    for kind in ['none','sma50','sma200','rsi70','atr10','trend7']:
        allp=filtered(full,frames,kind)
        for s in ['BTC','ETH','SOL']:
            n=len(frames[s])//2
            small=core(family,{s:frames[s].iloc[:n]})
            short=filtered(small,{s:frames[s].iloc[:n]},kind)
            pd.testing.assert_frame_equal(allp[s].iloc[:n],short[s]); checks+=1
    # Every variant: truncated execution and future data mutation preserve prior online decisions.
    for kind,c in variants(rep):
        p=filtered(full,frames,kind); cfg=resolved(c,frames)
        live=simulate_portfolio(p,return_trace=True,**cfg)
        cutoff=pd.Timestamp('2024-06-30',tz='UTC')
        sub={s:df.loc[:cutoff] for s,df in p.items() if len(df.loc[:cutoff])}
        short=simulate_portfolio(sub,return_trace=True,**cfg)
        assert short['trace'][:-1]==live['trace'][:len(short['trace'])-1]
        assert short['allocations']==[a for a in live['allocations'] if pd.Timestamp(a['date'])<=cutoff]
        changed={s:df.copy() for s,df in p.items()}
        for df in changed.values():
            future=df.index>cutoff
            df.loc[future,['Open','High','Low','Close']]*=3
            df.loc[future,'SIGNAL']=True; df.loc[future,'VOL_RATIO']=999
        altered=simulate_portfolio(changed,return_trace=True,**cfg)
        assert altered['trace'][:len(short['trace'])-1]==short['trace'][:-1]; checks+=2
        assert all(pd.Timestamp(a['known_through'])<pd.Timestamp(a['date']) for a in live['allocations'])
    return checks


def git_round(section, files, output):
    attempts=[]
    for _ in range(2):
        p=subprocess.run(['git','add',*files],cwd=ROOT,text=True,capture_output=True)
        attempts.append(dict(action='add',code=p.returncode,output=p.stdout+p.stderr))
        if p.returncode==0: break
    if p.returncode==0:
        p=subprocess.run(['git','commit','-m',f'research: 라운드8 섹션{section} 패밀리 탐색 및 검증'],cwd=ROOT,text=True,capture_output=True)
        attempts.append(dict(action='commit',code=p.returncode,output=p.stdout+p.stderr))
        if p.returncode==0:
            h=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
            p=subprocess.run(['git','push','origin','main'],cwd=ROOT,text=True,capture_output=True)
            attempts.append(dict(action='push',code=p.returncode,output=p.stdout+p.stderr))
            output['git'].append(dict(section=section,hash=h,attempts=attempts)); save(output); return
    output['git'].append(dict(section=section,hash=None,status='커밋 보류, 변경파일은 작업트리에 남음',attempts=attempts))
    save(output)
    with DOC.open('a') as f: f.write('\n- Git: 커밋 보류, 변경파일은 작업트리에 남음. git add 2회 재시도 실패; 오류는 결과 JSON git 항목 참조.\n')


def table(row):
    m=row['metrics']
    return f"{m['cagr']:+.2f}% | {m['mdd']:.2f}% | {m['sharpe']:.3f} | {m['trades']}"


def run():
    sources, inventory, top, allbest=aggregate()
    frames, manifest, skipped=load_data()
    assert len(frames)==45 and not skipped
    assert all(s['manifest']==manifest for s in sources.values())
    d=dict(manifest=manifest,source_hashes={f:hashlib.sha256((ROOT/'docs'/f).read_bytes()).hexdigest() for f in SOURCES},
           historical_inventory=inventory,all_family_representatives=allbest,top10=top,experiments=[],git=[],sections=[21],status='탐색중',
           methodology='45-symbol cached universe; 2019-09-08..2026-10-05; one-way fee 0.04%; next/confirmed open only; unchanged shared engine; no funding/slippage/survivorship correction')
    assert '## 21.' not in DOC.read_text()
    with DOC.open('a') as f:
        f.write('\n\n## 21. 상위 10개 패밀리 집계 + 자유탐색 루프 시작 (2026-10-07, 라운드8)\n\n')
        f.write(f'- 지정한 결과 JSON 8개 전체를 읽었다. 변형·재검증 중복 행을 포함한 출처는 JSON에 보존했다. 집계 행 {len(inventory)}개, 패밀리 {len(allbest)}개. 기간별 셀·랜덤대조군·leave-out 진단은 전략 후보 순위에 포함하지 않았다.\n')
        f.write('- Sharpe 내림차순, 동률이면 CAGR 내림차순. 거래량 cap3/5, CB 임계값·재개·사이징은 원신호 패밀리로 묶고, 두 하이브리드는 하이브리드로, N2/N3 분리자본은 앙상블로 묶었다. 하위 패밀리를 끼워 넣어 순위를 바꾸지 않았다.\n\n| 순위 | 패밀리 / 대표 파라미터 | CAGR | MDD | Sharpe | 거래수 | 이전 검증 상태 | 출처 |\n|---:|---|---:|---:|---:|---:|---|---|\n')
        for i,r in enumerate(top,1): f.write(f"| {i} | {LABELS[r['family']]} / {json.dumps(r['config'],ensure_ascii=False)} | {table(r)} | {r['status']} | {r['source']} |\n")
        f.write('\n- 통계검증 통과와 기존 운용 강건성 기각은 서로 다른 판정이다. 다른 변형의 검증 결과를 대표 변형에 자동 전이하지 않는다.\n- 신규 4검증: 실제 2년 창8개 중 알파 양수7개, 집중도103%/88% 이하, 랜덤300회 p<0.05 두 지표, 거래블록20건×1000회 CI 하한>0. 3/4 통과시 즉시 A 복귀. 기존 8창은 넓은 분할2개+2년6개이므로 신규 검사에서는 2년 창2개를 추가하여 실제 2년8개로 맞춘다.\n')
    save(d)
    subprocess.run(['python3','-m','py_compile','app/crypto_round8_research.py'],cwd=ROOT,check=True)
    git_round(21,['app/crypto_round8_research.py','docs/round8-results-2026-10-07.json','docs/전략-백테스트-종합.md'],d)
    for index,rep in enumerate(top):
        family=rep['family']; section=22+index
        print('FAMILY',index+1, family,rep['config'],flush=True)
        rows=[]
        if family=='ensemble':
            names=['volume','heikin_ashi','frvp']; prepared=[core(n,frames) for n in names]
            runs=[ledger_run(p,{}) for p in prepared]
            # Predeclared asymmetric initial shares; no ex-post weight selection.
            weightsets=[[w,1-w] for w in [.1,.2,.25,.35,.45,.55,.65,.75,.8,.9]]
            weightsets += [[.6,.3,.1],[.6,.1,.3],[.8,.1,.1],[.2,.6,.2],[.2,.2,.6]]
            for weights in weightsets:
                result=combine(runs[:len(weights)],weights)
                m=result[0]; row=dict(family=family,config=dict(names=names[:len(weights)],weights=weights),metrics=summary(m),dominates=dominates(m))
                # Ensemble audits require matched weighted random ledgers; refuse unvalidated A.
                if row['dominates']: raise RuntimeError('Ensemble dominance requires matching bucket robustness extension before continuation')
                rows.append(row)
            # Fixed initial weights combine causal component curves; independent prefix at calendar boundary.
            cutoff=pd.Timestamp('2024-06-30',tz='UTC')
            subruns=[ledger_run({s:df.loc[:cutoff] for s,df in p.items() if len(df.loc[:cutoff])},{}) for p in prepared]
            for weights in weightsets:
                live=combine(runs[:len(weights)],weights); short=combine(subruns[:len(weights)],weights)
                np.testing.assert_allclose(live[4][:len(short[4])-1],short[4][:-1],atol=1e-10)
            checks=len(weightsets)
        else:
            p=core(family,frames)
            checks=causal_audit(family,rep,frames)
            for kind,config in variants(rep):
                prepped=filtered(p,frames,kind); cfg=resolved(config,frames)
                m=simulate_portfolio(prepped,**cfg)
                row=dict(family=family,filter=kind,config=config,metrics=summary(m),dominates=dominates(m))
                if row['dominates']:
                    print('DOMINATING',family,kind,config,summary(m),flush=True)
                    row['robustness']=robustness(prepped,cfg,frames)
                rows.append(row)
                if row.get('robustness',{}).get('verdict')=='통과': d['status']='복귀조건 A 달성'; break
        assert len(rows)>=10 or d['status']=='복귀조건 A 달성'
        assert all(np.isfinite(list(r['metrics'].values())).all() and -100<r['metrics']['cagr']<1000 and 0<=r['metrics']['mdd']<=100 and r['metrics']['trades']>0 for r in rows)
        d['experiments'].extend(rows); d['sections'].append(section)
        with DOC.open('a') as f:
            f.write(f'\n\n## {section}. {LABELS[family]} 세부 변형 탐색 (2026-10-07, 라운드8-{index+1})\n\n')
            f.write(f'- 신규 {len(rows)}조합, 누적 {len(d["experiments"])}조합 / {len(set(r["family"] for r in d["experiments"]))}패밀리. 동일 캐시·기간·수수료, 공통 엔진 수정 없음. 신규 prefix/미래변형 검증 {checks}개 통과. 신호 당일 종가 체결 가정은 사용하지 않았다. 7일/28일 추세는 일봉 이동평균이며 주봉 리샘플이 아니다.\n\n| 필터 / 설정 | CAGR | MDD | Sharpe | 거래수 | 세 축 우위 / 강건성 |\n|---|---:|---:|---:|---:|---|\n')
            for r in sorted(rows,key=lambda r:(-r['metrics']['sharpe'],-r['metrics']['cagr'])):
                verdict=r.get('robustness',{}).get('verdict','해당 없음')
                f.write(f"| {r.get('filter','고정초기비중')} / {json.dumps(r['config'],ensure_ascii=False)} | {table(r)} | {'우위' if r['dominates'] else '미충족'} / {verdict} |\n")
            for r in rows:
                if 'robustness' not in r: continue
                b=r['robustness']; f.write(f"\n### {section}-1. 세 축 우위 후보 자체 강건성 검증\n\n- 설정: {r.get('filter')} / {json.dumps(r['config'],ensure_ascii=False)}. 판정 **{b['verdict']}**, {sum(b['votes'])}/4 통과.\n- 기간분리: 알파 양수 {b['alpha_positive']}/8, {'통과' if b['votes'][0] else '미통과'}.\n\n| 시작 | 종료 | 후보 CAGR | BTC CAGR | 차이 |\n|---|---|---:|---:|---:|\n")
                for cell in b['periods']: f.write(f"| {cell['start']} | {cell['end']} | {cell['metrics']['cagr']:+.2f}% | {cell['btc_cagr']:+.2f}% | {cell['alpha']:+.2f}%p |\n")
                f.write(f"\n- 집중도: 상위10건 {b['concentration']['10']['net_pct']:.4f}% / 상위5종목 {b['symbols']['net_pct']:.4f}%, {'통과' if b['votes'][1] else '같은 한계 공유; 미통과'}.\n- 랜덤진입300회: {json.dumps(b['monte_carlo']['tests'],ensure_ascii=False)}, {'통과' if b['votes'][2] else '미통과'}. 후보와 동일 슬롯·보유·필터후 OHLC·청산·CB·사이징; 빈도=거래수/유효 연속 종목일. 난수 신호는 필터를 다시 강제하지 않으며 무작위진입 대조군에 해당한다.\n- 블록20건×1000회 거래단위 Sharpe CI95 {b['bootstrap']['ci95']}, {'통과' if b['votes'][3] else '미통과'}. 포트폴리오 일별 Sharpe CI가 아닌 §19 거래단위 근사.\n")
            f.write('\n- 검증: 신규 모듈 py_compile, 45종목 manifest 일치, 실제 prefix 실행·과거 확정시간, 유한 지표·거래수>0·MDD0~100 확인. 상세 재현 설정·결과·원장·난수 seed·부트스트랩 시퀀스는 round8 결과 JSON에 보존.\n')
        save(d)
        subprocess.run(['python3','-m','py_compile','app/crypto_round8_research.py'],cwd=ROOT,check=True)
        git_round(section,['app/crypto_round8_research.py','docs/round8-results-2026-10-07.json','docs/전략-백테스트-종합.md'],d)
        print('PROGRESS',len(d['experiments']),len(set(r['family'] for r in d['experiments'])),flush=True)
        if d['status']=='복귀조건 A 달성': break
    if d['status']!='복귀조건 A 달성':
        assert len(set(r['family'] for r in d['experiments']))>=10 and all(sum(r['family']==f for r in d['experiments'])>=10 for f in {r['family'] for r in d['experiments']})
        d['status']='복귀조건 B 달성'
    save(d)
    with DOC.open('a') as f: f.write(f"\n**{d['status']}**. 신규 조합 {len(d['experiments'])}개, 패밀리 {len(set(r['family'] for r in d['experiments']))}개. 반복탐색 선택편향·미관측 OOS 부재·슬리피지/펀딩비/생존편향 한계는 남는다.\n")
    print(d['status'],flush=True)


if __name__=='__main__': run()
