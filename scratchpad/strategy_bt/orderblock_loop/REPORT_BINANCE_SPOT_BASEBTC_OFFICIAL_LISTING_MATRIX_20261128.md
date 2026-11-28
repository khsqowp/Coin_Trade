# Binance Spot BASEBTC 공식 1h 객체 목록 matrix — 2026-11-28

## 결론

고정된 CMC 2018 top-30 코호트의 BTC quote 29개 후보 중, 2018년과 2022년 모두 월별 12/12 ZIP 및 checksum key를 가진 pair는 **19/29**다. 사전등록 통과선 25/29에 미달하므로 이 경로는 연구 데이터 게이트를 통과하지 못했다. BTC/BTC benchmark key는 두 해 모두 0개이며 별도 행이다. 가격 파일을 내려받거나 OHLCV를 읽지 않았고, 전략 백테스트를 실행하지 않았다.

## 방법 및 범위

- 기준: `PREREG_BINANCE_SPOT_CMC201801_TOP30_BASEBTC_1H_OBJECT_MATRIX_20261127.md`와 endpoint 보충 `PREREG_BINANCE_SPOT_BASEBTC_OFFICIAL_LISTING_ENDPOINT_V2_20261128.md`.
- 공식 Binance Data Collection 페이지에 표시된 S3 bucket endpoint의 `ListObjectsV2` 응답만 사용했다.
- 고정 29 pair × 2018/2022와 BTC/BTC benchmark × 2018/2022의 총 60개 prefix를 조회했다. 목록 응답에서 key 이름만 집계했고 각 달에 ZIP 및 `.zip.CHECKSUM` key가 모두 존재할 때만 paired month로 셌다.
- 임시 집계 호출의 첫 목록은 사전등록 pair 집합과 다르게 구성되었다. 해당 60개 응답은 전부 무효화했고 본 보고서의 수치에 반영하지 않았다. 이 범위 오류는 endpoint 사전등록 보충 v2.2에 기록했다.
- 최초 XRPBTC prefix 누락으로 발생한 `KeyCount=0` 응답 또한 무효이며 부재 증거로 쓰지 않았다. 이후 올바른 filename prefix에서 XRPBTC 2018/2022 각각 12/12를 확인했다.
- endpoint 확인용 단일 XRPBTC probe는 S3 XML 원문을 도구 출력에 표시해 ETag·StorageClass 등 등록된 허용 목록 밖 항목을 노출했다. 해당 단일 probe는 본 판정에서 제외했고 그 값들은 저장·분석하지 않았다. matrix 집계 수치는 고정 pair에 대한 월별 ZIP key 및 checksum key 존재만으로 계산했다. 이 범위 정정은 endpoint 사전등록 보충 v2.3에 기록했다.

## Pair별 결과

`ZIP/checksum`은 각 해의 월별 key 개수이며, `paired`는 두 key가 모두 있는 월 개수다. `누락`은 paired month 기준이다.

| Pair | 2018 ZIP/checksum | 2018 paired / 누락월 | 2022 ZIP/checksum | 2022 paired / 누락월 | 두 해 12/12 |
|---|---:|---|---:|---|---|
| XRPBTC | 12/12 | 12 / - | 12/12 | 12 / - | 예 |
| ETHBTC | 12/12 | 12 / - | 12/12 | 12 / - | 예 |
| BCHBTC | 0/0 | 0 / 01-12 | 12/12 | 12 / - | 아니오 |
| ADABTC | 12/12 | 12 / - | 12/12 | 12 / - | 예 |
| LTCBTC | 12/12 | 12 / - | 12/12 | 12 / - | 예 |
| IOTABTC | 12/12 | 12 / - | 12/12 | 12 / - | 예 |
| XEMBTC | 10/10 | 10 / 01-02 | 11/11 | 11 / 12 | 아니오 |
| XLMBTC | 12/12 | 12 / - | 12/12 | 12 / - | 예 |
| DASHBTC | 12/12 | 12 / - | 12/12 | 12 / - | 예 |
| XMRBTC | 12/12 | 12 / - | 12/12 | 12 / - | 예 |
| NEOBTC | 12/12 | 12 / - | 12/12 | 12 / - | 예 |
| EOSBTC | 12/12 | 12 / - | 12/12 | 12 / - | 예 |
| BTGBTC | 12/12 | 12 / - | 10/10 | 10 / 11-12 | 아니오 |
| QTUMBTC | 12/12 | 12 / - | 12/12 | 12 / - | 예 |
| NANOBTC | 11/11 | 11 / 01 | 1/1 | 1 / 02-12 | 아니오 |
| TRXBTC | 12/12 | 12 / - | 12/12 | 12 / - | 예 |
| ETCBTC | 12/12 | 12 / - | 12/12 | 12 / - | 예 |
| LSKBTC | 12/12 | 12 / - | 12/12 | 12 / - | 예 |
| BCCBTC | 11/11 | 11 / 12 | 0/0 | 0 / 01-12 | 아니오; identity 미해결 |
| ICXBTC | 12/12 | 12 / - | 12/12 | 12 / - | 예 |
| XVGBTC | 12/12 | 12 / - | 6/6 | 6 / 07-12 | 아니오 |
| BTSBTC | 12/12 | 12 / - | 12/12 | 12 / - | 예 |
| OMGBTC | 12/12 | 12 / - | 12/12 | 12 / - | 예 |
| ZECBTC | 12/12 | 12 / - | 12/12 | 12 / - | 예 |
| ARDRBTC | 6/6 | 6 / 01-06 | 12/12 | 12 / - | 아니오 |
| STRATBTC | 12/12 | 12 / - | 0/0 | 0 / 01-12 | 아니오 |
| PPTBTC | 12/12 | 12 / - | 0/0 | 0 / 01-12 | 아니오 |
| USDTBTC | 0/0 | 0 / 01-12 | 0/0 | 0 / 01-12 | 아니오 |
| WAVESBTC | 12/12 | 12 / - | 12/12 | 12 / - | 예 |
| **BTC/BTC benchmark** | **0/0** | **0 / 01-12** | **0/0** | **0 / 01-12** | benchmark only |

## 판정 및 한계

- 29개 중 19개가 두 해 모두 object-key coverage를 충족한다. 고정 pass line 25개보다 6개 부족하다. BCC는 identity 미해결인 고정 실패로 유지했다. 자산·quote·기간 대체는 하지 않았다.
- key 존재는 ZIP 내부 봉의 연속성, 실제 거래 가능 시점, 상장폐지·정산 처리, 취득 당시 이용권, 전략 성과를 입증하지 않는다. 일부 월 누락의 이유도 이 key listing만으로는 알 수 없다.
- 이 표는 Binance 공개 아카이브의 key metadata 관측값이다. 파일 무결성은 checksum 본문을 검증해야 하지만 본 조사에서는 본문을 요청하지 않았다.
- 여기서 fail은 등록된 25/29 archive-coverage gate에 대한 판정이다. 이 결과만으로 다른 quote, 다른 거래소, 이미 보유한 데이터의 품질이나 별도 가설을 부정하지 않는다. 별도 코호트나 데이터 경로를 쓰려면 사전등록이 필요하다.

## 재현·검증 경계

실행은 저장소 cwd에서 `TRADING_DATA_DIR=/Users/user/CODE/Coin_Trade/trading_data` 환경변수를 설정한 Python urllib `ListObjectsV2` metadata 집계로 수행했다. 후보 29개와 benchmark만 대상으로, pair별 2018·2022 prefix를 조회했고 객체 본문은 열지 않았다. exact raw responses를 저장하지 않았으므로 이 요약은 실행 당시 도구 stdout과 고정 사전등록에 근거한다. 외부 재현은 같은 공식 endpoint에서 동일 prefix 목록을 재조회하면 된다.

전략 수익률, 비용 후 기대값, OOS, 승률/M2, PF, Sharpe, MDD, 다중검정 유의성: **미실행 / 확인 안 됨**.
