# 5분 오더블록 접촉 후 1분 확정 피벗 BOS — 개발 스크린 사전등록

- 실험 ID: `CRYPTO-OB-PIVOT-BOS-002`
- 버전: 3
- 상태: 2차 패널 REVISE 반영 초안. 최종 명시 승인·freeze 전에는 결과 산출 금지.
- 연구군: 기존 OB / mitigation / MSS 연구군의 추가 trial. 독립 전략군이나 OOS 검증으로 세지 않는다.
- 목적: OB 첫 접촉 즉시 진입 대신, 접촉 뒤 완성된 1분 구조 피벗의 종가 돌파를 기다리는 규칙이 개발 자료에서 반증을 견디는지 단 한 번 확인한다.

## 1. 사전 판정 기준

다음은 전략별 합격이 아니라 개발 스크린에서 살아남아 별도 전향 검증을 신청할 자격이다. 입력 자료는 이미 과거 연구에서 열람되었으므로 어떤 결과도 OOS·봉인 검증·Core 승격으로 취급하지 않는다.

1. 발행된 모든 `long|short` 신호의 M2 목표 선도달률 ≥80%.
2. 발행 신호 N≥200, 종목 내 20분 비중복 N≥200, 그리고 전체 종목을 통틀어 20분 간격으로 greedy 선정한 시간 비중복 N≥200.
3. 방향성 first-touch arm 중 BOS 발행 비율 ≥10%. 양방향 모호 접촉은 별도 보고하며 이 방향성 coverage 분모에서 제외한다. 이 수치는 확인 신호가 너무 희소한 것을 막는 arm-conversion gate이며 제품/Core의 전체 eligible-anchor coverage 합격을 뜻하지 않는다. 이전 후보의 10% coverage 판정은 소급 변경하지 않는다.
4. 모든 first-touch arm을 같은 가중치로 센 arm당 fee-only 순 단순수익이 base·stress 모두 양수여야 한다. 미발행 arm과 미체결 신호는 0수익·0수수료, 실행된 trade는 gross return에서 왕복 fee proxy를 뺀다. 발행 신호만 분모로 한 평균수익도 별도 보고한다. funding 자료가 없으므로 fee-only 결과를 완전한 경제성 통과라고 부르지 않는다.
5. 같은 first-touch arm을 쌍으로 둬 후보 arm M2(발행·목표 선도달만 1, 미발행·실패는 0)와 즉시진입 기준선 arm M2의 차이를 계산한다. 후보·기준선의 같은 UTC 주를 함께 재표집하는 2주 circular moving-block bootstrap에서 M2 차이와 base·stress 순수익 차이 각각의 95% 하한이 모두 0보다 커야 한다. 이는 조건부 발행 M2와 다른 추정량이며, 가족 내 선택편향을 제거하지 못한다.
6. 경제성 계산 전 고정 코호트 전체의 pre-cutoff 퍼페추얼 1분 OHLC 불변식과 warmed 5분 완전성을 선행 검사한다. 유한 OHLC 1분봉은 가격이 양수이고 `high >= max(open, close)`, `low <= min(open, close)`, `high >= low`여야 한다. 위반 봉 또는 불완전 5분봉이 하나라도 있으면 신호·경제성 점수나 arm/trade 원장을 계산·기록하지 않고 결함 수와 입력 fingerprint만 담은 `DATA_INVALID` 요약만 남긴다. preflight 뒤 신호 경로 결함이 하나라도 발견돼도 같은 방식으로 점수와 원장을 억제한다.

M1, Wilson 구간, 주별 cluster bootstrap, 종목별 결과, 연·월별 결과, 신호 빈도, 미발행 비율, stop/target/gap/timeout 사유를 모두 보고한다. Wilson 구간은 단순 기술통계이며 독립성 보장 구간으로 부르지 않는다.

## 2. 모집단·자료

- 대상: 이전 실험의 고정 32개 USDT 코인 COIN underlying 심볼, Binance USDⓈ-M perpetual 1분 OHLCV. spot은 이전 input bundle fingerprint를 보존하기 위한 무결성 자료일 뿐 신호·적격성·손익 계산에는 사용하지 않는다.
- 기간: `2024-10-01 00:00 UTC <= t < 2026-11-01 00:00 UTC`.
- 파일 목록·선택 코호트의 기존 aggregate SHA-256: `de5c87e883f4c3e00b818c541a0e36d1320f08a2577dc063d2bb9ff519ab9036`.
- 이전 후보의 1m/5m 자료는 이미 노출된 개발자료다. 전체 archive audit는 다른 코호트 오류 때문에 FAIL이므로, 기존 선택 코호트 일치·OHLC·시간 그리드·결측 규칙을 다시 확인하기 전 scoring 금지.
- 현재 로컬 Binance 코호트에는 해당 계약의 과거 funding rate 원장이 확인되지 않았다. 따라서 funding 반영 순기대값과 완전한 거래경제성은 점수화 불가다. 이 자료 부재를 0 funding으로 대체하지 않는다. 32개 고정 코호트의 당시 상장·상폐·거래 가능성도 입증되지 않아 시장 전체 대표성은 주장하지 않는다.
- 개발 anchor는 ATR warm-up 이후 perp 5분봉과 touch 뒤 10분 확인창·20분 경로의 perp 1분 OHLCV가 완전하고 전체 경로가 cutoff 전에 끝나는 완료 5분봉 close다. 결측은 보간하지 않는다. 1분 원자료 중 하나라도 빠졌거나 OHLCV가 비유한 값을 만들어 불완전해진 5분봉은 결함으로 센다. 기준 ATR warm-up 이후 cutoff 전의 불완전 5분봉이 하나라도 있으면 기존 zone/pending 상태를 초기화해 계속하는 대신 전체 개발 스크린을 `DATA_INVALID`로 처리하고 경제성 점수를 산출하지 않는다. 월 경계 재집계 오류나 5분 timestamp 결손도 동일하게 무효다. 터치 후 확인·실행 경로의 결측 또한 전체 스크린을 무효로 한다.

## 3. OB 및 최초 접촉 정의

1. 완료된 UTC 5분 USDⓈ-M 봉 `i`에서 ATR은 Wilder ATR(14)의 직전 봉 값만 사용한다.
2. 강세 OB: `close[i]-open[i] > 1.5*ATR14[i-1]` 및 `close[i] > high[i-1]`. 약세는 `open[i]-close[i] > 1.5*ATR14[i-1]` 및 `close[i] < low[i-1]`.
3. zone은 `i-1`부터 최대 `i-5`까지에서 찾은 가장 최근 반대색 완료 봉의 `[low, high]`다. OB는 생성 봉의 종가에만 이용 가능하므로 그 봉 안의 분봉 접촉은 금지한다.
4. 생성 봉이 `i`이면 유효 감시 봉은 `i+1…i+60`으로 총 60개다. 각 감시 봉에서 종가 무효화를 먼저 평가하고, 다음에 최초 접촉을 평가한다. 60번째 봉에서도 무효화되지 않았다면 그 봉의 첫 접촉은 인정한 뒤 zone을 소모한다. 60번째 봉에 접촉이 없으면 봉 종료 시 만료하며 이후 접촉은 인정하지 않는다. 완전한 5분봉 결측이 이 감시 구간에 발생하면 전체 개발 스크린은 `DATA_INVALID`다.
5. 최초 접촉은 생성 다음 완료 5분봉부터 고가·저가가 zone과 겹친 첫 봉이다. 1분 open-time `t`는 봉 시작 시각이고 5분봉은 `t`에서 시작해 `t+5m`에 닫힌다. 그 5분봉 close 뒤에만 arm한다. 동일 방향 동시 접촉 zone은 가장 최근 생성 zone 하나를 선택하고 그 봉에서 접촉한 나머지 zone도 소비한다. 양방향 동시 접촉은 모호 arm으로 기록하며 신호를 발행하지 않는다. 서로 다른 zone의 pending arm은 한 종목에 공존할 수 있으며 각 zone은 한 번만 arm한다. 이는 별도 자본 계정·독립 거래로 가정하지 않는다.

## 4. 신호·체결·청산

1. 접촉 5분봉 close `t+5m` 뒤 시작하는 첫 1분봉 `t+5m`부터 정확히 10개 봉(`t+5`…`t+14`)을 확인창으로 쓴다. 접촉 5분봉 내부 1분 데이터는 pivot/BOS 판정에 재사용하지 않는다. 10개는 두 좌·두 우 완료 확인봉과 별도 BOS close를 허용하는 사전고정 설계 상한이지 결과 최적화값이 아니다.
2. 방향은 OB 방향과 같다. pivot 중심봉 `p`와 왼쪽 두 봉은 모두 접촉 종료 뒤 시작해야 하고, 오른쪽 두 확인봉까지 전부 10개 확인창 안에서 닫혀야 한다. 롱은 pivot high가 네 이웃 고가보다 모두 엄격히 높아야 한다. 숏은 대칭 pivot low다. 최초로 확인된 방향 pivot 하나만 잠근다. 동률이면 pivot 아님으로 처리한다.
3. pivot은 오른쪽 두 확인봉이 모두 닫힌 시각에만 알려진다. 그 뒤의 별도 완료 1분봉 종가가 pivot high를 엄격히 상향 돌파(롱)하거나 pivot low를 엄격히 하향 돌파(숏)해야 BOS다. 확인봉과 BOS 봉이 같으면 신호가 아니다. wick-only 돌파는 BOS가 아니다. 확인창 OHLCV 한 건이라도 빠지면 해당 arm은 `DATA_DEFECT`고 스크린을 무효로 한다.
4. 각 1분 close 처리 순서는 (a) 이 시각 닫힌 5분봉을 포함해 arm 이후의 5분 종가 distal 무효화를 확인하고, 무효화되면 대기 arm을 즉시 취소해 `no_signal_arm=INVALIDATED`로 기록, (b) arm이 아직 유효하면 이미 확정된 pivot의 별도봉 BOS, (c) 이 시각 확정된 최초 pivot 저장, (d) 10번째 close 뒤 미발행 만료다. 무효화는 BOS와 같은 close 시각뿐 아니라 앞선 close 시각에도 우선한다. 따라서 취소된 zone에서 뒤늦은 신호는 발행되지 않는다. 10번째 봉 close의 BOS는 발행되고, 10번째 close에 pivot만 확인되고 BOS가 없으면 이후 BOS는 만료로 발행하지 않는다.
5. 진입은 BOS 봉 다음 1분봉 시가. 진입 open이 손절을 관통하거나 `R<=0`이면 신호는 유지하되 M2 실패·미체결·0수익·0수수료로 처리한다. TP는 실제 entry 기준 2R이므로 진입 open에서 이미 목표를 갭 통과하는 경우는 정의상 없다.
6. 손절: 최초 접촉 5분봉 전체 low(롱) 또는 high(숏)와 그 봉 close 뒤 arm 시작부터 BOS 봉 close까지 완료 1분 extreme 중 최저/최고값. 최초 접촉 5분봉 전체 극값을 쓰는 것은 실제 intrabar 접촉시각을 알 수 없기 때문이다. touch 이전 1분 움직임이 stop에 포함됨을 의도한 고정 정책이다. ATR buffer는 추가하지 않고 stop은 진입 뒤 수정하지 않는다.
7. 목표: 실제 entry에서 2R. 진입 1분봉부터 20개 봉(`t+15`…`t+34`, 마지막 close `t+35`)을 추적한다. 동일 1분봉 stop·target 양쪽 touch는 stop 우선. 불리한 stop gap은 시가 체결, 유리한 target gap은 목표가 체결. 만기까지 미도달하면 20번째 봉 종가 청산이며 M2 실패다.

## 5. 분모·비교·비용

- `eligible_anchor`: ATR warm-up, perp 경로 완전성, cutoff를 만족하는 완료 5분봉 close anchor. 전체 1분 timestamp 비율을 산출할 수 있으면 별도로 표시한다.
- `first_touch_arm`: eligible 구간에서 OB 최초 접촉을 완료한 방향성 이벤트. 양방향 모호 접촉은 방향 arm-conversion 분모에서 빼되 전체 접촉·모호 수 및 `issued/(directional arms+ambiguous)`를 같이 보고한다.
- `issued_signal`: BOS를 완료하고 다음 1분 시가 기준 방향 신호를 발행한 모든 건. M2 분모는 발행 신호 전부이며 미체결·경로 결함은 실패다.
- `no_signal_arm`: pivot/BOS 미확인, 5분 무효화, confirmation timeout. 각 이유를 분리한다. M2 issued 분모에는 없지만 candidate arm-M2에서는 실패, arm 순수익에서는 0으로 포함한다.
- 동일 종목 20분 내 중첩 신호는 issued M2에는 모두 남기고 비중복 표본에서는 앞선 신호부터 하나만 선택한다. 전체 시장 시간 비중복은 signal timestamp 순으로 정렬해 이전 선택 후 20분 안의 후속 종목 신호를 제외한다. 타임스탬프 동률은 심볼 사전순, 롱 우선이다. 개발 후보는 최소 20개 심볼에서 각 1건 이상 발행하고 단일 심볼 발행 비중 ≤20%여야 한다.
- 기준선은 같은 OB/first-touch 모집단에서 즉시 첫 1분 시가 진입, zone distal 바깥 0.1×ATR(직전 완료 5분봉), 2R, 20분 만기다. 후보와 기준선은 손절·진입이 다르므로 성과 차이를 BOS 인과효과라고 단정하지 않는다.
- 수수료 proxy: 왕복 10bp base / 30bp stress. 이는 고정 대용치이고 실측 호가·체결 슬리피지는 아니다. funding·시장충격 미포함으로 funding 경계를 넘는 거래의 진정한 net expectancy는 판정 불가다. 순수익은 fee-only proxy임을 표시하며 실제 순수익이라고 부르지 않는다.
- uncertainty: first-touch anchor UTC calendar week를 cluster로 묶어 고정 seed `20261122`의 1,000회 circular moving-block bootstrap을 수행한다. 각 반복은 2주 연속 블록을 원형 추출해 전체 주 수만큼 이어 붙인다. 같은 arm의 후보·기준선을 같은 주 추출에 함께 포함한다. 통계량은 후보 arm-M2와 기준선 arm-M2의 paired 차이 `sum(candidate_arm_m2-baseline_arm_m2)/sum(arm_count)`, 그리고 paired base/stress arm 평균 순수익 차이다. CI는 반복 통계량의 2.5/97.5 percentile이다. 주보다 긴 의존성과 trial-family 다중검정은 해결하지 못한다. 종목별·전체 timestamp 비중복 N도 보고한다.

## 6. 재현성·중단 조건

- 기존 frozen input fingerprint를 재확인하고, 신규 scorer·사전등록·실행환경을 고정한다. fingerprint가 다르면 scoring 금지.
- scorer는 퍼페추얼 원장만 신호·적격성·손익 계산에 읽는다. spot 파일은 input fingerprint 재확인 과정에서만 해시하며 전략 데이터로 로드하거나 timestamp 비교에 쓰지 않는다. scorer는 최초 실행 전 별도 commit/push하고, 그 다음 manifest-only freeze commit을 별도 생성한다. freeze manifest에는 prereg, 코드 tree, input fingerprint, trial-family 이력, 실제 배정에 맞춘 네 역할(`CRYPTO_BLUE`, `CRYPTO`, `DATA_METHODS`, `RED_TEAM`)의 판정을 기록한다. KR/US 전문가로 역할명을 바꾸어 적지 않는다. 결과 디렉터리는 새 경로만 사용하며 덮어쓰지 않는다.
- 합성 테스트: pivot 중심/오른쪽 확인봉 causal timing, confirmation/BOS 동일봉 거부, window 경계, touch-bar 미래 재사용 차단, zone 만료/무효화 동시 경합, gap, stop-first, timeout, missing minute, overlap, weekly cluster bootstrap 재현성.
- 본 후보의 탐색은 고정 규칙 1개만 실행한다. 결과를 본 뒤 파라미터 변경/하위 그룹 선택/반복 재시도 금지. 필요한 수정은 오류 수정으로 명백할 때만 기록하고 새 버전 trial로 분리한다.
- M2<80%, 최소 표본/arm conversion/심볼 분산 실패, fee-only arm 기대값 비양수, paired arm M2 또는 base/stress 순수익 차이의 bootstrap 95% 하한이 0 이하인 경우 중 하나면 `REJECT_DEV`. 모든 개발 gate 통과 후에도 verified funding·미사용 전향 표본·제품/Core coverage가 없으므로 최대 상태는 `HOLD_FUNDING_AND_OOS`며 전략 또는 전향투입 승인을 의미하지 않는다.
- 최종 OOS/Core gate는 고정한다: 전체 발행 신호 `issued_signal / eligible_anchor` ≥10% (`eligible_anchor`는 §5의 ATR warm-up·perp 경로 완전성·cutoff를 만족하는 완료 5분봉 close 수), 최소 20개 COIN underlying 계약에서 각 1건 이상 발행, 단일 계약 발행 비중 ≤20%, 전체 발행 M2 점추정 ≥80%와 Wilson 95% 하한이 같은 기간 즉시진입 기준선 arm-M2 점추정 초과, 전체 OOS 발행 N≥200 및 global nonoverlap N≥200, funding을 포함한 기본·스트레스 비용 후 기대값 양수여야 한다. 신규 관측기간과 독립 계약 유니버스로 결과 열람 전 이를 1회 평가한다. 과거 2024-10~2026-10 입력은 OOS로 재사용하지 않는다. 이 coverage는 후보 시점 전체 대비 비율이라 OB 희소성 때문에 비현실적으로 높을 수 있으며, 그 문제를 이유로 분모를 바꾸지 않는다.

## 7. 기존 trial과의 관계

같은 family의 과거 trial로 P6 `order_block`/`fabio_liquidity_mss`, P9-E `order_block_confluence_*`, P9-F OB 유니버스 확장, Round 10 sweep+taker-flow, first-touch same-bar spot/perpetual candidate 001, 그리고 이미 노출된 OB/FVG/MSS 변형을 계수한다. 정확한 총 trial 수가 registry와 archived outputs를 전수 대조하기 전까지 미확정이므로, 승률 신뢰구간은 선택편향/다중검정 조정 완료로 표현하지 않는다.

이 문서는 2차 패널 수정 반영 초안이다. 네 실제 배정 역할의 명시 승인, 오류 없는 합성 테스트, 별도 scorer 및 freeze commit 전에는 실험하지 않는다.
