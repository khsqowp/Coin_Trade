# Gate.io 2018 파생 데이터 게이트 점검 — 2026-11-24

## 결론

Gate 공식 자료는 과거 선물 캔들·체결·mark price·funding 데이터를 내려받을 수 있는 형식과 2018년 12월 perpetual 출시를 보여준다. 하지만 고정 30개 코인 유니버스가 2018년과 2022년 모두에서 관측 가능하다는 증거가 없고, 2018년이 출시월에 불과해 현재 오더블록 루프의 데이터 게이트를 열지 못한다. 이 경로로 다운로드하거나 백테스트하지 않았다.

## 직접 확인한 공식 근거

- Gate의 공식 연혁은 perpetual contract 출시 시점을 2018년 12월로 기록하고, 2018-12-11 FAQ는 당시 지원 대상을 BTC와 USDT로 설명한다. 이는 2018년 초부터의 연간 파생 시계열 또는 30개 코호트를 뒷받침하지 않는다: https://testnet.gate.com/media-kit, https://www.gate.com/pt/help/futures/futures/16695
- Gate의 2021-07-26 공식 안내는 과거 데이터 파일 형식과 URL 규칙을 제공한다. 파생 데이터 종류는 `trades`, `orderbooks`, `candlesticks_*`, `mark_prices`, `funding_updates`, `funding_applies`; 경로 예시는 `https://download.gatedata.org/${biz}/${type}/${year}${month}/${market}-${year}${month}.csv.gz` 형식이다. 이 안내는 경로 패턴과 데이터 종류의 근거이지 개별 파일의 실제 존재·연속성 증거는 아니다: https://www.gate.com/uk/announcements/article/21688/flow%20crypto%20cours
- Gate의 현재 Historical Quotation 페이지는 다운로드 UI의 candlestick·filled-order 자료 시작점을 2023년 1월, market depth 자료 시작점을 2021년 8월로 표시한다. 같은 페이지의 API URL 예제는 2023년 자료를 사용한다. 따라서 그 페이지도 2018·2022 파일의 존재를 입증하지 않는다: https://www.gate.com/fr/developer/historical_quotes
- Gate 공식 API 문서는 계약별 funding history endpoint와 Unix timestamp `from`/`to` 매개변수를 설명한다. 이는 인터페이스가 존재함을 보이지만, 2018년 30개 계약의 실제 자료가 남아 있음을 증명하지 않는다: https://www.gate.com/docs/developers/apiv4/en/futures/

## 고정 게이트와의 대조

| 요구 | 확인 결과 | 판정 |
|---|---|---|
| 2018년 perpetual 시작 | 공식 연혁상 2018년 12월 | 2018년 완전연도 비교 불가 |
| 2018년 30개 이상 고정 코인 | 출시 직후 공식 FAQ는 BTC·USDT만 언급; 30개는 확인 안 됨 | 미충족 |
| 2022년 30개 이상 동일 코호트 | 월별 공식 파일 존재 목록을 확인하지 않음 | 확인 안 됨 |
| OHLC·mark·funding의 동시 커버리지 | 파일 종류는 문서화됨; symbol-month 실제 커버리지는 미확인 | 확인 안 됨 |
| 연구·보관 이용권 | 공개 다운로드 문서에서 명시적 데이터 재사용 라이선스를 확인하지 못함 | 확인 안 됨 |
| Binance USD-M 선물 R8/R9를 대체 | 다른 venue·계약 규격이며 데이터 cohort/체결도 미검증 | 대체 불가 |

## 다음 허용 단계

새 Gate 전용 실험으로 전환하기 전에, 공식 계약 목록/월 파일의 HEAD 또는 목록 메타데이터만으로 사전 고정할 30개 심볼의 2018·2022 월별 객체 존재를 확인한다. 이어서 전체연도 연속성, 출시·상폐 시점, OHLC·mark·funding 간 timestamp 정합, 이용 약관을 확인한다. 결과를 본 뒤 유니버스를 고르지 않는다. 확인 전에는 다운로드·변환·전략 시험을 시작하지 않는다.

이 보고서는 메타데이터 수준의 게이트 조사다. 가격 행을 읽거나 파일을 내려받지 않았고, 연구 장부를 수정하지 않았으며, 새 전략 성과를 주장하지 않는다.
