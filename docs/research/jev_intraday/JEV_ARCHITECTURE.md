# Jev TypeSafe와 초단위 자동매매: 시스템 신뢰성 평가

**기준일:** 2026-10-16  
**범위:** 공식 TypeSafe 문서 조사, 로컬 Coin_Trade 브로커·시세 코드 및 제한된 NAS tick archive 점검, 주문 없는 paper benchmark 설계. 이 작업에서는 API 키/자격증명을 읽거나 실주문을 내지 않았다.

## 결론

Jev를 초단위 매매의 필수 인라인 의사결정 단계로 두는 것은 현재 근거로 정당화되지 않는다. TypeSafe가 문서화한 것은 JSON 단일 평가 요청과 구조화된 응답이지, 스트리밍 응답·지연 SLA·처리량 보장·주문 실행 보장이 아니다. 따라서 Jev는 충분히 빠르다는 측정 결과가 나와도 매수/매도 권한을 갖지 않고, 신호 후보의 분류/보조 점수 또는 비동기 리서치 경로에만 둬야 한다. 결정적 리스크 게이트가 데이터 신선도, 포지션, 주문 크기, 세션/장 상태, 손실 한도와 중복 방지를 검증하고, 검증 실패·타임아웃·모델 오류 시 신규 주문을 차단해야 한다.

## 확인된 Jev API 동작과 공개되지 않은 보장

| 항목 | 공식 문서에서 확인한 사실 | 이 평가에서의 의미 |
|---|---|---|
| HTTP 호출 | `POST https://api.typesafe.ai/v1/systemone`, Bearer 인증, JSON body. state와 질문 맵을 한 요청으로 보내고 질문 ID별 답을 받는다. | 요청-응답 방식의 동기 HTTP 경로다. 문서상 WebSocket/gRPC/SSE/token streaming 경로는 확인되지 않았다. |
| 답 형식 | `Choice`는 choice/probabilities/confidence, `Score`는 score/probabilities/confidence, `Noul`은 0~1 값. 응답에는 해석된 model id, answers, usage 예시가 있다. | 모델 결과는 구조화되어도 확률은 주문 승인이나 손실 한도의 대체물이 아니다. |
| 병렬 질문 | 같은 state에 대한 질문은 한 요청 안에서 병렬·독립 평가된다고 설명한다. | 필요한 독립 평가를 단일 요청으로 묶어 왕복을 줄일 수 있지만, 실제 지연 개선폭은 자체 측정 대상이다. |
| 모델 버전 | quick start의 `jev-latest` 요청 예제가 `jev-1.13.0` 응답을 보여준다. alias가 특정 버전으로 고정된다는 영구 보장은 문서에서 확인하지 못했다. | 임계값·결과 재현성이 중요하면 요청에 구체 버전을 지정하고 응답의 `model`을 기록/검증한다. 현재 사용 가능한 버전은 배포 시 `/v1/models` 및 콘솔로 다시 확인해야 한다. |
| 지연 | 초단위 매매용 p50/p95/p99, 최대 지연, 가용성 SLA가 공개 공식 문서에서 확인되지 않았다. “fast” 설명은 수치 SLA가 아니다. | 모델 단독 지연 추정치로 목표 달성 판정을 할 수 없다. 네트워크·큐잉·애플리케이션·브로커 승인/체결을 합친 end-to-end 측정이 필요하다. |
| 호출 제한 | 분당/초당 요청 제한 수치, 동시성 한도, 429 복구시간이 공식 문서에서 확인되지 않았다. | limit을 추측해 운영 설정에 넣지 않는다. 응답 헤더/status와 제한 응답을 paper 부하시험에서 관찰하고 공급자에 확인해야 한다. |
| 오류/재시도 | SDK 문서 인덱스에는 연결 오류, 타임아웃, rate-limit 예외, 재시도 정책 문서가 별도 존재한다. API 응답의 재시도가 주문과 원자적으로 묶인다는 보장은 없다. | 결정 요청 재시도는 가능해도 같은 market event에 대한 신호 중복을 허용하면 안 된다. 주문 재시도는 별도 idempotency/reconciliation 설계가 필요하다. |

공식 출처: [TypeSafe Introduction](https://docs.typesafe.ai/introduction), [Quick start](https://docs.typesafe.ai/introduction/quickstart), [API reference](https://docs.typesafe.ai/api), [Models](https://docs.typesafe.ai/models), [Python retries](https://docs.typesafe.ai/sdk/python/api/retries), [Python exceptions](https://docs.typesafe.ai/sdk/python/api/exceptions), [Python advanced usage](https://docs.typesafe.ai/sdk/python/usage/advanced). 문서 색인에서 API/model/retry 상세 페이지 링크를 확인했으나 이 조사 환경에서 일부 상세 페이지 본문은 열리지 않았다. 그러므로 제한값·상태코드별 재시도 의미를 확인한 것처럼 말하지 않는다. 위 지연 및 rate limit 항목은 “공식 문서에서 찾지 못함”이지 “공급자에 제한이 없음”이 아니다.

## 저장소 및 실제 데이터 경로 점검

작업 경로 `/Users/user/Desktop/CODE/trading_bot` 자체는 비어 있고 Git 저장소가 아니다. 관계가 확인되는 자매 저장소 `/Users/user/Desktop/CODE/Coin_Trade`를 읽기 전용으로 조사했다. 아래는 코드/주석으로 확인한 구현 상태이며 현재 프로세스가 실제 실행 중이라는 주장은 아니다.

### Crypto feed와 archive

`app/crypto_tick_stream.py` 구독은 Binance spot/perp `@trade`와 futures `@markPrice@1s`다. trade 이벤트의 exchange timestamp `T/E`, quantity `q`, maker-side flag `m`을 `_handle_*` 처리에서 보존하지 않고, 저장 시 `now_iso()` 수신시각과 price만 남긴다. futures mark-price 채널 역시 mark price 기록이지 order book depth가 아니다. L2 depth stream은 코드에 없다. 따라서 현 archive로는 과거 trade direction, volume delta, aggressor flow, 정확한 exchange-event-to-decision 지연, bid/ask imbalance를 복원할 수 없다.

NAS 경로 `/Volumes/HDD2TB/Trade/tick-archive`는 이 세션에서 직접 `du`와 제한된 `find`/샘플 읽기로 약 158GB임을 확인했다. 2026-09-01부터 10월 중순까지 crypto spot/perp 일별 JSONL은 각각 43개, `kr.jsonl`은 36개였고 `us.jsonl`은 0개였다. 2026-10-13 crypto perp 및 KR 파일의 제한 샘플 레코드는 `{"symbol", "ts", "price"}` 구조였다. 전체 158GB를 읽거나 줄 단위로 검증하지 않았다. 따라서 파일 수·용량·샘플 schema는 확인했지만 모든 날짜의 연속성, 종목 coverage, 누락률, 중복률은 검증하지 않았다.

가격만으로 가능한 대리 검증은 가격 변화 기반 이벤트 재생, 변동성/수익률 조건 신호, 과거 가격 기준 가상 체결, 지연 인위주입 민감도, 고정 가정 spread·수수료·슬리피지 스트레스다. 이것은 실제 orderflow나 호가 체결 가능성의 복원이 아니다. 재현 가능한 초단위 orderflow 실험에는 향후 L2 snapshot/delta와 sequence number, bid/ask price·size, 거래소 event timestamp 및 수신 monotonic timestamp, trade `q/m/T/E`, 연결/재구독 gap을 별도 수집해야 한다. 수집 전에는 volume-delta·imbalance 전략의 “역사적 검증”을 주장할 수 없다.

### KR/US feed coverage

`app/tick_stream.py`는 KIS 공개 체결가 WebSocket 구독 코드를 갖고 있으며 KR `H0STCNT0`, US `HDFSCNT0`를 처리한다. 구독 구현 여부는 과거 데이터 보유량·현재 연결상태·실제 종목 커버리지와 다르다. 위 NAS 관찰에서 `kr.jsonl` 36개이고 `us.jsonl` 0개다. 따라서 US는 코드 수준 지원은 있지만 이 archive에는 데이터가 없다. KR도 36개 파일 수는 전체 워치리스트·모든 거래일 연속 커버리지를 입증하지 않는다. tick stream은 체결 price 중심이며 L2 depth/size가 아니다. tick ingestion 자체를 매매 신호/주문과 잇는 완료된 초단위 파이프라인은 확인되지 않았다.

### Broker API

국내 주식은 `app/kis_order.py`에서 KIS 모의투자 REST 주문을 동기 호출한다. `app/kis_auth.py`는 요청 간 최소 1.05초 간격, 15초 기본 요청 timeout, 일부 rate-limit 코드 및 네트워크 예외에 재시도를 둔다. 이는 저지연 초단위 경로와 맞지 않으며 재시도 시 왕복 지연이 더 커질 수 있다. 해외주식 모의투자는 `app/kis_overseas_order.py`의 지정가 주문 및 ±1% marketable-limit buffer 주석을 갖는다. 이는 실체결 price/partial-fill의 모델이 아니다.

Crypto 실행 경로(`app/momentum_rotation_exec.py`)는 CCXT 동기 클라이언트, 15초 timeout, rate-limit 활성화, 계정/포지션 재조회, 시장가 실행 코드가 있다. 모드 전환에 mainnet도 있으나 이번 조사에서는 자격증명 접근 및 주문 실행이 없었다. 다른 곳에 실자금 전략이 있다는 README 경고가 있으므로 benchmark는 paper/mock endpoint 또는 로컬 fill simulator로 격리해야 한다.

기존 loop의 timeout wrapper는 별도 daemon thread가 계속 살아날 수 있다는 저장소 주석/기억된 장애 패턴이 있다. 실시간 파이프라인에서는 timeout 후 동일 종목 작업이 겹치지 않도록 단일 writer/actor, bounded queue, fencing epoch 또는 종료 가능한 process 경계를 사용해야 한다. 주문 제출 타임아웃은 “주문 실패”와 같지 않다. 접수됐지만 응답이 유실된 상태를 unknown으로 유지하고 주문조회/체결조회 후에만 재전송 여부를 결정한다.

## 권고 아키텍처

```text
Exchange WS (trade + L2; mark-price는 별도 feature)
    -> sequence/gap 검증·정규화·수신시각 기록
    -> bounded event queue -> deterministic features / candidate trigger
                               |                     |
                               |                     +-> Paper replay/fill simulator
                               +-> Jev async advisory (필요할 때만, pinned model)
                                         |
                         deterministic risk gate <--- typed result or timeout
                                         |
                      idempotent paper order adapter
                                         |
          ack / reject / partial fill / cancel / reconcile -> ledger
```

1. **Market data가 먼저다.** WebSocket은 체결과 사용 가능한 depth를 낮은 지연으로 공급한다. 각 메시지에 거래소 event time, 로컬 monotonic receive time, sequence, feed/source ID를 보존한다. gap, reconnect, out-of-order, stale quote 상태에서는 새 진입 금지다. mark-price feed를 trade/depth 신호로 취급하지 않는다.
2. **후보 신호와 의사결정 입력을 분리한다.** 매 tick마다 Jev를 호출하지 않는다. 결정적 feature trigger가 발생한 경우에만 최소 state(시점, 신선도, 가격/호가 요약, feature 값, 후보 방향)를 만들어 비동기 평가 요청을 보낸다. 시장 상태는 응답을 기다리는 동안 변하므로 결과에 입력 event ID와 최대 허용 age를 붙인다.
3. **Jev는 advisory로 둔다.** API 결과는 confidence/확률을 포함해도 모델 판정이다. 모델 호출 결과가 늦거나 형식/버전/label 검증에 실패하면 신규 진입 차단(no new risk), 기존 보호/취소·감축은 결정적 로컬 정책으로 처리한다. 모델이 주문 수량·가격·리스크 한도를 생성하거나 override하지 못하게 한다.
4. **독립적 결정론 리스크 게이트.** 주문 직전 stale-age, WS health, session status, allowed symbol/side, max notional/position/concentration, buying power, daily loss/drawdown, max open orders, price band/deviation, spread/depth, cooldown, kill switch, model version/decision age를 다시 검증한다. 모든 조건은 fail-closed 신규 진입 규칙으로 구현하고, 리스크 축소/취소는 별도 명시 정책으로 둔다.
5. **중복 방지 및 주문 상태기계.** `event_key = venue|symbol|channel|exchange_sequence_or_trade_id|strategy_version` 기반으로 신호를 중복 제거한다. 주문에는 결정적으로 생성된 client order ID를 넣고 DB unique constraint와 transactional outbox를 사용한다. 상태는 `created -> submitted -> acknowledged/unknown -> partially_filled -> filled/canceled/rejected`로 관리한다. timeout/연결끊김 후 같은 주문을 무조건 다시 POST하지 않고 broker order/exec 조회와 잔고 reconciliation을 먼저 한다. broker가 client ID 중복 거부/조회 기능을 제공하는지 대상 API별로 검증해야 하며 보장됐다고 가정하지 않는다.
6. **격리 및 감사.** Jev 호출 worker는 broker credential을 갖지 않는다. Paper adapter만 주문을 받으며 라이브 adapter와 credential/config를 분리한다. request/model/version, sanitized input hash, response, risk gate 결과, event timestamps, order state transition, fill model/fee assumptions를 append-only audit log에 기록한다. 상태 파일만을 체결 진실로 쓰지 않는다.

## 판정 및 도입 게이트

현재 답은 “Jev로 초단위 자동매매가 가능하다고 확인되지 않았다”다. 초단위 운영이 기술적으로 성립하려면 해당 시장/전략에서 정의한 deadline 내 p99 decision-to-paper-fill 충족, 데이터 신선도·연결 단절 fail-closed, 주문 중복 0건, reject/partial-fill 복구, fee/slippage 포함 기대값 양수 및 false-trigger 한도 충족이 함께 필요하다. Jev의 API 시간만 측정하거나 한 번의 성공 응답을 관찰하는 것은 이 기준을 통과시키지 않는다.

실험은 먼저 과거 price-only tick replay로 후보 신호/파이프라인을 검증하고, 실시간 paper/shadow에서는 거래소 WS와 broker paper API 또는 로컬 simulator를 연결한다. Jev-disabled 결정적 baseline과 Jev-enabled variant를 같은 이벤트에 비교한다. 안정적 p99/가용성/reject/체결 품질 기준을 여러 시장일·부하 구간에서 통과하기 전에는 Jev를 실주문 경로에 넣지 않는다. 과거 US 주식 archive가 없고 crypto event timestamp/orderflow 필드가 삭제된 점은 소급 검증의 명확한 한계다.

## 작업 산출물 및 검증 범위

- 이 보고서: `docs/research/jev_intraday/JEV_ARCHITECTURE.md`
- 실행 가능한 주문 없음 benchmark 계획: `docs/research/jev_intraday/benchmark_plan.json`
- 공식 근거는 위 TypeSafe 링크에 한정했다. 저장소 관찰은 Coin_Trade source 및 README에 기반한다. NAS 경로·대략 용량·파일 개수·일부 날짜의 샘플 schema는 이 턴의 OS 도구로 직접 확인했으나, 전체 archive의 연속성·누락/중복률은 스캔하지 않았다.
