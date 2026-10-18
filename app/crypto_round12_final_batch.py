"""Third Round12 batch; no claim that a finite grid exhausts all ideas."""
import json
from app.crypto_round12_research import PATH, DOC, save, execute, verify_and_section, git_section
from app.crypto_technical_ict_research import load_data


def groups():
    return [
        (59, 'Donchian·마하세븐 BTC확인기간과 보유기간 결합',
         [dict(family=n, btc_trend=True, btc_confirm=5, sizing='inverse_vol', target_vol=v, weight_cap=.25)
          for n in ['mach7', 'donchian', 'gap'] for v in [.8, 1.2]]),
        (60, '미소진 CCI·ROC·CMF·Stochastic 신호와 두 필터',
         [dict(family=n, **x) for n in ['cci', 'roc', 'cmf', 'stochastic']
          for x in [{'self_trend':True, 'volume_confirm':True}, {'weekly_trend':True, 'rank':'residual'}]]),
        (61, 'Donchian·압축돌파 시장폭과 위험예산',
         [dict(family=n, breadth=True, rank='low_vol', hold_days=h, top_k=k)
          for n in ['donchian', 'gap', 'compression_breakout'] for h, k in [(10, 8), (40, 8), (20, 12)]]),
    ]


def run():
    frames, manifest, skipped = load_data()
    out = json.loads(PATH.read_text())
    assert not skipped and manifest == out['manifest']
    if out['status'] == '복귀조건 A 달성':
        return
    out['status'] = '탐색중'
    save(out)
    for section, title, configs in groups():
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
    out['status'] = '복귀조건 미달성, 계속 진행 필요'
    out['next'] = ['완료월봉과 일봉압축 결합', '과거완료거래 승률의 축소추정 사이징',
                   '미소진 Aroon/WilliamsR/Ichimoku/PSAR 신호와 신규 필터 결합']
    save(out)
    if 62 not in out['sections']:
        with DOC.open('a') as f:
            f.write('\n\n## 62. 라운드12 세 번째 탐색 후 재개 지점 (2026-10-07)\n\n')
            f.write(f'- 1단계 고유진입전략 {len({r["config"]["family"] for r in out["experiments"] if r["phase"] == 1})}종, 변형포함 {sum(r["phase"] == 1 for r in out["experiments"])}조합. 2단계 {sum(r["phase"] == 2 for r in out["experiments"])}개 새조합, 신규총 {len(out["experiments"])}조합. §52/58보다 최신집계다.\n')
            f.write(f'- 세축우위 {sum(r["dominates"] for r in out["experiments"])}개는 모두 5검사 전부실행, 엄격전부통과 {sum(r.get("robustness", {}).get("verdict") == "통과" for r in out["experiments"])}개.\n')
            f.write('- 신규필터 정의: 자체추세=종가>SMA200; 거래량확인=전20일중앙값대비1.5배; 주봉=완료일요일UTC종가>10주평균을 이후일에만 forward-fill; 시장폭=유효50일평균상방종목/유효종목≥50%; 지속성=거래대금/직전60일중앙값≥1.5인날이 최근5일중3일이상; 요일=익일진입일UTC평일; 월경계=익일1~5일 또는25일이후.\n')
            f.write('- 순위 정의: 상대강도=90일종가수익률; 저변동=20일일수익률표준편차의음수; 하방변동=30일음수수익률제곱평균제곱근의음수; BTC잔차=전일까지90일(최소60)공분산/분산 베타로 당일수익률−베타×BTC당일수익률 계산후20일합. 순위지표의 초기결측값은−1. 신규상장자료를 미래기간에서 역보충하지 않는다.\n')
            f.write('- 신규진입축: 압축돌파=20일BB폭(4×표준편차/평균)이직전120일25분위미만인날이최근10일존재+종가>직전20일고점+SMA50상방; 건조눌림=거래량<직전20일평균0.6배+종가<10일평균인날이직전5일존재후전일고점회복+SMA50상방+거래량전일대비증가; OBV=누적부호수익률×거래량이직전55일고점돌파+가격20일돌파+SMA50상방; 잔차반등=직전5일BTC잔차합<직전60일잔차표준편차×−√5후양의잔차+가격반등+SMA200상방.\n')
            f.write('- 추가레포신호: CCI20<-100·SMA200상방(205일워밍업), ROC12>5%·SMA200상방(205일), CMF20의0상향돌파·SMA50상방(55일), Stochastic14/3/3 K>D상향교차·K<20(30일). 새조합에는지정추세/거래량또는완료주봉/잔차순위를추가했다.\n')
            closest = sorted(out['experiments'], key=lambda r: max(0, (out['baseline']['cagr']-r['metrics']['cagr'])/out['baseline']['cagr'])+max(0, (r['metrics']['mdd']-out['baseline']['mdd'])/out['baseline']['mdd'])+max(0, (out['baseline']['sharpe']-r['metrics']['sharpe'])/out['baseline']['sharpe']))[:3]
            for r in closest:
                f.write(f'- 세축거리 근접: {r["config"]}, {r["metrics"]}, 검증판정 {r.get("robustness", {}).get("verdict", "세축미달")}。\n')
            f.write('- **복귀조건 미달성, 계속 진행 필요.** 합리적 아이디어가 '+ ' / '.join(out['next'])+'으로 남아 있다. 최소20개 탐색은 만족하지만 B의 아이디어소진 조건을 만족하지 못했다. §63부터 이어서 진행한다.\n')
        out['sections'].append(62)
        save(out)
        git_section(out, 62)
    print(out['status'], flush=True)


if __name__ == '__main__':
    run()
