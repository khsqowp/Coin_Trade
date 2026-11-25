# 전략 연구 이어가기 기록 — 2026-11-24 후속

## 결론

검증 통과 전략은 아직 0개다. R4 코인 탐색은 기존 PID가 실행 중이라 보존했고, R9는 고정 데이터·단일 실행 슬롯·레드팀 게이트가 해결되지 않아 실데이터 TRAIN을 시작하지 않았다. 이번 작업은 R9 인과성/M2 연결 테스트 보강과 미국 후보의 합성 테스트 fixture 수정이다.

## 이번에 실제로 한 일

- `tests/test_search_crypto_r9.py`에 뒤쪽 봉을 크게 변형해도 이미 확정된 sweep/reclaim 판정이 바뀌지 않는지 검사하는 접두구간 불변성 테스트를 추가했다.
- 같은 파일에 발행된 신호 식별자가 진입 이벤트와 M2 진입·종료 시각에 연결되는지 검사하는 합성 테스트를 추가했다. 매매 규칙·비용·기준은 바꾸지 않았다.
- `tests/test_search_us_macro_overlay_v1.py`의 합성 출처 fixture를 현재 컷오프 매니페스트 계약에 맞췄다. 테스트 임시폴더 안에 읽기 전용 합성 스냅샷과 변환 파일, 고정 매니페스트를 만들고 실제 검증 함수로 해시·경로·기간·파일상태를 확인한다. 실시장 파일은 열지 않는다.
- 현재 검증: R9 단위 테스트 34개, 미국 매크로 전용 테스트 26개가 모두 통과했다. 연구루프 전체는 342개 실행, 실패·오류 0, 건너뜀 2다. 미국 전용 테스트 첫 실행은 fixture의 normalized-source alias/읽기전용 합성파일/유효 해시 불일치로 5 오류·2 실패였고, 원인을 고쳐 재실행해 26/26 통과했다. 전체 테스트는 `/opt/anaconda3/bin/python3`(Python 3.13.5, pyarrow 21.0.0)로 수행했다. 먼저 시도한 Python 3.12 환경에는 `pyarrow`가 없어 해당 환경의 전체 실행은 실패했고, 의존성이 있는 Python 3.13에서 다시 실행해 모두 통과했다.

재현 명령:

```sh
cd /Users/user/CODE/Coin_Trade/scratchpad/strategy_bt/orderblock_loop
PYTHONPATH=scratchpad/strategy_bt/orderblock_loop /opt/homebrew/bin/python3.12 -m unittest discover -s scratchpad/strategy_bt/orderblock_loop/tests -p 'test_search_crypto_r9.py' -v
PYTHONPATH=scratchpad/strategy_bt/orderblock_loop /opt/homebrew/bin/python3.12 -m unittest discover -s scratchpad/strategy_bt/orderblock_loop/tests -p 'test_search_us_macro_overlay_v1.py' -v
PYTHONPATH=scratchpad/strategy_bt/orderblock_loop /opt/anaconda3/bin/python3 -m unittest discover -s scratchpad/strategy_bt/orderblock_loop/tests
```

## 현재 실행·장부 스냅샷

- R4 PID `30488`은 2026-11-24 16:41 KST에 여전히 실행 중이었다. 조회값: 경과 08:02:39, CPU 99.1%, RSS 312,400 KiB, 상태 `RNs`. 종료·중단 조작은 하지 않았다.
- 장부를 읽기 전용 집계했을 때 전체 `N_train=1,549`, 현재 R4 코드 지문에 맞는 완료 행은 18건, 마지막 해당 행 시각은 `2026-11-24T07:23:05.006885+00:00`였다. 이 집계는 실행 중 장부 스냅샷이므로 종료 후 다시 계산해야 한다. 이 18건은 TRAIN 진단이지 OOS/G 통과가 아니다.
- GitHub 원격은 이번 작업에서 확인하지 않았다. 이번 변경은 별도 커밋·푸시를 하지 않았다. 원격 DNS 실패가 확인된 이전 스냅샷을 현재 상태처럼 취급하지 않는다.

## 시장별 현재 판정과 다음에 의미 있는 작업

### 코인 오더블록

- R4 기존 TRAIN 일부는 이미 음의 기대값·낮은 M2/PF를 보인 것으로 직전 연구 기록에 남아 있다. 그 수치만으로 OOS 판정하지 않는다.
- R9 4시간 입력 사전점검은 비어 있지 않은 심볼 32/35와 심볼 파일 집합 일치를 기록했지만, 2018 시작 심볼 0개, funding mark 미확인 6건, 35개 유니버스의 당시 선정 근거 미입증 상태다. R10 공통 1h/4h 적격 심볼은 사전등록 최소 30개에 못 미치는 7개여서 실행 대상이 아니다.
- R9 사전등록은 전체 테스트와 레드팀 검토, 고정 코드·유니버스·사전등록·TRAIN 입력 지문, 단일 실행 슬롯을 요구한다. 현재 PID가 공유 `TRAIN_TRIALS.csv`를 쓰고 있으므로 R9를 병렬 시작하지 않는다. 이번의 접두구간/M2 연결 테스트 보강은 완료했지만, 독립 레드팀의 변경 후 확인은 대기 중이다.
- 기존 데이터 카탈로그는 Binance 무기한 선물 자료를 2019/2020년 이후, funding 자료를 2020년 이후로 적는다. 별도 spot 데이터는 2017년 이후라고 적혀 있지만 선물·funding과 다른 상품이므로 R9 데이터로 대체하지 않았다. raw 가격자료는 열지 않았다.
- 새로 확인한 공식 자료는 Deribit이 2018년 8월 BTC perpetual 출시를 알리고, 공식 문서에서 거래·상품 이력과 공개 funding history API를 설명한다. 이는 2018 위기 구간을 조사할 수 있는 잠재 자료원일 뿐, 현재 실제 과거 응답·권리·마크/펀딩 완전성·30코인 범위를 검증한 결과가 아니다. 샘플 조회나 다운로드는 하지 않았다. [Deribit perpetual 출시 안내](https://insights.deribit.com/exchange-updates/introducing-the-deribit-perpetual/), [Deribit 역사 데이터 안내](https://statics.deribit.com/files/DeribitInstitutionalSetupGuide.pdf), [공식 funding history API](https://docs.deribit.com/api-reference/market-data/public-get_funding_rate_history).
- 다음은 R4 완료를 기다리는 동안 R9의 독립 레드팀 판정을 받고, Deribit 자료가 고정 게이트를 보완할 수 있는지 소스·권리·상품범위만 문서로 확인하는 것이다. R9 결과를 G 통과 후보로 올리지 않는다.

### 미장

- 현재 미장 고유 전략 중 G를 만족하는 후보는 확인되지 않았다. SPY 단일 종목 VIX/CFTC 오버레이는 미사용 종목군 기준을 충족할 수 없고, PIT·기업행위와 시점 정보도 추가 확인이 필요하다. PEAD는 기존 검토상 발표 시각·당시 컨센서스·PIT 유니버스 데이터가 부족하다.
- 합성 fixture 수정은 테스트 출처 검사와의 계약을 맞춘 코드 품질 작업이다. 미국 매크로 전략을 실데이터에 실행하거나 12개 시도를 장부에 등록하지 않았다.

### 국장

- KOSPI200 총수익 ETF SMA 후보는 사전등록되어 있으나, 실제 입력의 재사용 권리·PIT 구성원·상폐 가격·기업행위 데이터가 입증되지 않아 수익 백테스트 단계가 아니다.
- KRX 공식 API 목록은 ETF·주식 일별 데이터를 2010년부터 제공한다고 안내하지만, API 키 신청/승인이 필요하다. API 약관은 비상업 목적 제한과 제공정보의 제3자 제공 금지를 둔다. 공개 데이터 마켓플레이스 약관은 자동수집을 금지하고 사전 허락 없는 복사·복제를 금지한다. 따라서 여기서 자동 수집·API 등록·파일 복사를 하지 않았다. [KRX API 서비스 목록](https://openapi.krx.co.kr/contents/OPP/INFO/service/OPPINFO004.cmd), [KRX API 이용약관](https://openapi.krx.co.kr/contents/OPP/INFO/OPPINFO002.jsp), [KRX Data Marketplace 약관](https://data.krx.co.kr/contents/MDC/INFO/informationController/MDCINFO003.cmd), [상장폐지 종목 시세 추이 화면](https://data.krx.co.kr/contents/MDC/STAT/issue/MDCSTAT239.jsp).

## 규칙·작업경계

- TEST/OOS 및 2026-06-01 이후 원시시장 데이터에 접근하지 않았다.
- R4 PID·공유 장부·실거래·서버·Ochestration·비밀값·원격 저장소를 수정하지 않았다.
- 코드 변경은 두 테스트 파일뿐이고, 후속 기록 문서도 새로 만들었다. 이 저장소의 기존 변경은 보존했다. 테스트와 보고 파일은 현재 커밋되지 않았다.
- 앞선 별도 R9 리뷰어의 출력에 장부 행 세부 내용이 포함됐다는 상태 보고가 있었다. 이 후속 작업은 해당 행을 열거나 재인용하지 않았고, 재발 방지를 위해 새 리뷰 요청에서 장부 파일 접근을 명시적으로 금지했다.
- 자동화 다운로드, 계정·인증키 신청, 구매, 실제 데이터의 권리 추정은 하지 않았다.
- GitHub 현재 원격 동기화 상태는 확인하지 않았다.

## 중단점과 다음 순서

1. R4 PID `30488`의 종료 여부를 읽기 전용으로 다시 확인하고, 종료 후 장부 writer가 없는 것을 확인한다.
2. 안정된 장부에서 현재 총 시도 수와 R4 코드·격자·입력 지문별 성공/실패/미완료를 집계한다. 행 내용을 보고서에 복사하지 않는다.
3. R9 변경 후 레드팀 판정을 받고, 데이터 자격과 고정 G 충족 가능성을 먼저 판단한다. 2018·유니버스·funding 차단이 풀리지 않으면 R9 TRAIN을 G 후보 탐색으로 실행하지 않는다.
4. 미장·국장에서는 데이터 이용권·PIT·상폐·기업행위가 검증되기 전 실데이터 전략 탐색을 하지 않는다. 먼저 무료 또는 이미 허가된 공식 데이터 경로가 실제로 이 게이트를 충족하는지 증명한다.
5. 어떤 시험도 실행 전에 사전등록하고, OOS는 동결 전까지 열지 않는다. 통과 전략 2개씩의 목표와 모든 합격 문턱은 유지한다.

## 이번 턴 독립 연구 검토와 데이터 경로 갱신

네 역할(KR·US·코인 대안·레드팀)이 문서·코드·카탈로그만 읽고 서로 겹치지 않게 검토했다. 원시 데이터, `TRAIN_TRIALS.csv` 행, 활성 산출물은 보지 않았고, 새 백테스트나 다운로드를 하지 않았다.

- **국장:** 새 G 후보 0개. 유일한 미실행 후보는 KOSPI200 총수익 ETF SMA 6개 설정이지만 출처·재사용권·분배금·과거 거래가능성 자료가 부족해 실행 자격이 없다. 069500 압축돌파는 비용 후 음수 및 표본 부족으로 기각 기록이 있어 재시험하지 않는다. 월간 모멘텀은 MDD·Sharpe 및 PIT/상폐 문제로 G 탈락이다. 문서상 근거는 `PREREG_KR_TR_ETF_TREND_V1.md`, `docs/research/equity_kr_compression_breakout_results_20261115.md`, `docs/research/inventory/runs/stock_momentum_robustness_20261120_v5/report.md`다.
- **미장:** 새 G 후보 0개. SPY VIX/CFTC 오버레이는 등록된 탐색 가설이지만 단일 SPY라 미사용 종목군 게이트를 충족할 수 없다. PEAD는 발표시각·당시 컨센서스·PIT 유니버스가 부족하다. 12개월 모멘텀은 기존 등록 후보이며 상폐·당시 유니버스 자료가 미확인이다. 출처는 `PREREG_US_MACRO_OVERLAY_V1.md`, `PREREG.md`의 R4-E2-A, `REPORT_R4.md`, `REPORT_R5.md`다.
- **코인 오더블록:** 기존 R4·R6–R10과 구조적으로 구분 가능한 새 실행 가능 가설은 이전 문서 점검에서는 0개였다. 이후 검토한 OFI 매도흡수·호가 재충전은 OHLCV가 아닌 과거 L2/체결 이벤트가 필요해 현 데이터로 실행 불가다. `search_crypto_r11.py`/`search_crypto_r12.py` 코드는 있으나 둘 다 오더블록 구역 재방문이 아니라 범위돌파/펀딩 조건 진단이고, 별도 prereg/test가 없으므로 현재 목표의 적격 시도도 실행 자격도 없다. 2018년 다종목 파생·펀딩 이력과 PIT 유니버스가 여전히 핵심 차단이다.
- **레드팀:** 신규 고비용 실행 전 원천 권리·시점 정보·PIT/상폐·기업행위, cutoff 전용 입력, 사전등록과 실패 포함 trial 수, prefix/체결 테스트, 활성 장부 writer 종료를 먼저 닫아야 한다. TRAIN 양수만으로 승격하지 않고 모든 동결 G 요건을 유지한다.

공식 원천 문서에서 다음의 *잠재 경로*는 확인했지만 실제 데이터 적격성을 입증한 것은 아니다.

- Deribit은 BTC perpetual을 2018-08-14 출시했다고 발표했고, 공식 API 문서는 지정 구간의 perpetual funding history를 제공한다고 설명한다. 따라서 BTC 2018 자료를 확인할 수 있는 후보 경로다. 다만 30개 코인의 2018 파생상품·펀딩 커버리지, 실제 endpoint 응답의 시작시각, 재사용권·유니버스 완전성은 확인 안 됨이다. 문서만으로 R9 입력 게이트는 열리지 않는다. [Deribit 출시 안내](https://insights.deribit.com/exchange-updates/introducing-the-deribit-perpetual/), [Deribit funding API](https://docs.deribit.com/api-reference/market-data/public-get_funding_rate_history), [Deribit historical data 안내](https://statics.deribit.com/files/DeribitInstitutionalSetupGuide.pdf).
- KRX는 상장폐지 종목 시세 추이 화면에 종가·시가·고가·저가·거래량·거래대금·시가총액 열과 다운로드 UI를 제공하며, 주식·ETF 일별 API 카탈로그는 2010-01-04부터를 명시한다. 이는 상폐가격의 공식 조회 가능성을 보여주는 진전이다. 그러나 필요한 날짜 전체·정리매매/최종정산 처리·ETF 분배금·당시 지수 편입 기록·대량 사용 권리는 아직 확인 안 됨이다. API는 키 신청과 약관 동의가 필요하고, 약관은 비상업 목적 및 제3자 제공 제한을 둔다. 이 작업에서는 가입·키 신청·화면 다운로드·자동 수집을 하지 않았다. [상폐종목 시세 추이](https://data.krx.co.kr/contents/MDC/STAT/issue/MDCSTAT239.jsp), [KRX API 서비스 목록](https://openapi.krx.co.kr/contents/OPP/INFO/service/OPPINFO004.cmd), [KRX API 약관](https://openapi.krx.co.kr/contents/OPP/INFO/OPPINFO002.jsp).
- **미국 데이터 대안:** CRSP의 공식 설명은 일·월봉 가격과 기업행위를 36,000개 넘는 현·비활성 증권에 대해 제공한다고 하며, PERMNO/PERMCO 영구 식별자를 언급한다. CRSPMI 제품 문서에는 2011년 이후 일별 지수 편입(시가/종가) 자료가 나온다. 이는 현재 Yahoo 기반 생존종목 자료보다 PIT·상폐·기업행위 게이트를 해결할 가능성이 높은 경로다. 다만 상품·ETF 범위가 이 연구 유니버스를 전부 덮는지, 200bp 왕복보다 더 엄격한 비용 모델로 쓸 자료인지, 사용권·가격·샘플·실제 데이터 품질은 확인 안 됨이다. 제품 페이지는 가격표 대신 구독정보 요청을 안내한다. 요청 제출·계정 생성·구매·데이터 취득은 하지 않았다. [CRSP US Stock Databases](https://indexes.morningstar.com/research-data-products/crsp-us-stock-databases), [CRSPMI 과거 데이터](https://www.crsp.org/research/crspmi-historical-database/), [CRSPMI 가이드](https://www.crsp.org/wp-content/uploads/guides/CRSPMI_Historical_Database_Guide.pdf), [CRSP 상장폐지 수익 정의](https://wrds-www.wharton.upenn.edu/documents/396/CRSP_US_Stock_Indices_Data_Descriptions.pdf).

한 리뷰 응답의 링크 일부가 canonical repo 바깥의 `scratchpad/strategy_bot/...`를 가리켰다. 해당 위치는 열지 않았고 그 링크만으로는 어떤 주장도 검증하지 않았다. 리뷰어는 장부 접근 금지 지시를 받았으며, 이전 별도 리뷰에서 장부 행 내용이 출력에 포함됐다는 보고는 위 규칙·작업경계에 기록했다.

현재 결론은 **전략 목표 6개 중 G 통과 0개**다. 다음 가능한 실질 단계는 R4 writer가 끝난 뒤 공유 장부를 행 내용 노출 없이 안정 집계하고, 미국 CRSP·국장 KRX의 이용범위·가격·샘플을 각각 확인하며, Deribit이 요구된 다종목 과거 이력을 실제로 갖는지 확인하는 것이다. 어느 게이트도 해소되지 않으면 전략을 더 조합하거나 기준을 낮추지 않고 `DATA_BLOCKED`로 기록한다.

## 이번 이어가기: 데이터 적격성 경로와 신규 가설 검토

### R4 상태 재확인

- 2026-11-24에 PID `30488`이 살아 있음을 프로세스 메타데이터로 확인했다. 경과 `08:08:24`, 누적 CPU `486:31.44`, RSS `280832 KiB`, 상태 `RNs`였다.
- 프로세스는 중단하거나 신호를 보내지 않았다. 장부 행은 읽지 않았다. 공유 장부의 현재 수치와 R4의 완료 수는 이 확인으로 갱신되지 않았다.

### 공식 데이터 경로에서 확인된 추가 사실

- **KRX 시점별 지수 구성:** KRX의 공개 「지수구성종목」 화면은 지수명과 조회일자를 입력하도록 되어 있고 종목코드·종목명·종가·등락률·시가총액을 표시한다. 별도의 「상장폐지종목 시세 추이」 화면은 폐지 종목의 조회기간과 일자별 OHLCV·거래대금 등을 표시한다. 이는 PIT 구성 조회와 상폐 종목 가격의 잠재 경로를 구체화한다. 다만 실제 과거 조회 가능기간, 전체 지수·ETF/상폐 ETF 범위, 일괄 추출 재현성, 이용권은 증명되지 않았다. KRX 화면에 다운로드 UI가 있다는 사실만으로 대량 연구·재배포 권한을 추정하지 않는다. [KRX 지수 구성종목 조회](https://data.krx.co.kr/contents/MDC/STAT/standard/MDCSTAT006.jsp), [KRX 상장폐지 종목 시세](https://data.krx.co.kr/contents/MDC/STAT/issue/MDCSTAT239.jsp), [KRX 상장폐지 종목 현황](https://data.krx.co.kr/contents/MDC/STAT/issue/MDCSTAT238.jsp), [KRX 데이터 이용약관](https://data.krx.co.kr/contents/MDC/INFO/informationController/MDCINFO003.cmd).
- **KRX 정식 지수 자료상품:** KRX 지수 정보상품 설명은 종가 기준·익일 기준 지수 데이터, 구성 종목·반영 주식수·가격·비중·유동비율, 기업행위 및 구성변경 정보를 파일로 제공한다고 적는다. 지수 구성 이력에 필요한 데이터 종류는 존재하지만, 이 연구의 사용 허가·가격·기간·개인 연구 목적의 이용 조건은 공개 페이지에서 확정하지 못했다. 기존 국장 사전등록은 해제되지 않는다. [KRX 지수 라이선스/정보상품](https://openapi.krx.co.kr/contents/OPP/DATA/OPPDATA005.jsp).
- **미국 CRSP:** 현재 공식 안내는 36,000개 초과 활성·비활성 증권의 일·월 데이터, 영구 식별자, 기업행위·상장폐지 정보와 ETF를 식별하는 `SecuritySubType`을 문서화한다. CIZ 필드 정의에서 지수 구성원 시작·종료일도 확인된다. 별도 CRSPMI 구성원 데이터는 2011년부터 CRSP 자체 지수의 일별 개장/마감 편입을 제공한다. 단, CRSPMI는 모든 외부 지수 구성원 이력이 아니며, 상품의 구독·가격·샘플은 공개 문서만으로 알 수 없다. CRSP의 과거 무료 제공 안내는 2024년 11월까지였으므로 현재 무료 조건으로 간주하지 않는다. [CRSP US Stock Databases](https://indexes.morningstar.com/research-data-products/crsp-us-stock-databases), [CIZ 사용자 안내서](https://www.crsp.org/wp-content/uploads/guides/CRSP_US_Stock_%26_Indexes_Database_Guide_Flat_File_Format_2.0.pdf), [CRSPMI 과거 지수 구성원](https://www.crsp.org/research/crspmi-historical-database/), [CRSP 샘플 데이터 안내서](https://www.crsp.org/wp-content/uploads/2023/09/CRSP_Sample_Data_and_Software_Guide.pdf).
- **기존 전략과의 충돌:** US SPY 매크로 오버레이 사전등록은 고정 단일 ETF 전략이며, 그 문서 자체가 캠페인의 미사용 종목군 60% 기준을 충족할 수 없다고 명시한다. 그러므로 해당 실험이 정상 실행·테스트되더라도 현재 고정 G 아래에서는 통과 후보로 계산할 수 없다. 이를 독립적인 두 번째 미장 전략처럼 세지 않는다.

### 새 코인 오더블록 가설 — 아이디어만, 실험 미등록

네 명의 읽기 전용 검토 중 코인 연구 역할은 기존 displacement/BOS/거래량·다중주기·극성반전·sweep/reclaim 조합과 구별될 수 있는 두 가지 미시구조 가설을 제안했다. 아직 이 저장소의 기존 전략 등록부 및 자료를 읽어 독립성·자료 보유를 검증한 단계가 아니며, 새 시도 장부 행이나 결과가 아니다.

1. **주문장 유동성 회복력:** 가격 충격 직후 OB 재방문 때 해당 구간 호가 깊이가 얼마나 빠르게 회복되는지로 지지/저항 반응의 선도달을 예측한다. 원인 메커니즘은 충격 후 주문장의 회복 속도 차이다. 시간순 L2 스냅샷과 증분 업데이트가 필요하며, 호가 취소/스푸핑·누락 업데이트가 주된 실패 요인이다. 연구 근거는 전통 전자 주문장 회복력에 관한 것이며 암호화폐 선물의 수익성 증거는 아니다. [Large, 주문장 회복력](https://doi.org/10.1016/j.finmar.2006.09.001), [Lo & Hall, 주문장 회복력](https://doi.org/10.1016/j.dyncon.2015.09.001).
2. **체결흐름–호가 재고 불일치:** OB 접촉 때 공격적 체결 방향과 동기화된 최우선 호가 잔량 변화가 서로 어긋나는 흡수/고갈 상태를 측정한다. 공격자 방향 체결과 시간 동기화된 L2 변경이 필요하다. 짧은 호가 예측 관계가 선물 target-first 수익으로 이어진다고 가정할 수 없으며, 목표/손절 선도달을 별도 검정해야 한다. [Cont·Kukanov·Stoikov, 주문장 이벤트의 가격 영향](https://arxiv.org/abs/1011.6402), [Gould·Bonart, 호가 불균형의 다음 틱 연구](https://arxiv.org/abs/1512.03492).

두 가설 모두 현재 확인된 과거 시계열 L2 적격 자료가 없어 실행 가능 후보가 아니다. Binance의 실시간/현재 호가 스트림 또는 aggregate trade 문서 존재만으로 과거 전 기간의 주문장 이력을 입증할 수 없다. 특히 두 번째 가설의 짧은 구간 결과를 1m/5m OHLC로 대체해서는 안 된다. 사전등록·코드·백테스트·다운로드는 하지 않았다. 기존 과거 체결 틱이나 깊이 데이터가 실제 대상 심볼·기간·동기화 요건을 만족하는지는 확인 안 됨이다.

다만 저장소 안의 현재 **데이터 카탈로그**(`/Users/user/CODE/Coin_Trade/data_sources/CRYPTO_SOURCES.md`)를 대조해 한 가지를 정정한다. 그 카탈로그는 Binance UM `bookDepth`를 30초 간격의 ±1~5% 누적 깊이/명목가치 구간 스냅샷으로 기록하고, 2023-01-01부터 2026-11-19까지 BTC·ETH 2종목, 파일 94개로 인벤토리화한다. 이 범위에서 2026-06-01 이후 실제 시세 행은 읽지 않았다. 이 자료는 2023-01~2026-05의 BTC·ETH에서 **대략적인 깊이 회복/불균형**을 탐색할 잠재 입력이다. 그러나 원시 개별호가·주문 이벤트를 보존한 L2 스트림과 동등하지 않고, 최소 30개 종목 조건을 충족하지 않으며, 필수 2018·2022 구간도 포함하지 않는다. 그러므로 새 가설의 작은 개발 파일럿 가능성은 생겼지만, 현재 campaign G 후보로 인정할 수는 없다. 실제 파일 메타데이터·필드·날짜 완전성·라이선스는 아직 미검증이고, R4가 끝나기 전에는 해당 실험을 실행하지 않는다. Binance 공개 데이터 README는 일/월 파일 제공, 체크섬 검증, 아카이브 파일의 사후 갱신 가능성을 명시한다. 별도 Dataset Terms(2026-08-26 개정)는 개인의 비상업적·비프로덕션 역사 백테스트를 허용 범위로 열거하고, 상업 사용·실거래 자동주문·보상성 제3자 신호배포를 금지하며, 파생물의 재배포에는 표시·동일 라이선스 조건을 둔다. 기존 다운로드 시점에 적용된 약관과 해당 파일의 provenance는 따로 확인해야 한다. [Binance 공개 데이터 저장소 README](https://github.com/binance/binance-public-data/blob/master/README.md), [Binance Vision Dataset Terms](https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md), [Binance 선물 주문장 스트림 문서](https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams/How-to-manage-a-local-order-book).

### 검토 결과와 다음 결정 게이트

- 네 역할의 독립 검토 결과는 **국장 신규 G 후보 0, 미장 신규 G 후보 0, 코인 신규 실행 가능 OB 후보 0**이다. 코인 미시구조 아이디어 2개는 데이터가 없으므로 실행 가능한 후보 수에 넣지 않는다.
- 레드팀은 목표 숫자를 맞추기 위해 기준을 느슨하게 해석하지 말라고 확인했다. 단일 SPY 오버레이의 횡단면 유니버스 게이트 불충족, 코인 2018 선물/펀딩 및 PIT 유니버스 미확인, KRX 권리·범위 미확인은 각각 독립 차단점이다.
- 현재 G 통과는 시장별로 각각 `0/2`다. 이 수치는 새 OOS 백테스트를 돌린 결과가 아니라 현재 기록으로 확인된 통과 후보 수다.
- 다음 실행 전 해야 할 일은 (1) R4가 종료된 뒤에만 장부 writer 부재를 확인하고 행을 노출하지 않은 집계 수행, (2) KRX의 지정 과거일 지수구성 및 상폐 종목 실제 범위·연구 이용권 확인, (3) CRSP 샘플의 구독 자격·기간·ETF/상폐/기업행위 범위 확인, (4) 코인 과거 L2의 심볼·시간대·연속성·사용권을 메타데이터로 확인하는 것이다. 각 항목은 아직 완료되지 않았으며, 문의·신청·결제·다운로드는 수행하지 않았다.
- 네 역할은 외부 공개 문서만 검토했고, 에이전트들은 저장소·데이터·장부를 열거나 변경하거나 백테스트를 실행하지 않았다. 단, 통합 뒤 실행한 검증 명령 `git diff --check`의 범위를 파일로 제한하지 않아 기존 변경분 중 `TRAIN_TRIALS.csv`의 diff 줄이 도구 출력에 포함됐다. 장부 파일을 수정하지 않았고 해당 줄을 이 보고서에 복사하지 않았지만, 장부 행 내용을 출력에 노출한 것은 금지 경계 위반이다. 추가 장부 조회나 전체 저장소 diff 검사는 하지 않는다.

## 추가 국장 파일 메타데이터 점검

요청된 세 Parquet 파일은 파일시스템 stat만 했고, 데이터 내용은 열지 않았다. 파일명·크기·수정시각은 보조 증거이며 성과 데이터로 사용하지 않았다.

| 파일 | 매니페스트/문서 메타데이터 | G에 대한 의미 |
|---|---|---|
| `external/equities/kr/daily_stocks_delisted.parquet` | 매니페스트: 2,345,921행, 원천은 `FinanceDataReader.DataReader`의 Naver fchart 조정주가, 날짜범위 1996-01-30~2026-11-19. FDR 코드도 NAVER reader가 `fchart.stock.naver.com`을 호출함을 명시한다. `EQUITY_SOURCES.md`는 4,229개 상폐 코드 중 가격을 받은 코드는 1,190개뿐이라고 기록한다. | 2026-06-01 이후를 포함하는 원본이라 그대로 탐색에 쓸 수 없다. Npay 증권 공식 FAQ는 서비스 화면 열람 외에 증권 데이터를 재가공해 개인 프로그램·웹페이지에 사용하는 것을 금지한다고 밝힌다. 매니페스트와 FDR 코드의 출처 표기, Npay 이용 안내를 종합해 이 파일은 전략 코드·백테스트 입력에 사용하지 않는 것으로 처리한다. 278530 ETF 총수익 계열도 아니며, 이 파일로 KOSPI200 TR ETF 사전등록을 통과시킬 수 없다. [FinanceDataReader Naver 가격 수집 경로](https://github.com/FinanceData/FinanceDataReader/blob/master/src/FinanceDataReader/naver/data.py), [Npay 증권 정보 이용 안내](https://help.pay.naver.com/faq/content.help?faqId=17106) |
| `external/equities/kr/listing_krx_delisted.parquet` | 매니페스트: 4,229행, FinanceDataReader `KRX-DELISTING` (KRX KIND). | 상폐 메타데이터 목록이다. 날짜별 편입·거래 가능성·완전한 상폐 가격 패널을 제공한다고 확인되지 않았다. |
| `external/equities/kr/listing_krx_current.parquet` | 매니페스트: 2,878행, FinanceDataReader `KRX`의 2026-11 현재 스냅샷. | 현재 목록이므로 과거 PIT 유니버스가 아니다. |

`data_sources/kr_pit/README.md`도 FDR/KIND 목록과 월말 목록 스냅샷이 정확한 IPO·상폐일이나 KRX 편입을 보증하지 않고, 상폐 일봉 수집 경로가 로그인 요구로 빈 결과를 냈다고 기록한다. Npay 공식 안내는 서비스 내 증권정보를 개인 프로그램·웹에서 재가공하는 것을 금지한다. 따라서 Naver fchart 파일은 사용불가, FDR/KIND 목록은 시점별 KRX 편입을 증명하지 않는 스냅샷, KRX API 경로는 이용 권한과 로그인 승인 미확인으로 분류한다. 국장 데이터 게이트는 여전히 닫혀 있다. 공식 KRX 과거일 조회 UI는 잠재 경로지만 지정 날짜의 실제 범위·완전성·이용 허가를 검증하지 않았다.

메타데이터 전용 확인 요청을 처리하는 중, 한 번은 repo 전체에서 경로명을 검색해 상폐가격 파일을 참조하는 기존 `universe/*.csv` 행이 출력됐다. Parquet 원시 행은 열지 않았고, 해당 유니버스 행을 보고서에 옮기거나 수정하지 않았다. 다만 요청 범위를 메타데이터 파일로만 제한하지 못한 추가 범위 실수다. 이후에는 지정된 매니페스트 행과 전용 README만 확인한다.

## KIS 기존 캐시 대안 점검

`data_sources/EQUITY_SOURCES.md`는 저장소 밖 KIS 일봉 캐시가 184개 티커이고 2010-08부터 2026-11-17까지라고 기록한다. 원시 CSV·캐시 파일은 열지 않았다. 이 기록만으로는 종목별 기간, 2026-05-31 cutoff 이전 전용 스냅샷, 과거 편입·상폐 멤버십, 가격조정·분배금 처리 또는 연구 재사용 권한이 확인되지 않는다. 따라서 현재 KIS 파일을 직접 백테스트 입력으로 쓰지 않는다. 원시 파일에 cutoff 이후 날짜가 포함될 수 있어 이번 규칙 아래 전체 파일을 읽거나 해시하는 것도 금지한다.

KIS 공식 포털은 Open API 시세조회와 별도 백테스터를 제공한다고 설명한다. 그러나 그 백테스터가 본 프로젝트의 사전등록·공유 trial 수·독립 레드팀·고정 비용/귀무/다중검정 G를 대신한다는 근거는 없다. 또한 공식 API 문서 접근과 개인 API 키 발급/사용은 별개다. 이번 작업은 계정·키·네트워크 API를 쓰지 않았다. KIS 캐시는 권한이 확인된 cutoff 전용 사본과 PIT/상폐 구성 증거가 제공되면 후보 개발 입력으로 다시 검토할 수 있지만, 그 단계에서도 현재 G 통과를 주장할 수는 없다. [KIS Developers API 문서](https://apiportal.koreainvestment.com/apiservice), [KIS 공식 백테스터 안내](https://apiportal.koreainvestment.com/toolkit-backtest).

이 KIS 경로 확인 중 `rg` 검색 범위를 저장소 전체로 넓혀 기존 시장 아티팩트 인벤토리 CSV의 파일명·크기 정보가 도구 출력에 포함됐다. 해당 캐시 데이터의 내용, KIS CSV 행, 비밀 설정은 열지 않았고 어떤 인벤토리 행도 연구 결과로 복사하지 않았다. 요청된 좁은 KIS 문서·카탈로그 밖의 출력이었으므로 추가 검색은 하지 않는다.

## 2026-11-24 공식 무료 데이터 경로·신규 코인 가설 재검토

### 기존 실행 보호

- 현재 프로세스 조회에서 PID `30488`이 `search_crypto_r4.py`를 실행 중임을 확인했다(경과 08:25:58, 상태 RNs). 조회 외 신호·종료·재시작은 하지 않았다. `TRAIN_TRIALS.csv`는 열지 않았다.
- 기존 Coin_Trade 카탈로그 `data_sources/CRYPTO_SOURCES.md`에는 Binance USD-M 1분봉 35종이 2020-01 이후, 과거 USD-M book depth가 BTC·ETH 2종뿐이고 2023-01 이후로 기록되어 있다. 이는 카탈로그에 기록된 기존 보유 자료의 범위이며 실제 파일 재검증이나 전체 2018 코호트 증명은 아니다.

### 오더북 자료 게이트

- Gate 공식 과거데이터 페이지는 체결·캔들 다운로드를 2023년 1월부터, 시장 깊이와 깊이 스냅샷을 2021년 8월부터 지원한다고 표시한다. 문서의 `futures_usdt` 자료 형식과 시간별 파일 예시만으로 2018년부터 30개 이상의 perpetual 심볼에 동기화된 체결·L2가 존재한다고 추정하지 않는다. [Gate 과거데이터 페이지](https://www.gate.com/pt-br/developer/historical_quotes), [Gate 데이터 형식 공지](https://www.gate.com/announcements/article/21688)
- OKX 공식 페이지는 체결 2021-09 이후, 캔들 2023-07 이후, 펀딩 2022-03 이후, 고해상도 L2 2023-03 이후로 안내한다. 요구되는 2018 시작점은 충족하지 않는다. [OKX 과거 시장 데이터](https://www.okx.com/historical-data)
- Binance 공식 공개 데이터 저장소는 집계체결·캔들 파일의 데이터 구조를 문서화하지만, 이번에 읽은 공개 README만으로는 2018년부터 다종목 선물 L2와 체결을 동기화해 제공한다는 근거를 찾지 못했다. 별도 Binance L2 커버리지 주장은 공식 문서 근거를 추가 확보하기 전까지 미확인으로 둔다. [Binance Public Data 저장소](https://github.com/binance/binance-public-data/blob/master/README.md)
- 결론: 기존 오더북 회복력·호가/체결 불균형 가설은 L2 기반의 2018–2026-05-31, 30종 코호트 자료가 입증되지 않아 실행 후보가 아니다. Gate 단독 자료도 고정 자료 게이트를 열지 않는다.

### 주식 자료 게이트

- 금융위원회 주식시세 API는 KRX 종목 시세를 제공하지만 공공누리 4유형의 비상업·변경금지 조건과 제3자 제공/재배포 제한을 명시한다. 이 연구에서 허용되는 PIT·기업행위·상폐 결과 결합 입력으로 사용할 권리를 확인하지 못했다. [금융위원회 주식시세정보 API](https://www.data.go.kr/data/15094808/openapi.do)
- KRX 상장폐지 종목 화면에는 조회기간과 일별 OHLCV·거래대금 등이 있지만, 화면에 필드가 있다는 사실은 최장 보유기간·일괄 추출 재현성·자동 연구 이용허가를 증명하지 않는다. [KRX 상장폐지 종목 시세 추이](https://data.krx.co.kr/contents/MDC/STAT/issue/MDCSTAT239.jsp)
- SEC·FINRA·Nasdaq·NYSE 공개 자료 검토 결과도 전체 PIT 주식·ETF 유니버스, 일별 총수익, 비활성 종목의 최종 상폐수익을 결합하는 무료 공식 경로를 입증하지 못했다. CRSP는 가장 가까운 문서화된 상품이지만 구독형이므로 무료 게이트를 열지 않는다. 표본·견적 조회 범위에서 구매나 계정 생성은 하지 않았다. [CRSP 미국 주식 데이터베이스](https://www.crsp.org/research__trashed/crsp-us-stock-databases/), [SEC EDGAR API](https://www.sec.gov/search-filings/edgar-application-programming-interfaces), [Nasdaq 역사 데이터](https://www.nasdaq.com/market-activity/quotes/historical), [NYSE TAQ Closing Prices](https://www.nyse.com/data-products/catalog/taq-nyse-closing-prices)

### 후보 가설 적대 검토 — 결과가 아니라 아이디어

- 일반 임펄스 직전 반대색 봉 재방문 후 추세 지속은 기존 displacement/BOS 오더블록·재방문 연구와 구조적으로 겹치므로 새 라운드 후보로 승격하지 않는다.
- 구역을 벗어난 종가 돌파가 구역 안으로 재진입한 뒤 반대 방향 거래하는 실패 돌파 가설은 기존 무효화 구역의 저항 전환 및 distal sweep/recovery 등록과 중복 가능성이 크다. 독립성 확인 전 재등록하지 않는다.
- 재방문 오더블록에 공개된 시점의 OI 변화·직전 확정 funding 조건을 추가하는 가설은 별도 검토 여지가 있다. 다만 데이터 결측, 공개 시각, 기존 비용/funding 처리와의 구조 차이를 확인하고, 사전등록 소유자(A)가 새 설정·겹침 중복·다중검정 분모를 승인하기 전에는 실행하지 않는다.
- 네 명의 독립 역할 검토는 외부 공개 자료·가설 제안만 수행했다. 원시 시장자료, 공유 장부, 코드, 백테스트는 열거나 수정하지 않았다. 제안된 세 가설은 수익 근거가 없으며 이번 연구에서 시도 수나 통과 수에 포함하지 않는다.

### 이번 확인 범위와 판정

- 공식 페이지를 직접 확인하고 독립 연구자 4명의 출처 제안과 대조했다. 웹 자료는 데이터의 공개 설명만 입증하며 실제 파일의 존재·완전성·라이선스 적합성·전략 성과를 입증하지 않는다.
- 시장별 고정 G 통과 전략은 여전히 0개로 보고한다. 진행 중 R4 결과는 아직 완결·대사되지 않아 새 수치나 현재 완료 건수를 주장하지 않는다. OOS/TEST와 2026-06-01 이후 가격행은 열지 않았다.
- 이번 작업에서 실행한 것은 프로세스 메타데이터 조회와 문서/공식 출처 검토뿐이다. 백테스트·통계 검정·테스트는 실행하지 않았다. 이 보고서 외 파일을 변경하지 않았으며 커밋·푸시도 하지 않았다.

## 2차 교차 레드팀 판정과 데이터 경로 보완

- **Binance 선물 L2:** 공식 자료 설명은 T_DEPTH 틱 단위 L2를 2020-07-01부터로 적지만, API 접근은 Futures 계정과 허용 목록에 등록된 API 키가 필요하고, T_DEPTH는 API 수집이라 gap이 있을 수 있다. S_DEPTH 스냅샷은 현재 BTCUSDT만 지원한다고 적혀 있으며, T_DEPTH_BACKFILL은 2021년 7월 중순 이후 생성이 중단됐다고 적혀 있다. 따라서 “무료 공개 파일로 2018년부터 30종 이상의 동기화 L2+체결을 확보”했다는 근거가 아니다. 이 자료에 접근하거나 키를 사용하지 않았다. [Binance Futures Historical L2 설명](https://github.com/binance/binance-public-data/diffs/0?commit=e8cdb38250d443e8b948f6cf7e37207614a7ad43&name=master&sha1=4d66fc593d6afa301c9266aed28598f8fc76d6a4&sha2=e8cdb38250d443e8b948f6cf7e37207614a7ad43&short_path=eefa7af&w=false)
- **KRX 자동 접근 조건:** 현재 공개 홈페이지 이용약관은 자동화 수단으로 정보를 무단 수집·복제·배포하는 행위와 사전 허락 없는 복사·복제·배포·전송을 금지하며, 마켓데이터 상품은 별도 구매·이용 약관을 따르도록 한다. 이는 공개 페이지의 필드 존재만으로 스크립트 수집이 승인됐다고 볼 수 없다는 근거다. 공공데이터 API는 별도의 공공누리 4유형 제한도 표시한다. [KRX 홈페이지 이용약관](https://data.krx.co.kr/contents/MDC/INFO/informationController/MDCINFO003.cmd), [금융위원회 주식시세 API 조건](https://www.data.go.kr/data/15094808/openapi.do)
- **미국 무료 샘플의 한계:** Nasdaq Data Link SHARADAR/SEP 안내는 무료 샘플 범위를 30개 지정 주식, 2018-09-01~2018-12-31로 표시한다. 이는 특정 구간의 일부 가격 필드 표본이지, 전 시장 주식·ETF PIT 유니버스와 상폐/기업행위 총수익 기록의 전 기간 대안이 아니다. [Nasdaq SEP 샘플 문서](https://data.nasdaq.com/databases/SEP/documentation?anchor=sample-data)
- **2차 교차 레드팀:** 네 역할은 기존 데이터 게이트를 반증할 공식 경로를 재검토했다. 미국 무료 자료는 G 전체 범위를 채우지 못하고, 한국은 날짜별 KRX 구성·상폐 시세 화면이 일부 필드의 존재를 증명하지만 기간·완전성·ETF 분배금/기업행위·재현성·허용 이용권을 함께 입증하지 못했다. Gate/Binance/OKX L2 시작기간은 기존 라운드의 요구 범위와 맞지 않는다. 따라서 데이터 게이트는 계속 닫혔다.
- **가설 독립성 심사:** 세 가설 중 사전등록 가치가 있다고 승인된 것은 0개다. 별도 리뷰어는 현재 대화에서 R4·R6–R10의 본문을 직접 확인하지 않았으므로 중복 판정을 미확인으로 남겼다. 본 보고서의 제한된 사전등록 대조에서는 일반 임펄스 재방문이 기존 구조와 겹치고, 실패 돌파 반전도 기존 sweep/recovery·무효화 구역 반전과 중복 위험이 커 신규 후보로 올리지 않았다. OI·funding 조건부 가설은 이 변수들의 기존 사용 여부를 정확히 대조하고 시점·결측을 확인하기 전까지 미등록 상태다.
- **현물 이력의 제한된 가능성:** 별도 읽기 전용 manifest 집계 결과 Binance spot은 2026-05까지 33심볼, 2,249 symbol-month 파일이다. 2018년은 일부 월 8심볼, 12개월 모두 파일이 있는 심볼은 4개(BTC/ETH/BNB/LTC)다. 2022년은 일부 월 25심볼, 12개월 모두 파일이 있는 심볼은 23개다. 이는 월 파일 존재 여부만 집계한 값이며 파일 내부 분봉 연속성이나 PIT 유니버스를 증명하지 않는다. 따라서 기존 30심볼/2018 gate에 미달한다. 게다가 spot은 프로젝트 선물 전용 범위와 다르므로 funding·선물 체결비용 검증을 대체할 수 없고, 선물 G 통과로 계산하지 않는다. 보고된 Binance 공개 데이터 약관은 개인·비상업·비생산 역사 백테스트를 허용하는 CC BY-NC-SA 조건이나, 기존 파일 취득 시점의 권리·약관 provenance는 미확인이다. 현물 자료를 실제 실험에 쓰려면 이 출처·취득권과 별도 사전등록을 먼저 확인해야 한다.
- **마지막 프로세스 확인:** 2026-11-24 프로세스 재조회에서 PID `30488`은 `search_crypto_r4.py`로 계속 실행 중이었다(경과 08:32:05, 상태 RNs). 종료·신호·재시작하지 않았다.

## 공식 표본·가격 접근 경로 재확인 (08:20 UTC)

- **KRX 데이터 상품:** 공식 구입 안내는 회원가입·로그인 후 상품별 제공기간·항목·샘플·가격을 확인하고, 신청·결제와 이용목적 심사를 마친 뒤 데이터를 받는 절차라고 명시한다. 학술 목적 할인은 학생·교직원·학교법인에 한해 50%라고 적혀 있다. 이 공개 안내만으로 실제 종목·기간별 가격이나 개인 연구자의 사용권은 확인되지 않는다. 이번에는 로그인, 문의, 신청, 결제를 하지 않았으므로 국장 자료 게이트는 계속 닫혀 있다. [KRX 데이터 구입 안내](https://openapi.krx.co.kr/contents/OPP/DATA/OPPDATA001.jsp)
- **KRX ETF 상품 카탈로그:** 공개 상품 목록은 ETF·ETN·ELW 일별 매매와 1분·10분 장중 매매, 호가·체결 상품의 존재를 보여주지만, 공개 페이지에서 가격이나 과거 제공 시작일은 확인되지 않는다. 이 목록은 데이터 상품의 존재를 입증할 뿐 무료 접근이나 본 전략에 쓸 수 있는 재사용권을 입증하지 않는다. [KRX 증권상품 카탈로그](https://data.krx.co.kr/contents/MDC/DATA/datasale/index.cmd?prodType=EP&viewNm=dataProdList)
- **CRSP 표본:** 공식 표본 안내서는 내부 평가용 스냅샷이며, CRSP Stock & Index 표본은 25개 PERMNO, 전체 주식 이력은 2019년 12월까지라고 적는다. 표본 자체는 상장·비상장 과거 증권 데이터의 스키마와 조정/상장폐지 필드 확인에는 쓸 수 있으나, 캠페인의 60개 OOS 거래·미사용 종목군 검증에 필요한 대규모 표본은 아니다. 요청은 구독부서 이메일/전화로 하도록 안내되어 있다. 사용자는 샘플·견적 조회를 허용했지만 계정/결제나 연락 발송을 요청하지 않았고, 연결된 이메일 발송 도구도 없어 연락은 하지 않았다. [CRSP 표본 데이터 안내서](https://www.crsp.org/wp-content/uploads/2023/09/CRSP_Sample_Data_and_Software_Guide.pdf)
- **CRSP 본 상품:** 공식 제품 설명은 36,000개가 넘는 활성·비활성 미국 증권에 대해 일·월 시장자료와 기업행동, 영구 식별자를 제공하며 구독 라이선스 이용자에게 공급한다고 명시한다. 현재 공개 페이지에서 가격표는 찾지 못했다. 따라서 본 상품은 구조상 미국 생존편향 문제에 맞는 후보 데이터지만, 가격·개인 이용권·ETF 필드 범위·샘플 적격성이 확인되기 전에는 확보된 자료나 연구 입력으로 간주할 수 없다. [CRSP US Stock Databases](https://indexes.morningstar.com/research-data-products/crsp-us-stock-databases)
- **R4 상태/장부 경계:** 08:19 UTC 조회에서 PID `30488`은 실행 중(경과 08:40:59, CPU 518:52.51, RSS 300,048 KiB)이었다. 공유 장부는 내용 없이 파일 메타데이터만 조회했으며, 마지막 수정 시각은 17:16:32 KST였다. 이 시각이 프로세스의 진행을 증명하지는 않으므로 R4 완료 셀 수는 `확인 안 됨`으로 유지한다. R4를 중지·재시작하지 않았고 장부를 열지 않았다.
- **이번 작업의 경계:** 공식 페이지와 표본 문서만 확인했다. 새로운 데이터를 내려받거나 행을 읽지 않았고, 공유 장부에 시도 행을 추가하지 않았으며, 합성 검증·성과 백테스트도 실행하지 않았다. 가격을 확인하려면 KRX 회원 로그인 또는 CRSP 구독부서와의 별도 연락이 필요하다는 것이 확인된 다음 게이트다.

## 4역할 독립 데이터 레드팀 추가 결과 (08:25 UTC)

네 역할을 분리해 공식 자료만 읽게 하고, Coin_Trade 파일·가격 행·장부·백테스트는 건드리지 않았다.

- **한국:** KRX 상폐 종목 시세 화면은 종목별 OHLCV와 날짜 조회가 있으나 최대 과거기간·재사용권·조정/TR 체계가 공개 설명만으로 확인되지 않는다. 금융위 주식·ETF 시세 API는 날짜 검색 필드가 있지만 과거 시작 범위와 상폐 종목 포함 여부가 명확하지 않으며, 공공누리 4유형(비영리·변경금지·재배포 제한)이다. 따라서 상폐·PIT·기업행위·사용권 게이트가 모두 해결되지 않았다. [KRX 상폐 시세 화면](https://data.krx.co.kr/contents/MDC/STAT/issue/MDCSTAT239.jsp), [금융위 ETF 시세 API](https://www.data.go.kr/data/15094806/openapi.do)
- **미국:** SEC·FINRA·Nasdaq·NYSE 무료 자료의 조합도 전체 주식/ETF 일봉, 상폐 최종가, 과거 전체 PIT 유니버스를 동시에 채우지 못한다. 일부 OTC/Nasdaq 상장변경 공지는 있으나 시장 범위·접근·가격 자료가 따로 분리된다. CRSP 외 무료 완결 대안은 확인되지 않았다. 
- **코인:** Bybit 공식 API에서 과거 캔들·마크·funding 조회 기능은 확인되지만, 2018년 30+ 계약 연속 커버리지나 과거 오더북 아카이브를 증명하지 않는다. Deribit 펀딩 자료는 2019년 5월부터이고 고빈도 과거 오더북 경로는 키가 필요한 제휴자료다. Hyperliquid 아카이브는 2023년 이후 형식 및 요청자 부담 전송 조건이라 2018 gate를 채우지 못한다. API의 날짜 매개변수는 그 시점 데이터의 실제 보존 증거가 아니다. [Bybit 캔들](https://bybit-exchange.github.io/docs/v5/market/kline), [Bybit 펀딩](https://bybit-exchange.github.io/docs/api-explorer/v5/market/history-fund-rate), [Deribit funding history](https://insights.deribit.com/dev-hub/deribit-perpetual-funding-python/), [Hyperliquid archive](https://hyperliquid.gitbook.io/hyperliquid-docs/historical-data)
- **2018 대체 거래소 이력:** BitMEX는 2016년 XBTUSD 무기한을 출시했고 ETHUSD 무기한은 2018-08-03에 출시했다. 이는 2018년에 해당 거래소 무기한의 실제 역사가 있었음을 보이지만, 두 계약뿐이라 G의 30+ 심볼 요건을 충족할 수 없다. 현재 BitMEX 안내는 2026-09-23 거래 종료를 명시하므로 이를 실시간 대체 거래소로 보지도 않는다. [BitMEX XBTUSD 출시](https://www.bitmex.com/blog/site-announcement/2432), [BitMEX ETHUSD 출시](https://www.bitmex.com/blog/announcing-the-new-ethusd-perpetual-contract), [거래 종료 공지](https://www.bitmex.com/contact/)
- **OKX 2018 무기한 목록 교차확인:** OKX 공식 공지에는 무기한 스왑 웹/앱 출시가 2018-12-19, EOS 12-24, ETH 12-26, BCH 12-27, BSV 12-28, XRP 12-29로 기록되어 있다. 그해 마지막 주의 출시 목록은 R4가 요구하는 2018년 전체·30심볼 선물 cohort의 대체 증거가 아니다. 이 확인은 당시 OKX perp 목록의 일부 출시일만 증명하며, 모든 거래소를 통틀어 계약이 30개 미만이었다고 일반화하지 않는다. [OKX 2018 거래 업데이트 목록](https://www.okx.com/en-sg/help/section/announcements-trading-updates/page/31), [EOS perp 출시](https://www.okx.com/en-us/help/eos-perpetual-swap-available), [XRP perp 출시](https://www.okx.com/cs/help/xrp-perpetual-swap-available)

## Binance Spot 2018 고정 코호트 전제 검증

- 공식 Binance 2018 연말 회고는 2018년 시작 당시 101개 코인과 245개 거래쌍을 기록하지만, 당시의 완전한 티커 목록을 제시하지 않는다. 따라서 이 숫자로 특정 자산군의 구성원을 역산하거나 2018년 자료 경로를 본 뒤 후보를 선택하지 않는다. [Binance 2018 Recap](https://www.binance.com/en/blog/all/286445971261435904)
- 공식 `Binance.com Stats 2017/8/27`은 Binance Spot 출시일과 일부 상장 연혁을 제공하지만 문서가 요약 목록이라고 밝히며, 2017년 말 상태가 아니다. 2017-09-06 중단 공지도 존재해 8월 목록을 연말 유효 자산 목록으로 간주할 수 없다. 전체 2017-12-31 유효 티커·거래쌍을 완전하게 재구성하는 공식 exhaustive snapshot은 이번 조사에서 확인되지 않았다. [Binance.com Stats 2017/8/27](https://www.binance.com/en/support/announcement/detail/115001292531), [2017-09-06 거래 중단 공지](https://www.binance.com/en/support/announcement/detail/115001444731)
- 코인과 pair 중 무엇을 표본 단위로 할지, 기준 시각·quote asset·상장/중단 효력시각·토큰 마이그레이션 정규화도 고정할 근거가 부족하다. 별도 제한 조회에서 BTCUSDT의 2018년·2022년 월별 Spot 객체 이름을 확인했지만, 이는 코호트 선정에 사용하지 않았고 전체 유니버스 증거가 아니다. 후보·수익률을 고르거나 Spot 사전등록을 만들지 않았다. 상세 경계는 [Binance Spot S3 PIT 코호트 점검](REPORT_BINANCE_SPOT_S3_PIT_COHORT_CHECK_20261124T0845Z.md)을 참조한다.
- **판정:** 공식 2018 listing 기반의 재현 가능한 고정 cohort를 증명하지 못했다. 그러므로 현재 보유 Spot 33심볼 manifest를 확대 대체하거나, S3 경로 존재 여부를 이용해 새로운 cohort를 구성하는 것은 허용되지 않는다. Binance Spot 파일럿도 별도의 공식 PIT/listing 증거가 생길 때까지 `DATA_BLOCKED`이며, 기존 선물 G의 대체가 아니다.
- 이 코호트 점검을 마칠 때 PID `30488`은 실행 중(경과 09:03:46, CPU 99.6%, RSS 298,480 KiB)이고, 장부 메타데이터는 17:30:59 KST / 70,225,619 bytes였다. 공유 장부 내용은 읽지 않았다.
- 08:44 UTC 재확인에서도 PID `30488`은 실행 중(경과 09:05:45, CPU 100.0%, RSS 313,536 KiB)이었다. `TRAIN_TRIALS.csv`는 여전히 17:30:59 KST, 70,225,619 bytes다. 프로세스 생존과 CPU 활동은 확인했지만 해당 시점에 어떤 trial을 계산하는지, 결과·완료 설정 수는 확인하지 않았다.
- **G 독립 레드팀:** Binance USDⓈ-M 카탈로그 범위가 2019/2020 이후라 2018 약세장 검증은 현재 선물 데이터셋으로 불가하다. 2022 가격 데이터는 카탈로그상 범위에 있으나 심볼별 연속성·funding/mark 결측·OI 가용성·실제 목표/손절 선도달 거래 수는 미확인이다. 35개 가격 파일 집합은 미사용 종목군임을 증명하지 않으며, M2 N≥200·거래 100개 및 다중검정 분모도 장부/실제 결과 없이는 판정할 수 없다. 
- **R4 재확인:** 08:25 UTC에도 PID `30488`이 실행 중이며 CPU 99.6%, RSS 184,160 KiB였다. 장부 수정 시각은 17:16:32 KST로 그대로다. 이는 프로세스 실행 상태만 증명하며 완료 셀 수·현재 전략 성과는 `확인 안 됨`이다. 종료나 장부 열람은 하지 않았다.
- **판정:** 이 독립 교차검토에서도 고정 G를 충족하는 데이터 경로가 새로 발견되지 않았다. 통과 후보 수는 코인 0/2, 국장 0/2, 미장 0/2로 유지한다. 이는 이번 점검에서 발생한 결과이며, R4의 최종 판정이 아니다.

## 병렬 연구 메모 3건 반영 (사용자 제공, 17:22 KST)

요청된 세 메모를 확인해 상태만 반영했다. 각각 원본 담당자의 보조 메모이며, 성과 검증이나 G 통과를 뜻하지 않는다.

- [현물 오더블록 파일럿 적격성](REPORT_SPOT_OB_PILOT_ELIGIBILITY_20261124_1722KST.md): 2018년 파일 12개월 완비는 4심볼, 2022년은 23심볼이다. Binance 공개 약관의 개인 비상업 역사 백테스트 범위 안에서 별도 구조 진단을 제안하지만, 선물 사전등록 대체가 아니고 30심볼/2018 G 실패다. R4 종료 및 writer 부재 확인 전 파일럿 실행 금지. 아직 preregistration이나 실행은 없다.
- [KIS 한국주식 데이터 경로](REPORT_KR_KIS_PIT_ROUTE_20261124.md): KIS 캐시 92개 CSV, 278530 부재, 출처·재사용권·TR 조정·PIT·상폐 증거가 없다. 기존 압축 캐시는 내용 확인 전이라 증거로 보지 않는다. KR 후보는 계속 `DATA_BLOCKED`.
- [미국주식 데이터 게이트](US_EQUITY_DATA_GATE_INVENTORY_20261124.md): 변화하는 종목 유니버스 전략은 상폐 OHLC·최종가치와 공식 PIT 구성 기록이 없어 부적격. 단일 고정 ETF 오버레이만 데이터 범위상 가능성이 있으나 티커·기업행위 필드의 footer 검증과 새로운 사전등록이 선행되어야 한다. 성과 후보가 아니다.
- R4 상태를 다시 확인한 시각은 08:27 UTC다. PID `30488`은 실행 중(경과 08:46:38, CPU 524:29.18, RSS 266,720 KiB)이고 공유 장부의 파일 수정시각은 17:16:32 KST였다. 장부 내용은 확인하지 않았으며 완료 셀·최신 성과는 확인되지 않았다. 따라서 R4 종료 전 파일럿·새 writer·추가 백테스트를 시작하지 않는다.

## Coinbase·Kraken 대체 현물 경로 메모 반영

사용자가 제공한 두 공식 출처 조사 메모를 검토해 현물 자료의 한계만 반영했다. 기존 Binance USDⓈ-M 목표/장부에 대체 적용하거나 새 후보로 세지 않았다.

- [Coinbase Exchange 2018 범위](REPORT_COINBASE_EXCHANGE_2018_COVERAGE_20261124_1735KST.md): 공식 OHLCV API는 300캔들/요청 제한과 무거래 구간 생략 가능성을 밝히며 full-history 연속성을 보장하지 않는다. 조사 메모가 직접 확인한 2018 지원 자산은 17개이고, 2018 Q4 자산 공지 완전성을 전제로 계산한 회사 전체 상한은 24개 미만이다(후자는 메모의 추론). 2018·2022 30개 공통 심볼 조건을 충족하지 못한다. Marketplace는 구매·라이선스 계약이 필요하고, 현재 Market Data 약관의 AI/알고리즘 개발·검증 관련 제한도 해소되지 않았다. 따라서 API/Marketplace 모두 현재 실험 입력으로 채택하지 않는다.
- [Kraken Spot 아카이브 적격성](REPORT_KRAKEN_SPOT_ARCHIVE_ELIGIBILITY_20261124.md): 공식 OHLCVT 아카이브는 pair 최초 거래부터 2026-09-30까지의 1m~1d 봉과 거래 데이터를 제공한다고 안내하며, 계정·키가 필요 없는 다운로드 경로가 있으나 이용약관은 자동 대량수집·로컬 변환·파생 통계 권한을 명확히 허용한다고 확인되지 않았다. 고정 CRYPTO_35 중 2022 이후 상장된 자산이 최소 8개여서 2018/2022 완전연도 공통자산 상한은 27개이며, pair별 gap·상폐 보존도 미검증이다. Spot은 funding이 있는 선물 전략과 별도 venue/instrument이므로 G 대체가 아니다.
- 두 메모는 공식 문서·상장 공지·기존 고정 심볼 목록만 검토했고, API 호출·다운로드·가격 행·공유 장부·R4를 건드리지 않았다. 새 데이터 경로를 찾았지만 G 적격 경로는 아니며, 검증 후보 수에는 변화가 없다.
- 메모 반영 시 R4 상태는 PID `30488` 실행 중(경과 약 08:59:45, CPU 약 98.8%)이었다. 공유 장부 메타데이터는 17:30:59 KST / 70,225,619 bytes로 마지막 점검과 같았다. 완료 설정 수 및 성과는 확인하지 않았다.

## R4 장시간 단일 설정 계산 여부 확인 (08:29 UTC)

- PID `30488`은 08:27 UTC와 08:28 UTC 두 차례 확인 모두 살아 있었고 CPU는 각각 99.3% 내외, 경과시간은 08:47:47에서 08:50:00으로 증가했다. `TRAIN_TRIALS.csv` 크기와 수정 시각은 두 확인에서 변하지 않았다(70,223,450 bytes, 17:16:32 KST).
- 코드 흐름을 읽기 전용으로 확인했다. `run()`은 설정별로 `_trial(config, barsets, zone_cache)`가 끝난 뒤 `_append(...)`를 호출하고, 그 다음 진행 메시지를 출력한다. 따라서 장부 mtime 정체만으로 멈춤이라고 판정할 수 없다. 이 확인은 가능한 설명을 제공할 뿐, PID가 어느 설정을 계산 중인지나 내부 진척을 증명하지 않는다.
- R4의 stdout/stderr는 파일이 아니라 pipe로 연결되어 있었고 공개된 진행 로그 파일은 확인되지 않았다. 실행 PID에는 신호를 보내지 않았으며 공유 장부 행을 읽지 않았다. **현재 상태: 실행 중, 셀 수/결과 확인 안 됨.** 다음 동작은 같은 PID 및 파일 메타데이터를 다시 확인하는 것이다. 재시작·중복 실행은 하지 않는다.

## 미국 ETF 후보의 스키마 전용 확인 (08:31 UTC)

- 외부 데이터 카탈로그가 가리키는 `yahoo_daily_us_etf.parquet`을 orderblock 연구 venv의 PyArrow footer API로만 열었다. 1,175,278행·2 row group이며 스키마는 `ticker`, `date`, `open/high/low/close`, `adj_close`, `volume`, `dividends`, `stock_splits`, `capital_gains`다. 이 점검은 파일 footer만 읽었으며 가격행은 반환하지 않았다.
- 외부 `us/` 디렉터리 파일명 검색에서는 ticker/universe manifest가 따로 발견되지 않았다. 따라서 `SPY`가 실제 종목 패널에 포함되는지, action 필드 값의 날짜·정의가 무엇인지, 2026-05-31까지 cutoff 전용 입력이 이미 있는지는 아직 확인되지 않았다. 파일 전체 기간에는 cutoff 이후 자료가 들어 있으므로 본 점검에서는 어떤 행도 읽지 않았다.
- **다음 판정:** 단일 ETF 실험을 바로 실행할 수 있는 것은 아니다. 정확한 ETF 존재를 비행 데이터 메타데이터나 별도 사전등록된 cutoff snapshot으로 확인하고, cutoff 이후 행을 절대 열지 않는 입력 경로와 G 적용 가능성을 책임자가 먼저 승인해야 한다. 고정 단일 ETF는 미사용 종목군 60% 기준을 충족하지 못하므로 현재 G 아래 합격 후보가 될 수 없다는 한계도 유지된다.
- 같은 시각대에 재조회한 R4는 여전히 PID `30488`, CPU 약 96.7%, 경과 08:51:06이었다. 장부 파일은 70,223,450 bytes / 17:16:32 KST로 변하지 않았다. 실행 중 프로세스가 설정별 `_trial()` 완료 후에만 `_append()`하도록 되어 있으므로 정체 판정은 내리지 않았다. 결과 수치는 확인 안 됨이다.

## R4 후속 진행 증거 (08:32 UTC)

- 앞선 상태 기록 이후 60초 기다린 뒤 같은 PID `30488`을 재확인했다. 프로세스는 계속 살아 있고 CPU 100%, 경과 08:53:37, RSS 425,984 KiB였다.
- `TRAIN_TRIALS.csv`는 파일 메타데이터만 비교했다. 수정 시각이 17:16:32에서 17:30:59 KST로 바뀌었고 크기는 70,223,450에서 70,225,619 bytes로 2,169 bytes 증가했다. 이는 R4가 새로 파일을 쓴 증거다. 행 내용은 읽지 않았으므로 기록된 설정 수·결과·G 판정은 여전히 확인 안 됨이다.
- 따라서 이전의 장부 정체 우려는 해소됐다. R4를 계속 보존하고, 완료/종료 전에는 파일럿·다른 writer·중복 실행을 시작하지 않는다.

## 2018 코인 자료 경로 재확인 및 현재 실행 체크포인트 (08:46 UTC)

- 공식 Binance 자료만으로 2017-12-31 기준 전체 Spot 자산/거래쌍 목록과 거래 가능 상태를 완전하게 복원하는 스냅샷을 찾지 못했다. 2017-08-27 공식 통계 공지는 일부 목록이라고 한정하고, 2017-09-06 거래·입금 중단 공지는 앞선 티커 일부가 이미 거래 불가였음을 보여준다. 따라서 연말 코호트는 아직 고정되지 않았다. [Binance 2017 통계](https://www.binance.com/en/support/announcement/detail/115001292531), [Binance 2017 중단 공지](https://www.binance.com/en/support/announcement/detail/115001444731)
- 공식 공지센터에는 신규 상장·상폐 카테고리, 페이지네이션, sitemap이 있지만 이들이 2017년 전체 유효 이벤트를 빠짐없이 보존한다는 보장은 확인되지 않았다. 공지 작성일만으로 거래 개시·중단 효력 시각, 현물/선물 구분, 개별 거래쌍을 완전하게 복원할 수도 없다. 별도 제한 조회가 BTCUSDT 단일 pair의 2018·2022년 각 12개월 ZIP 객체 이름을 확인했다. 이 결과는 해당 archive object 경로의 존재만 뜻하며 연속된 봉 데이터, 30개 base asset, 기준일 PIT 코호트를 증명하지 않는다.
- 별도 독립 검토도 무상·무계정 공식 자료에서 2018년 연속 파생 OHLC/mark/funding 30종 이상을 함께 입증하지 못했다. Binance Futures는 2019년 9월 출시라 2018 자료원이 아니며, BitMEX 공식 예시는 XBTUSD 과거 quote 가능성만 보여준다. 이 예시는 30개 계약, 연속성, mark/funding을 입증하지 않는다. Deribit은 초기 BTC 중심, OKX 공개 이력은 2021/2022/2023 이후로 안내된다. [Binance Futures 출시](https://www.binance.com/en/support/announcement/detail/360033273472), [BitMEX API 예시](https://github.com/BitMEX/api-connectors/blob/master/official-http/python-swaggerpy/README.md#instrument-data), [Deribit 소개](https://support.deribit.com/hc/en-us/articles/25944687804957-About-Us), [OKX 과거 자료](https://www.okx.com/en-us/historical-data)
- Spot S3의 전체 코호트 탐색은 여전히 보류한다. 먼저 고정된 공식 PIT 유니버스가 필요하다. BTCUSDT 단일 pair 결과를 후보 선택이나 수익 평가에 쓰지 않았으며, Spot 자료는 선물·펀딩 전략을 대체하지 않는다. 새 유니버스·전략 후보 또는 수익률은 추가되지 않았다.
- 국장 KIS 관련 보조 메모는 개인 업무의 시세 이용 문구를 확인했지만, 오프라인 과거 백테스트와 장기 CSV 보존·백업 권리를 확인하지 못해 권리 게이트를 열지 않았다. `KR_069500.csv`는 파일 존재만으로 기간·품질·권리 미검증이며 기존 278530 자료의 대체가 아니다. 가격행이나 키는 확인하지 않았다.
- 승인된 권한 상승으로 `/bin/ps -p 30488`을 읽기 전용 실행해 PID 30488이 `search_crypto_r4.py`로 실행 중임을 확인했다(경과 09:08:42, CPU 100.0%, RSS 389,840 KiB, 상태 RNs). 장부는 메타데이터만 비교했으며 17:46:06 KST / 70,229,939 bytes였다(이전 17:30:59 KST / 70,225,619 bytes에서 갱신). 행 수·trial 완료 수·성과값은 확인하지 않았다. R4를 중단·재시작하지 않았고, 새 writer나 백테스트도 시작하지 않았다.
- `df -h` 기준 저장소가 있는 볼륨의 여유 공간은 78 GiB였다. 이번 점검에서 대용량 연산은 수행하지 않았다.
- 이 체크포인트 이후 받은 같은 R4의 메타데이터 폴링은 PID 30488 실행 중(경과 09:09:55, CPU 약 100%)과 장부 갱신 17:47:45 KST / 70,234,256 bytes를 보고했다. 이는 17:46:06 KST / 70,229,939 bytes보다 증가한 값이다. 이는 호출 스레드가 보고한 관측이며 현재 재조회 값은 아니다. 행·시도 수는 여전히 확인하지 않았다.
- 60초 대기 후 직접 재조회한 시각은 08:50 UTC다. PID 30488은 계속 실행 중(경과 09:12:28, CPU 98.9%, RSS 309,888 KiB, 상태 RNs)이며, 장부 파일 메타데이터는 17:50:23 KST / 70,240,746 bytes다. 17:47:45 이후에도 파일이 증가했다. 내용은 읽지 않았으므로 시험 수·결과는 확인 안 됨이다.
- 별도 독립 검증 스레드는 `scratchpad/strategy_bt/orderblock_loop`에서 `/Users/user/CODE/trading_data/cache/orderblock/venv/bin/python -m unittest discover -s tests -p 'test_search_us_macro_overlay_v1.py' -v`를 실행해 합성 입력 테스트 26개 통과(0.069초)라고 보고했다. 임시 `TRADING_DATA_DIR`를 사용했고 실데이터·공유 장부를 읽지 않았다고 했다. 이 테스트는 합성 harness의 안전성/인과성만 검증하며 SPY 데이터 적격성, 수익, G 통과를 입증하지 않는다. 나는 이 테스트를 재실행하지 않았다.
- 같은 별도 스레드가 이어서 보고한 R4 메타데이터는 PID 30488 CPU 사용 중, 장부 17:51:18 KST / 70,242,907 bytes다. 이는 전달받은 관측이고, 장부 내용이나 trial 수는 확인하지 않았다.
- 08:52 UTC 직접 재조회에서 PID 30488은 계속 실행 중(경과 09:13:42, CPU 99.9%, RSS 312,448 KiB, 상태 RNs)이고 장부 메타데이터는 17:52:12 KST / 70,245,070 bytes다. 공유 장부 내용은 읽지 않았으며 현재 완료 trial 수와 성과는 확인 안 됨이다.

## 4역할 데이터·가설 레드팀 결과 (읽기 전용)

- **국장:** 금융위 API는 OHLCV 필드가 있으나 실시간 설명만으로 과거 전기간·상폐 포함·PIT를 증명하지 않는다. 공공누리 제4유형은 변경·2차 저작물 제한이 있어 패널 정규화·결합 권리는 별도 확인 필요하다. KIND 상폐현황과 ETF 분배 공시는 공식 이벤트 단서지만 완전한 상폐 최종 가치·전종목 OHLCV·기업행위 이력을 구성하지 못한다. 판정은 `DATA_BLOCKED` 유지. [금융위 주식시세](https://www.data.go.kr/data/15094808/openapi.do), [공공누리 제4유형](https://www.kogl.or.kr/info/licenseType4.do), [KIND 상장폐지현황](https://kind.krx.co.kr/investwarn/delcompany.do?method=searchDelCompanyMain), [KIND ETF 분배금 공시 예시](https://kind.krx.co.kr/external/2026/11/11/000448/20261111000929/68659.htm)
- **미장:** 공개 `sp500-data` 저장소는 S&P 500 구성 이력·일봉·기업행위 필드를 제공한다고 주장하지만 작성자 주장이고, CRSP/Tiingo/Yahoo/WIKI 혼합 출처·명시적 라이선스 부재·상폐 최종 정산 미확인·범위가 S&P 500으로 제한된 점 때문에 사용 적격이 아니다. 무료 샘플·요인 자료도 필요한 전체 PIT+개별 OHLCV를 채우지 않는다. 판정은 `DATA_BLOCKED` 유지. [저장소 README](https://github.com/Johnbrick123/sp500-data), [라이선스 경로](https://github.com/Johnbrick123/sp500-data/blob/main/LICENSE)
- 두 결과는 독립 연구 스레드의 보고를 받아 반영했으며, 이 세션에서 가격 행·API·데이터 다운로드·백테스트를 수행하지 않았다. 기존 G 문턱을 통과한 주식 전략은 추가되지 않았다.
- 이 체크포인트의 S3 정정: 별도 공식 `ListObjectsV2` 메타데이터 확인이 BTCUSDT 1m Spot의 2018년 12개월(객체 합계 25,281,048 bytes)과 2022년 12개월(26,608,406 bytes) ZIP 객체 경로를 확인했다. 이는 단일 pair의 월별 archive object 존재만 입증하며 실제 봉 연속성, 기준일 유니버스, 30개 이상의 base asset을 입증하지 않는다. 조회 내역은 [Binance Spot S3 PIT 코호트 점검](REPORT_BINANCE_SPOT_S3_PIT_COHORT_CHECK_20261124T0845Z.md)에 있다.

## 오더북 기반 신규 가설 검토 — 사전등록 아님

- 독립 연구원은 기존 캔들 오더블록과 다른 미시구조 가설 2개를 제안했다: (1) 큰 시장가 매도 불균형에도 가격이 밀리지 않는 매도 흡수 구간, (2) 호가 깊이가 급감한 뒤 회복되는 유동성 재충전 구간. 둘 다 구간 확정 뒤 최초 재방문에서만 진입하고, 다음 관측 가능 시점 체결·고정 손절·2R 목표·시간 만료를 사용하도록 설계 가능하다. 아직 성과 측정 전이므로 시도 수나 후보 수에 포함하지 않는다.
- 첫 가설은 순서가 보장된 체결·최우선 호가 업데이트로 OFI를 계산해야 한다. 두 번째는 과거 diff-depth 스냅샷/업데이트 연결과 여러 단계 잔량의 연속 이력이 필요하다. OHLCV로는 어느 가설도 재구성할 수 없다. 현재 고정 G의 2018년 시작·30+ 심볼 역사자료와 이용권을 충족하는 해당 호가 이력 경로가 확인되지 않아 `DATA_BLOCKED`이며, 역사적 적격 자료 확인·사전등록 전 실험은 금지한다. OFI 문헌은 메커니즘 설명이지 수익성 증거가 아니다. [Cont·Kukanov·Stoikov](https://arxiv.org/abs/1011.6402), [Binance USDⓈ-M 시장 스트림 문서](https://developers.binance.com/en/docs/products/derivatives-trading-usds-futures/websocket-market-streams/Connect)
- 새 상태 전달: PID 30488은 실행 중(경과 09:16:28, CPU 95.4%)이며 장부 메타데이터는 17:54:58 KST / 70,247,230 bytes로 갱신됐다고 보고됐다. 내용·행·시도 수는 읽지 않았다.
- **총괄/레드팀 감사:** 고정 G의 모든 게이트는 그대로 유지한다. 현 자료 상태로 코인 2018 레짐, 주식 PIT·상폐·권리 게이트가 닫혀 있어 6개 목표의 달성 경로가 아직 증명되지 않았다. 이는 기준을 바꾸거나 연구를 끝낼 이유가 아니라, 해당 시장 후보를 `DATA_BLOCKED`로 유지하고 R4 및 대체 데이터 증거를 계속 추적할 근거다. R4-C volume-displacement는 R4-A displacement의 내포된 하위집합이므로 독립 전략으로 세지 않으며, R9/R10도 결과가 아니라 OOS 상관·신호 중복·메커니즘 독립성이 확인되어야 2개로 셀 수 있다.
- 같은 감사에서 현재 `search_crypto_r11.py`, `search_crypto_r12.py`는 있으나 `PREREG_R11_R12.md` 및 R11/R12 테스트 파일은 없음을 확인했다. 따라서 이 둘은 실행 자격이 없다. 실행 가능한 다음 단계는 R4 PID 종료와 다른 writer 부재 확인 → 그 뒤 사전등록 해시·코드 지문 기준 72설정 결과 대사 → TRAIN 보고만 작성하는 순서다. 현재 R4 완료 전 장부는 열지 않는다.
- 감사자가 `AGENTS.md`와 `LOOP.md`의 동시성 문구 충돌을 지적했다. 이번 작업에서는 실제 R4와 공유 장부를 보호하기 위해 같은 장부에 병렬 writer를 추가하지 않는다. CPU·워커를 제한하는 자원 규칙으로 해석하지 않으며, 다른 독립·읽기 전용 분석은 병행할 수 있다. 커밋·푸시는 검증된 작업 단위가 끝나고 소유 범위를 확인한 뒤 처리한다.
- 추가로 전달된 합성 검증 결과: 별도 스레드가 `/Users/user/CODE/trading_data/cache/orderblock/venv/bin/python -m unittest discover -s tests -p '<test_file>' -v` 형식으로 실행했다고 보고했다. 결과는 `test_kr_pit_manifest_v1.py` 13/13(0.022초), `test_search_us_macro_overlay_v1.py` 26/26(0.069초), `test_search_crypto_r8.py` 10/10(0.003초), `test_search_crypto_r9.py` 34/34(0.011초), `test_search_crypto_r10.py` 23/23(0.009초), `test_gate_check.py` 14/14(0.302초), 합계 120/120이다. `test_gate_check.py` 명령은 별도 보고에 `python -m unittest discover -s tests -p 'test_gate_check.py' -v`로도 명시됐다. 테스트는 합성 입력과 임시 ledger/cache를 사용하며 공유 장부·실데이터를 읽지 않았다고 한다. 이 턴에는 재실행하지 않았다. 통과는 하네스/합성 경계 동작만 검증하며 실데이터 적격성·전략 수익·G 통과를 증명하지 않는다.
- 이 단락 작성 당시 새 직접 재조회에서 PID 30488은 실행 중(경과 09:18:15, CPU 99.4%, RSS 349,008 KiB, 상태 RNs)이며 `TRAIN_TRIALS.csv` 메타데이터는 17:54:58 KST / 70,247,230 bytes였다. 행 수·trial 수·성과는 확인하지 않았다.
- 후속 직접 확인에서도 PID 30488은 계속 실행 중(경과 09:20:27, CPU 100.0%, RSS 290,544 KiB, 상태 RNs)이었고 `TRAIN_TRIALS.csv` 메타데이터는 17:57:33 KST / 70,249,393 bytes로 증가했다. 장부 내용은 읽지 않았다. 현재 셀 완료 수·R4 성과·남은 셀은 확인 안 됨이다.

## 합성 테스트 품질 적대 감사 — 수정 전 결함 기록

독립 스레드의 정적 검토는 위 120/120 통과를 취소하지 않지만, 이를 실제 데이터·G 통과 증거로 해석하지 말라고 판정했다. 지적된 결함은 아래와 같고, 이 단계에서 소스·테스트는 수정하지 않았다.

- **게이트 판정기:** 동결 후보 상태를 증명하지 않은 채 모든 후보 행을 분모로 쓸 수 있다. M2 200건 fixture는 단일 합성 AAA 이벤트이며 실제 OOS 완전성·출처 대사가 없다. 2배 비용·1봉 지연 companion CSV는 기본 거래의 +2% 복제라 비용 재계산·지연 재실행·동일 거래 ID를 보장하지 않는다. 미사용 심볼 fixture도 AAA 한 종목뿐이다. 독립 재구현은 숫자 `1.0` 비교만 한다. 데이터 무결성은 2개 봉·임의 SHA 형식·플래그에 그친다. 2018/2022 표시는 합성 coverage다. RC/SPA 통과는 mocked p=0.001이다. random-entry/circular-shift CLI 경로가 없어 전체 판정은 fail-closed `incomplete`가 맞지만, G 구현 자체는 불완전하다.
- **미장 합성 테스트:** 임시 fixture 격리와 cutoff 후 입력의 숫자 파싱 차단은 의미 있다. 그러나 next-open 테스트의 close=open fixture에는 체결가격 기록이 없어 실제 다음 시가 체결을 증명하지 않는다. TEST 이후 행 미접근 감시 sentinel이 없다. COT causal test는 과거 신호의 불변성만 확인해 미래 신호 변경 누출을 막지 못할 수 있고, VIX future-mutation oracle도 없다. 기업행위 ex-date와 다음 시가 체결 경계도 미검증이다.
- **국장 합성 테스트:** cutoff 뒤 action 다음에 cutoff 안의 정상 행이 오는 비정렬 입력에서 parser 조기 종료 누락 가능성, 정산 현금액 빈값/0 방어, 거래일 달력 완전성, 재사용 심볼 입력의 최종 상태 assertion이 미흡하다. 부분 달력과 가격만 맞는 fixture도 통과할 가능성이 있다.
- **후속 검증 설계:** (1) 동결 후보·분모의 명시적 상태 전이/출처 연결, (2) 거래별 비용 2배 및 1봉 지연을 실제 simulator로 재실행하고 ID·입력 지문을 교차검증, (3) 미사용 심볼 다수 fixture와 결과 비율 경계, (4) 독립 엔진 재구현을 거래별 반환 경로로 비교, (5) 임의 hash·coverage flag 대신 실제 cutoff/fingerprint 검증, (6) 매매신호 이후 데이터 변조에 대한 prefix/full-series 미래누출 oracle, (7) 실제 다음 봉 시가 체결, COT/VIX 미래변조 및 기업행위 ex-date 경계, (8) KR 비정렬 행·정산현금·완전 거래일 달력·최종 BLOCKED assertion을 추가 설계한다. R4 실행 중에는 이 테스트·코드 보강이나 다른 연구 루프를 시작하지 않는다.
- 따라서 `120/120 합성 테스트 통과`는 전달된 테스트 실행 결과로 유지하되, 테스트 범위의 한계 때문에 실제 G 검증·시장 적격성·전략 성과 증명은 **0건**이다.
- 이 정적 감사 업데이트 전 직접 R4 폴링은 08:55 UTC에 PID 30488 실행 중(경과 09:22:29, CPU 100.0%, RSS 318,416 KiB, 상태 RNs), 장부 메타데이터 17:59:59 KST / 70,251,557 bytes를 확인했다. 이전 17:57:33 KST / 70,249,393 bytes에서 파일이 증가했다. 장부 내용과 셀별 결과는 읽지 않았다.
- 이후 독립 폴링이 09:24:03 elapsed에서 PID 30488 활성(CPU 100%, RSS 347,600 KiB), 장부 18:02:20 KST / 70,253,713 bytes라고 보고했다. 직접 재확인에서 PID는 경과 09:24:23, CPU 100%, RSS 277,696 KiB, 상태 RNs로 실행 중이었고 장부 mtime/size는 18:02:20 KST / 70,253,713 bytes였다. 계속 실행 중이고 파일이 증가했지만 완료 설정 수·성과는 확인 안 됨이다. 장부 행은 열지 않았다.
- 60초 후 직접 확인한 PID 30488은 경과 09:25:58, CPU 100%, RSS 302,912 KiB, 상태 RNs로 계속 실행 중이었고 장부는 18:02:20 KST / 70,253,713 bytes로 변하지 않았다. 별도 폴링도 같은 시각대에 파일 변화가 없었다고 보고했다. 프로세스가 살아 있고 CPU를 쓰며, 코드상 각 설정 종료 후에만 기록하므로 이 짧은 무기록 구간은 중단 증거가 아니다. 재시작하지 않았다.
- 현재 사전등록의 R4/R8 fingerprint addendum은 기존 R4 79행을 모두 보존하고 현 코드 hash와 일치하는 과거 행이 0개라고 명시한다. 따라서 live R4 cohort는 과거 `REPORT_R4_COIN_GRID.md`의 72개 결과나 이전 6/72 완료 수를 재사용하지 않는 신규 72회다. R8은 별도 1회이며 R4 종료 전 실행하지 않는다. 예정 N=1,604는 문서상 기준이며, 실제 누적 분모는 실행 직전 이후 장부 writer가 추가됐을 수 있어 종료 뒤 공식 장부 대사로 다시 고정해야 한다.
- 정적 코드 지문을 현재 소스 6개 파일(`crypto.py`, `search_crypto.py`, `search_crypto_r4.py`, `data_access.py`, `metrics.py`, `resource_guard.py`)의 바이트를 문서화 순서로 연결해 계산한 값은 `bc643f64ec2524a7e8fac5cdb7147fdb3f0be4e10a17bde7431b4fe28d50fd66`다. PID 30488 시작은 08:38:38 KST였고 `resource_guard.py` 파일시각은 15:21:14 KST로 더 늦지만 현재 파일의 Git index blob과 worktree blob hash는 같다(`c00b8ae9…`). 파일시각만으로 내용이 바뀌었다고 말할 수 없으므로, 프로세스 종료 뒤 장부 기록 hash와 현재/보존된 실행 hash를 실제 대조하기 전까지 정확한 실행 hash는 확인 안 됨이다.
- R4 구현을 사전등록과 정적으로 대조해 signal 정의, next-bar open, D 24/48, target/stop, same-bar stop 우선, adverse-only funding 경계와 48봉 보유는 대응하는 코드를 확인했다. 한 경계 차이는 진입시가가 롱 OB 저가와 같을 때 `<=`로, 숏 OB 고가와 같을 때 `>=`로 거래를 건너뛰는 부분이다. 문구상 “경계를 넘어섬”은 엄격 초과로도 읽힐 수 있어 동등 경계 처리가 사전등록과 일치하는지 애매하다. 보수적 제외로 보이지만 사전등록 재해석·코드 변경은 실행 도중 하지 않고, 완료 후 결과 대사 전 adjudication 항목으로 남긴다.
- 추가로 `crypto.py`의 `simulate_trade` docstring은 entry timestamp와 같은 funding event를 포지션이 정산 직전에는 열리지 않았으므로 제외한다고 설명한다. 실제 `_funding_order()`는 이를 순서 미확정으로 표시하고 R4의 `adverse_only` 정책은 유효한 불리한 흐름을 손익에 반영한다. 이는 현재 R4 사전등록의 동등시각 adverse-only 규칙과 구현에는 맞지만, docstring 및 관련 테스트(정확 entry timestamp의 favorable/adverse funding 및 daily-PnL 대사)는 불일치/미검증이다. 실행 중 수정하지 않고, R4 완료 뒤 거래결과 해석 및 문서·테스트 보강 전 확인할 항목이다.
- 독립 리뷰어는 ambiguous funding 거래를 primary 성과에 포함하는 것을 초기에는 사전등록 불일치로 분류했다. 그러나 현재 R4 전용 addendum §3은 ambiguous valid-price 거래의 adverse-only 손익 반영을 primary로 보존하고 strict 표본에서만 제외한다고 명시한다(§4는 primary와 strict를 분리 유지). 코드 `_trial`도 ambiguous 거래를 `returns`/기본 일간곡선에 포함하고 `strict_*`에서 제외한다. 따라서 그 첫 주장은 현재 읽은 구체적 R4 addendum에 비춰 **확정된 불일치로 채택하지 않는다**. 독립 리뷰어에게 해당 조항을 대조해 재판정 요청했다. missing mark/settlement sentinel 거래는 별도 fail-closed 규칙으로 unscorable 처리해야 하며 이와 혼동하지 않는다.
- 직접 재확인 시각대의 PID 30488은 경과 09:31:00, CPU 99.6%, RSS 267,936 KiB, 상태 RNs로 계속 실행 중이었다. 장부 메타데이터는 18:07:18 KST / 70,258,039 bytes로 이전 18:04:52 KST / 70,255,878 bytes보다 증가했다. 내용이나 완료 설정 수는 읽지 않았다.
- 다음 read-only 관측은 09:32:08 UTC 보고로, PID 30488 활성(RNs, CPU 99.3%, RSS 307,568 KiB), 장부 18:09:40 KST / 70,260,199 bytes로 갱신됐으며 여유 디스크 78 GiB였다. 이 전달 상태도 장부 내용·fresh cohort 완료 수를 공개하지 않는다.
- **현재 스레드 재확인 (2026-11-24 09:15 UTC):** PID 30488은 `search_crypto_r4.py`를 실행 중(RNs, 경과 09:36:42, CPU 98.9%, RSS 295,088 KiB)이었다. `TRAIN_TRIALS.csv`는 메타데이터만 확인했고 수정 시각 18:15:05 KST, 크기 70,271,002 bytes였다. 이전 기록(18:14:17 KST / 70,268,837 bytes)보다 증가했다. 장부 행·fresh cohort 완료 수·성과는 읽거나 확인하지 않았다. 이번 상태와 기존 보고서를 대조하고 `git diff --check`를 실행했으며 오류가 없었다. R4 종료 및 다른 writer 부재 전까지 동일 PID를 보존하고 장부 내용을 열지 않는다.
- **현재 스레드 재확인 (2026-11-24 09:16 UTC):** 직후 재조회에서 PID 30488은 `search_crypto_r4.py` 단일 writer로 계속 실행 중(RNs, 경과 09:37:43, CPU 95.3%, RSS 276,160 KiB)이었다. 장부는 metadata-only로 18:15:55 KST / 70,273,170 bytes로 증가했다. 행 내용과 설정 수는 읽지 않았다. 이 확인은 live 실행 보존 지시와 일치하며, 종료 시 전체 writer 부재를 확인한 뒤 새 72개 행만 현재 code/grid/data fingerprint로 대사하고, 그 뒤 고정 G 및 사전등록으로 판정한다.
- **현재 스레드 재확인 (2026-11-24 09:17 UTC):** PID 30488은 여전히 유일한 `search_crypto_r4.py` writer로 실행 중(RNs, 경과 09:38:28, CPU 99.3%, RSS 291,776 KiB)이었다. `TRAIN_TRIALS.csv` 메타데이터는 18:16:45 KST / 70,275,338 bytes로 갱신됐다. 장부 행, 새 코호트의 완료 수와 성과는 열지 않았다. 보고서 `git diff --check`는 통과했다.
- **현재 스레드 재확인 (2026-11-24 09:17:53 UTC):** PID 30488은 계속 활성(RNs, 경과 09:39:11, CPU 97.6%, RSS 300,704 KiB)이고, `search_crypto_r4.py` 프로세스는 하나만 확인됐다. `TRAIN_TRIALS.csv`는 메타데이터만 조회했으며 18:17:39 KST / 70,277,504 bytes로 증가했다. 행 내용·trial 수·성과는 확인하지 않았다.
- **현재 스레드 재확인 (2026-11-24 09:19 UTC):** PID 30488은 활성(RNs, 경과 09:40:43, CPU 98.5%, RSS 292,032 KiB)이었으며 `search_crypto_r4.py` writer는 한 개였다. `TRAIN_TRIALS.csv` 메타데이터는 18:19:13 KST / 70,296,896 bytes로 증가했다. 장부 행 및 새 코호트의 완료 수·성과는 읽지 않았다.
- **KRX 상장폐지 시세 경로 조사 추가:** `REPORT_KRX_DELISTED_PRICE_ROUTE_20261124.md`에서 공식 KRX 화면에 일별 OHLCV·상장폐지일·사유 필드가 표시됨을 확인했다. 전체 과거 기간, 최종 현금정산가, 시계열 완전성은 입증되지 않았고 KRX 이용약관/API 목적 제한으로 로컬 백테스트용 자동 수집·보관 권리도 미확인이다. 국장 데이터 게이트는 계속 닫혀 있으며 자료는 전략 테스트에 사용하지 않는다.
- **현재 스레드 재확인 (2026-11-24 09:20 UTC):** PID 30488은 활성 상태(RNs, 경과 09:42:01, CPU 99.6%, RSS 284,864 KiB)였으며 `search_crypto_r4.py` 프로세스 한 개만 확인했다. `TRAIN_TRIALS.csv` 메타데이터는 18:20:32 KST / 70,311,988 bytes로 증가했다. 디스크 여유는 78 GiB다. 장부 행과 fresh cohort 완료 수·성과는 열지 않았다.

## R4 신규 코호트 대사 및 TRAIN 진단 (2026-11-24, 프로세스 종료 후)

- PID `30488` 종료, R4 writer 및 장부 파일 핸들 부재를 확인한 뒤에만 장부를 스트리밍했다. 종료 코드/stdout 전체는 보존되지 않았으므로 이를 정상 종료로 단정하지 않는다.
- 장부는 1,603개 데이터 행이다. 사전등록 당시 계획 분모 1,604에는 별도 R8 1회가 포함됐으나, 현재 실제 장부에는 그 1회가 없다. 현 행 기준 `0.05/N = 0.0000311915`; 이후 새 시도 전 실제 행 수를 다시 동결해야 한다.
- 새 R4 묶음은 grid SHA `e203d499…`에서 정확히 72/72 고유 설정(15m·1h·4h 각 24개)이며 모두 `completed`다. 데이터 fingerprint는 주기별 하나씩 존재하고 빈 값이 없다. 모든 설정은 32개 종목으로 계산됐다.
- 기록 code SHA `74d6301d…`는 현재 worktree `bc643f64…` 및 현재 HEAD/index `77a5f663…`와 다르다. 원인을 조사한 결과 R4 행은 2026-11-23 23:52 UTC부터 2026-11-24 09:21 UTC까지 기록됐고, 그 사이 15:22 KST 커밋 `21c1387`이 `resource_guard.py`를 1,614바이트에서 499바이트로 바꾸며 실행 lock·`nice(10)`만 제거했다(40GiB 디스크 검사 유지). R4가 시작할 때 읽은 나머지 다섯 파일과 이 커밋의 부모 버전 `resource_guard.py`를 결합하면 장부 code SHA `74d6301d…`가 정확히 재생성된다. `search_crypto_r4.py`는 시작 전에 수정된 dirty worktree였으므로 이 혼합 파일 조합은 하나의 commit/tree로 보존돼 있지 않다. hash mismatch는 설명되지만 원자적 실행 snapshot/stdout/종료 코드는 없다. 따라서 아래 수치는 **기록된 TRAIN 진단**이며 현재 코드의 독립 재현이나 재현 가능한 승인 결과로 부르지 않는다.
- 새 72행의 세 TRAIN fingerprint는 앞선 72행 묶음(`f54a64a3…`)의 세 fingerprint와 각각 같고, 두 묶음의 공통 24개 지표 값은 72/72 설정 모두 일치했다. 이는 같은 입력·기록 지표가 반복된다는 일관성 확인일 뿐 독립 표본이나 추가 성과 증거가 아니다.

| 시간대 | M2 목표 선도달률 | PF | 기대값 (bp/거래) | 연환산 Sharpe | 합성 게이트 핵심 기준 동시 충족 |
|---|---:|---:|---:|---:|---:|
| 15분 (24개) | 28.50–39.64% (Wilson 상한 39.21%) | 0.725–0.826 | -17.25–-11.28 | -3.563–-2.390 | 0/24 |
| 1시간 (24개) | 29.08–39.23% (Wilson 상한 38.35%) | 0.756–0.956 | -35.51–-5.58 | -2.566–-0.292 | 0/24 |
| 4시간 (24개) | 27.03–38.79% (Wilson 상한 36.32%) | 0.819–1.076 | -48.08–+21.06 | -0.984–+0.328 | 0/24 |

핵심 일부 기준은 M2 ≥80%, PF ≥1.30, 기대값 ≥15bp, Sharpe ≥1.0의 동시충족이다. 전 72개에서 M2 비율과 Wilson 하한은 각각 80%에 못 미쳤다. 엄격 funding 판정불가도 72/72 설정에서 0보다 컸다.

사전등록된 TRAIN 선별식(점수화 거래 ≥100, 기대값 >0, 최대 3개)에 들어가는 상위 세 설정은 다음과 같다. 이들은 잠정 TRAIN 후보이며 동결 TEST 후보가 아니다.

| 설정 | 거래 / 종목 | 기대값 | PF | Sharpe | 엄격 기대값 / PF / Sharpe |
|---|---:|---:|---:|---:|---:|
| displacement · 4h long · D24 · 2R | 966 / 32 | +21.06bp | 1.076 | 0.328 | +45.13bp / 1.157 / 0.340 |
| displacement · 4h long · D48 · 2R | 1,024 / 32 | +20.42bp | 1.073 | 0.308 | +10.81bp / 1.037 / 0.086 |
| volume-displacement · 4h long · D48 · 2R | 954 / 32 | +0.44bp | 1.002 | 0.006 | -14.39bp / 0.952 / -0.109 |

첫 두 설정은 같은 R4-A 가설의 기한 변형이고, R4-C는 R4-A에 거래량 조건을 더한 내포된 하위집합이다. 따라서 세 설정을 독립 전략 세 개로 셀 수 없다. `FROZEN_TEST_CANDIDATES.csv`는 헤더만 있고 동결 후보 0개다. OOS/TEST, 2018 게이트, 2배 비용·1봉 지연, 무작위/순환이동 귀무, 최종 G는 실행되지 않았다. 이 코호트만으로 합격 후보는 0개다.
