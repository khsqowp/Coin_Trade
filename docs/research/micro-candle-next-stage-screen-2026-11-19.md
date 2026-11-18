# 다음 초단기 후보 스크리닝 — 2026-11-19

## 결정

**새 성과 백테스트 후보 없음.** 캔들 기반 단일·다중봉 계열을 더 조합하면 기존 연구의 재탕 또는 사후 조건 추가가 된다. 체결흐름 기반 흡수 신호도 이미 2026-11-17에 등록된 후보와 R005 liquidity-replenishment 가설에 겹친다. 새 이름이나 임계값만 붙여 시험하지 않는다.

## 이번 라운드 연구 범위

- Phase 5–8 결과와 preregistration, 차트 setup 라이브러리, MACD/RSI 백테스트, 기존 taker-imbalance·liquidity-sweep 결과를 검색했다.
- 두 독립 에이전트에 각각 OHLC 1분 미세패턴의 신규성·중복 검토를 맡겼다. 둘 다 신규 후보를 제시하지 않았다.
- 같은 두 연구자에게 이벤트 단위 `trades`/`aggTrades` 신호를 별도로 검토시켰다. 하나는 이미 있는 taker-flow/absorption 및 R005 계획과 중복, 다른 하나는 실행가격·스프레드·호가자료 부재로 방어 가능한 규칙을 지금 고정할 근거가 부족하다고 판정했다.
- 에이전트는 원본 데이터 파일을 내려받지 않았고, 연구 라벨을 읽거나 새 백테스트를 돌리지 않았다.

## 현재 로컬 데이터에서 확인한 사실

- 연구용 `vision_pit_dev_sample.sqlite`는 30,363,320,320 bytes, 86개 심볼이며 관측 범위는 2021-01-01 00:00 UTC부터 2026-10-31 23:59 UTC다. 이 DB는 `/Users/user/CODE/Coin_Trade`의 100심볼 `candles.sqlite`와 다른 스냅샷이다.
- `candles`에는 `quote_volume`, `taker_buy_base`, `taker_buy_quote`, `trade_count`가 있다. 전체 테이블 스캔에서 `taker_buy_quote`와 `quote_volume` null 수는 0이고, `taker_buy_quote < 0` 또는 `taker_buy_quote > quote_volume`인 행도 0이었다.
- `quote_volume <= 0`인 행은 여러 심볼에서 관측됐다. 따라서 이 바를 0 imbalance로 간주해서는 안 되고, 신호 적격성·커버리지를 별도로 보고 제외해야 한다.
- 기존 manifest 보고는 86심볼·70개월 중 월별 기대 1분 행수가 모두 채워진 심볼 37개, 38개 심볼의 구조적 minute gap 577,125개를 기록한다. 이 DB의 86심볼 전체가 point-in-time 상장·상폐 유니버스이거나 모든 월별 archive lineage가 검증됐다는 뜻은 아니다.
- 로컬 데이터 폴더에는 별도 raw `trades`/`aggTrades` ZIP·CSV·Parquet 파일이 없었다. 현재 taker 필드는 1분 OHLCV 집계치라 체결 순서·호가 잔량 회복·실행 가능한 bid/ask를 복원할 수 없다.

## 중복 근거

- 기존 taker-flow 제안은 5분봉 taker imbalance와 가격 비진행/확인, 4시간 EMA 허용 필터를 사용한다. 상태는 데이터·방법 게이트 미통과이며 성과시험 금지다. [기존 제안](agent_work_2026-11-17/crypto_taker_flow.md)
- 이전 연구에 1분 sweep/wick/taker-flow 조합이 있고, 별도 taker-imbalance 다중 시간봉 그리드는 1분을 포함해 결과가 부정적이었다. 위 제안은 새 이론이라기보다 흡수 해석을 덧붙인 근접 가설이다.
- raw trade aggressor flow만으로 가격 정체를 “호가 흡수”라고 결론 낼 수 없다. 실제 liquidity replenishment는 L2 이벤트나 최소한 동기화된 bid/ask·depth가 필요하다. Binance USDⓈ-M 역사 `trades` 아카이브는 체결 ID, 가격, 수량, 시간, `isBuyerMaker`를 제공하지만 호가 잔량은 제공하지 않는다.

## 새 시험 전에 필요한 최소 데이터 게이트

1. 다음 연구가 raw trade-flow라면 `trades` 또는 `aggTrades` 중 하나만 고른다. 둘은 집계 단위가 달라 혼합 금지.
2. outcome을 열기 전에 후보 심볼·기간별 파일 URL/버전·SHA-256·행수·열·timestamp 단위·ID 중복/갭·시간 정렬·필드 null/범위를 검증한다.
3. 기존 월별 archive manifest와 분별 candle volume/taker-buy 값을 대조한다. 시간대별 체결 집계와 candle quote volume의 정합성을 측정하되, 설명되지 않는 차이는 통과 처리하지 않는다.
4. 거래비용 자료가 없으면 10/30bp는 측정값이 아닌 스트레스 가정으로 표기한다. 호가·체결 가능 가격·지연이 없는 결과를 비용 견고성으로 부르지 않는다.
5. 그 후에만 outcome-blind 빈도 게이트를 계산한다. 가설/방향/각 OOS 구간별 비중복 N≥200 및 심볼≥20을 확인하고, 실패하면 결과 라벨 단계로 넘어가지 않는다.
6. 새 가설이 정말 중복되지 않을 경우에만 전체 발행 M2≥80%, 기한 종료 방향 정확도 별도, 비용 후 순 R 기준을 사전등록한다. 5×(504일 train/252일 test) walk-forward, 1,000회 trade-order Monte Carlo, ±10%/±20% 이웃 민감도는 결과 열기 전에 전부 정의한다. 연구 노출 과거는 독립 OOS로 포장하지 않는다.

## 공개 데이터 범위와 제한

Binance Public Data는 USDⓈ-M `trades`·`aggTrades` 역사 파일과 체결 방향 필드를 문서화한다. 데이터는 연구·개인 비프로덕션 역사 백테스트에만 사용한다. Binance Vision 약관은 live proprietary execution, 자동 주문 생성, 보상성 signal distribution을 금지하고 다운로드·파생 지표에도 적용한다. 따라서 이를 이용한 어떤 결과도 실시간 시그널 또는 실매매에 연결하지 않는다.

## 처리 결과

- Phase 8 성과시험: 모든 8개 셀 탈락. [결과](micro-candle-phase8-10m-15m-m2-results-2026-11-18.md)
- Phase 9 성과시험: **실행 안 함**. 중복·데이터 계측 한계가 먼저 확인됐다.
- 다음 유효 작업: 새로 등록하는 전략이 아니라, 기존 Phase 9 제안의 데이터 품질·빈도만 outcome-blind로 검증하거나, 실제 L2를 포함하는 별도 연구 범위를 정한 뒤 preregistration을 다시 검토한다.
