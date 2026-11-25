# 자료 게이트 재점검 — 2026-11-24

## 판정

이번 재점검으로 시장별 원시 성과 실험을 새로 시작할 수 있는 게이트는 열리지 않았다. 코인 R4는 계속 실행 중이어서 공유 TRAIN 장부를 쓰는 추가 실험을 겹치지 않았다. 세 시장 모두 검증 후보 수는 변하지 않았다: 코인 오더블록 0/2, 한국주식 0/2, 미국주식 0/2.

## 연구 목표의 검증 문턱

전략 후보는 TRAIN 수익만으로 승격하지 않는다. 프로젝트 규칙상 시간순 60/40 분할, 사전등록한 파라미터·비용·시도 수, 다중검정 보정, 2018·2022 레짐 확인, 비용 2배와 1봉 지연, 파라미터 주변 평탄도, 미사용 종목 검증이 필요하다. 코인 게이트 코드는 전체 완료 신호의 target-first 비율 80% 이상과 심볼별 비중복 M2 표본 200개 이상을 따로 요구한다([gate_check.py](/Users/user/CODE/Coin_Trade/scratchpad/strategy_bt/orderblock_loop/gate_check.py:214)). 통과 후보 2개는 pairwise OOS 일별수익 상관도 0.5 미만이어야 독립 전략 2개로 센다([PREREG.md](/Users/user/CODE/Coin_Trade/scratchpad/strategy_bt/orderblock_loop/PREREG.md:767)).

## 한국주식: 기존 상장폐지 가격 파일은 사용 자격이 없다

파일 목록과 매니페스트 메타데이터만 확인했다. `/Users/user/CODE/trading_data/external/equities/kr/daily_stocks_delisted.parquet`은 2,345,921행, 1996-01-30~2026-11-19로 기록돼 있고, 매니페스트는 FinanceDataReader의 Naver fchart 조정가격 수집물로 출처를 표시한다. 원시 Parquet 행은 열지 않았다.

Npay 증권 공식 고객센터는 증권 정보가 콘텐츠 제공사와의 유료 계약으로 제공되며, 서비스 화면 직접 열람을 벗어난 재가공·개인 프로그램 사용과 제3자 재배포를 금지한다고 명시한다. 따라서 이 파일을 전략 연구 코드에서 읽거나 백테스트에 사용하지 않는다. [Npay 증권 정보 이용 안내](https://help.pay.naver.com/faq/content.help?faqId=17106)

별도 확인된 `equity_membership_kr.csv`에는 `alive_from/alive_through` 필드가 있지만, 이는 현재·상폐 종목 목록과 월별 첫/마지막 관측일에 기댄 생존기간 보조표다. 정확한 IPO·상폐일 또는 KOSPI200 같은 지수의 과거 구성·비중 이력을 보증하지 않으며, 상폐 종목 목록의 역사적 완전성과 ISIN 연결도 보증되지 않는다. 과거 가격 완전성과 최종 상폐 회수값도 해결하지 않는다.

별도 KRX API 경로도 승인된 계정·키와 이용 목적 승인 없이 자동 호출하거나 다운로드하지 않는다. 파일의 과거 가격 보유 사실만으로 이용권·기업행위 품질·PIT 지수구성 이력이 해결됐다고 판정하지 않는다. 한국주식 트랙은 계속 `DATA_BLOCKED`다.

정부 공공데이터포털의 무료 대안도 확인했다. 금융위 주식시세정보 API는 KRX 상장주식 OHLCV를 종목·기준일로 조회하게 해주지만, 상장폐지 종목의 과거 보존 범위는 명시하지 않고 `serviceKey`가 필요하다. 이용 조건은 공공누리 4유형(비상업·변경금지)이며 제3자 무단 제공·재배포도 금지한다. 주가를 정규화해 총수익을 구성하는 연구에 그대로 쓰기 어려운 권리 조건이다. [주식시세정보](https://www.data.go.kr/data/15094808/openapi.do)

금융위 지수시세정보는 2020-01-01 이후 KOSPI 등 지수 값이며 과거 구성종목·비중 이력을 제공하지 않는다. 주식발행정보·공시정보에는 상장/상폐일과 배당·증자·감자 공시 일부가 있지만, 일별 OHLC·조정계수·TR 수익률 또는 과거 지수 유니버스가 아니다. 이 API들도 인증키가 필요하고, 주식발행정보는 비상업 조건 또는 상업 이용 시 KSD 계약이 필요하다. [지수시세정보](https://www.data.go.kr/data/15094807/openapi.do), [주식발행정보](https://www.data.go.kr/data/15043423/openapi.do), [공시정보](https://www.data.go.kr/data/15059649/openapi.do)

## 미국주식: 기존 로컬 자료로 G 충족 실험 불가

매니페스트에는 Yahoo 일별 주식·ETF 패널과 1996~2019년 S&P500 구성 이력이 있다. 구성 파일은 `date,tickers`만 담고, 제거 종목의 일별 가격·상장폐지 최종 정산이 없다고 기존 카탈로그가 기록한다. 현재 로컬 데이터에는 종목 생존기간(`alive_from/alive_through`) 및 상폐가격 패널이 확인되지 않았다. SPY 단일 자산 거시 오버레이는 미사용 종목 기준을 충족하지 못하며, cutoff 전용 입력 계약·거래소 달력·자료 이용권도 아직 확인되지 않았다. 따라서 실데이터 교차단면 연구를 실행하지 않는다.

공식 공급 경로를 추가 대조했다. CRSP는 일별·월별 시장자료와 기업행동을 활성·비활성 36,000개 이상 종목에 대해 제공하고 영구 ID로 시계열 연결을 지원한다고 명시하지만, 기관·정부기관·투자 실무자 대상 구독 데이터이며 공개 가격은 없다. 필드별 상폐 후 최종 정산 범위와 개인 연구자의 이용권은 제품 가이드·계약에서 별도 확인해야 한다. [CRSP 제품 설명](https://indexes.morningstar.com/research-data-products/crsp-us-stock-databases)

NYSE Daily TAQ는 1993년부터 미국 통합 테이프의 전 종목 거래·호가를 제공하지만, 기업행동·상폐 최종 회수액·과거 지수구성원을 단독으로 제공하지 않는다. 2026년 10월 가격표 기준 상업용 구독은 월 $3,800, 최소 12개월이며, 추가 과거자료는 월별 콘텐츠 $500이다. 학술가격은 공개되지 않아 확인하지 않았다. [Daily TAQ 범위](https://www.nyse.com/data-products/catalog/daily-taq), [공식 가격표](https://www.nyse.com/publicdocs/nyse/data/NYSE_Historical_Market_Data_Pricing.pdf)

S&P DJI 역사 구성종목 정보도 별도 라이선스가 필요한 자료로 안내돼 있다. SEC EDGAR는 Form 25/25-NSE 상장폐지 통지를 제공하지만, 해당 통지 자체는 가격이나 최종 회수액을 제공하지 않는다. 따라서 현재 확인한 무료 공개 자료만으로 가격·기업행동·비활성 종목·PIT 유니버스를 모두 채우는 경로는 없다. [S&P DJI 역사 구성원 접근 안내](https://pages.marketintelligence.spglobal.com/SP-Dow-Jones-Indices-Constituent-Removal.html), [SEC 거래소 상장폐지 기록](https://www.sec.gov/rules-regulations/exchange-delistings)

## 코인 오더블록: 제한된 진단 입력과 검증 불가 구간

카탈로그·기존 데이터 사전 점검을 재대조한 범위에서 Binance UM의 4시간 봉은 35개 파일 중 32개가 비어 있지 않지만, 2018년에 시작하는 적격 선물 심볼은 0개다. Funding 입력은 카탈로그상 2020년부터이며, R9 사전점검에선 6개 심볼의 funding mark 연결 여부가 남아 있다. 따라서 R9는 R4 완료 후 TRAIN 진단을 할 수 있어도 2018 약세장·PIT·funding 게이트를 충족하는 후보 검증이 아니다.

UM `bookDepth`는 약 30초 간격의 누적 깊이 스냅샷으로 기록된 파일 94개, BTC·ETH 2개 심볼, 2023-01~2026-11-19 범위다. 이는 원시 호가 이벤트 L2가 아니고 2018/2022 레짐을 포함하지 않는다. BTC·ETH 일부 기간 파일럿의 입력 가능성은 남지만, 스키마·연속성·cutoff·이용권 검증 전에는 실행 적격 자료로 세지 않는다. R10은 공통 적격 심볼 7/30이라 현 사전등록 기준에서 실행할 수 없다.

대안 공식 아카이브로 Gate.io도 문서만 확인했다. 거래소는 2018년 12월 FAQ에서 당시 perpetual 계약을 BTC/USDT 기준으로 설명하고, XMR·XLM perpetual 출시 공지는 2019년 1월이다. 과거 데이터 안내는 캔들·체결·호가·마크가격·펀딩 CSV를 설명하며 2018 월별 경로 예시가 있으나, 그 예시는 파일의 실제 존재나 계약별 시작일을 보증하지 않는다. 현재 다운로드 인덱스에서 확인되는 캔들/체결은 2023-01+, depth는 2021-08+다. 그래서 2018년 30개 perp 종목·funding·PIT cohort와 사용권을 증명하지 못한다. API·다운로드를 수행하지 않았다. [2018 perpetual FAQ](https://www.gate.com/pt/help/futures/perpetual/16695), [2019년 XMR/XLM 출시 공지](https://www.gate.com/announcements/article/16746), [Gate 과거 데이터 안내](https://www.gate.com/zh-tw/announcements/article/21688), [현재 다운로드 인덱스](https://www.gate.com/pt-br/developer/historical_quotes)

기존 Binance spot 1분봉 매니페스트를 경로명·월·심볼·행 수 메타데이터만으로 제한 집계했다. 2026-05까지 33개 심볼에 2,249개 월 파일이 있다. 2018년 어느 달이든 자료가 있는 심볼은 8개뿐이고, 2018년 12개월 파일이 모두 있는 심볼은 BTCUSDT·ETHUSDT·BNBUSDT·LTCUSDT 4개다. 2022년 12개월 파일이 모두 있는 심볼은 23개다. 월 파일 존재는 분봉 내부 연속성이나 당시 상장 유니버스를 증명하지 않는다. 현재 Binance Vision 약관은 순수 개인·비상업·비생산 목적의 역사적 백테스트를 허용하지만, 해당 파일의 취득 시점 약관·provenance는 확인되지 않았다. R4의 선물 전략 정의를 spot으로 바꾸면 funding·숏 체결 규칙도 달라지므로 기존 사전등록의 대체로 실행하지 않는다. 별도 사전등록을 하더라도 2018년 30심볼 요건에 못 미쳐 G 검증 입력으로는 불충분하다. [Binance 공개 데이터 안내](https://github.com/binance/binance-public-data/), [현재 Binance Vision 약관](https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md)

## 작업 경계 및 다음 순서

- R4 PID 30488은 이번 확인 때도 실행 중이었다. 프로세스 종료·재시작 또는 공유 장부 열람은 하지 않았다.
- KRX/Naver, Yahoo, 코인 데이터의 원시 가격 행을 열거나 다운로드하지 않았다. 2026-06-01 이후 데이터는 연구 입력으로 읽지 않았다. 위 날짜는 파일 매니페스트의 메타데이터 표기만 인용한다.
- 계정·API 키 신청, 유료 데이터 구매, API 호출, 서버·실거래 변경, 커밋·푸시는 없었다.
- 유료 자료 비용은 조사 메모에만 기록했다. CRSP 구독료 및 NYSE 학술 요금은 공개되지 않았으므로, 어떤 구매도 승인·시작하지 않았다.
- R4가 끝난 뒤 R4 코드/데이터 지문과 완료 수를 대사한다. 그다음 R9 실데이터 TRAIN 여부를 사전등록과 데이터 기간에 맞춰 판정하되, 통과하지 못한 G 조건은 명시하고 후보로 세지 않는다.
- 한국·미국 트랙은 권한이 확인된 적격 데이터를 확보할 때까지 원시 성과 검색을 중단한다. 합성 테스트는 수익 증거가 아니다.

