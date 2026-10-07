"""Round11 predeclared elimination grid, offline provenance and strict five gates."""
import json
import subprocess
import sys
import numpy as np
import pandas as pd
from app.crypto_technical_ict_research import ROOT, load_data
from app.crypto_round8_research import core
from app.crypto_round7_research import summary, random_data, block_bootstrap
from app.crypto_round4_robustness import concentration
from app.crypto_round6_research import symbols, btc_period
from app.crypto_round10_research import transition_stats
from app.technical_portfolio_engine import prepare, simulate_portfolio, simulate_research_portfolio
from app.technical_signal_common import ta

PATH = ROOT/'docs/round11-results-2026-10-07.json'
DOC = ROOT/'docs/전략-백테스트-종합.md'
NAMES = {1:'숏·롱숏 동시진입',2:'주간·월간 신규진입 주기',3:'동적 거래량·대형주 유니버스',
         5:'3신호 합의투표',6:'ATR 챈들리어 트레일링스탑',7:'시장 변동성 레짐',
         8:'과거 상관클러스터 분산',9:'동적 TOP_K'}
AUDIT_INPUTS = None


def save(out):
    PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2, allow_nan=False,
                               default=lambda v: v.item() if isinstance(v,np.generic) else str(v)))


def configs():
    return {
        1:[dict(family=f, top_k=k, long_short=True) for f,k in
           [('volume',8),('heikin_ashi',8),('frvp',8),('volume',4),('volume',12)]],
        2:[dict(family='volume', calendar=c, hold_days=h) for c,h in
           [('weekly',20),('monthly',20),('weekly',7),('monthly',30)]],
        3:[dict(family='volume', universe=u) for u in ['volume10','volume20','volume30','large10']],
        5:[dict(family='volume', vote=v) for v in ['same2','recent3_2','recent5_2','same3']],
        6:[dict(family=f, trailing=t, hold_days=10000) for f,t in
           [('volume',2.),('volume',2.5),('volume',3.),('heikin_ashi',2.),('heikin_ashi',3.)]],
        7:[dict(family='volume', vol_quantile=q, low_scale=s) for q,s in
           [(.5,.5),(.75,.5),(.75,.25),(.9,0.)]],
        8:[dict(family='volume', correlation=t, cluster_cap=c) for t,c in
           [(.6,.25),(.7,.25),(.8,.25),(.7,.375)]],
        9:[dict(family='volume', dynamic=v) for v in ['count4_12','count4_16','strength4_12','strength6_16']],
    }


def monthly_labels(frames, threshold):
    """Connected components of trailing90-day positive correlations >= threshold.

    Monthly refresh at completed month's final day; valid pairs need60 overlaps.
    No backward fill, no whole-sample clustering or future membership selection.
    """
    prices = pd.DataFrame({s:f.Close for s,f in frames.items()}).sort_index()
    returns = prices.pct_change(fill_method=None)
    labels, previous = {}, {}
    for d in prices.index:
        if (d+pd.Timedelta(days=1)).month != d.month:
            corr = returns.loc[:d].tail(90).corr(min_periods=60)
            parent = {s:s for s in prices.columns}
            def root(s):
                while parent[s] != s:
                    s = parent[s]
                return s
            for x in prices.columns:
                for y in prices.columns:
                    if x < y and np.isfinite(corr.loc[x,y]) and corr.loc[x,y] >= threshold:
                        a,b = root(x),root(y)
                        parent[max(a,b)] = min(a,b)
            previous = {s:root(s) for s in prices.columns}
        labels[d] = previous.copy()
    return labels


def build(config, frames, cores):
    p = {s:f.copy() for s,f in cores[config['family']].items()}
    dates = sorted(set().union(*(f.index for f in p.values())))
    kwargs = {k:config[k] for k in ['top_k','hold_days','long_short','trailing','cluster_cap'] if k in config}
    state = None
    if config.get('trailing'):
        # volume_prep historically stores ATR14=0 because champion has no stop.
        # Compute real causal ATR for this experiment, never interpret0 as data.
        for s,f in p.items():
            price = frames[s]
            f['ATR14'] = ta.atr(price.High,price.Low,price.Close,length=14)
    if config.get('long_short'):
        for f in p.values():
            # Opposite signal: no positive entry signal, lowest causal strength.
            f['SHORT_SIGNAL'] = (~f.SIGNAL.astype(bool)) & f.VOL_RATIO.notna()
    if 'calendar' in config:
        kind = config['calendar']
        kwargs['calendar'] = {d:(d.weekday()==0 if kind=='weekly' else d.day==1) for d in dates}
    if 'universe' in config:
        u = config['universe']
        if u == 'large10':
            # Fixed research basket, NOT historical point-in-time market-cap top10.
            allowed = set(['BTC','ETH','SOL','BNB','XRP','DOGE','ADA','TRX','AVAX','LINK'])
            for s,f in p.items():
                if s not in allowed:
                    f['SIGNAL'] = False
        else:
            n = int(u.removeprefix('volume'))
            volume = pd.DataFrame({s:(f.Volume*f.Close).rolling(30,min_periods=20).mean()
                                   for s,f in frames.items()}).reindex(dates)
            membership, current = {}, set()
            for d in dates:
                if (d+pd.Timedelta(days=1)).month != d.month:
                    current = set(volume.loc[d].dropna().sort_values(ascending=False,kind='stable').head(n).index)
                membership[d] = current.copy()
            for s,f in p.items():
                f['SIGNAL'] &= pd.Series({d:s in membership[d] for d in f.index})
    if 'vote' in config:
        window = {'same2':1,'recent3_2':3,'recent5_2':5,'same3':1}[config['vote']]
        needed = 3 if config['vote']=='same3' else 2
        states = []
        for s,f in p.items():
            votes = sum(cores[n][s].SIGNAL.astype(int).rolling(window,min_periods=1).max()
                        for n in ['volume','heikin_ashi','frvp'])
            f['SIGNAL'] = votes >= needed
            states.append(f.SIGNAL.reindex(dates,fill_value=False).astype(int).to_numpy())
        # Exact eligible vote-mask transitions, rather than just signal counts.
        mask = np.array(states).T
        ids, tokens = [], {}
        for row in mask:
            token = tuple(row)
            ids.append(tokens.setdefault(token,len(tokens)))
        state = pd.Series(ids,index=dates)
    if 'vol_quantile' in config:
        rv = frames['BTC'].Close.pct_change(fill_method=None).rolling(20).std()*np.sqrt(365)
        threshold = rv.expanding(min_periods=200).quantile(config['vol_quantile'])
        high = (rv > threshold).where(threshold.notna(),False)
        scale = pd.Series(np.where(high,config['low_scale'],1.),index=rv.index)
        kwargs['scales'] = scale.to_dict()
        state = high.astype(int)
    if 'correlation' in config:
        kwargs['clusters'] = monthly_labels(frames, config['correlation'])
    if 'dynamic' in config:
        signals = pd.DataFrame({s:f.SIGNAL for s,f in p.items()}).fillna(False)
        count = signals.sum(axis=1)
        if config['dynamic'].startswith('count'):
            lower,upper = (4,12) if config['dynamic']=='count4_12' else (4,16)
            k = count.clip(lower,upper).astype(int)
        else:
            ratios = pd.DataFrame({s:f.VOL_RATIO for s,f in p.items()}).where(signals)
            strength = ratios.mean(axis=1).fillna(0)
            k = pd.Series(np.where(strength>=5,12,4) if config['dynamic']=='strength4_12'
                          else np.where(strength>=4,16,6),index=strength.index)
        kwargs['dynamic_k'] = k.to_dict()
    data = prepare(p)
    if config.get('long_short'):
        data[2]['SHORT_SIGNAL'] = np.array([p[s].SHORT_SIGNAL.reindex(data[0]).to_numpy(dtype=float)
                                          for s in data[1]]).T
    return p, data, kwargs, state


def audit(config, frames, cores, full):
    global AUDIT_INPUTS
    cutoff = pd.Timestamp('2024-06-30',tz='UTC')
    if AUDIT_INPUTS is None:
        smallframes = {s:f.loc[:cutoff] for s,f in frames.items() if len(f.loc[:cutoff])}
        smallcores = {n:core(n,smallframes) for n in cores}
        alteredframes = {s:f.copy() for s,f in frames.items()}
        for f in alteredframes.values():
            future = f.index > cutoff
            f.loc[future,['Open','High','Low','Close']] *= 3
            f.loc[future,'Volume'] *= 7
        alteredcores = {n:core(n,alteredframes) for n in cores}
        AUDIT_INPUTS = smallframes,smallcores,alteredframes,alteredcores
    smallframes,smallcores,alteredframes,alteredcores = AUDIT_INPUTS
    p,data,kw,_ = build(config,smallframes,smallcores)
    small = simulate_research_portfolio(p,prepared=data,return_trace=True,**kw)
    assert small['trace'][:-1] == full['trace'][:len(small['trace'])-1]
    assert small['allocations'] == [e for e in full['allocations'] if pd.Timestamp(e['date'])<=cutoff]
    p,data,kw,_ = build(config,alteredframes,alteredcores)
    changed = simulate_research_portfolio(p,prepared=data,return_trace=True,**kw)
    assert changed['trace'][:len(small['trace'])-1] == small['trace'][:-1]
    assert all(pd.Timestamp(e['known_through']) < pd.Timestamp(e['date']) for e in full['allocations'])
    return 4


def robust(config, frames, cores, full, thrashing):
    old = json.loads((ROOT/'docs/round4-results-2026-10-07.json').read_text())['periods']
    recent = json.loads((ROOT/'docs/round9-results-2026-10-07.json').read_text())['periods']
    actual = [(c['start'],c['end']) for c in recent]
    p,data,kw,_ = build(config,frames,cores)
    cells = {}
    for start,end in dict.fromkeys([tuple(c) for c in old]+actual):
        sub = {s:f.loc[start:end] for s,f in p.items() if len(f.loc[start:end])}
        sliced = prepare(sub)
        if config.get('long_short'):
            sliced[2]['SHORT_SIGNAL'] = np.array([sub[s].SHORT_SIGNAL.reindex(sliced[0]).to_numpy(dtype=float) for s in sliced[1]]).T
        m = simulate_research_portfolio(sub,prepared=sliced,**kw)
        b = btc_period(frames['BTC'],start,end)['cagr']
        cells[(start,end)] = dict(start=start,end=end,metrics=summary(m),btc_cagr=b,alpha=m['cagr']-b)
    records = full['records']
    conc,sy = concentration(records),symbols(records)
    eligible = np.isfinite(data[2]['Open'][:-1]) & np.isfinite(data[2]['Open'][1:])
    probability = len(records)/eligible.sum()
    trials = []
    for seed in range(1100000,1100300):
        random = random_data(data,seed,probability)
        if config.get('long_short'):
            rng = np.random.default_rng(seed+300)
            random[2]['SHORT_SIGNAL'] = (rng.random((len(data[0]),len(data[1]))) < probability) & ~random[2]['SIGNAL']
        trials.append(dict(seed=seed,**summary(simulate_research_portfolio(p,prepared=random,**kw))))
    tests = {k:dict(p=float((1+sum(t[k]>=full[k] for t in trials))/301)) for k in ['cagr','sharpe']}
    boot = block_bootstrap(records,full)
    legacy = [cells[tuple(c)] for c in old]
    current = [cells[c] for c in actual]
    votes = [sum(c['alpha']>0 for c in current)>=7 and sum(c['alpha']>0 for c in legacy)>=7,
             conc['10']['net_pct']<=103 and sy['net_pct']<=88,
             all(t['p']<.05 for t in tests.values()),bool(boot['significant']),
             thrashing is None or thrashing['within']['5']['pct']<=50]
    return dict(periods=current,legacy_periods=legacy,concentration=conc,symbols=sy,
                alpha_positive=sum(c['alpha']>0 for c in current),
                legacy_alpha_positive=sum(c['alpha']>0 for c in legacy),
                monte_carlo=dict(probability=probability,trials=trials,tests=tests),
                bootstrap=boot,thrashing=thrashing,votes=[bool(v) for v in votes],
                verdict='통과' if all(votes) else '기각')


def git_section(section, out):
    files = ['app/technical_portfolio_engine.py','app/round11_portfolio.py',
             'app/crypto_round11_research.py','app/verify_round11.py',str(PATH.relative_to(ROOT)),str(DOC.relative_to(ROOT))]
    files += [str(p.relative_to(ROOT)) for p in sorted((ROOT/'docs').glob('round11-*')) if p.name != PATH.name]
    attempts, h, pushed = [], None, False
    for action,args in [('add',['git','add',*files]),
                        ('commit',['git','commit','-m',f'research: 라운드11 섹션{section} 시나리오 소거 및 검증']),
                        ('push',['git','push','origin','main'])]:
        for _ in range(3):
            r = subprocess.run(args,cwd=ROOT,text=True,capture_output=True,timeout=60)
            attempts.append(dict(action=action,code=r.returncode,output=r.stdout+r.stderr))
            if r.returncode == 0:
                if action == 'commit':
                    h = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
                if action == 'push':
                    pushed = True
                break
        if r.returncode != 0:
            break
    entry = dict(section=section,hash=h,pushed=pushed,status='성공' if pushed else '푸시 보류' if h else '커밋 보류',attempts=attempts)
    out['git'].append(entry)
    save(out)
    with (ROOT/'docs/round11-git-2026-10-07.txt').open('a') as f:
        f.write(json.dumps(entry,ensure_ascii=False,indent=2)+'\n')
    if not pushed:
        with DOC.open('a') as f:
            f.write(f'\n- Git §{section}: {entry["status"]}, 해시 {h or "없음"}. 최초+2회 재시도 오류는 round11-git 로그 참조.\n')


def table(m):
    return f'{m["cagr"]:+.4f}% | {m["mdd"]:.4f}% | {m["sharpe"]:.6f} | {m["trades"]}'


def write_section(section, category, rows):
    with DOC.open('a') as f:
        f.write(f'\n\n## {section}. {NAMES[category]} (2026-10-07, 라운드11)\n\n')
        descriptions = {
            1:'상위 양의신호 롱 / 양의신호 없는 하위강도 숏. TOP_K는 양쪽 합산4/8/12슬롯, 각 신규 배치 50:50 동시진입·동일만기. 총 증거금≤NAV, 숏 매도대금 재사용 없음. 가격 하락시 숏 이익·상승시 손실, 진입/청산 수수료 각각 차감. 최초 달러중립이며 보유중 가격변화로 순노출이 이동한다. 베타중립 또는 상시 달러중립이라고 주장하지 않는다. 실제 유지증거금/강제청산·시장충격 미모델링, NAV≤0이면 지급불능 기각. 양의펀딩은 숏 수령/음의펀딩은 숏 지불이나 공정비교 비용0.',
            2:'UTC 월요일/월초1일 시가에만 전일신호 신규진입. 기존 포지션은 정해진20일/7일/30일 만기 종가 청산, 강제 전체 리밸런싱은 하지 않는다. 일정 자체만 미리 알 수 있고 미래 신호는 읽지 않는다.',
            3:'매월 마지막 완료봉에서 과거30일 Close×Volume 평균 상위10/20/30종목 선정, 다음달부터 적용. 최초 월말 전 신규진입 없음. large10은 BTC/ETH/SOL/BNB/XRP/DOGE/ADA/TRX/AVAX/LINK 고정 바스켓이며 역사적 시총상위10 실측 아님. 레포 다른 유니버스 소스 검색, OHLCV 캐시는 기존45종목만 존재하므로 검증 가능한 확대(c)는 생략. 현재45종목의 생존편향은 제거되지 않는다.',
            5:'volume+HA+FRVP의 동봉2/3·과거3일2/3·과거5일2/3·동봉3/3 투표. 각 신호는 현재까지 확정된 봉만 사용하고 VOL_RATIO는 챔피언으로 통일. 스래싱은 전체종목의 진입허용 투표마스크가 바뀐 날짜에서 다음 변경까지5일 이내 비율, 마지막 변경을 분모에 포함.',
            6:'ATR14×2/2.5/3. 진입가격−배수×전일ATR로 최초 보호선, 이후 진입후 누적 고가−현재 완료ATR에서 기존선과 큰 값으로 다음날 보호선 갱신. 현재일 고가로 현재일 저가 청산하지 않는다. 갭은 시가/일중은 보호선, 기간상한10000일로 고정20일 청산 대체, 마지막 데이터 종가 강제청산.',
            7:'BTC20일 수익률 표준편차×√365 대 과거확장분포(최소200유효값) 50/75/90분위. 고변동 시 신규진입0/25/50%, 저변동100%, 임계값 워밍업은100%. 기존 보유 미재조정. BTC 추세방향과 무관한 변동성 수준 축. 확장분포는 판단일 현재까지만 포함. 이진 변동성 상태변경의5일 스래싱 검사.',
            8:'매월말 과거90일 일수익률 상관(최소60중첩)≥0.6/0.7/0.8 연결성분 군집. 같은 군집 기존 시가평가+신규예산을 NAV25%/37.5%로 제한, 이후 가격변동으로 상한 초과시 강제매도 없음. 현재 군집으로 기존 보유를 재분류. 군집 미확정은 개별종목 군집.',
            9:'전일 신호수 clip(4,12)/clip(4,16), 신호종목 평균 VOL_RATIO≥5면12 아니면4 / ≥4면16 아니면6. 신규예산 NAV/당일K, 기존보유 K초과시 새진입0·기존보유 정상만기. 현재일 신호나 전체기간 최대값을 사용하지 않는다.'}
        f.write('- '+descriptions[category]+'\n')
        f.write(f'- 신규 {len(rows)}변형, 원래 미펀딩 챔피언과 비교. 모든 조합 prefix 재산출·미래가격/거래량 변경·실행시간 감사4개 통과, 원장 P&L합=NAV−1 검증.\n\n| 설정 | CAGR | MDD | Sharpe | 거래 | 세축/판정 |\n|---|---:|---:|---:|---:|---|\n')
        for r in rows:
            f.write(f'| {json.dumps(r["config"],ensure_ascii=False)} | {table(r["metrics"])} | {"우위" if r["dominates"] else "미충족"}/{r.get("robustness",{}).get("verdict","기각")} |\n')
            if 'robustness' in r:
                b=r['robustness']
                f.write(f'\n- 강건성 {json.dumps(r["config"],ensure_ascii=False)}: 기간 알파 {b["alpha_positive"]}/8·원경계 {b["legacy_alpha_positive"]}/8, 집중도 {b["concentration"]["10"]["net_pct"]:.4f}%/{b["symbols"]["net_pct"]:.4f}%, 랜덤300회 {json.dumps(b["monte_carlo"]["tests"])}, 블록20건×1000 CI {b["bootstrap"]["ci95"]}, 스래싱 {json.dumps(b["thrashing"],ensure_ascii=False) if b["thrashing"] else "비레짐 규칙 해당없음"}, 5판정 {b["votes"]}: **{b["verdict"]}**. 두 기간표·거래원장·난수seed·블록표본은 원시JSON에 보존.\n')
        failures = [r for r in rows if not r['dominates']]
        f.write(f'\n- 소거 근거: 세축 미충족 {len(failures)}/{len(rows)}, 세축 우위 후보 {len(rows)-len(failures)}개는 5개 필수검사 전부통과시에만 승격. 명백한 세축 미달은 추가 강건성 검사하지 않았다.\n')


def run():
    frames,manifest,skipped = load_data()
    assert len(frames)==45 and not skipped
    cores = {n:core(n,frames) for n in ['volume','heikin_ashi','frvp']}
    baseline = simulate_portfolio(cores['volume'])
    assert summary(baseline)==json.loads((ROOT/'docs/round10-results-2026-10-07.json').read_text())['baseline']['volume']
    out = json.loads(PATH.read_text()) if PATH.exists() else dict(manifest=manifest,baseline=summary(baseline),experiments=[],sections=[],git=[],status='탐색중')
    assert out['manifest']==manifest
    if out['status'].startswith('복귀조건 '):
        raise RuntimeError('finished; use verifier')
    if 29 not in out['sections']:
        assert '## 29.' not in DOC.read_text()
        funding=[]
        for annual,slip in [(0.,0.),(.05,.0005),(.1095,.0005),(.1095,.001),(.15,.001)]:
            m = simulate_research_portfolio(cores['volume'],funding_annual=annual,slippage=slip,return_trace=True)
            if annual==slip==0:
                for k in summary(baseline):
                    assert abs(summary(m)[k]-summary(baseline)[k])<1e-8
            funding.append(dict(annual=annual,slippage=slip,metrics=summary(m),records=m['records']))
        out['funding']=funding
        with DOC.open('a') as f:
            f.write('\n\n## 29. 펀딩비·슬리피지 현실성 기준선 (2026-10-07, 라운드11 첫 작업)\n\n')
            f.write('- .screen_cache 전45파일은 일봉 OHLCV뿐, 펀딩비 캐시0. Binance fapi/v1/fundingRate 실접근은 curl DNS 실패(6: Could not resolve host). 과거 펀딩 실측 사용불가. [Binance 공식 펀딩 설명](https://www.binance.com/en/support/faq/detail/360033525031)의 기본 이자성분0.01%/8h→일0.03%×365=연10.95%를 중앙 비용 시나리오로 가정했다. 이는 실제 펀딩평균의 근거가 아니며 프리미엄에 따라 음/양, 계약별 정산간격4h/1h 가능. 5%/15%는 하한/상한 민감도 가정이다.\n')
            f.write('- 비용은 보유중 전일종가 명목금액에 일할 차감, 진입일은 시가명목×2/3일(00시 이후08/16시 두 정산), 만기일 종가청산 전1일. 기존 hold20은 진입index+20일종가여서 약20⅔일 비용. 8시간별 mark price 미보유로 실제 정산 재현 아님. 슬리피지는 진입가격×(1+s), 청산가격×(1−s), 수수료0.04%는 각각 별도. 배분과 NAV는 비용차감에 따라 다시 계산하며 최종 CAGR에서 단순히 연비용을 빼지 않았다.\n\n| 연펀딩 / 편도슬리피지 | CAGR | MDD | Sharpe | 거래 |\n|---|---:|---:|---:|---:|\n')
            for r in funding:
                f.write(f'| {r["annual"]*100:.2f}% / {r["slippage"]*100:.2f}% | {table(r["metrics"])} |\n')
            f.write('\n**이 표는 기각 대상이 아닌 비용 반영 현실성 기준선이다. 이후8카테고리는 원래 챔피언(CAGR62.35%/MDD53.38%/Sharpe1.165, 실제 반올림전 수치) 대비 미펀딩·슬리피지0으로 공정 비교한다. 실측 비용·상장폐지·시장충격을 포함한 실거래 성과 확정치는 아니다.**\n- 새 opt-in 공통 엔진은 기존 엔진과 격리, 무정책·비용0 챔피언 지표·거래수 완전 재현. 상세 검증/전체 Round1~10 회귀로그는 round11-verification/regression-summary.\n')
        out['sections'].append(29)
        save(out)
        git_section(29,out)
    for section,(category,group) in enumerate(configs().items(),30):
        if section in out['sections']:
            continue
        rows=[r for r in out['experiments'] if r['category']==category]
        for config in group:
            if any(r['config']==config for r in rows):
                continue
            p,data,kw,state = build(config,frames,cores)
            full = simulate_research_portfolio(p,prepared=data,return_trace=True,**kw)
            checks = audit(config,frames,cores,full)
            assert np.isfinite(list(summary(full).values())).all()
            dominates = not full['insolvent'] and full['cagr']>baseline['cagr'] and full['mdd']<baseline['mdd'] and full['sharpe']>baseline['sharpe']
            thrashing = transition_stats(state,data[0]) if state is not None else None
            row=dict(category=category,config=config,metrics=summary(full),insolvent=full['insolvent'],dominates=bool(dominates),causal_checks=checks,thrashing=thrashing,records=full['records'])
            if dominates:
                row['robustness']=robust(config,frames,cores,full,thrashing)
            rows.append(row)
            out['experiments'].append(row)
            save(out)
            print('RESULT',category,config,summary(full),row.get('robustness',{}).get('verdict'),flush=True)
            if row.get('robustness',{}).get('verdict')=='통과':
                out['status']='복귀조건 A 달성'
                break
        save(out)
        subprocess.run([sys.executable,'-m','app.verify_round11'],cwd=ROOT,check=True)
        write_section(section,category,rows)
        out['sections'].append(section)
        save(out)
        git_section(section,out)
        if out['status']=='복귀조건 A 달성':
            break
    if out['status']!='복귀조건 A 달성':
        assert len(out['experiments'])==34 and all(sum(r['category']==c for r in out['experiments'])>=4 for c in configs())
        out['status']='복귀조건 B 달성'
        out['sections'].append(38)
        closest=sorted(out['experiments'],key=lambda r:(-r['metrics']['sharpe'],-r['metrics']['cagr']))[:3]
        out['closest']=[r['config'] for r in closest]
        with DOC.open('a') as f:
            f.write('\n\n## 38. 라운드1~11 전체 최종 결론 (2026-10-07)\n\n')
            f.write('- §28 Round1~10의 파라미터·BTC추세 메타전략 미발견 결론에 Round11 비용현실성·롱숏·주기·유니버스·투표·ATR추적청산·변동성레짐·상관군집·동적슬롯34변형을 추가했다. 비용5시나리오는34변형에 합산하지 않는다.\n')
            f.write(f'- 신규 세축우위 {sum(r["dominates"] for r in out["experiments"])}개, 엄격5항목 전부통과0개. 검증대상이 없는 조합을 통계검증 실패라고 부르지 않는다.\n')
            for r in closest:
                f.write(f'- Sharpe 기준 근접 조합 {json.dumps(r["config"],ensure_ascii=False)}: {table(r["metrics"])}, 강건성 {r.get("robustness",{}).get("verdict","세축 미달로 미실행")}.\n')
            f.write('**최종 판정: Round1~11 조사범위 내에서 §12 챔피언을 CAGR/MDD/Sharpe 세축 전부에서 이기며 필수 강건성 검증을 모두 통과한 대체 전략은 미발견이다. 챔피언의 미비용 수치는 낙관적 연구 기준선이며, 비용 시나리오 기준선은 §29로 갱신한다. 이 결과는 모든 전략의 불가능성 또는 실거래 승격을 뜻하지 않는다.**\n\n- 상위거래/종목 집중, 현재유니버스 생존편향, 반복선택 편향 미보정, 겹친 역사창, 미관측OOS 없음은 유지된다. 숏은 유지증거금·실제청산 미포함이고 상관분산은 상한 진입제한이며 계속 재조정이 아니다. 거래블록 부트스트랩은 §19 거래단위 Sharpe근사, 일별NAV Sharpe CI가 아니다.\n\n**복귀조건 B 달성 — 조사범위 내 미발견.**\n')
        save(out)
        subprocess.run([sys.executable,'-m','app.verify_round11'],cwd=ROOT,check=True)
        git_section(38,out)
    print(out['status'],flush=True)


if __name__=='__main__':
    run()
