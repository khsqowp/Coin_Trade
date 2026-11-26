# 워뇨띠 공개 기록의 포지션 상태 재구성 게이트

확인일: 2026-11-26 (Asia/Seoul)

## 판정

현재 보유한 공개 자료만으로 워뇨띠의 실제 보유 포지션 상태를 신뢰성 있게 재구성할 수 없다. 따라서 체결 흐름 신호를 포지션 복제 전략으로 바꾸는 추가 백테스트는 실행하지 않았다.

## 확인 근거

- 기존 체결 CSV의 필드에는 `side`, `lastqty`, `orderqty`, `leavesqty`, `cumqty`, `ordstatus`, `transacttime` 등이 있다. 기록된 체결의 방향·수량은 알 수 있지만, 해당 체결이 기존 포지션을 늘렸는지 줄였는지 또는 반전했는지 명시하는 신뢰 가능한 포지션 스냅샷은 확인되지 않았다.
- 기존 지갑 CSV의 헤더는 `currency`, `amount`, `transacttype`, `walletbalance` 등의 지갑 거래 필드다. 이는 잔고 이동 기록이며 포지션 수량·평단·미실현 손익의 시계열이 아니다.
- 계정의 최초 관측 시점 직전 보유량이 0이었다는 증거가 없다. 모든 체결 수량을 단순 누적해 포지션을 만들면 미관측 초기 포지션 오차가 전체 이후 신호에 전파될 수 있다.
- 이미 실행한 사전등록 시험 2건은 시간별 signed-flow를 예측변수로 사용했다. Binance 대리시장 OOS는 654건에서 비용 후 EV −9.199193bp, PF 0.786612, 방향 적중 50.76%였다. BitMEX 동일시장 OOS는 932건에서 EV −23.93bp, PF 0.312, 방향 적중 50.32%였다. 모두 탈락이며 워뇨띠 실제 매매 규칙이나 포지션 복제 결과가 아니다.

## 다음 단계 게이트

포지션 복제 연구를 재개하려면 최초 관측 시점의 포지션 스냅샷과 전체 체결 이력의 완전성을 입증하는 기록이 먼저 필요하다. 그 자료가 없으면 `cumulative signed fills`는 사실로 확인된 포지션이 아니라 가정 기반 대리변수이므로, 별도 사전등록·민감도 분석·명확한 탐색 라벨 없이 백테스트하지 않는다. 이미 공개한 시험구간을 새 후보의 미사용 OOS라고 부르지 않는다.

## 시장 데이터 경계

- Binance 공식 자료에 따르면 Binance Futures는 2019년 9월 출시됐고 최초 USDⓈ-M 무기한 계약은 BTCUSDT였다. 따라서 Binance USDⓈ-M으로 2018년 전략 성과를 구성할 수 없다. [Binance 공식 출시 안내](https://www.binance.com/en/support/announcement/detail/360033273472) [Binance 공식 회고](https://www.binance.com/en/blog/all/421499824684900979)
- KRX Open API 서비스 카탈로그는 주식 일별매매정보를 2010년 이후 제공한다고 밝힌다. 이 사실만으로 상장폐지 후 종결수익, 전체 시점별 유니버스, 개인의 비공개 반복 백테스트 이용권이 충족되는 것은 아니다. [KRX Open API 서비스 목록](https://openapi.krx.co.kr/contents/OPP/INFO/service/OPPINFO004.cmd)
- Nasdaq Data Link의 ZHDM은 1987년 이후 상장폐지 기업을 포함한 기업행위 자료지만 Premium이며, 가격 OHLC 자료가 아니다. [Nasdaq Data Link ZHDM](https://data.nasdaq.com/databases/ZHDM)

이 기록은 데이터 적격성 판단이며 새 전략의 성과 실험이 아니다. 새 데이터 다운로드, 가격 백테스트, 장부 변경, 실거래, 서버 변경은 하지 않았다. 작업 및 데이터 경로는 `/Users/user/CODE/Coin_Trade/`와 그 내부 `trading_data/`로 제한했다.
