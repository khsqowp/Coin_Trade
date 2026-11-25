# BitMEX 2018 자료 적격성 — 2026-11-24

## 판정

BitMEX 공식 공개자료만으로는 2018 코인 전략의 30종목·OHLC·mark·funding 게이트를 열 수 없다. Binance USD-M 2018 결손의 대체자료로 인정하지 않는다.

## 확인된 공식 정보

- BitMEX 공개 아카이브 검색 색인에서 `quote/`, `trade/`, `porl/` 최상위 분류가 보인다. 이것만으로 각 분류의 연도별 파일·종목 수·완전성은 증명되지 않는다. [공개 아카이브 목록](https://public.bitmex.com/?prefix=data%2Fquote%2F)
- BitMEX API 문서는 체결(`trade`) 및 최우선 매수·매도 시세(`quote`)를 설명한다. 체결 데이터로 OHLC를 재구성할 가능성은 있지만, quote는 mark 가격이 아니며 mark/funding 보관파일의 심볼·기간 일치가 확인되지 않았다. [Get Quotes API](https://docs.bitmex.com/api-explorer/get-quote.html), [공식 API 스키마](https://github.com/BitMEX/api-connectors/blob/master/swagger.json)
- 공개 목록만으로는 2018년 월별 perpetual 종목 수, 각 심볼의 연속성, 2022 범위, mark/funding의 동시 커버리지를 확인할 수 없다. 목록에서 항목이 안 보인다고 파일 부재로 단정하지도 않는다.
- 약관은 공개 데이터 열람 가능성을 설명하지만, 공개 열람이 개인 로컬 복사·백테스트·영구 저장을 허가한다는 증거는 아니다. 연구용 재사용 라이선스는 확인되지 않았다. [2025년 6월 BitMEX 약관](https://static.bitmex.com/documents/Terms_of_Service__June_2025.pdf), [BitMEX Publications 약관](https://assets.ctfassets.net/kp25gfur5p5i/2R8EK3v7h1pjZCkccXXyPq/60a91d232523f5cbd322bf60671f758c/Terms_of_Service__December_2024_.pdf)
- BitMEX 거래소는 2026-09-23 거래를 중단했다. 현재 홈페이지는 종료 안내로 이동하므로 아카이브의 현재 접근 가능성도 별도 확인이 필요하다. [BitMEX 공식 종료 안내](https://www.bitmex.com/)

## 구분

- **확인:** 자료 분류 `quote`, `trade`, `porl`; API의 공개 market-data 유형; 현재 거래 종료.
- **추정:** 체결에서 OHLC를 만들 수 있을 수 있다.
- **확인 안 됨:** 2018/2022 월별 30종목, 연속 OHLC, mark/funding 교차 커버리지, 저장·백테스트 재사용 권한.
- **작업 경계:** 파일 다운로드, API 호출, 계정 접근, 저장소·장부 변경 없이 공식 공개 문서와 검색 색인만 검토했다.
