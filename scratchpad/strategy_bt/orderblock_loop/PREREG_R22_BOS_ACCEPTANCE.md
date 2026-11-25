# R22 사전등록 — sweep 이후 BOS 경계 수용

상태: 실행 전 고정. 결과를 확인한 뒤 조건이나 기준을 바꾸지 않는다.

## 가설

R21의 사전 BOS 외부 sweep 조건만으로는 M2가 63.27%였다. sweep 뒤 생성된 BOS에서 다음 완료 4h봉이 OB 바깥 방향으로 마감하는 구조 수용을 확인하면 첫 재방문 신호의 품질이 높아질 수 있다. R22는 동일 TRAIN에서 이 조건 하나만 평가한다. R21은 0.50R 목표의 기준선으로만 인용하며 재계산하지 않는다.

## 고정 규칙

- **유니버스·자료:** `universe/CRYPTO_35.csv` 고정 35심볼, cutoff-aware 완성 4h/1h bars, 기존 공통 TRAIN cutoff `2023-11-06T16:00:00Z`. 실제 자료 심볼이 30 미만이면 `unscorable`. 데이터의 2023-11-06T16:00:00Z 이후 TEST/OOS 및 2026-06-01 이후 구간은 열지 않는다.
- **기준 구역:** 기존 `crypto.r4_zones(segment, "bos_origin")`만 사용한다. R21과 동일하게 BOS 방향 반대쪽의 직전 20완료 4h봉 극값을 wick으로 넘고 종가가 극값 안으로 복귀한 sweep가 BOS보다 1–3봉 앞에 있어야 한다.
- **새 acceptance 조건:** BOS 신호봉 `i` 다음에 있는 완료 4h봉 `i+1`의 종가가 롱이면 해당 zone.high보다 높고, 숏이면 zone.low보다 낮아야 한다. 등호는 통과가 아니다. 다음 봉이 segment 안에 없으면 확인 불가로 제외하고 카운터에 남긴다. 데이터 행의 future mutation으로 이전 구역 결과가 변하면 테스트 실패다.
- **인과적 activation:** acceptance 봉이 완전히 닫힌 뒤에만 거래를 허용한다. 통과 zone의 `signal_index`를 `i+1`로 이동하여 R14 mapper가 그 완료봉 close 시점부터 이후 1h 구간에만 zone을 활성화하도록 한다. acceptance 이전 timestamp의 1h bars는 어떤 거래도 만들 수 없다.
- **진입:** 활성화 후 24개 완료 1h봉 안 첫 zone overlap만 허용한다. 접촉봉 종가가 zone midpoint를 BOS 방향으로 회복하고 distal 경계를 침범하지 않으면 다음 완료 1h 시가에 진입한다. 실패·무효화·만기·새 zone 대체 후 재시도 금지.
- **손절·목표·보유:** distal 경계 바깥 0.10×BOS 시점 4h ATR14 손절, 목표 0.50R, 진입봉 포함 최대 24개 1h봉, 만기 시 다음 완료봉 시가. 한 봉에서 stop/target 동시 touch면 stop 우선.
- **비용·funding:** 왕복 12bp, R14 `adverse_only` funding 처리. 불명확 funding을 0으로 치환하거나 유리한 거래만 선택하지 않는다.
- **기록 필드:** raw BOS zones, pre-BOS sweep zones, acceptance-confirmed zones, 다음봉 부재/미통과 수, acceptance-confirmed activation zones, R14 `first_touches`·`trades` 및 종료 audit, M2 전체·비중복, Wilson 95%, win rate, 비용 후 EV/PF, 연환산 Sharpe, 누적 순수익/MDD, gap·불완전 봉·funding 미판정 건수. 서로 다른 단계 분모를 합치지 않는다.

## 판정과 다중검정

- 코인 최종 G는 그대로 유지한다: OOS 전체 발행 신호 목표 선도달률≥80%, 별도 비중복 OOS N≥200, 비용 후 EV≥15bp, PF≥1.30 및 나머지 고정 위험·강건성·다중비교·시장자료 적격성 게이트를 모두 통과해야 한다.
- 이번 실행은 단일 TRAIN 선별만이다. 어떤 TRAIN 값도 G 통과가 아니다. R21 기준선보다 M2와 비용 후 EV가 함께 개선되지 않으면 가설을 반려한다. 거래수가 줄어 M2만 커진 경우도 독립적인 성공으로 포장하지 않는다. 불확실성 구간, 표본, 수익 집중, R21 대비 차이를 기록한다.
- 장부 사전 행 수 1,678, 이번 단일 설정 포함 다중검정 계획 N=1,679. 실제 장부 행이 다르면 데이터 접근 전에 사전등록·분모를 수정하고 결과 열람 전 재고정한다. 파라미터 격자·반복 시도 없음.

## 실행·중단 조건

- `search_crypto_r22_bos_acceptance.py`의 code/grid/prereg/master prereg/data fingerprint를 기록하고, 실행 전·append 전·실행 후 writable ledger FD와 중복 process/lock을 검사한다. append-only `TRAIN_TRIALS.csv`에는 실행 결과 한 행을 추가한다.
- 합성 테스트는 sweep 1–3봉 경계, acceptance 상·하단 strict inequality, 확인봉 누락, future mutation, activation 지연, 실제 R14 zone-mapping 연동, partial ledger append rollback을 확인한다. 전체 테스트는 real market performance를 입증하지 않는다.
- 사전 행수 mismatch, source/prereg hash 변경, stale lock/writer, cutoff 불일치, 합성 경계 실패 시 가격 데이터를 열지 않고 중단한다. data-access 이후 계산·append 오류는 같은 frozen 분모로 실패 행 하나만 기록한다. 손상 가능성이 있는 append rollback 실패 시 추가 행을 쓰지 않고 기록 장애로 멈춘다.
- 기존 2018 futures 30심볼·PIT/universe provenance·상장폐지 및 데이터 이용권 게이트는 여전히 닫혀 있다. R22 결과로 이를 우회하지 않는다.
