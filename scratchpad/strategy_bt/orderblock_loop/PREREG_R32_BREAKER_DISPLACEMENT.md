# R32 사전등록 — 강한 종가 무효화 후 브레이커 재시험

상태: 실행 전 고정. R31 단일 규칙을 재실행하지 않는다. R31과 같은 zone·시간축·entry·exit를 쓰되, 무효화가 발생하는 최소 종가 돌파 깊이 하나만 추가한다.

## 가설과 근거

R31은 1,590건에서 M2 61.70%, 비용 후 EV −16.76bp, PF 0.863으로 반려됐다. 전체 표본은 충분했고 2020–2023 전부 EV가 음수였다. 약한 종가 이탈까지 “추세 전환/역할 반전”으로 간주하는 것이 원인일 수 있다. R32는 zone의 distal 경계를 최소 0.25×4h BOS ATR14만큼 종가로 넘어간 경우에만 무효화로 확정한다. 이는 무효화가 단순 흔들림이 아닌 실질적 방향 이동이어야 브레이커가 성립한다는 가설이다.

R26의 0.25 ATR 사전 sweep 깊이는 EV +81.26bp/PF 2.007이었으나 M2 62.26%, N=106으로 기준 미달이었다. 따라서 0.25 ATR을 “성공 수치”라고 가정하지 않으며, 다른 이벤트 정의(4h sweep wick이 아니라 1h 무효화 종가)에 전이해 단 한 번 검사한다. 이 임계값은 사후 최적화 격자가 아니며 인접 값은 시험하지 않는다.

## 고정 규칙

- **자료/유니버스:** R31과 동일한 고정 35종목 `universe/CRYPTO_35.csv`, Binance USD-M 4h/1h TRAIN, cutoff `2023-11-06T16:00:00Z`. 완료 1h/4h 봉만 사용. 적격 심볼 30개 미만이면 `unscorable`.
- **Zone:** R14 `bos_origin`, R14 4h close→1h activation mapper 및 single-active-zone lifetime.
- **강한 무효화 필터:** 원래 bullish zone(롱)의 1h 완료봉이 `close < zone.low`이면 `overshoot=(zone.low-close)/zone.atr_at_signal`. `overshoot >= 0.25`일 때만 무효화로 확정하고 숏 브레이커 대기로 이동한다. 얕은 이탈(`0 < overshoot <0.25`)은 `shallow_close_break_rejected`로 세되 zone을 폐기하지 않고, 원래 R31 24개 봉 만기 안에서 다음 완료봉을 관찰한다. 원래 bearish zone(숏)은 `close > zone.high`, `overshoot=(close-zone.high)/zone.atr_at_signal`로 대칭 처리한다. ATR이 0/음수/비유한이면 전체 시도를 fail-closed 처리한다. wick만 경계를 넘는 것은 무효화가 아니다.
- 매 봉에서 기존 R31 24봉 zone 만기를 강도 필터보다 먼저 판정한다. 얕은 이탈이 반복돼도 만기를 넘겨 활성 zone을 연장하지 않는다. R31의 재시험 24봉 만기도 그대로 재사용한다.
- **역할 반전/재시험:** 강한 무효화봉 다음 1h 봉부터 최대 24개 완료봉 내 첫 외부 재시험. 숏은 `open<zone.low AND high>=zone.low AND close<zone.low`, 롱은 `open>zone.high AND low<=zone.high AND close>zone.high`. zone 안 종가 복귀 또는 반대 edge까지 wick 관통은 즉시 취소한다. 약한 이탈봉을 무효화봉으로 재사용하지 않는다.
- **체결/청산:** R31 그대로, 확인 다음 1h 시가 진입, zone 내부 gap-in 또는 stop gap이면 취소, far edge ±0.10×zone ATR stop, 0.50R target, 24개 1h 최대보유, 같은 봉 stop 우선, 왕복 12bp 및 `adverse_only` funding.
- **통계:** M2는 완료된 모든 신호를 분모로 하고 funding 미확정 신호도 포함한다. 비용·손익 통계의 선별용 N은 funding 및 일별 PnL 계산 가능한 scoreable 거래 수다. 전체/비중복 M2 및 Wilson 95%, 승률, EV(bp), PF, Sharpe, 누적손익/MDD, 연도·방향별 수치와 필터 funnel/약한 이탈 거부수를 보고한다.

## 통과 기준 — 변경 금지

- TRAIN 선별(전부): scoreable N≥200, 전체 신호 M2≥75%, 비용 후 EV≥+15bp, PF≥1.30. 하나라도 미달이면 반려하고 R32를 반복하지 않는다.
- 최종 G는 OOS M2≥80%, 비중복 OOS N≥200, EV≥+15bp, PF≥1.30, Sharpe≥1.0, MDD<누적 OOS 순수익 절반, Bonferroni 0.05/N·Reality Check/SPA·Deflated Sharpe, 무작위 진입 200회·순환이동 1,000회, 비용 2배·1봉 지연, plateau·2018/2022·미사용 코호트·독립 재구현·권리/PIT gate를 모두 요구한다. TRAIN 통과도 G 통과가 아니다.
- 이전 R31은 이미 같은 TRAIN cutoff에서 열람했으므로 R32는 독립 OOS가 아니다. 이 결과로 OOS를 대체하지 않는다. R32 실패 후에도 TEST/2026-06-01 이후는 열지 않는다.

## 검증·실행 식별

- 데이터 전 합성시험: R31 전체 regression, 강한/약한 overshoot 경계(정확히 0.25 포함), 롱숏 대칭, ATR 불량 fail-closed, 반복 약한 이탈에서의 24봉 만기 경계, 미래 prefix 변조, zone 매핑→강도 필터→R31 state→공통 simulator 경로, funding/cost, R32 자체 ledger writer 충돌·부분 append 후 재시도 금지·lock/hash 검사.
- R31 완료 후 이전 장부 1,688행, 계획 분모 N=1,689, R32 기존행 0. 실행 전에 정확한 row count, writer/lock 부재, 40GB 이상 여유, split/universe/data hashes 및 코드·상세/master prereg hashes를 확인한다. 불일치하면 가격 행 접근 없이 중단한다.
- 단일 TRAIN 실행. append 실패/결과 불확실 시 재실행하지 말고 장부 상태를 대사한다. 시도 후 파라미터 조정 금지.
- 주식 PIT/상장폐지/권리 gate와 USD-M 2018·취득권 gate는 여전히 닫혀 있으며 이 실험은 그 공백을 해결하지 않는다.

## 사후 결과 기록 (2026-11-25)

단일 TRAIN 시도는 32개 종목·1,181 거래에서 완료됐다. M2 747/1,181=63.25% (Wilson 하한 60.46%), 승률 66.13%, 비용 후 EV −4.65bp, PF 0.958, Sharpe −0.243, 누적 −1.72%, MDD 4.95%였다. scoreable N만 충족했고 M2≥75%, EV≥15bp, PF≥1.30은 모두 미달하여 반려한다. 상세 수치와 R31 비교는 `REPORT_R32_BREAKER_DISPLACEMENT.md`에 둔다.

실행 당시 이 사양의 SHA-256은 `4f70da0a4097bcfe7d81f1fe8eaa57a5c51711b5291d7341c5ca596064667ee1`; 본 사후 기록은 실행 뒤 추가했으며 원본 실행 시점 해시를 대체하지 않는다.
