# 사전등록 — Binance 대체 quote + Gate Spot 고정 코호트 메타데이터 합집합

상태: **로컬 메타데이터 열람 전 고정**
목적: 전략성과를 시험하지 않고, 기존 고정 CMC 2018 코호트에서 현재 기록된 Binance 다중 quote 결과와 기존 Gate 월별 객체 매트릭스를 자산별 단일 venue로 결합할 수 있는지 산술 대사한다.

## 고정 범위

- 코호트: `PREREG_BINANCE_SPOT_FIXED_QUOTE_FALLBACK_CMC201801_20261128.md`의 CMC 2018 상위 30 고정 목록. BTC benchmark를 제외한 29개 분모를 유지한다. 자산 추가·제거·alias 변경은 금지한다.
- Binance 입력: `REPORT_BINANCE_SPOT_FIXED_QUOTE_FALLBACK_CMC201801_20261128.md`에 기록된 20개 완전 pair만 쓴다. 해당 보고서에서 확인한 pair/asset 목록 외에 새 Binance endpoint나 파일을 조회하지 않는다.
- Gate 입력: 기존 `trading_data/external/crypto/gate/spot_ada_btc_4h_2018_2022_qa/CMC201801_TOP30_MONTH_MATRIX.csv`의 pair-string·연도·월·HTTP 상태 열만 읽는다. 가격·체결 행을 열지 않는다. Gate 보관·가공 권리는 미해결로 유지한다. 이 대사는 기존 로컬 메타데이터의 source upper-bound만 계산하며 Gate 데이터를 새로 취득하거나 전략 입력으로 승인하지 않는다.
- Gate identity: `REPORT_GATE_OFFICIAL_PAIR_IDENTITY_AUDIT_20261126.md`와 `REPORT_GATEIO_SPOT_2018_BACKTEST_SOURCE_LEAD_20261126.md`에서 명시적으로 모호·오매핑으로 판정된 자산은 매트릭스에 12/12가 있어도 Gate 완전 자산으로 세지 않는다. 새 pair 추정·quote 환산은 금지한다.

## 판정 규칙

1. Gate pair는 고정 CMC 자산과 identity가 명확히 일치하고 2018·2022 각각 12개 월 key가 모두 HTTP 200인 경우에만 complete로 센다.
2. Binance 자산은 고정 quote 사전등록 결과에서 확인된 `complete`만 complete로 센다.
3. 같은 자산이 두 venue 모두 complete여도 한 번만 센다. 두 해를 venue별로 나눠 잇거나 월별로 venue를 바꾸지 않는다.
4. 수치 `N_union`은 29개 고정 자산 중 단일 venue 하나가 두 해 모두 complete인 고유 자산 수다. 통과 문턱은 25/29로 고정한다. `N_union <25`이면 FAIL이며 어떤 가격 자료·전략 시험도 시작하지 않는다.
5. 이 수치는 월별 object-name metadata에 대한 상한이다. ZIP 무결성, 봉 연속성, PIT·상폐 처리, Gate 이용권, benchmark·비용·전략 수익을 통과했다고 해석하지 않는다. Gate 권리 미해결은 별도 차단 게이트로 유지한다.

## 금지 및 기록

- `TRAIN_TRIALS.csv` 접근·수정, 백테스트, 가격행·trade archive 열람, 새 네트워크 요청, 다운로드, 계정/API key 사용은 하지 않는다.
- 파서 코드는 `-B`로 메모리 내에서만 실행하고, 출력은 고정 자산별 Gate/Binance 판정 및 합집합 숫자뿐이다. 임시·캐시·로그 파일은 만들지 않는다.
- 모든 연구 실행에는 `TRADING_DATA_DIR=/Users/user/CODE/Coin_Trade/trading_data`를 전달한다.
- 이 검사는 전략 trial이 아니므로 전략 후보나 G 통과 수를 늘리지 않는다. 결과와 제외 사유는 별도 REPORT 파일에만 기록한다.
