# R26 사전등록 — R21 pre-BOS sweep 깊이 최소치

상태: 단일 TRAIN 실행 전 고정. R21과 같은 시간축·유니버스·진입·청산을 유지하고 sweep 깊이 조건 하나만 추가한다. R25의 1h/15m 이전 실험은 반려됐으며 이와 별개의 설정이다.

## 가설과 근거

R21의 4h external sweep→1~3봉 내 BOS 하위집단은 TRAIN 196건에서 M2 63.27%, EV +50.55bp, PF 1.548이었으나 M2≥80%, 비중복 OOS N≥200, Sharpe 및 강건성 G를 충족하지 못했다. R22의 다음 4h 확인봉 대기는 EV/PF를 낮췄고, R24의 BOS impulse 극값 목표는 M2를 44.56%까지 낮췄다. R25는 같은 sweep 순서를 1h/15m로 이전했지만 881건에서 EV −26.60bp, PF 0.648이었다. R26은 4h/1h 시간축과 R21의 수익 구조를 그대로 두고, 이전 20봉 극값을 아주 조금 넘은 wick을 진짜 sweep으로 보지 않는다는 기계적 가설을 한 번 시험한다.

## 고정 규칙

- **데이터·유니버스:** R21과 같은 `CRYPTO_35.csv` 고정 35심볼, cutoff-aware 완성 Binance USDⓈ-M 4h/1h TRAIN bars, cutoff `2023-11-06T16:00:00Z`. 분석 가능 심볼 30개 미만은 `unscorable`. OOS/TEST와 2026-06-01 이후는 열지 않는다.
- **OB 정의·zone lifecycle:** R21 `bos_origin` 및 기존 1-active-zone 규칙.
- **sweep 후보:** 각 BOS 신호 4h봉 index `i`의 직전 1~3개 완료 4h봉만 조사한다. 후보 sweep 봉 `j`의 기준 레벨은 `bars[j-20:j]`로 계산한 이전 20개 완료 봉의 최저 wick(롱)/최고 wick(숏). 롱은 `low < level AND close > level`, 숏은 `high > level AND close < level`이어야 한다.
- **새 깊이 필터:** sweep 봉 `j`의 완성 시점 ATR14를 기존 공통 `_atr(bars, j, 14)`로 계산한다. 롱 깊이는 `(prior20_min_low - bars[j].low) / ATR14`; 숏 깊이는 `(bars[j].high - prior20_max_high) / ATR14`. 값이 `>=0.25`인 후보 sweep이 BOS 직전 1~3봉 중 하나라도 있을 때만 zone을 유지한다. ATR14가 없거나 0이면 불합격. 임계값 0.25는 한 번만 사용하며 격자·결과 후 조정 금지.
- **진입·손절·목표·만기:** R21 그대로: BOS zone 활성화 후 첫 1h 재방문 24개 봉 내 첫 접촉만, zone midpoint를 방향대로 회복하고 distal을 침범하지 않으면 다음 1h 시가 진입, distal 바깥 0.10×BOS ATR14 손절, 0.50R 목표, 최대 24개 1h봉 보유, 재접촉 금지.
- **비용·funding:** 왕복 12bp, 동일 봉 stop 우선, `adverse_only` funding, 기존 R14 gap·불완전봉·검열 규칙.
- **집계:** raw BOS→기본 R21 sweep→0.25 ATR 깊이 통과→zone 활성화→첫 접촉→거래 funnel, 전체/비중복 M2와 Wilson 95%, 거래 승률, EV, PF, Sharpe, 누적손익/MDD, 기본 sweep은 있었으나 깊이 미달인 zone 수, ATR warmup/무효값으로 거부된 zone 수, 불완전·gap 카운터, 방향 및 UTC entry-year 귀속을 보고한다. 두 거부 카운터는 깊은 sweep이 하나라도 있으면 해당 zone에서 0이며, 미달과 ATR 거부가 서로 다른 후보 봉에서 함께 나온 zone은 두 카운터에 모두 포함될 수 있다.

## 판정·중단

- 최종 G는 변경하지 않는다: OOS M2≥80%, 비중복 OOS N≥200, 비용 후 EV≥15bp, PF≥1.30 및 고정 다중검정·강건성·PIT/출처/이용권 gate 전부 통과해야 한다. R26 TRAIN은 G 통과가 될 수 없다.
- 후속 OOS 후보 검토 기준은 실행 전에 고정: TRAIN 거래 N≥200, M2≥75%, EV≥15bp, PF≥1.30 모두 충족. 미달하면 반려하고 R21 대비 원인을 기록한다. 이 기준은 최종 G를 낮추지 않는다.
- 단일 설정·단일 실행. 실행 전 장부 본문 1,682행, 이번 시도 포함 계획 다중검정 분모 N=1,683. 행 수, writer/lock, source/prereg hash, 30심볼, cutoff, 필수 합성 종단간 테스트가 하나라도 맞지 않으면 가격 입력 전에 중단한다. 실패 시도도 분모에 포함한다.
- R21과 다른 점은 sweep 깊이 문턱 하나뿐이다. 손실·M2 결과를 본 뒤 조건·임계값·목표·보유기간을 수정하거나 같은 설정을 재실행하지 않는다.

## 필수 합성 검증

ATR14 경계와 warmup, 깊이 0.25 미만/정확히 0.25/초과, 롱·숏 대칭, 이전 20봉 기준 레벨·현재 BOS봉 제외, 1·3봉 인정/4봉 거부, sweep 직후부터 BOS 전까지의 봉 및 BOS 이후 데이터 mutation 불변성, R21 필터→R14 실제 4h→1h 매퍼→첫 접촉→setup→공통 simulator 체결·same-bar stop-first·비용/funding까지 연결하는 종단간 테스트를 데이터 실행 전에 통과시킨다.

## 실행 결과 위치

한 번의 cutoff-safe TRAIN 실행 결과는 `REPORT_R26_DEEP_SWEEP_ATR.md`에 저장하고 stdout·append-only ledger 행·code/grid/data/prereg 지문을 대조한다. 실제 거래나 서버·NAS 작업은 하지 않는다.
