# 거래소 공식 과거자료 경로 교차 점검 — 2026-11-24

## 결론

조사한 Gate.io, Binance Futures, OKX 공식 자료만으로는 오더블록 전략에 필요한 동일 코인군의 2018·2022 연속 시세·호가 자료를 입증하지 못했다. 데이터 게이트를 열지 않았고, 다운로드·API 호출·장부 쓰기·백테스트를 하지 않았다.

## 공식 출처와 확인 범위

| 거래소 | 공식 자료에서 확인한 내용 | 연구 게이트 영향 |
|---|---|---|
| Gate.io | 2018년 12월 perpetual 출시, 2021년 안내의 futures candlestick/trade/mark/funding 월별 파일 형식. 별도 공식 화면의 OHLC 다운로드 시작은 2023년 1월, market depth는 2021년 8월로 표시됨. | 출시 월 자체는 2018년 완전연도 근거가 아니다. 2018·2022 동일 30심볼, 월별 객체 연속성, OHLC·mark·funding 정합, 이용권은 미확인. 기존 Gate 보고서 참조. |
| Binance Futures | 2020-06-01 공식 공지는 과거 선물 자료를 당시 YTD tick-level 거래자료로 제공하며 신청 절차를 안내함. Binance의 공식 블로그는 통합 자료에 선물 호가 스냅샷이 있다고 설명하지만, 호가 데이터는 whitelist된 futures account를 요구한다고 밝힘. | 2018 고정 코호트 증거가 아니다. 호가 자료 접근은 추가 계정 자격을 전제로 하므로 공개 무인증 자료로 간주할 수 없다. 요청·다운로드하지 않았다. |
| OKX | 공식 historical-data 페이지는 trade tick history 2021년 9월 이후, candlestick 2023년 7월 이후, funding 2022년 3월 이후, L2 order book 2023년 3월 이후를 표시함. | 오더북 자료는 2018·2022 게이트를 충족하지 않는다. 거래소별 상품·계약이 달라 Binance 코호트 자료의 대체로 취급하지 않는다. |

## 판정 기준 대조

- 2018년에 사전 고정한 코인 유니버스 30개 이상이 살아 있고 거래 가능했다는 시점별 증거가 필요하다.
- 같은 심볼 코호트에 대해 2018년과 2022년 전체 연도 커버리지, 상장·상폐·계약 변경, 시간대·캔들 연속성을 확인해야 한다.
- 오더블록의 체결 가능성을 주장하려면 OHLC만으로 충분하지 않다. 전략이 의존하는 호가 깊이·체결·비용 자료의 존재와 시점 정합도 검증해야 한다.
- 공개 경로, 사용 권한, 파일 목록·체크섬을 확인하기 전에는 원자료를 받거나 실험을 시작하지 않는다.

## 다음 단계

공식 무료 자료에서 2018/2022 동일 코호트와 필요한 오더북 깊이 자료가 확인되지 않으면, 이 연구에서 역사적 강건성 게이트는 계속 닫힌다. 계정 whitelist, API 키, 유료 접근, 또는 데이터 게이트 완화로 우회하지 않는다. 허용 가능한 공개 자료 경로가 새로 확인되면 먼저 심볼·월별 파일 인벤토리와 권리 조건만 검토하고, preregistration과 데이터 fingerprint를 확정한 뒤 실험 여부를 결정한다.

## 출처

- Binance, “Binance Futures Historical Data Now Available” (2020-06-01): https://www.binance.com/en/support/announcement/detail/360044357931
- Binance, “Backtest Your Trading Strategy With Binance Historical Data”: https://www.binance.com/en/blog/futures/421499824684901131
- OKX, “Historical Market Data”: https://www.okx.com/en-us/historical-data
- Gate.io 공식 출처와 개별 검증 범위: `REPORT_GATEIO_2018_DATA_GATE_20261124.md`

이 보고서는 공개 공식 문서에 적힌 기능·시작 시점 수준의 점검이다. 파일 객체 존재, 실제 시계열 완전성, 약관상 재사용 권한은 별도 검증 사항이며 현재 확인되지 않았다.
