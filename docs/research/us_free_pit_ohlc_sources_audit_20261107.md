# 무료 미국 일봉 OHLC + 상장폐지 PIT 자료원 조사

- 조사일: 2026-11-07
- 범위: 공식 거래소·정부·학술 원자료 및 재현성 프로젝트의 공개 문서
- 기존 조사에서 제외된 OHLC.io, HistoricalData.net, Nasdaq Data Link WIKI 및 그 외 이미 열거된 상용/집계 API는 신규 후보로 재검토하지 않음.
- 금지 범위 준수: 데이터 파일/가격값 다운로드, API 키·계정 생성, 약관 수락, 서버 접속, 라이브 서비스 변경 없음.
- 통과 목표: 무료 접근, 미국 개별주 daily OHLC, 상장폐지 포함 PIT 유니버스/멤버십, 전체 구간에 적용 가능한 내부 전략 백테스트 권한이 문서로 명확해야 함.

## 결론

**이번 조사 범위에서 목표를 모두 충족하는 무료 자료원을 확인하지 못했다.** 가장 근접한 학술 공개 프로젝트인 HF Data Library는 무료·OHLCV·CC BY 4.0을 표방하지만, 이용약관은 학술·교육 연구만 허용하고 실거래용 전략의 구축·운영에 사용하지 않도록 명시한다. 더구나 원본은 IEX 단일 거래소 데이터이며 S&P500에 필요한 PIT 유니버스가 아니다. 정확도·권리·범위가 목표에 더 가까운 CRSP 및 NYSE TAQ 계열은 무료 공개 자료가 아니거나 일부 기관 구독자에게만 제한적으로 제공된다.

## 후보별 게이트

| 출처 | 무료/공개 접근 | OHLC·기간 | 상폐/PIT | 내부 백테스트 이용권 | 판정 |
|---|---|---|---|---|---|
| HF Data Library (IEX HIST 기반) | 문서는 무료라고 안내하지만 다운로드/API는 계정 필요. 계정 생성은 하지 않음 | 미국 주식·ETF 1분 OHLCV, 2022-03-07 이후. split 조정만; 배당/분사는 조정 제외 | 1,253개 고정 ticker, 현재 유니버스는 PIT가 아님. 일부 상폐 종목은 남지만 상장·상폐 시점별 자격 집합은 재구성되지 않음 | CC BY 4.0은 컴파일/문서 저작권 범위. 데이터는 IEX 약관에도 종속. 제공자 약관은 학술·교육 목적만 허용하며 실거래 전략 수립/운영에 이용하지 말라고 명시 | **불가**: 전시장 consolidated OHLC 아님, 기간 짧음, S&P 구성 PIT 없음, 내부 trading research 허용 불명확/제한 |
| CRSP US Stock Databases / CRSPMI | 제품 문서·방법론은 공개, 실제 자료는 라이선스 구독자 접근. 개인 무료 공개 저장소 아님 | CRSP는 일/월 시장 데이터와 기업행위, 수만 개 active/inactive 증권의 장기 기록을 표방. 데이터 항목에 가격·수익/상폐 정보 포함. S&P membership/index 상품은 별도 제품/접근 범위 확인 필요 | 생존편향 없는 역사 자료와 PERMNO/PERMCO 영구 식별자 제공을 표방. CRSPMI는 일별 지수 구성종목 개시/종료 membership/pro forma 기록을 제공한다고 공개문서에 설명 | 현재 공개 페이지는 기관 구독·라이선스·subscription 정보 요청을 요구. 과거 무상 제공 공지는 이미 CRSP 주요 데이터베이스 구독 기관에 한정됐고 기간도 종료됨 | **무료 게이트 탈락; 유료/기관 라이선스 대안**: 품질·PIT 측면의 가장 가까운 기준점이나 비용/권리 미확인 |
| Ken French Data Library | 연구 수익률·요인·정렬 포트폴리오 일부를 웹에서 파일로 제공 | 개별 종목 OHLC가 아닌 일별 요인/포트폴리오 수익률 | 포트폴리오 구성은 당시 데이터/CRSP 조건에 기반한 방법론을 설명하지만, 종목별 OHLC 또는 일별 S&P membership 파일 아님 | 사이트는 public research return 산출물 제공. 개별 OHLC를 제공하지 않으며, 이번 조사에서 trading research에 대한 별도 재사용 license 문구는 확인하지 않음 | **대상 아님**: 요인/포트폴리오 벤치마크 검증에만 유용 |
| NYSE Daily TAQ / TAQ Closing Prices | 공식 공개 페이지에 제품 설명 및 일부 샘플 링크 존재. 전체 이력은 구매/라이선스 | Daily TAQ는 1993년부터 consolidated tape 거래·호가의 역사 자료. 거래 기록에서 일봉을 파생할 수 있음. TAQ Closing Prices는 NYSE 계열 거래소 종목 OHLC/Last/volume를 제공한다고 명시되나 미국 전체 거래소가 아님 | 광범위 거래/마스터 파일을 제공하지만, 역사적 S&P 구성 membership 자체는 별도. 상폐 기업 식별·최종 정산에 대한 이번 문서 확인으로 충분치 않음 | NYSE는 학술기관에 할인 제공하지만 공인 기관의 독립 학술연구·교육 목적에 한함. 무료 일반 사용자 내부 백테스트 라이선스 확인 안 됨 | **무료 게이트 탈락**: 공개 샘플/문서가 전체 라이선스 데이터의 무료 배포를 뜻하지 않음 |
| Nasdaq 공개 Historical Data 페이지 | 웹에서 개별 종목 자료 조회 안내. 공개 페이지는 최대 10년 일별 가격·거래량이라 설명 | 공식 페이지는 일별 가격·거래량을 제공하지만 페이지 범위만 설명하며 전 시장 OHLC 파일/일괄 다운로드 계약은 확인 못함 | 현재 페이지 안내에는 delisted PIT universe/과거 S&P500 membership 제공 근거 없음 | 이용권 문서를 통해 자동 수집 및 전략 백테스트용 내부 보관 권리를 확정하지 못함. 유료 Nasdaq Data Link/market-data 제품과 별개로 취급해야 함 | **불가**: 웹 표시 자료와 라이선스가 명확한 PIT 벌크 OHLC 데이터는 다름 |
| SEC EDGAR API / bulk filings | 공공 API·bulk 공개, API 키 불필요 | 기업 제출 문서/XBRL 재무 정보 제공. 일별 거래소 OHLC는 포함되지 않음 | 회사/제출자 ID 및 공시 이력은 제공하지만 가격기반 유니버스/상폐 수익 시계열 아님 | 공공 공시 데이터 재사용은 가능하나, 필요한 가격 데이터가 없음 | **대상 아님**: 주가 자료원의 대체가 아니라 공시 기반 신호 보완용 |

## 근거 세부

### HF Data Library

- 프로젝트 방법론은 IEX HIST TOPS pcap을 1분 OHLCV로 파싱한다고 명시한다. IEX 거래소 단독 데이터이며 프로젝트 문서는 IEX 비중이 미국 consolidated volume의 약 2–3%라고 설명한다. 이는 미국 전체 체결가/거래량이 아니므로 전체 시장 전략의 실행가격·슬리피지 검증 자료로 대체할 수 없다.
- 범위는 약 1,253 ticker, 2022-03-07 이후, split만 가격조정, 배당·spin-off 미조정이다. 유니버스는 point-in-time이 아니다. ticker 목록은 고정되어 자동 상장/상폐 등록이 되지 않고, 상장폐지 종목도 일부만 남는다.
- Terms of Use의 목적 제한은 명확하다. 실제 자금으로 사용될 trading strategy/signal/algorithm/system을 구축·보정·운영하거나 매수·매도·보유·공매도 결정에 데이터를 신뢰하지 않겠다는 조건이 있다. “학술 연구용” 고지와 CC BY 4.0 표기만으로 이 제한을 무효화할 수 없다. underlying IEX terms도 함께 적용된다.
- 다운로드/API 사용 전 계정이 필요하다고 명시되어 있어 사용자 요청의 계정 생성 금지 조건상 자료 자체에 접근하지 않았다. 공개된 필드·방법론 메타데이터만 확인했다.

### CRSP / CRSPMI

- CRSP 공식 제품 문서는 수만 개 active/inactive 미국 종목, 일·월 가격과 기업행위, 영구 식별자, survivorship-bias-free history를 제공한다고 설명한다. CRSP 프로그래밍/데이터 사전 문서에는 delisting return 계산과 delisting information 필드가 정의되어 있어 상폐 처리도 연구용으로 구성되어 있다.
- CRSPMI 제품 문서는 2011년부터 당일까지 day-by-day index levels, opening/closing constituents, pro forma 데이터를 제공한다고 설명한다. S&P500 구성 membership가 데이터 상품에 포함되는지, 가입 요건과 정확한 entitlement는 제품·기관 계약 기준으로 별도 확인해야 한다.
- CRSP는 구독자에게 전달되는 데이터 제품이다. 2023년 공지의 임시 무상 조건은 이미 CRSP stock/index databases에 가입한 academic/government 기관에 한정되었으며 종료 시점이 명시되어 있었다. 따라서 지금 일반 개인이 무료 공개로 받을 수 있는 경로로 분류하지 않았다.

### Ken French Data Library

- 공식 Data Library는 CRSP CIZ를 사용해 미국 연구 수익률을 생성한다고 설명하고, 일별 Fama/French factors와 포트폴리오 자료를 파일로 제공한다. 파일은 요인 또는 정렬된 포트폴리오의 수익률이지 기업별 일별 OHLC가 아니다.
- 구성 절차의 일부는 월별/연도별 재구성과 CRSP 자격·가격·수익률 데이터 기준을 쓴다. 따라서 개별 종목전략이 소비할 체결 가능한 OHLC 가격 패널이나 역사적 S&P membership을 공급하지 않는다.

### NYSE / Nasdaq / SEC

- NYSE Daily TAQ는 CTA/UTP consolidated tape에서 미국 여러 거래소 종목 거래·호가를 포함한 역사자료를 1993년부터 제공한다고 설명한다. 전체 가격대장 상품은 구매 절차가 있고, academic 할인도 공인 기관의 독립 연구에 제한된다. 공식 페이지의 sample 링크는 테스트 샘플일 뿐 전체 데이터의 무상 라이선스 근거가 아니다.
- NYSE TAQ Closing Prices는 NYSE, NYSE American, Arca, National, Texas 계열 종목에 대해 open/high/low/last/volume을 안내한다. Nasdaq/타 거래소 전체를 포괄하지 않으며 product page에서 접근은 구매로 안내한다.
- Nasdaq의 공개 Historical Data 페이지는 종목별 최대 10년의 일별 가격·거래량 조회를 소개한다. 이는 역사적 S&P membership, delisted 전체 목록, PIT 보관권을 갖춘 벌크 OHLC 라이선스와 동일하지 않다. 자동화/재사용/내부 전략 연구 권한은 이번 공개 페이지에서 명확히 확인되지 않아 적격 판정하지 않았다.
- SEC EDGAR API는 제출 이력과 XBRL 재무정보를 API key 없이 제공하지만 일일 시세/거래소 OHLC 자료는 제공하지 않는다.

## 결정과 안전한 다음 경로

1. **무료 데이터로 목표를 그대로 유지하려면 현재는 DATA_BLOCKED다.** HF Data Library를 trading strategy research에 쓰는 것은 약관상 적절한 근거를 확보하지 못했고, OHLC 및 PIT 조건도 부족하다.
2. 당장 데이터 대안은 기관 라이선스가 이미 있는 경우 CRSP/WRDS/CRSPMI 접근권을 확인하는 것이다. 기관 구독을 보유하지 않았다면 CRSP/NYSE 유료 조건을 확인하기 전 비용·접근을 전제하지 않는다.
3. 무료 연구 대안을 찾더라도 외부 후보가 갖춰야 할 요건은 (a) S&P500 당시 constituents 및 effective date, (b) 상폐/회사행위 후 포지션 가치, (c) 기업별 매일 실행 가능한 OHLCV 또는 이를 무손실 재구성할 체결 자료, (d) 내부 research/backtest 보관·파생성과 이용 권리, (e) 파일 버전·취득일·해시 및 데이터 품질 검증이다.
4. SEC 공시는 가격 시계열이 아니며, Ken French 요인수익률은 개별 종목의 체결 성능검증 자료가 아니다. 둘을 OHLC 자료처럼 합산·대체하지 않는다.

## 출처

- HF Data Library 약관: https://hfdatalibrary.com/pages/terms
- HF Data Library 방법론·커버리지: https://hfdatalibrary.com/pages/docs
- HF Data Library 다운로드 및 접근요건: https://hfdatalibrary.com/pages/download
- CRSP US Stock 제품: https://www.crsp.org/research/crsp-us-stock-databases-2025-layout/
- CRSPMI 제품 자료(2025 제품 공지): https://www.crsp.org/wp-content/uploads/mdaz_202502.pdf
- CRSP 가격·수익·delisting 정의(CRSP/WRDS data descriptions): https://wrds-www.wharton.upenn.edu/documents/396/CRSP_US_Stock_Indices_Data_Descriptions.pdf
- CRSP 데이터 접근 및 라이선스 제품 정보: https://indexes.morningstar.com/research-data-products
- Ken French Data Library: https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html
- NYSE Daily TAQ 제품·구매 및 sample 링크: https://beta.nyse.com/data-products/catalog/daily-taq
- NYSE academic access 조건: https://beta.nyse.com/market-data/academics
- NYSE TAQ Closing Prices 제품 필드/범위: https://beta.nyse.com/data-products/catalog/taq-closing-prices
- Nasdaq public historical page: https://www.nasdaq.com/market-activity/quotes/historical
- SEC EDGAR APIs: https://www.sec.gov/search-filings/edgar-application-programming-interfaces

## 한계 및 프로토콜 기록

- 공개된 provider documentation와 product/terms pages만 읽었다. 파일 샘플, 가격 행, API 가격 응답은 다운로드하거나 조회하지 않았다. 계정/API key 생성, 로그인, 약관 수락, API 호출도 하지 않았다.
- 공급자가 설명한 데이터 품질을 실제 샘플이나 전체 패널로 검증하지 않았다. CRSP 데이터는 유료 권한을 보유한 상태를 가정하지 않았다.
- 이번 결과는 공개 문서상 무료 + 권한 명확 + PIT OHLC 적격 자료원이 발견되지 않았다는 조사 결과이지, 전 세계 모든 자료원이 존재하지 않는다는 증명은 아니다.
