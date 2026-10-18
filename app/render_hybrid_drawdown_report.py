"""Reproducible Korean Round 2 section from execution and verification artifacts."""
import json
from app.crypto_hybrid_drawdown_research import ROOT, PATH, LABELS

LABELS={**LABELS,'volume_spike_cap5':'§12 실제 챔피언 cap5% 재실행판'}


def label(r):
    return LABELS[r['name']]+(f" / CB {r['dd_trigger']:.0%}" if 'dd_trigger' in r else ' / CB 없음')


def metric_row(title,m):
    return f"| {title} | {m['cagr']:+.2f}% | {m['mdd']:.2f}% | {m['sharpe']:.3f} | {m['trades']} |"


def render():
    d=json.loads(PATH.read_text()); verification=(ROOT/'docs/hybrid-drawdown-verification-2026-10-06.txt').read_text()
    assert 'PASS:' in verification
    lines=['## 14. 하이브리드 신호 + 드로다운 서킷브레이커 (2026-10-06, 라운드2)','',
           '실행: `python3.12 -m app.crypto_hybrid_drawdown_research`. 원시 결과: `docs/hybrid-drawdown-results-2026-10-06.json`. 실행 로그: `docs/hybrid-drawdown-execution-2026-10-06.log`. 검증: `python3.12 -m app.verify_hybrid_drawdown`, `docs/hybrid-drawdown-verification-2026-10-06.txt`. 문서 생성: `python3.12 -m app.render_hybrid_drawdown_report`.','',
           '### 14-1. 엔진 공정비교 보정','',
           '| 설정·엔진 | CAGR | MDD | Sharpe | 매매건수 |','|---|---|---|---|---|',
           '| §12-3 원본 cap3%·구엔진 | +54.2% | 56.2% | 1.09 | 원본 미기록 |',
           '| §12-3 원본 cap5%·구엔진(실제 최고 Sharpe) | +66.1% | 53.7% | 1.20 | 원본 미기록 |']
    for pair in d['engine_comparison']:
        for engine,title in [('legacy','구엔진 동일 캐시 재실행'),('new','신규엔진 재실행')]:
            lines.append(metric_row(f"cap{pair['price_cap']:g}% / {title}",pair[engine]))
    lines+=['',
        '- **요청 배경의 cap3%=+66.1% 연결은 원본 §12-3과 다르다.** 실제 챔피언은 cap5%다. 필수 실험의 재기준선은 요청대로 cap3%이며, 실제 챔피언 cap5% 신규엔진 결과도 별도 재기준선으로 제시했다. §12-4의 “cap3% 승자” 표현도 이 구분으로 해석해야 한다.',
        '- **§14 전체는 2019-09-08~2026-10-05, 신규엔진, 동일 45종목 캐시로 통일했다.** SINCE=2019-01-01 요청은 유지하되 캐시에 없는 2019-01-01~09-07 가격을 생성하지 않는다. 캐시 SHA256·종목별 시작일이 Round 1 manifest와 완전히 일치했다. 상장 전 후보 제외, 미완성 UTC 봉 제외.',
        '- 거래량폭증 및 하이브리드의 거래량 조건: 20일 과거평균×3 이상, 종가 등락률 상한 미만(음수 포함). 체결·계좌 공통: 다음날 실제 시가, TOP_K=8·20일·손절/익절/레짐 없음·무배율·편도 수수료 0.04%. 매매건수는 청산 완료 건수이며 신규엔진은 최종일 강제청산을 포함한다. Sharpe는 일수익률 표본표준편차×√365·무위험수익률 0.',
        '- **기간 고정의 엔진 순효과: cap3% CAGR −3.218%p, MDD +0.114%p, Sharpe −0.03424, 청산 −6건; cap5% CAGR −3.630%p, MDD −0.278%p, Sharpe −0.03369, 청산 −7건.** 당일 종가를 미리 사용한 시가 배분 제거, 당일 종가 만기청산금의 같은 시가 재투자 제거, 최종 강제청산 수수료 등 엔진 차이의 합계다. 배분 버그 하나의 기여도만 분리한 실험은 아니다.',
        '- **원본 대비 기간·데이터 효과는 정확히 식별 불가다.** 같은 구엔진·cap3% 재실행은 원본 +54.2% 대비 −0.088%p, cap5%는 +66.1% 대비 −0.116%p다. 원본은 반올림 수치이고 원본 캐시 SHA256·정확한 종료봉·개별 거래 원장이 없어 이 잔차를 “시작일 이동 때문”으로 단정할 수 없다. SINCE 문자열이 2019-01-01이어도 실제 선물 데이터 시작일이 같았을 수 있다. 2019-09-08 이전 부재 구간의 효과를 계산할 증거는 없다. §12 원본 수치는 역사 기록이며 승자 비교에는 사용하지 않는다.','',
        '### 14-2. 하이브리드 신호 2종 baseline 결과','',
        '| 신호·CB 없음 | CAGR | MDD | Sharpe | 매매건수 |','|---|---|---|---|---|']
    for r in d['baselines']: lines.append(metric_row(LABELS[r['name']],r['metrics']))
    for child,parent in [('heikin_ashi_volume_spike','heikin_ashi'),('frvp_volume_spike','frvp')]:
        a=next(r for r in d['baselines'] if r['name']==child);b=next(r for r in d['baselines'] if r['name']==parent)
        lines.append(f"\n- **{LABELS[child]} MDD {b['metrics']['mdd']-a['metrics']['mdd']:.2f}%p 개선, 원시 교집합 신호 {a['signal_count']}건·매매 {a['metrics']['trades']}건.** 단독 신호와 거래량폭증이 같은 날 True인 교집합만 인정하고 거래량비율 내림차순으로 배분한다. CAGR {a['metrics']['cagr']:+.2f}%·Sharpe {a['metrics']['sharpe']:.3f}로 목표 미달이며 낮은 낙폭만으로 필터의 우수성을 입증하지 못했다.")
    lines+=['','- **단독 하이킨 아시·FRVP 재실행은 Round 1 반올림 전 수치와 일치했다.** FRVP는 일봉 전형가격 히스토그램 근사이며 실제 가격별 거래량이 아니다.','',
        '### 14-3. 드로다운 서킷브레이커 20조합 결과','',
        '| 전략 | 중단 X | CAGR | MDD | Sharpe | 매매 | MDD 개선 %p | CAGR 손실 %p | Sharpe 손실 | 중단/재개 | 차단일 |','|---|---|---|---|---|---|---|---|---|---|']
    for r in d['sweep']:
        m=r['metrics'];lines.append(f"| {LABELS[r['name']]} | {r['dd_trigger']:.0%} | {m['cagr']:+.2f}% | {m['mdd']:.2f}% | {m['sharpe']:.3f} | {m['trades']} | {r['mdd_improvement']:.2f} | {r['cagr_loss']:.2f} | {r['sharpe_loss']:.3f} | {m['breaker_events']}/{m['breaker_resumes']} | {m['blocked_days']} |")
    lines+=['',
        '- **피크는 초기자산 1에서 시작해 관측한 시가·종가 평가자산만으로 갱신한다.** 시가 갭 손절 처리 후 현재 시가 평가 → DD≥X면 그 시가 신규 진입 차단, 종가 평가 → DD≥X면 다음 시가부터 차단. 중단 중 DD≤10%면 재개한다. 기존 포지션의 손절·만기·최종 청산은 유지하며 피크를 중단 시 리셋하지 않는다.',
        '- **서킷브레이커는 최대낙폭 보장 장치가 아니다.** 기존 포지션이 계속 손실을 내므로 X보다 MDD가 더 커질 수 있다. 시가/종가 온라인 피크와 보고 MDD의 종가 피크 기준도 다르다.',
        '- **현금화 후 계좌 회복 불가능이라는 영구중단 문제가 있다.** 계좌 자체의 피크 대비 회복만 재개 조건으로 삼으면 무수익 현금은 회복하지 못한다. 20조합 중 실제 중단이 발생한 12조합 모두 종료 시점에 중단 상태다. 하이브리드 8조합은 임계점에 도달하지 않아 baseline 수치가 그대로다. 재개용 별도 시장 신호나 가상 운용계좌는 이번 요구사항에 추가하지 않았다.',
        '- **최대 낙폭 개선은 FRVP·CB15%(CB20% 동률): 73.07%→21.40%, 51.67%p 개선.** CAGR 67.45%→−2.24%(69.69%p 손실), Sharpe 1.113→−0.349(1.462 손실), 5건 후 장기간 현금 대기다. 위험조정 운용 개선으로 채택할 근거가 없다.','',
        '### 14-4. 목표 달성 여부·Pareto 후보·Round 3','',
        f"- **Round 2 승자 {'있음' if d['winners'] else '없음'}: 필수 25조합과 실제 cap5% 챔피언 재실행을 포함한 26조합 중 CAGR≥66% AND Sharpe≥1.20 AND MDD≤55% 동시 충족 {len(d['winners'])}조합.** 판정은 반올림 전 수치를 사용했다. 실제 챔피언 신규엔진 baseline 자체도 CAGR·Sharpe 목표에 미달한다.",
        '- 후보는 CAGR·Sharpe 최대화/MDD 최소화 3축의 비지배 집합에서 정규화 목표 미달량 합계가 작은 3개를 선택했다. 미달량=max(0,(66−CAGR)/66)+max(0,(1.20−Sharpe)/1.20)+max(0,(MDD−55)/55). 유일한 경제적 최적점이라는 뜻은 아니다.','',
        '| Pareto 후보 | CAGR | MDD | Sharpe | 매매건수 |','|---|---|---|---|---|']
    for r in d['closest_candidates']:lines.append(metric_row(label(r),r['metrics']))
    lines+=['',
        '- **cap5% 신규엔진: MDD 통과, CAGR 3.65%p·Sharpe 0.0354 부족.** 요청 cap3% 재기준선을 세 축 모두에서 지배하지만 고정 목표는 미달이다.',
        '- **FRVP·CB30%: Sharpe·MDD 통과, CAGR 19.66%p 부족.** 신규 cap3% 대비 CAGR은 낮고 Sharpe·MDD는 개선된다. 재개 없이 1,965일 진입 차단된 결과이므로 지속 운용 가능한 승자로 해석하지 않는다.',
        '- **하이킨 아시 단독: CAGR 통과, Sharpe 0.0903 부족·MDD 17.24%p 초과.** 고수익을 유지하며 위험을 줄이는 후속 연구용 비교군이다.',
        '- **검증 통과.** 신규·수정 Python 모듈 py_compile, Round 1 전체 신호 prefix/체결검증 재실행, 하이브리드 45종목 prefix·교집합 검증, 서킷브레이커 실제 데이터 12개 prefix와 합성 중단/재개/시가갭/현금 영구중단 검증을 수행했다. 최종봉 강제청산은 prefix의 마지막 봉에만 발생하므로 온라인 비교에서 마지막 봉을 제외했다. 25개 필수 결과와 cap5% 추가 baseline의 공통기간·유한 수치·매매 0건 없음·목표 판정도 확인했다. FRVP 교집합 4건은 버그가 아닌 과도한 희소성이며 통계적 근거가 부족하다.',
        '- 펀딩비·슬리피지·시장충격·상장폐지 생존편향 미반영, 동일 표본 반복탐색 결과다. 워크포워드 전 실거래 승격 보류.','',
        '### 다음 (TODO, Round 3)','',
        '- **변동성 기반 포지션 사이징:** 신호일 ATR/종가 또는 과거 20~60일 실현변동성으로 종목 비중을 정하고 계좌 목표변동성·현금 최소비중을 적용한다. cap5% 재기준선과 하이킨 아시를 대상으로 동일 기간·엔진에서 고정 TOP8 배분과 비교하고 연도별/워크포워드로 확인한다.',
        '- **회복 가능한 재진입 규칙:** 영구 현금 잠김을 제거하도록 중단 중 수익에 반영하지 않는 가상계좌 또는 BTC 추세 회복+최소 대기기간으로 재개를 판단한다. 기존 계좌 회복 규칙과 별도 전략으로 명시하고 미래참조 검증·재개 횟수·중단 지속기간을 함께 기록한다.',
        '- **상관관계 기반 분산:** 과거 수익률만으로 동시 후보 군집을 만들고 군집별 비중 상한과 현금 비중 확대(무배율 상태에서 총 투자비중 축소)를 적용한다. 같은 날 엄격 교집합 대신 최근 3~5일 신호 확인창도 독립 실험하고 신호 수·노출일수·MDD/CAGR 손실을 비교한다.',
        '- cap5% 재기준선 및 FRVP·CB30%를 연도별/워크포워드·펀딩비·슬리피지 포함으로 재검증. FRVP 실제 volume-at-price 검증, pandas_ta/TA-Lib fallback 수치 대조, 국장/미장 포트폴리오·KIS 캐싱 과제 유지.','', '---','']
    p=ROOT/'docs/전략-백테스트-종합.md';s=p.read_text()
    if '## 14. 하이브리드' in s:
        a=s.index('## 14. 하이브리드');b=s.index('## 결론',a);s=s[:a]+s[b:]
    s=s.replace('### 다음 (TODO)\n','### 다음 (TODO, §13 당시 — 최신 우선순위는 §14 참고)\n')
    s=s.replace('- 거래량폭증 계좌단위 서킷브레이커·국장/미장 포트폴리오 로테이션·KIS 캐싱은 기존 미완료 과제로 유지.', '- 거래량폭증 계좌단위 서킷브레이커는 §14에서 검증 완료. 영구중단 문제 개선은 Round 3 과제이며 국장/미장 포트폴리오 로테이션·KIS 캐싱은 미완료 과제로 유지.')
    s=s.replace('## 결론','\n'.join(lines)+'\n## 결론',1);p.write_text(s)


if __name__=='__main__':
    render()
