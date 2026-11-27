# 사전등록 — Binance Spot 고정 코호트 대체 quote 원천 게이트

등록일: 2026-11-28 (Asia/Seoul)
상태: 공식 객체 메타데이터 조회 전 고정
작업 유형: 데이터 원천 적격성 진단이며 전략 수익 시험이 아님

## 질문과 범위

기존 고정 CMC 2018 상위 30 자산 코호트에서 BTC quote 한 종류만으로는 2018·2022 완전 월 key 기준 25/29를 확인하지 못했다. 동일한 자산 정체성과 연도 범위를 바꾸지 않고, Binance Spot의 사전 지정 quote 후보 중에서 각 자산별로 완전한 archive key가 있는 pair를 고르면 25/29 원천 게이트에 도달할 수 있는가?

이 조사는 기존 BTC-quote 사전등록의 실패를 수정하거나 소급 합격시키지 않는다. 결과는 별도 현물 데이터 후보이며 USD-M perpetual, 기존 오더블록 성과, 오더블록 G 판정을 대체하지 않는다.

## 사전 고정 입력

- 자산 분모: [`PREREG_BINANCE_SPOT_CMC201801_TOP30_BASEBTC_1H_OBJECT_MATRIX_20261127.md`](PREREG_BINANCE_SPOT_CMC201801_TOP30_BASEBTC_1H_OBJECT_MATRIX_20261127.md)에 고정된 CMC 2018 상위 30 snapshot. BTC는 benchmark, 나머지 29개가 분모다. `BCC` identity 미확정은 실패로 남기고 alias나 자산을 바꾸지 않는다. 기존에 승인된 `MIOTA→IOTA` 외 ticker 변경은 금지한다.
- 기간·주기: 2018년 1–12월과 2022년 1–12월, Binance Spot 월간 1h kline archive. 다른 연도·주기는 조회하지 않는다.
- quote 후보와 고정 선택 순서: `BTC`, `USDT`, `ETH`, `BNB`. 각 기초자산에 대해 이 순서를 따라 두 연도 모두 매월 ZIP 및 같은 key의 `.CHECKSUM` sidecar 이름이 모두 명시적으로 확인된 첫 quote 하나를 선택한다. 각 후보를 차례로 점검하되, `unverified`는 완전한 pair로 세지 않고 다음 사전 고정 quote를 확인한다. 더 낮은 순위의 quote가 완전해도 상위 후보의 미확인 상태는 별도로 보고한다. 네 후보 중 완전 pair가 없으면 그 자산은 통과하지 못한다.
- 동일 기초자산에서 여러 quote의 가격 또는 수익을 비교·선택하지 않는다. 가격·checksum 본문·가격행은 이 gate에서 읽지 않는다.
- 고정 문턱: identity-confirmed 29개 중 최소 25개가 두 해 모두 12/12월 ZIP과 checksum key를 가져야 한다. `BCC` 실패를 분모에서 빼지 않는다.

## 조회 방법과 안전 제한

- 공개 공식 Binance Vision archive에서 key-name metadata만 조회한다. 허용 정보는 HTTP 상태 또는 XML의 `Key`, `Size`, `LastModified`, pagination marker뿐이다.
- 각 요청은 위에 고정한 pair, 주기, 2018/2022 범위만 대상으로 한다. 공식 bucket의 기존 승인된 목록/정확 key metadata 방법 외에 다른 호스트·mirror·검색 endpoint를 즉흥적으로 시도하지 않는다.
- ZIP 또는 checksum 본문 GET, 가격 파일 다운로드, 거래 API·인증·계정·키 사용, post-cutoff 정보 조회는 금지한다.
- 모든 기록·캐시·로그·임시파일은 정규 저장소 내부만 허용하며, 데이터가 필요해지는 별도 단계는 `TRADING_DATA_DIR=/Users/user/CODE/Coin_Trade/trading_data`로만 고정한다. 본 metadata-only 단계에서는 로컬 데이터 파일을 새로 만들지 않는다.
- `TRAIN_TRIALS.csv`는 열거나 검색하거나 수정하지 않는다. 이 source gate는 전략 성과 trial이 아니다.

## 판정과 후속 게이트

- 25/29 이상이면 `SOURCE_METADATA_PASS`는 key-name 커버리지에 한해 판정한다. 가격행 존재·체결 가능성·연속성·PIT 상장 상태·delisting 처리·data rights·수익성은 증명되지 않는다.
- 완전 pair가 25/29 미만이면 `SOURCE_METADATA_FAIL`로 끝낸다. 정확히 확인되지 않은 후보는 `unverified`로 표시하고 문턱에 포함하지 않는다. 표본·분모·quote 순서·기간을 결과에 맞춰 바꾸지 않는다.
- metadata pass 이후에도 별도 전략 사전등록이 필요하다. 그 등록에서 quote별 가격을 BTC 단위로 변환하는 방법, cross-rate의 동시성, 수수료·슬리피지, 상장·상폐, delisted asset 결말, 고정 시간 분할, OOS, 2018·2022 BTC 상대성과, M2/EV/PF/Sharpe 및 강건성 검사를 가격행 접근 전에 정한다.
- 단일 CMC 코호트의 같은 전략 변형은 독립 후보 수로 중복 계산하지 않는다. 이 source gate 자체는 전략 후보 수를 증가시키지 않는다.

## 조회 경로 보충 v1.1 — 실제 object metadata 조회 전

최초의 metadata 요청은 `https://data.binance.vision/` 홈페이지를 반환했고, query string은 S3 key 목록으로 처리되지 않았다. 그 HTML의 공개 설정은 bucket endpoint를 `https://s3-ap-northeast-1.amazonaws.com/data.binance.vision`으로 명시한다. 따라서 아래의 경로만 추가로 고정한다: 이 공식 HTML이 가리킨 bucket endpoint에 `ListObjectsV2` 요청을 보내고, prefix를 정확히 `data/spot/monthly/klines/<PAIR>/1h/<PAIR>-1h-<2018|2022>-`로 제한한다. 리다이렉트는 따르지 않는다. 허용 응답은 해당 prefix 안의 XML `Key`, `Size`, `LastModified`, pagination marker뿐이다. endpoint가 XML 목록을 주지 않거나 응답을 해석할 수 없으면 해당 후보는 `unverified`다. 이 보충은 호스트 선택 근거와 조회 경로만 고정하며 자산·quote·기간·분모·통과 기준을 바꾸지 않는다.

이 보충 전에 홈페이지 route를 확인한 응답은 HTML 설정 확인에 그쳤고 object key·가격 파일·성과값을 반환하지 않았다. 원 prereg SHA-256은 보충 전 문서에만 해당하며, 실제 key query 전에는 보충 반영 후 새 문서 SHA-256을 고정한다.
