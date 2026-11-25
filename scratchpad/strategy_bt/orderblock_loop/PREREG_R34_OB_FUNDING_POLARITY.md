# R34 — 첫 오더블록 재시험 직전 역방향 funding 상태 (단일 TRAIN 진단)

## 목적과 의존성

**사전 고정 가설:** R14의 4시간 `bos_origin` 오더블록 첫 재방문·중앙값 회복이 이미 확인된 경우, 확인봉 종가 직전에 확정된 가장 최근 펀딩이 오더블록 방향과 반대이면 반대편 포지션 쏠림이 청산 연료가 되어 목표 선도달률과 비용 후 기대값이 개선될 수 있다.

이것은 새 독립 전략이 아니다. R14의 동일 신호·진입·청산에 단일 funding 필터만 추가하는 후속 하위집단 시험이다. R13의 funding 과열 숏, R29/R30의 체결흐름, R31/R32 브레이커, R33 지연 sweep과도 독립 증거로 계산하지 않는다. 이전에 본 TRAIN 신호를 다시 선택하므로 trial denominator에 포함하며 결과가 좋아도 별도 독립 확인 전에는 후보로 승격하지 않는다. funding 부호만으로 레버리지·청산 압력을 직접 관측했다고 주장하지 않는다.

## 고정 입력 및 시점

- 고정 `universe/CRYPTO_35.csv`, Binance USD-M 4h/1h 완료봉 및 기존 funding-event 입력만 사용한다. R14와 동일한 공통 60/40 TRAIN 경계, 1시간봉 신호/다음 1시간봉 시가 체결, UTC cutoff `2023-11-06T16:00:00Z`를 적용한다.
- TEST/OOS, 2026-06-01 이후 데이터, 새 다운로드, 라이브 주문은 사용하지 않는다. USD-M의 2018/PIT/취득권 gate가 닫힌 사실은 그대로 유지한다.
- 1h 확인봉의 `close_ts = open_time + 1h`에서 최소 1시간 전까지의 funding timestamp만 후보로 한다 (`timestamp <= close_ts - 1h`). funding event는 settlement timestamp 기준으로 정렬한다. 1h buffer는 발표 지연을 증명하지 않으며, 최신 후보 age는 `1..12h` inclusive다.
- 원본 스키마에는 별도 공개/확정 시각 필드가 없고 `calc_time`을 settlement timestamp로 쓴다. 1h buffer는 지연 위험을 낮추는 보수적 가정이며 publication latency는 확인되지 않은 한계다. source schema·catalog·기존 timestamp preregistration을 가격 행 로딩 전에 확인하고, 불일치하면 중단한다.
- 먼저 close 이전 이벤트 중 **최신 이벤트 하나**를 선택한 뒤 유효성을 판정한다. 그 이벤트가 무효라고 과거 이벤트로 후퇴하지 않는다. event가 없으면 해당 R14 유효 setup은 거부한다.
- 신선도는 `1h <= close_ts - event.timestamp <= 12h`를 모두 만족해야 한다. `coverage_gap=True`, 중립 rate `0`, NaN/무한대, `abs(rate) >= 1`, mark 가격 없음·비유한·0 이하인 이벤트는 거부한다. 실제 mark만 사용하며 `used_candle_close_fallback=True`도 거부한다.
- 롱 setup은 최신 유효 rate `< 0`일 때만, 숏 setup은 rate `> 0`일 때만 필터를 통과한다. 반대 부호와 0은 모두 진입 거부다. 방향과 부호 규칙은 바꾸지 않는다.

## 거래 규칙과 평가

- zone 탐지, R14 첫 접촉·중앙값 방향 회복, 다음 1h 시가, distal 경계 ±`0.10×4h BOS ATR14` 손절, `0.50R` 목표, 최대 24개 1h봉, 같은 봉 stop 우선, 왕복 12bp 비용, `adverse_only` 보유기간 funding은 R14와 동일하다.
- selector에 이용하는 최신 funding event는 setup 적격성만 결정한다. 거래 simulator에는 R14가 사용하던 **전체** funding map을 그대로 넘겨 보유 중 settlement·coverage gap 계산을 유지한다.
- 보고할 funnel: R14 유효 setup 수, funding 통과 수, 거부 사유별 수(없음/오래됨/gap/비정상 rate/중립 rate/표시가 결측 또는 fallback/방향 불일치), 발행 신호·scoreable 거래·비중복 거래 수. 결과는 R14의 기존 전체 결과를 참조 대조군으로만 인용하고 R14를 재실행하지 않는다.
- 고정 TRAIN 선별선: scoreable 거래 `N>=200`, 전체 발행 신호 M2 `>=75%`, 비용 후 EV `>=+15bp`, PF `>=1.30`를 모두 만족해야만 다음 봉인 검증 단계의 검토 대상이다. 미달은 반려/판정 불가이며, 기준을 낮추거나 부호·신선도 격자를 시험하지 않는다.
- 사용자 최종 G는 변함없다: 봉인 OOS M2 `>=80%`, 비중복 OOS `N>=200`, 비용 후 EV `>=+15bp`, PF `>=1.30`, 연환산 Sharpe `>=1.0`, MDD `< positive OOS net gain의 절반`, 다중검정 보정과 모든 강건성·레짐·PIT·권리 gate를 모두 통과해야 한다. 이 R34 단일 TRAIN 결과는 G 통과가 될 수 없다.

## 실패·검증 규칙

- 실행 전 합성 테스트로 cutoff 이전/동일/이후 timestamp, `close_ts-1h` 경계와 그보다 1ms 최근인 이벤트 배제, 12h 경계와 +1ms, 최신 gap 뒤 과거 유효 이벤트로의 후퇴 금지, gap 뒤 새 정상 이벤트, 방향별 부호·중립·비정상 rate, 실제 mark 출처, 유효 setup만 필터링, 미래 이벤트 변조 불변성, 전체 funding map의 simulator 전달, R14 baseline 호출 복원, 다음 시가·손절/목표/비용/adverse funding 보존, funding schema·문서 사전검사를 확인한다.
- 시점 검색은 `timestamp <= close_ts - 1h`를 먼저 적용한 뒤 가장 최신 이벤트 하나를 고른다. close 이후에 생성된 trailing-gap sentinel은 과거 신호를 오염시키지 않는다. 선택된 최신 이벤트가 부적격이면 이전 이벤트로 후퇴하지 않는다. upstream이 여러 차례 연속 누락을 gap marker 하나로 나타낼 수 있으므로 12h age 제한은 별도 경계이지 upstream gap 검출 완전성의 증거가 아니다.
- selector에는 symbol 전체 TRAIN funding map을 사용하고, simulator에는 기존 R14 segment funding map을 그대로 전달한다. segment 첫 봉 이전의 최신 12h event 누락을 막기 위해 segment와 symbol map의 연결을 테스트한다. 필터에서 거부된 첫 접촉 zone은 R14와 같이 소진한다.
- 가격 데이터 접근 전 현재 ledger 행수, R34 중복 행 부재, 두 연구 lock/writer 부재, 상세/master prereg·소스 hash, cutoff-safe input fingerprint 경로, 최소 40 GiB 여유 공간을 확인한다. 실행 시점의 전체 행수+1을 Bonferroni denominator로 사용한다. 실행 직전 행수가 사전등록 기대값과 달라지면 가격 행에 접근하지 않고 중단한다. 분모를 갱신해야 하면 데이터 접근 전에 새 사전등록 버전을 고정하고 다시 검토한다.
- 연구 writer 외 다른 프로세스가 있거나 lock이 이미 존재하면 시작하지 않는다. 각 설정은 단 한 번만 시도한다. 계산 뒤 append가 불확실하면 재시도하지 않고 파일 상태를 먼저 대사한다.
- 합성 테스트나 TRAIN 성과는 데이터 사용권·2018 coverage·OOS·실거래 성과를 입증하지 않는다. 실행하지 않은 검증은 `확인 안 됨`으로 보고한다.

## 실행 전 검토 결론

이 가설은 실패한 R14 진입을 이용한 선택 편향 위험이 크지만, 반대편 funding crowding을 단일 시점에서 분리한다는 점에서 제한적인 메커니즘 진단 가치는 있다. 성공을 가정하지 않으며 사전 선별선 미달이면 해당 규칙의 재튜닝을 하지 않는다.

## 실행 후 결과 — 고정 시도 1회

- 2026-11-25 단일 TRAIN 실행 완료. 사전 장부 4,190행, 이번 포함 분모 4,191. 완료행 1개이며 같은 설정 재실행 금지.
- 32종목, funding filter 후보 setup 8,490개, 통과 2,966개, 반대 방향 5,269개, 중립 funding 204개, 표시가 무효/종가 fallback 51개. 그 외 거부는 0개. 발행·채점 신호 2,965개, right-censored setup 1개.
- 목표 선도달 1,846/2,965 = 62.26%; Wilson 95% 하한 60.50%. 비용 후 EV −18.51bp, PF 0.842, 연환산 Sharpe −1.349, 누적손익 −17.15%, MDD 18.36%. N은 넘었지만 M2·EV·PF 기준을 모두 미달해 반려한다.
- R14 전체 TRAIN과의 단순 기술 비교는 M2 60.89%→62.26%, EV −20.88→−18.51bp, PF 0.826→0.842다. 신호 선택이 겹치고 trade-ID paired test를 저장하지 않았으므로 이 차이를 필터의 유의한 개선이라고 주장하지 않는다. 두 설정 모두 손실이다.
- 신호 시간이 funding 기록 timestamp에 실제로 관측 가능했는지, publication latency, OOS, 비용 스트레스, bootstrap/Monte Carlo, 연·월별 수익 집중도, Reality Check/SPA/Deflated Sharpe는 확인 안 됨. 결과를 보고 1h buffer·부호·12h 기준을 다시 조정하지 않는다. 상세 [`REPORT_R34_OB_FUNDING_POLARITY.md`](REPORT_R34_OB_FUNDING_POLARITY.md).
