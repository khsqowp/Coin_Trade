# Coin Metrics Community 시장 데이터 게이트 검토 — 2026-11-24

## 결론

Coin Metrics의 공개 Community API는 현재 코인 오더블록 G를 충족하는 2018·2022 시장 캔들 입력 경로로 승인할 수 없다. 공식 문서는 Community 무키 이용을 비상업 용도로 제한하고, 무료 시장 데이터에는 직전 24시간 체결만 명시한다. 역사적 시장 캔들 전 기간은 Pro 기관 데이터로 안내되며 가격·계약·개별 시장 커버리지는 공개 문서만으로 확인되지 않았다.

## 확인한 공식 문서

- Community Data 설명은 Network Data Pro와 Market Data Pro 중 일부를 Community API와 시각화 도구로 무료 제공한다고 적는다. 별도로 Reference Rates Community의 세밀한 주기 데이터는 최근 7개 관측치로 제한한다고 명시한다. 이 설명은 모든 Market Data Pro 이력을 무료로 푼다는 뜻이 아니다.
- API 접근 안내는 Community API에 키가 필요하지 않고, 무료 비상업 사용은 Creative Commons 조건이라고 명시한다. 반면 기관용 Pro 데이터는 API 키가 필요하며 구매 문의를 안내한다.
- Market Candles 문서는 OHLC·VWAP·거래량·거래 건수 필드와 1분~1일 주기를 설명한다. 값은 거래소 체결에서 계산하며 거래가 없는 구간을 이전 종가로 채우는 gapless 방식이다. 문서는 상폐 시장에서 candle fill-forward가 필요한 기간보다 오래 이어지는 알려진 문제도 적는다.
- 같은 Market Candles 문서의 접근 설명은 Community에서 직전 24시간 체결 데이터만 이용 가능하다고 하고, 전체 체결 데이터는 Pro API라고 구분한다. Community tier가 과거 2018·2022 캔들을 제공한다는 내용은 확인되지 않았다.
- 공식 문서의 거래소 표는 거래소별 시장 수와 일부 시작일을 보여준다. 그러나 2018년과 2022년 모두에 거래 가능한 30개 고정 자산, 시점별 상장·폐지 전체, 실제 무료 endpoint의 자산별 날짜 범위를 입증하지 않는다.

## 고정 G 적합성

| 요구 | 공개 문서의 증거 | 판정 |
|---|---|---|
| 무료 접근 | Community API에 키 불필요, 비상업 사용 | 접근은 가능하나 역사적 OHLC 권리·범위는 별도 미확인 |
| 2018·2022 캔들 | Community 무료 시장 데이터 설명은 직전 24시간 체결로 한정. 캔들 이력의 과거 범위 미기재 | 불충족/미입증 |
| 30개 이상의 고정 PIT 자산 | 공식 거래소 카탈로그는 시장 수와 일부 기간 설명을 제공하지만 연초 PIT 전체 목록을 무료로 확인하지 않음 | 미입증 |
| 거래 가능 체결가격 | 캔들은 원 거래소 체결에서 집계된 값이나 실제 Community 역사 캔들 접근 여부 미확인 | 미입증 |
| 상폐 종목 결과 | 캔들은 상폐 뒤 fill-forward 문제가 있음을 문서화 | 최종 청산·상폐 수익 입증 불가 |
| 구매 가능 범위 | Pro는 API 키·구매 문의 대상, 공개 요금·연구 이용권 미확인 | 사용자 비용 승인과 계약 확인 전 사용 불가 |

## 작업 경계

공식 Coin Metrics 문서만 열었다. 계정 생성, 문의 전송, 계약 수락, API 호출, 키 사용, 데이터 다운로드, 시장 행 열람, 실험·백테스트, 사전등록·공용 장부 변경은 하지 않았다. 이 보고서는 가격 파일의 실제 범위나 이용권 계약을 대신하지 않는다.

## 다음에 필요한 증거

1. 무료 Community endpoint에서 2018·2022의 시장 캔들을 받을 수 있다는 공식 문서 또는 약관 허용이 확인되어야 한다. 현재 문서에는 해당 근거가 없다.
2. Pro 접근을 검토할 경우 구매 전, 연구용 로컬 보관·파생 백테스트·결과 보존권, 전체 시장·상폐 커버리지, 2018/2022 시장별 기간, 총 비용을 서면으로 확인해야 한다.
3. 어떤 접근 경로든 전략 시도 전에 실제 30개 이상 고정 PIT 자산과 가격행 연속성·상폐 결말·비용 데이터가 별도 검증되어야 한다. 기존 G는 변경하지 않는다.

## 공식 출처

- [Coin Metrics Community Data](https://github.com/coinmetrics/product-docs/blob/master/docs/packages/coin-metrics-community-data.md)
- [Coin Metrics API 접근 및 무료/Pro 조건](https://github.com/coinmetrics/product-docs/blob/master/docs/access-our-data/api/README.md)
- [Coin Metrics Market Candles 정의·가용성·알려진 문제](https://github.com/coinmetrics/docs-website/blob/master/market-data/market-candles.md)
