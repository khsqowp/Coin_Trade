# R30 사전등록 — 첫 재방문 중앙값 회복봉의 체결흐름 확인

상태: 실행 전 고정된 단일 TRAIN 가설. 실데이터를 읽기 전에 합성 검증·독립 리뷰·장부/해시/잠금 사전점검을 통과해야 한다.

## 1. 가설

R14 기본 신호는 4h BOS-origin 오더블록을 1h에서 처음 재방문한 뒤, 접촉 1h봉이 중앙값을 BOS 방향으로 회복하면 다음 1h 시가에 진입한다. R29는 같은 방향의 taker-buy quote 비중을 4h BOS 발생 시점에 적용했으나 TRAIN에서 M2 60.93%, EV −19.79bp, PF 0.827로 반려됐다. R30은 BOS 순간의 과거 체결압력을 반복하지 않고, 실제 첫 재방문 확인봉 내부의 공격적 체결이 구역 반응을 지지하는지 한 번만 시험한다.

검증할 메커니즘은 “오더블록 구역에서 가격이 중앙값을 회복하는 동시에 taker 체결량도 같은 방향으로 치우치면, 그 첫 반응 이후 목표가 손절보다 먼저 닿을 확률이 증가한다”이다. 이는 가설이지 성과 주장이 아니다. Kline taker-buy quote 비중은 호가장 잔량·취소를 포함하는 order-flow imbalance와 다르며, 거래량 비율만으로 신규 포지션과 청산을 구분하지 못한다.

## 2. 실험·유니버스·기간

- 시장: Binance USDⓈ-M USDT 무기한 선물, 고정 `universe/CRYPTO_35.csv` 35종목.
- 사용할 심볼 수: cutoff-safe 1h/4h 데이터가 모두 있는 종목을 기록한다. 적격 심볼이 30개 미만이면 `unscorable`; 심볼을 사후 대체하지 않는다.
- 전략 베이스: R14의 코드 정의 `bos_origin`, 4h zone → 1h 첫 재방문 및 첫 touch 1h봉의 방향성 중앙값 회복 → 다음 1h 시가 체결.
- 시간 범위: R14와 동일한 고정 TRAIN 분할, 마지막 허용 학습봉 마감 `2023-11-06T16:00:00Z` 이하. 1m 원본의 행 필터도 `open_time < 2023-11-06T16:00:00Z`로 고정한다.
- OOS/TEST, final-freeze 구간, 2026-06-01 이후 데이터는 열지 않는다.
- 단일 고정 설정, 한 번의 시도다. 파라미터 격자·다른 임계값·다른 시간창은 없다.

## 3. 1m 체결흐름 필터

R14에서 이미 `setup`이 유효하게 생성된 첫-touch 1h 확인봉 `b`에 대해 정확한 시간구간 `[b.timestamp, b.timestamp + 3,600,000ms)`의 1m Kline 60개를 사용한다.

```text
buy_share = Σ(taker_buy_quote_volume) / Σ(quote_volume)
롱 통과: buy_share > 0.50
숏 통과: buy_share < 0.50
정확히 0.50: 거부
```

해당 1h봉의 종가와 60개 1m 봉은 확인봉 종료 시점에만 이용 가능하다. 필터가 통과해도 진입 가격·시간은 변경하지 않고 다음 1h봉 시가로 고정한다. 확인봉 종료 뒤 또는 진입 시가 뒤의 값은 필터 계산에 넣지 않는다.

필터가 방향 불일치·동률이면 setup을 거부한다. 첫-touch zone은 이미 한 번 사용한 것으로 처리하고 두 번째 접촉에서 다시 진입하지 않는다. 필터 거부 zone은 다른 활성 zone을 제거하거나 대체하지 않는다.

## 4. 원자료·시간 정합성·fail-closed

- 원자료는 이미 저장된 `TRADING_DATA_DIR/external/crypto/binance/um_klines_1m/<SYMBOL>/<YYYY-MM>.parquet`만 쓴다. 네트워크 다운로드, 거래소 API 호출, 새 데이터 변환본 저장은 하지 않는다.
- 필요 열: `open_time, open, high, low, close, volume, quote_volume, taker_buy_quote_volume`.
- 입력은 월 파일 단위로 한 번 읽고 1h UTC 시간 구간으로 그룹화한다. 각 적격 1h candle은 정확히 60개 분봉이 있어야 하며 open_time이 순서대로 1분 간격이어야 한다. 중복, 빠진 분, 정렬 오류, 비정수·비유한 시각은 전체 시도를 실패 처리한다.
- 각 1m 봉은 양수 저가와 내부 일관 OHLC, 음이 아닌 base/quote volume, `0 ≤ taker_buy_quote_volume ≤ quote_volume`을 만족해야 한다. quote 합계는 양수여야 한다.
- 60개 1m 봉으로 재집계한 1h 시가·고가·저가·종가·base volume은 기존 cutoff-safe 1h cache와 사전 고정 `math.isclose(rel_tol=1e-9, abs_tol=1e-9)`로 일치해야 한다. 하나라도 불일치하면 실험 전체를 실패 처리한다.
- 2023-11-06 16:00 UTC 이후 open_time이 섞이지 않도록 Parquet 읽기 필터를 적용한다. 해당 cutoff를 넘는 파일명·시각은 판단 근거로 사용하지 않는다.
- 특징 지문은 심볼·1h 시각·재집계 quote/taker 합계만 순서대로 해시한다. 원자료 행이나 결과 데이터셋을 저장소 안에 만들지 않는다.

## 5. 고정 진입·청산·비용

R14 엔진과 동일하게 유지한다.

- 진입: first-touch 1h봉의 중앙값 회복과 이 사전등록의 체결흐름 조건이 모두 성립한 뒤 다음 1h 시가.
- 무효화: 롱은 zone 저가, 숏은 zone 고가 재관통.
- 손절: distal zone 경계 바깥 `0.10 × BOS 시점 4h ATR14`.
- 목표: `0.50R`.
- 시간 청산: 최대 24개 1h봉. 만기 시 기존 R14 체결 규칙 유지.
- 같은 봉에서 손절·목표 동시 터치: 손절 우선.
- 왕복 비용: 12bp. funding은 R14 `adverse_only` 결제 이벤트 규칙 그대로 반영한다. 미판정은 누락하거나 제거하지 말고 수와 상태를 보고한다.
- 포지션 크기·레버리지·복리 방식은 R14와 같은 엔진 규칙으로 고정하며 결과에 맞춘 변경은 금지한다.

## 6. 사전 판정선

탐색 TRAIN에서 선별 통과하려면 아래 전부를 만족해야 한다.

1. 전체 목표 선도달 표본 `N ≥ 200`.
2. 전체 신호 M2 `≥75%`.
3. 비용 후 거래당 기대값 `≥+15bp`.
4. PF `≥1.30`.

하나라도 미달이면 반려하고 같은 체결흐름 구간·같은 임계값을 재시험하지 않는다. 통과해도 이는 OOS·최종 후보 승인이 아니다. 최종 코인 G는 봉인 OOS에서 M2 목표 선도달률 `≥80%`, 비중복 표본 `N≥200`, 비용 후 거래당 기대값 `≥+15bp`, PF `≥1.30`, 연환산 Sharpe `≥1.0`, 최대 낙폭 `< OOS 누적 순수익의 절반`을 모두 만족해야 한다. 무작위 귀무·순환이동·비용 2배·1봉 지연·평탄도·레짐·미사용 심볼군·Bonferroni/Reality Check·SPA/Deflated Sharpe·독립 재구현·데이터 권리/PIT 조건도 그대로 통과해야 한다.

## 7. 시도 장부와 고정 해시 절차

- 장부: `scratchpad/strategy_bt/orderblock_loop/TRAIN_TRIALS.csv` append-only.
- 실행 직전 예상 행수 1,686. 이 R30을 포함한 Bonferroni 분모 `N=1,687`.
- 실행 직전 장부 writer/전용 lock 부재, 장부 행수, R30 중복 ID, 1h/4h 고정 split manifest, 35개 종목 key, cutoff, code/prereg hash를 확인한다. 예상 행수나 고정 입력 지문이 다르면 실험 시도 자체를 시작하지 않고 시장 가격행 접근 전 중단한다. 이 경우 ledger 행을 억지로 추가하지 않는다. 중단 사유와 확인한 메타데이터는 별도 상태 보고에 남기며, 원인을 해결한 뒤 새 사전등록/hash로만 재개한다.
- 실행 중 prereg·코드·split 입력은 불변이다. 성공/실패를 포함해 한 행만 기록하며 append 불확실 시 자동 재시도하지 않는다.
- 기준 변경·기준 완화·R30 재실행 금지. 이번 시도 후 조정은 새 ID와 새 prereg가 필요하다.

## 8. 테스트·독립 검토

실데이터 접근 전에 다음 합성 테스트와 독립 red-team review를 모두 통과한다.

1. 60분 연속성, UTC hour 정렬, 월 경계, cutoff 경계, 중복·누락·역순·fractional/NaN/bool timestamp를 검사한다.
2. OHLC/base-volume 재집계 일치·불일치, quote 합계 0, 음수/비유한 거래량, taker-buy가 총 quote보다 큰 경우를 각각 검사한다.
3. 롱/숏 50% 경계와 정확한 동률 거부를 검사한다.
4. 확인 1h봉 종료 이후 1m행을 수정·추가해도 해당 신호·flow 비율·이전 신호가 바뀌지 않는 미래변조 불변성을 검사한다.
5. 실제 R14 zone 생성→첫 접촉→midpoint setup→flow filter→다음 시가 거래 시뮬레이터 경로를 합성 종단 검증한다. flow mismatch가 setup을 거부하고 zone을 재사용하지 않는지 확인한다.
6. 예외 발생 때 monkeypatch 원복, 장부 append 1회, 중복 R30 거부, 고정 split 미변경 및 writer-lock 동작을 검사한다.

레드팀은 timestamp의 lookahead, 1m/1h 봉 정렬, 첫 터치 소진, 수수료·funding 동일 적용, 저장소 밖 데이터 경로, 해시 고정, 분모 및 실패 기록을 독립 점검한다.

## 9. 결과 보고 필드

완료 또는 실패 후 1m 입력 지문, code/grid/detailed/master prereg hash, 종목 수, 1m source 파일 수·행 수, 1h eligible/validated bar 수, 누락/부정합 수, R14 raw setup 수, flow 평가·통과·거부 수, 전체 M2와 Wilson 구간, 비중복 표본/M2, 승률, 평균 이익·손실, EV(bp), PF, 누적순손익, Sharpe, MDD, funding 미판정 수, 연도·방향별 결과를 기록한다.

성공하지 못한 원인은 사전등록된 funnel과 결과만으로 분석한다. 과도한 목표, 비용, 신호 시점, 데이터 지연 또는 비용 민감도 중 증거가 있는 항목과 확인할 수 없는 항목을 분리한다. 결과가 나오기 전 기준이나 다음 조건을 바꾸지 않는다.

## 10. 범위·자료 근거·알려진 한계

- Binance USD-M Kline 공식 스키마는 quote asset volume 및 taker buy quote asset volume을 정의한다: <https://github.com/binance/binance-public-data/blob/master/README.md>.
- Binance Vision 약관은 개인 비상업·비생산 역사 백테스트 범위에 조건을 두고 데이터 및 파생지표의 사용을 규정한다: <https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md>. 로컬에 이미 보유한 파일의 실제 취득 시점 provenance는 별도로 완전히 입증되지 않았다.
- Cont, Kukanov, Stoikov의 연구는 주문장 기반 OFI의 설명력을 다룬다: <https://arxiv.org/abs/1011.6402>. Kline의 taker-buy quote 비중이 OFI와 동일하다는 주장은 하지 않는다.
- 현재 Binance UM 고정 코호트 데이터가 2020년 이후라 이 실험은 2018 약세장·상폐·완전 PIT를 검증할 수 없다. 이에 따라 R30이 TRAIN 선별선을 통과해도 최종 G 증거는 아니다.
- 실주문·API 키·실시간 신호 배포·서버·TEST 데이터 접근은 이 연구 범위에 포함되지 않는다.
