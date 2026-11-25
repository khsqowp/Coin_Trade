# 데이터 공급자 게이트 후속 조사 — 2026-11-24

## 판정

전략 후보는 여전히 **0/6**이다. 공개 문서 재조사로 일부 공급자의 기간·가격·이용 범위는 구체화됐지만, 코인 파생 2018년 고정 코호트, 한국 주식 PIT·상폐 정산, 미국 주식 전체 PIT·상폐 proceeds와 cutoff를 함께 입증하는 데이터 게이트는 어느 시장에서도 열리지 않았다. 이 문서는 공급자 탐색 결과만 기록하며 전략 시험이나 사전등록 변경을 뜻하지 않는다.

## 코인 오더블록: 공급자 기간이 2018 요구와 맞지 않음

- Tardis의 거래소별 과거 데이터 문서는 BitMEX·Deribit·OKX 자료 시작을 2019-03-30, Binance USDT 선물을 2019-11-17로 표시한다. 기록 채널 설명에 거래·파생 티커·펀딩 등의 자료가 있어도 이 시작일은 2018년 관측치를 만들지 못한다. [Tardis 거래소별 자료 범위](https://docs.tardis.dev/faq/general), [Tardis 과거 데이터 상세](https://docs.tardis.dev/historical-data-details)
- Kaiko 자료 사전은 perpetual funding 및 파생 가격 계열을 2020년 7월부터 제공한다고 설명한다. 더 오래된 현물 또는 일반 OHLCV가 있더라도 2018년 perpetual mark·funding을 보충하지 못한다. [Kaiko Data Dictionary](https://docs.kaiko.com/explore-our-data/data-dictionary)
- CryptoDataDownload은 공개 카탈로그에서 Binance USDS-M funding 시작을 2019-09-08로 표시한다. 공표한 라이선스가 있더라도 2018년 30개 이상 동일 파생 계약군의 OHLC·mark·funding을 채우지 못한다. [CryptoDataDownload 카탈로그](https://api.cryptodatadownload.com/), [자료 목록](https://www.cryptodatadownload.com/data/)

**결론:** 추가 공급자 경로도 고정 2018 파생 데이터 게이트를 충족하지 않는다. 서로 다른 거래소·현물 자료를 합쳐 동일 venue의 선물 코호트로 간주하지 않는다. 이 조사에서는 문서만 확인했고 파일 샘플, API, 데이터 행, 계정, 견적, 구매를 이용하지 않았다.

## 한국 주식: 유료 상품 경로는 있으나 사양·권리가 미확인

- KRX 구매 안내는 상품별 상세에서 제공 기간·필드·전달 방식·샘플·가격을 확인하고 구매 신청 후 이용 목적 심사를 받는 절차를 설명한다. 공개 목록만으로 특정 상품이 2018·2022 전체 상장·상폐 종목, 정리매매 가격, 합병·청산 최종 대가를 제공하는지 확인되지 않는다. [KRX 데이터 구매 안내](https://openapi.krx.co.kr/contents/OPP/DATA/OPPDATA001.jsp), [주식 상품 목록](https://data.krx.co.kr/contents/MDC/DATA/datasale/index.cmd?prodType=ST&viewNm=dataProdList)
- KRX OPEN API의 공개 이용약관은 비상업 목적만 허용하고, 제공된 정보를 제3자에게 넘기거나 계약 종료 후 계속 사용하는 것을 금지한다. API 이용기간은 인증키 발급 뒤 1년 단위이며 요청 한도는 키당 하루 10,000회다. 서비스 카탈로그는 주식 및 ETF 일별매매·종목기본정보를 2010-01-04부터 제공한다고 하지만, 개발구간 시작 2007-06-05보다 짧고 과거 상폐/정리매매/최종 대가 완전성도 확인되지 않았다. 상품 설명은 가격 필드를 약속하지만, 회원가입·인증키 신청·응답 확인은 하지 않았다. [KRX OPEN API 이용약관](https://openapi.krx.co.kr/contents/OPP/INFO/OPPINFO002.jsp), [서비스 목록](https://openapi.krx.co.kr/contents/OPP/INFO/service/OPPINFO004.cmd), [주식 일별매매정보](https://openapi.krx.co.kr/contents/OPP/USES/service/OPPUSES002_S2.cmd?BO_ID=JvJFzlAENzZlPBDNGAWC), [ETF 일별매매정보](https://openapi.krx.co.kr/contents/OPP/USES/service/OPPUSES003_S2.cmd?BO_ID=nrEpCLaZpoLCTzPUMxuF)

**결론:** 구매 가능성만 확인됐다. 가격·샘플·전체 기간·상폐 proceeds·장기 보관 및 내부 연구 권리가 확인되기 전까지 구매 적격 소스로 세지 않는다. 로그인, 문의, API 신청·호출, 구매는 하지 않았다.

## 미국 주식: 가격·PIT 부분 경로가 있으나 전체 G 불충족

- HistoricalData.net은 일봉 archive를 2003-10-01부터 2026-11-20까지로 표기하고, 현재 상품 페이지는 단독 사용자 가격을 USD 190 일회성으로 제시한다. 다만 종목별 파일의 첫·마지막 날짜는 서로 다르며, 공개 FAQ는 split/dividend를 설명하지만 merger·spin-off 등 모든 기업행사와 상폐 최종 proceeds를 입증하지 않는다. [HistoricalData 일봉 상품](https://historicaldata.net/stocks.html), [FAQ](https://historicaldata.net/faq.html)
- HistoricalData 공개 API 문서는 `/api/symbol/{symbol}`가 심볼별 일봉 파일의 날짜 경계와 종목 식별·상폐 메타데이터를 반환하며, 조회는 날짜 연속성을 검증하지 않는다고 명시한다. 최대 10개 심볼을 묶는 MCP 조회도 설명하지만, 실제 심볼 조회는 이번 조사에서 수행하지 않았다. 따라서 공급자 전체 통계나 샘플만으로 고정 코호트의 2018·2022 완전성을 추정하지 않는다. [Coverage API 문서](https://historicaldata.net/api.html)
- FirstRate Data는 2000년부터 S&P 500의 시점별 구성원·편입/편출·상폐 종목을 제공한다고 설명한다. 데모는 최근 약 1년으로 제한되고, 전체 이력 상품의 일회성 구매가격은 공개 페이지에서 확인되지 않았다. 이 조합도 S&P 500 바깥의 전체 미국 상장 종목 유니버스를 제공한다고 입증되지 않는다. [FirstRate S&P 500 구성원 데이터](https://firstratedata.com/fundamental-data/sp500-index-components/), [US Fundamentals 상품](https://firstratedata.com/fundamental-data/)

### 신규 유료 후보: MarketParquet

- 공식 상품 페이지는 미국 주식·ETF 일봉 전체 이력을 2000년부터, 약 16,000개 주식 중 8,500개 상폐 종목을 포함해 제공한다고 주장한다. 완전 아카이브 가격은 USD 79 일회성이고 구독이 아니며, 공개 라이선스는 개인 트레이딩·연구·단일 조직 내부 업무, 로컬 영구 보관 및 파생 통계/성과 공개를 허용하고 원자료 재배포를 금지한다. 사용자 개인 연구에 관한 공개 문구는 이전 가격 후보보다 명확하다. [요금·커버리지](https://marketparquet.com/pricing), [데이터 라이선스](https://marketparquet.com/ko/license)
- 데이터는 분할 조정 OHLCV이며 현금배당은 반영하지 않는다. 합병 및 대부분 spin-off는 별도 처리를 하지 않고 당시 거래가격으로 남긴다고 명시한다. 별도 기업행사 파일은 포함하지 않는다고 한다. 따라서 실제 정산·총수익 처리가 필요한 R4 교차자산 성과에는 빈칸이 남는다. [가격·방법론](https://marketparquet.com/ko/historical-market-data), [품질·기업행사 방법론](https://marketparquet.com/data-quality)
- 공급자는 일별 파일에 과거 해당 거래일의 거래 가능 심볼을 포함한다고 주장해 PIT 유니버스 대체 후보로 보인다. 그러나 R4 규칙은 가격 패널에서 유니버스를 유추하지 말고 별도 공식 PIT membership source를 요구한다. 공급자 파일/manifest와 가입기간·티커 변경 이력의 실제 행을 적법하게 확보해 별도 대사하기 전에는 이 주장으로 membership 게이트를 통과시킬 수 없다.
- 공급자의 공개 변경 기록은 2026-11-23에 2003–2020년 519개 ETF의 592 일별 종가(2,768행)를 바꿨고, 수백 개 종목의 split basis/이력도 여러 날짜에 걸쳐 수정했다고 적는다. 따라서 현재 버전의 과거 행은 cutoff 이후 기업행사·수정이 소급 반영된 값일 수 있다. 수정분 전체 manifest·as-of revision log가 없으면 2026-05-31 point-in-time 값/코드의 재현성은 증명되지 않는다. 가격이 분할 조정만이면 일반 백분율 수익은 보존될 수 있으나 절대 가격 기반 신호와 체결 레벨의 과거 재현성은 따로 검증해야 한다. [공급자 수정 내역](https://marketparquet.com/data-quality)
- 공급자는 정확성 보증을 제한하고, 공개 페이지는 원시 시세의 기관 공급원 이름, 고정된 과거 revision snapshot, 2018·2022 모든 종목의 연속성, 상폐 정산 대가를 입증하지 않는다. 따라서 이 자료는 미국 데이터 조달 후보로 추가되지만 현 상태에서 백테스트 입력 적격 또는 G 통과로 보지 않는다. 무료 샘플은 라이선스/자료 이용조건을 별도로 확인하지 않았고 이번 조사에서는 다운로드하지 않았다.

**결론:** 미국 일봉 가격의 유료 경로와 S&P 500 PIT 주장까지는 확인됐다. 그러나 고정 전체 PIT 유니버스, 2018·2022 종목별 가격 연속성, 최종 상폐/기업행사 proceeds, 2026-05-31 cutoff 강제, 전체 라이선스 비용은 확인되지 않았다. USD 190 상품이나 FirstRate 상품은 구매하지 않았다. 공급자에 연락하지 않았고 실제 가격 데이터·샘플을 받지 않았다.

## 다음 허용 단계와 완료 조건

1. 미답변 조달 승인 전에는 유료 자료를 사거나 공급자에게 연락하지 않는다. 미국 USD 190 승인만으로 별도 가격이 공개되지 않은 FirstRate나 KRX 구매까지 승인된 것으로 해석하지 않는다.
2. 공개 커버리지 메타데이터를 추가 조회할 수 있으면 대상 심볼 목록과 조회일, 응답 파일 식별자·날짜 경계를 보존한다. 날짜 경계는 연속성 증거로 과장하지 않는다.
3. 데이터가 적법하게 확보되더라도 immutable cutoff manifest, 권리·보관 조건, 고정 PIT 유니버스, 기업행사/상폐 총수익 처리, OHLCV 누락·중복·시간대 검증 전까지 실험을 시작하지 않는다.
4. R11은 48개 TRAIN만 완료됐고 고정 G 후보가 아니다. 현재 R11 보고서 표에는 0.25R EV 범위가 −36.00~−19.25bp로 수정되어 있고, 48개 전체의 M2 최고값은 74.06%로 80% 미달이다. 최신 사용자 인계는 48행 표 대사·CI 재계산, R11 단위 테스트 5+38=43 통과, 보고서 `git diff --no-index --check` 및 trailing-whitespace 검증 통과를 확인한다. 이번 조사에서는 이 테스트를 재실행하지 않았다. R12_BTC_DAILY_ALIGNMENT 초안은 사용자 최신 확인상 사전등록과 runner만 있으며 hash 미고정, 테스트·실행·장부 기록이 전혀 없다. 별도 `PREREG_R12_TECHNICAL_RETRY.md`, R12 테스트·runner·보고서 파일은 checkout에 존재하고 일부 완료·합성 테스트를 주장하지만, 이를 BTC_DAILY_ALIGNMENT 초안이나 실제 코호트 실행의 증거로 합치지 않는다. 사용자의 중단 지시에 따라 이 스레드에서는 R12를 실행하거나 장부를 확인하지 않는다. 공유 장부를 열지 않았고 현재 writer 상태도 이번 조사에서 조회하지 않았다. 이 보고서는 사용자 인계와 서로 다른 R12 파일군의 범위를 구분하며 R11/R12 코드·사전등록·공유 장부를 수정하지 않는다.

## 작업 범위

공급자·거래소 공식 문서와 공개 상품 설명을 확인했고, HistoricalData.net의 공개 `/api/catalog` 메타데이터 응답을 열람했다. 심볼별 coverage API, 가격·펀딩 데이터 API, 가격 행 조회나 파일 다운로드, 계정 로그인, 결제, 공급자 연락, shared ledger 읽기·쓰기, 사전등록 또는 코드 수정은 하지 않았다. 본 보고서는 공개 문서로 확인한 공급자 주장과 미확인 항목을 구분해 기록하며, 실제 파일 완전성이나 투자 성과를 증명하지 않는다.

## 추가 공급자 경로 재조사 — 같은 날 후속

### 코인 파생자료

- Kraken은 상장된 파생상품의 funding 자료를 각 거래쌍 개시 시점부터 CSV로 내보낸다고 설명한다. 다만 Kraken 자체 연혁은 선물 사업 진입을 2019년으로 표시하고, 2018년의 동일 venue 30개 perpetual 코호트나 상폐계약 이력을 보이지 않는다. 현재 지원 문서의 상폐표는 계약 정산가를 일부 제시하지만 완전한 과거 상장 명부가 아니다. [Kraken funding export](https://support.kraken.com/articles/export-historical-funding-rates), [Kraken 2019 파생상품 출시 안내](https://blog.kraken.com/product/kraken-derivatives/kraken-futures-is-a-new-way-to-trade), [상폐 계약 안내](https://support.kraken.com/articles/7526425887508-derivatives-contracts-trading-suspensions-delistings)
- Amberdata 검색 색인에 남은 Deribit 설명은 perpetual 자료 시작을 2018-08-13으로 주장하지만, 같은 페이지의 상세 역사자료 문구는 futures history를 2021-05-21부터라고 표시한다. 링크를 현재 열면 Amberdata 개별 페이지가 Kaiko 공통 제품 페이지로 리다이렉트되어 이 충돌을 현재 문서에서 재확인할 수 없다. 따라서 Amberdata의 2018 Deribit perp 시작일은 검증된 기록이 아니라 미해결 공급자 주장이다. [Amberdata Deribit 페이지 검색색인](https://www.amberdata.io/deribit-market-data)
- Amberdata 검색 색인의 Bybit 설명은 futures OHLCV·open interest를 2018-11-14부터라고 주장하지만 historical funding rates 절은 swaps funding 시작을 2021-09-24로 적는다. Bybit 자체 2018-12-01 출시 글은 BTC가 첫 perp 제품이었다고 명시한다. 따라서 Bybit는 2018년 funding 연속성도, 30계약 유니버스도 충족하지 못한다. Amberdata 페이지 링크는 현재 Kaiko 공통 페이지로 리다이렉트된다. [Amberdata Bybit 페이지 검색색인](https://www.amberdata.io/bybit-market-data), [Bybit 출시 안내](https://medium.com/bybit/a-cryptocurrency-trading-platform-built-for-fairness-and-transparency-2c9bc7f85549)
- CoinAPI 공식 FAQ는 funding 시작을 Binance·Deribit·Bitfinex 2021-01-01, Bybit 2021-01-04, Kraken Futures 2021-01-18, OKX 2022-03-23 등으로 열거한다. 해당 API는 지원 종료 심볼을 보유한다고 설명하지만, 이 funding 시작일은 2018 공백을 메우지 못한다. [CoinAPI historical data FAQ](https://www.coinapi.io/products/market-data-api/faq)

**판정:** Kraken의 2018 계약 수와 PIT/상폐 전체성이 부족하고, 다른 상용 공급자도 당시 30계약 동시 상장을 입증하지 못한다. 같은 venue·같은 30개 종목의 2018 OHLC/mark/funding 조건은 닫혀 있다.

### 한국 주식: 코스콤 DataMall

코스콤은 KRX 체결 정보를 분배하고 DATAMALL에서 주식 등 데이터 상품을 제공한다고 설명한다. 조사 agent가 확인한 공개 안내에는 KOSPI 일별정보 1975년, KOSDAQ 일별정보 1996년 시작이 표기되어 명목상 2007년 개발구간과 2018·2022 약세장을 포함한다. 이는 코스콤의 유통 경로이며 KRX와 독립된 가격 원천은 아니다. [코스콤 금융정보 서비스](https://www.koscom.co.kr/mobile/main/contents.do?menuNo=400044), [DataMall 소개](https://www.koscom.co.kr/portal/bbs/B0000037/view.do?menuNo=200433&nttId=714)

2026-11-24 공개 DataMall 화면에서 `국내주식 수정주가` 상세를 직접 확인했다. 상품은 기업조치(CA)를 반영해 상장일부터 당일까지 가격을 소급 조정하며, 범위는 “KRX 상장 전체 주식 종목”, 과거 시계열 제공 가능 시점은 2009년 3월, 갱신은 일별 익일 03:30, 전달은 FTP다. 공개 상세만으로는 상장폐지 종목이 현재 전체 상품에 남는지, 비상장 말기 정산·현금/주식 합병대가가 포함되는지, 과거 각 시점에 관측 가능했던 조정계수/종목목록, PIT 유니버스 재현 가능성, 가격·이용권을 확인할 수 없다. 현재까지의 공개 상세는 소급 수정 가격이므로 그대로 과거 시점 전략에 넣으면 미래 기업조치가 과거 값에 반영될 수 있다. 판매자가 PIT 처리와 권리를 문서로 확인하고 표본 파일로 검증하기 전까지 생존편향·미래수정 게이트는 닫힌다. 확인은 공개 페이지 읽기에 한정했고 로그인·문의·다운로드는 하지 않았다. [DataMall 국내주식 수정주가 상품](https://datamall.koscom.co.kr/kor/main.do)

추가로 KRX Data Marketplace 공개 화면에서 `상장폐지종목 시세 추이`는 종목명·조회기간 검색과 날짜, 종목코드, 종가·시가·고가·저가·거래량·거래대금·시가총액 열을, `상장폐지종목 현황`은 시장, 상장일, 폐지일, 폐지사유 등 종목 마스터 필드를 노출한다. 종목 검색창에도 “상장폐지종목 포함” 선택이 있다. KIND 상장폐지현황은 시장·회사·기간 조회와 Excel 버튼을 표시한다. 이로써 KRX 공식 공개 UI에 상폐 종목 가격/마스터 자료 경로가 있다는 점은 확인됐고, 한국 PIT 가격 게이트의 다음 구체 후보로 승격한다. 그러나 페이지 렌더링은 빈 결과 상태였으며 조회·다운로드하지 않았다. 따라서 시작일, 전기간 종목 수, 실제 일자별 연속성, 거래정지 구간, 대가/배당/합병 총수익, 보관·재사용 권리는 확인되지 않았다. 상장폐지 직전 마지막 매매일 정보는 최종 주주 회수금과 같지 않다. KRX 법적고지 링크는 현재 조사 환경에서 HTTP 403을 반환해 이용권 판단을 완료하지 못했다. [KRX 상장폐지종목 시세 추이](https://data.krx.co.kr/contents/MDC/STAT/issue/MDCSTAT239.jsp), [KRX 상장폐지종목 현황](https://data.krx.co.kr/contents/MDC/STAT/issue/MDCSTAT238.jsp), [KRX 종목 찾기(상폐 포함 선택)](https://data.krx.co.kr/comm/finder/finder_datastkisu.jsp), [KIND 상장폐지현황](https://kind.krx.co.kr/investwarn/delcompany.do?method=searchDelCompanyMain)

공공데이터포털의 금융위원회 주식발행정보는 무료 REST API이며 종목 상장·상장폐지일 및 발행 내역을 제공한다고 명시한다. 단, 이용조건은 공공누리 제2유형(출처표시·상업적 이용금지)이고 상업 활용은 원천기관 한국예탁결제원과 별도 계약이 필요하다고 고지한다. 이 API는 가격 이력이나 상폐 최종 대가가 아니며, 사용자 목적에 적용 가능한 권리도 확인되지 않았다. 이번 조사에서는 API 호출이나 키 사용을 하지 않았다. [금융위원회 주식발행정보 API 및 이용조건](https://www.data.go.kr/data/15043423/openapi.do)

KRX Data Marketplace 홈페이지 이용약관(2026-08-29 시행)은 자동화 수단으로 정보를 무단 수집·복제·배포하는 행위를 금지하고, 사전 허락 없는 정보 복사·복제·배포 등을 금지한다. 별도 마켓데이터 상품 이용약관도 적용된다고 명시한다. 그러므로 상장폐지 시세 페이지가 공개 조회/엑셀 UI를 노출한다는 사실만으로 로컬 장기 보관·재사용 권한을 추정하지 않는다. 본 조사에서는 자동수집·복사·다운로드를 하지 않았다. [KRX Data Marketplace 홈페이지 이용약관](https://data.krx.co.kr/contents/MDC/INFO/informationController/MDCINFO003.cmd)

검색 중 발견한 공개·연구 데이터셋도 현 사전등록 입력 대안이 되지 않는다. Zenodo의 한국 주식 연구 SAS 파일은 KOSPI/KOSDAQ 비금융 보통주 및 상폐 종목을 포함하고 2000-02~2022-06 기간이라고 설명하지만, 상세는 주식 초과수익 자료로 설명되어 OHLC·다음 시가 체결을 확인할 수 없고, Zenodo `Rights/License` 메타데이터는 비어 있다. 파일은 120.2MB로 표시되며 열거나 내려받지 않았다. [Zenodo 연구 데이터셋](https://zenodo.org/records/8395057)

Hugging Face의 `kospi-daily-stock-features-2021-2026`은 948종목, 1,214,339행, 2021-01-04~2026-05-29이며 OHLCV 필드를 설명한다. 그러나 2018 가격이 없고, 과거 PIT 전체 종목·상폐 포함을 입증하지 않으며, CC BY-NC 4.0과 “원천 가격 자료의 권리는 각 제공처에 남는다”는 안내가 있다. 2022 약세장 일부만 포함하는 데이터이고 G를 충족하지 않으므로 사용·다운로드하지 않았다. [Hugging Face 데이터 설명·라이선스](https://huggingface.co/datasets/podongchip/kospi-daily-stock-features-2021-2026)

한국주식데이터 공개 아카이브는 2020년부터의 일봉과 현재 2,787개 종목 파일을 설명하지만 “현재 수록 종목만 게시하고, 목록에서 빠진 상폐 종목 파일은 내린다”고 명시한다. 시세 원천의 이용조건도 공공누리 제4유형(비상업적 이용·변경금지)을 따른다고 적혀 있고, 2018 자료와 상폐 코호트가 없으므로 기존 사전등록에 부적격이다. [한국주식데이터 범위·이용조건](https://aikstockdata.com/downloads/history)

GitHub의 13개 시장 상폐 티커 목록은 한국 374개 회사와 대략적인 상폐 연도(1994–2018)를 담는다고 설명하지만, OHLCV·일자별 거래 가능 이력·현금/주식 정산가는 제공하지 않는다. 따라서 이는 이름 연결을 위한 보조 목록일 뿐 가격·PIT 데이터가 아니다. [상폐 ticker 목록과 한계](https://github.com/YLiu95/delisted-equity-data)

공개 설명은 상품별 OHLCV 필드와 상폐 종목 포함, 과거 PIT 구성, 합병·상폐 최종 proceeds, 표본 전체 연속성, 구매 후 장기 보관·개인 내부 연구 권리를 확정하지 않는다. DataMall은 견적/상품 스펙을 받아볼 구매 조사 대상으로 남지만, 별도 사용자 승인을 받기 전에는 문의·구매하지 않는다. **게이트는 미통과**다.

### 미국 주식: CRSP 및 새 유료 데이터 조합

- CRSP US Stock Databases는 32,000개 이상 활성·비활성 미국 증권에 대한 일별/월별 자료, OHLC·거래량·기업행사, 영구 PERMNO/PERMCO 식별자를 제공한다고 설명한다. 거래소 범위와 첫 자료일도 NYSE(1925-12-31), NYSE American(1962-07-02), NASDAQ(1972-12-14), NYSE Arca(2006-03-08), Cboe BZX(2012-01-24)로 명시한다. CRSP 가이드는 delisting return이 최종 현금/증권 분배 등으로 계산될 수 있다고 설명하는 동시에 -55/-66/-99 등의 미결·누락 코드를 명시한다. 가격과 기업행사 범위 면에서 이전 후보보다 강하지만 모든 상폐 proceeds 완전성을 보증한다고 해석할 수 없다. [CRSP US Stock Databases](https://www.crsp.org/research/crsp-us-stock-databases-2025-layout/), [CRSP 데이터 정의 및 delisting return 가이드](https://www.crsp.org/crsp_pdf/crsp-us-stock-indexes-databases-data-descriptions-guide-crspaccess/)
- CRSP 현 페이지는 구독 정보 요청을 안내하고 개인 가격표·구매가격·개인 연구자 적용 라이선스를 공개하지 않는다. 구매/접근 권한은 확인되지 않았다. 계약과 실제 데이터 품질 대사가 선행되어야 하며 CRSP가 자동으로 G 통과를 뜻하지 않는다.
- OHLC.io는 전체시장 일봉 및 과거 `as_of` 조회를 설명하지만, 공개 요금에서 Commercial은 월 USD 899, Scale은 월 USD 1,499이고 전체 이력이 두 플랜에만 포함된다. corporate actions 문서는 배당·분할·spin-off만 열거하며 합병 대가·파산 회수액은 없다. 공급자 문서는 security master가 2026년 9월 구축됐고 그 이전 상폐 회사(TWTR, SIVB 등)는 종목 resolve가 안 된다고 명시한다. `as_of`가 있어도 필요한 2018 상폐 유니버스가 없는 결함은 보완하지 못한다. 따라서 Full G는 입증되지 않았다. [요금 및 이용권](https://ohlc.io/pricing), [일봉·PIT 설명](https://ohlc.io/data/historical-stock-prices), [과거 ticker 조회 한계](https://ohlc.io/docs/dataset-coverage), [기업행사 범위](https://ohlc.io/docs/corporate-actions)
- Nasdaq Data Link의 SEP(1998년부터 상장·상폐 가격/기업행사/참조정보 주장)와 ZHDM(1987년부터 미국·캐나다 기업 및 상폐·심볼 변경 이력 주장)은 유료 Premium이다. 공개 페이지에서는 가격, 개인 연구 이용권, PIT membership 완전성, 상폐 최종 proceeds가 확정되지 않았다. [SEP 제품 문서](https://data.nasdaq.com/databases/SEP/documentation?anchor=sample-data), [ZHDM 제품 설명](https://data.nasdaq.com/databases/ZHDM)

**판정:** CRSP는 계약 가격·권리·완전성 확인을 진행할 가치가 있는 새 유료 후보지만 현 이용권 증거가 없다. OHLC.io와 Nasdaq Data Link 조합도 각각 과거 상폐/PIT/최종 proceeds의 공백이 남는다. 공개·무료 조합은 찾지 못했고 미국 G도 닫혀 있다.

## 추가 재조사 결론

코인·한국·미국에서 각각 유료/공식 부분 경로는 추가로 확인했지만, 어느 것도 구매 승인 및 계약 또는 데이터 행 대사 없이 실험 가능한 상태가 아니다. CRSP/코스콤은 완전성·범위 확인을 더 진행할 가치가 있는 구매 경로, MarketParquet은 공개 USD 79·명시적 내부 연구권이 있는 저비용 미국 가격 후보지만 기업행사·과거 수정 완전성이 미입증, HistoricalData.net은 단일 일봉 가격 상품, OHLC.io/Nasdaq Data Link는 미해결 기업행사·PIT가 있는 상용 조합으로 분류한다. 각 후보의 구매·이용 승인 여부는 별도다. 전략 후보 수는 계속 **0/6**이다.

## 코인 오더북 추가 공급 경로: Amberdata 페이지의 Kaiko 통합 후 사양

- Amberdata의 구 Binance 페이지는 현재 Kaiko의 Level 1/Level 2 제품 안내로 리다이렉트된다. 과거 Amberdata 검색 색인 문구는 Binance 현물 2017-08-17, 선물 2019-09-08부터라고 주장하며, 호가 스냅샷은 매분 전체 깊이, 호가 이벤트 데이터는 tick 단위라고 설명한다. 이 문구는 구 페이지의 색인 내용이고 현재 계약 또는 심볼별 보장을 뜻하지 않는다. [Amberdata Binance 페이지의 현재 리다이렉트](https://www.amberdata.io/binance-market-data)
- 현재 Kaiko 제품 안내는 Level 2 집계형을 월 USD 2,000부터, tick-level을 월 USD 2,500부터 표시한다. raw order book snapshot은 최소 분당 1회 스냅샷을 포함하고, 클라우드 CSV 이력은 2015년부터라고 하지만 거래소별 범위가 다르다고 명시한다. 반면 전체 bid/ask의 tick-level CSV 이력은 2023년 8월부터다. 따라서 이 자료만으로 Binance 2018/2022 특정 30개 무기한 계약의 스냅샷 연속성이나 전체 order-book event 재현을 입증할 수 없다. [Kaiko Level 1/2 사양·가격](https://www.kaiko.com/products/l1-l2-data)
- 이 후보는 1분 호가 스냅샷으로 일부 깊이·흡수 가설을 연구할 가능성은 있으나, R4의 고정 코호트, 동일 거래소·계약, 2018·2022 전체 기간, funding/mark/거래 자료 연결, 원자료 이용·보관 권리와 총비용은 미확인이다. 가격은 기존 USD 79 MarketParquet 문의와 별개의 월간 상품이며 구매·문의·가입·샘플 다운로드를 하지 않았다.

**판정:** 연구용 공급처 후보로만 기록한다. 2018년 full tick-level order-book 이력은 현 공개 사양상 입증되지 않았고, 분당 snapshot의 Binance별 기간·심볼·연속성도 확인되지 않아 데이터 gate는 닫힌 상태다.

## 저가 암호화폐 과거자료 후보: FinzData 공개 사양 불일치

- FinzData 상품 페이지는 Crypto Complete로 512 USD 페어, 상폐 72개, BTC 2013년·ETH 2016년 이후, 1분·5분·1시간·일봉 자료를 USD 79 일회성으로 제시한다. 약관은 개별 구매 자료를 개인 연구·매매에만 허용하고 raw 재배포를 금지하며, 조직을 위한 사용은 Institutional plan을 요구한다. 이 상품은 기존 MarketParquet USD 79 승인 질문과 다른 공급자·상품이며, 구매·계정 생성·문의는 하지 않았다. [상품과 가격](https://finzdata.com/shop), [FinzData 약관](https://finzdata.com/terms)
- 같은 공급자의 Crypto API 설명은 15개 USD 페어라고 쓰면서, FAQ에는 74개라고 적는다. 날짜 설명도 상품 페이지의 BTC 2013년과 API 페이지의 BTC 2015년이 다르다. 문서는 데이터를 "our vendor"에서 받는다고만 하며 거래소, 계약 종류, 상장폐지 가격 규칙, 원천 라이선스, 심볼별 2018·2022 전체 범위를 공개하지 않는다. [Crypto API 설명](https://finzdata.com/crypto-data-api)
- 공개 사양만으로는 현재 고정 코인 코호트 30개가 2018·2022에 동일 거래소/상품으로 거래됐는지 확인되지 않는다. 상품 설명은 USD 현물 페어로 보이며 무기한 계약의 mark/funding 또는 호가 깊이를 명시하지 않는다. 따라서 가격이 싸고 일부 범위가 맞아 보이더라도 기존 perp/orderbook 검증 경로를 대체하지 못하며, 적격 실험 데이터로 세지 않는다.
- 공급자 약관은 데이터 정확성·완전성 보증을 부인하고 "as is"로 제공한다고 명시한다. 열람 가능한 공개 샘플은 10행 설명뿐이고, coverage CSV 링크는 웹 수집기가 `text/csv` 형식을 처리하지 못해 조회되지 않았다. 원자료·샘플·coverage 파일은 받지 않았다. [약관의 정확성 조항](https://finzdata.com/terms), [무료 샘플 안내](https://finzdata.com/samples)

**판정:** 공개 상품과 개인 연구용 약관, 가격만 확인했다. 문서 내부 수량·시작일 불일치, 거래소·현물/선물 구분, 고정 코호트 범위, raw source rights와 데이터 품질이 미해결이므로 구매 전 추가 증거가 필요하다. 현재 코인 G 데이터 게이트는 닫힌 상태이며 이 상품 구매 권한은 부여되지 않았다.

## 미국 주식 전체 유니버스 후보: FinzData

- 공급자는 2000년 이후 NYSE·Nasdaq에서 거래된 16,000개 이상의 주식, 상폐종목 포함, 일봉과 여러 분봉을 제공한다고 주장한다. 무료 계정은 최근 12개월만 제공하고, 전체 시장 묶음은 5년 USD 195부터 시작하며 20년 USD 480 또는 30년 USD 670에 매일 갱신 옵션 USD 19.95/월이 표시된다. 20년 상품의 정확한 시작일과 결제·갱신 조건은 구매 전 확인이 필요하다. [주식 커버리지](https://finzdata.com/survivorship-free-stock-data), [요금표](https://finzdata.com/shop)
- 약관은 무료·Look-back 자료를 개인 한 명의 개인 연구·매매 용도로만 허용한다. 회사·펀드·고용주 업무는 Institutional 상품이 필요하다. 원자료 재배포 금지이며, 정확도·완전성·적시성은 보증하지 않는다고 명시한다. [FinzData 약관](https://finzdata.com/terms)
- 공급자 페이지의 PIT·상폐 포함 주장은 현재 공급자 설명일 뿐, 사전등록의 2018·2022 고정 코호트·거래 가능 시점, 종목별 가격 연속성, 상폐 최종 proceeds, point-in-time corporate action 처리, 원천별 entitlement를 입증하는 표본/manifest는 아직 없다. 기존 구매 후보보다 범위가 넓어 후속 검증 가치가 있지만, 현재 승격할 수 없다.
- 무료 데이터 범위는 최근 12개월이므로 2026-06-01 이전의 검증 표본을 대체하지 못한다. 계정·API key가 필요하며 이번 조사에서 이를 만들거나 요청하지 않았다. 전체 묶음 구매가 필요할 수 있어 사용자 승인 없이는 결제하지 않는다.

**판정:** 미국 주식 대체 조달 후보로 기록한다. 2000년 이후의 상폐 포함·전체 유니버스 주장은 현재 공개 설명만 확인됐고, 사용자 계약·데이터 샘플·고정 cohort 및 corporate-action 검증은 미완료다. 사용권의 범위와 월 갱신료를 포함한 총비용을 확인하기 전에는 실험을 시작하지 않는다.

## Kaiko 공개 문서 재확인 — Binance 2018/2022 코호트 미입증

- Kaiko Developer Hub 데이터 사전은 원시 호가 스냅샷 CSV가 하루 단위로 갱신되고 최소 분당 1회 스냅샷을 포함하며, 기록 시작점은 2015년이지만 거래소별로 다르다고 설명한다. 현물 및 파생상품 시장이 범위라고 명시하지만, 공개 문서에서 Binance 현물의 시작일, 2018년 개별 심볼 목록, 2022년 동일 심볼 목록, 날짜별 결측률은 확인되지 않았다. 이 설명은 상품 수준의 범위이지 R4 고정 코호트 충족 증거가 아니다. [Kaiko 데이터 사전](https://docs.kaiko.com/explore-our-data/data-dictionary)
- 같은 자료는 전체 bid/ask 수준의 tick 단위 CSV 이력이 2023년 8월부터라고 구분한다. 그러므로 2018년 OB 연구 후보가 될 수 있는 것은 분당 스냅샷으로 계산하는 깊이·불균형 계열뿐이며, 과거 전체 호가 이벤트를 재생하는 검증은 이 공개 사양으로 입증되지 않는다. [Kaiko 데이터 사전](https://docs.kaiko.com/explore-our-data/data-dictionary)
- Kaiko 문서의 REST 스냅샷 기반 일부 지표는 최근 1개월 rolling history로 표시된다. 이는 장기 이력의 대체 경로가 아니며, 별도의 클라우드 CSV 상품 설명과 구분해야 한다. 이번 조사에서는 API, cloud bucket, coverage explorer에 접속하지 않았고 심볼별 응답도 받지 않았다. [Kaiko 가격 슬리피지 예시](https://docs.kaiko.com/getting-started/kaiko-examples/compare-price-slippage-between-exchanges)

**판정:** Kaiko 분당 스냅샷은 추가 확인 가치가 있는 상품 경로지만, 공개 자료만으로 Binance 2018·2022 동일 30종목/계약 및 연속성이 증명되지 않는다. 이전 Kaiko 판정을 바꾸지 않으며 코인 오더북 데이터 gate는 닫혀 있다. 구매·문의·가입·다운로드·실험·공유 장부 접근은 하지 않았다.

## 한국 주식 추가 공급 경로 — Koscom DataMall 이용권 경계

- Koscom은 DataMall이 주식 일별 정보를 KOSPI 1975년부터, KOSDAQ 1996년부터 제공한다고 안내하고, 개별 주식·종목정보·자본금 변동 및 주요 종목조치 범주를 제시한다. 이는 후보의 기간 범위가 전략 기간을 덮을 수 있다는 상품 설명이며, 특정 ETF/주식의 실제 행·상폐 가격·최종 정산 또는 PIT 유니버스 완전성을 보장하지 않는다. [Koscom 금융정보 서비스](https://www.koscom.co.kr/mobile/main/contents.do?menuNo=400044)
- KRX 공식 수신방법 안내는 개인이 단순 참고 외 목적으로 시세정보를 사용하려면 별도 계약이 필요하다고 명시한다. Koscom FAQ는 정보이용료가 기본료와 변동료로 구성되며 유형별 가격 문의가 필요하다고 설명한다. 따라서 자동 백테스트·장기 로컬 보관 권리와 총비용은 공개된 제품 설명만으로 확인되지 않는다. [KRX 데이터 수신방법](https://openapi.krx.co.kr/contents/OPP/DATA/OPPDATA003.jsp), [Koscom FAQ](https://me.koscom.co.kr/portal/main/contents.do?menuNo=200643)
- Koscom 문서는 DataMall을 REST/open API와 별도 서비스로 구분한다. 데이터몰 소개에서 사용자가 Excel 자료를 저장할 수 있다고 한 사실은 계약 종료 후 계속 보관·재현할 권리를 증명하지 않는다. 이번 조사에서는 계정, 계약, 가격 문의, 데이터 접근을 하지 않았다. [Koscom OpenAPI FAQ](https://koscom.gitbook.io/open-api/faq/market), [DataMall 소개](https://www.koscom.co.kr/portal/bbs/B0000037/view.do?menuNo=200433&nttId=714)

**판정:** Koscom DataMall은 명목상 기간이 맞는 유료 후보지만, 현재는 개인 자동 연구 사용권·장기 보관·정확한 종목/상폐/정산 커버리지와 가격이 미확인이다. 한국 주식 데이터 gate는 닫힌 상태이며, 기존 사전등록 또는 시험은 실행하지 않았다.

## 보유 Binance 현물 1분봉 manifest 재집계 — 기존 코호트 부족 확인

- 저장소 밖 `trading_data/external/crypto/MANIFEST.csv`의 `binance/spot_klines_1m/<symbol>/<YYYY-MM>.parquet` 항목만 메타데이터로 묶었다. 2018년에는 일부 월 파일이 있는 심볼 8개, 12개월 모두 파일이 있는 심볼 4개(BNBUSDT, BTCUSDT, ETHUSDT, LTCUSDT)였다. 2022년에는 각각 25개와 23개였다.
- 이는 현물 OHLCV 월 파일 존재 수만 센 값이다. 분봉 내부 연속성, 소스 원본의 행 완전성, 당시 point-in-time 전체 유니버스, 미사용 심볼 기준, 오더북 데이터는 검증하지 않았다. 따라서 order-book 신호나 기존 파생상품 R4를 입증하지 않는다.
- 현물 데이터가 개인 연구용 백테스트에 사용 가능하다는 기존 카탈로그의 권리 설명을 전제로 하더라도, 2018·2022 각각의 30심볼 요건을 충족하지 않는다. 심볼 교집합·성능 집계·실험은 하지 않았다.

**판정:** 이미 보유한 Binance 현물 가격 자료만으로도 기존 30심볼 G를 채울 수 없다는 점을 현재 manifest 메타데이터가 재확인한다. 데이터 추가 조사 대상으로 남기되 실험 후보로 승격하지 않는다.

## 이미 보유한 equity manifest의 현재 범위 대조

- 저장소 밖 `/Users/user/CODE/trading_data/external/equities/MANIFEST.csv`를 메타데이터로 확인했다. 미국 Yahoo 일봉 패널은 10,885,803행으로 표시되지만 출처는 Yahoo Finance이며 기존 카탈로그가 생존 종목 중심이라고 경고한다. 개별 일자/심볼 행은 열지 않았다. 현재 미국 S&P500 membership 파일은 커뮤니티 저장소 `fja05680/sp500` 출처, 2,595행, 1996-01-02~2019-01-11로 기재되어 있어 2022 point-in-time membership를 제공하지 않는다.
- 같은 manifest에서 한국 상폐 일봉은 Naver fchart 조정 가격, 2,345,921행, 1996-01-30~2026-11-19로 표시된다. 기존 데이터 카탈로그는 KIND 상폐 목록 4,229개 중 가격이 반환된 코드를 1,190개로 기록한다. 이는 부분 생존편향 보완 자료이며 누락된 나머지 종목의 가격·정산을 대체하지 않는다.
- 이 manifest 확인은 파일 경로·행 수·출처·기간·해시 메타데이터만 사용했다. 가격행, 2026-06-01 이후 시세값, 공유 trial ledger는 열지 않았다. 현재 보유자료만으로 미국 2022 PIT universe와 한국 전체 상폐/최종 정산 G를 열 수 없다는 이전 판정이 유지된다.

**판정:** 로컬 equity 파일은 전략 탐색에 쓸 수 있는 일부 입력을 보유하지만, 해당 소스 권리·시점별 유니버스·상폐 최종 총수익 처리가 고정 G에 충분하지 않다. 이 상태로 백테스트를 수행해 후보를 뽑으면 사전등록 기준 위반이므로 실행하지 않는다.

## 보유 3시장 manifest 재대조 — 추가 비용 없는 실험 게이트 닫힘

- 코인: 보유 Binance UM 선물 가격·mark·premium·funding manifest는 2020-01 이후, 35심볼로 기록되어 2018 구간이 없다. 보유 `um_bookDepth`는 2023-01 이후 BTC·ETH 2심볼의 일별 자료다. 따라서 2022 일부 구간이 있더라도 2018 동일 venue perpetual cohort, 최소 30개 계약, 역사적 오더북 요건을 충족하지 않는다. spot OHLCV의 2018/2022 심볼 수는 앞 절의 4/23 완전연도 결과 그대로다.
- 국장: 보유 KIS 파일 92개라는 기존 읽기 전용 감사와 Naver/FDR 기반 외부 자료의 manifest만으로는 공식 데이터 권리, 정확한 일별 PIT 상태, 전체 상폐 OHLCV 및 terminal proceeds를 확인할 수 없다. 1,190/4,229 상폐 코드 가격 보유는 부분 범위다. KOSPI200 TR ETF 경로는 선택 심볼의 전체 수익 성격과 장기 연구권이 확인되지 않았다.
- 미장: 보유 Yahoo 일봉 가격은 10,885,803행으로 기록되어 있지만 Yahoo 생존 종목 패널이고, S&P 구성 이력은 1996-01-02~2019-01-11까지다. cutoff 이후 행을 포함한 원 파일에서 cutoff 이전만 분리한 검증본도 이번 조회로 만들지 않았다. SEC·FINRA 보유 자료는 가격·완전 PIT 유니버스·상폐 최종 정산을 대신하지 않는다.
- Binance Vision 공개 약관은 무료 이용·비상업적 개인의 비프로덕션 과거 알고리즘 백테스트 허용 범위를 설명하지만, 이는 보유 현물/파생 manifest의 기간·코호트 결손을 보완하지 않는다. Yahoo/FDR/Naver는 카탈로그상 개인 이용 주장이 있어도 현 작업에서 요구되는 대량 보관·자동 백테스트 권리와 데이터 무결성 근거가 확정되지 않았다. [Binance Public Data 이용조건](https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md)
- 이번 대조는 저장소 카탈로그, `MANIFEST.csv`/`MISC_MANIFEST.csv` 메타데이터 및 파일명·범위만을 대상으로 했다. 원시 가격행·공유 장부·사전등록·R12 데이터·cutoff 이후 가격값은 읽지 않았으며, 어떤 데이터도 실행에 투입하지 않았다.

**판정:** 이미 보유한 경로 가운데 추가 비용 없이 기존 고정 G의 완전한 데이터 게이트를 여는 시장은 없다. 이는 영구적인 전략 불가능 판정이 아니라, 현재 보유자료로 검증 후보를 만들면 기준을 위반한다는 판정이다. 다음 적격 행동은 새 유료/키 경로가 승인·확보되거나, 사용자 제공 권리 증거와 cutoff-bounded 적격 데이터가 생긴 뒤 그 범위만 검증하는 것이다. G 기준 자체는 변경하지 않는다.

## 범위 사고 — Binance Spot 최신 디렉터리 목록 조회

- 이번 이어서 조사에서 S3의 `data/spot/monthly/klines/` 루트에 `ListObjectsV2` 요청(`delimiter=/`, `max-keys=1000`)을 보내고 live `CommonPrefixes` 응답 일부를 받았다. 이는 과거 연도 전용 prefix가 아니며 2026-06-01 이후 상장된 거래쌍 이름이 섞일 수 있는 현재 디렉터리 목록이다.
- 파일·가격 행은 다운로드하거나 열지 않았지만, 응답 자체가 cutoff 경계를 보장하지 않는다. 따라서 이 응답의 심볼, 수량, 정렬, 범위는 폐기하며 코호트·전략·G 판정에 사용하지 않는다. 앞선 2018·2022 연도별 BTC prefix 조회는 역사 날짜 prefix로 한정됐던 별도 감사의 증거이며 이번 live root 응답과 혼합하지 않는다.
- live S3 목록을 다시 요청하지 않는다. 이후 S3 조회는 이미 고정된 cutoff 이전 심볼 집합에 대한 특정 과거 연도/월 prefix만 허용하고, 역사 시점의 전체 유니버스를 입증하지 못하는 경우 그 자료는 여전히 불충분으로 처리한다.

**격리 판정:** 이번 응답은 데이터 범위 사고로 분류해 격리했다. 이후 보고된 결과에는 해당 live 응답에서 얻은 어떤 심볼 정보나 집계도 포함하지 않는다.

## Binance Spot PIT 보완 공급 경로 — Angolin 문서 검토

- Binance Public Data의 공식 GitHub 이슈 #479는 2019-09-02 시점의 과거 spot USDT 전체 심볼 manifest와 공식 dated manifest/상태변경 로그가 존재하는지 질문한다. 2026-11-24에 추가된 후속 질문까지 이슈가 `Open`으로 남아 있고 이슈 화면에 Binance maintainer의 답변은 표시되지 않는다. 이는 공개 공식 보관소에서 완전한 과거 PIT manifest를 찾지 못한 기존 판정을 보강한다. [Binance Public Data issue #479](https://github.com/binance/binance-public-data/issues/479)
- Angolin 문서는 Binance Spot 약 3,600 pair에 대해 1분·1시간·일봉 OHLCV, 상폐 pair 전체 가격 이력, quote별 과거 listing period를 제공한다고 주장한다. 과거 유니버스는 2026-10-27 이전에 직접 매시간 관측된 기록이 아니라, 시간봉 존재, Binance listing/delisting 공지, Internet Archive의 과거 exchangeInfo snapshot으로 재구성했다고 밝힌다. 공급자 비교상 snapshot과 99.97% 일치한다는 수치도 제공자 자체 설명이며, archive 공백이 남을 수 있다고 함께 명시한다. 이 자료는 실제 원장 또는 공식 완전한 기록과 동등하다고 간주할 수 없다. [Angolin Binance coverage/methodology](https://angolin.com/docs/exchanges/binance)
- Angolin의 `exchange_universe`는 `listed_from`/`listed_until` 기준 시점별 유니버스를 반환하지만 API key와 활성 구독이 필요하며, `start` 이력 깊이는 요금제에 좌우된다. 공개 가격표나 개인 연구·장기 저장 권한의 구체 조항은 이번 공식 문서 검토에서 찾지 못했다. 따라서 이는 지금 실행할 수 있는 무료 보유 경로가 아니라, 가격·권리·계약 확인이 필요한 잠재 조달 후보로 분류한다. [Universe endpoint](https://angolin.com/docs/endpoints/exchange-universe), [Authentication](https://angolin.com/docs/authentication)
- Angolin 공개 문서는 Binance Spot OHLCV와 유니버스만 설명하고 L2 order-book depth/snapshot을 제공한다고 하지 않는다. 따라서 캔들에서 계산하는 별도 Spot 오더블록 연구를 지원할 수 있는지의 조달 후보일 뿐, 2018년 Binance perpetual/실제 호가장부를 요구하는 현재 R4를 대체하지 않는다.
- live Angolin catalog endpoint는 앞선 cutoff 사고 기록의 격리 조치에 따라 재호출하지 않았다. 현재 이 절의 근거는 고정 문서만이며 계정·구독·API key·가격행 다운로드·공급자 연락·시험은 하지 않았다.

**판정:** Angolin은 상장폐지 종목과 PIT pair 기간을 함께 다루는 가장 구체적인 Spot challenger 후보로 좁혀졌지만, reconstructive coverage의 정확도·문서상 gap, API 구독 비용, 사용권, OHLCV 실제 연속성과 주문장 부재 때문에 아직 data gate는 닫혀 있다. 구매·계약 전에 먼저 문서상 요금과 연구·보관 권리를 확인해야 하며, 별도 Spot 사전등록 없이 현 파생상품 R4에 섞지 않는다.

## 고정 Binance USDⓈ-M 오더블록 G의 구조적 연도 결손

- Binance의 공식 첫해 회고는 첫 USDⓈ-M BTCUSDT perpetual futures가 2019-09-09에 시작됐다고 기록한다. 따라서 현재 고정 G가 요구하는 **2018년 USDⓈ-M perpetual** 가격·mark·funding 코호트는 이 거래소 상품에서 존재할 수 없다. Spot OHLC나 다른 거래소 계약으로 2018년을 채우면 사전등록된 instrument/venue와 달라진다. [Binance Futures 첫해 회고](https://www.binance.com/en/blog/all/421499824684900979)
- Binance Public Data 담당자는 공개 futures L2가 2023-05-28 이전에 API/WebSocket으로 재구성됐고 “일부 gaps”가 있었으며, 그 날짜 이후 내부 로그로 바꾸어 gap-free 보장을 한다고 이슈 답변에 적었다. 이는 2018년 L2의 완전한 orderbook 재생을 뒷받침하지 않고, 2023-05-28 이전 구간도 별도 결손 감사가 필요함을 뜻한다. [Binance Public Data issue #268](https://github.com/binance/binance-public-data/issues/268)

**판정:** 고정 venue·instrument·2018 조건을 그대로 두면 이 경로로 crypto 오더블록 G를 통과할 수 없다. Spot·타 거래소 혼합이나 2018 가격 합성은 허용 가능한 데이터 보완이 아니다. 다음에 가능한 일은 원래 전략 가설을 줄이는 것이 아니라, 권한자가 venue/instrument/time 범위를 새 사전등록으로 재정의하는 경우에만 별도 연구를 시작하는 것이다. 현재 R4 기준을 이 보고서에서 바꾸거나 실행하지 않았다.

### 대체 venue 교차확인과 Spot 분리 대안

- OKX 공식 공지는 Perpetual Swap의 2018-12-19 최초 단계를 BTC 지원으로 시작했다고 명시한다. 2018-12-26 ETH를 추가하면서 LTC·ETC·XRP·BCH·BSV는 “곧 출시” 예정이라고 설명했다. 이 공식 연혁도 2018년에 30개 동시 perpetual 계약을 보유했다는 근거가 되지 않는다. 따라서 Binance USDⓈ-M을 OKX로 치환해도 같은 2018·30계약 G를 해결하지 못한다. [OKX perpetual 첫 출시 공지](https://www.okx.com/en-sg/help/perpetual-swap-officially-launched-on-okx-website-and-app-12-19-2018), [ETH 및 예정 계약 공지](https://www.okx.com/en-sg/help/eth-perpetual-swap-available)
- 별도 후보로는 Binance Spot OHLCV 기반 캔들 오더블록 연구가 가능성은 있다. Binance Public Data는 spot 월별·일별 klines archive와 개인 비생산 과거 알고리즘 백테스트의 이용조건을 공개한다. 다만 현재 보유 manifest에서 2018 전체 12개월 월 파일이 확인된 spot 심볼은 4개였고 2022년은 23개였으며, 이는 실제 봉 연속성·PIT 전체 코호트 증거가 아니다. 지금 고정된 Binance USDⓈ-M 35심볼 연구와는 instrument/거래비용/funding 정의가 달라 별도 사전등록 및 추가 코호트 입증이 필요하다. [Binance Public Data README](https://github.com/binance/binance-public-data/blob/master/README.md), [Binance Public Data 이용조건](https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md)
- 진짜 L2 기반 체결/호가장부 가설은 Spot candle 가설과도 다르다. Binance 담당자는 공개 Futures L2의 2023-05-28 전 구간에 일부 공백이 있었다고 밝혔으므로, 다른 instrument로 바꾼다는 사실만으로 역사 L2 재생 품질이 해결되지 않는다. [Binance Public Data L2 issue #268](https://github.com/binance/binance-public-data/issues/268)

**대체안 판정:** 기존 성과 G 기준을 유지하면서 별도 Binance Spot 사전등록으로 가는 길은 개념상 가능하지만, 고정 Futures 결과와 섞지 않고 2018·2022의 동일 ≥30심볼 완전성·연속성 및 정확한 현물 비용을 먼저 입증해야 한다. 해당 범위 변경은 승인 대기이며 이번 연구에서 새 preregistration·다운로드·실험을 만들거나 실행하지 않았다.

## 한국 주식 추가 후보 — FnGuide 시점별 종목 목록과 DataFeed 권리 경계

- FnSpace 도움말은 조회일 당시 상장 상태였던 기업이면 현재 상장폐지됐더라도 해당 과거 시점의 종목 코드·이름·시장 정보가 목록에 나올 수 있다고 설명한다. 외감 비상장사 및 상장된 적 없는 회사는 제외한다고 밝힌다. 이는 현재 생존 종목만의 리스트보다 한국 주식 PIT 유니버스 후보에 가깝지만, 매 거래일별 완전한 상장·상폐 날짜, 정리매매 가격, 최종 정산을 입증하지 않는다. [FnSpace 상장폐지 종목 FAQ](https://help-fnspace.fnguide.com/ko/articles/%EC%83%81%EC%9E%A5%ED%8F%90%EC%A7%80%EB%90%9C-%EC%A2%85%EB%AA%A9%EC%9D%98-%EB%8D%B0%EC%9D%B4%ED%84%B0%EB%82%98-%EB%A6%AC%EC%8A%A4%ED%8A%B8%EB%8F%84-%ED%99%95%EC%9D%B8%ED%95%A0-%EC%88%98-%EC%9E%88%EB%82%98%EC%9A%94-fdb742b2)
- FnGuide는 DataGuide 국내 주식 가격·수정주가·수익률과 이벤트 데이터를 1980년부터 제공한다고 설명하며, Quantiwise Time Series(Company)는 상장·상장폐지·IPO 기업을 대상으로 시계열 가격·재무·컨센서스를 출력한다고 명시한다. 각각의 상품 설명은 기간·필드 범위에 대한 공급자 주장이고, 전체 상폐 수익/최종 proceeds의 종목별 완전성은 별개다. [DataGuide 제공 데이터 안내](https://help-dataguide.fnguide.com/ko/articles/%EC%A0%9C%EA%B3%B5-%EB%8D%B0%EC%9D%B4%ED%84%B0-%EC%95%88%EB%82%B4-5c5347da), [Quantiwise Company 시계열 안내](https://help-quantiwise.fnguide.com/ko/articles/%EB%A9%94%EB%89%B4-%EC%86%8C%EA%B0%9C-Time-SeriesCompany-cb6ce702)
- 현재 공개된 DataGuide 조건은 법인 상담·계약 기반이며 최초 계정 연 720만원(VAT 별도), 1년 이내 중도해지 불가다. 사용 목적은 조회·분석으로 한정되고 기계적 대량추출이나 DB 구축은 계약 위반이라고 명시한다. 따라서 이 데스크톱 분석 라이선스만으로 자동 백테스트 입력을 만들 수 없다. 별도 DataFeed 경로가 존재하더라도 그 계약이 과거자료 대량전송, 개인 연구, 로컬 장기보관, PIT membership, 최종 상폐 지급 데이터를 허용하는지는 확인되지 않았다. [DataGuide 이용·요금·데이터 정책](https://help-dataguide.fnguide.com/ko/articles/%EC%9D%B4%EC%9A%A9-%EB%B0%8F-%EC%9A%94%EA%B8%88-%EC%95%88%EB%82%B4-48b18a4b), [FnGuide DataFeed 안내](https://corp.fnguide.com/fng/serviceinfo_quantiwiseDownload)
- FnGuide의 금융정보 서비스 설명은 DataFeed를 DataGuide/QuantiWise의 별도 Database 서비스로 구분한다. 고객이 원하는 데이터를 FTP/API로 보내며, 고객 서버로 대용량 데이터를 전송하고 API는 퀀트 분석·시뮬레이션 접근에 사용된다고 안내한다. 반면 공개 QuantiWise 사용자 약관은 프로그램·스크립트·매크로·알고리즘 등 기계적 방식의 다운로드, 고객사 DB 구축, 제3자 공유를 금지한다. 따라서 그 데스크톱 약관을 DataFeed 계약에 자동 적용하거나 DataFeed를 이미 허용된 것으로 간주하지 않고, 별도 계약의 명시 조항을 받아야 한다. [FnGuide DataFeed/DB 서비스 설명](https://corp.fnguide.com/Service/FinancialService), [QuantiWise 공개 사용자 약관](https://corp.fnguide.com/fng/cmcen_Service_20240728)

**판정:** FnGuide DataFeed는 고정된 자동 백테스트 목적과 명시적으로 관련된 유력한 계약 경로다. 그러나 가격·개인/기관 구매 자격·대량 과거 추출·장기 보관·PIT 정확도·전체 상폐 정산은 공개 자료에서 입증되지 않았다. 계약조건 문의나 제품 시범은 하지 않았으므로 KR 데이터 게이트는 닫힌 상태다.

## 미국 주식 추가 후보 — Sharadar SEP와 개인용 라이선스 부적합 조건

- Sharadar의 SEP 주가 문서는 활성·상폐 미국 주식 약 21,000개 OHLCV와 1997-12 이후 이력을 명시하며, actions 문서는 분할·배당·spin-off·티커 변경·상장/상폐일·상폐 사유·인수 상대를 포함한다고 설명한다. 따라서 현재 Yahoo 패널보다 넓은 생존 종목 자료와 기업행사 교차 확인을 제공할 잠재 후보지만, 각 설명은 공급자 커버리지 주장이다. [SEP 가격 스키마](https://sharadar.com/docs/stocks), [기업행사 스키마](https://sharadar.com/docs/actions)
- 공개 스키마는 가격 식별자를 ticker+date로 두고 별도 영구 security ID나 상폐 후 지급액·지급일·상폐수익 필드를 열거하지 않는다. 상폐일·이유·인수 상대 티커만으로 최종 회수액을 입증할 수 없고, 티커 재사용·법인 연속성 대사도 별도로 필요하다. 공급자가 말하는 S&P 구성종목 이력은 전체 미국 상장 유니버스와 다르다.
- Sharadar의 공개 개인 라이선스는 자연인의 비전문적 개인 사용만 허용하고 전문 연구·기관/조직 용도 및 데이터 공유를 금지한다. 시험/평가 결과도 사전 서면 허가 없이 문서나 외부에 공개할 수 없으며, 구독 종료 후 30일 내 원자료·bulk 파일·캐시·데이터를 재현할 수 있는 추출본을 삭제하라고 명시한다. 가격표는 이번 공개 문서에서 확인되지 않았다. [Sharadar 개인 라이선스 약관](https://sharadar.com/terms)

**판정:** Sharadar의 기간과 생존/상폐 가격 범위는 후보에 가깝지만, 현재 개인용 계약은 이 다중 에이전트 연구 기록·평가 절차와 양립하는지 확인되지 않았고 최종 상폐 지급 필드도 문서에서 확인되지 않는다. 별도 서면 기관/연구 라이선스가 공개적으로 적격화되지 않아 계정·API·구매·데이터 접근을 하지 않았고, US G 후보로 승격하지 않는다.

## R11 다음 가설 정체 감사 — BTC 방향 필터는 이미 시험됨

- R11 보고서는 작은 목표거리 48개 조합을 탐색했지만 기본 비용 후 EV는 48/48 음수, PF는 48/48 1 미만, M2는 48/48 80% 미달이었다. 목표값만 바꾸는 재시험은 실패 기록상 제외해야 한다. [R11 결과 보고서](REPORT_R11_TARGET_DISTANCE.md)
- R11의 “상위 시간대 방향 정렬” 제안과 가까운 이전 실험 R7은 BTC 4시간 SMA150 위·상승 조건의 알트코인 롱 오더블록 1개 설정이었다. 현재 R7 보고서 기록은 EV +6.15bp, PF 1.023, 연환산 Sharpe 0.096이며 M2 미기록, 시각 정합성 미확정, OOS/독립성·강건성 검증 미실행이다. R7도 후보가 아니므로 이 필터를 바꾸지 않고 다시 넣는 것은 독립 개선 증거가 아니다. [R7 결과·한계](REPORT_R7.md)
- “구조 재확인”은 R7의 추세 필터와 다른 구성요소일 수 있지만, 해당 규칙·시점·비용·표본 분모는 별도로 고정해 시험하기 전까지 효과가 확인되지 않았다. 현재 고정 Binance 2018 USDⓈ-M 상품 결손 때문에 해당 방향의 crypto 후보를 G로 검증할 수 없다. 새 사전등록이나 venue 범위 변경은 이 보고서에서 수행하지 않았다.

**판정:** 반복 금지할 것은 목표거리만 바꾸는 48셀 탐색과 BTC 방향 필터 단독 변형이다. 구조 재확인 결합 가설은 아직 미검증 아이디어이며, 그 자체를 통과 후보로 취급하지 않는다. 데이터 gate를 해결할 수 있는 적법한 동일 범위 입력이 생기기 전까지 실험 실행은 금지 상태다.

## 조사 범위 기록 — R12 경로 검색 출력 노출

- R7·R11 가설 중복을 찾는 범위 검색이 예상보다 넓어 R12 파일 경로 및 텍스트 일부가 터미널 출력에 표시됐다. 별도 R12 본문을 지정해 열거나 분석하지 않았지만, 검색 결과 일부가 노출됐으므로 이를 범위 사고로 기록한다. 해당 출력은 본 조사의 근거·가설 선택·결론에 사용하지 않았고, R12 파일은 수정하지 않았으며 이후 검색에서 제외한다.

## 미국 주식 후보 — OHLC.io PIT/상폐 API 사양 및 실제 G 적합성

- OHLC.io `/v1/eod` 문서는 NYSE/Nasdaq를 포함한 U.S. 주식·ETF 일봉 OHLCV, 시장 전체 날짜별 행, `as_of` 지식 cutoff, 안정적인 `instrument_id`, 상폐 종목의 가격 이력, raw/split/total-return 출력, coverage endpoint의 종목별 내부 gap 목록을 설명한다. 이 명세는 기존 Yahoo 생존 종목 패널보다 필요한 데이터 필드에 가깝다. [역사적 주가 API](https://ohlc.io/data/historical-stock-prices), [API 개요](https://ohlc.io/ohlc-api)
- 공개 가격표는 Free/Developer 5년(현재 기준 2021-11 이후), Pro USD 149/월 15년(2011-11 이후), Commercial USD 899/월과 Scale USD 1,499/월의 전체 이력을 제시한다. 고정 US 사전등록의 2007-06-05 시작 구간을 덮으려면 문서상 Commercial 또는 Scale이 필요하다. Developer는 전체 미국 주식도 제공하지만 2018·2022에 닿지 않고, Pro는 해당 약세장에는 닿아도 2007 시작 구간을 덮지 않는다. [OHLC 가격표](https://ohlc.io/pricing)
- 이용약관은 Free/Developer의 개인 사용, Pro의 내부 사용, Commercial/Scale의 상업 표시·재배포 권리를 구분한다. 이 연구에 Commercial 표시/재배포 권리가 필요한 것은 아니지만, 전체 역사에 접근 가능한 플랜이 Commercial부터라는 공개 가격표 조합이 핵심이다. 해당 요금은 자동 월 반복 결제·선불이며 환불은 법률상 의무 또는 별도 합의 외에는 없다고 약관은 밝힌다. 등록·결제·키 발급·API 호출은 하지 않았다. [이용약관](https://ohlc.io/terms)
- 중요한 반대 증거: Corporate-action/기업 master 문서는 security master가 2026-09에 만들어져 그 시점부터의 상폐만 기록하며, TWTR·SIVB 등 이전에 상폐된 많은 발행자는 날짜로 resolve되지 않는다고 명시한다. 상폐 가격행이 남아 있다는 설명만으로 과거 전체 상폐 유니버스의 완전한 PIT 분모가 확보된 것은 아니다. 따라서 현재 문서만으로는 전체 주식 G의 상폐·PIT 게이트를 통과했다고 할 수 없다. [Corporate actions API](https://ohlc.io/docs/corporate-actions), [종목별 데이터 coverage](https://ohlc.io/docs/dataset-coverage)
- Total-return OHLC는 과거 배당을 반영한 조정 시계열이고 `as_of` 응답은 당시까지 알려진 값 및 이후 수정사항을 함께 반영할 수 있다. 거래 신호에 미래 지식이 섞이지 않도록 raw OHLC로 causal feature를 계산하고 배당·분할을 실현 시점에 적용하는 처리법이 필요하다. 인수·파산 대가 및 terminal cash proceeds가 전체 상폐 종목에 빠짐없이 표준화됐다는 문서상 증거는 확인되지 않았다. [역사적 주가 API](https://ohlc.io/data/historical-stock-prices), [이용약관의 데이터 한계](https://ohlc.io/terms)

**판정:** OHLC.io는 2007~2026 일별 가격 및 PIT 조회에 대한 유망한 조달 후보지만, full-history 플랜은 월 USD 899부터이고 과거 상폐 주체의 security-master 연결 결손이 공개 문서에 명시되어 있다. 현재는 비용·권리·유니버스 완전성·최종 상폐 정산이 모두 적격화되지 않아 데이터 게이트가 닫혀 있다. 구매승인·계약·실제 샘플 없이 US 전략 실험에 투입하지 않는다.

## 미국 주식 정산 데이터의 더 강한 공식 경로 — CRSP 필드와 잔여 결손

- CRSP US Stock Database 공식 설명은 NYSE, NYSE American, NYSE Arca, Nasdaq, Cboe BZX의 활성·비활성 32,000개 이상 미국 증권에 대해 생존편향 없는 가격·기업행사·상폐 이력을 제공한다고 밝힌다. 각 거래소의 가격 계열은 서로 다른 시작일을 가지며 Nasdaq은 1972-12-14부터라고 적혀 있어 고정 연구기간 2007-06-05~2026-05-31을 덮을 명목 기간은 있다. [CRSP US Stock Databases](https://www.crsp.org/research__trashed/crsp-us-stock-databases/)
- 공식 데이터 사전에는 상폐 코드, 상폐 후 금액, 상폐 가격, 상폐수익(배당 포함/제외), 상폐일, 후속 정보일, 지급일 및 기업행사 분배 내역 필드가 있다. CRSP 계산 지침은 지급액이 상폐 가격, 최종 분배금 또는 둘의 합일 수 있다고 설명한다. 이는 OHLC.io의 과거 security-master 결손보다 상폐 정산을 검증할 구체적인 관측 필드가 있는 경로다. [CRSP 데이터 구조와 상폐 필드](https://www.crsp.org/crsp_pdf/crsp-us-stock-indexes-databases-data-descriptions-guide-crspaccess/), [CRSP 수익 계산 지침](https://www.crsp.org/wp-content/uploads/2023/09/programmers-guide.pdf)
- 이 자료가 모든 종목의 최종 회수액을 보장하지는 않는다. CRSP 문서는 정보가 없거나 불완전하면 상폐수익을 계산하지 않는다고 명시하고, 최근 상폐 이벤트 한 건만 현재 이벤트 배열에 기록한다고 설명한다. 그러므로 실제 적격화에는 미확정/누락 상폐 상태의 수, 고정 코호트와 영구 ID 연결, 해당 시점의 가격·분배 내역, cutoff 시점 이후 수정 여부를 파일 수준에서 대사해야 한다.
- 상폐수익 계산 설명에는 가격·지급 근거가 없어 반환하지 못한 값의 사유 코드 `-55`가 있고, 월간 파일의 마지막 부분월 수익은 실제 상폐 후 수익이 아닐 수 있다고 별도로 경고한다. 따라서 CRSP를 받더라도 일봉 분배·상폐 이벤트를 직접 대사하고 `-55` 및 부분월 값을 전략의 실현 청산으로 오인하지 않는 검증이 선행돼야 한다. [CRSP 데이터 정의: 상폐수익 누락 코드와 월간 예외](https://www.crsp.org/crsp_pdf/crsp-us-stock-indexes-databases-data-descriptions-guide-crspaccess/)
- CRSP 구독은 기관용 데이터 라이선스 절차로 안내되고 공개 페이지에는 개인 연구자의 직접 이용 가능 여부나 가격이 제시되지 않는다. WRDS에서 쿼리 UI가 보이는 사실도 이 사용자의 계정 권한을 증명하지 않는다. 이번 조사에서는 계정 상태, 가격, 샘플, 쿼리, 실제 파일, 라이선스를 확인하거나 요청하지 않았다. [CRSP 구독 안내](https://www.crsp.org/research/)

**판정:** CRSP가 공개 자료에서 확인된 미국 주식 경로 중 상폐 지급과 기업행사를 가장 직접적으로 점검할 필드 정의를 갖췄다. 명목 데이터 기간은 고정 시작일을 덮지만, 이용권·가격·현재 계정 접근·코호트별 누락 상폐 정산 비율·2007~2026 실제 PIT 완전성은 확인되지 않았다. 따라서 후보 조달 경로로만 승격하며, 데이터 게이트와 전략 후보 수는 바꾸지 않는다.

### CRSP 접근 자격 및 누락 상폐 보완 가능성

- WRDS 약관은 WRDS 접근을 구독 기관/법인과 그 승인 사용자로 한정하며, 학술기관 개인 계정은 해당 구독기관의 교수·연구직·현재 재학생 등 자격을 제시한다. 기관 IP Daypass도 해당 기관에서 통제하는 공간과 유효한 기관 이메일을 전제로 한다. WRDS 공개 가격은 게시되지 않고 가격 문의를 안내한다. CRSP/Morningstar 역시 연구 데이터베이스가 학술기관·정부기관·투자 실무자 라이선스 사용자에게 제공된다고 설명한다. 사용자의 기관 소속·구독 자격은 확인되지 않았으므로 개인이 즉시 쓸 수 있는 공개 무료 경로로 취급하지 않는다. [WRDS 이용 약관](https://wrds-www.wharton.upenn.edu/users/tou/), [WRDS 구독·가격 안내](https://wrds-www.wharton.upenn.edu/pages/about/what-wrds/), [CRSP research data access](https://indexes.morningstar.com/research-data-products)
- SEC의 공개 API는 제출 이력과 기업이 제출한 XBRL 재무 데이터를 제공하지만, 기업별 표준 상폐 최종 지급액 테이블은 명세에 없다. FINRA OTC Daily List는 일부 장외 전환·기업행사 추적에는 도움이 될 수 있지만 모든 거래소 상폐의 최종 proceeds를 일괄 대체하지 않는다. 따라서 이 공개 데이터들을 CRSP의 상폐 `−55` 누락을 모두 채우는 자동 보완 자료로 간주하지 않는다. [SEC EDGAR API 범위](https://www.sec.gov/search-filings/edgar-application-programming-interfaces), [FINRA 개발자 문서](https://developer.finra.org/docs)
- CRSP 지수 산정 문서에 나타나는 “10거래일 뒤 0으로 처리” 규칙은 지수 산출을 위한 평가방법이다. 개별 주식 전략의 실제 경제적 최종 지급액을 입증하는 상폐 시세 근거가 아니므로, `−55` 수익을 0으로 메우는 방식으로 전용하지 않는다. [CRSP Market Index methodology](https://www.crsp.org/wp-content/uploads/guides/CRSP_Market_Indexes_Methodology_Guide-December_2025.pdf)

**판정:** CRSP는 현 공개 문서 기준 미국의 가장 강한 데이터 스펙 후보이지만, 개인 직접 접근과 가격이 확인되지 않았고 기관 자격이 필요할 가능성이 높다. SEC/FINRA 공개 자료는 일부 사건 확인에 쓸 수 있어도 결손 상폐 수익을 전체 대체하지 않는다. 구매·기관 문의·계정 접근 없이 현재 US 데이터 gate는 닫힌 상태다.

## 미국 주식 추가 후보 — Sharadar SEP와 개인용 라이선스 부적합 조건

- Sharadar의 SEP 주가 문서는 활성·상폐 미국 주식 약 21,000개 OHLCV와 1997-12 이후 이력을 명시하며, actions 문서는 분할·배당·spin-off·티커 변경·상장/상폐일·상폐 사유·인수 상대를 포함한다고 설명한다. 따라서 현재 Yahoo 패널보다 넓은 생존 종목 자료와 기업행사 교차 확인을 제공할 잠재 후보지만, 각 설명은 공급자 커버리지 주장이다. [SEP 가격 스키마](https://sharadar.com/docs/stocks), [기업행사 스키마](https://sharadar.com/docs/actions)
- 공개 스키마는 가격 식별자를 ticker+date로 두고 별도 영구 security ID나 상폐 후 지급액·지급일·상폐수익 필드를 열거하지 않는다. 상폐일·이유·인수 상대 티커만으로 최종 회수액을 입증할 수 없고, 티커 재사용·법인 연속성 대사도 별도로 필요하다. 공급자가 말하는 S&P 구성종목 이력은 전체 미국 상장 유니버스와 다르다.
- Sharadar의 공개 개인 라이선스는 자연인의 비전문적 개인 사용만 허용하고 전문 연구·기관/조직 용도 및 데이터 공유를 금지한다. 시험/평가 결과도 사전 서면 허가 없이 문서나 외부에 공개할 수 없으며, 구독 종료 후 30일 내 원자료·bulk 파일·캐시·데이터를 재현할 수 있는 추출본을 삭제하라고 명시한다. 가격표는 이번 공개 문서에서 확인되지 않았다. [Sharadar 개인 라이선스 약관](https://sharadar.com/terms)

**판정:** 기간과 생존/상폐 가격 범위는 후보에 가깝지만, 현재 개인용 계약은 이 다중 에이전트 연구 기록·평가 절차와 양립하는지 확인되지 않았고, 최종 상폐 지급 필드도 문서에서 확인되지 않는다. 별도 서면 기관/연구 라이선스가 공개적으로 적격화되지 않아 계정·API·구매·데이터 접근을 하지 않았고, US G 후보로 승격하지 않는다.

## 한국 주식 PIT 데이터 경로 — Koscom 상품과 지수 라이선스 조건

- Koscom DataMall은 자사 국내 일별 데이터 범위를 KOSPI 1975년~현재, KOSDAQ 1996년~현재로 소개하고, 개별주 시세·종목정보·자본금 변동 및 주요 종목조치(CA) 자료를 제공한다고 명시한다. 상품 카탈로그에는 기업행동 반영 조정 종가 상품도 표시되며, 과거 시계열의 실제 시작일·필드·가격은 문의 항목으로 남아 있다. 이 공개 설명은 기간과 CA 자료가 있을 수 있음을 보여주지만, 모든 상폐 종목의 OHLC 및 최종 정산이나 상장 당시 전체 종목 집합을 입증하지 않는다. [Koscom DataMall 범위](https://www.koscom.co.kr/mobile/main/contents.do?menuNo=400044), [Koscom DataMall 상품 카탈로그](https://datamall.koscom.co.kr/eng/main.do)
- Koscom CHECK 도움말의 지수구성종목·지수조치 화면은 KRX 및 해당 지수군과 라이선스 계약이 필요하다고 명시한다. 구성종목의 적용일·발표일·선정/제외 및 주식수 조치 정보를 다루므로 PIT 유니버스 측면에서 직접 관련 있지만, 이 자료는 별도 라이선스 대상이며 자유 공개 데이터가 아니다. 개인 사용자의 라이선스 적격성·비용과 DataMall의 역사적 구성 이력 범위는 공개 자료만으로 확인되지 않았다. [Koscom CHECK 지수구성종목 라이선스 안내](https://helpcheck.koscom.co.kr/KO/cdbc4d9756c9272e)

**판정:** Koscom은 한국의 가격·기업조치 자료에서 기간상 유망한 공식 조달 경로지만, PIT 구성 이력은 별도 라이선스가 필요한 것으로 확인되며 상폐 최종 proceeds, 개별 파일 이력, 가격·장기 보관 권리는 미확인이다. 계정·문의·구매·API·데이터 접근 없이 후보 경로로만 기록한다. 한국 G와 전략 후보 수는 변경하지 않는다.

## 2026-11-24 공개자료 후속 — KRX 상폐 OHLC, 미국 사건 연혁, Binance Spot 한계

### 한국 주식: 마지막 거래 가능 시세의 공개 필드와 수집권 경계

- KRX 정보데이터시스템의 「상장폐지종목 현황」은 종목코드·시장·증권구분·상장일·폐지일·폐지사유를 표시하며, 자료 기준이 상장폐지 직전 마지막 매매일이라고 명시한다. 「상장폐지종목 시세 추이」는 일자별 OHLC·거래량·거래대금과 상장폐지일·사유를 표시하고, 가격은 정규시장 기준이라고 적는다. 이는 상폐 가격이 전혀 없다는 가정을 바로잡지만, 실제 청산 배당·합병 대가·상폐 후 회수액을 뜻하지 않는다. [상장폐지종목 현황](https://data.krx.co.kr/contents/MDC/STAT/issue/MDCSTAT238.jsp), [상장폐지종목 시세 추이](https://data.krx.co.kr/contents/MDC/STAT/issue/MDCSTAT239.jsp)
- KRX 규정 설명상 상장폐지 확정 종목은 투자자에게 마지막 환금 기회를 주기 위해 7매매일 정리매매가 허용될 수 있다. 정리매매는 30분 단위 단일가 체결, 일 14회, 가격제한폭 없음으로 운영된다. 그러므로 정리매매 중 마지막 실제 체결 시세를 연구 종료 가격으로 쓸 가능성은 있으나, 거래정지·미체결·거래대금·개별 종목의 실제 매도 가능성과 대가 완전성을 별도로 검증해야 한다. [KOSPI 정리매매 방식](https://regulation.krx.co.kr/contents/RGL/03/03010306/RGL03010306.jsp), [KOSDAQ 정리매매 방식](https://regulation.krx.co.kr/contents/RGL/03/03020308/RGL03020308.jsp)
- 사이트 약관은 자동화 수단으로 정보를 무단 수집·복제·배포하는 행위를 금지하고, 거래소의 사전 허락 없는 복사·복제·배포·전송도 금지한다. 개인의 단순 참고 목적을 벗어난 시세 이용은 별도 계약이 필요하다고 안내한다. 화면에 다운로드 버튼이 있다는 사실은 대량 자동수집·로컬 장기보관·백테스트 권한을 부여하지 않는다. 전체 역사 범위, 데이터 완전성, 사용자가 요청한 연구에 적용되는 권한은 문서상 확정되지 않아 수집을 시작하지 않는다. [KRX 정보데이터시스템 약관](https://data.krx.co.kr/contents/MDC/INFO/informationController/MDCINFO003.cmd), [KRX 데이터 수신방법](https://openapi.krx.co.kr/contents/OPP/DATA/OPPDATA003.jsp)
- 코스콤 시장정보 이용정책은 개인가입자를 자연인, 비사업 목적, 본인 자산의 관리·투자 용도, 제3자 미제공 조건으로 정의한다. 같은 정책에서 계량분석 등 실시간정보 가공 이용을 비조회형으로 분류하고 계약·신고·가격표 적용 가능성을 설명한다. 다만 이는 코스콤 정보이용계약 대상 정책이며, 공개 KRX 화면의 과거 자료를 내려받아 로컬 백테스트에 쓰는 권리를 직접 허가하거나 금지하는 조항으로 확대해석할 수 없다. 사용자 연구의 적용 상품·계약·요금은 확인되지 않았다. [코스콤 시장정보 이용정책](https://data.krx.co.kr/inc/datasale/Market%20Data%20Usage%20Polices_ko.pdf?v=20230121_1)

**판정:** 한국의 공개 공식 화면은 상폐 직전 OHLC와 거래 가능 정리매매 기간을 확인할 수 있는 조사 경로다. 권리·자동화 허용·전체 커버리지·실제 거래 가능성 검증이 남아 있어 입력 데이터 게이트는 닫혀 있고 한국 전략 후보는 0개다.

### 미국 주식: 무료 사건 자료는 가격·대가 전량을 대신하지 못함

- Nasdaq의 Daily List 상품 설명은 1999년 이후 신규상장·상장폐지·심볼/회사명 변경·배당 등 기업행사 이력을 제시한다. 공개된 필드 사양은 유니버스 사건의 날짜와 심볼 변경을 추적하는 데 유용하지만, 현재 일일 파일은 보안 FTP 경로이며 무료 과거 파일 접근권·라이선스·상폐 대가 필드는 확인되지 않았다. [Nasdaq Daily List 설명](https://www.nasdaqtrader.com/trader.aspx/Trader.aspx?id=DailyListPD), [필드 사양 PDF](https://www.nasdaqtrader.com/content/technicalSupport/specifications/dataproducts/dlcompletespec.pdf)
- FINRA OTC Daily List의 공개 과거 자료는 OTC 시장의 2014-11-17 이후 추가·삭제·이름/심볼 변경을 보완할 수 있지만, 미국 전체 거래소 유니버스, 2007~2014, 상폐 후 대가를 채우지 않는다. [FINRA 과거 파일](https://otce.finra.org/otce/DailyList/staticArchives), [FINRA 사용자 안내](https://www.finra.org/sites/default/files/OTCE_Daily_List_User_Guide.pdf)
- SEC EDGAR 공개자료는 무료 접근·재사용 경로와 20년 이상 신고서 검색을 제공하며 Form 25 및 합병/교환 공시에서 일부 상폐 시점·대가를 사례별로 대사할 수 있다. 그러나 API의 표준 응답은 모든 종목의 최종 회수액 데이터베이스가 아니며, 사건별 문서 해석과 식별자·지급액 대사가 필요하다. [SEC 자료 재사용 안내](https://www.sec.gov/about/webmaster-frequently-asked-questions), [EDGAR 데이터 접근](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data), [SEC API 범위](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)

**판정:** 공개 사건 연혁과 SEC 공시로 표본 사건을 독립 확인할 수는 있지만, 2007~2026년 완전한 일별 PIT 유니버스와 종목별 종료 대가를 함께 입증할 무료 경로는 확인되지 않았다. US 전략 후보는 0개다.

### 코인: Binance Spot OHLCV는 별도 연구의 자료 후보일 뿐

- Binance 공식 공개 아카이브는 Spot 월별 OHLCV 파일 경로, 지원 interval, 체크섬 및 사후 파일 교체 공지를 설명한다. 공개 Vision 약관은 개인의 비상업·비실전 과거 백테스트 범위를 허용한다고 명시하지만, 상업 사용은 별도 서면 허가가 필요하다. [공식 아카이브 README](https://github.com/binance/binance-public-data/blob/master/README.md), [공식 이용조건](https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md)
- 공식 다운로드 스크립트의 2018·2022 연도 목록과 BTCUSDT/BNBUSDT 예시는 해당 연도에 30개 이상의 동일 적격 종목이 존재하거나 각 종목의 월별 파일 12개가 완전함을 증명하지 않는다. Binance 이슈에는 2022년 NANOUSDT 월별 klines 중단 및 XNO 이름 변경 사례가 기록돼 있어 현재 심볼목록만으로 과거 유니버스를 구성하면 종목변경 누락 위험이 있다. [공식 스크립트](https://github.com/binance/binance-public-data/blob/master/shell/download-klines.sh), [심볼 변경 사례](https://github.com/binance/binance-public-data/issues/238)
- 따라서 Spot 캔들 오더블록은 USDⓈ-M R11/R12와 분리된 새 사전등록, 역사적 기준일의 유니버스 고정, 2018·2022 동일 30종목 이상 및 월별 존재·연속성 대사가 선행되어야 한다. 현재는 별도 사전등록 승인과 코호트 증거가 없으므로 다운로드·메타데이터 조회·가격행 접근·백테스트를 하지 않는다.

**판정:** 코인 Spot 자료 이용조건이 적격일 가능성은 있으나, 고정 G의 과거 코호트·완전성은 공식 설명만으로 미입증이다. 기존 USDⓈ-M 연구와 섞지 않으며 코인 전략 후보는 0개다.

### 이 후속 조사에서 하지 않은 일

공식 문서·약관과 이미 공개된 필드 설명만 확인했다. KRX 자동수집·다운로드, Nasdaq/FINRA/SEC 데이터셋 수집, Binance 파일목록·체크섬 조회, 가격행 열람, API 키·계정 접근, 업체·기관 문의, 사전등록·공유 장부 변경, 실험·백테스트는 하지 않았다. 이 결과는 세 시장 모두의 데이터 경로를 더 구체화하지만 검증 게이트를 열거나 후보 수를 늘리지 않는다.

## 실행환경 데이터 경로 확인 — 메타데이터만

- 최초 확인 당시 현재 프로세스의 `TRADING_DATA_DIR`는 설정되지 않았고 `/Users/user/CODE/trading_data`도 없었다. 저장 규칙에 따른 빈 기본 디렉터리를 생성하고 readback한 뒤에는 해당 기본 경로가 존재하며 자식 항목은 0개다. `TRADING_DATA_DIR`는 여전히 설정되지 않았고 `external/equities/{kr,us}` 자료도 없다. 따라서 `data_sources/EQUITY_SOURCES.md`에 적힌 외부 주식 패널을 현재 세션에서 사용할 수 있다고 가정하지 않는다.
- 추가로 확인 가능한 `/Volumes/home/mac/CODE/Coin_Trade` 경로는 존재하지만, 그 옆의 `/Volumes/home/mac/CODE/trading_data`는 존재하지 않는다. 이 좁은 경로 확인에서도 카탈로그의 별도 데이터 루트는 찾지 못했다.
- 저장소 내 `scratchpad/strategy_bt/data_long/`의 Parquet 10개와 `scratchpad/bb_stoch_stc/data/`의 Parquet 78개를 `/opt/anaconda3/bin/python3`의 PyArrow 21.0.0으로 footer metadata만 읽었다. `data_long`은 4개 고유 심볼이며 모두의 `date_min`이 2018년 말 이전이다. `bb_stoch_stc/data`는 날짜통계를 가진 21개 고유 심볼 중 4개의 `date_min`이 2018년 말 이전, 13개의 `date_min`이 2022년 말 이전이다. 확인한 footer의 `date_max`는 모두 2026-06-01 뒤여서 이 원본 Parquet를 직접 cutoff 입력으로 열지 않았다. 가격행·후행 행·지표값은 열지 않았다.
- 실제 R11 어댑터인 `data_access.iter_crypto_bars`는 `TRADING_DATA_DIR/cache/orderblock/bars/<timeframe>`에서 중간 Parquet를 찾으며, 기본 루트가 `/Users/user/CODE/trading_data`다. 이 데이터 루트가 없으므로 방금 조사한 저장소 내 `data_long`/`bb_stoch_stc/data` 파일들은 R11 러너의 등록 입력이 아니다. 기존 실행을 재현하는 데 필요한 외부 원본·봉 변환물·funding 자료는 현재 작업환경에서 확인할 수 없다.
- 이 관찰은 현재 샌드박스 경로가 작업 카탈로그와 다를 수 있음을 보여줄 뿐, 사용자의 실제 Mac이나 별도 세션에 해당 자료가 없다는 뜻은 아니다. 코인 Parquet 파일은 기존 위치 그대로 두었으며 이동·변환·백테스트 입력으로 사용하지 않았다.

**판정:** 올바른 외부 데이터 저장 기본 경로는 현재 생성했지만 비어 있다. 현재 작업환경에서 확인 가능한 한국·미국 외부 일봉 자료는 0개다. 코인 Parquet footer로 확인되는 과거 시작 심볼은 2018년 4개, 2022년 13개뿐이며, 이는 고정 30심볼 요건보다 적다. 날짜 범위 통계는 연속성, 당시 상장 유니버스, 거래소·원천, 사용권을 입증하지 않으며 R11 러너의 별도 입력 경로도 비어 있어 코인 데이터 게이트는 닫혀 있다. 세 시장의 후보 수는 모두 0개다.

## 실행환경 재확인 — 외부 데이터 루트와 KIS 도구의 증거 한계

- 이번 세션에서 `/Users/user/CODE/trading_data`와 `/Volumes/home/mac/CODE/trading_data`만 메타데이터 수준으로 확인했다. 두 루트 모두 존재하지만 `external/crypto`, `external/equities`, `market_data/kis-cache`, `cache/orderblock` 하위 경로는 모두 없었다. 저장소 안 `trading_data/`는 작업트리에 나타나지만 사용자 저장 규칙상 대용량 데이터는 저장소 밖이어야 하므로 그 내용을 열지 않았고 입력자료로 간주하지 않았다.
- 현재 `TRAIN_TRIALS.csv` 메타데이터는 70,467,503 bytes, 수정시각 2026-11-24 20:30:12 KST였다. 행 내용은 읽지 않았다. `sysmon` 조회 실패가 앞서 기록되어 전체 프로세스(writer) 부재를 이번 확인만으로 단정할 수 없다.
- 한국투자증권 공식 개발자 포털은 백테스트 엔진·그리드 탐색 기능을 소개하지만, 빠른 시작은 API key 설정을 요구한다. 이 제품 설명은 KIS 과거 시세의 자산별 시작일, 상장폐지 포함 여부, 파일 장기보존 권리 또는 이 프로젝트의 고정 유니버스 적합성을 보증하지 않는다. 따라서 API/키 접근과 백테스트를 시작하지 않았고, KIS 후보를 통과 처리하지 않았다. [KIS 백테스트 엔진 안내](https://apiportal.koreainvestment.com/toolkit-backtest)
- KRX OPEN API 영문 약관은 사용자가 약관에 동의하고 인증키를 신청·발급받아야 API를 쓸 수 있다고 명시한다. 이 약관 확인만으로 비인증 공개 데이터 이용이나 상폐 가격의 과거 완전성이 성립하지 않는다. 인증키 신청 또는 약관 동의는 하지 않았다. [KRX OPEN API 이용약관](https://openapi.krx.co.kr/contents/OPP/INFO/OPPINFO005.jsp)

**판정:** 외부 데이터 루트에는 이번 재확인 시점에도 전략 입력 자료가 보이지 않았다. 한국의 공식 백테스트 제품 존재는 자료 사용권·기간·품질 게이트와 별개이므로 시장 후보 수는 여전히 0개씩이다. 장부 행, 저장소 내부 데이터, cutoff 뒤 가격행, 키·계정 정보는 열지 않았다.

## 신규 코인 자료 후보 — CryptoDataDownload 공개 카탈로그

- 제공처는 무료 암호화폐 자료 페이지에서 여러 거래소의 현물·선물 OHLCV를 CSV로 제공하고, 카탈로그 기준으로 20개 이상 출처·1,500개 이상 상품과 2017년 이후 아카이브를 주장한다. 다운로드를 위해 계정이 필요 없다고도 안내한다. 라이선스로는 CC BY-NC-SA 4.0을 표시한다. 이는 무료 공개 후보로 새로 발견했으나 거래소 원천의 공식 아카이브는 아니다. [CryptoDataDownload 무료 과거 자료 카탈로그](https://www.cryptodatadownload.com/data/)
- 제공처의 자료무결성 안내는 운영·기술 문제로 데이터 수집이나 정확성이 저하될 수 있음을 명시한다. 전체 면책문은 웹사이트 정보의 정확성·완전성을 보장하지 않으며, 저작권자 허가 없이 포함된 저작물을 공정이용이라고 판단해 제공할 수 있고, 공정이용 범위를 넘어 자료를 쓰려면 권리자의 허가가 필요하다고 적는다. 따라서 제공처가 표시한 CC 라이선스만으로 원거래소 원자료의 권리까지 정리됐다고 볼 수 없다. [자료무결성 안내](https://www.cryptodatadownload.com/data/integrity/), [전체 면책문](https://www.cryptodatadownload.com/disclaimer/), [CC BY-NC-SA 4.0 요약](https://creativecommons.org/licenses/by-nc-sa/4.0/)
- 카탈로그 설명은 심볼별 `First Date Available` 및 `Last Date Available` 필드를 제공한다고 하지만, 이번 웹 문서 열람 결과로는 해당 전체 심볼 테이블이 실제 표시되지 않았다. 그러므로 2018·2022에 같은 기준으로 적격인 자산이 30개인지, 고정 선물 코호트와 어떤 교집합인지, 당시 PIT 상장군과 폐지 후 최종 회수가 기록됐는지는 확인하지 못했다. 제공처는 무결점·완전성을 보장하지 않으며, 라이선스 조건도 별도 확인이 필요하다.
- 제공처의 별도 정적 카탈로그는 Binance 현물 일봉·시봉·분봉 각각에 1,102개 심볼과 `2017-01-01` 시작 범위를 표시하며 가격을 `Public (free)`로 분류한다. 이는 그 자료군에서 가장 이른 커버리지 날짜와 현재 목록 규모에 대한 카탈로그 설명이다. 1,102개 각각이 2017년에 상장돼 있었다거나 전 종목이 2018·2022 두 해에 존재했다는 뜻은 아니다. Binance 페이지는 시봉·분봉의 경우 무료 계정이 필요할 수 있다고 별도로 안내한다. [CryptoDataDownload 정적 카탈로그](https://api.cryptodatadownload.com/static/catalog/CDD_Data_Catalog.html), [Binance 자료 페이지](https://www.cryptodatadownload.com/data/binance/)

**판정:** CryptoDataDownload는 후속 메타데이터 조사 대상으로는 남기지만, 현재는 사용권·공통 코호트·PIT·상폐 결말이 미입증이라 데이터 게이트를 열지 않는다. 데이터·파일·원시 가격행 다운로드, 제공처 계정 생성, 웹 API 사용 또는 백테스트는 하지 않았다. 이미 공식 Binance Vision 원천의 사용권은 확인돼 있으나 동일 코호트·과거 유니버스·상폐 처리 부족으로 막혀 있다는 판정과 구분한다.

## 독립 미국 자료 경로 재검증 — CRSP, S&P DJI, EDGAR

- CRSP의 미국 주식 자료 설명은 현존·비현존 증권, 일별 가격, 기업행위 및 영구 식별자를 포함하는 구독 상품을 설명한다. 현재 CIZ 가이드는 상장폐지 총수익(`DelRet`) 및 결측 사유 필드(`DelRetMissType`)를 열거하므로, 정산 불명 건은 실제 파일에서도 별도로 판정해야 한다. CRSP 이용권이 있더라도 전체 상폐 종료값 완전성이 자동으로 입증되는 것은 아니며, 이용권·가격은 공개 무료 경로로 확인되지 않았다. [CRSP US Stock Databases](https://indexes.morningstar.com/research-data-products/crsp-us-stock-databases), [CRSP CIZ 데이터 안내서](https://www.crsp.org/wp-content/uploads/guides/CRSP_US_Stock_%26_Indexes_Database_Guide_Flat_File_Format_2.0.pdf)
- S&P DJI 자료는 구성 변경 공지를 통한 특정 지수의 편입·편출 대사에 일부 쓸 수 있으나 미국 전체 시장의 유니버스가 아니다. S&P DJI 법적 고지는 사전 서면 허가 없이 자료를 수정·복제·배포하거나 데이터베이스/검색시스템에 저장하지 못하도록 제한한다. [S&P DJI 법적 고지](https://www.spglobal.com/spdji/en/disclaimers/)
- SEC EDGAR 자료는 무료이고 1994년 이후 공시 인덱스 및 회사 신고서를 제공하지만, OHLCV 가격 데이터가 아니다. 따라서 상폐·기업행사 공시를 조사하는 보조자료이지 일별 PIT 가격 패널을 대신하지 않는다. [SEC EDGAR 자료 접근 안내](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data)

**판정:** 기존 미국 게이트를 새로 열 자료는 없다. CRSP/WRDS 기존 기관 이용권 존재 여부는 현재 세션에서 확인되지 않았으며, 구매·로그인·공급자 연락은 하지 않았다. 미국 후보 수는 0개다.

## 병렬 독립 감사 결과 — 요약

세 시장에 대해 별도 읽기 전용 검토를 병렬로 수행했다. 검토자들은 로컬 가격행, 공유 장부, R12 파일을 열거나 수정하지 않았고 API 호출·계정 신청·다운로드·테스트를 하지 않았다.

- **코인:** Binance Vision이 공개 원천 중 가장 가까운 경로지만 2018년 동일 30개 PIT 코호트와 상폐 최종 결과는 입증되지 않았다. CryptoDataDownload는 별도 무료 카탈로그 후보이나 심볼별 2018/2022 공통 범위와 원천 데이터 재이용 권한이 미확인이라 입력으로 승격하지 않는다.
- **한국:** KRX 카탈로그의 2010년 이후 일별 시세는 기간상 2018·2022를 포함할 수 있으나, PIT/상폐 전량·최종 대가가 불명이며 API 이용은 약관 동의와 키 신청을 요구한다. 계약 종료 후 제공정보 이용이 금지되어 장기 재현용 캐시 권리가 확보되지 않았다.
- **미국:** 무료 공개자료 중 OHLCV·PIT 구성·상폐 최종값을 연구용으로 함께 허용하는 경로를 찾지 못했다. CRSP는 가장 가까운 licensed source이고, S&P 구성 자료는 별도 저장/복제권이 필요할 수 있다. SEC는 공시 보조자료이지 시세 패널이 아니다.

**누적 판정:** 세 시장 모두 추가 데이터 접근 또는 이미 보유한 이용권 증거가 없으면 적격 탐색·고정 G 검증으로 갈 수 없다. 코인 0개, 한국 0개, 미국 0개 후보이며 기존 문서의 고정 기준·라운드 기록을 임의로 바꾸지 않는다.

## 추가 공개 데이터 경로 감사 — 대체 코인 거래소 및 무료 KR/US 자료

이번 추가 조사는 공식 API/약관과 공개 데이터 설명만 확인했다. 파일 다운로드, API 호출, 계정 생성, 가격행 열람은 하지 않았다.

### 코인 현물 대체 거래소

- KuCoin의 공식 Spot klines 문서는 과거 조회에 명시된 시작 제한이 없고 요청당 최대 1,500개를 반환한다고 설명한다. 문서는 거래가 없던 간격은 응답에 포함되지 않을 수 있다고 경고한다. 그러므로 “제한이 기재되지 않음”은 2018년 자료 보유, 30개 공통 종목, 연속 봉, 역사적 상장 종목군을 증명하지 않는다. [KuCoin Klines API](https://www.kucoin.com/docs-new/rest/ua/get-klines)
- OKX 공개 과거 파일 안내는 캔들 자료 시작을 2023년 7월로 표시해 고정 2018·2022 약세장 조건을 충족하지 않는다. 별도 약관은 해당 파일의 개인 보유·자기 매매전략 개발을 허용하는 제한적 무상 라이선스를 설명하지만, 이용권이 있어도 필요한 과거 구간이 없다. [OKX 과거 자료 안내](https://www.okx.com/historical-data), [OKX 과거 자료 약관](https://www.okx.com/help/historicaldata-terms-and-conditions)
- Poloniex API 문서는 캔들 시작·종료 시각과 요청당 최대 500개를 설명하지만, 2018년 보관 범위·완전성·연구용 저장 권한은 해당 문서로 확인되지 않는다. HTX 공개 문서의 캔들 요청 제한도 역사적 기준일 유니버스와 장기 커버리지를 입증하지 못한다. [Poloniex Market Data API](https://api-docs.poloniex.com/spot/api/public/market-data), [HTX Spot API 문서](https://huobiapi.github.io/docs/spot/v1/en/)

**판정:** 조사한 대체 현물 거래소 중 어느 것도 동일한 고정 코호트의 2018·2022 자료, 연속성, 당시 상장 유니버스와 사용권을 함께 입증하지 못했다. 코인 데이터 게이트는 계속 닫혀 있고 새 실험은 시작하지 않았다.

### 한국 주식 무료 공식 API

- 공공데이터포털의 금융위원회 상장종목 API는 “현재 상장” 종목을 대상으로 설명하며 날짜 검색 필드와 무료 사용을 표시한다. 주식 시세 API는 날짜별 OHLCV 필드를 제시한다. 두 서비스 모두 인증키가 필요하고 공공누리 제4유형(출처표시·비상업적 이용·변경금지·무단 재배포 금지)이다. 공개 설명은 2007년부터의 이력, 상장폐지 종목 완전성, 본 전략 연구 기록에 대한 적용 권리를 확정하지 않는다. [금융위원회 상장종목 정보 API](https://www.data.go.kr/data/15094775/openapi.do), [금융위원회 주식시세 API](https://www.data.go.kr/data/15094808/openapi.do)
- 금융위원회 기업공시 API는 파산·회생·해산·합병·주식교환·감자 등 사건을 제공하고 이용조건 제한 없음으로 표시한다. 사건 정보만으로 일별 가격, 모든 종목의 상장폐지 최종 회수액, 지급 시점은 대체되지 않는다. 주식발행정보 API는 상장·상장폐지일 필드가 있지만 공공누리 제2유형이며 가격·회수 대가 데이터가 아니다. [금융위원회 기업공시 API](https://www.data.go.kr/data/15059649/openapi.do), [금융위원회 주식발행정보 API](https://www.data.go.kr/data/15059607/openapi.do)

**판정:** 무료 공식 API 설명은 종목·가격·사건의 일부 필드를 확인시켜 줄 뿐, 고정 사전등록의 역사적 종목군·가격 완전성·상폐 대가와 필요한 연구 이용권을 입증하지 않는다. API 키가 현재 확인되지 않았고, 이 조사에서 신청·발급·호출하지 않았다. 한국 데이터 게이트는 닫혀 있다.

### 미국 무료 공개 자료

- ML4T Wiki Prices 문서는 상장폐지 종목을 포함한 미국 주식 3,199개, 1962년부터 2018-03-27까지의 자료를 설명한다. 종료 시점이 고정 연구의 2026년 cutoff보다 이르고, 원본의 재배포·연구 기록 이용권과 종목별 최종 상폐 대가도 이 문서만으로 확인되지 않는다. [ML4T Wiki Prices 자료 설명](https://github.com/ml4t/data/blob/main/docs/providers/wiki_prices.md)
- `YLiu95/delisted-equity-data`는 미국 상장폐지 사건 약 515건을 열거하며, 저자 설명상 2008년 이후 SEC Form 25/15 기반 461건과 그 이전의 선별 사례 약 50건으로 구성된다. 해당 저장소도 완전한 전체 유니버스가 아니라고 명시하고, 일별 OHLC와 최종 회수액을 제공하는 패널이 아니다. 저장소 화면에서 명시적 라이선스를 확인하지 못했다. [Delisted Equity Data 및 출처 설명](https://github.com/YLiu95/delisted-equity-data), [자료 출처 목록](https://github.com/YLiu95/delisted-equity-data/blob/main/SOURCES.md)

**판정:** 이 자료들은 조사 대상을 좁히는 참고 경로일 뿐, 사전등록된 2007–2026 미국 전체 PIT 일별 패널과 종료 대가의 증거가 아니다. US 데이터 게이트는 닫혀 있다.

### 이번 갱신 이후 상태

새로 확인한 공식 문서나 무료 공개 자료는 어느 시장의 고정 게이트도 열지 못했다. 후보 수는 코인 0개, 한국 0개, 미국 0개다. 데이터 권리·역사적 유니버스·필수 구간·연속성 중 하나라도 확인되지 않은 상태에서는 가격 데이터를 수집하거나 백테스트를 실행하지 않는다.
