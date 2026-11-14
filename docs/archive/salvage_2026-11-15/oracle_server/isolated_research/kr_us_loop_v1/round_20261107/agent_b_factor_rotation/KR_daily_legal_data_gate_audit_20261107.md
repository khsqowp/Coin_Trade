# KR 주식·ETF 일봉 데이터 사용권 및 연구 적합성 감사

**작성:** Agent B, 독립 조사  
**기준일:** 2026-11-07  
**범위:** OpenDART·KRX·금융위원회 원본 API를 대체할 수 있는 공식 공급자/API의 약관·기능·PIT 적합성. 공개된 1차 출처만으로 판단했다. 계정 생성, API 키 발급, 데이터 다운로드, 데이터 값 열람, 백테스트는 하지 않았다.

## 결론

**무료·공개·자동수집 가능·파생 백테스트 허용·PIT/상폐/기업행위까지 충족하는 KR 전종목 일봉 소스는 확인하지 못했다.** 가장 현실적인 대체 데이터 경로는 EODHD의 유료 개인용 All World 계열이다. 공급자 약관은 본인만 사용하는 비상업적 퀀트 연구·백테스트·파생 결과 보관을 명시적으로 허용한다. 하지만 상장폐지 전체 커버리지와 과거 수정본/빈티지를 보장하지 않으므로, **라이선스 가능성은 높지만 이번 연구의 PIT 데이터 게이트는 아직 통과하지 못했다.**

## 게이트 결과

| 경로 | 수집·파생 백테스트 권리 | 커버리지·PIT·기업행위 | 판정 |
|---|---|---|---|
| **EODHD 개인용 유료 API** | 약관은 개인 비전문 사용자가 사적·비상업 목적으로 데이터를 저장·가공·분석하도록 허용한다. 공급자 FAQ는 본인만 쓰는 퀀트 연구, 백테스트, 자동 계산을 허용하고 파생 결과도 본인만 보관할 수 있다고 명시한다. 자동 API 수집/계획적 다운로드는 API 제한 준수 조건으로 허용된다. 무료 요금제는 하루 20호출·EOD 1년뿐이고, 전체 이력·상폐 티커는 유료 All World에 포함된다. | KRX·KOSDAQ(XKRX/XKOS) 거래소를 지원하고 EOD OHLC, ETF, 상폐 티커, split/dividend API를 제공한다고 문서화한다. 그러나 종목별 기록의 결측·마지막 거래일 누락·장기 지속성을 보장하지 않는다. 상폐 전 2018년은 EOD만 제공한다고 안내한다. OHLC는 원시 체결세션 가격, `adjusted_close`는 배당·분할 조정값이다. 과거 바·기업행위 수정은 언제든 덮어쓰며 변경 이력/과거 빈티지가 없다. 거래시간·휴장일 API는 Extended/All-In-One 플랜이다. | **유료로 개인 연구는 가능.** 다운로드 스냅샷을 보관하고 상폐·기간·기업행위를 실제 검증하기 전에는 PIT 게이트 실패. 자료가 정확한 체결가라는 보장도 아님. |
| **Twelve Data 개인용 API** | 개인 요금제는 개인/내부 비상업 사용, 데이터 처리 및 역산 불가능한 파생 데이터 생성을 허용한다. API 사용은 약관상 자동화된 플랫폼 사용에 포함된다. 다만 제3자 거래소 데이터는 별도 교환사 규칙·수수료·라이선스를 적용할 수 있다고 약관에 명시한다. 한국 시세를 무료 Basic에서 쓸 수 있다는 근거는 없다. Basic은 제한된 trial symbols이고, 유료 Grow/Pro/Ultra에서 국제시장 접근이 확대된다. | 한국 KOSDAQ(XKOS), KRX ETF가 공급자 카탈로그에 존재하고 일봉 OHLC·기업행위 API를 제공한다. 하지만 상폐 종목의 포괄 목록, 한국 과거 빈티지/수정 이력, 종목별 완전 기간, 가격 조정/분배금 회계가 PIT 요구를 충족한다는 1차 근거를 찾지 못했다. | **조건부 유료 후보.** 비상업 파생 분석은 허용되나, KRX 원천 데이터 권리와 한국 종목별 상폐·빈티지·가격 범위를 Twelve Data에 서면 확인하기 전에는 허용 데이터 소스/백테스트 입력으로 승인 불가. |
| **한국투자증권(KIS) Open API + 공식 백테스트 엔진** | 공급자는 시세를 계좌 보유 개인이 본인 자산의 투자 목적으로 쓰고 제3자 제공은 할 수 없다고 안내한다. 공식 Lean 기반 백테스트 엔진이 존재하므로 본인 전략 테스트는 공급자가 상정한 사용 사례로 볼 근거가 있다. 계좌와 API 서비스 신청 및 키가 필요하다. | API 문서에는 국내주식 기간별 시세(일/주/월/년)와 ETF 항목이 있다. 공개 문서만으로 전체 상폐 유니버스, 오래된 일봉 보유기간, 과거 수정가/기업행위의 시점별 스냅샷을 확인하지 못했다. | **본인 계좌 중심 제한적 연구 후보.** 법적 사용 목적은 비교적 명확하지만, PIT/상폐 전종목 연구를 대체하지 못한다. 계정·키 발급 및 실제 커버리지 확인은 이번 조사에서 하지 않았다. |
| **Stooq** | 공식 이용약관/다운로드 조건 페이지가 현재 JavaScript 검증 화면만 반환하여 자동 수집 및 2차 분석 허가 문구를 1차 출처로 확인할 수 없었다. 외부 2차 사이트는 개인 이용 한정·상업 이용 금지·재배포 금지를 인용하지만, 그 자체로 약관 증거로 채택하지 않았다. | 한국 전체 시장, 상폐, 기업행위 조정, 수정본 버전에 대한 공식 보장 문서를 확인하지 못했다. 최근 자동 다운로드가 CAPTCHA/차단에 걸린다는 2차 보고도 있으나 시도하지 않았다. | **허가 불명 + 커버리지 미입증. 제외.** 공개 다운로드 URL이 있다는 사실은 자동수집 권한이 아니다. |
| **Yahoo Finance / yfinance** | Yahoo 공식 약관은 명시적 사전 허가 없이 로봇·스크레이퍼 등 자동 수집을 금지한다. `yfinance`는 Yahoo가 승인한 공식 데이터 API/라이선스가 아니다. | 조정주가 및 기업행위 자료의 과거 재작성/빈티지 보장과 한국 상폐 종목 전체의 PIT 목록을 확인하지 못했다. | **자동 수집 권한 게이트 실패. 제외.** |
| **aikstockdata 및 공개 파생 데이터셋** | 자체 페이지가 원천을 금융위원회 공공데이터로 표기하고 공공누리 4유형(출처표시·비상업·변경금지) 및 제3자 재배포 제한을 승계한다고 명시한다. 파생 백테스트에 필요한 가격 변경·수익률 산출을 허용한다고 볼 수 없다. | 게시된 샘플은 2020년 이후 일별 가격 기록이며 ETF가 없다고 안내한다. 상폐 PIT 포함 및 기업행위/빈티지 보장은 확인되지 않았다. | **현재 요청 목적에는 부적합.** 원본보다 자동 수집이 편해도 원천 라이선스의 제한을 우회하지 못한다. |

## 데이터 게이트별 판정

1. **사용권·자동수집:** EODHD가 가장 명확한 후보지만 유료이며 개인 본인 연구 한정이다. 자료·키·결과를 다른 사람이나 조직에 제공할 수 없다. AI 에이전트/격리 서버가 대신 수집·연산하는 구조가 개인용 계약상 허용되는지는 공개 문서에서 명확히 정의되지 않아 실행 전에 공급자 확인이 필요하다. Twelve Data는 개인용 파생 분석을 허용하지만 한국 시장의 제3자 라이선스 요건은 별도 확인이 남는다.
2. **PIT 유니버스·상장폐지:** EODHD는 `delisted=1` 티커 목록 및 과거 가격을 제공하지만 “티커별 범위·결측·최종 거래일 불완전 가능, 완전성 보장 없음”을 명시한다. 현재 상장 종목과 현재 조회되는 상폐 종목 목록만으로 과거 시점의 모든 매매가능 종목·시장구분·상장/거래정지/상폐 상태를 재구성할 수 있다고 간주해서는 안 된다. 한국 과거 명칭변경 이력도 확인되지 않았다.
3. **기업행위·수정 이력:** EODHD의 원시 OHLC는 분할·배당 미조정이고 별도 조정종가 및 split/dividend API가 있다. 하지만 기업행위/과거 바 정정은 현행 값에 덮어쓰고 벤더는 `as-of` 스냅샷을 제공하지 않는다고 명시한다. 따라서 수집일자·원문 응답·해시를 저장해야 하며, 과거 신호 계산에는 해당 시점까지 알려졌던 기업행위만 적용해야 한다. 수집 전 보유하지 않은 빈티지는 복원할 수 없다.
4. **실행 가격·달력:** EOD 일봉 OHLC는 일별 시뮬레이션에서 다음 거래일 시가/종가의 가격 프록시로 사용할 수 있지만, 주문 체결 가능 가격이나 호가/체결 순서를 입증하지 않는다. 실제 체결비용·슬리피지·가격제한·거래정지·유동성 미체결을 포함해야 한다. EODHD 거래소 휴장일 API는 별도 상위 플랜에 있어, base EOD 플랜만으로 공식 KRX 세션 달력을 만족한다고 보지 않았다.

## 권고 진행 순서

1. **무료만 고수한다면 KR 전종목 PIT 백테스트는 보류**한다. 확인된 공공 무료 소스는 파생 금지/재배포 제한 또는 범위 부족에 걸린다.
2. **유료 1인 연구를 허용한다면 EODHD를 먼저 검토**한다. 결제 전에 KRX·KOSDAQ과 국내 ETF별 실제 기간/상폐 목록/종목코드 재사용/기업행위/거래달력 커버리지, 개인 서버·자동화 에이전트의 사용 가능 여부를 공급자에게 서면으로 확인한다. 월 결제 전에는 `demo`로 미국 샘플만 가능하므로 한국 시세 검증이 되지 않는 점과 무료 플랜 1년 한계를 고려한다.
3. 사용권 통과 후에도, 대상 유니버스의 상장일·상폐일·거래정지 상태를 날짜별로 검증하고, 상폐 표본과 배당·분할 사례를 원시 OHLC/기업행위와 교차 확인한다. 매일 스냅샷과 수집 타임스탬프·원본 해시를 보존한다.
4. 전체 종목·장기 PIT가 목표라면, **거래소 원천의 라이선스된 전문 데이터 계약 또는 과거 데이터 소유자가 보관한 스냅샷**이 현실적인 통과 경로다. 무료/스크래핑 경로로 조건을 약화하지 않는다.

## 공식 자료

- EODHD 개인용 사용권, 백테스트 및 파생 결과 보관: [Personal use and licensing](https://eodhd.com/help/personal-use), [Storage, retention and cancellation](https://eodhd.com/help/storage), [Terms and Conditions](https://eodhd.com/financial-apis/terms-conditions)
- EODHD 플랜/무료 한도/완전성 비보장: [Plans, Free Trial and Student Discount](https://eodhd.com/help/plans)
- EODHD 한국 거래소 지원, 상폐·기업행위·정정·빈티지 한계: [Supported exchanges](https://eodhd.com/list-of-stock-markets), [Data methodology](https://eodhd.com/help/methodology), [Delisted stock data](https://eodhd.com/financial-apis/delisted-stock-companies-data-2)
- Twelve Data 사용권/한국 시장/ETF·EOD 범위: [Terms](https://twelvedata.com/terms), [Commercial and personal usage](https://support.twelvedata.com/en/articles/5332349-commercial-and-personal-usage), [EOD market data](https://support.twelvedata.com/en/articles/12682324-end-of-day-eod-pricing-market-data), [KOSDAQ exchange page](https://twelvedata.com/exchanges/XKOS), [ETF coverage](https://twelvedata.com/etf), [Trial plans](https://support.twelvedata.com/en/articles/5335783-trial)
- KIS 개인 계좌·자산용 시세 범위와 공식 백테스트: [Open API service](https://apiportal.koreainvestment.com/about-open-api), [Backtest engine](https://apiportal.koreainvestment.com/toolkit-backtest), [API reference listing](https://apiportal.koreainvestment.com/apiservice)
- Yahoo 자동 수집 제한: [Yahoo Terms of Service](https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html)
- Stooq 공식 이용 페이지는 현재 브라우저 검증만 반환: [Terms](https://stooq.com/t/?i=1), [Historical downloads](https://stooq.com/db/h/). 약관 문구는 확인할 수 없어 허가를 추정하지 않았다.
- 비교용 공공데이터 제한(해당 원천은 요청에서 제외됐지만 오픈 데이터 대안으로 혼동하지 않도록 표기): [FSC Index Price Information](https://www.data.go.kr/en/data/15094807/openapi.do) — 지수만 제공, KOGL Type 4(비상업·변경금지), 무단 제3자 제공/재배포 금지.

**최종 상태:** 후보 탐색과 약관 감사만 완료. 데이터/API 호출 0, 가격 셀 열람 0, 데이터 파일 0, 백테스트 0, 외부 계정·키 동작 0, 라이브 거래 0.
