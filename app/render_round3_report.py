"""Render the Korean Round 3 tables directly from verified artifacts."""
import json
from app.crypto_round3_research import ROOT, PATH, LABELS


def label(r):
    c=r['config'];s=LABELS[r['name']]
    if 'dd_trigger' in c:
        s+=f" / CB{c['dd_trigger']:.0%} / "+(f"쿨다운{c['cooldown_days']}일" if c['resume_mode']=='cooldown' else 'BTC>SMA50')
    elif c.get('sizing'): s+=' / 역변동성40%'
    return s


def row(title,m):
    return f"| {title} | {m['cagr']:+.2f}% | {m['mdd']:.2f}% | {m['sharpe']:.3f} | {m['trades']} |"


def render():
    d=json.loads(PATH.read_text())
    verification=(ROOT/'docs/round3-verification-2026-10-06.txt').read_text()
    assert 'PASS:' in verification
    lines=['## 15. 서킷브레이커 재진입 수정 + 변동성사이징 + 완화된 하이브리드 (2026-10-06, 라운드3)','',
           '실행: `python3.12 -m app.crypto_round3_research`. 원시 결과: `docs/round3-results-2026-10-06.json`. 실행 로그: `docs/round3-execution-2026-10-06.log`. 검증: `python3.12 -m app.verify_round3`, `docs/round3-verification-2026-10-06.txt`. 문서 생성: `python3.12 -m app.render_round3_report`. 연구 종료봉과 섹션 날짜는 Round 2와 고정했고 실제 실행일은 2026-10-07이다.','',
           '- **유일한 기준선은 cap5% 신엔진 재실행판이다.** 2019-09-08~2026-10-05·동일 45종목 캐시 SHA256 일치·TOP_K=8·20일 보유·다음날 시가·손절/익절 없음·무배율·편도 수수료 0.04%. §12 구엔진 수치는 역사 기록으로만 남긴다.',
           '- **요청 목표는 반올림 전 결과에 CAGR≥62.35% AND Sharpe≥1.165 AND MDD≤53.38%를 적용한다.** 실제 기준선은 CAGR 62.3537020197% / MDD 53.3838464735% / Sharpe 1.1645781354다. 기준선 자체는 표기 목표의 Sharpe·MDD를 미세하게 넘지 못하므로, 실제 기준선 세 축 동등 이상 판정도 별도로 기록했다. 신규 53조합의 두 판정 승자 집합은 일치한다.','',
           '| 신엔진 균등비중 비교군 | CAGR | MDD | Sharpe | 매매건수 |','|---|---|---|---|---|']
    for r in d['baselines']:lines.append(row(LABELS[r['name']],r['metrics']))
    lines+=['','### 15-1. 서킷브레이커 재진입 로직 수정 결과','',
           '| 전략·재개 | CAGR | MDD | Sharpe | 매매 | 중단/재개 | 차단일 | 종료 대기(경과일) |','|---|---|---|---|---|---|---|---|']
    for r in d['breaker']:
        m=r['metrics'];lines.append(row(label(r),m)+f" {m['breaker_events']}/{m['breaker_resumes']} | {m['blocked_days']} | {'대기' if m['breaker_paused_final'] else '운용'}({m['paused_age_final']}) |")
    paused=[r for r in d['breaker'] if r['metrics']['breaker_paused_final']]
    cooldown=[r for r in paused if r['config']['resume_mode']=='cooldown']
    lines+=['',
        '- **48조합 모두 실제 재개 이벤트가 발생했고, 계좌가 현금이라 회복할 수 없는 구조적 영구잠금은 해소됐다.** 계좌 피크는 리셋하지 않는다. 쿨다운은 발동 인덱스에서 20/40/60 거래봉 경과한 시가에 재개한다. 코인은 주말 포함 일봉이 거래일이다. BTC 방식은 전일 완료 종가>SMA50이면 다음 시가에 재개하며, 중단 후 반드시 새로운 상향교차를 요구하지는 않는다. 신호 당일 종가를 당일 시가에서 사용하지 않는다.',
        '- **재개일 전체에 신규 진입을 허용하고 다음 거래일부터 DD≥X를 다시 평가한다.** 재개와 중단을 같은 관측에서 처리하면 진입 기회 없이 즉시 재잠기므로 1일 유예를 명시했다. 유예 외에는 원래 피크 대비 중단 임계값 15/20/25/30%를 그대로 유지하고, 기존 포지션은 만기/최종일에 청산한다. 전량 즉시청산 옵션은 추가하지 않았다.',
        f"- **종료 시 중단 상태는 {len(paused)}/48조합이다.** 전부 쿨다운 방식({len(cooldown)}/36)이며 마지막 중단 후 설정된 대기일이 아직 지나지 않았다. BTC 방식 12조합은 전부 종료 시 운용 상태다. 종료 대기를 영구잠금으로 오인하지 않도록 각 조합의 이벤트 날짜·대기 경과일과 검증 로그 사유를 기록했다. 미경과 대기 이후의 실제 미래 성과는 측정하지 않았다.",
        '- **재개가 MDD 개선을 보장하지 않는다.** 중단 중 보유종목의 추가 손실과 재개 후 손실이 가능하다. BTC 방식은 피크 아래에서 중단·재개를 반복하며 하이킨 아시 CB25%는 수백 회 이벤트가 생긴다. 이 반복 구조를 결과에서 숨기지 않고 펀딩비·슬리피지 포함 후속 검증 대상으로 남긴다.','',
        '| 재개방식별 최고 Sharpe(사후 선택) | CAGR | MDD | Sharpe | 매매건수 |','|---|---|---|---|---|']
    deltas=[]
    for baseline in d['baselines']:
        for mode in ['cooldown','btc_sma50']:
            r=max([r for r in d['breaker'] if r['name']==baseline['name'] and r['config']['resume_mode']==mode],key=lambda r:r['metrics']['sharpe'])
            lines.append(row(label(r),r['metrics']))
            m=r['metrics'];b=baseline['metrics']
            deltas.append(f"- **{label(r)}: 해당 단독 대비 CAGR {m['cagr']-b['cagr']:+.2f}%p / MDD {m['mdd']-b['mdd']:+.2f}%p / Sharpe {m['sharpe']-b['sharpe']:+.3f}.** MDD 음수 차이가 낙폭 개선이다.")
    lines+=['']+deltas+['']
    lines+=['### 15-2. 변동성 타겟 포지션사이징 결과','',
           '| 전략·배분 | CAGR | MDD | Sharpe | 매매건수 |','|---|---|---|---|---|']
    for r in d['volatility']:
        baseline=next(b for b in d['baselines'] if b['name']==r['name'])
        lines.append(row(LABELS[r['name']]+' / 균등',baseline['metrics']))
        lines.append(row(label(r),r['metrics']))
    lines+=['',
        '- **신규 진입의 역변동성 배분은 직전 완료봉까지 20개 일별 수익률 표본표준편차×√365만 사용한다.** 워밍업 부족·0변동성은 진입 제외한다. 후보 역변동성 비례 비중을 가용현금/계좌와 후보수/8 중 작은 투자 풀에 배분하고 25%로 캡한다. 캡 후 남는 자금은 현금으로 남긴다. 적은 후보가 계좌 전액을 차지하지 않도록 슬롯 용량을 유지한다.',
        '- **연환산 목표 40%는 신규 배분 시점의 추정 위험 상한이다.** 기존 비중×개별 연환산 σ의 합과 신규 비중×σ의 합을 사용한다(완전 양의 상관 가정). 신규 배분만 축소하고 기존 포지션은 재조정하지 않는다. 따라서 이후 가격·변동성 변화에 따른 실제 계좌 변동성이나 기존 비중의 25% 초과를 항상 막는 장치는 아니다. 공분산 모델을 추정한 결과도 아니다.','']
    for r in d['volatility']:
        b=next(b['metrics'] for b in d['baselines'] if b['name']==r['name']);m=r['metrics']
        lines.append(f"- **{LABELS[r['name']]}: CAGR {m['cagr']-b['cagr']:+.2f}%p / MDD {m['mdd']-b['mdd']:+.2f}%p / Sharpe {m['sharpe']-b['sharpe']:+.3f}.** 낙폭은 감소했지만 CAGR 목표는 미달이다.")
    lines+=['','### 15-3. 하이브리드 확인창 완화(±3거래일) 결과','',
           '| 하이브리드·확인창 | CAGR | MDD | Sharpe | 매매건수 |','|---|---|---|---|---|']
    for r in d['loose']:
        lines.append(row(LABELS[r['name']].replace(' ±3일','')+' / 같은 날 AND',r['strict']['metrics']))
        lines.append(row(LABELS[r['name']],r['metrics']))
    lines+=['',
        '- **두 신호 간격≤3개 종목 거래봉일 때 더 늦은 신호일에만 확정하고 다음 시가에 진입한다.** 현재 보조신호 AND 최근 0~3봉 거래량 신호, 또는 현재 거래량 신호 AND 최근 0~3봉 보조신호다. 과거 첫 신호일로 소급하지 않는다. 두 신호가 모두 과거에만 있으면 새로운 신호를 생성하지 않는다. 여러 보조 이벤트가 같은 거래량 이벤트와 대응하면 각각 확정 가능하지만 보유 중에는 재진입하지 않는다. 랭킹은 최근 유효 거래량 이벤트의 거래량비율을 쓴다. cap3%는 Round 2 하이브리드 조건 그대로이며 cap5% 기준선과 구분한다.','']
    for r in d['loose']:
        m=r['metrics'];b=r['strict']['metrics']
        lines.append(f"- **{LABELS[r['name']]}: 매매 {b['trades']}→{m['trades']}건({m['trades']/b['trades']:.2f}배), 원시 신호 {r['strict']['signal_count']}→{r['signal_count']}건.** CAGR {m['cagr']-b['cagr']:+.2f}%p / MDD {m['mdd']-b['mdd']:+.2f}%p / Sharpe {m['sharpe']-b['sharpe']:+.3f}. 엄격 교집합의 낮은 낙폭은 희석됐고 수익은 증가했지만 목표에는 미달한다.")
    lines+=['','### 15-4. 목표 달성 여부 — Round 3 승자','',
        f"- **Round 3 승자 {len(d['winners'])}조합: 신규 53조합(서킷브레이커 48+변동성 3+완화 2) 중 요청 목표와 실제 기준선 동등 이상을 모두 충족했다.** 같은 표본에서 선택한 연구 승자이며 실거래 승격 판정은 아니다.",'',
        '| 목표 동시 충족 조합 | CAGR | MDD | Sharpe | 매매건수 |','|---|---|---|---|---|']
    for r in d['winners']:lines.append(row(label(r),r['metrics']))
    winner=max(d['winners'],key=lambda r:r['metrics']['sharpe'])
    m=winner['metrics'];b=d['reference']
    lines+=['',f"- **최고 Sharpe 승자: {label(winner)}.** cap5% 신엔진 기준선 대비 CAGR {m['cagr']-b['cagr']:+.2f}%p / MDD {m['mdd']-b['mdd']:+.2f}%p / Sharpe {m['sharpe']-b['sharpe']:+.3f}. FRVP CB20%·60일은 수익 목표 여유가 작지만 MDD 35.86%로 승자 중 가장 낮다.",
        '- **검증 통과:** 신규/수정 모듈 py_compile, 45종목 두 완화 신호의 독립 쌍 확인·prefix invariance, 두 신호 순서와 경계 3/4봉 검증, BTC SMA50 prefix·1봉 지연, 현금 상태 합성 재개·정확한 쿨다운·재개일 진입, 실제 3전략×3모드×3prefix 및 미래 가격 변조, 역변동성 비율/비중캡/추정위험 상한, 48조합 이벤트 전수 감사, 56결과 공통기간·매매 0건 없음·유한수치·목표 판정을 확인했다. 기존 Round 1/2 검증도 재실행했다. prefix 마지막 봉 강제청산은 온라인 비교에서 제외한다.',
        '- 펀딩비·슬리피지·시장충격·상장폐지 생존편향 미반영, 동일 표본 반복탐색의 과최적화 위험은 남는다.','',
        '### 다음 (TODO, Round 4)','',
        '- **워크포워드 검증:** 승자 5종을 고정한 뒤 연도별 수익·최대낙폭·최악 일수익·노출·비용을 비교하고, 학습 구간과 평가 구간을 분리한다. 신규 신호 튜닝보다 CB25% BTC 승자와 CB20% 60일 후보의 수익 집중도를 먼저 확인한다.',
        '- **재개 반복 감소:** BTC>SMA50에 최소 쿨다운과 상향교차 또는 3봉 지속확인을 결합한다. 기존 피크 유지와 새 위험 에피소드 기준을 별도 실험해 재개일 1일 유예 의존도와 이벤트 반복 횟수를 비교한다.',
        '- **상관관계·앙상블:** 과거 공분산 기반 배분과 군집 상한, 하이킨 아시/FRVP 독립 신호의 투표·분리 자본 버킷을 같은 신엔진에서 검증한다. 변동성 목표 40%의 CAGR 감소가 단순 노출 축소인지 종목별 배분 효과인지 분해한다.',
        '- FRVP 실제 volume-at-price, pandas_ta/TA-Lib fallback 수치 대조, 국장/미장 포트폴리오·KIS 캐싱 과제 유지.','', '---','']
    p=ROOT/'docs/전략-백테스트-종합.md';s=p.read_text()
    if '## 15. 서킷브레이커' in s:
        a=s.index('## 15. 서킷브레이커');b=s.index('## 결론',a);s=s[:a]+s[b:]
    s=s.replace('### 다음 (TODO, Round 3)','### 다음 (TODO, §14 당시 — 최신 우선순위는 §15 참고)')
    s=s.replace('## 결론','\n'.join(lines)+'\n## 결론',1);p.write_text(s)


if __name__=='__main__':
    render()
