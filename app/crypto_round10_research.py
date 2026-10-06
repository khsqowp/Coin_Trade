"""Round10: causal BTC regime overlays, frozen baseline signals and strict audits."""
import json
import subprocess
import sys

import numpy as np
import pandas as pd

from app.crypto_technical_ict_research import ROOT, load_data, HOLD
from app.crypto_round8_research import core
from app.crypto_round4_robustness import ledger_run, concentration, flapping
from app.crypto_round6_research import btc_period, symbols
from app.crypto_round7_research import random_data, block_bootstrap, summary
from app.technical_portfolio_engine import prepare, simulate_portfolio

PATH = ROOT / 'docs/round10-results-2026-10-07.json'
DOC = ROOT / 'docs/전략-백테스트-종합.md'
FAMILIES = ['volume', 'heikin_ashi', 'frvp', 'fvg', 'vwap']
CONFIRM = [1, 3, 5, 10]
HOLDS = {f: HOLD.get(f, 20) for f in FAMILIES}


def confirmed(raw, days):
    """Warm-up stays unavailable; require N identical completed bars to change."""
    if days < 1:
        raise ValueError('positive confirmation period required')
    state = -1
    pending = -1
    count = 0
    result = []
    for value in raw:
        value = int(value)
        if value < 0:
            pending, count = -1, 0
        else:
            count = count + 1 if value == pending else 1
            pending = value
            if count >= days:
                state = value
        result.append(state)
    return pd.Series(result, index=raw.index, dtype=int)


def regimes(btc):
    close = btc.Close
    sma200 = close.rolling(200, min_periods=200).mean()
    sma50 = close.rolling(50, min_periods=50).mean()
    tr = pd.concat([btc.High-btc.Low, (btc.High-close.shift(1)).abs(),
                    (btc.Low-close.shift(1)).abs()], axis=1).max(axis=1)
    # ATR200 here explicitly means arithmetic mean of 200 true ranges.
    atr200 = tr.rolling(200, min_periods=200).mean()
    bull = close > sma200
    fast = close > sma50
    valid = sma200.notna() & sma50.notna()
    binary = pd.Series(np.where(valid, bull.astype(int), -1), index=close.index)
    four = pd.Series(np.select([bull & fast, bull & ~fast, ~bull & fast],
                               [3, 2, 1], default=0), index=close.index).where(valid, -1)
    strength = (close-sma200)/atr200
    roc = close.pct_change(20, fill_method=None)
    out = pd.DataFrame(dict(close=close, sma200=sma200, sma50=sma50,
                            atr200=atr200, strength=strength, roc20=roc))
    for n in CONFIRM:
        out[f'binary{n}'] = confirmed(binary, n)
        out[f'four{n}'] = confirmed(four, n)
    # Fixed normalization, no full-sample min/max: clip(0.5 + strength/10).
    out['atr_weight'] = (.5+strength/10).clip(0, 1).fillna(0)
    out['roc_weight'] = (.5+roc/0.4).clip(0, 1).where(valid, 0).fillna(0)
    for kind in ['atr', 'roc']:
        out[f'{kind}_smooth5'] = out[f'{kind}_weight'].ewm(span=5, adjust=False).mean()
    return out


def transition_stats(series, dates):
    """Reuse Round4 resume-to-first-pause arithmetic for EVERY regime transition."""
    values = series.reindex(dates).fillna(-1).to_numpy()
    changes = [i for i in range(1, len(values))
               if values[i] != values[i-1] and values[i] != -1 and values[i-1] != -1]
    if not changes:
        return dict(transitions=0, censored_5d=0,
                    within={str(n): dict(count=0, pct=0.) for n in [1, 3, 5]}, events=[])
    log = []
    for j, i in enumerate(changes):
        if j:
            log.append(dict(kind='pause', index=i, date=str(dates[i])))
        log.append(dict(kind='resume', index=i, date=str(dates[i])))
    observed = flapping(dict(breaker_log=log, breaker_events=max(0, len(changes)-1),
                            breaker_resumes=len(changes), trace=[None]*len(dates)))
    # Independent consecutive-gap arithmetic guards the event adapter.
    gaps = np.diff(changes)
    for n in [1, 3, 5]:
        assert observed['within'][str(n)]['count'] == int((gaps <= n).sum())
    return dict(transitions=len(changes), censored_5d=observed['censored_5d'],
                within=observed['within'], events=[dict(index=i, date=str(dates[i]),
                previous=int(values[i-1]), current=int(values[i])) for i in changes])


def configs():
    groups = []
    gates = [dict(meta='gate', family=f, confirm=n) for f in FAMILIES for n in CONFIRM]
    groups.append((25, 'BTC 레짐 정의와 이진 신규진입 게이트', gates))
    scales = [dict(meta='scale', family=f, confirm=n, mapping=m)
              for f in FAMILIES for n in CONFIRM for m in ['four0', 'four10']]
    scales += [dict(meta='scale', family=f, confirm=1, mapping=m)
               for f in FAMILIES for m in ['atr', 'atr_smooth5', 'roc', 'roc_smooth5']]
    groups.append((26, '4단계·연속 추세강도 비중조절', scales))
    pairs = [('volume', 'frvp'), ('volume', 'cash'), ('heikin_ashi', 'frvp'),
             ('heikin_ashi', 'cash'), ('fvg', 'vwap'), ('vwap', 'frvp'), ('frvp', 'cash')]
    switches = [dict(meta='switch', family=a, bear=b, confirm=n, exit=mode)
                for a, b in pairs for n in CONFIRM for mode in ['natural', 'immediate']]
    groups.append((27, 'BTC 불·베어 전략교체와 청산방식 비교', switches))
    return groups


def execution(config, prepared, regime):
    f, n = config['family'], config['confirm']
    kwargs = dict(hold_days=HOLDS[f], prepared=prepared[f])
    if config['meta'] == 'gate':
        kwargs['btc_ok'] = (regime[f'binary{n}'] == 1).to_dict()
    elif config['meta'] == 'scale':
        mapping = config['mapping']
        if mapping.startswith('four'):
            weights = [0., .4, .7, 1.] if mapping == 'four0' else [.1, .4, .7, 1.]
            weight = regime[f'four{n}'].map(dict(enumerate(weights))).fillna(0)
        else:
            weight = regime[mapping if 'smooth' in mapping else f'{mapping}_weight']
        kwargs['entry_scale'] = weight.to_dict()
    else:
        bear = config['bear']
        schedule = {d: f if v == 1 else bear if v == 0 and bear != 'cash' else None
                    for d, v in regime[f'binary{n}'].items()}
        names = [f] + ([bear] if bear != 'cash' else [])
        kwargs.update(strategy_data={s: prepared[s] for s in names}, active_strategy=schedule,
                      strategy_holds=HOLDS, liquidate_on_switch=config['exit'] == 'immediate')
    return kwargs


def sliced(prepped, start=None, end=None):
    return {s: df.loc[start:end] for s, df in prepped.items() if len(df.loc[start:end])}


def audit(config, prepped, prepared, regime, frames):
    cutoff = pd.Timestamp('2024-06-30', tz='UTC')
    f = config['family']
    kwargs = execution(config, prepared, regime)
    full = simulate_portfolio(prepped[f], return_trace=True, **kwargs)
    smallp = {k: sliced(v, end=cutoff) for k, v in prepped.items()}
    smalldata = {k: prepare(v) for k, v in smallp.items()}
    smallr = regimes(frames['BTC'].loc[:cutoff])
    pd.testing.assert_frame_equal(regime.loc[:cutoff], smallr)
    short = simulate_portfolio(smallp[f], return_trace=True, **execution(config, smalldata, smallr))
    assert short['trace'][:-1] == full['trace'][:len(short['trace'])-1]
    assert short['allocations'] == [a for a in full['allocations'] if pd.Timestamp(a['date']) <= cutoff]
    changedbtc = frames['BTC'].copy()
    changedbtc.loc[changedbtc.index > cutoff, ['Open','High','Low','Close']] *= 3
    changedr = regimes(changedbtc)
    pd.testing.assert_frame_equal(changedr.loc[:cutoff], smallr)
    changed = {}
    for name, data in prepared.items():
        arrays = {k: v.copy() for k, v in data[2].items()}
        future = np.array(data[0]) > cutoff
        for field in ['Open', 'High', 'Low', 'Close']:
            arrays[field][future] *= 3
        arrays['SIGNAL'][future] = True
        arrays['VOL_RATIO'][future] = 999
        changed[name] = data[0], data[1], arrays
    altered = simulate_portfolio(prepped[f], return_trace=True, **execution(config, changed, changedr))
    assert altered['trace'][:len(short['trace'])-1] == short['trace'][:-1]
    assert all(pd.Timestamp(a['known_through']) < pd.Timestamp(a['date']) for a in full['allocations'])
    return 4


def robust(config, prepped, prepared, regime, frames, full, thrashing):
    f = config['family']
    replay, records, _, _, _ = ledger_run(prepped[f], execution(config, prepared, regime))
    assert summary(replay) == summary(full)
    old = json.loads((ROOT/'docs/round4-results-2026-10-07.json').read_text())['periods']
    recent = json.loads((ROOT/'docs/round9-results-2026-10-07.json').read_text())['periods']
    actual = [(c['start'], c['end']) for c in recent]
    cells = {}
    for start, end in dict.fromkeys([tuple(p) for p in old] + actual):
        sub = {s: sliced(p, start, end) for s, p in prepped.items()}
        data = {s: prepare(p) for s, p in sub.items()}
        m = simulate_portfolio(sub[f], **execution(config, data, regime))
        btc = btc_period(frames['BTC'], start, end)['cagr']
        cells[(start,end)] = dict(start=start, end=end, metrics=summary(m), btc_cagr=btc, alpha=m['cagr']-btc)
    legacy = [cells[tuple(p)] for p in old]
    current = [cells[p] for p in actual]
    conc, sy = concentration(records), symbols(records)
    data = prepared[f]
    eligible = np.isfinite(data[2]['Open'][:-1]) & np.isfinite(data[2]['Open'][1:])
    # Frequency calibration is historical, as in Round8, not a trading input.
    probability = len(records)/eligible.sum()
    trials = []
    for seed in range(1000000, 1000300):
        random_banks = {s: random_data(p, seed, probability) for s, p in prepared.items()}
        m = simulate_portfolio(prepped[f], **execution(config, random_banks, regime))
        trials.append(dict(seed=seed, **summary(m)))
        if len(trials) % 50 == 0:
            print('MC', config, len(trials), flush=True)
    tests = {k: dict(p=float((1+sum(t[k]>=full[k] for t in trials))/301),
                    q95=float(np.percentile([t[k] for t in trials],95))) for k in ['cagr','sharpe']}
    boot = block_bootstrap(records, full)
    votes = [sum(c['alpha']>0 for c in current)>=7 and sum(c['alpha']>0 for c in legacy)>=7,
             conc['10']['net_pct']<=103 and sy['net_pct']<=88,
             all(t['p']<.05 for t in tests.values()), bool(boot['significant']),
             thrashing['within']['5']['pct']<=50]
    return dict(periods=current, legacy_periods=legacy,
                alpha_positive=int(sum(c['alpha']>0 for c in current)),
                legacy_alpha_positive=int(sum(c['alpha']>0 for c in legacy)),
                concentration=conc, symbols=sy, monte_carlo=dict(probability=probability,trials=trials,tests=tests),
                bootstrap=boot, thrashing=thrashing, votes=[bool(v) for v in votes],
                verdict='통과' if all(votes) else '기각', trades=records)


def json_scalar(value):
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(f'Unsupported JSON value: {type(value).__name__}')


def save(output):
    temp = PATH.with_suffix('.tmp')
    temp.write_text(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False,
                               default=json_scalar))
    temp.replace(PATH)


def git_section(section, output):
    files = ['app/technical_portfolio_engine.py','app/crypto_round4_robustness.py',
             'app/crypto_round10_research.py','app/verify_round10.py',
             'docs/round10-results-2026-10-07.json','docs/전략-백테스트-종합.md']
    files += [str(p.relative_to(ROOT)) for p in sorted((ROOT/'docs').glob('round10-*-2026-10-07.*')) if p.name != PATH.name]
    attempts = []
    success = False
    for _ in range(3):  # first attempt + at most two retries
        p = subprocess.run(['git','add',*files],cwd=ROOT,text=True,capture_output=True)
        attempts.append(dict(action='add',code=p.returncode,output=p.stdout+p.stderr))
        if p.returncode == 0:
            success = True
            break
    h = None
    pushed = False
    if success:
        for _ in range(3):
            p = subprocess.run(['git','commit','-m',f'research: 라운드10 섹션{section} BTC 레짐 메타전략 검증'],cwd=ROOT,text=True,capture_output=True)
            attempts.append(dict(action='commit',code=p.returncode,output=p.stdout+p.stderr))
            if p.returncode == 0:
                h = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
                break
        if h:
            for _ in range(3):
                p = subprocess.run(['git','push','origin','main'],cwd=ROOT,text=True,capture_output=True)
                attempts.append(dict(action='push',code=p.returncode,output=p.stdout+p.stderr))
                if p.returncode == 0:
                    pushed = True
                    break
    output['git'].append(dict(section=section, hash=h, pushed=pushed,
                             status='커밋·푸시 성공' if pushed else '푸시 보류' if h else '커밋 보류', attempts=attempts))
    save(output)
    with (ROOT/'docs/round10-git-2026-10-07.txt').open('a') as stream:
        stream.write(json.dumps(output['git'][-1],ensure_ascii=False,indent=2)+'\n')
    if not pushed:
        with DOC.open('a') as stream:
            stream.write(f'\n- Git 섹션{section}: {output["git"][-1]["status"]}. 최초 시도+최대2회 재시도 결과는 round10-git-2026-10-07.txt. 해시 {h or "없음"}.\n')


def write_section(section, title, rows, output):
    with DOC.open('a') as stream:
        stream.write(f'\n\n## {section}. {title} (2026-10-07, 라운드10)\n\n')
        if section == 25:
            stream.write('- 캐시 CSV 직접 읽기(load_data 재사용), 45종목·2019-09-08~2026-10-05·편도0.04%·TOP_K8·무배율·손절/익절/CB 없음. 당일 완료봉 레짐→다음 UTC 일봉 시가 실행. SMA200 최초200봉 미충족 기간에는 신규진입0, 기존 포지션 정상청산.\n')
            stream.write('- 이진: Close>SMA200이면 불1, Close≤SMA200이면 베어0. 4단계: Close>SMA200 AND Close>SMA50=강세불3; Close>SMA200 AND Close≤SMA50=약세불2; Close≤SMA200 AND Close>SMA50=약세베어1; Close≤SMA200 AND Close≤SMA50=강세베어0. SMA50>SMA200의 별도 순서 조건은 요구하지 않는다.\n')
            stream.write('- 추세강도=(Close−SMA200)/ATR200. TR=max(High−Low,|High−전일Close|,|Low−전일Close|), ATR200은 최근200 TR 산술평균(Wilder ATR 아님). 비중=clip(0.5+강도/10,0,1). ROC20=Close/20일전Close−1, 비중=clip(0.5+ROC20/0.4,0,1). 5일 완화는 과거방향 EWM(span5,adjust=False), 전구간 min/max 정규화 없음.\n')
            stream.write('- 확인기간1/3/5/10일: 새 조건이 N일 연속 동일하면 레짐 변경, 그 전에는 직전 확정상태 유지. 최초 확인 전은 미확정−1. 이진과4단계에 각각 적용. 연속값에는 이산 확인기간을 강제하지 않고 EWM 변형으로 비교.\n')
            stream.write('- 동결 신호: 챔피언 vol3배/cap5%/lookback20/hold20; HA 음→양 전환/몸통÷ATR14 rank/hold20; FRVP 과거60일24bin POC/LVN 돌파/hold20; FVG 3봉 갭 최초재진입·60일만료/hold20; VWAP 전형가격×거래량 rolling20 이탈→복귀/hold10. 각 find_signals 기본값 사용(VWAP 스윕 조합 사용 안 함). 5개 무레짐 기준선을 §13/챔피언 원시 JSON과 완전 대조.\n')
            stream.write('- 기간경계 불일치 처리: §16/18의 원래8창은 넓은분할2+실제2년6이다. §23의 실제2년8창을 주요 검사로 재사용하고, §16/18의 원래8창도 추가 실행하여 양쪽 모두7/8 이상을 요구한다. 경계를 임의 변경하거나 과거8/8 결과를 전이하지 않는다.\n')
            stream.write('- 강건성은 세 축을 반올림 전 실제 챔피언보다 엄격하게 이긴 후보 전부에만 실행. 5항목 모두 통과 필수. 집중도103%/88%, 랜덤300회 두 p<0.05, 거래블록20×1000 CI하한>0, 5일 스래싱≤50%. Round4 원장·집중도·플래핑, Round6 BTC/종목집중도, Round7 랜덤/부트스트랩, Round8/9 기간설계 재사용.\n')
            stream.write('- 스래싱: 초기 미확정→확정은 전환에서 제외, 모든 확정 레짐 변경부터 최초 후속 변경까지 거래일 인덱스 차이. Round4 flapping에 resume/pause 쌍으로 어댑트, 분모=전체전환수(마지막 전환 포함), 1/3/5일 및 마지막5일 중도절단 별도 기록. 4단계 비중은4단계 변경, 연속비중은 즉시 이진 BTC 추세전환 기준을 사용. 연속값 일별 변경률은 별도로 기록하며 이산전환과 혼동하지 않는다.\n')
        elif section == 26:
            stream.write('- 신규 진입예산=NAV/8×레짐비중, 가용현금 상한·기존8슬롯 유지. 기존 보유수량은 재조정하지 않는다. four0=[강세베어0,약세베어0.4,약세불0.7,강세불1], four10=[0.1,0.4,0.7,1]. 이진20 + 4단계40 + 연속20 구성이며 노출 변화가 성과에 미친 영향까지 포함한다.\n')
        elif section == 27:
            stream.write('- 불/베어에 지정한 신호뱅크를 한 계좌·8슬롯에서 선택. 기존종목 중복진입 금지. natural은 원진입전략의 보유만기까지 유지하며 새전략과 공존; immediate는 전일 확정레짐을 다음날 시가에 적용해 이전전략 보유분 청산(수수료 차감) 후 신규전략 진입. 시가 없는 종목은 실제 다음 유효시가까지 청산 유예. 현금레짐은 신규진입0. VWAP 포지션만10일, 나머지20일 만기를 진입시 고정한다.\n')
        stream.write(f'- 이 묶음 {len(rows)}개, 누적 {len(output["experiments"])}개. 각 조합 미래가격/신호변형·절단실행·BTC지표prefix·과거확정시간 검증4개 통과. 기준선·합성검증 및 Round1~9 회귀로그는 round10-verification/round10-round*-regression 파일.\n\n| 설정 | CAGR | MDD | Sharpe | 거래 | 레짐전환 | 5일 스래싱 | 세축/판정 |\n|---|---:|---:|---:|---:|---:|---:|---|\n')
        for row in rows:
            m, t = row['metrics'], row['thrashing']
            stream.write(f'| {json.dumps(row["config"],ensure_ascii=False)} | {m["cagr"]:+.4f}% | {m["mdd"]:.4f}% | {m["sharpe"]:.6f} | {m["trades"]} | {t["transitions"]} | {t["within"]["5"]["pct"]:.2f}% | {"우위" if row["dominates"] else "미충족"}/{row.get("robustness",{}).get("verdict","검증대상 아님")} |\n')
        for row in rows:
            if 'robustness' not in row:
                continue
            b = row['robustness']
            stream.write(f'\n### {section}-{rows.index(row)+1}. 세 축 우위 후보 검증\n\n- 설정 {json.dumps(row["config"],ensure_ascii=False)}: **{b["verdict"]}**, {sum(b["votes"])}/5. 실제2년 알파 {b["alpha_positive"]}/8, 원경계 {b["legacy_alpha_positive"]}/8. 집중도 상위10건 {b["concentration"]["10"]["net_pct"]:.4f}% / 상위5종목 {b["symbols"]["net_pct"]:.4f}%. 랜덤300회 {json.dumps(b["monte_carlo"]["tests"],ensure_ascii=False)}. 블록20×1000 CI {b["bootstrap"]["ci95"]}. 5일 스래싱 {b["thrashing"]["within"]["5"]["pct"]:.4f}%. 순서별 통과 {b["votes"]}.\n\n| 시작 | 종료 | 후보 CAGR | BTC CAGR | 알파 |\n|---|---|---:|---:|---:|\n')
            for c in b['periods']:
                stream.write(f'| {c["start"]} | {c["end"]} | {c["metrics"]["cagr"]:+.4f}% | {c["btc_cagr"]:+.4f}% | {c["alpha"]:+.4f}%p |\n')
            stream.write('- 원시결과 JSON에 두 경계표·거래원장·난수seed·1000블록시퀀스·전환날짜 전부 보존. 랜덤대조군은 같은 BTC정책/슬롯/예산/만기/청산을 유지하고 실제 신호/랭킹만 Round7 난수로 치환한다. 부트스트랩은 §19 거래단위 근사이며 포트폴리오 일별 Sharpe CI가 아니다.\n')


def run():
    frames, manifest, skipped = load_data()
    assert len(frames) == 45 and not skipped
    assert manifest == json.loads((ROOT/'docs/round9-results-2026-10-07.json').read_text())['manifest']
    resume = json.loads(PATH.read_text()) if PATH.exists() else None
    if resume and resume['status'].startswith('복귀조건 '):
        raise RuntimeError('Round10 already finished; run verifier')
    prepped = {f: core(f, frames) for f in FAMILIES}
    prepared = {f: prepare(p) for f,p in prepped.items()}
    regime = regimes(frames['BTC'])
    baseline = {f: summary(simulate_portfolio(p, prepared=prepared[f], hold_days=HOLDS[f])) for f,p in prepped.items()}
    prior = json.loads((ROOT/'docs/technical-ict-results-2026-10-06.json').read_text())
    for f in FAMILIES[1:]:
        assert baseline[f] == summary(next(s for s in prior['strategies'] if s['name']==f)['baseline'])
    assert baseline['volume'] == summary(json.loads((ROOT/'docs/round7-results-2026-10-07.json').read_text())['baseline'])
    champion = baseline['volume']
    output = dict(manifest=manifest, baseline=baseline, experiments=[], sections=[], git=[], status='탐색중',
                  regimes=[dict(date=str(d), **{k: None if pd.isna(v) else float(v) for k,v in row.items()}) for d,row in regime.iterrows()],
                  planned_combinations=sum(len(g[2]) for g in configs()))
    if resume:
        assert resume['manifest'] == manifest and resume['baseline'] == baseline
        output = resume
    save(output)
    for section,title,group in configs():
        if section in output['sections']:
            continue
        rows = [r for r in output['experiments'] if r['config'] in group]
        completed = [r['config'] for r in rows]
        for config in group:
            if config in completed:
                continue
            kwargs = execution(config, prepared, regime)
            full = simulate_portfolio(prepped[config['family']], **kwargs)
            assert np.isfinite(list(summary(full).values())).all() and -100 < full['cagr'] < 1000 and 0 <= full['mdd'] <= 100 and full['trades'] > 0
            checks = audit(config, prepped, prepared, regime, frames)
            key = f'four{config["confirm"]}' if config.get('mapping','').startswith('four') else f'binary{config["confirm"]}'
            thrashing = transition_stats(regime[key], prepared[config['family']][0])
            dominates = full['cagr'] > champion['cagr'] and full['mdd'] < champion['mdd'] and full['sharpe'] > champion['sharpe']
            row = dict(config=config, metrics=summary(full), dominates=bool(dominates), thrashing=thrashing, causal_checks=checks)
            if config['meta'] == 'scale':
                weight = pd.Series(kwargs['entry_scale']).reindex(prepared[config['family']][0]).fillna(0)
                row['weight_changes'] = dict(days=int((weight.diff().abs()>1e-12).sum()),
                    mean_abs_change=float(weight.diff().abs().mean()), max_abs_change=float(weight.diff().abs().max()))
            if dominates:
                row['robustness'] = robust(config, prepped, prepared, regime, frames, full, thrashing)
            rows.append(row)
            output['experiments'].append(row)
            save(output)
            print('RESULT',len(output['experiments']),config,summary(full),row.get('robustness',{}).get('verdict'),flush=True)
            if row.get('robustness',{}).get('verdict') == '통과':
                output['status'] = '복귀조건 A 달성'
                break
        output['sections'].append(section)
        write_section(section,title,rows,output)
        save(output)
        subprocess.run([sys.executable,'-m','app.verify_round10'],cwd=ROOT,check=True)
        git_section(section,output)
        if output['status'] == '복귀조건 A 달성':
            break
    if output['status'] != '복귀조건 A 달성':
        assert len(output['experiments']) >= 50 and {r['config']['meta'] for r in output['experiments']} == {'gate','scale','switch'}
        output['status'] = '복귀조건 B 달성'
        output['sections'].append(28)
        top = sorted(output['experiments'],key=lambda r:(-r['metrics']['sharpe'],-r['metrics']['cagr']))[:3]
        output['closest'] = [r['config'] for r in top]
        with DOC.open('a') as stream:
            stream.write('\n\n## 28. 라운드1~10 최종 결론 (2026-10-07)\n\n')
            stream.write('- Round1(§13) 10신호/스윕; Round2(§14) 하이브리드/CB; Round3(§15) 재진입/변동성사이징; Round4(§16) 강건성 기각; Round5(§17) 챔피언집중/앙상블 기각; Round6(§18) BTC초과기간/쏠림완화; Round7(§19) 챔피언통계검증 통과; Round8(§21~22) TOP_K12 느슨한3/4 판정; Round9(§23~24) 강화기준 최종기각; Round10(§25~27) BTC 레짐 비중/전략교체 검증.\n')
            stream.write(f'- Round10 신규 {len(output["experiments"])}조합, 세 축 우위 {sum(r["dominates"] for r in output["experiments"])}개, 5검증 전부통과0개. 무레짐5개 재현은 신규 조합수에 더하지 않는다. 확인기간·4단계2매핑·ATR/ROC·완화·7개교체쌍/2청산방식을 검토했다.\n')
            stream.write('**최종 판정: Round1~10 조사범위 내에서 §12 챔피언을 CAGR/MDD/Sharpe 세 축 전부에서 지배하면서 필수 강건성 검증을 모두 통과하는 대체 전략은 발견되지 않았다. BTC 레짐 메타전략도 승격 근거를 확보하지 못했다.**\n\n')
            for row in top:
                stream.write(f'- Sharpe 기준 근접 조합: {json.dumps(row["config"],ensure_ascii=False)}, {json.dumps(row["metrics"],ensure_ascii=False)}, 세축 {row["dominates"]}, 강건성 {row.get("robustness",{}).get("verdict","세축 미충족으로 미실행")}.\n')
            stream.write('- 레짐 위험축소는 강세 초기/회복기 노출을 함께 줄이고, FRVP·VWAP라는 신호명 자체가 베어장에서 유효한 평균회귀 엣지를 보장하지 않는다. 확인기간은 짧은 재전환을 줄이는 대신 신규 진입과 전략전환을 늦춘다. 구체 반례·전체수치·탈락항목은 §25~27 표와 원시 JSON으로 확인한다.\n- 챔피언의 §19 통계검증을 유지하되 실거래승격으로 해석하지 않는다. 상위10건103%/상위5종목87.85% 집중, 미관측OOS 부재, 겹친창, 반복탐색 선택편향 미보정, 비용/펀딩/생존편향 미반영은 남는다. 신규 탐색이 모든 BTC 레짐 규칙의 실패를 증명하지는 않는다.\n\n**복귀조건 B 달성 — 조사범위 내 미발견.**\n')
        save(output)
        subprocess.run([sys.executable,'-m','app.verify_round10'],cwd=ROOT,check=True)
        git_section(28,output)
    print(output['status'],flush=True)


if __name__ == '__main__':
    run()
