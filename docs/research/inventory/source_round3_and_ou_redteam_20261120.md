# 외부 후보 재탐색 및 OU 저장소 레드팀 — 2026-11-20

## 판정 요약

**새로 사전등록할 외부 전략 후보는 0개다. `yoho369/crypto-perpetual-arbitrage`는 현재 코드와 성과를 채점 근거로 쓸 수 없다. 거래소 간 OU 평균회귀 메커니즘만 미검증 연구 가설로 남기며, Phase 9는 계속 차단한다.**

이번 기록은 두 작업을 구분한다.

1. 1분 BBO가 필요해 현 로컬 데이터로 시험할 수 없는 OU 저장소를 공개 소스 기준으로 적대 검토했다.
2. 현재 확보 자료(1시간 캔들·마크가격·펀딩)만으로 시험 가능한 새 외부 규칙을 SNS, TradingView/Pine, 커뮤니티, GitHub/논문에서 다시 찾았다.

외부 성과 주장은 독립 재현하지 않았으므로 결과로 인용하지 않았다. 외부 저장소를 내려받거나 실행하지 않았다.

### 로컬 데이터 적격성 확인

`/private/tmp/cointrade-50_50-data/manifest.jsonl`을 읽어 데이터 종류를 집계했다: `klines_1h` 2,610개, `funding` 2,610개, `mark_price_1h` 5,220개, 45개 심볼이며 manifest상 1분 BBO 파일은 0개다. 다음 보관 위치도 경로 단위로 확인했지만 현재 접근되지 않았다: `/Users/user/CODE/Ochestration/trading/trading-tick-archive`, `/Users/user/Desktop/CODE/Ochestration/trading/trading-tick-archive`, `/Volumes/HDD2TB/Trade/tick-archive`. `/Volumes/HDD2TB` 마운트도 확인되지 않았다. 이는 이 세 경로에서 자료를 찾지 못했다는 뜻이며, 다른 위치나 NAS 자체에 자료가 없다는 증거는 아니다. 따라서 OU의 1분 BBO 기반 검정은 현재 확인된 데이터로 불가하다.

## OU 후보 소스 감사

저장소 README는 거래소 간 funding-adjusted 가격 차이에 1,440분 AR(1)/OU 점수와 실행가능 EV 문턱을 적용한다고 설명하고 2026년 2개월 OOS 성과를 주장한다. 같은 README는 필요한 Parquet 데이터를 저장소에서 제외하고 외부 Google Drive에서 받도록 안내한다. 이 주장과 데이터는 이번 감사에서 재현·검증하지 않았다. [저장소 README](https://github.com/yoho369/crypto-perpetual-arbitrage)

### 코드에서 확인한 사항

| 항목 | 원문 코드 동작 | 판정과 한계 |
|---|---|---|
| 미래 참조 가능성 | `backtest_eng.py`는 1,440분 rolling spread median 뒤에 `bfill()`을 적용하고 해당 값으로 진입 EV를 걸러낸다. | 코드에 미래 방향 채움이 존재한다. 다만 실행 루프는 1,440번째 행부터 시작하므로 최초 점수에 실제 영향을 줬는지는 해당 창의 결측·갭에 달렸다. 발생 여부와 성과 영향은 데이터 없이 미확인이다. |
| funding 시점 표식 | 현재 funding epoch ID와 다음 행 ID를 비교해 경계 직전 행을 표시하고, 그 표식으로 포지션을 닫는다. | 다음 행을 참조하는 구현은 확인된다. 정산 직전 종료가 의도된 정책인지, 실제 정산 시각과 맞는지는 원자료·시간 의미 확인 전 단정하지 않는다. |
| funding 간격 추정 | `data_pipeline.py`는 현재 변경 이후 다음 funding-rate 변경까지 간격을 `shift(-1)`로 계산하고 결과를 뒤로 채운다. 그 간격은 funding-adjusted 가격에 사용된다. | 이후 변경을 사용한 interval 계산은 코드상 확인된다. point-in-time 가용성과 실제 adjusted spread 영향은 별도 데이터 재현 없이는 미확인이다. |
| stale 가격 | 파이프라인이 stale 플래그를 만든 뒤 BBO·index·mark 가격을 무기한 forward-fill한다. 백테스트는 별도 BBO를 최대 3분 forward-fill하고 stale 유효성 차단을 하지 않는다. | 오래된 값이 후속 입력 또는 체결 가격에 들어갈 수 있는 경로가 있다. 실제 사용 빈도·성과 영향은 미확인이다. |
| 무효 호가 청산 | 청산 호가가 유효하지 않을 때 직전 유효 호가를 쓰며, 쓸 수 있는 호가가 없으면 네 가격을 모두 `1.0`으로 대체하는 분기가 있다. | `1.0`은 실제 관측 체결 호가가 아니다. 그 분기가 결과 표본에서 실행됐는지는 미확인이다. |
| 종료 강제청산 | 마지막 유효 BBO를 사용한다. 해당 호가가 평가 종료 시각과 같다는 보장은 없다. | 종료 경계의 가격 왜곡 가능성이 코드상 남는다. 실제 발생·영향은 미확인이다. |
| 유동성 toll 의미 | rolling toll은 진입 EV 문턱에 쓰이고, 실현 PnL은 진입·청산 BBO로 계산한 손익에서 왕복 수수료를 뺀다. | toll을 실현손익에서 재차 빼지 않는 사실만으로 비용 누락이라고 단정하지 않는다. 보수 필터인지 추가 비용 추정치인지 정의·단위를 명확히 해야 한다. 체결 BBO 손익과 EV 기준의 일관성은 독립 검증이 필요하다. |

원문: [backtest_eng.py](https://raw.githubusercontent.com/yoho369/crypto-perpetual-arbitrage/main/src/backtest_eng.py), [data_pipeline.py](https://raw.githubusercontent.com/yoho369/crypto-perpetual-arbitrage/main/src/data_pipeline.py), [statistical_eng.py](https://raw.githubusercontent.com/yoho369/crypto-perpetual-arbitrage/main/src/statistical_eng.py). 라이선스는 저장소에서 MIT로 표시되어 있으나, 이는 외부 Google Drive 데이터의 이용 권리를 증명하지 않는다. [라이선스](https://github.com/yoho369/crypto-perpetual-arbitrage/blob/main/LICENSE)

## 4인 레드팀·블루팀·Methods·Judge 토론

두 차례 독립 의견 수집과 상호 반론을 거쳤다. 네 역할의 최종 공통 판정은 다음과 같다.

- **Blue:** 거래소 간 가격 차이의 평균회귀 및 funding 정규화는 가설로 연구할 수 있다. 이는 수익성이나 현재 구현의 승인이 아니다.
- **Red:** 현재 코드 경로는 미래 참조, stale/무효 호가, funding 시점과 종료 가격 처리의 검증 공백을 가진다. 현재 저장소 산출물은 frozen core gate 통과 증거로 인정하지 않는다.
- **Methods:** 현재 로컬 자료는 시간 단위다. 동기화된 1분 BBO가 없어 이 전략의 스프레드, 체결, stale 호가, 지연, funding 시점 검증을 할 수 없다. 시간봉 대체는 같은 가설 시험이 아니다.
- **Judge:** 저장소 구현은 성과 검증용으로 부적격. OU는 메커니즘 전용 리드, liquidation echo는 설명·기술통계 전용으로 남긴다. 둘 다 전략 점수화·사전등록 후보가 아니며 Phase 9는 차단한다.

`liquidity_toll`의 실현손익 차감 여부는 비용누락으로 단정하지 않는다는 점, `bfill()`의 실제 채점 영향은 초기 평가 창 결측 여부를 확인해야 한다는 점, stale·무효 호가 경로의 표본 발생 여부와 실제 metric 영향은 미확인이라는 점을 최종 판정에 반영했다.

## 한 시간 자료에 맞춘 4출처군 재탐색

각 조사자는 기존 [연구 레지스트리](../registry.jsonl)와 대조하고, 진입·목표·무효화·만기까지 재현 가능하며 1시간 자료로 시험할 수 있는 신규 후보만 제출하도록 했다. 후보가 없으면 억지로 규칙을 만들지 않도록 했다.

| 출처군 | 조사 결과 | 후보가 되지 않은 이유 |
|---|---|---|
| SNS | 신규 적격 후보 0개. “조용한 구간 뒤 20봉 고점 돌파”는 기존 압축·돌파군과 겹침. 뉴욕장 시간대 매수, funding 숏 등은 방향·손절·목표·만기 또는 임계값이 미완성. | 기존 중복 또는 룰 불완전. 게시물의 성과 주장은 독립 근거가 아님. [예시 글](https://www.reddit.com/r/algotradingcrypto/comments/1x8ykz1/trying_to_break_my_robustness_filter/) |
| TradingView/Pine | 신규 적격 후보 0개. Market Regime Engine은 ATR 군집·ER·EMA 편향을 제시하나 진입·목표·무효화·만기를 완성하지 않으며 핵심은 레지스트리 항목 109와 중복. OI/집계 거래량 지표는 입력 해상도·데이터 조건 부적합. | 공개 지표 설명만으로 실행 규칙을 만들면 별도 신규 설계가 됨. 실제 Pine 코드 검토가 되지 않은 항목은 수식·인과성 확인으로 간주하지 않음. [Market Regime Engine](https://www.tradingview.com/script/MIEZDvM9-Market-Regime-Engine/), [Crypto Money Flow Tracker](https://www.tradingview.com/script/npr5WIMA-Crypto-Money-Flow-Tracker/), [Aggregated Volume Spot & Futures](https://www.tradingview.com/script/T6dlVzTV-Aggregated-Volume-Spot-Futures/) |
| 공개 커뮤니티 | 신규 적격 후보 0개. 변동성 압축 돌파와 funding fade는 기존 연구군과 중복. 여러 ATR·거래량·몸통 조건 조합은 합성 점수와 진입·청산 규칙이 공개되지 않음. | 중복 또는 코드화 불가. [예시 글](https://www.reddit.com/r/algotradingcrypto/comments/1x1ufcb/update_on_crypto_bot_shifted_from_15m_noise_to/) |
| GitHub/스킬/논문 | 신규 적격 후보 0개. Funding-rate arbitrage는 기존 funding-tail과 겹침. spot-perp carry는 로컬 현물가격 입력 부재 또는 M2 target-first 규칙 미완성. 교차거래소 OU는 1분 BBO가 필요. | 중복, 데이터 부적합 또는 완결된 target-first 규칙 부재. 프레임워크/스킬은 전략으로 세지 않음. 예: [funding-rate-arbitrage](https://github.com/santzmr/funding-rate-arbitrage), [binance-futures-backtest](https://github.com/Gotodataru/binance-futures-backtest), [spot-perp relative value](https://github.com/haa7717/crypto-funding-basis-relative-value). |

**결과:** 새 사전등록 후보 0개, 신규 성과시험 0회, 새 수익률 수치 0개. 이는 전략군 전체가 실패했다는 뜻이 아니라, 이번 공개 출처 조사에서 기존 자료와 구별되고 고정 데이터·M2 평가에 바로 넣을 자격이 있는 규칙을 찾지 못했다는 뜻이다.

## 다음 연구 순서

| 순서 | 실행 | 완료/중단 기준 |
|---|---|---|
| 1 | OU용 동기화 1분 BBO·funding 원자료가 현재 접근 가능한 로컬/NAS 아카이브에 있는지, 파일 manifest·해상도·기간·심볼·출처만 읽어 확인한다. | **완료 — 현재 확인한 manifest에 BBO 0개.** 지정한 tick archive 세 경로가 없거나 접근되지 않고 NAS 마운트도 확인되지 않았다. 이는 경로 한정 확인이며 전체 디스크 부재를 뜻하지 않는다. OU 점수화는 자료 확인 전 중단. |
| 2 | 별도로, 1시간 전략 발굴을 이어갈 때는 새 가설의 구조적 차이·코드화 완전성·기존 등록 중복을 먼저 독립 심사한다. | **이번 4출처군 라운드 완료 — 적격 후보 0개.** 완전한 진입·목표·무효화·만기 또는 사전등록 가능한 고유 가설이 없으면 백테스트하지 않는다. |
| 3 | 1분 원자료가 확보될 때만 OU 구현을 독립적으로 재현하고, 미래 참조·funding 경계·stale/invalid/terminal 호가·비용 정의를 수정 또는 격리한 뒤 prefix/future-mutation 및 synthetic edge-case 테스트를 수행한다. | 모든 인과성·호가 유효성·원장 대조 테스트 통과 전 성과를 계산하지 않는다. 외부 코드를 그대로 채택하지 않는다. |
| 4 | 데이터와 구현 게이트 통과 뒤에만 사전등록된 비중첩 독립 OOS 평가를 수행한다. | M2 목표 선도달률 ≥80%, 전체 신호 및 비중복 N≥200, 커버리지 ≥10%, 20개 이상 심볼, 비용·슬리피지·funding 후 순기대값 양수, 독립 OOS와 강건성 조건을 모두 충족해야 한다. |
| 5 | Core가 위 조건을 모두 통과한 경우에만 레드팀 재심 후 Phase 9 결합 평가를 연다. | 미달이면 Core 미승인, Phase 9 미진입으로 기록한다. |

### 현재 결론과 남은 작업

- **검증된 Core:** 없음.
- **외부 신규 적격 전략:** 이번 4출처군 재탐색 기준 0개.
- **OU 저장소:** 현재 구현·성과는 증거에서 제외. OU 메커니즘은 데이터 확보 시 검토할 가설로만 보존.
- **liquidation echo:** 방향·수익 전략이 아니라 기술적 활동 관측으로 제한.
- **Phase 9:** 차단.
- **다음 즉시 작업:** 실험이 아니라 1분 BBO/funding 데이터의 위치·출처·해상도·보존 상태를 읽기 전용으로 확인한다. 데이터가 없으면 이를 명시하고, 기존 자료에 맞는 독립적인 신규 가설 발굴을 계속한다.

