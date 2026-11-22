# 사전등록 — 동일구간 현물/퍼페추얼 OB 재탈환 개발 반증 실험

상태: `IMPLEMENTATION_TESTED — 4인 패널 승인·입력 fingerprint·합성 테스트 완료; commit SHA 고정 전에는 실행 금지`
기록일: 2026-11-22  
시장: Binance USDⓈ-M perpetual / historical backtest only  
가설 ID: `CRYPTO-OB-SPOTPERP-SAMEBAR-001`  
기존 가설군: order-block / first-mitigation / retest-confluence. 독립 전략군으로 세지 않는다.

## 사전 가설

동일 UTC 5분 구간에서 현물 종가가 오더블록 밖으로 회복한 반면 무기한 종가가 그 오더블록 내부에 남는 첫 접촉은, 무기한 오더블록 방향만 사용하는 동일 접촉 이벤트보다 2R 목표가 손절보다 먼저 도달하는 비율을 높일 수 있다. 이는 같은 구간의 종가 상대 위치를 시험할 뿐 현물이 먼저 움직였다는 선행성 가설이 아니다.

현재 예상 성과값은 없다. 결과가 목표에 못 미치면 정의를 수정하지 않고 이 버전을 기각한다. 수정은 별도 가설·새 trial이다.

## 이전 연구·trial 가족

- 연구 레지스트리 #7 / P6: `order_block`, `fabio_liquidity_mss`; 기존 Stage C에서 두 전략 모두 사용자 승률 기준에 미달.
- 레지스트리 #20 / P9-E: `order_block_confluence_{aggressive,balanced,conservative}`; 보수적 필터가 표본만 줄이고 기대 hit-rate 개선은 확인하지 못함.
- 레지스트리 #21 / P9-F: 20종목 OB 확장; 기존 1분봉 hit-rate 및 비용 후 수익 기준에 미달.
- `PREREG_USDM_1H_SETUP_M2_20261120.md`의 38 setup × 2 horizon 시험에도 OB와 관련 변형이 포함됐다.
- 이 실험은 신규 독립군이 아니라 같은 OB 연구가족의 조건부 변형이다. 이전 계열 탐색을 다 포함한 정확한 전체 trial 수는 아직 감사되지 않았다. 따라서 이 개발 반증 실험은 설명적이며 어떤 p-value도 새 전략의 확증 근거로 취급하지 않는다.

## 데이터·고정 코호트

- 입력: 로컬 `/Users/user/CODE/trading_data/external/crypto/binance/{spot_klines_1m,um_klines_1m}`; 읽기 전용. `chart_predictor/data`의 실시간 수집 DB는 읽지 않는다.
- 고정 심볼: `AAVEUSDT, ADAUSDT, APTUSDT, ARBUSDT, ATOMUSDT, AVAXUSDT, BCHUSDT, BNBUSDT, BTCUSDT, CRVUSDT, DOGEUSDT, DOTUSDT, ENAUSDT, ETCUSDT, ETHUSDT, FILUSDT, HBARUSDT, INJUSDT, LINKUSDT, LTCUSDT, NEARUSDT, OPUSDT, POLUSDT, RUNEUSDT, SEIUSDT, SOLUSDT, SUIUSDT, TIAUSDT, TRXUSDT, UNIUSDT, WLDUSDT, XRPUSDT`.
- 범위: 2024-10-01 00:00 UTC부터 2026-11-01 00:00 UTC 직전까지. 2026-11 파일은 후보 동결 이전 생성됐고 현재 월도 미완성이므로 제외한다. 신호 확정 후 100분 평가창 전체가 cutoff 이전에 끝나는 신호 시각까지만 eligible로 두며, cutoff와 평가창의 접점은 미포함한다. cutoff 직전에서 평가창을 끝낼 수 없는 anchor 수는 사전 제외 수로 집계하고 coverage 분모에서 제외한다. 행정적 tail censoring은 데이터 결함 실패로 세지 않지만 eligible anchor의 이후 경로 안에서 거래분 누락·정렬 실패가 있으면 별도 data-defect 및 M2 실패로 남긴다.
- 역할: 이 범위 전체는 이미 노출된 개발 자료다. 검증(validation), sealed OOS, forward 구간으로 부르거나 그 역할로 재사용하지 않는다.
- 2026-11-22 로컬 읽기 전용 감사에서 32개 고정 심볼 × 25개월의 spot/perp 1분 시각 배열은 일치했고, 해당 코호트의 OHLC 값 규칙 위반은 0이었다. 전체 아카이브는 mark-price 간극·미선택 심볼 및 funding 문제로 `FAIL`이다. 그 전역 실패를 감춰 전체 데이터를 깨끗하다고 표현하지 않는다.
- 선택한 spot/perpetual 원본 1,600개 파일(32종목 × 25개월)의 실제 SHA-256과 크기·수정시각 안정성 검사를 마쳤다. 총 2,965,576,645 bytes, 모든 파일 해시 중 변경 0건. 파일별 기록과 aggregate fingerprint는 [`crypto_ob_reclaim_input_fingerprint_20261122.json`](crypto_ob_reclaim_input_fingerprint_20261122.json)에 있다. aggregate SHA-256=`de5c87e883f4c3e00b818c541a0e36d1320f08a2577dc063d2bb9ff519ab9036`. 변경·누락·원본 감사와의 메타데이터 불일치가 발생하면 점수화를 중단한다.

## 규칙 — 결과 열람 전에 동결

### 봉 및 오더블록

1. Spot과 USD-M 1분봉만 UTC 5분 경계로 리샘플한다. 한 5분봉은 해당 UTC 구간의 5개 분봉이 모두 존재하고 시간 배열이 동일할 때만 사용한다. 고가/저가/시가/종가/거래량은 각각 표준 OHLCV 집계 규칙을 쓴다. **OB 생성, ATR, zone 무효화, 접촉, zone 기반 stop은 USDⓈ-M perpetual OHLCV만 사용한다.** Spot OHLCV는 후보의 동일구간 close 필터에만 사용한다.
2. 오더블록 생성은 USDⓈ-M perpetual 5분 OHLC에 대해 `chart_predictor/setups.py`의 `order_block` 정의를 그대로 독립 재현한다. 완료 5분봉 `i`에서 `ATR14[i-1]`가 유효하고, bullish는 `close[i]-open[i] > 1.5×ATR14[i-1]` 및 `close[i] > high[i-1]`; bearish는 대칭 조건이다. 직전 1~5개 봉 중 가장 최근 반대색 봉의 `[low, high]`를 zone으로 사용한다.
3. Long zone은 생성봉 다음부터 완료된 5분봉 60개(감시 인덱스 1..60)를 감시한다. 각 봉에서 `close < zone_low` 무효화를 먼저 판정한다. 무효화되지 않은 zone은 그 봉의 high/low로 접촉 여부를 판정하며, close 무효화와 touch가 모두 있는 봉에서는 무효화가 우선한다. 60번째 감시봉의 무효화·touch 판정을 마친 뒤에도 미접촉이면 해당 봉 종료 시 만료한다. 따라서 무효화되지 않은 60번째 봉의 touch는 유효하다. Short는 대칭이다.
4. 접촉은 `low <= zone_high AND high >= zone_low`. 이 가설은 네이티브 `setups.py`의 반전 종가 재탈환 규칙을 그대로 재사용하지 않는다. zone 생성만 기존 정의에서 가져오고, 각 zone의 **최초 접촉에서 한 번만** 후보/대조 이벤트를 만들며, spot/perp 조건 통과 여부와 무관하게 해당 zone을 소비한다. 이는 새 first-touch 규칙으로 명시해 네이티브 OB retest 성과와 섞지 않는다. 한 봉에 같은 방향 zone이 여러 개 접촉되면 가장 최근 생성 zone만 그 방향 이벤트의 stop/target 기준으로 선택하며, 해당 봉에서 접촉된 그 방향 zone은 전부 소비한다. 상·하방 zone이 동시에 접촉되면 모호 이벤트로 따로 집계하고 후보 신호를 내지 않는다.

### 후보 신호와 비교군

- **후보:** 첫 접촉 5분봉이 닫혔을 때 long zone에서 `spot_close > zone_high` 및 `zone_low <= perp_close <= zone_high`면 long 신호를 발행한다. Short zone은 `spot_close < zone_low` 및 `zone_low <= perp_close <= zone_high`면 short 신호다. 모든 비교는 동일 UTC 5분 구간의 완료 종가다.
- **유일한 1차 비교군:** 고정 코호트의 모든 최초 접촉 이벤트에서 OB 방향으로 진입하는 무필터 first-touch 규칙. 후보와 동일한 이벤트 생성, 방향, next-open 진입, stop/target/만기 및 비용 계약을 사용하되 spot/perp 종가 필터만 적용하지 않는다. 후보 신호는 이 고정 비교군 거래 집합의 부분집합이므로 `후보 적중률 - 전체 무필터 적중률`, `후보 적중률 - 필터 미통과 이벤트 적중률`, 발행 coverage를 함께 보고한다. 동일 anchor 양쪽의 거래 결과는 같으므로 이를 독립 표본처럼 세지 않고 짝지어진 anchor 수와 차이를 따로 표시한다. 조건부 후보 hit-rate만으로 필터의 인과적 증분효과를 주장하지 않는다. 개발 결과에서 비교군을 고르거나 바꾸지 않는다. **참고 진단군:** `setups.py` 네이티브 `generate_signals` retest 및 모든 eligible anchor의 always-long/always-short는 규칙이 다른 보조 표로만 보고하며 합격 기준선 선택에 사용하지 않는다. prospective 사전등록에서는 후보와 이 단일 1차 비교군을 함께 고정해 OOS 평가한다.
- 신호는 현재 5분 봉이 닫힌 뒤 확정한다. 진입은 정확히 다음 UTC 5분 구간의 첫 1분봉(`minute_open_time == next_5m_bucket_open`)의 실제 perp open이다. 그 진입 분봉 자체를 100개 경로 관측의 첫 번째 분봉으로 포함한다. 완전한 다음 5분봉의 첫 분 데이터가 없거나 경계가 맞지 않으면 신호 원장에 남기고 M2 실패 및 데이터 결함으로 처리한다.
- 횡단 중첩 OB zone은 각각 최초 접촉 여부를 추적하되, 하나의 anchor에서 후보 신호는 최대 한 건만 발행한다. 상충 방향 접촉은 위 모호 이벤트 정책을 따른다. 포지션 중첩은 허용해 모든 emitted signal을 scoring하고, 상관·비중복 결과를 별도 보고한다.

### 손절·목표·경로 채점

- Stop buffer는 signal 직전 완료 5분 ATR14의 0.1배다. Long stop=`zone_low - 0.1×ATR14`; short stop=`zone_high + 0.1×ATR14`.
- 위험 `R=abs(entry-stop)`. Long target=`entry+2R`, short target=`entry-2R`. R≤0, 비정상 가격, 다음 봉이 이미 stop 바깥에서 시작한 경우도 신호 분모에 남기고 non-executable/M2 failure로 기록한다.
- 경로는 실제 다음 5분봉의 첫 1분봉 open 진입 후, 그 진입 분봉을 포함해 100개 완료 1분봉(100분)까지만 확인한다. 각 분봉은 먼저 open gap을 판정한다: open이 stop을 넘어 불리하게 갭이면 open 가격 체결, open이 target을 넘어 유리하게 갭이면 target 가격 체결로 제한한다. open이 두 barrier 사이면 high/low를 확인하고 같은 분봉에서 stop과 target이 모두 닿으면 stop-first 실패다. 시간 만료는 M2 실패이며 100번째 분봉 종가에 청산해 그 수익을 경제성 지표에 반영한다. 사전 제외 tail이 아닌 시계열 결측·정렬 위반은 성공에서 제외하지 않고 M2 실패로 세며 데이터 결함률을 따로 보고하고, 데이터 결함 신호가 한 건이라도 있으면 경제성 스크린을 중단한다.
- M1은 100분 종료 가격을 신호 기준 5분 종가와 비교한다. flat band는 `0.25 × ATR14(신호 직전 5분봉) × sqrt(20)`로 고정하고, 그 위/아래 종가를 각각 long/short 적중으로 채점한다. M1은 M2 대체 지표가 아니다.
- 비용: 역사 코인 비교 프로토콜의 왕복 10bp base와 30bp stress를 그대로 쓴다. 실제 spread/slippage가 아니며 미측정 spread/market-impact를 대변하지 않는다. Funding cash flow와 그 timestamp semantics는 아래 별도 게이트가 해결되기 전까지 계산하지 않는다. 따라서 `net expectancy after fees, before funding`만 설명 지표이며 수익성 합격 판정에는 사용할 수 없다.

## 분모·독립 표본·지표

- M2 주 분모는 모든 발행 `side=long|short` 신호다. 미체결·무효 진입·손절·시간 만료·동시 touch·결측 경로는 실패다. 비체결/무효 위험 신호는 실현 손익 0·거래비용 0으로 기록하되 M2 실패로 분모에 남긴다. 왕복 수수료는 실제 진입이 체결된 신호에만 적용하고, 유효 체결 신호는 target/stop 체결가 또는 시간 만료 종가의 gross 손익에서 고정 왕복 수수료를 뺀다. 수수료 후 평균 simple return은 모든 발행 신호 분모에 포함해 계산하고, 체결 신호만의 평균 R도 **수수료 차감 후** 별도 표시한다. `side=none` 모호 anchor는 별도 건수와 모든 eligible anchor coverage에 반영한다.
- eligible anchor는 고정 코호트의 완전하게 존재하고 spot/perp 정렬된 USDⓈ-M 및 spot 5분봉, ATR warm-up 완료, 그리고 신호 확정 후 100분 평가창 전체가 cutoff 이전에 끝나는 시각이다. OB 계산은 USDⓈ-M만 사용하고 spot은 동일구간 close 필터에만 쓴다. zone이 없는 봉도 분모에 포함한다. cutoff 직전 행정적 tail 제외 건수는 별도 공개한다. eligible 신호의 이후 경로 안에 있는 결측·불일치는 해당 신호의 M2 실패로 포함한다. 전체 발행 M2와 Wilson 95% interval, M1, M2 outcome별 수, coverage=`actionable issued / all fixed-cohort eligible 5m anchors`, 최초 접촉 대비 발행률, 종목별 신호·M2·M1·수익, 동시간 코인 anchor 군집, 수수료 후 all-issued 평균수익 및 체결-only 평균 R을 출력한다. Wilson 구간은 군집 보정하지 않은 기술 통계로 표시한다.
- 비중복 표본은 종목 내 시간순으로 정렬한다. 앞 신호의 최대 100분 평가창이 끝나기 전에 나온 다음 신호는 전체 발행 M2에 남기되 비중복 M2에는 넣지 않는다. 합격 게이트의 비중복 `N≥200`은 심볼별이 아니라 전체 코호트 합계이며, 심볼별 분포와 상위 심볼 집중도를 따로 보고한다. 시장 전체 동시간 알트 상관은 별도 5분 anchor cluster로 집계한다.
- 성공적 개발 스크린은 다음 모두가 필요하다: 후보 전체 발행 M2 ≥80%; 전체 고정 코호트 합산 비중복 신호 N≥200; coverage≥10%; base/stress 두 경우 모두 수수료 후·펀딩 전 기대값 >0; 후보 M2의 Wilson 하한이 위에 고정한 단 하나의 1차 비교군 M2 점추정치보다 높음. 모든 종목의 신호·성공 수와 종목 집중도도 보고하되 종목별 N≥200을 요구하지 않는다. 이 비교는 역사 개발자료에서의 선별 스크린일 뿐이며 가설의 인과효과나 엣지 증명이 아니다. prospective/sealed OOS 실험에 진입할 자격만 부여한다. 표본 부족은 `INSUFFICIENT_SAMPLE`, 조건 미달은 `REJECT`.
- 최종 코인 승인은 개발 스크린이 아니다. 미사용 prospective/valid sealed OOS에서 전체 발행 N≥200, 비중복 N≥200, ≥20개 종목, coverage≥10%, M2≥80%, 두 비용 후 funding 포함 기대값>0, 사전고정 기준선보다 Wilson lower-bound 우위, walk-forward/cluster/bootstrap/multiple-testing/red-team 게이트까지 모두 필요하다.

## Funding·약관·OOS 중단조건

- 해당 Binance funding 공개 보관소에서 `calc_time`, `last_funding_rate`, `funding_interval_hours`가 실제 정산·청구 시각과 값을 뜻하는지, interval이 끝나는 구간인지 다음 구간인지 현재 공식 답변이 확인되지 않았다. 공식 공개 데이터 이슈 #519도 같은 질문을 열어 두고 있다. 답이 나오기 전 funding은 비용 합격 계산에 넣었다고 주장할 수 없다.
- Binance Vision은 현재 비상업적 개인 목적의 역사 백테스트/비프로덕션 연구로 제한된다. 이번 사용은 그 범위 안의 개발 반증에만 한정한다. 이 자료나 파생 신호를 live/manual signal feed·실거래·상업적 시스템에 사용하지 않는다. 사용범위가 바뀌면 별도 권리 확인 전 중단한다.
- 이 문서의 commit SHA와 전략 코드/data fingerprint를 먼저 고정한다. 이후 개발 점수만 한 번 계산한다. 후보 규칙 또는 비용·기준선을 결과를 보고 변경하지 않는다.
- 현재 파일은 freeze 날짜 이전 생성이므로 이 연구에서 sealed/OOS로 사용할 날짜는 0일이다. 개발 스크린이 통과해도 그 결론은 prospective forward 평가를 위한 사전등록된 코드 준비로만 이어진다. 새 관측은 그 규칙·코드·기준선·데이터 cutoff를 동결한 뒤부터 모은다.

## 실행 전 필수 게이트

1. 4인 panel은 Blue/Red/Data/Methods/Judge로 역할을 나누고 이 규칙, 분모, 비교군, 기존 trial 가족, 약관, funding caveat, 실험 가치를 독립 검토한다. 허용 판정은 `APPROVE`, `REVISE`, `NO-SCORE`다. `REVISE`가 하나라도 나오면 규칙을 수정해 네 명 모두에게 다시 동결 전 리뷰한다. `NO-SCORE`가 하나라도 있으면 이번 historical performance screen은 하지 않는다.
2. [`crypto_ob_reclaim_input_fingerprint_20261122.json`](crypto_ob_reclaim_input_fingerprint_20261122.json)의 파일별 SHA-256, 크기, 수정시각 안정성 기록과 선택 코호트를 대조한다. 기존 시각/OHLC 감사의 32×25 cohort 밖으로 심볼·기간을 늘리지 않는다.
3. 실험 ID와 이 문서 SHA를 저장하고 테스트/실행 코드의 SHA를 고정한다. 테스트 코드가 synthetic fixture에서 first-touch 소비, 미래정보 차단, next-open, all-issued denominator, overlap, stop-first 및 gap 경계를 확인해야 한다.
4. 위 조건을 통과한 뒤 historical dev falsification 한 번만 실행한다. 실패 후 같은 기간에서 아이디어를 고쳐 재평가하지 않는다.

### 패널 기록 — 2026-11-22

| 역할 | 검토자 | 판정 | 적용 범위 |
|---|---|---|---|
| Blue / 가설·규칙 가치 | Hubble | `APPROVE` | 개발용 사전등록 문서 |
| Data / Methods | Harvey | `APPROVE` | cohort·분모·기준선 명료성 |
| Execution / Causality | Singer | `APPROVE` | 가격원천·시점·경로 체결 규칙 |
| Red / Judge | Raman | `APPROVE` | baseline·선택편향·레드팀 검토 |

1차·2차 리뷰에서 나온 모호성 수정 후 네 명이 같은 3차 수정본을 승인했다. 이어 경로 결측·만기 회계·미체결 비용 처리를 보강했고 네 명 모두 최종 accounting wording도 승인했다. 패널 승인은 역사 개발자료의 단 한 차례 반증 실험을 위한 문서 승인일 뿐이며, 커밋된 코드/문서 지문 및 약관 확인을 대체하지 않는다. 현재 구현의 전략·입력 freeze 합성 테스트 17개와 지문/아카이브 회귀 테스트 6개가 통과했다. 어떤 OOS·수익성·실거래 승인도 아니다.

## 근거 문서

- OB 생성 코드의 기준 정의: [`chart_predictor/setups.py`](../../chart_predictor/setups.py)
- 기존 비용·분할·M2 원칙: [`PREREG_USDM_1H_SETUP_M2_20261120.md`](PREREG_USDM_1H_SETUP_M2_20261120.md), [`comparable_evaluation_protocol_v1.md`](comparable_evaluation_protocol_v1.md)
- Binance는 Vision 데이터를 개인의 비상업 역사 백테스트·비프로덕션 연구로 제한하고, 상업적 활용과 유료 신호 배포를 별도로 금지한다: [Binance Vision Dataset Terms](https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md).
- Binance 공개 데이터 issue [#519](https://github.com/binance/binance-public-data/issues/519)는 `calc_time`이 `fundingTime`과 일치하는지 및 interval 의미를 공식 확인해 달라는 질문이 열린 상태다. 따라서 이 연구는 funding을 합격 경제성 산정에 넣지 않으며, 그 점을 미확인 비용으로 남긴다.
