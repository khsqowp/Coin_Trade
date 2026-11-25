# Alpha Vantage 미국 주식 자료 경로 판정 — 2026-11-24

## 결론

Alpha Vantage는 문서상 미국 주식 상장·상폐 상태를 과거 날짜 기준으로 조회하고 25년 이상 OHLC 이력을 제공하지만, 프로젝트의 무료·비용 없는 연구 경로로 사용할 수 있다고 확인되지 않았다. 2018/2022 가격 전체 출력은 premium 기능이며, 이용약관은 투자 분석·연구·테스트를 상업적 사용 조건에 포함한다. 계정·키 신청, API 호출, 구매, 데이터 다운로드는 하지 않았다.

## 확인한 공식 문서

- `LISTING_STATUS`는 미국 주식·ETF의 active/delisted 목록을 역사상 특정 날짜 기준으로 돌려보내며, 2010-01-01 뒤 날짜를 지원한다고 문서화되어 있다. 이 호출에는 API key가 필요하다. 문서만으로 종목별 상장·상폐 이벤트 전체 이력, 해당 심볼의 과거 OHLC 보존, 최종 거래·정산가 완전성은 확인되지 않는다.
- `TIME_SERIES_DAILY`는 25년 이상 OHLCV를 제공한다고 설명하지만, `outputsize=full`은 premium key에서만 가능하다. 무료 계정은 100개 최신 데이터만 반환하는 `compact` 범위로 제한된다. 따라서 무료 계정만으로 2018/2022 전체 시계열을 얻을 수 있다고 볼 수 없다.
- 공식 지원 페이지는 대부분의 API를 무료로 하루 25회 요청할 수 있다고 하지만, 무료 키를 받으려면 API key 신청 절차가 필요하다. 이는 전체 과거 일봉의 무료 접근을 뜻하지 않는다.
- 공식 이용약관의 상업적 사용 기준은 개인적인 범위를 넘어서는 투자 분석, 연구, 시험, 모니터링을 열거한다. 본 과업은 전략 분석·백테스트 연구이므로, 별도 서면 조건 없이 개인 비상업 사용이라고 가정하지 않는다.

## 고정 게이트와의 대조

| 요건 | 문서상 상태 | 판정 |
|---|---|---|
| 2018·2022 전 종목 가격 이력 | 25년 이상 시계열 설명은 있으나 full 출력은 premium 전용 | 무료 경로로 미충족 |
| 날짜별 PIT active/delisted universe | 특정 날짜의 active/delisted 목록 기능은 존재 | 유용한 보조 기능이나 OHLC·기업행위와의 완전한 연결은 미확인 |
| 상폐 최종 가격·현금 정산 | API 설명에서 확인 안 됨 | 미충족 |
| 이용권의 연구 적합성 | 약관에 연구·테스트를 상업적 사용 기준으로 열거 | 명확한 허용 확인 안 됨 |
| 비용·인증 조건 | 키 신청 필수, 전체 과거 OHLC는 premium key | 현 비용 경계에서 사용하지 않음 |

이 경로는 추가 무료 가격·PIT 소스로 채택하지 않는다. 사전등록·실험·장부에는 반영하지 않았으며 미국 G 후보 수는 변하지 않는다.

## 공식 출처

- [Alpha Vantage API documentation](https://www.alphavantage.co/documentation/) — `TIME_SERIES_DAILY`, `LISTING_STATUS`, API key 및 outputsize 설명
- [Alpha Vantage Terms of Service](https://www.alphavantage.co/terms_of_service/) — personal/non-commercial 범위와 investment analysis/research/testing을 포함한 commercial-use 기준
- [Alpha Vantage free API key/support](https://www.alphavantage.co/support/api-key/) — 키 신청 및 무료 하루 25회 API 요청 안내

## 수행하지 않은 작업

API key 신청, 로그인·계정 생성, API 호출, 원시 가격 조회·다운로드, 데이터 로컬 저장, 전략 시험, 사전등록 변경, 공유 trial ledger 수정은 수행하지 않았다.
