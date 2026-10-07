"""Resumable offline Round12 elimination; common engine is never modified."""
import json
import subprocess
import sys
import numpy as np
import pandas as pd
from app.crypto_technical_ict_research import ROOT, load_data
from app.crypto_bucket_ensemble_research import volume_prep
from app.technical_portfolio_engine import prepare, simulate_portfolio, simulate_research_portfolio
from app.crypto_round4_robustness import ledger_run, concentration
from app.crypto_round6_research import btc_period, symbols
from app.crypto_round7_research import summary, random_data, block_bootstrap
from app.crypto_round10_research import transition_stats, confirmed
from app.round12_signals import FAMILIES, find_signals

PATH = ROOT/'docs/round12-results-2026-10-07.json'
DOC = ROOT/'docs/전략-백테스트-종합.md'
GITLOG = ROOT/'docs/round12-git-2026-10-07.txt'
START = pd.Timestamp('2019-09-08', tz='UTC')
GROUPS = [('마하세븐 눌림목', ['mach7']), ('스퀴즈', ['squeeze']),
          ('눌림목 반등', ['rebound']), ('Supertrend·Range-Reversion', ['supertrend', 'range']),
          ('RSI2·BB+MACD+ADX', ['rsi2', 'bb_macd_adx']),
          ('Donchian·Dual-Thrust·MA-Pullback·Gap', ['donchian', 'dual_thrust', 'ma_pullback', 'gap'])]


def save(out):
    PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2, allow_nan=False,
                               default=lambda x: x.item() if isinstance(x, np.generic) else str(x)))


def build(frames, config):
    p = {s:find_signals(f, config['family'], **config.get('params', {})) for s, f in frames.items()}
    btc = frames['BTC'].Close
    trend = btc > btc.rolling(200).mean()
    state = None
    kwargs = {k:config[k] for k in ['top_k', 'hold_days', 'stop', 'tp', 'sizing',
                                   'target_vol', 'weight_cap'] if k in config}
    if config.get('btc_trend'):
        if config.get('btc_confirm'):
            trend = confirmed(trend.astype(int), config['btc_confirm']) == 1
        kwargs['btc_ok'] = trend.to_dict()
        state = trend.astype(int)
    if config.get('breaker'):
        kwargs.update(dd_trigger=.25, dd_resume=.10, resume_mode='cooldown', cooldown_days=40)
    if config.get('breadth'):
        breadth = pd.DataFrame({s:f.Close > f.Close.rolling(50).mean() for s, f in frames.items()})
        # Listed and warmed observations only; missing listings are not bearish.
        eligible = pd.DataFrame({s:f.Close.rolling(50).mean().notna() for s, f in frames.items()})
        mask = breadth.sum(axis=1)/eligible.sum(axis=1).replace(0, np.nan) >= .5
        for f in p.values():
            f['SIGNAL'] &= mask.reindex(f.index, fill_value=False)
        state = mask.astype(int)
    for s, f in p.items():
        raw = frames[s]
        c = raw.Close
        if config.get('self_trend'):
            f['SIGNAL'] &= c > c.rolling(200).mean()
        if config.get('volume_confirm'):
            f['SIGNAL'] &= f.VOL_RATIO >= 1.5
        if config.get('persistence'):
            turnover = raw.Volume*raw.Close
            ratio = turnover/turnover.shift(1).rolling(60).median()
            f['SIGNAL'] &= (ratio >= 1.5).rolling(5).sum() >= 3
        if config.get('weekly_trend'):
            # Completed weekly close is only published Sunday UTC at close;
            # forward-fill to subsequent days, never backfill into the week.
            weekly = c.resample('W-SUN').last()
            allowed = weekly > weekly.rolling(10).mean()
            f['SIGNAL'] &= allowed.reindex(c.index, method='ffill').fillna(False)
        if config.get('rank') == 'relative_strength':
            f['VOL_RATIO'] = c.pct_change(90, fill_method=None).fillna(-1.)
        if config.get('rank') == 'low_vol':
            f['VOL_RATIO'] = (-c.pct_change(fill_method=None).rolling(20).std()).fillna(-1.)
        if config.get('rank') == 'downside':
            f['VOL_RATIO'] = (-c.pct_change(fill_method=None).clip(upper=0).pow(2).rolling(30).mean().pow(.5)).fillna(-1.)
        if config.get('rank') == 'residual' or config['family'] == 'residual_rebound':
            ret = c.pct_change(fill_method=None)
            market = btc.pct_change(fill_method=None).reindex(c.index)
            beta = ret.rolling(90, min_periods=60).cov(market)/market.rolling(90, min_periods=60).var()
            # Fit at t-1, then observe t's residual; no fit with later data.
            residual = ret-beta.shift(1)*market
            if config.get('rank') == 'residual':
                f['VOL_RATIO'] = residual.rolling(20).sum().fillna(-1.)
            if config['family'] == 'residual_rebound':
                past = residual.shift(1).rolling(5).sum()
                threshold = residual.shift(1).rolling(60).std()*np.sqrt(5)
                f['SIGNAL'] &= (past < -threshold) & (residual > 0)
        if config.get('weekdays'):
            # Entry tomorrow, so use tomorrow's known weekday.
            f['SIGNAL'] &= pd.Series((f.index+pd.Timedelta(days=1)).weekday < 5, index=f.index)
        if config.get('month_edge'):
            tomorrow = f.index+pd.Timedelta(days=1)
            f['SIGNAL'] &= pd.Series((tomorrow.day <= 5) | (tomorrow.day >= 25), index=f.index)
        p[s] = f.loc[START:]
    return p, kwargs, state


def audit(frames, config, full):
    cutoff = pd.Timestamp('2024-06-30', tz='UTC')
    short = {s:f.loc[:cutoff] for s, f in frames.items() if len(f.loc[:cutoff])}
    # Keep EVERY listing already observed at cutoff, including short histories.
    # Later listings exist in the full bank but must not affect its past breadth.
    reference, _, _ = build(frames, config)
    prefix, kw, _ = build(short, config)
    changed = {s:f.copy() for s, f in frames.items()}
    for f in changed.values():
        future = f.index > cutoff
        f.loc[future, ['Open', 'High', 'Low', 'Close']] *= 3
        f.loc[future, 'Volume'] *= 7
    mutated, _, _ = build(changed, config)
    for s, f in prefix.items():
        for name in ['SIGNAL', 'VOL_RATIO', 'ATR14', 'STOP_LEVEL']:
            np.testing.assert_allclose(f[name], reference[s].loc[f.index, name], equal_nan=True)
            np.testing.assert_allclose(f[name], mutated[s].loc[f.index, name], equal_nan=True)
    # Full execution prefix ignores final-bar forced liquidation differences.
    ref, rk, _ = build(frames, config)
    a = simulate_portfolio(ref, return_trace=True, **rk)
    b = simulate_portfolio(prefix, return_trace=True, **kw)
    assert a['trace'][:len(b['trace'])-1] == b['trace'][:-1]
    assert all(pd.Timestamp(e['known_through']) < pd.Timestamp(e['date']) for e in full['allocations'])
    return dict(signal_prefix=True, future_mutation=True, execution_prefix=True, previous_bar_entries=True)


def robustness(p, kw, state, full):
    periods = json.loads((ROOT/'docs/round9-results-2026-10-07.json').read_text())['periods']
    legacy = json.loads((ROOT/'docs/round4-results-2026-10-07.json').read_text())['periods']
    rows = {}
    for start, end in dict.fromkeys([(r['start'], r['end']) for r in periods]+[tuple(r) for r in legacy]):
        sub = {s:f.loc[start:end] for s, f in p.items() if len(f.loc[start:end])}
        m = simulate_portfolio(sub, **kw)
        b = btc_period(p['BTC'], start, end)['cagr']
        rows[(start, end)] = dict(start=start, end=end, metrics=summary(m), btc_cagr=b, alpha=m['cagr']-b)
    m, records, _, _, _ = ledger_run(p, kw)
    for k in summary(m):
        assert abs(m[k]-full[k]) < 1e-8
    conc, sy = concentration(records), symbols(records)
    data = prepare(p)
    eligible = np.isfinite(data[2]['Open'][:-1]) & np.isfinite(data[2]['Open'][1:])
    probability = len(records)/eligible.sum()
    trials = []
    for seed in range(1200000, 1200300):
        trials.append(dict(seed=seed, **summary(simulate_portfolio(p, prepared=random_data(data, seed, probability), **kw))))
    tests = {k:dict(p=float((1+sum(t[k] >= full[k] for t in trials))/301)) for k in ['cagr', 'sharpe']}
    boot = block_bootstrap(records, full)
    current = [rows[(r['start'], r['end'])] for r in periods]
    original = [rows[tuple(r)] for r in legacy]
    if kw.get('dd_trigger'):
        # Identical Round4 breaker definition: resume-to-next-pause in 5 days.
        log = full['breaker_log']
        resumes = [e for e in log if e['kind'] == 'resume']
        near = 0
        for e in resumes:
            nxt = next((x for x in log if x['index'] > e['index'] and x['kind'] == 'pause'), None)
            near += bool(nxt and nxt['index']-e['index'] <= 5)
        breaker_pct = 100*near/len(resumes) if resumes else 0.
    else:
        breaker_pct = None
    transitions = transition_stats(state, data[0]) if state is not None else None
    rates = ([breaker_pct] if breaker_pct is not None else [])+([transitions['within']['5']['pct']] if transitions else [])
    votes = [sum(r['alpha'] > 0 for r in current) >= 7 and sum(r['alpha'] > 0 for r in original) >= 7,
             conc['10']['net_pct'] <= 103 and sy['net_pct'] <= 88,
             all(t['p'] < .05 for t in tests.values()), boot['ci95'][0] > 0,
             all(x <= 50 for x in rates)]
    return dict(periods=current, legacy_periods=original, concentration=conc, symbols=sy,
                monte_carlo=dict(probability=probability, trials=trials, tests=tests), bootstrap=boot,
                thrashing=transitions, breaker_5day_pct=breaker_pct,
                votes=[bool(x) for x in votes], verdict='통과' if all(votes) else '기각', records=records)


def git_section(out, section):
    files = ['app/round12_signals.py', 'app/crypto_round12_research.py', 'app/verify_round12.py',
             str(PATH.relative_to(ROOT)), str(DOC.relative_to(ROOT)), 'docs/round12-verification-2026-10-07.txt']
    if (ROOT/'app/crypto_round12_extension.py').exists():
        files.append('app/crypto_round12_extension.py')
    if (ROOT/'app/crypto_round12_final_batch.py').exists():
        files.append('app/crypto_round12_final_batch.py')
    files += ['docs/round12-execution-2026-10-07.log']
    if GITLOG.exists():
        files.append(str(GITLOG.relative_to(ROOT)))
    events = []
    h, pushed = None, False
    for action, cmd in [('add', ['git', 'add', *files]),
                        ('commit', ['git', 'commit', '-m', f'research: 라운드12 섹션{section} 신규전략 소거 및 인과성 검증']),
                        ('push', ['git', 'push', 'origin', 'main'])]:
        for attempt in range(3):
            try:
                r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=50)
                code, message = r.returncode, r.stdout+r.stderr
            except subprocess.TimeoutExpired:
                code, message = 124, '50초 제한 초과'
            events.append(dict(action=action, attempt=attempt+1, code=code, output=message))
            if code == 0:
                if action == 'commit':
                    h = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
                if action == 'push':
                    pushed = True
                break
        if code:
            break
    entry = dict(section=section, hash=h, pushed=pushed, status='성공' if pushed else '푸시 보류' if h else '커밋 보류', attempts=events)
    out['git'].append(entry)
    save(out)
    with GITLOG.open('a') as f:
        f.write(json.dumps(entry, ensure_ascii=False, indent=2)+'\n')
    if not pushed:
        with DOC.open('a') as f:
            f.write(f'\n- Git §{section}: {entry["status"]}, 해시 {h or "없음"}. 최초+2회 재시도 기록: round12-git-2026-10-07.txt.\n')


def write_section(section, title, rows):
    with DOC.open('a') as f:
        f.write(f'\n\n## {section}. {title} (2026-10-07, 라운드12)\n\n')
        f.write('- 기존45종목 일봉 캐시·2019-09-08~2026-10-05·편도0.04%·TOP_K8·20일 만기·손절없음을 기본으로 technical_portfolio_engine 재사용. 원전략의 신호만 이식하고 청산/사이징은 공통화한다. 1h/4h 원전략의 원래 성과 재현이 아니라 일봉 진입신호 로테이션 비교다. VOL_RATIO는 전일20봉 거래량 중앙값 대비 현재 확정 거래량으로 통일한다. 거시 서술형 REGIME은 사용하지 않는다.\n')
        f.write('- 마하세븐10/50/200·최근10일눌림(실제 포트폴리오 모듈 기본값); 스퀴즈20/200이격3%·최근10일·교차횟수20일≤3; 반등SMA5재돌파; Supertrend10×3 상승전환; Range30일하단20%; RSI2<10·SMA200상방; BB20×2(ddof0)+MACD12/26/9+ADX14>30; Donchian55일직전고점·SMA200상방; DualThrust21일×0.71; MA눌림 SMA50>SMA200·종가>SMA50·RSI14<35; Gap은 시가갭이 아닌 종가간10%급등. 원모듈의 워밍업을 유지한다.\n')
        f.write('- 기본 python3에 pandas 없음, python3.12로 실제 실행. pandas_ta 없음: 기존 technical_indicator_fallback의 EMA/RSI/ATR/RMA를 사용하며 신규 Supertrend 재귀·BB/MACD/ADX 공식을 명시했다. 신호prefix·미래가격3배/거래량7배변조·실행prefix·전일정보진입을 매조합 검증한다.\n\n| 설정 | CAGR | MDD | Sharpe | 거래 | 세축/판정 |\n|---|---:|---:|---:|---:|---|\n')
        for r in rows:
            m = r['metrics']
            f.write(f'| {json.dumps(r["config"], ensure_ascii=False)} | {m["cagr"]:+.4f}% | {m["mdd"]:.4f}% | {m["sharpe"]:.6f} | {m["trades"]} | {"우위" if r["dominates"] else "미충족"}/{r.get("robustness", {}).get("verdict", "세축미달 기각")} |\n')
            if 'robustness' in r:
                b = r['robustness']
                f.write(f'\n- 강건성 {json.dumps(r["config"], ensure_ascii=False)}: 기간 알파 {sum(x["alpha"] > 0 for x in b["periods"])}/8·원경계 {sum(x["alpha"] > 0 for x in b["legacy_periods"])}/8, 집중도10건 {b["concentration"]["10"]["net_pct"]:.4f}%·5종목 {b["symbols"]["net_pct"]:.4f}%, 랜덤300회 {b["monte_carlo"]["tests"]}, 20건블록1000회95%CI {b["bootstrap"]["ci95"]}, 전환 {b["thrashing"]}, 재개후5일재중단% {b["breaker_5day_pct"]}, 5판정 {b["votes"]}: **{b["verdict"]}**. 블록CI는 기존 거래단위Sharpe근사이며 일별NAV Sharpe CI가 아니다.\n')
        f.write(f'\n- 신규 {len(rows)}조합, 세축우위 {sum(r["dominates"] for r in rows)}개. 명백히 세축미달은 지정 기준에 따라 강건성검사 미실행. 0거래도 신호빈도·기간을 확인하고 실패 결과로 보존한다. 전체 데이터·공식·반복선택에 따른 생존/탐색편향은 제거되지 않는다.\n')


def phase2_groups():
    # Exactly novel triple combinations: fresh entry family + two policies.
    risk = [dict(family=n, btc_trend=True, sizing='inverse_vol', target_vol=.60, weight_cap=.25) for n in FAMILIES]
    confirmation = [dict(family=n, self_trend=True, volume_confirm=True) for n in FAMILIES]
    weekly = [dict(family=n, weekly_trend=True, rank='relative_strength') for n in ['mach7', 'rebound', 'supertrend', 'donchian', 'gap']]
    breadth = [dict(family=n, breadth=True, rank='low_vol') for n in ['mach7', 'supertrend', 'donchian', 'gap']]
    compression = [dict(family='compression_breakout', **x) for x in [{}, {'hold_days':10}, {'hold_days':40}, {'weekly_trend':True, 'volume_confirm':True}, {'btc_trend':True, 'sizing':'inverse_vol', 'target_vol':.60}, {'self_trend':True, 'rank':'relative_strength'}]]
    seasonal = [dict(family=n, weekdays=True, volume_confirm=True) for n in ['mach7', 'rebound', 'gap']]
    seasonal += [dict(family=n, month_edge=True, self_trend=True) for n in ['mach7', 'rebound', 'gap']]
    breaker = [dict(family=n, breaker=True, volume_confirm=True) for n in ['mach7', 'supertrend', 'donchian', 'gap']]
    return [('신규신호+BTC추세+역변동성', risk), ('신규신호+자체장기추세+거래량확인', confirmation),
            ('완료주봉+상대강도순위', weekly), ('시장폭+저변동순위', breadth),
            ('BB압축후돌파 신규축', compression), ('요일·월경계 조합', seasonal), ('신규신호+쿨다운+거래량확인', breaker)]


def execute(out, frames, phase, config):
    if any(r['phase'] == phase and r['config'] == config for r in out['experiments']):
        return
    p, kw, state = build(frames, config)
    full = simulate_portfolio(p, return_trace=True, **kw)
    m = summary(full)
    assert np.isfinite(list(m.values())).all() and 0 <= m['mdd'] <= 100 and m['final'] > 0
    assert full['start'].startswith('2019-09-08') and full['end'].startswith('2026-10-05')
    b = out['baseline']
    dominates = m['cagr'] > b['cagr'] and m['mdd'] < b['mdd'] and m['sharpe'] > b['sharpe']
    row = dict(phase=phase, config=config, metrics=m, dominates=bool(dominates),
               signal_count=sum(int(f.SIGNAL.sum()) for f in p.values()), causal_checks=audit(frames, config, full))
    if dominates:
        row['robustness'] = robustness(p, kw, state, full)
        if row['robustness']['verdict'] == '통과':
            out['status'] = '복귀조건 A 달성'
            # Cost engine equality must hold before cost estimates are attached.
            assert not kw.get('sizing', 'equal') == 'inverse_vol' and not kw.get('dd_trigger') and not kw.get('stop') and not kw.get('tp'), 'winner cost adapter required for extra execution policies'
            rk = {k:kw[k] for k in ['top_k', 'hold_days'] if k in kw}
            if kw.get('btc_ok'):
                for f in p.values():
                    f['SIGNAL'] &= pd.Series(kw['btc_ok']).reindex(f.index, fill_value=False)
            zero = simulate_research_portfolio(p, **rk)
            for k in m:
                assert abs(zero[k]-m[k]) < 1e-8
            row['costs'] = [dict(funding_annual=.1095, slippage=slip,
                                 metrics=summary(simulate_research_portfolio(p, funding_annual=.1095, slippage=slip, **rk))) for slip in [.0005, .001]]
    out['experiments'].append(row)
    save(out)
    print('RESULT', phase, config, m, row.get('robustness', {}).get('verdict'), flush=True)


def verify_and_section(out, section, title, rows):
    modules = ['app/round12_signals.py', 'app/crypto_round12_research.py', 'app/verify_round12.py']
    modules += [str(p.relative_to(ROOT)) for p in [ROOT/'app/crypto_round12_extension.py', ROOT/'app/crypto_round12_final_batch.py'] if p.exists()]
    subprocess.run(['python3', '-m', 'py_compile', *modules], cwd=ROOT, check=True)
    with (ROOT/'docs/round12-verification-2026-10-07.txt').open('a') as f:
        subprocess.run([sys.executable, '-m', 'app.verify_round12'], cwd=ROOT, stdout=f, stderr=subprocess.STDOUT, check=True)
    write_section(section, title, rows)
    out['sections'].append(section)
    save(out)
    git_section(out, section)


def run():
    frames, manifest, skipped = load_data()
    assert len(frames) == 45 and not skipped
    champion = volume_prep(frames)
    baseline = summary(simulate_portfolio(champion))
    assert baseline == json.loads((ROOT/'docs/round11-results-2026-10-07.json').read_text())['baseline']
    out = json.loads(PATH.read_text()) if PATH.exists() else dict(manifest=manifest, baseline=baseline, experiments=[], sections=[], git=[], status='탐색중')
    assert out['manifest'] == manifest
    if out['status'] == '복귀조건 A 달성':
        return
    for index, (title, names) in enumerate(GROUPS):
        section = 39+index
        if section in out['sections']:
            continue
        for name in names:
            execute(out, frames, 1, dict(family=name))
            base = next(r for r in out['experiments'] if r['config'] == dict(family=name))
            variations = []
            if name == 'mach7':
                variations = [dict(family=name, top_k=k) for k in [3, 5]]
            elif base['metrics']['cagr'] > 40 and base['metrics']['sharpe'] > .9:
                variations = [dict(family=name, top_k=4), dict(family=name, hold_days=10)]
            if out['status'] != '복귀조건 A 달성':
                for config in variations:
                    execute(out, frames, 1, config)
                    if out['status'] == '복귀조건 A 달성':
                        break
            if out['status'] == '복귀조건 A 달성':
                break
        rows = [r for r in out['experiments'] if r['phase'] == 1 and r['config']['family'] in names]
        verify_and_section(out, section, title, rows)
        if out['status'] == '복귀조건 A 달성':
            return
    for index, (title, configs) in enumerate(phase2_groups()):
        section = 45+index
        if section in out['sections']:
            continue
        for config in configs:
            execute(out, frames, 2, config)
            if out['status'] == '복귀조건 A 달성':
                break
        rows = [r for r in out['experiments'] if r['phase'] == 2 and r['config'] in configs]
        verify_and_section(out, section, title, rows)
        if out['status'] == '복귀조건 A 달성':
            return
    # Twenty failures cannot prove ideas exhausted. Preserve an honest checkpoint.
    out['status'] = '복귀조건 미달성, 계속 진행 필요'
    out['next'] = ['일봉급등 신호의 거시유동성 아닌 횡단면 잔차강도·거래량 지속성 결합',
                   '완료월봉 추세와 일봉압축 해제의 합의', '과거완료거래 승률의 축소추정 사이징',
                   '신규 레포 broad_strategies의 CCI/OBV/CMF/Aroon 등 미소진 진입군']
    save(out)
    if 52 not in out['sections']:
        with DOC.open('a') as f:
            f.write('\n\n## 52. 라운드12 재개 체크포인트 (2026-10-07)\n\n')
            f.write(f'- 1단계 고유전략 {len({r["config"]["family"] for r in out["experiments"] if r["phase"] == 1})}종·변형포함 {sum(r["phase"] == 1 for r in out["experiments"])}조합, 2단계 {sum(r["phase"] == 2 for r in out["experiments"])}조합. 신규 총 {len(out["experiments"])}조합.\n')
            f.write('- **복귀조건 미달성, 계속 진행 필요.** 6전략군과20개 이상 새 조합은 실행했지만 합리적 아이디어 소진을 입증하지 않았다. B로 승격하거나 Round1~12 최종결론으로 단정하지 않는다. 다음 탐색: '+ ' / '.join(out['next'])+'。\n')
            f.write('- 재개 시 원시JSON의 phase/config 키로 중복제거하고 §53부터 진행한다. 완료섹션을 다시 추가하거나 구실행을 신규실행으로 세지 않는다. 핵심엔진 미수정으로 Round1~11 전체회귀는 재실행하지 않고 신규검증과 챔피언 수치 재현을 수행했다.\n')
        out['sections'].append(52)
        save(out)
        git_section(out, 52)
    print(out['status'], flush=True)


if __name__ == '__main__':
    run()
