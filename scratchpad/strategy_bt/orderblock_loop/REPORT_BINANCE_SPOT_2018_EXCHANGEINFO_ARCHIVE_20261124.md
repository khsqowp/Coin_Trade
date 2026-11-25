# Binance Spot 2018 exchangeInfo 보존본 조사

확인일: 2026-11-24 KST
범위: Internet Archive CDX의 2017–2018 캡처 목록과 2018년 Binance 공식 API 응답 사본만 확인. 현재 Binance API, 시세·OHLC 데이터, post-cutoff 자료, 공유 장부는 조회하지 않았다.

## 확인 결과

Internet Archive CDX에서 `https://api.binance.com/api/v1/exchangeInfo`의 HTTP 200 JSON 캡처가 2018년에 2건 확인됐다.

| 캡처 시각 (UTC) | 보존 응답 바이트 | JSON 심볼 수 | 상태 |
|---|---:|---:|---|
| 2018-03-04 04:50:06 | 137,704 | 274 | 전부 `TRADING` |
| 2018-03-05 19:40:52 | 139,206 | 277 | 전부 `TRADING` |

두 원본 캡처는 `exchangeFilters`, `rateLimits`, `serverTime`, `symbols`, `timezone` 필드를 포함한 JSON으로 파싱됐다. HTTP 200 전체 응답 바이트를 메모리에서 파싱하고 시각·응답 크기·심볼 수·상태별 개수만 출력했다. JSON 본문과 전체 심볼 목록은 저장하지 않았다.

CDX 조회 범위는 `from=2017&to=2018`로 고정했고 2017–2018 이외 캡처는 요청하지 않았다. `api/v3/exchangeInfo`는 같은 기간 캡처가 0건이었다. CDX 메타데이터의 보존 digest는 3월 4일 `UWAH6UY4MF5WPJ5D37JRVMIMXGUQUDT4`, 3월 5일 `FJ6W3WVEIDGVFSC5ULNZCDTICTGYCQQP`다.

같은 기간 `www.binance.com`과 `data.binance.com`의 v1/v3 URL 변형도 CDX에서 조회했다. 네 변형 모두 HTTP 200 캡처 0건이었다. `api.binance.com/api/v1/exchangeInfo?` 변형은 위 3월 4일·5일 두 캡처만 반환했다. 이 bounded URL 점검에서 2018-01-01 스냅샷은 발견되지 않았다.

## 해석과 한계

- 이 보존본은 2018년 3월 초 Binance의 거래 가능한 Spot **pair** 목록 스냅샷이며, 2018-01-01 당시 목록이 아니다.
- 3월 4일과 5일 사이에 pair 수가 달라진다. 따라서 한 시점의 스냅샷을 연초 전체에 적용하면 미래정보·생존편향이 생길 수 있다.
- 보존본이 발견됐다고 Internet Archive의 전체 캡처가 완전하다는 뜻은 아니다. 2018년 1월 초 캡처와 연초 이후 모든 상장·상폐 이벤트의 완전성은 확인되지 않았다.
- Binance의 2018 회고 글은 연초 101개 코인과 245개 거래쌍이었다고 기록하지만, 이름 목록은 제공하지 않는다: https://www.binance.com/en/blog/all/286445971261435904
- Binance Public Data Issue #479에는 완전한 과거 Spot 심볼 manifest의 공식 존재 여부를 묻는 미해결 질문이 있다. 이 페이지에는 완전한 공식 답변이 없다: https://github.com/binance/binance-public-data/issues/479
- Binance API `exchangeInfo`는 현재 거래 규칙·심볼 정보를 제공하는 API로 문서화돼 있다. 이 보고서에서 사용한 2018 응답은 Internet Archive에 저장된 당시 응답 사본이다: https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md#exchange-information

따라서 이 경로는 역사적 Spot 유니버스를 일부 복원할 수 있는 실제 자료지만, 현재 고정된 연초 PIT 유니버스·2018 전체 기간·2022 동일 코호트 요건을 열지는 못한다. 전략 실험·코호트 선택·G 판정에 사용하지 않는다.

## 재현 가능한 보존 링크

- 2018-03-04 캡처: https://web.archive.org/web/20180304045006id_/https://api.binance.com/api/v1/exchangeInfo
- 2018-03-05 캡처: https://web.archive.org/web/20180305194052id_/https://api.binance.com/api/v1/exchangeInfo
- CDX 메타데이터 요청: https://web.archive.org/cdx/search/cdx?url=api.binance.com%2Fapi%2Fv1%2FexchangeInfo&output=json&filter=statuscode%3A200&from=2017&to=2018

다음으로 허용 가능한 복원은 2018-01-01 기준 전체 심볼 목록 또는 그 시점까지의 모든 공식 상장·상폐 이벤트를 과거 보존 자료로 교차검증하는 것이다. 그 자료의 완전성을 증명할 수 없으면 Spot 데이터 경로도 PIT/G 부적격으로 유지한다.
