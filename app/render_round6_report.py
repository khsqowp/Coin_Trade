"""Render complete Round 6 artifact into the Korean research record."""
import json
from app.crypto_round6_research import PATH, ROOT


def render():
    d = json.loads(PATH.read_text())
    lines = ['## 18. 알파기준 재판정 + 쏠림완화 시도 (2026-10-07, 라운드6)', '',
             '**Round 4/5의 절대기준 기간분리는 장세효과와 전략결함을 구분하지 못한 방법론적 결함이 있었다. 이번 라운드에서는 구간별 Sharpe≥0.5 AND CAGR≥0을 BTC 대비 CAGR 차이>0으로 교체한다. 기존 집중도·종목쏠림 불안정 판정은 유지한다.**', '',
             '기존 §16·§17 판정은 당시 기준의 기록으로 남긴다. 절대수익 부진만으로 과최적화를 단정한 해석은 철회한다. BTC 초과 CAGR은 요청한 알파 대용 지표이며 베타를 추정한 회귀 알파나 통계적 유의성의 증명이 아니다. 겹치는 롤링 창은 독립 표본이 아니며 미관측 OOS가 아니다.', '',
             '실행: `python3.12 -m app.crypto_round6_research`. 결과: `docs/round6-results-2026-10-07.json`. 실행·검증: `docs/round6-execution-2026-10-07.log`, `docs/round6-verification-2026-10-07.txt`. 문서 생성: `python3.12 -m app.render_round6_report`.', '',
             '### 18-1. 알파기준 재판정 결과', '',
             '- 전략 구간별 수치는 Round 4 승자 5개와 Round 5 챔피언 JSON에서 그대로 재사용했다. 48개 전략 구간의 신규 백테스트는 실행하지 않았다. 8개 경계는 Round 4 JSON을 직접 읽고 Round 5와 일치 확인했다.',
             '- BTC 캐시를 직접 읽어 시작일 시가 매수→종료일 종가 매도, 편도 0.04% 두 번을 적용했다. 최종배수=(종료종가/시작시가)×(1−0.0004)², CAGR=(최종배수^(365.25/경과일수)−1)×100. §13·§15 공통 benchmark 함수와 전체기간 수치가 1e-12 이내 일치한다.', '',
             '| BTC 구간 | 시작시가 | 종료종가 | B&H CAGR |', '|---|---:|---:|---:|']
    for b in d['btc']:
        lines.append(f"| {b['start']}~{b['end']} | {b['open']:.2f} | {b['close']:.2f} | {b['cagr']:+.2f}% |")
    lines += ['', '| 전략·구간 (48셀) | 전략 CAGR | BTC CAGR | 알파 (%p) | MDD | Sharpe | 거래수 | 절대기준 | 알파기준 |', '|---|---:|---:|---:|---:|---:|---:|---|---|']
    for r in d['strategies']:
        for p in r['periods']:
            m = p['metrics']
            lines.append(f"| {r['name']} / {p['start']}~{p['end']} | {m['cagr']:+.2f}% | {p['btc_cagr']:+.2f}% | {p['alpha']:+.2f} | {m['mdd']:.2f}% | {m['sharpe']:.3f} | {m['trades']} | {'통과' if p['absolute_pass'] else '실패'} | {'알파 있음(통과)' if p['alpha_pass'] else '알파 없음(실패)'} |")
    lines += ['', '| 전략 | 절대기준 실패 | 알파기준 실패 | 실패→통과 | 통과→실패 | 기간분리 판정 |', '|---|---:|---:|---:|---:|---|']
    for r in d['strategies']:
        lines.append(f"| {r['name']} | {r['absolute_failures']}/8 | {r['alpha_failures']}/8 | {r['converted']} | {r['newly_failed']} | {'기간분리 — 알파기준 안정' if r['alpha_failures']==0 else '알파기준으로도 불안정'} |")
    converted = sum(r['converted'] for r in d['strategies'])
    stabilized = sum(r['absolute_failures'] > 0 and r['alpha_failures']==0 for r in d['strategies'])
    bear = d['btc'][4]
    lines += ['', f"- 절대기준 실패 {sum(r['absolute_failures'] for r in d['strategies'])}/48 → 알파기준 실패 {sum(r['alpha_failures'] for r in d['strategies'])}/48. 실패→통과 {converted}셀, 전구간 실패 전략→안정 전략 {stabilized}개. 반대로 통과→실패 {sum(r['newly_failed'] for r in d['strategies'])}셀도 있다. 모든 절대기준 통과 구간이 BTC를 이기는 것은 아니다.",
              f"- **베어마켓 포함 2021-09-08~2023-09-07의 BTC B&H CAGR은 {bear['cagr']:+.2f}%, 누적수익은 {(bear['final']-1)*100:+.2f}%다.** 해당 시장 구간 자체가 나빴음을 가격·수수료 수치로 확인했다. 전략의 음수 CAGR 또는 낮은 Sharpe만으로 알파 부재를 단정할 수 없다. 상대우위도 쏠림·과최적화 부재의 증거는 아니다.", '',
              '### 18-2. 쏠림완화 시도 결과', '',
              '- 방법은 동일 종목 누적 완료 거래 비율 상한 1개, X=10/15/20% 3단계로 제한했다. §12 cap5%/신엔진의 신호·랭킹·보유·수수료를 재사용했다. 상한 차단은 랭킹/슬롯 선정 전에 적용하여 허용 종목이 기존 순위대로 슬롯을 채운다.',
              '- 전체 완료 거래가 0건이면 허용한다. 이후 해당 종목 완료수>상한×전체 완료수일 때 신규 진입만 차단하고, 비율이 상한 이하이면 허용한다. 미청산 포지션·당일 이후 종가 청산·미래 거래를 세지 않는다. 기존 보유는 정상 청산한다. 상한은 신규 진입 규칙이며 최종 거래 비중의 엄격한 상한은 아니다.',
              '- 실행 전 고정한 완화 통과 기준: 상위5 순손익 기여도 10%p 이상 감소 AND CAGR 손실 20%p 미만 AND Sharpe 상대손실 20% 미만. Sharpe는 %p가 아닌 무차원 값이므로 상대손실을 사용한다. 성과 개선은 음의 손실로 표기한다. 기여도 분모는 각 실행의 순누적손익이다.', '',
              '| X | 상위5 손익기여도 | 감소 (%p) | CAGR | CAGR 손실 (%p) | MDD | Sharpe | Sharpe 상대손실 | 거래수 | 완화 판정 |', '|---|---:|---:|---:|---:|---:|---:|---:|---:|---|']
    base = d['baseline']; m = base['metrics']
    lines.append(f"| 제한 없음 | {base['symbols']['net_pct']:.2f}% | 0.00 | {m['cagr']:+.2f}% | 0.00 | {m['mdd']:.2f}% | {m['sharpe']:.3f} | 0.00% | {m['trades']} | 기존 쏠림 불안정 |")
    for c in d['caps']:
        m=c['metrics']; loss=c['losses']
        lines.append(f"| {c['cap']*100:.0f}% | {c['symbols']['net_pct']:.2f}% | {loss['top5_reduction_pp']:+.2f} | {m['cagr']:+.2f}% | {loss['cagr_loss_pp']:+.2f} | {m['mdd']:.2f}% | {m['sharpe']:.3f} | {loss['sharpe_loss_relative_pct']:+.2f}% | {m['trades']} | {'통과' if c['mitigation_pass'] else '미달'} |")
    lines += ['', '| X | 손익 상위5종목 | 상위10거래 순손익 기여도 | 차단 판단 횟수 |', '|---|---|---:|---:|']
    for c in d['caps']:
        lines.append(f"| {c['cap']*100:.0f}% | {', '.join(c['symbols']['top5'])} | {c['concentration']['10']['net_pct']:.2f}% | {sum(e['blocked'] for e in c['decisions'])} |")
    lines += ['', '15%·20% 결과가 같은 이유는 두 실행 모두 2020-03-13의 BTC·LINK 신규 후보만 차단했기 때문이다. 당시 전체 완료 2건 중 각 종목 1건으로 비율이 50%였다. 이후에는 두 상한 모두 차단이 없어 거래 원장과 성과가 같았다. 10%는 이후에도 차단하지만 상위 손익 종목의 집중을 해소하지 못했다.', '',
              '거래 횟수와 절대손익은 다른 변수다. 거래 비율 제한만으로 큰 수익 거래의 종목 집중을 제거할 수 없었다. CAGR·Sharpe 개선만으로 쏠림 완화를 통과로 판정하지 않는다.', '', '### 18-3. 종합 판정표', '',
              '| 조합 | 알파기준 기간분리 | 기존 상위10거래 / 상위5종목 기여도 | 쏠림 상태 | 완화 시도 | 종합 판정 |', '|---|---|---|---|---|---|']
    for i,r in enumerate(d['strategies']):
        lines.append(f"| {r['name']} | {'전구간 통과' if r['alpha_failures']==0 else str(r['alpha_failures'])+'구간 실패'} | {r['top10_net_pct']:.2f}% / {r['top5_net_pct']:.2f}% | {'불안정 유지' if r['top10_net_pct']>=50 or r['top5_net_pct']>=50 else '50% 기준 미해당'} | {'10/15/20% 모두 미달' if i==0 else '미실행, 챔피언 결과 전이 불가'} | 후보 조건 미충족 |")
    assert not d['candidate']
    lines += ['', '**현재까지 가장 신뢰할 만한 후보는 없다.** 알파기준 전구간 통과와 쏠림완화 성공을 동시에 만족한 조합이 없다. 완화 옵션을 적용한 챔피언의 8개 기간은 새로 백테스트하지 않았으므로 원형 챔피언의 기간 판정을 수정 조합에 그대로 전이할 수도 없다. 실거래 승격이나 현재까지 최선이라는 표현을 사용하지 않는다.', '',
              '- 검증: 캐시 45종목 manifest 일치, 48셀 원본 재사용, BTC 공식·전체기간 기준값 일치, 3개 거래 원장과 일별 NAV 합산, 완료 거래수 독립 대조 및 차단 진입 부재, 2개 절단점×3개 X의 prefix·미래변형 총 12비교, 유한 수치·MDD 범위·옵션 미사용 기존 결과 회귀를 확인했다.',
              '- Round 1~5 회귀 로그: `docs/round6-round1-regression-2026-10-07.txt`, `docs/round6-round2-regression-2026-10-07.txt`, `docs/round6-round3-regression-2026-10-07.txt`, `docs/round6-round4-regression-2026-10-07.txt`, `docs/round6-round5-regression-2026-10-07.txt`. 신규/수정 모듈 py_compile 통과. 펀딩비·슬리피지·시장충격·생존편향은 기존과 같이 미반영이다.', '',
              '### 다음 (TODO, Round 7)', '',
              '- 최우선: 수익 쏠림의 원인과 §12-1 이벤트스터디 엣지 재검증. 같은 종목·시장 국면의 무작위 진입 대조, 종목/연도 제외, 블록 재표본화로 큰 수익 거래 의존성을 분리한다. 이번 거래 횟수 상한의 실패를 근거로 X 추가 튜닝은 중단한다.',
              '- BTC 초과 CAGR에 더해 시장 노출·베타·비용을 고정한 검증 계획을 작성한다. 완화 조합을 다시 검토하려면 그 조합 자체의 기간 안정성 검증이 필요하다. 전체기간 선택 편향과 겹치는 창을 명시한다.',
              '- 규칙·유니버스·허용 MDD·비용을 동결한 이후 신규 봉으로 전향적 모의운용을 수행하여 진짜 미관측 OOS를 확보한다. 역사적 후반 구간 재사용을 진짜 OOS로 부르지 않는다. 펀딩비·슬리피지·상장폐지 유니버스, FRVP volume-at-price, 국장/미장 KIS 캐싱 미완료 과제는 유지한다.', '', '---', '']
    path = ROOT / 'docs/전략-백테스트-종합.md'
    doc = path.read_text()
    doc = doc.replace('### 다음 (TODO, Round 6)', '### 다음 (TODO, §17 당시 — 최신 판정·우선순위는 §18 참고)')
    start = doc.find('## 18.')
    if start >= 0:
        doc = doc[:start] + doc[doc.index('## 결론',start):]
    doc = doc.replace('## 결론', '\n'.join(lines)+'\n## 결론',1)
    path.write_text(doc)
    print('PASS: section 18 rendered; 48 complete cells; 8 benchmarks; six verdicts; three caps; TODO updated')


if __name__ == '__main__':
    render()
