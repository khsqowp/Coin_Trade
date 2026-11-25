# R31 — 무효화 오더블록 역할 반전 재시험

## 사전등록 상태

- 상태: 실행 전 사전등록. 이 문서가 고정되고 구현·합성테스트·독립 레드팀 검토가 모두 통과하기 전에는 실가격 행을 열지 않는다.
- 가설: 4시간 BOS-origin 오더블록이 완료된 1시간봉 종가로 명확히 무효화되면, 그 구역은 기존 방향의 수요/공급이 아니라 반대 방향의 저항/지지(브레이커)로 바뀐다. 돌파 뒤 첫 외부 재시험이 돌파 방향으로 다시 닫히는 경우만 진입하면 단순 첫 재방문과 다른 구조적 역할 전환을 포착할 수 있다.
- 실패 근거와 차별성: R14 기본 첫 재시험은 비용 후 EV −20.88bp, R29 BOS 시점 taker 흐름은 −19.79bp, R30 첫 재시험봉 taker 흐름은 −23.94bp였다. R30은 같은 방향의 기존 zone을 유지한 가격 회복 필터였으나 R31은 zone의 명시적 종가 무효화 후 반대 방향으로만 진입한다. 과거 실패 조건을 다른 문턱으로 반복하지 않는다.

## 고정 데이터·표본

- 시장: Binance USD-M perpetual. 고정 유니버스 `universe/CRYPTO_35.csv`; 1h·4h TRAIN만 사용한다.
- cutoff: 모든 사용 봉 종가 `2023-11-06T16:00:00Z` 이하. OOS/TEST와 2026-06-01 이후 데이터는 접근하지 않는다.
- 재사용되는 R14와 동일한 데이터 접근 함수·기초 OHLC 검증·split manifest를 사용한다. 적격 종목이 30개 미만이면 `unscorable`로 기록한다.
- 2018 선물 및 PIT/상폐 생존편향·취득시점 이용권은 해결되지 않았다. 이 TRAIN 결과만으로 G 통과나 실제 사용권을 주장하지 않는다.

## 인과적 규칙 — 단일 설정, 격자 없음

1. Zone은 기존 `r4_zones(segment_4h, "bos_origin")`만 사용한다. 4h 신호봉 종료 후 다음 정각부터 1h에서 활성화한다. R14와 동일한 4h→1h timestamp mapping을 사용한다.
2. 같은 1h 연속 구간 안에서 한 번에 하나의 zone만 활성화한다. active 중 생성된 새 zone은 기존 R14 규칙대로 `superseding_zones_dropped`에 세고 폐기한다. 1h 데이터 gap은 segment 경계이며 gap을 건너 zone·포지션을 유지하지 않는다.
3. 활성 후 최대 24개의 완료된 1h 봉 안에서 distal edge를 종가로 넘어야 한다. 원래 bullish zone이면 `close < zone.low`일 때 zone을 무효화하고 숏 후보로 전환한다. 원래 bearish zone이면 `close > zone.high`일 때 무효화하고 롱 후보로 전환한다. 고가/저가 wick만 경계를 넘어간 것은 무효화가 아니다. 무효화 종가가 발생한 봉에서는 재시험을 동시에 인정하지 않는다.
4. 무효화 이후 최대 24개의 다음 완료 1h 봉에서 첫 재시험 하나만 본다. 숏 브레이커(원래 bullish zone)는 `open < zone.low AND high >= zone.low AND close < zone.low`를 모두 만족해야 한다. 롱 브레이커(원래 bearish zone)는 `open > zone.high AND low <= zone.high AND close > zone.high`를 모두 만족해야 한다. 재시험은 이전 무효화 봉 다음 봉부터 시작하며 같은 봉 돌파·재시험은 금지한다.
5. 첫 재시험이 zone 안쪽에서 닫히거나 반대쪽(distal 반대편) 경계까지 wick으로 관통하면 브레이커 실패로 zone을 폐기한다. 즉 short는 `close >= zone.low OR high >= zone.high`, long은 `close <= zone.high OR low <= zone.low`면 취소한다. 확인 조건을 만족하지 않는 단순 wick 접촉은 계속 대기하되 첫 유효 재시험보다 뒤의 재접촉은 평가하지 않는다. 24봉 이내 성공 재시험이 없으면 만료한다.
6. 확인봉 다음의 1h 시가에 진입한다. 시가가 zone 안으로 되돌아온 gap이면 `entry_gapped_into_zone`, 손절선을 이미 통과한 gap이면 `entry_gapped_past_stop`으로 각각 세고 거래하지 않는다. 원래 bullish zone에서 뒤집힌 숏의 stop은 `zone.high + 0.10×zone.atr_at_signal`; 원래 bearish zone에서 뒤집힌 롱의 stop은 `zone.low - 0.10×zone.atr_at_signal`이다. 손절까지의 거리가 0 이하이면 생략한다.
7. 목표는 진입가에서 위험거리의 0.50배를 반대 방향으로 둔다. 최대 보유 24개의 1h봉, 같은 봉 stop 우선, R14 `simulate_trade`의 왕복 12bp 비용과 `adverse_only` funding 처리로 청산한다. 거래가 완료되지 않는 오른쪽 경계 표본은 성과 표본에서 제외하고 개수를 기록한다.
8. 전체 신호 M2는 목표가 손절보다 먼저 체결되었는지로 계산한다. stop/target 동시 터치는 stop 우선이다. 별도 비중복 M2, Wilson 95% 구간, 손익비·승률, EV(bp), PF, 누적 순수익, 연환산 Sharpe, MDD, 연도·방향별 성과와 전체 zone→break→retest→entry funnel을 기록한다.

## 사전 고정 판정

- TRAIN 선별 기준(모두 필요): funding과 일별손익까지 계산 가능한 scoreable trade `N≥200`, 완료된 전체 신호 기준 목표 선도달률 M2 `≥75%`, 비용 후 기대값 `≥+15bp`, Profit Factor `≥1.30`. M2 분모에는 목표/손절/시간만료까지 관측된 모든 거래를 포함하며, 이 중 funding 미확정은 M2에서는 세되 손익 통계에서는 빼고 별도 수를 보고한다. 하나라도 미달이면 반려하고 같은 규칙을 재시도하지 않는다.
- 최종 사용자 G는 별도이며 완화하지 않는다: OOS M2 `≥80%`, 비중복 OOS N `≥200`, 비용 후 EV `≥+15bp`, PF `≥1.30`, 연환산 Sharpe `≥1.0`, MDD `< OOS 누적 순수익의 절반`, Bonferroni `0.05/N`·Reality Check/SPA·Deflated Sharpe, 무작위 진입 200회·순환이동 1,000회 귀무 95백분위, 주변 파라미터 평탄도, 2018·2022 약세장, 비용 2배·1봉 지연, 미사용 종목군 양의 성과 60% 이상, 수익 상위 한 해 비중 50% 미만, 독립 재구현 오차 1% 이내, 데이터·권리·PIT gate를 모두 요구한다.
- R31은 단일 고정 전략이라 파라미터 최적점을 찾지 않는다. 따라서 plateau 검증은 적용 가능한 경계 매개변수(무효화·재시험 24봉, stop buffer 0.10 ATR, target 0.50R)를 별도 새 시도로 preregister하지 않는 한 승인 근거로 대체하지 않는다. 현재 라운드에서 임의 이웃 탐색은 금지한다.
- 결과를 본 뒤 방향별 필터·진입 지연·목표/손절·유니버스·기간을 조정하지 않는다. 새 가설은 다음 라운드에서 별도 preregister한다.

## 검증 게이트

가격 데이터 이전에 다음 합성 테스트와 독립 적대 검토를 모두 통과한다.

- 종가 무효화와 wick 무효화 구분, 롱/숏 대칭, 무효화봉과 재시험봉 분리, 재시험 방향 종가 조건, 24봉 경계의 off-by-one.
- zone 내부 재진입·반대 edge 침범 시 폐기, 무효화 전 wick touch는 유지, first valid retest 이후 zone 재사용 금지, active 중 새 zone 폐기.
- 다음 시가 체결, 시가가 stop을 gap으로 넘으면 취소, stop과 target 같은 봉이면 손절 우선, funding/cost가 R14 simulator를 그대로 통과.
- 데이터 prefix/future mutation으로 과거 거래결정 불변, OHLC 불일치·중복/역순/누락 1h·4h봉 fail-closed, 불완전봉 제외, timeframe 경계 정렬.
- 실제 `r4_zones` → R14 4h→1h 매핑 → R31 state machine → `simulate_trade`까지 연결된 end-to-end synthetic case.
- append-once, 부분 쓰기에서 예외 후 재시도 금지, 기존 장부 보존, writer 경합·lock 충돌, 중복 R31 차단, 실행 중 hash 변경, cutoff/split/universe 검사, R31/공용 ledger lock과 기존 writer 상태 확인.

독립 레드팀은 규칙 해석, lookahead, segment/gap, 불완전 봉, stop/target 우선순위, 장부 멱등성 및 보고 지표를 검토한다. 차단 지적이 있으면 수정 후 합성시험을 다시 실행한다. 실제 TRAIN 실행은 단 한 번이며, 시도 중 실패하면 재실행하지 않고 장부·프로세스 상태부터 대사한다.

## 실행 식별 및 분모

- R30 단일 완료행 뒤 계획된 ledger data rows: 1,687. R31 포함 Bonferroni 분모: `N=1,688`.
- 실행 직전 실제 행수 1,687, 기존 R31행 0, CSV schema, writer 없음, R31/공용 lock 없음, 디스크 여유 40GB 이상, split fingerprint, fixed universe hash, 현재 code/detail prereg/master prereg hash를 확인한다. 하나라도 다르면 가격 행 접근 전 중단한다.
- R31 ledger row는 전체 trial history에 append-only로 추가한다. append 결과가 불확실하면 재시도 금지.
- 사용자 목표는 코인 2개, 국장 2개, 미장 2개지만 이 실험은 코인 오더블록 1개 후보만 다룬다. 국장·미장은 현재 적격 데이터/권리 gate가 닫혀 있어 성과를 추정하지 않는다.
