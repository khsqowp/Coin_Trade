# 사전등록 — Binance 현물 BASEBTC 공식 목록 endpoint 확인 v2

등록 시각: 2026-11-28 (Asia/Seoul)
작업 유형: 성과를 보지 않는 공개 객체 이름 메타데이터 조사. 가격 데이터·전략 시험·장부 trial이 아니다.

## 목적과 고정 범위

기존 `PREREG_BINANCE_SPOT_CMC201801_TOP30_BASEBTC_1H_OBJECT_MATRIX_20261127.md`의 고정 29개 후보쌍에서 2018년·2022년 월별 `1h` ZIP 및 checksum key 이름을 공식 저장소 인덱스로 확인한다. 코호트, pair, quote, 월, 25/29 통과선, 해석 기준은 기존 사전등록 그대로 유지한다.

기존 사전등록의 `https://data.binance.vision/` 목록 질의는 XML이 아니라 Binance Data Collection HTML을 반환했다. 그 HTML 본문에 공개된 `BUCKET_URL` 값은 `https://s3-ap-northeast-1.amazonaws.com/data.binance.vision`이다. 이번 보충은 그 공식 페이지가 직접 노출한 주소만 목록 endpoint로 허용한다. 다른 host·region·mirror를 추측하거나 DNS/TLS 검증을 우회하지 않는다.

## 조회 절차와 사전 고정 판정

1. 먼저 고정 pair `XRPBTC`, 주기 `1h`, 연도 `2018` prefix 하나만 `ListObjectsV2`로 조회한다: `data/spot/monthly/klines/XRPBTC/1h/XRPBTC-1h-2018-`.
2. 정상 XML 목록이면 같은 endpoint·목록 방식으로 기존 사전등록의 고정 29 pair에 한정하여 2018·2022 연도 prefix를 조회한다. 각 pair-year의 12개월 ZIP key와 같은 경로의 `.zip.CHECKSUM` key를 별도로 센다.
3. 기존 고정 통과선인 identity-confirmed 29개 중 25개 이상이 두 해 각각 12/12 ZIP 및 checksum key를 갖는지 판정한다. unresolved BCC는 실패로 유지하고 자산을 대체하지 않는다.
4. HTTP 오류, DNS/TLS 실패, pagination 불완전, XML 파싱 오류, 또는 고정 prefix 밖 응답은 `unverified`로 남기고 해당 endpoint 조회를 종료한다. 오류를 객체 부재로 해석하지 않는다.

## 데이터·저장 경계

- 허용 응답 필드: `Key`, `Size`, `LastModified`, continuation token. 객체 본문, ZIP, checksum 본문, OHLCV 가격행은 요청하지 않는다.
- 로컬 파일·캐시·임시파일을 만들지 않는다. 명령 실행 시 작업 저장소는 `/Users/user/CODE/Coin_Trade`이며 `TRADING_DATA_DIR=/Users/user/CODE/Coin_Trade/trading_data`를 설정한다.
- `TRAIN_TRIALS.csv`를 읽거나 쓰지 않는다. 이 메타데이터 조회는 전략 trial 수·다중검정 분모에 포함하지 않는다.
- key 존재는 파일 무결성, 월내 연속성, 상장/PIT, 상폐 처리, 이용권, 비용, 체결 가능성 또는 수익성을 입증하지 않는다. 성공해도 별도 권리·품질 게이트와 신규 현물 전략 사전등록이 필요하다.

## 실패·완료 기준

- 완료: 고정 분모의 29개 pair-year key 상태와 25/29 기준의 충족 여부를 증거와 함께 별도 보고서에 기록한다.
- 미완료: endpoint가 오류를 반환하거나 목록 페이지를 끝까지 확인하지 못하면 `확인 안 됨`으로 종료한다. 다른 endpoint를 추측해 재시도하거나 데이터를 다운로드하지 않는다.

## 사전 조회 구문 정정 v2.1 — 2026-11-28

첫 메타데이터 요청은 위 디렉터리 안의 filename prefix를 빠뜨린 `.../1h/2018-`를 보냈고, `KeyCount=0`을 반환했다. 이 값은 객체 부재 증거로 사용하지 않는다. 기존 고정 파일명 규칙 `<PAIR>-1h-<YYYY>-<MM>.zip`에 맞춰 다음 요청 전에 prefix를 `.../1h/XRPBTC-1h-2018-`로 바로잡았다. pair·연도·통과 기준은 변경하지 않았다.

## 사전 범위 집행 사고 v2.2 — 잘못된 pair 집합 응답 무효화

수정 prefix의 단일 XRPBTC 확인 뒤, 집계용 임시 호출 목록이 기존 고정 CMC pair 표와 대조되지 않은 채 실행되어 사전등록 밖 pair 이름에 대해 2018·2022 목록 응답을 받았다. 그 응답과 숫자는 전부 무효이며 결과·coverage 판단에 사용하지 않는다. 이 파일에 고정된 CMC pair 목록 및 BTC benchmark만 다시 코드상 대조한 뒤 재조회한다. 이 사고 자체는 가격 데이터 취득이나 전략 trial이 아니다.

## 응답 표시 범위 정정 v2.3 — 단일 probe 출력 무효화

단일 XRPBTC probe는 curl 원문을 그대로 출력했고, S3가 허용 목록 외 XML 항목(ETag, StorageClass 포함)을 함께 반환하여 그 값들이 도구 출력에 노출됐다. 해당 probe 출력은 메타데이터 gate 판정 및 matrix 계산 근거에서 제외한다. 그 값은 별도 저장·분석하지 않았다. matrix 집계는 새 프로세스에서 사전등록 pair만 대상으로 ZIP key 이름의 연월과 checksum key의 존재만 세었으며, ETag·StorageClass 값은 출력하지 않았다. 이후의 동일 endpoint 조회는 추가하지 않는다.
