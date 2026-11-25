# R29 사전등록 — BOS 체결흐름 일치 필터

상태: 실행 전 사전등록. 고정 1개 가설, 파라미터 탐색 없음. 결과를 열기 전에 본 문서와 `PREREG.md` 항목을 고정한다.

## 가설과 구분점

기존 R27·R28은 각각 BOS 캔들 주변 가격 공백(FVG)과 종가 위치를 사용했고, 비용 후 기대값을 개선하지 못했다. R29는 가격 모양을 추가하지 않고, BOS가 완료된 바로 그 4시간 동안 공격적 매수 체결이 전체 quote 거래량의 절반보다 많은지 확인한다. 상승 BOS의 매수체결 우위가 이후 첫 구역 재방문에서 매수 지속성을 높이고, 하락 BOS의 매도체결 우위가 매도 지속성을 높인다는 가설이다. 단, Binance Kline taker-buy quote 비중은 호가장 주문 추가·취소까지 포함하는 order-flow imbalance가 아니며, 시장가 체결량만 이용하는 더 약한 대리변수다. 그 차이를 넘어서 문헌 결과를 그대로 적용한다고 주장하지 않는다.

## 고정 규칙

- 시장·유니버스: 기존 `universe/CRYPTO_35.csv`의 35개 Binance USD-M USDT 무기한 심볼. 심볼 선택이나 제외를 결과에 맞춰 바꾸지 않는다.
- 데이터: 로컬에 이미 있는 `external/crypto/binance/um_klines_1m/<SYMBOL>/<YYYY-MM>.parquet`의 1분 Kline. 계산에 필요한 열은 `open_time, open, high, low, close, volume, quote_volume, taker_buy_quote_volume`이다. 외부에서 다시 받지 않는다.
- 시점: 4h BOS 봉 `[timestamp, timestamp+4h)` 안의 240개 1분봉만 사용한다. 데이터 접근은 각 1m `open_time < 2023-11-06T16:00:00Z`로 제한한다. BOS 4h 봉은 완료되어야 하며 미래 1분봉·확인봉·진입봉 값은 필터에 사용하지 않는다.
- 입력 무결성: 해당 4h 학습봉마다 1분 open_time이 정확히 240개이고 분 간격·정렬·중복이 없어야 한다. 1분 OHLC와 기초 거래량을 재집계한 값은 기존 4h 봉과 사전 고정 허용오차 `rel_tol=1e-9, abs_tol=1e-9` 안에서 일치해야 한다. 총 quote volume은 양수, taker-buy quote는 0 이상이고 총 quote 이하이어야 한다. 불일치·누락·잘못된 수치는 해당 봉을 조용히 빼지 않고 실험 전체의 데이터 무결성 오류로 처리한다.
- 계산: `buy_share = sum(taker_buy_quote_volume) / sum(quote_volume)`. 롱 BOS는 `buy_share > 0.50`, 숏 BOS는 `buy_share < 0.50`일 때만 통과한다. 정확히 0.50이면 거부한다. 임계값은 탐색하지 않는다.
- 순서: 이 필터는 4h BOS 봉이 닫힌 후 zone을 생성할 때 적용한다. 거부된 zone은 이후 활성 zone·구역 목록을 대체하지 않는다. 먼저 통과한 구역만 기존 R14 매퍼에 전달한다.
- 진입·청산: 기존 R14와 동일하게 4h `bos_origin`, 1h 첫 재방문, zone 중앙값 회복 확인, 그 다음 1h 시가 진입, zone 바깥 `0.10×ATR` 손절, `0.50R` 목표, 최대 24개 1h 봉, 같은 봉 손절 우선, 왕복 비용 12bp, 불리한 방향 펀딩만 차감한다. 다른 값은 조정하지 않는다.
- 기간: 기존 공통 시간순 TRAIN만 사용하며 학습봉 close cutoff는 `2023-11-06T16:00:00Z`. OOS/TEST, 동결구간, 2026-06-01 이후 자료를 열지 않는다.
- 장부: 실행 전 1,685행, 이번 1회 포함 계획 분모 `N=1,686`. 기준 불일치면 데이터 성과를 계산하지 않는다. 단일 실행만 허용하며 실패도 한 번의 시도로 남긴다.

## 사전 고정 판정

TRAIN 선별 통과는 거래 수 `N≥200`, 전체 신호 M2 `≥75%`, 비용 후 EV `≥+15bp`, PF `≥1.30`을 모두 충족하는 경우뿐이다. 이는 탐색 단계 선별선이며 코인 최종 G를 낮추지 않는다. 최종 G는 사용자가 정한 OOS 전체 M2 `≥80%`, 별도 비중복 OOS `N≥200`, EV `≥+15bp`, PF `≥1.30`, 통계·강건성·데이터 gate 전부를 계속 요구한다. 현재 Binance USD-M 로컬 1분 아카이브는 2020년부터라 R29 단독으로 2018 약세장 조건을 검증할 수 없다. 이 결함은 통과로 간주하지 않는다.

## 요구 테스트 및 중단 조건

1. `buy_share` long/short 경계, 0.50 동률, 잘못된/0 quote volume 테스트.
2. 240분 완전성, 중복·누락·정렬, 월 경계, cutoff 경계, OHLC/기초거래량 재집계 불일치 테스트.
3. BOS 시점 이후 분봉을 변조·추가해도 이미 끝난 BOS 비율과 필터 결과가 변하지 않는 인과성 테스트.
4. 실제 `crypto.r4_zones` BOS 검출 → 필터 → R14 매핑·활성화·진입·손절/목표 시뮬레이션 합성 종단 테스트. 거부된 후행 구역이 앞서 통과한 활성 구역을 대체하지 않아야 한다.
5. 고정 split 캐시가 불변이고 모든 frozen symbol 파일 셋이 정확한지 확인한다. 장부 중복·append 불확실성·다른 writer 존재 시 실행하지 않는다.
6. 독립 레드팀이 코드·사전등록·테스트를 승인해야 한다. 이 승인은 실데이터 성과나 전략 우수성의 증거가 아니다.

## 출처·권리 경계

- Binance Public Data의 Kline 스키마에는 `Quote asset volume`, `Taker buy quote asset volume`이 포함된다: <https://github.com/binance/binance-public-data/blob/master/README.md>.
- Binance Vision 2026-08-26 약관은 개인 비상업·비생산 역사 백테스트를 허용 범위에 두고 데이터 및 파생 지표에 조건을 적용한다: <https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md>. 로컬 파일 취득 시점의 적용 약관·완전한 provenance는 별도 감사 대상이며 이 사전등록만으로 입증하지 않는다. 실시간 신호 배포·상업 사용·실주문에는 사용하지 않는다.
- Cont, Kukanov, Stoikov (2010/2014), <https://arxiv.org/abs/1011.6402>: best bid/ask의 limit order·market order·취소를 포함하는 OFI가 단순 체결량보다 가격 움직임과 더 강한 관계를 보였다고 보고한다. R29는 그 OFI가 아니라 거래소 Kline의 taker-buy 체결 비중만 시험하므로, 본 논문은 가설의 동기만 제공한다.

## 결과 보고 항목

총 거래·M2와 Wilson 95% 구간·비중복 M2·승률·평균 이익/손실·EV(bp)·PF·누적 순손익·Sharpe·MDD·펀딩 미채점·비용·연도별 결과, 전체 4h 봉 수 및 매핑된 flow 봉 수, 원자료 재집계 불일치/누락 수, raw BOS/flow 평가·통과·거부/매핑/활성화 funnel을 기록한다. 결과는 TRAIN 전용이며 OOS 및 G 통과로 표시하지 않는다.
