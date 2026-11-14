# Source_Collector 공개 데이터 코인 백테스트

실행일: 2026-10-25 (UTC run id: `20261025T085825Z`)

## 결론

공개 Binance USDT-M 선물 캔들·펀딩 데이터로 5개 심볼, 5개 봉 주기, 최대 5년 구간에 걸쳐 132개 규칙 전략 변형과 3개 기준선을 비교했다. 총 결과는 20,925행이다. 이번 결과는 탐색용 스크리닝이며, 검증된 수익 전략이나 실거래 승인으로 해석할 수 없다.

## 범위

- 심볼: BTCUSDT, ETHUSDT, BNBUSDT, XRPUSDT, ADAUSDT
- 봉: 1m(최대 90일), 5m(365일), 15m(1,095일), 1h(1,825일), 4h(1,825일)
- 각 구간 길이: 7, 30, 90, 180, 365, 730, 1,095, 1,825일 중 해당 봉의 데이터 범위 안에 들어오는 구간
- 전략: SMA/EMA 교차, Donchian 돌파, RSI 평균회귀·극단, Bollinger 평균회귀·돌파, MACD, ROC 롱·롱숏, 변동성 레짐 추세 등 132 변형
- 비교 기준선: 항상 롱, 항상 숏, 현금(노출 없음)
- 자본 표시: 128.88323162 USDT. 이는 사용자 제공 연구 자본을 결과에 기록한 값이며, 포지션 수량·최소 주문 금액·수량 단위는 모델링하지 않았다.

## 방법과 비용 가정

Binance 공개 `/fapi/v1/klines`와 `/fapi/v1/fundingRate`에서 OHLCV·펀딩 이력을 가져왔다. API 키, 계정, 주문 엔드포인트는 사용하지 않았다. 신호는 봉 마감 후 생성하고 다음 봉 시가부터 적용했다. 기본 비용은 편도 taker 수수료 0.05%, 편도 슬리피지 0.02%로 가정했고, 과거 펀딩을 포지션에 반영했다. 명목 노출은 1배다. 실제 수수료 등급·슬리피지는 확인하지 않았으므로 비용 수치는 가정이다.

전략 정의·파라미터 탐색 범위는 실행 스크립트 [source_collector_backtest.py](source_collector_backtest.py)와 결과 manifest에서 확인할 수 있다. Binance 엔드포인트 정의는 [Kline/Candlestick Data 문서](https://developers.binance.com/en/docs/products/derivatives-trading-usds-futures/market-data/rest-api/Kline-Candlestick-Data)와 [Funding Rate History 문서](https://developers.binance.com/en/docs/products/derivatives-trading-usds-futures/market-data/rest-api/Get-Funding-Rate-History)를 참조했다.

## 관측 결과

아래 값은 각 봉에서 이용 가능한 가장 긴 기간에 대해 5개 심볼의 중앙값이다. `return`은 해당 구간 누적 수익률, `MDD`는 최대낙폭이다.

| 봉 | 최대 구간 | 롱 기준선 수익 / Sharpe / MDD | 숏 기준선 수익 / Sharpe / MDD | 최고 전략군 중앙 Sharpe / 수익 / MDD |
|---|---:|---:|---:|---:|
| 1m | 90일 | +21.68% / 1.60 / -18.92% | -24.04% / -1.63 / -36.94% | RSI 평균회귀 -8.47 / -45.01% / -45.23% |
| 5m | 365일 | -42.35% / -0.69 / -62.99% | +23.92% / 0.68 / -47.27% | RSI 평균회귀 -1.92 / -53.09% / -54.82% |
| 15m | 1,095일 | +85.53% / 0.66 / -69.78% | -88.07% / -0.66 / -92.56% | RSI 평균회귀 -0.14 / -37.00% / -63.83% |
| 1h | 1,825일 | -12.76% / 0.21 / -78.48% | -74.02% / -0.21 / -96.29% | RSI 평균회귀 0.05 / -29.88% / -63.98% |
| 4h | 1,825일 | -11.90% / 0.21 / -78.36% | -73.10% / -0.21 / -95.88% | Bollinger 돌파 0.27 / +16.93% / -50.53% |

가장 나은 군은 4시간 Bollinger 돌파지만 중앙 누적 수익 +16.93%에 5년 MDD -50.53%다. 개별 최상 조합을 기준으로 선택하면 다중 탐색 편향이 생기므로 성과 증거로 볼 수 없다. 수수료·슬리피지 민감도, 시간 순서 외 표본 검증, 여러 전략 탐색 보정(DSR 등), 파라미터 안정성, 시장 체제별 결과 검증을 거쳐야 후보 여부를 판단할 수 있다.

분봉 결과는 비용 가정에 민감하다. 현재 심볼만 선택한 생존편향, 주문장·시장충격 부재, 청산·증거금 모델 부재, 거래소 수량/최소주문 제약 부재도 결과 한계다. 비용·체결 조건에 따라 결과가 바뀔 수 있다.

## 산출물과 서버 위치

- 실행 스크립트: [source_collector_backtest.py](source_collector_backtest.py)
- 기준선 후처리 스크립트: [append_backtest_baselines.py](append_backtest_baselines.py)
- 전략별 행 결과: [strategy_results_20261025T085825Z.csv](source_collector_backtest_results/strategy_results_20261025T085825Z.csv)
- 전략군 요약: [family_summary_20261025T085825Z.csv](source_collector_backtest_results/family_summary_20261025T085825Z.csv)
- 범위·가정·행 수 manifest: [manifest_20261025T085825Z.json](source_collector_backtest_results/manifest_20261025T085825Z.json)
- Oracle 결과 디렉터리: `/home/opc/source_collector_backtest/results/`
- 다운로드한 데이터 캐시: Oracle `/home/opc/source_collector_backtest/data/`

실주문 호출은 없었다. 기존 서버 컨테이너는 실행 전후 상태가 Up인 채 유지됐다.
