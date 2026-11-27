# 사전등록: Binance·Kraken 고정 코호트 월별 커버리지 게이트

등록일: 2026-11-28 (Asia/Seoul)
상태: 실행 전 고정

## 목적

선행 Binance spot 고정 코호트의 20개 완전 월별 자산에, 이미 저장된 Kraken OHLCVT 현물 아카이브의 실제 월별 캔들 존재를 더할 수 있는지 확인한다. 이 검사는 원천 적격성 탐색이며 가격 성과·전략 우수성·기존 선물 결과의 재현을 주장하지 않는다.

## 고정 입력과 유니버스

- 코호트: `PREREG_BINANCE_SPOT_CMC201801_TOP30_BASEBTC_1H_OBJECT_MATRIX_20261127.md`의 고정 CMC 2018 상위 30 자산에서 BTC benchmark를 제외한 29개. 코호트·ticker identity 변경 금지.
- Binance 기준: `REPORT_BINANCE_SPOT_FIXED_QUOTE_FALLBACK_CMC201801_20261128.md`에서 확인된 2018·2022 완전 월별 자산 집합 20개를 고정 입력으로 사용한다. 해당 보고서와 집합은 결과를 보기 전에 정해져 있다.
- Kraken 입력: 저장소 내부 `TRADING_DATA_DIR/external/crypto/kraken/ohlcvt_full_2026-09-30/Kraken_OHLCVT_Full.zip`의 60-minute(1h) member만 읽는다. Binance 대체 quote 기준과 timeframe을 맞춘다. 각 자산은 사전 고정 alias에 따라 direct USD pair를 우선하고, 없을 때만 direct XBT quote pair를 쓴다. ticker가 모호하거나 exact alias가 없는 pair는 실패 처리한다.
- 다른 venue, 현재 상장목록, 현재 시세, 외부 다운로드/API, 사용자 계정·키를 사용하지 않는다.

## 데이터 읽기 경계

- ZIP을 수정·추출하지 않는다. 지정된 Kraken 1h CSV member의 첫 열(epoch timestamp)만 순차 읽어 2018-01~2018-12 및 2022-01~2022-12 월 존재 여부를 계산한다. OHLCV·trade-count 열은 해석·출력·저장하지 않는다.
- 각 member는 2022-12-31 23:59:59 UTC 다음 첫 timestamp에서 읽기를 멈춘다. 2023년 이후 행은 읽지 않는다. 파일이 시간순이 아니거나 timestamp가 해석 불가하면 해당 member를 `invalid`로 처리한다.
- 개별 행·가격·거래량·거래 수를 보고서/CSV/로그에 저장하지 않는다. 결과물은 자산별 월 bitmask, 유효 pair alias, 연도별 12/12 여부, 합집합 개수만 기록한다.
- 모든 명령은 `TRADING_DATA_DIR=/Users/user/CODE/Coin_Trade/trading_data`를 명시하고, 데이터 외 출력은 저장소 안에만 둔다. `TRAIN_TRIALS.csv`는 열거나 검색하지 않는다.

## 사전 고정 판정

- Binance 단독 기준은 이미 기록된 20/29다.
- Kraken 월 완전 자산은 두 연도 각각 12개월 모두 timestamp가 하나 이상 존재하고, 정확한 ticker alias가 유효한 자산으로 센다.
- Binance·Kraken 합집합은 동일한 29개 자산 중 각 자산이 Binance 또는 Kraken 단일 venue 하나에서 양 연도 12/12를 충족하면 1개로 센다. venue의 가격을 이어붙이거나 혼합하지 않는다.
- 25/29 이상이면 `SOURCE_SCREEN_PASS`로만 판정하고, 별도 권리·PIT·캔들 품질·비용·전략 사전등록 게이트가 열리기 전까지 전략시험은 금지한다.
- 25/29 미만이면 `SOURCE_SCREEN_FAIL`; 기준을 낮추거나 분모·연도·quote·alias를 사후 변경하지 않는다.

## 검증·재현

- 스크립트가 입력 ZIP 경로를 canonical `TRADING_DATA_DIR` 하위로 정규화하고, ZIP 멤버 경로 및 출력 경로를 검사해야 실행한다.
- 실행은 저장소 내부 스크립트 파일을 새로 만들지 않는 단일 메모리 실행으로 한다. archive를 열기 전에 인메모리 합성 timestamp/pair/path assertions를 실행하고, 동일 실행의 terminal command와 출력 집계를 결과 보고서에 남긴다. 별도 합성 ZIP·산출 파일은 만들지 않는다.
- 재현 명령, 코드·사전등록 hash, 자산별 월 bitmask, 최종 numerator/denominator, 테스트 결과를 결과 보고서에 기록한다. 실행 실패나 누락은 성공으로 세지 않는다.

## 금지

- 가격·성과 백테스트, 전략 튜닝, OOS 선택, 공용 ledger 읽기/쓰기, 전체 아카이브 추출, 외부 통신·다운로드, 임의 코호트 변경, 원본 데이터 이동·삭제를 하지 않는다.
- 이 사전등록은 Binance/Kraken 현물 source-screen에만 적용되며 USDⓈ-M 선물 오더블록 G를 대체하지 않는다.
