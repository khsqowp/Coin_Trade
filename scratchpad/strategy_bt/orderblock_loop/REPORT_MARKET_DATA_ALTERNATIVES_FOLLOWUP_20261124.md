# 3개 시장 대체 데이터 경로 재조사 — 2026-11-24

## 결론

코인 오더블록·한국 주식·미국 주식의 현재 고정 데이터 게이트를 모두 충족하는 새 무료 공개자료 경로는 확인되지 않았다. 게이트는 그대로 닫혀 있고, 연구 후보는 여전히 0개다. 조사 대상은 공식 문서·약관·제품 설명뿐이며, API 호출·가격 행 열람·다운로드·계정 활동·장부 접근은 하지 않았다.

## 코인 오더블록: 2018년 동일 30개 파생자산 이력

- Binance 공식 자료에 따르면 Binance Futures는 2019년 9월 출시됐고 첫 USDT 담보 무기한 계약은 BTCUSDT였다. 따라서 2018년 Binance USDⓈ-M 선물 가격·펀딩 관측은 당시 존재하지 않았다. [Binance Futures 출시 공지](https://www.binance.com/en/support/announcement/detail/360033273472), [Binance의 출시 1주년 설명](https://www.binance.com/en/blog/all/421499824684900979)
- OKX 공식 2018년 상장 공지는 무기한 스왑이 12월 19일 BTC로 시작됐고, EOS·ETH·BCH/BSV·XRP가 12월 말 추가됐음을 보여준다. 연말에도 고정 30자산 요건에 못 미친다. [OKX 2018-12-19 출시 공지](https://www.okx.com/en-us/help/perpetual-swap-officially-launched-on-okx-website-and-app-12-19-2018), [공식 거래 공지 목록](https://www.okx.com/en-sg/help/section/announcements-trading-updates/page/31)
- BitMEX는 2016년 XBTUSD 무기한과 2018년 ETHUSD 무기한의 자료가 확인되지만, 공식 공개 문서만으로 2018년 전체 PIT 파생계약군이 동일 30개였는지, 각 계약의 OHLC·mark·funding 전 구간이 보존됐는지 증명되지 않았다. [XBTUSD 소개](https://www.bitmex.com/blog/site-announcement/2432), [ETHUSD 무기한 출시](https://www.bitmex.com/blog/announcing-the-new-ethusd-perpetual-contract), [공개 데이터 아카이브](https://public.bitmex.com/)
- Binance Public Data 저장소는 역사 데이터 이용조건과 선물 자료 종류를 안내하지만 2018년 Binance Futures 가격 자료의 부재를 해결하지 않는다. 마크·인덱스·프리미엄 캔들 보존 시작이 2020년이라고 설명된 자료도 확인됐다. [Binance Public Data](https://github.com/binance/binance-public-data), [다운로더 문서](https://github.com/binance/binance-public-data/blob/master/python/README.md?plain=1), [데이터 이용조건](https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md)

**판정:** 실패. 다른 거래소 가격을 Binance USDⓈ-M과 동일한 체결·펀딩 자료로 취급하지 않는다. 2022년 자료가 있어도 2018년 동일 30자산 코호트 부재를 메우지 못한다. 고정 G를 완화하지 않는다.

### 별도 Binance Spot 오더블록 challenger

Spot은 USDⓈ-M의 대체 자료가 아니라 별도 시장 연구로만 평가했다. Binance의 2018 회고는 연초 101개 코인·245개 거래쌍이라는 합계만 제공하고 전체 심볼 이름은 싣지 않는다. Binance의 현재 `exchangeInfo` 문서는 현행 거래 규칙·심볼 정보를 설명하며 과거 기준시점(as-of) 인수를 제공하지 않는다. 공식 Public Data 저장소는 월별 파일 규칙과 현재 거래쌍 조회 도구를 제공하지만, 2018-01-01의 동결 유니버스 manifest를 공개하지 않는다. [Binance 2018 회고](https://www.binance.com/en/blog/all/286445971261435904), [현재 exchangeInfo 문서](https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md#exchange-information), [Binance Public Data](https://github.com/binance/binance-public-data)

공식 월별 kline 파일이 2018년 1월에 존재하더라도 그 쌍이 1월 1일 전에 이미 상장되어 있었다는 사실까지 증명하지 않는다. 공식 상장 공지로 일부 개별 이벤트는 검증할 수 있지만, 현재 검토 자료에서 연초 전체 코호트를 구성하는 완전한 과거 snapshot이나 모든 상장·폐지 이벤트 원장은 확인하지 못했다. 이번 후속 조사에서도 S3 객체 키 전체 목록을 얻지 못해 동일 30개 자산의 2018·2022 각 월 파일 커버리지를 확인하지 못했다. 따라서 Spot 자체도 현 단계에서 PIT·30자산·두 약세장 데이터 게이트를 통과하지 못하며 후보로 세지 않는다.

## 한국 주식: OHLCV·상폐 처리·PIT 유니버스

- 금융위원회/KSD 주식발행정보 및 예탁가능정보는 상장·상폐 상태와 종목 메타데이터의 보조 근거가 될 수 있다. 해당 설명은 일별 가격, 정리매매 OHLCV, 상폐·합병 후 최종 현금/주식 대가를 제공한다고 하지 않는다. 2018·2022 당시 정보의 완전성·공표 시각도 입증되지 않았다. [주식발행정보 API](https://www.data.go.kr/data/15043423/openapi.do), [주식등록예탁가능정보 API](https://www.data.go.kr/data/15059607/openapi.do)
- OpenDART는 합병·주식교환·분할·감자·부도·회생·해산 등 공시를 찾고 일부 사건 대가를 보완하는 자료다. API 인증키/회원 등록이 필요하며, 공시 이벤트는 전 종목의 일별 가격 패널이나 표준화된 최종 총수익 정산 원장이 아니다. [OpenDART 주요사항보고서 안내](https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS005&apiId=2020053), [OpenDART 공시검색 안내](https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019001), [이용약관](https://opendart.fss.or.kr/intro/terms.do)
- KIND 상장폐지 현황과 상장업무 설명은 상장폐지 이벤트·절차의 보조자료다. 이 자료만으로 과거 상폐 전 일별 가격, 모든 정리매매 실제 체결가, 최종 proceeds와 가격 패널의 연결을 입증할 수 없다. [KIND 상장폐지 현황](https://kind.krx.co.kr/investwarn/delcompany.do?method=searchDelCompanyMain), [상장업무 해설서](https://kind.krx.co.kr/external/dst/reference/10827/%EC%9C%A0%EA%B0%80%EC%A6%9D%EA%B6%8C%EC%8B%9C%EC%9E%A5%20%EA%B3%B5%EC%8B%9C_%EC%83%81%EC%9E%A5%20%EC%97%85%EB%AC%B4%ED%95%B4%EC%84%A4%EC%84%9C.pdf)

**판정:** 실패. 상장상태와 기업행사 단서는 일부 보완할 수 있지만 OHLCV·당시 전체 유니버스·최종 정산·권리 및 기간 완전성이 함께 확인되지 않았다.

## 미국 주식: 전 시장 상폐 포함 패널

- SEC EDGAR API와 Form 25는 공시·상장폐지 이벤트의 보조 경로다. EDGAR는 일별 OHLC를 제공하지 않고, 공시 단위 검색만으로 전체 인수·청산 대가를 빠짐없이 연결할 수 없다. [SEC EDGAR API](https://www.sec.gov/search-filings/edgar-application-programming-interfaces), [SEC 상장폐지/Form 25 안내](https://www.sec.gov/rules-regulations/exchange-delistings)
- FINRA OTC Daily List는 OTC 종목의 추가·삭제·심볼 변경·일부 기업행사 기록을 제공하지만, OTC에 한정되고 전체 시장 가격·최종 proceeds를 제공하지 않는다. Nasdaq Historical Data는 종목별 최대 10년 안내이며, 비활성 종목 전체·전 거래소 범위·자동 수집 및 내부 저장 권리를 입증하지 않는다. [FINRA OTC Daily List](https://otce.finra.org/otce/dailyList?viewType=Dividends%2FD), [Nasdaq Historical Data](https://www.nasdaq.com/market-activity/quotes/historical)
- Nasdaq Daily List·NYSE TAQ 계열은 부분 이벤트/가격 자료의 유료 경로다. 이미 보유한 이용권은 확인되지 않았고, 전체 시장 PIT·정산 완전성도 무료 공개자료만으로 확인되지 않았다. [Nasdaq Daily List](https://data.nasdaq.com/databases/NDL/documentation?anchor=product-overview), [NYSE TAQ 자료 안내](https://www.nyse.com/publicdocs/nyse/data/Daily_TAQ_Client_Spec_v4.3.pdf)

**판정:** 실패. 가격·PIT 구성·기업행위/최종 정산·이용권을 함께 충족하는 무료 공개자료 조합을 찾지 못했다.

## 다음 단계와 금지된 우회

1. 각 시장에서 이미 적법하게 보유 중인 데이터의 이용권·기간·전 종목 범위·필드 빈티지·체크섬/행 수 근거가 확인되기 전까지 새 실험을 시작하지 않는다.
2. 유료상품은 사용자 승인 전 가입·견적 요청·구매하지 않는다. 인증키가 필요한 API는 현재 키/권한을 추측하지 않고 호출하지 않는다.
3. 2018년 파생 이력, 30자산 동일 코호트, 상폐·최종 정산, cutoff 또는 이용권이 부족하면 실패로 기록한다. 현물·다른 venue·현재 생존 종목을 같은 G의 대체재로 세지 않는다.

## 조사 범위 및 한계

공식 발표·API 문서·약관·상품 설명만 검토했다. 실제 데이터 커버리지·연속성·가격 성과를 조회하지 않았다. 계정 로그인, 인증키/API 호출, 파일 다운로드, 구매, 데이터 행 열람, 백테스트, 사전등록·코드·공유 장부 수정은 하지 않았다. Binance Futures의 2018년 부재는 공식 출시 시점으로 구조적으로 확인됐지만, BitMEX의 계약 수 및 2018년 전체 보존 범위는 공개자료만으로 확정할 수 없다.
