# R24 사전등록 — R21 사전 BOS sweep + BOS impulse 극값 익절

상태: 단일 TRAIN 실험 전 고정. 결과를 본 뒤 목표 산식·진입 규칙을 조정하지 않는다.

## 가설과 사전 근거

R21의 고정 0.50R 목표는 M2 63.27%였고 EV +50.55bp/PF 1.548이었다. R22에서 BOS 다음 확인봉을 기다리는 추가 진입 필터는 M2·EV·PF를 개선하지 못했다. R23은 R21 성과가 한 방향이나 한 entry year에만 몰리지 않았음을 보여줬다. R24는 진입 신호·시각을 그대로 두고, 시장 구조에 이미 형성된 BOS impulse 극값을 목표로 삼는 단 하나의 익절 가설을 시험한다. 이는 일반 오더블록의 고정 R 거리 격자 R11과 다른 목표 산식이지만, 동일 데이터/기본 전략 선택 이후의 TRAIN 탐색이므로 독립 검증으로 과장하지 않는다.

## 고정 규칙

- **데이터·유니버스:** `CRYPTO_35.csv` 35심볼, cutoff-aware 완성 Binance USDⓈ-M TRAIN 4h/1h bars, cutoff `2023-11-06T16:00:00Z`. 분석 가능 심볼 30개 미만은 `unscorable`. OOS/TEST와 2026-06-01 이후는 열지 않는다.
- **OB 신호:** 기존 `bos_origin` 정의. 방향 반대쪽의 바로 전 20개 완료 4h봉 극값을 wick으로 넘고 종가가 안쪽으로 회수하는 external sweep이 BOS보다 1–3개의 완료 4h봉 앞에 있어야 한다. R21과 같은 구역만 사용한다.
- **진입:** R14/R21처럼 BOS 4h zone activation 후 24개 완료 1h bar 안의 첫 zone overlap만 본다. 첫 접촉봉이 zone midpoint를 BOS 방향으로 회복하고 distal을 침범하지 않을 때, 다음 완료 1h bar open을 진입 기준으로 삼는다. 이때 목표가 제한 시장성 지정가로 모델링한다: 롱은 다음 시가가 목표보다 낮을 때만 그 시가에 체결하고, 시가가 목표와 같거나 높으면 목표가를 이미 지나친 주문으로 보고 미체결 취소한다. 숏은 다음 시가가 목표보다 높을 때만 체결하고, 시가가 목표와 같거나 낮으면 미체결 취소한다. 취소는 거래·목표 선도달 성공으로 세지 않고 `structure_target_not_ahead` 별도 건수로 기록한다. 이는 과거 OHLC의 체결 가정이며 실제 거래소 지정가 체결·호가 우선순위를 증명하지 않는다. 접촉 실패·무효화·zone 교체·만기 후 재시도 금지.
- **손절:** zone distal 경계 바깥 `0.10 × BOS-signal ATR14`. 기존 R14의 동일봉 stop/target 우선순위(stop 우선), exit candle·funding 정산 처리 그대로.
- **목표:** mapped R14 1h zone activation index를 `k`라 할 때, **바로 앞의 4개 1h bars `[k-4:k]`**가 BOS 신호가 확정된 4h candle을 구성한다. long target은 그 4개의 `max(high)`, short target은 그 4개의 `min(low)`. 이 자료는 zone activation·진입 confirmation 전에 모두 완료돼야 한다. 미래/진입 이후 bars는 target 계산에 사용하지 않는다.
- **무효 목표:** 4개 연속 선행 1h bars가 없거나 timestamps가 각각 1시간 간격이 아니면 `structure_target_unavailable`로 setup을 거절한다. Long target ≤ 다음 시가 또는 short target ≥ 다음 시가이면 `structure_target_not_ahead`로 미체결 취소한다. 이 취소 수는 trade/M2 funnel에서 별도로 보고한다. 경계값은 엄격하게 취소 처리한다.
- **Exit/비용/funding:** target/stop 중 먼저 닿은 값, same bar면 stop 우선, 최대 24개 1h bars 보유 후 기존 R14 규칙의 종료 체결. 왕복 12bp, funding `adverse_only`. 시가 gap/불완전·누락 바 처리는 R14 그대로.
- **보고:** 전체 M2, 비중복 M2, Wilson 95% 하한, 승률과 손익비, scoreable trades, 비용 후 EV/PF, 연환산 Sharpe, 누적 순수익/MDD, 4h BOS→sweep→zone→first touch→valid/invalid structural target→trade funnel, target 거리(entry 대비 R), gap/불완전 bars, funding 미판정 거래. R21 비교는 기존 기록된 집계 수치만 인용한다.

## 기준·분모·중단

- 코인 G는 변경하지 않는다: 최종 OOS M2≥80%, 비중복 OOS N≥200, 비용 후 EV≥15bp, PF≥1.30, 위험·강건성·다중검정·PIT/출처/이용권 모든 gate를 충족해야 한다. R24는 TRAIN이므로 G 통과로 셀 수 없다. M2만 증가하고 EV가 악화되거나 표본이 감소하면 성공 판정하지 않는다.
- 단일 고정 설정, 목표/손절/기한 격자 없음. 장부 사전 행 1,680, 이번 시도 포함 계획 Bonferroni N=1,681. 실행 직전 행 수·코드/prereg hash·data fingerprint 기준·cutoff·lock/writer를 대조한다. mismatch·test 실패이면 가격 데이터를 열지 않는다. 데이터 로드 후 예외는 `failed` 시도로 보존한다.
- 합성 테스트 필수: target 산출이 정확히 4개 선행 1h bars만 읽는지, 1시간 gap·부족 이력·잘못된 side target 취소, long/short 경계, 미래봉 mutation 불변성, R21 filter→R14 실제 zone mapper/setup/체결엔진 통합, 비용/funding 및 same-bar stop-first 불변성을 검증한다.
- 코인 2018 30심볼 선물·funding, full survivorship/PIT, delist final proceeds, data-use gate 미해결 상태를 유지한다. 이를 보완한 것으로 표현하지 않는다.
