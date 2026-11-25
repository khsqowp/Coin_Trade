# 데이터 경로 후속 조사 — 2026-11-25

## 결론

새로 확인된 자료는 일부 시장에서 추가 검토할 가치가 있지만, 현재 6개 전략 목표의 데이터 게이트를 열지 않는다. Binance Spot의 공식 아카이브는 2018년 캔들 파일을 지원하는 경로이나 기존 Binance USDⓈ-M 선물과 다른 상품이다. 한국 주식은 적격한 새 무료 전체 패널을 찾지 못했다. 미국 주식은 무료 소표본 경로와 유료 상폐 포함 아카이브가 확인됐으나 고정 G의 전 기간·이용권 증거가 부족하다.

이번 조사는 공식·제공자 문서와 카탈로그만 확인했다. API 요청, 계정 생성, 파일 다운로드, 가격행 열람, 구매·문의, 장부 기록, 사전등록·백테스트 변경은 없었다.

## 코인 — 공식 Binance Spot 아카이브

- Binance 공식 `binance-public-data` 저장소는 공개 데이터가 일별·월별 파일이며 Spot 데이터에 `klines`가 포함되고 모든 심볼을 지원한다고 설명한다. 파일에는 체크섬이 제공되며, 과거 수정 파일과 체크섬을 기록한 변경 내역도 공개한다. 공식 예시 경로는 Spot 월별 `1h` 캔들이며, 공식 스크립트는 2018년을 포함한 연도 목록으로 해당 경로를 구성한다. [공식 저장소 README](https://github.com/binance/binance-public-data), [공식 월별 klines 예시 스크립트](https://github.com/binance/binance-public-data/blob/master/shell/download-klines.sh)
- 공식 약관은 2026-08-26 갱신 문서에서 비상업 용도를 학술 연구, 비수익 교육 프로젝트, 개인의 비생산 연구 목적의 과거 알고리즘 백테스트 및 비상업 오픈소스 평가로 제한한다고 설명한다. 이 프로젝트의 로컬 연구가 이 범위에 해당하는지에 대한 법률 판단은 하지 않았다. [Binance Public Data 이용조건](https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md)
- 이 경로는 기존 USDⓈ-M 무기한 선물 결과를 대체하지 않는다. Spot 캔들에는 선물 funding이 없고, 선물과 현물은 체결시장·가격·비용이 다르다. Spot에서 별도 전략 가설과 비용모형을 사전등록해야 하며 과거 선물의 R11/R12 결과와 합치면 안 된다.
- Binance 공식 공개 인덱스의 BTCUSDT Spot 월별 `1h` 디렉터리를 브라우저에서 확인했다. 목록에는 `2018-01`~`2018-12` 및 `2022-01`~`2022-12`의 ZIP과 각각의 `.CHECKSUM` 파일이 모두 표시됐다. 이는 해당 월별 객체 이름이 있다는 메타데이터 증거다. ZIP을 내려받거나 체크섬 내용과 파일 바이트를 검증하지 않았고, 내부 행·연속성도 확인하지 않았다. [BTCUSDT Spot 1h 아카이브 목록](https://data.binance.vision/?prefix=data/spot/monthly/klines/BTCUSDT/1h/)
- 공식 인덱스의 상위 Spot 월별 klines 목록은 3,768개 심볼 디렉터리를 표시했다. 이는 현 아카이브 디렉터리 수이지, 2018년 당시 상장 유니버스 수가 아니다. 2018년과 2022년의 월별 공통 30개 심볼·당시 상장/상폐 구성·PIT 코호트는 아직 추출·대사하지 못했다. 따라서 이 자료는 **BTC 단일 심볼의 파일 경로와 기간 존재는 확인됐지만, 30심볼 G 데이터 게이트는 미통과**다.
- 공식 공개데이터 저장소 이슈 #479는 전체 과거 심볼 목록(상폐·이름 변경·재상장 포함)과 일별 아카이브 경계 의미를 요청하는 공개 질문이다. 확인한 페이지에는 이 범위를 확정하는 관리자의 답변이 없었다. 공식 `fetch-all-trading-pairs.sh` 스크립트는 현재 `exchangeInfo`를 조회하므로 과거 유니버스 자료로 대체할 수 없다. 체크섬은 개별 아카이브 파일의 무결성 점검 수단이지, 과거 유니버스 완전성이나 봉 연속성 증명은 아니다. [공식 공개데이터 이슈 #479](https://github.com/binance/binance-public-data/issues/479), [현재 심볼 목록 스크립트](https://github.com/binance/binance-public-data/blob/master/shell/fetch-all-trading-pairs.sh)
- Angolin은 Binance Spot 약 3,600개 페어의 `1d`, `1h`, `1m` OHLCV와 상폐 페어 이력을 제공한다고 설명한다. 2026-10-27 이전의 상장 유니버스는 시간별 봉, Binance 상장·상폐 공지, Internet Archive의 Binance 심볼 목록 스냅샷으로 재구성했다고 하며, 자체 비교 스냅샷과 99.97% 일치한다고 주장한다. 단, 이는 공급자 설명이며 일치율 분모·표본·제외 기준을 이 문서만으로 검증할 수 없다. 문서상 아카이브 공백에 공지나 스냅샷도 없으면 상장 기간이 누락될 수 있다. [Binance 커버리지·유니버스 방법](https://angolin.com/docs/exchanges/binance)
- Angolin의 공개 카탈로그는 Binance 거래쌍과 각 페어의 첫·마지막 실제 봉 시각을 제공한다고 문서화돼 있지만, 날짜 범위만으로 내부 봉 연속성을 보증하지 않는다. 다운로드 안내에는 `universe_binance_usdt_periods.parquet` 예시 파일명이 나오지만, 검토한 문서에서는 실제 공개 다운로드 URL이나 그 파일의 접근·재사용 조건을 확인하지 못했다. 별도 Universe API는 API 키와 구독 플랜의 과거 범위가 필요하다. 공개 카탈로그는 무인증·무과금이라고 문서화돼 있으나, 해당 catalog 응답에는 시점별 전체 상장 기간이 아니라 봉의 첫·마지막 시각만 있다고 안내돼 있다. 따라서 Angolin은 **PIT 유니버스를 재구성하려는 유력한 조달 경로**지만, 실제 접근성·권리·가격과 2018·2022 공통 30심볼·OHLCV 연속성은 미확인이고 G 데이터 게이트는 미통과다. [Periods 다운로드 스키마](https://angolin.com/docs/download/universe/periods), [공개 카탈로그 문서](https://angolin.com/docs/endpoints/catalog), [Universe API 문서](https://angolin.com/docs/endpoints/exchange-universe), [인증·플랜 범위](https://angolin.com/docs/authentication)
- CryptoDataDownload의 2026-06 카탈로그도 Binance Spot 일봉·시봉·분봉을 공공 무료로 표기하지만, 같은 카탈로그의 무료 요약은 공개 일봉 CSV를 명시하고 익명 API 사용은 카탈로그 탐색으로 제한한다. 실제 심볼별 일자 표와 파일 사용 권리는 아직 대사되지 않았다. 제공자 약관은 자료를 비상업 용도로만 쓰도록 하고 정확성·제3자 권리를 보증하지 않는다. 이를 Binance 공식 아카이브와 혼동하거나 출처 검증을 생략하지 않는다. [CDD 카탈로그](https://api.cryptodatadownload.com/static/catalog/CDD_Data_Catalog.html), [CDD 이용약관](https://www.cryptodatadownload.com/terms-of-use/)
- CryptoHFTData는 Binance·여러 거래소 L2/체결 자료를 무료 제공한다고 설명하지만, 공식 커버리지 안내상 보관 시작은 2025-06-28이다. 2018·2022 게이트에 쓸 수 없다. [CryptoHFTData 이용조건](https://www.cryptohftdata.com/terms), [자료 범위 및 가격](https://www.cryptohftdata.com/pricing)

## 한국 주식 — 이용권 변경 예정, 데이터 게이트는 미통과

금융위원회 공공데이터포털 공지는 주식시세와 KRX 상장정보를 포함한 10개 API의 이용허락조건을 기존 제4유형에서 제1유형으로 **2026-12-17부터** 바꾸며, 기존 버전 API에도 변경 조건을 적용한다고 안내한다. 이는 현재 날짜(2026-11-25) 기준 아직 시행 전이며, 출처표시 조건 완화가 예정된 것이다. 과거 기간의 전체 가격, 당시 상장 유니버스, 상폐 후 최종 회수액, 봉 연속성, 이 프로젝트가 실제 보유한 접근권은 입증하지 않는다. 시행일 이후 조건을 다시 확인해야 한다. [공식 공지](https://www.data.go.kr/bbs/ntc/selectNotice.do?originId=NOTICE_0000000005172)

KRX 상장폐지 종목 화면은 일별 OHLCV와 상폐일·사유 필드를 표시하지만, 전체 기간·최종 정산가·완전성·자동수집 및 보관 권리를 보장하는 근거는 아니다. 금융위 주식시세 API 설명은 티커별 OHLC를 제공하지만 과거 커버리지 시작점, 상폐종목 포함 여부, 연속성은 확인되지 않았다. KRX 상장종목 API는 특정 기준일의 목록을 보조할 뿐 과거 PIT 전체 이력을 입증하지 않는다. 발행정보 API와 DART 공시는 상장·상폐 사건과 주식 수 등 보조 자료이지, 모든 종목의 최종 회수액 패널이 아니다. [KRX 상폐 시세 화면](https://data.krx.co.kr/contents/MDC/STAT/issue/MDCSTAT239.jsp), [금융위 주식시세 API](https://www.data.go.kr/data/15094808/openapi.do), [KRX 상장종목 API](https://www.data.go.kr/data/15094775/openapi.do), [주식 발행정보 API](https://www.data.go.kr/data/15043423/openapi.do)

KRX OPEN API 서비스 목록은 유가증권·코스닥 일별 매매정보와 종목기본정보의 제공 시작일을 2010-01-04로 표시한다. 이는 G의 2018·2022 기간을 포함하는 공식 가격자료 후보를 특정한다. 단, 서비스 설명은 “상장되어 있는 주권”이라고만 하며 상장폐지 종목의 과거 행, 기준일별 전체 종목 상태, 마지막 회수액이 포함되는지 증명하지 않는다. 개별 서비스는 인증키와 이용신청이 필요하다. 현재 KRX OPEN API 약관은 비상업 목적만 허용하고, 제공 결과의 제3자 제공을 금지하며, 이용 계약 종료 후에는 제공 정보를 이용할 수 없다고 규정한다. 키 발급, 실제 자료 접근, 장기 로컬 보관 범위는 확인하지 않았다. 이 약관은 금융위 API의 2026-12-17 예정 이용조건 변경과 별도이므로 그 변경을 KRX OPEN API에 확대 적용하지 않는다. [KRX OPEN API 서비스 범위](https://openapi.krx.co.kr/contents/OPP/INFO/service/OPPINFO004.cmd), [유가증권 일별 매매정보](https://openapi.krx.co.kr/contents/OPP/USES/service/OPPUSES002_S2.cmd?BO_ID=JvJFzlAENzZlPBDNGAWC), [종목기본정보](https://openapi.krx.co.kr/contents/OPP/USES/service/OPPUSES002_S2.cmd?BO_ID=PiwgMdTwmsenXhmqqxuj), [KRX OPEN API 이용약관](https://openapi.krx.co.kr/contents/OPP/INFO/OPPINFO002.jsp)

계정·키·API 응답·내보내기 이용조건을 확인하거나 데이터를 취득하지 않았다. 한국 후보는 계속 0/2다.

## 미국 주식 — 공개 범위와 비용 경계

- OHLC의 제공자 문서는 무료 등급에서 AAPL, NVDA, JNJ, PEP, MSFT, QQQ 여섯 종목의 일봉을 최근 5년 제공한다고 설명한다. 과거 시점 조회(`as_of`)와 거래가 끝난 종목의 instrument ID 기능도 소개하지만, 무료 등급의 고정 6종목·5년은 2018 및 전체 상폐/PIT 코호트 기준을 충족하지 않는다. 유료 Developer는 미국 전체 종목의 5년, Pro는 15년, 더 높은 요금제는 전체 이력을 표기한다. 가격행·실제 이용권·종목 범위는 호출하지 않았다. [OHLC 과거 주가 데이터 문서](https://ohlc.io/data/historical-stock-prices)
- HistoricalData.net은 2003-10 이후 일봉·분봉과 상폐 티커를 포함한다고 광고하고 일회성 구매 가격을 일봉 USD 190, 분봉 USD 670으로 표시한다. 사이트는 주식 아카이브에 대한 거래소 기준 전체 검증 결과를 제시하지 않았고, 표본 비교는 옵션 자료의 특정 표본에 관한 것이다. 상폐가치·PIT 유니버스·현 프로젝트의 이용권을 보장하는 근거로 볼 수 없다. 지출 승인이나 데이터 취득은 없었다. [자료 안내·가격·필드 예시](https://historicaldata.net/)
- HistPrice는 시장 전반의 일봉·시봉 및 상폐/PIT 범위를 광고하지만, 요금표상 무료는 월 100만 봉이며 PIT 편입·상폐와 대량 Parquet는 USD 49 Quant 등급으로 기재돼 있다. 상단의 “전체 데이터” 설명과 등급별 기능 설명을 함께 보아야 한다. 제공된 원천·실제 종목별 커버리지·품질 대사·저장 및 사용권은 확인하지 않았다. 따라서 무료 경로로 G를 열 수 있다고 판정하지 않는다. [HistPrice 기능과 가격](https://histprice.com/)
- Nasdaq Data Link의 Sharadar Equity Prices (`SEP`)는 1998년부터 21,000개 이상 미국 기업의 일별 OHLCV를 제공하고 활성·상폐 티커를 포함한다고 설명한다. 조정·비조정 가격과 기업행위 자료가 별도 표로 나뉘며, corporate actions 문서는 상장·상폐일과 상폐 사유, 티커 변경 등을 열거한다. 데이터셋은 Premium이고 가격 확인·API 접근에는 계정/API 키가 필요하다. 이 설명은 상폐 후 최종 회수금이나 전체 PIT 유니버스 완전성을 입증하지 않으며 실제 이용권·추출물도 확인하지 않았다. 따라서 Sharadar는 CRSP와 함께 **문서상 유력한 유료 조달 후보**로만 기록한다. [Nasdaq Sharadar SEP 문서](https://data.nasdaq.com/databases/SEP/documentation?anchor=sample-data), [Sharadar 가격 문서](https://sharadar.com/docs/stocks), [기업행위 필드 문서](https://sharadar.com/docs/actions)
- CRSP는 미국 주식의 일별·월별 자료와 기업행위, 영구 식별자, 현재 및 상장폐지 종목을 포함하는 생존편향 방지 이력을 제공한다고 설명하는 강한 후보 경로다. CRSP 설명서의 상장폐지 수익률 정의는 상장폐지 후 금액·분배금 및 일부 미해결 결측 코드를 다루므로 실제 추출물에서는 결측 처리와 회수값 정의까지 대사해야 한다. 이 자료는 라이선스 상품이며, 현재 프로젝트의 구독·이용권·보관권 및 실제 추출물의 기간·종목 완전성은 확인되지 않았다. 따라서 CRSP는 **문서상 유력한 유료 경로**일 뿐, 현재 열려 있는 데이터 게이트가 아니다. [CRSP 미국 주식 DB](https://www.crsp.org/research/crsp-us-stock-databases-2025-layout/), [CRSP 데이터 설명서](https://www.crsp.org/crsp_pdf/crsp-us-stock-indexes-databases-data-descriptions-guide-crspaccess/)
- 위 두 유료 제공자의 상품은 잠재적 조달 경로로만 기록한다. 사용자는 지출을 명시적으로 승인하지 않았고, 현재 자료 설명만으로는 고정 G를 충족한다고 입증되지 않았으므로 구매·문의·계정 생성은 하지 않는다. 미국 후보는 계속 0/2다.

## 다음 검증 순서

1. Binance Spot을 연구 경로로 검토할 경우, 기존 선물 가설과 분리된 신규 사전등록 여부부터 정한다. Angolin의 과거 재구성 기준·분모가 명확한 검증 자료·가격·이용권을 문서로 먼저 확인한다. 유료·계정 전용 자료는 승인 전 취득하지 않는다. 이후 적법한 메타데이터 접근이 확보되면 2018·2022 동시 상장 30심볼, 시점별 전체 유니버스, 월별 파일 체크섬과 연속성을 각각 대사한다. 하나라도 증명하지 못하면 게이트 실패로 기록한다.
2. 한국은 KRX OPEN API가 2010년부터 제공한다고 명시한 가격 범위가 상폐 종목까지 포함하는지, 과거 종목기본정보가 시점별 PIT 목록을 재현하는지, 계약 종료 뒤 보관·연구 사용을 허용하는지 공식 문서로 확인한다. 금융위 API 이용조건은 2026-12-17 시행 후 별도로 재확인하되, 그 변경만으로 데이터 게이트를 통과시키지 않는다.
3. 미국은 CRSP·Sharadar 등 유료 경로에서 실제 접근권을 전제하지 말고, 취득 전 고정 G가 요구하는 전체 기간·PIT·종료가치·기업행위·보관 및 사용권을 문서로 확인한다. 지출은 별도 명시 승인 전 하지 않는다.
4. 이 증거가 준비되기 전에는 R12를 실행하거나 결과를 장부에 쓰지 않는다. 전략 후보 수는 코인 0/2, 한국 0/2, 미국 0/2로 유지한다.
