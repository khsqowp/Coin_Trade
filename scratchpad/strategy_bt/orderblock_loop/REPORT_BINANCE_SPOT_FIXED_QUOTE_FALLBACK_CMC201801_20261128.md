# Binance Spot 고정 코호트 대체 quote 원천 게이트 결과 — 2026-11-28

## 판정

**실패: 20/29 자산에서만 두 해 전체 월 key가 확인됐다. 사전 고정 문턱 25/29에 미달하므로 가격 파일을 받거나 전략 백테스트를 시작하지 않았다.** 이 결과는 Binance Spot의 고정 CMC 2018 코호트에 한정되며 Binance USD-M 무기한 선물 결과를 대체하지 않는다.

## 고정 규칙과 결과

- 사전등록: [`PREREG_BINANCE_SPOT_FIXED_QUOTE_FALLBACK_CMC201801_20261128.md`](PREREG_BINANCE_SPOT_FIXED_QUOTE_FALLBACK_CMC201801_20261128.md), 최종 조회 전 SHA-256 `bcf0e23a7212232b81b45403b5cef5681bc09a213f42f1d5399e9d4e652a1a5c`.
- 고정 코호트는 CMC 2018 상위 30개이며 BTC benchmark를 제외한 29개 분모를 유지했다. Quote 순서는 BTC → USDT → ETH → BNB다. 2018·2022 각각 12개월 ZIP 및 `.CHECKSUM` key가 모두 명시 확인된 첫 quote만 해당 자산의 완전 자료로 셌다. `BCC`는 종목 정체성 미확정으로 계속 실패 처리했다.
- 기존 Binance BASEBTC 공식 HEAD 결과의 11개 완전 pair와 네 개의 명시적 실패를 재사용했다. 이전에 미조회였던 pair·quote만 새 ListObjectsV2 경로로 점검했다. 재시도와 리다이렉트는 없었다.
- 완전 자료가 확인된 20개: `XRPBTC`, `ETHBTC`, `ADABTC`, `LTCBTC`, `IOTABTC`, `XLMBTC`, `DASHBTC`, `XMRBTC`, `NEOBTC`, `EOSBTC`, `QTUMBTC`, `TRXBTC`, `ETCBTC`, `LSKBTC`, `ICXBTC`, `XVGETH`, `BTSBTC`, `OMGBTC`, `ZECBTC`, `WAVESBTC`.
- 고정 분모에서 20/29만 확인됐고, 25/29보다 5개 부족하다. `BCH`, `XEM`, `BTG`, `NANO`, `ARDR`, `STRAT`, `PPT`, `USDT`는 이번 조회에서 완전한 quote pair를 확인하지 못했다. `BCC`는 identity 미확정이다. 이 표현은 모든 가능한 거래쌍에 자료가 없다는 뜻이 아니라, 사전등록한 네 quote 순서에서 완전 자료를 확인하지 못했다는 뜻이다.

## 조회 방법과 예외

- Binance Vision 공식 홈페이지의 읽기 응답은 S3 key 목록 대신 정적 HTML을 반환했다. HTML이 공개한 bucket 주소를 그대로 사용해 고정 pair-year prefix만 ListObjectsV2로 조회했다. 2018·2022 prefix만 요청했으며 2026년 이후 key나 가격 데이터는 요청하지 않았다.
- 새 검사기 실행은 51회였고, 사전등록 전이 아닌 사전등록 완료 뒤 별도로 확인한 `TRXBTC` 2018·2022 prefix 2회를 합쳐 공식 S3 목록 요청은 총 53회다. 별도의 홈페이지 경로 확인 요청 1회가 있었다. 월 단위 key 이름 집계는 20/29다.
- **범위 예외:** S3 ListObjectsV2 응답에는 API가 `ETag` 필드를 함께 반환한다. 첫 수동 `TRXBTC` 2018 조회의 원 XML을 콘솔에서 확인해 그 필드가 노출됐다. ETag는 성과·커버리지 판정에 쓰지 않았고 보고서에 값도 보존하지 않았다. 검사기는 `<Key>`만 읽도록 구성했다. 가격 본문·checksum 본문·시장 행은 열지 않았다.
- 이 원천 게이트는 key 이름의 존재만 본다. 실제 ZIP 무결성, 봉 연속성, 상장 가능 시점, 상폐 잔고 처리, quote→BTC 환산 시계열, 거래비용, 데이터 장기 연구 이용권의 전체 적용은 입증하지 않는다. 특히 `XVGETH`를 BTC 기준 포트폴리오에 쓰려면 별도 고정된 ETH/BTC 환산 자료와 체결 규칙이 필요하다.

## 검증 및 재현 범위

- 검사기: [`probe_binance_spot_quote_metadata.py`](probe_binance_spot_quote_metadata.py), SHA-256 `5ff4fcae521fa952de6f59fa0c1b1587d6bb2a9f635e54b22fb473e1566f0a35`.
- 합성 테스트: 저장소의 Python 3.15.2 가상환경으로 `python -B -m unittest discover -s scratchpad/strategy_bt/orderblock_loop/tests -p 'test_probe_binance_spot_quote_metadata.py' -v` — **6/6 통과**. Python 3.9 기본 인터프리터는 기존 `research_paths.py`의 `str | None` 문법에서 테스트 수집 중 실패했으며, 이를 결과로 세지 않고 지정 가상환경에서 재실행했다.
- 테스트는 합성 XML에서 고정 기간, 12/12 ZIP·checksum, 부분연도, 잘린 응답, 잘못된 prefix 처리를 검사했다. 이는 파서 검사이지 시장 데이터나 수익전략 검증이 아니다.
- 실행 명령은 `TRADING_DATA_DIR=/Users/user/CODE/Coin_Trade/trading_data`를 사용했다. 가격 ZIP·checksum 다운로드 0건, 로컬 시장 행 열람 0건, `TRAIN_TRIALS.csv` 열람·수정 0건, 데이터·로그·임시파일 생성 0건이다.
- 현재 프로세스 목록은 샌드박스에서 `pgrep`가 `Cannot get process list`로 실패해 확인하지 못했다. 이 메타데이터 작업은 공유 장부와 시장 데이터에 쓰지 않았고, 완료된 실행은 해당 도구 세션에서 종료코드 0으로 확인했다.

## 다음 판정

Binance Spot의 고정 quote 후보 네 가지를 사용한 source gate는 탈락이다. 이 결과에 가격 데이터를 추가하거나 25/29 기준을 낮추지 않는다. 코인 오더블록 목표 후보 수는 변하지 않으며, 다음에는 기존 Gate·Kraken 등 각기 사전등록된 venue의 완전 코호트가 실제로 독립 결합 가능한지 metadata와 이용권만 대조한다. 결합 source gate가 25/29 미달이면 해당 현물 연구를 종료하고 다른 적격 데이터 경로를 찾는다.
