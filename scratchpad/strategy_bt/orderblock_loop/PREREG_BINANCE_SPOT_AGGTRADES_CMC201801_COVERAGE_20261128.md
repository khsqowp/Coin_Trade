# 사전등록: Binance Spot aggTrades 고정 코호트 원천 메타데이터 게이트

등록일: 2026-11-28 (Asia/Seoul)
상태: 실행 전 고정

## 목적과 가설 연결

독립 연구에서 제안된 “오더블록 첫 재방문에서 공격적 매도/매수 체결 불균형과 가격 회복이 함께 보이는 흡수 확인” 가설의 데이터 원천만 선별한다. Binance Spot aggTrades는 개별 체결 집계와 매수자 maker 여부를 제공하는 별도 데이터이며, Binance USDⓈ-M 선물 시장 데이터나 주문장 잔량과 동일하지 않다. 이번 메타데이터 통과는 전략 시험 승인 또는 후보 판정이 아니다.

## 고정 입력·유니버스·기간

- 유니버스: `PREREG_BINANCE_SPOT_CMC201801_TOP30_BASEBTC_1H_OBJECT_MATRIX_20261127.md`에 고정된 CMC 2018 상위 30개 중 BTC benchmark 제외 29자산. BTC는 기준자산, BCC는 정체성 미확정 실패, MIOTA→IOTA만 기존 고정 alias로 사용한다.
- 고정 quote 순서: `BTC → USDT → ETH → BNB`. 자산별로 이 순서상 첫 quote에서 2018·2022 양쪽 완전월이 있으면 선택한다. 선택 뒤 더 좋은 quote로 교체하지 않는다.
- 기간: 2018-01~2018-12, 2022-01~2022-12만. 2026-06-01 이후 어떤 데이터도 열지 않는다.
- 입력은 이미 저장된 `/Users/user/CODE/Coin_Trade/trading_data/external/crypto/binance/` 아래의 카탈로그·파일명 메타데이터에 한정한다. 입력 루트는 정확한 `TRADING_DATA_DIR=/Users/user/CODE/Coin_Trade/trading_data`로 검증한다.

## 읽기·기록 범위

- `spot/aggTrades`의 월별 파일 key 또는 파일명, 월, pair, byte size, checksum-sidecar 존재 표시만 확인한다. ZIP/CSV/parquet 내용, trade 행·가격·수량·시각·maker 방향, 결과 ledger는 열지 않는다.
- 네트워크, API 호출, 외부 다운로드, 계정·키, 압축 해제, 데이터 생성은 하지 않는다.
- pair별로 2018·2022 각각 12개월의 data object와 대응 checksum metadata가 모두 확인될 때만 완전월로 센다. 카탈로그/파일명의 범위가 불일치하거나 `unverified`면 실패 분모에 남긴다.
- 산출물은 pair별 quote 선택, 연도별 완전 월수, data/checksum key 수, 고정 분모 대비 합계만 기록한다. 원시 trade 필드와 CSV를 만들지 않는다.

## 사전 고정 판정

- `25/29` 이상이면 `SOURCE_SCREEN_PASS`로만 분류한다. 이후 별도 권리·출처시점·실제 ZIP 무결성·중복 trade·월 연속성·PIT·가격 정합성 검증 및 전략 사전등록 없이는 어떠한 전략 실행도 허용하지 않는다.
- `25/29` 미만이면 `SOURCE_SCREEN_FAIL`이며, 코호트·기간·quote 순서·문턱을 결과에 맞춰 바꾸지 않는다.
- Binance Vision 현행 약관은 개인 비상업 비생산 역사 백테스트를 명시하지만, 기존 파일은 취득시점·당시 약관·provenance를 별도 확인해야 한다. 공식 문서가 없는 부분은 미확인으로 남긴다.

## 재현·보호 규칙

- 조회 명령 전에 고정 입력/출력 및 Python/cache/temp 경로를 정적으로 검사하고 모든 실행에 정확한 `TRADING_DATA_DIR`를 지정한다.
- `TRAIN_TRIALS.csv` 및 기타 공유 ledger를 읽거나 쓰지 않는다. 진행 중 연구 writer/process를 추측 또는 중단하지 않는다.
- 이 검사는 현물 체결흐름의 원천 screen이며 선물 전략 데이터, 수익률, 통계유의성, 목표 선도달률, 독립 후보 개수를 검증하지 않는다.
