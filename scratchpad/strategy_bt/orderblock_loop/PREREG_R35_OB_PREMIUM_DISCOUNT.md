# R35 — 오더블록의 사전 형성 범위 내 위치 필터 (단일 TRAIN)

## 가설과 기존 결과와의 차이

수요 오더블록은 형성 직전 거래 범위의 중간값 아래(discount), 공급 오더블록은 중간값 위(premium)에 있을 때만 첫 재방문을 허용한다. 가격 추세, BOS 후속 확인, FVG, sweep, 거래량·taker 흐름, funding 신호를 덧붙이지 않는다. R14의 `bos_origin` 및 첫 재방문 진입에 종속된 단일 하위집단 시험이며 독립 전략 증거나 R14의 OOS 검증으로 세지 않는다.

기존 탐색에서 압축·squeeze 돌파, 거래량 변위, BOS FVG·종가 위치, 추세 정렬, pre-BOS sweep, taker 흐름, funding 부호, breaker 재시험은 이미 다뤘다. 현재 확인한 사전등록·보고서·archive 검색에서는 **오더블록을 BOS 직전 고정 거래범위의 절반과 대조하는 premium/discount 위치 필터**를 발견하지 못했다. 이 범위는 확인한 저장소 검색 안에서의 중복 판단이며 모든 외부 전략과 완전히 다르다는 주장은 아니다.

## 실행 규칙

- **기본 설정:** R14의 고정 4h `bos_origin` zone → 1h 첫 접촉·중앙값 방향 회복 → 다음 1h 시가 진입을 유지한다.
- **위치 기준:** 4h BOS 신호봉 index `i` 직전의 완료·연속된 20개 4h봉 `[i-20, i)`에서 `range_mid = (max(high) + min(low))/2`를 계산한다. BOS 신호봉은 계산에서 제외한다. zone 위치는 `(zone.low+zone.high)/2`다.
- **진입 허용:** 롱은 `zone_mid < range_mid`, 숏은 `zone_mid > range_mid`일 때만 zone을 유지한다. 같으면 거부한다. 유효한 직전 20봉이 없거나 timestamp gap·불완전·비정상 OHLC가 있으면 거부한다. 범위·zone 값은 BOS 종가에 고정하고 재방문 때 재계산하지 않는다.
- **기본 체결·청산:** distal ±`0.10×4h BOS ATR14` stop, target `0.50R`, 최대 24개의 1h봉, 같은 봉 stop/target 충돌은 stop 우선, 왕복 12bp, 보유 중 `adverse_only` funding. R14 시뮬레이터를 그대로 호출한다.
- **자료:** 고정 `CRYPTO_35.csv`, cutoff `2023-11-06T16:00:00Z`까지의 기존 Binance USD-M TRAIN 4h/1h 자료만 사용한다. OOS/TEST, 2026-06-01 이후 행, 새 다운로드, 실제 주문은 금지한다.
- **단일 시도:** 실행 전 ledger 데이터행 4,191, 이번 포함 Bonferroni 분모 4,192를 다시 확인한다. R35 중복 행·writer·lock 부재, 상세/master prereg와 코드 hash, cutoff-safe split manifest, 40 GiB 이상 여유 공간을 확인한다. 행수 또는 hash가 다르면 가격행에 접근하지 않는다.

## 고정 판정선

- TRAIN 선별선은 scoreable 신호 `N≥200`, 전체 신호 M2 `≥75%`, 비용 후 EV `≥+15bp`, PF `≥1.30` 모두다. 하나라도 미달이면 반려하고 파라미터를 바꾸지 않는다.
- 최종 G는 봉인 OOS M2 `≥80%`, 비중복 OOS `N≥200`, 비용 후 EV `≥+15bp`, PF `≥1.30`, 연환산 Sharpe `≥1.0`, MDD `< 양의 OOS 순수익 절반`, Bonferroni·Reality Check/SPA·Deflated Sharpe, 무작위 귀무, 1봉 지연·2배 비용, plateau, 약세장·미사용 심볼군·PIT·권리 검증을 모두 유지한다. R35 TRAIN 1회는 G 통과로 판정할 수 없다.

## 예상 실패와 검증 요구

주요 실패 가능성은 range-mid가 BOS의 직전 구조와 겹쳐 zone 위치 정보를 새로 제공하지 않는 것, 필터가 표본을 줄이지만 M2·EV·PF를 개선하지 못하는 것, 현재 심볼 생존편향 및 USD-M 역사·PIT·취득권 게이트가 닫힌 것이다. 실행 전 합성 테스트로 20봉 정확 경계, BOS봉 제외, strict/equality 경계, 롱숏 대칭, 불완전·gap 처리, 미래봉 변조 불변성, 실제 R14 mapper/simulator·비용/funding 경로, append 단일행·실패 fail-closed를 확인한다. R35 결과를 본 뒤 위치 기준이나 holding/target/stop을 재시험하지 않는다.
