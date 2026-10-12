"""Render Round 5 tables from the reproducible offline artifact."""
import json
from app.crypto_bucket_ensemble_research import ROOT, PATH
from app.render_round4_report import row


def render():
    d = json.loads(PATH.read_text())
    champion = d['champion']
    lines = ['## 17. 챔피언 자체 검증 + 분리자본 앙상블 (2026-10-07, 라운드5)', '',
             f"**챔피언 자체 {champion['verdict']}({champion['unstable_count']}/4 불안정) · N=2 앙상블 {d['ensembles'][0]['verdict']} · N=3 앙상블 {d['ensembles'][1]['verdict']}. 현재까지의 비교기준 자체가 과최적화 위험을 안고 있다.**", '',
             '실행 순서: `python3.12 -m app.crypto_bucket_ensemble_research --champion` 완료·판정 확인 후 `python3.12 -m app.crypto_bucket_ensemble_research`. 원시 결과: `docs/round5-champion-results-2026-10-07.json`, `docs/round5-results-2026-10-07.json`. 실행 로그: `docs/round5-champion-execution-2026-10-07.log`, `docs/round5-ensemble-execution-2026-10-07.log`. 문서 생성: `python3.12 -m app.render_round5_report`.', '',
             '- **§16 방법론·판정 임계값 유지.** 기간 경계는 Round 4 JSON의 8개를 직접 읽었다. 구간마다 각 버킷의 자본=1·보유=0으로 독립 실행한다. 지표는 시작 전 역사로 워밍업하고 구간 첫날 신규진입 없음·마지막날 강제청산. CAGR은 365.25일, Sharpe는 일수익 표본표준편차·√365, MDD는 종가 곡선 기준이다.',
             '- **역사적 강건성 검사이며 미관측 OOS가 아니다.** 전체기간으로 이미 선택한 파라미터에 대한 검사이고 롤링 창은 겹친다. 기준선은 cap5%/신엔진·3배·20일·TOP_K=8·손절/익절/CB 없음·편도수수료0.04%·45종목·2019-09-08~2026-10-05로 고정했다. cap은 당일 등락률 상한이며 절댓값 제한이 아니다. SHA256 manifest가 Round 4와 전수 일치한다.',
             '- **수익 집중도와 종목쏠림 판정은 순누적손익 분모다.** 상위10거래≥50%, 손익 상위5종목≥50%면 불안정. 기간은 모든 창 Sharpe≥0.5·CAGR≥0이어야 안정. 민감도는 정렬된 인접점 ΔCAGR>30%p 또는 ΔMDD>10%p 또는 ΔSharpe>0.30이면 불안정. 2개 이상 실패면 기각; 1개 실패는 조건부 보류로 구분한다.', '',
             '### 17-1. 챔피언 자체 워크포워드/강건성 검증 결과', '',
             '| 전략 | CAGR | MDD | Sharpe | 매매건수 |', '|---|---|---|---|---|', row('챔피언 cap5%/신엔진', champion['full'])]

    def audit_tables(title, r):
        lines.extend(['', f"**{title}: {r['verdict']} · {r['unstable_count']}/4 불안정.**", '',
                      '| 독립 구간 | CAGR | MDD | Sharpe | 매매건수 |', '|---|---|---|---|---|'])
        for p in r['periods']:
            lines.append(row(f"{p['start']}~{p['end']}", p['metrics']))
        failures = [p for p in r['periods'] if p['metrics']['cagr'] < 0 or p['metrics']['sharpe'] < .5]
        lines.append(f"\n- 기간분리: {'불안정' if failures else '안정'}, {len(failures)}/8 구간 실패.")
        lines.extend(['', '| 상위 거래 | 절대손익 합 | 순누적손익 대비 | 양의 손익 합 대비 |', '|---|---|---|---|'])
        for n in ['10', '20']:
            c = r['concentration'][n]
            lines.append(f"| {n}건 | {c['pnl']:+.6f} | {c['net_pct']:.2f}% | {c['positive_pct']:.2f}% |")
        lines.extend(['', '| 제거 거래수(절대금액 고정) | CAGR | MDD | Sharpe | 남은 거래수 |', '|---|---|---|---|---|'])
        for p in r['leave_top_out']:
            lines.append(row(str(p['n']), p['metrics']))
        lines.extend(['', '| 제거 거래수(상대노출 고정 보조) | CAGR | MDD | Sharpe | 남은 거래수 |', '|---|---|---|---|---|'])
        for p in r['leave_top_out']:
            lines.append(row(str(p['n']), p['normalized_metrics']))
        lines.append('\n- 절대금액 고정은 원 체결일·수량·투자액을 유지하고 제거 거래 원금은 현금으로 남긴다. 거래별 매일 평가손익과 청산손익을 차감하며 후속 배분을 재계산하지 않는다. 자산≤0이면 CAGR/MDD/Sharpe는 산출 불가; 원시 낙폭은 정상 엔진 MDD가 아니다. 상대노출 보조는 남은 일별 손익을 원본 전일 NAV로 나눈 뒤 복리 연결한다. 모두 사후 스트레스이며 실행 가능한 신규전략이 아니다.')
        for p in r['leave_top_out']:
            m = p['metrics']
            if m['insolvent']:
                lines.append(f"- {p['n']}건 제거: 최초 자산≤0 {m['first_nonpositive_date']}, 최소자산 {m['minimum_equity']:+.6f}, 최종잔액 {m['final']:+.6f}.")
        sy = r['symbols']
        lines.extend(['', '| 종목(순손익 순) | 매매건수 | 순손익 기여(전체 초기자본 1) | 순손익 비중 |', '|---|---|---|---|'])
        for s in sy['rows']:
            lines.append(f"| {s['symbol']} | {s['trades']} | {s['pnl']:+.6f} | {s['pnl']/(r['full']['final']-1)*100:+.2f}% |")
        lines.append(f"\n- 손익 상위5종목 {', '.join(sy['top5'])}: 순손익 {sy['net_pct']:.2f}%, 매매건수 {sy['trades_pct']:.2f}%. 거래건수 상위5종목 {', '.join(s['symbol'] for s in sy['top5_by_count'])}: {sy['top5_count_pct']:.2f}%. 쏠림 판정: {'불안정' if r['flags']['symbols'] else '안정'}.")
        if 'excluded_metrics' in sy:
            lines.extend(['', '| 유니버스 | CAGR | MDD | Sharpe | 매매건수 |', '|---|---|---|---|---|', row('손익 상위5 제외 40종목', sy['excluded_metrics'])])
            delta = {k:sy['excluded_metrics'][k]-r['full'][k] for k in ['cagr','mdd','sharpe']}
            lines.append(f"\n- 40종목 재실행은 각 버킷의 신호·슬롯·현금을 전부 재계산했다. 원본 대비 CAGR {delta['cagr']:+.2f}%p / MDD {delta['mdd']:+.2f}%p / Sharpe {delta['sharpe']:+.3f}; 집중도 실패를 상쇄하지 않는다.")
        lines.extend(['', '| 검증 | 판정 |', '|---|---|'])
        for k, label in [('periods','기간분리'),('concentration','수익집중도'),('sensitivity','민감도'),('symbols','종목쏠림')]:
            lines.append(f"| {label} | {'불안정' if r['flags'][k] else '안정'} |")

    def sensitivity_table(label, series):
        lines.extend(['', f'**{label}**', '', '| 값(챔피언 비중 또는 파라미터) | CAGR | MDD | Sharpe | 매매건수 |', '|---|---|---|---|---|'])
        for p in series['points']:
            lines.append(row(f"{p['value']:.6g}",p['metrics']))
        maxima = {k:max(j['delta'][k] for j in series['jumps']) for k in ['cagr','mdd','sharpe']}
        lines.append(f"\n- 인접점 최대변화: CAGR {maxima['cagr']:.2f}%p / MDD {maxima['mdd']:.2f}%p / Sharpe {maxima['sharpe']:.3f}. 판정: {'불안정' if any(j['unstable'] for j in series['jumps']) else '안정'}. 검사한 수열에 한정한 판정이며 미측정 점의 연속성을 증명하지 않는다.")

    audit_tables('챔피언', champion)
    for key, label in [('volume_multiple','VOLUME_MULTIPLE(PRICE_CAP=5% 고정)'),('price_cap','PRICE_CAP %(VOLUME_MULTIPLE=3 고정)')]:
        sensitivity_table(label, champion['sensitivity'][key])
    lines.append('\n- 기준점 3.0/5%를 한 번만 실행한 9개 변형이다. 두 정렬 수열 중 하나라도 임계값을 넘으면 민감도 항목 실패로 센다. BTC 재개 플래핑은 CB가 없어 해당 없음.')
    lines.extend(['', '### 17-2. 분리자본 앙상블(N=2, N=3) 결과', '',
                  '- **초기자본만 균등 분할·버킷 간 이체와 재균형 없음.** 각 버킷은 자기 TOP_K=8·자기 신호로 공통 엔진을 독립 실행하며 시작 NAV=1인 일별곡선을 초기비중으로 합산한다. N=2는 cap5%+하이킨 아시, N=3은 cap5%+하이킨 아시+FRVP. 하이킨 아시와 FRVP는 Round 1 단독 baseline 설정·CB 없음이다. 매매건수는 합계이고 같은 종목·날짜라도 다른 버킷 거래는 각각 센다. 시간이 지나면 실제 자본비중은 성과에 따라 변한다.', '',
                  '| 구성 | CAGR | MDD | Sharpe | 매매건수 |','|---|---|---|---|---|', row('챔피언 단독',champion['full'])])
    for r in d['ensembles']:
        lines.append(row(f"N={r['n']}",r['full']))
    lines.extend(['', f"| 일별수익률 상관(공통 {d['correlation_days']}일·피어슨) | 계수 |", '|---|---|'])
    for a,b in [('volume_spike_cap5','heikin_ashi'),('volume_spike_cap5','frvp'),('heikin_ashi','frvp')]:
        lines.append(f"| {a} / {b} | {d['correlation'][a][b]:.6f} |")
    lines.append('\n- 양의 상관과 공통시장 노출이 남는다. 상관계수만으로 분산 성공을 선언하지 않고 실제 합산 MDD·Sharpe를 함께 평가한다. 비중 검사는 결과를 선택하는 튜닝이 아니다. N=2 챔피언 비중 30/40/50/60/70%, N=3 20/30/33⅓/40/50%를 미리 고정했고 N=3의 나머지는 하이킨 아시:FRVP=1:1이다. N=3 검사는 이 한 축에 한정하며 전체 3차원 비중 공간을 검증한 것은 아니다.')
    for r in d['ensembles']:
        delta = {k:r['full'][k]-champion['full'][k] for k in ['cagr','mdd','sharpe']}
        lines.append(f"\n- N={r['n']} 단독 대비: CAGR {delta['cagr']:+.2f}%p / MDD {delta['mdd']:+.2f}%p / Sharpe {delta['sharpe']:+.3f}. 세 축 우월 여부 {r['better_axes']}; **{r['verdict']}**. 승격후보에는 세 축 모두 엄격 우월·4개 검증 전부 통과를 요구한다.")
        audit_tables(f"N={r['n']} 앙상블", r)
        sensitivity_table(f"N={r['n']} 초기 비중 민감도",r['sensitivity'])
    cb = d['btc_confirmation']; f = cb['flapping']; old = cb['original_flapping']
    lines.extend(['', '### 17-3. BTC재개 플래핑 완화(3일 확인) 참고 결과', '',
                  '- 최근 3개 완료 BTC 일봉이 연속 Close>SMA50일 때만 다음날 시가에 재개한다. 코인 거래일은 주말 포함이다. CB25%·기존 피크·재개일 1일 유예를 유지했고 공통 엔진은 수정하지 않았다. 확인 시리즈는 과거 방향 rolling이며 엔진은 전일 값만 조회한다.', '',
                  '| 하이킨 아시/CB25% 재개 | CAGR | MDD | Sharpe | 매매건수 |', '|---|---|---|---|---|', row('3일 확인',cb['full']), '',
                  '| 재중단 시점 | 즉시 재개 | 3일 확인 재개 |','|---|---|---|'])
    for n in ['1','3','5']:
        lines.append(f"| {n}일 내 | {old['within'][n]['count']}/{old['resumes']} ({old['within'][n]['pct']:.2f}%) | {f['within'][n]['count']}/{f['resumes']} ({f['within'][n]['pct']:.2f}%) |")
    lines.append(f"\n- 중단/재개 {f['pauses']}/{f['resumes']}, 5일 관찰 중도절단 {f['censored_5d']}건. 5일 플래핑 변화 {f['within']['5']['pct']-old['within']['5']['pct']:+.2f}%p. 분모는 §16처럼 전체 재개수이며 최초 후속 중단까지 인덱스 차이를 센다. **채택 재검토용 참고 수치이며 새로운 승자가 아니다.** 추세 확인만으로 기존 피크에 의한 반복 재중단 구조가 제거되지 않는다.")
    lines.extend(['', '### 17-4. Round 5 종합 판정', '',
                  '- **현재까지의 비교기준 자체가 과최적화 위험을 안고 있다.** 챔피언 3/4 불안정으로 기각 수준이며, Round 1~5에서 이번 기준의 강건성 검증까지 버틴 기준선은 없다. §15의 비교기준이라는 지위는 역사 성과 비교용이지 검증된 실거래 기준선이라는 뜻이 아니다.',
                  '- **N=2·N=3 앙상블 승격 기각.** 챔피언 대비 세 축 동시 개선과 모든 강건성 검증 통과를 충족하지 못했다. 최초 균등분할 후보가 실패했다고 비중 민감도 점에서 새 승자를 고르지 않는다.',
                  '- **검증:** 일별 원장 합산·수수료·최종손익 대조, 날짜 정렬·동일 캘린더·초기자본 정규화, 독립 구간별 초기화, 제거곡선 및 보조곡선 독립 산술, 실제 신호/버킷/합산 prefix·미래변형, BTC 3일 확인 prefix·재개 이벤트 감사와 Round 1~4 회귀검증 통과. 신규 모듈 `python3 -m py_compile` 통과. 로그: `docs/round5-verification-2026-10-07.txt`, `docs/round5-round1-regression-2026-10-07.txt`, `docs/round5-round2-regression-2026-10-07.txt`, `docs/round5-round3-regression-2026-10-07.txt`, `docs/round5-round4-regression-2026-10-07.txt`.',
                  '- 캐시 기반 역사 연구이며 펀딩비·슬리피지·시장충격·상장폐지 생존편향은 미반영이다. README·실거래 설정 변경 없음.', '',
                  '### 다음 (TODO, Round 6)', '',
                  '- **최우선: §12-1 이벤트스터디로 돌아가 엣지 재검증.** 손익 절대금액·시장상승 효과를 분리하고, 같은 종목·같은 시장 국면의 무작위 진입 대조, 블록 단위 재표본화, 종목/연도 제외 검사를 사전 고정한다. 50조합 이상을 이미 탐색한 선택 편향을 보고하고 새 최적값 탐색을 중단한다.',
                  '- 역사적 재설계안: 2019-09-08~2021-12-31만 훈련·규칙 확정에 쓰고 이후 2022-01-01~2026-10-05를 동결 검증한다. 다만 후반 기간도 이미 관측했으므로 이를 진정한 미관측 OOS로 주장하지 않는다. 완전 미관측 검증은 규칙·비용·유니버스를 지금 동결한 이후 신규 봉의 전향적 모의운용으로 확보한다.',
                  '- 다음 연구 전 펀딩비·슬리피지·상장폐지 포함 유니버스·허용 MDD와 판정기준을 고정한다. BTC 재개는 위험 에피소드/피크 정의를 별도 설계한 뒤 검증하고 이번 3일 확인 성과로 재채택하지 않는다. FRVP 실제 volume-at-price, 지표 fallback 대조, 국장/미장 포트폴리오·KIS 캐싱은 미완료 과제로 유지한다.', '', '---', ''])
    path = ROOT / 'docs/전략-백테스트-종합.md'
    doc = path.read_text()
    if '## 17.' in doc:
        a = doc.index('## 17.'); b = doc.index('## 결론',a)
        doc = doc[:a]+doc[b:]
    doc = doc.replace('### 다음 (TODO, Round 5)', '### 다음 (TODO, §16 당시 — 최신 판정·우선순위는 §17 참고)')
    doc = doc.replace('## 결론', '\n'.join(lines)+'\n## 결론', 1)
    path.write_text(doc)


if __name__ == '__main__':
    render()
