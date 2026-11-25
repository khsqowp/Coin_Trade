# R27 사전등록 — BOS 봉의 방향 일치 FVG 결합

상태: 사전등록 완료. 2026-11-25 구현 레드팀은 최종 수정본에 차단 요인이 없다고 판단했고 R27 synthetic 17/17이 통과했다. 아래 최종 장부·writer·cutoff 게이트를 다시 확인한 뒤 한 번의 TRAIN 시도만 허용한다. 아직 OOS/G 합격이나 시장 엣지 판정은 아니다.

## 가설

R14의 4h BOS-origin 오더블록과 1h 첫 재방문 중앙값 회복은 TRAIN 7,729건에서 M2 60.89%, 비용 후 EV −20.88bp, PF 0.826이었다. R21의 사전 BOS sweep 집단은 EV +50.55bp였지만 N=196, M2 63.27%이고, R26의 깊이≥0.25 ATR 필터는 N=106, M2 62.26%였다. 단순 추세 정렬·다음 봉 확인·sweep 깊이만으로 목표 선도달률을 크게 높이지 못했다. R27은 주문블록 구역이 BOS로부터 이탈할 때 같은 방향의 3봉 불균형(FVG)도 생기는 경우를 별도 구조 확인으로 본다. 불균형이 동반된 BOS 구역은 단순한 pivot 종가 돌파보다 방향성 있는 주문 흐름을 반영해 첫 재방문에서 목표에 먼저 도달할 가능성이 높다는 가설이다.

## 고정 규칙

- 데이터·유니버스: 기존 고정 `CRYPTO_35.csv`, cutoff-aware 완성 Binance USDⓈ-M TRAIN 4h/1h bars, cutoff `2023-11-06T16:00:00Z`. 두 시간축 사용 가능 종목이 30개 미만이면 `unscorable`. OOS/TEST 및 2026-06-01 이후 행은 열지 않는다.
- OB 후보: R14 `bos_origin` 그대로. BOS 신호 index를 `i`라 할 때 롱은 `bars[i].low > bars[i-2].high`, 숏은 `bars[i].high < bars[i-2].low`일 때만 같은 방향 FVG가 있다고 본다. 등호는 통과하지 않는다. gap 크기/ATR 최소치는 추가하지 않는다.
- FVG 입력은 완료된 BOS봉 `i`와 그보다 두 봉 앞선 완료봉 `i-2`만 사용한다. FVG는 BOS봉 마감 시 확정되며, BOS 후 봉은 FVG 분류에 쓰지 않는다. 오더블록 구역이 FVG와 겹치는지 추가 조건을 넣지 않는다.
- 필터 순서와 구역 수명주기: 각 `r4_zones(..., "bos_origin")` 출력 구역을 BOS봉 마감 시 FVG 조건으로 먼저 판정한다. FVG 통과 구역만 R14의 4h→1h 시각 매핑과 활성 구역 엔진에 전달한다. FVG 미통과 구역은 활성화되지 않고 기존 활성 구역도 대체하지 않는다. 통과 구역끼리 겹치거나 같은 활성 시각에 도달할 때는 R14의 원래 정렬·단일 활성 구역·새 구역 대체 규칙을 그대로 적용한다. 따라서 R27 funnel에는 원시 BOS, FVG 통과/거부, 매핑·활성화, 첫 접촉, 실제 거래를 각각 별도로 기록한다.
- 진입·손절·목표·만기: R14 그대로. BOS 구역 활성화 후 첫 1h 재방문 24개 봉 내 첫 접촉, 구역 중앙값 회복·distal 무효화 아님을 확인한 뒤 다음 1h 시가 진입, distal 바깥 0.10×BOS ATR14 손절, 0.50R 목표, 최대 24개 1h봉 보유, 재접촉 금지.
- 비용·funding: 왕복 12bp, 동일 봉 stop 우선, `adverse_only` funding, 기존 gap·불완전 봉·검열 처리.
- 보고: 원시 BOS 이벤트→반대색 origin이 있는 BOS 구역→방향 일치 FVG 통과/거부→1h 매핑/정렬실패→실제 활성화/활성 중 새 구역 폐기→첫 접촉→거래 funnel을 각기 분리한다. 활성화 수는 만료 경계의 같은 봉 재처리, 첫 접촉 censor, simulator censor를 포함해 R14 lifecycle을 재생해 센다. 전체/비중복 M2 및 Wilson 95%, 승률, EV, PF, Sharpe, 누적손익/MDD, funding/gap/불완전 봉, 방향·UTC entry-year 귀속도 보고한다.

## 기준·실행 게이트

- 최종 G 변경 금지: OOS M2≥80%, 비중복 OOS N≥200, 비용 후 EV≥15bp, PF≥1.30 및 다중검정/강건성/출처/PIT/이용권 gate 전부 필요. TRAIN은 G 통과가 될 수 없다.
- TRAIN 후속 검토선은 N≥200, M2≥75%, EV≥15bp, PF≥1.30 모두 충족으로 고정한다. 이 선도 최종 합격선이 아니다.
- 예상 ledger rows 1,683, 이번 설정 포함 계획 Bonferroni 분모 N=1,684. 실행은 `.cointrade_train_trials.lock`과 `.ob_attrition_train_trials.lock` 두 writer 계열 잠금을 함께 보유하고 장부 writer 부재를 확인한 뒤 시작한다. 실행 전 ledger 행수, source/prereg hash, 30심볼, cutoff 및 합성 종단 테스트도 확인한다. 잠금·writer 부재를 증명할 수 없거나 장부 스키마/중복 R27이 확인되면 장부를 건드리지 않고 사전 데이터 중단으로 보고한다. 안전한 writer 부재가 확인된 뒤 prereg/hash 또는 분모만 불일치하면 시장 행을 열지 않고 실패 sentinel을 한 줄 추가하며, 분모는 실제 기존 행 수+1로 기록한다. 쓰기 오류 시 타 writer의 기록을 보존하기 위해 장부를 truncate하지 않고, tail 상태 불명으로 중단·보고한다.
- 한 번만 실행한다. 같은 정의의 threshold 변경·부분집단 선택·사후 재실행은 금지한다. 손익 결과를 보고 기준·정의를 바꾸지 않는다.
- 사전등록 중단선: train 표본 N<200이면 후속 후보 선별선 미달로 즉시 반려하되 시도 1건을 기록한다. 결과를 확인한 다음 새 cutoff나 새 가설로 바꾸지 않는다.

## 필수 합성 검증

3봉 FVG의 롱·숏 대칭, strict inequality와 동일 경계 거부, i-2 및 i 봉의 올바른 사용, BOS 완료 전/후 데이터 미래변경 불변성, FVG 여부에 따른 zone funnel 카운터, R27 필터→실제 R14 4h→1h 매핑→첫 접촉→setup→공통 simulator의 체결/stop-first/비용/funding 경로를 검증한다.

## 계획 산출

단일 cutoff-safe TRAIN 결과와 사후 ledger/stdout/hash 대사는 `REPORT_R27_BOS_FVG_CONFLUENCE.md`에 기록한다. 사전 데이터 gate 실패는 위의 append-safe 규칙으로 sentinel 또는 사전 데이터 중단 보고를 남긴다. 서버, 실거래, OOS, 데이터 다운로드는 범위 밖이다.
