# Jev(TypeSafe System One) 보조 초단위 주식매매 가능성 조사

- 조사일: 2026-10-16
- 대상: `/Users/user/Desktop/CODE/Ochestration/trading` 코드·로컬 산출물, 연결된 `Coin_Trade` tick 수집 코드, 사용자가 제시한 NAS archive. 외부 현재 사실은 거래소·규제기관·브로커·TypeSafe 공식 1차 출처에 한정했다.
- 목적/경계: US/KR 주식의 초단위 paper 실험 가능성과 필요한 추가 데이터를 판정한다. 본 문서는 전략의 수익성 주장이나 실거래 허가가 아니다. 주문·자격증명 사용은 없었다.

## 결론

기술적으로는 두 시장 모두 KIS WebSocket 시세를 받아 로컬 paper 엔진에서 초단위 의사결정 흐름을 검증할 수 있다. 그러나 현재 Ochestration의 주식 가격 데이터는 일봉뿐이며 NAS archive에는 미국 주식 레코드가 없고, 한국주식·코인 tick도 가격만 보존되어 있다. 따라서 지금 즉시 가능한 것은 파이프라인/운영 모의와 제한된 price-only tick 연구이고, 진정한 과거 초단위 신호·체결·호가 replay는 불가능하다. Jev의 서비스 latency SLA 또는 공식 수치도 확인되지 않아 Jev 단독 latency 숫자로 초단위 적합성을 단정해서는 안 된다.

권고는 (1) 기존 paper 계좌/API를 사용한 무주문 shadow 수집, (2) tick 원본과 event time을 보존하고 로컬 상태 판단과 Jev 호출을 분리, (3) 충분한 기간·시장국면을 모은 뒤 동기화된 paper fill simulator에서 평가하는 것이다. 실시간 주문은 조사 범위 밖이며 진행하지 않았다.

## 1. 조사 근거와 저장소 상태

### 저장소/구현 확인

- Ochestration HEAD: `e3222c82216453f1b5b0f22748f9c7849b2045ff` (`2026-10-16`, `Add US and KR equity strategy transfer research`). 조사 당시 dirty 상태: `app/momentum_rotation_loop.py` 수정, `app/crypto_tick_state.py` 및 `app/crypto_tick_stream.py` 삭제 표시, `.rs_cache/`와 `agent_sandbox/` 미추적. 해당 변경은 건드리지 않았다.
- README는 국내 64종목·미국 55종목 KIS swing을 paper로 분류한다. 기존 루프는 분봉·틱 전략 검증물이 아니며, `agent_sandbox`는 코인 선물 테스트넷 harness로 equities paper broker가 아니다.
- Ochestration `docs/research/equity_transfer_2026-10/DATA_AVAILABILITY.md`는 2026-10-14 현재 `.kis-cache`의 일봉 118 파일(US 54, KR 64), 249,592행, intraday timestamp 0개를 기록한다. 데이터 범위는 US 2018-01-02–2026-10-12, KR 2018-01-02–2026-10-02. 이 문서의 inventory 결과를 이번에 재수집하지는 않았으며, 현재 repo의 기록된 확인값으로 인용한다.
- 해당 연구 어댑터는 `b4`(4시간 자료)가 비어 있고 비일봉 timeframe을 거절한다. 기존 equity transfer 결과는 모두 분봉·초봉 체결 성과로 해석하면 안 된다.
- 연결된 `Coin_Trade/app/tick_stream.py`는 KIS 공개체결 KR(`H0STCNT0`)·US(`HDFSCNT0`) 구독을 구현한다. 코드 주석상 모의투자 전용 WebSocket 호스트를 사용하고 구독 후보를 동적으로 만든다. 이 사실은 코드가 구독을 시도할 수 있음을 뜻할 뿐, 각 종목이 구독 승인되거나 아카이브/계좌에서 실제 데이터가 지속 확보됨을 입증하지 않는다.
- `Coin_Trade/app/crypto_tick_stream.py`는 Binance spot/perpetual `@trade`, futures `@markPrice@1s`를 구독한다. handler는 거래 이벤트의 exchange timestamp(`T`/`E`), 수량 `q`, maker-side `m`를 저장하지 않고 `now_iso()` 수신 시각과 가격만 남긴다. L2 depth 구독은 없다. 코드 주석도 수집·저장만 수행하고 tick signal을 봇의 진입/청산 판단에 연결하지 않았다고 명시한다.

### NAS tick archive: 제한된 점검

전체 파일 내용은 읽지 않았다. 경로 이름의 `find`, 전체 용량 `du -sh`, 날짜별 파일 개수, KR·crypto 파일 각 3줄 샘플만 확인했다.

| 파일 종류 | 확인된 파일 수 | 확인 내용 |
|---|---:|---|
| `crypto_spot.jsonl` | 43 | 2026-09-01 이후 샘플은 `symbol`, `ts`, `price` |
| `crypto_perp.jsonl` | 43 | Binance trade 스트림에서 온 archive category. 원천 exchange timestamp·trade qty·maker flag 미보존 |
| `kr.jsonl` | 36 | 2026-09-01–2026-10-16. 샘플은 `symbol`, `ts`, `price` |
| `us.jsonl` | 0 | 미국주식 tick archive 파일 없음 |
| archive 전체 | — | `du -sh` 출력 158G |

KR 파일 개수는 정확한 basename `kr.jsonl`로 세었다. 넓은 `*kr.jsonl` 패턴은 `crypto_perp.jsonl`까지 세어 과대계수하는 오류가 있어 폐기했다. 샘플은 필드 존재를 확인한 제한 표본이지, 158GB 전체의 schema/연속성/중복률/coverage 검사가 아니다. 파일별 레코드 수·종목 수·결측구간·정렬 상태를 전수 검사했다고 주장하지 않는다.

결론적으로 현재 archive로 계산 가능한 것은 가격 변화·가격 수익률·수신 timestamp 기반의 coarse event-count/price-momentum·가격 변동성 proxy다. 초 단위 수익 재구성은 timestamp가 원천 이벤트 시간이 아니라 collector 수신시각이고, NAS 저장/flush도 원본 거래 이벤트 전체를 보존했다는 증거가 없어 오차가 있다. 체결량 imbalance, signed volume delta, aggressor flow, bid/ask depth imbalance, queue position, spread crossing·market impact는 필드가 없어 재구성할 수 없다. 암호화폐에서도 이 제약은 동일하며 L2 및 원천 event metadata 수집이 추가로 필요하다.

## 2. 시장 세션과 현실적 실험 창

### 미국 주식

NYSE core는 미국 동부시간 09:30–16:00이며 조기/연장 세션은 거래소·종목·브로커별로 다르다. NYSE 공식 시간표를 기준으로 하되, 초단위 실험의 첫 범위는 정규장만으로 고정하고 정규장 개장·종가 경매 구간은 별도 표기한다. [NYSE 공식 Trading Information](https://www.nyse.com/trade/trading-information)

서울 시간 환산은 미국 DST에 따라 달라진다. EST(UTC−5)면 한국 23:30–다음날 06:00, EDT(UTC−4)면 한국 22:30–다음날 05:00이다. 휴장·조기폐장 캘린더와 DST는 매 거래일 확인해야 한다. 시장 session key는 거래소 현지 날짜/타임존으로 계산하고 KST 기록과 UTC 이벤트 시간을 함께 보존한다.

### 한국 주식

KRX 정규 연속매매는 09:00–15:30 KST다. 시가/종가 단일가, 시간외 시장, NXT 별도 세션/라우팅은 정규 KRX 연속매매와 혼합하지 않는다. KRX가 공개한 정규·시간외 거래시간표를 사용한다. [KRX 공식 한국 주식시장 거래 안내](https://global.krx.co.kr/contents/GLB/01/0109/0109000000/guide_to_trading_in_the_korean_stock_market.pdf), [KRX Trading Hours](https://global.krx.co.kr/contents/GLB/06/0602/0602010201/GLB0602010201T1.jsp)

한국 낮 장과 미국 야간 장은 별도 worker/session으로 운영해야 한다. 한 세션의 마지막 가격/포지션을 다른 세션의 stale state로 평가하지 말고, 각 시장의 공휴일·서머타임·조기종료를 독립 처리한다.

## 3. 브로커/API 및 feed 현실성

### KIS: paper 계좌와 시세 API

KIS Developers 공식 카탈로그에는 국내 현금주문/계좌, 국내 당일·일별 분봉, 당일 시간대별 체결 및 국내 실시간 체결·호가 WebSocket endpoint가 열거되어 있다. 해외주식 주문·계좌, 해외 분봉, 현재 체결/호가와 실시간 시세 항목도 있다. 다만 해외 실시간 체결 항목의 공식 명칭은 `해외주식 실시간지연체결가`이며, 제목만으로 무지연 feed라고 해석하면 안 된다. 구독 가능 상품, 지연 여부, 모의 계정 지원, 구독 수 제한, 과거 조회 범위는 API별 문서 및 계정/실측 확인이 필요하다. [KIS Developers API 카탈로그](https://apiportal.koreainvestment.com/apiservice)

KIS API 포털은 REST/WebSocket 및 API 항목이 존재한다는 점을 증명한다. 연구 시점의 코드에서 공개 KR/US 체결 구독 경로가 있더라도, 이는 US/KR 양 시장에 “paper+실시간+과거 replay”가 모두 갖춰졌다는 증거가 아니다. 특히 미국주는 현재 NAS archive가 0 파일이므로 현재 로컬 historical tick replay 불가다. KIS REST 분봉 endpoint가 보여도 일별 호출 제한·당일/최근 N일 보유 제한 등 개별 문서 조건을 확인하기 전에는 장기 분봉 데이터 존재로 간주하지 않는다.

KIS API 호출률/동시 WebSocket 구독 상한은 이번 조사에서 공개 포털의 개별 endpoint 규격을 전부 계정 조건별로 확정하지 못했다. `Coin_Trade/app/tick_stream.py` 주석도 공식 세션당 상한을 모른다고 밝히고, 전체 워치리스트 구독을 시도하면 한도초과 시 중단하도록 되어 있다. 따라서 초기에는 소수 종목 구독으로 ACK·재접속·유실률을 실측하고, 운영 전에 KIS 현행 제한을 문서/문의로 확인해야 한다.

모의 주문계정은 주문경로·잔고/체결 통보·order state machine 검증에 유용하지만, simulation fill은 실거래 queue priority, latency, borrow availability, market impact를 보증하지 않는다. paper에서 접수/체결 성공만 확인해 실전 성능으로 외삽하면 안 된다. 보고서 조사 중 계정이나 키로 모의 endpoint를 호출하지 않았다.

### Jev (TypeSafe System One)

TypeSafe 공식 API는 HTTPS `POST https://api.typesafe.ai/v1/systemone`의 state + typed questions 요청과 완성된 typed `answers` 응답을 정의한다. 응답에는 사용량의 input/output token이 포함된다. API reference는 스트리밍 토큰 출력이나 latency 보장/SLA/수치형 rate limit을 문서화하지 않고, 429(한도초과)와 529(일시 과부하)를 정의하며 SDK의 exponential backoff 재시도를 권고한다. [TypeSafe API reference](https://docs.typesafe.ai/api)

따라서 호출 소요시간은 실측해야 한다. RTT, 서버 처리, 네트워크/지역, request state 크기, typed questions 수, 동시성, 재시도, 429/529를 분리 측정한다. 시장 tick 수신부터 action 생성까지 종단시간을 따로 잰다. Jev의 단일 호출 평균/중앙값만으로 p95/p99 deadline 적합성이나 특정 초단위 전략의 수익성을 입증할 수 없다.

Jev는 완성된 상태를 평가하는 decision service로 배치하고, 매 tick마다 호출하지 않는다. 이를테면 로컬 규칙이 후보 이벤트를 감지한 경우에만 compact snapshot을 묶어 호출하고, 답변이 deadline 이후 도착하면 폐기한다. Jev는 주문 API/리스크 엔진이 아니므로 결과를 직접 주문으로 변환하지 말고, 로컬 deterministic gate에서 세션·시세 age·보유/주문 중복·가격단위·현금/수량·손실한도·paper mode를 다시 검증한다. 온전한 응답 전까지 동작을 추정하거나 부분 답변을 실행하지 않는다.

## 4. 공매도, 수수료, 호가단위

### 미국

- SEC Regulation SHO는 short-sale marking, locate, close-out 요구를 포함한다. Rule 201은 전일 정규장 종가 대비 당일 10% 이상 하락한 covered security에 대해 당일 잔여시간과 다음 거래일에 가격 테스트 제한을 적용한다. 이는 과거의 단순 uptick/last-sale tick test와 동일한 규칙이 아니다. [SEC Regulation SHO FAQ](https://www.sec.gov/rules-regulations/staff-guidance/trading-markets-frequently-asked-questions-8), [SEC Rule 201 FAQ](https://www.sec.gov/rules-regulations/staff-guidance/trading-markets-frequently-asked-questions-7)
- 개인 paper 환경에서는 종목 borrow 가능 여부, locate fee, hard-to-borrow 비용, broker short-sale restriction/주문 거부를 정확히 복원하기 어렵다. 시작 실험은 long-only로 분리하고, short 결과는 borrow availability/fee/recall/SSR를 명시적으로 모사하지 않는 한 별도 비현실적 참고치로만 취급한다.
- US 주식 최소 호가단위를 모든 종목에 고정 1센트로 하드코딩하지 않는다. SEC Rule 612 개정은 가격 $1 이상 종목 중 일부에 0.005달러 increment를 설정하지만, SEC는 관련 이행 일정을 2026년 11월 첫 영업일까지 유예한다고 2026-06-11 기준 발표했다. 연구일 현재 유효 호가단위는 종목별로 거래소/브로커의 현행 tick assignment 확인이 필요하다. [SEC Tick Sizes Guide](https://www.sec.gov/resources-small-businesses/small-business-compliance-guides/tick-sizes), [SEC 2026-06-11 statement](https://www.sec.gov/newsroom/speeches-statements/atkins-statement-minimum-pricing-increments-access-fee-caps-061126)
- KIS commission, 환전 spread, SEC/FINRA pass-through, short borrow 및 기타 수수료는 계좌 유형·프로모션·종목/주문에 따라 달라질 수 있다. 고정된 ‘현재 미국 수수료’를 단정하지 말고 계좌 약정표와 실제 paper 주문내역을 기준으로 round-trip cost를 설정한다. 기존 연구의 KIS 0.36% 편도 및 저비용 0.08%는 과거 연구의 비용 시나리오이지 현재 확정요율이 아니다.

### 한국

- KRX는 원칙상 무차입 공매도를 금지하며, 차입이 확보된 covered short만 예외적으로 허용한다. 공매도 호가에는 업틱 규칙과 주문표시/회원사 검증이 적용된다. 따라서 일반 현금 paper 계좌에서 자유롭게 가능한 매도처럼 시뮬레이션하면 안 된다. [KRX 공식 공매도 규정 설명](https://global.krx.co.kr/contents/GLB/06/0602/0602010204/GLB0602010204T5.jsp)
- KR 표준주식 tick size(가격 구간별 1/5/10/50/100/500/1000원)는 상장상품·시장 제도에 따라 예외가 있을 수 있어 instrument master로 검증한다. [KRX 공식 호가단위](https://global.krx.co.kr/contents/GLB/06/0602/0602010201/GLB0602010201T3.jsp)
- KIS 수수료는 계좌별 적용표를 확인한다. 국내 매도 거래세/농특세 등은 시장·상품·시점에 따라 달라질 수 있다. 기존 Ochestration 연구의 수수료 0.015%, 매도세 0.18%, 대차 연 3%는 그 시나리오 가정이지 지금 모든 계좌/시장에 적용되는 현행 보장요율이 아니다. 최신 법정세율·계좌 요율을 확인해 실험 전에 별도 cost config로 고정한다. KRX의 해당 날짜 공식 시장 요율표를 이번 조사에서 충분히 확인하지 못했으므로 현행 세율 숫자는 여기서 단정하지 않는다.
- 한국 대차 종목·담보·수수료·대주 가능 여부는 계좌와 종목에 의존한다. paper fill이 short borrow를 모사하지 않으면 KR short 실험은 전략 논리가 아니라 실행 가능성 가정의 테스트다.

## 5. 데이터 분류: 실제 초/틱 vs 분봉 proxy

| 범주 | 지금 로컬에서 확인된 상태 | 할 수 있는 검증 | 못 하는 주장/추가 필요 |
|---|---|---|---|
| US 주식 tick | NAS `us.jsonl` 0개 | 코드 구독 구현 검토, API 연결 가능 시 실시간 shadow 수집 | 과거 trade/quote replay·초단위 백테스트 불가. 구독 및 지연 특성 확인 후 historical feed 필요 |
| KR 주식 tick | 36일 파일, 가격-only 샘플 | 저장된 timestamp/price 기반 price-change/event-density proxy, stream 적재 검증 | 원본 거래량·매수/매도 체결 flag·호가 미보존. 정확한 signed flow/queue/fill replay 불가 |
| Crypto spot/perp ticks | 각 43일 파일, price-only archive | 가격 움직임·가격 기반 trigger의 coarse replay, 시장별 단순 비교 | trade qty/maker flag/event time 누락. signed volume delta·trade imbalance 불가. 과거 L2 데이터 없음 |
| KIS 분봉 API | API 카탈로그에 KR/US minute bars listed | 계정과 endpoint 접근 확보 후 제한된 기간의 분봉 baseline/paper integration | 장기 과거 깊이·모의환경 제공·분봉의 완전성은 endpoint별 확인 필요. 1분봉은 초 경로를 복원하지 못함 |
| 로컬 KIS equity cache | 문서화된 US 54/KR 64 종목 일봉, intraday timestamp 0 | 비용/세션 가정을 둔 일봉 실험, 범용 코드·위험 gate 단위시험 | 분봉·틱·세션 미시구조 기반 결과 아님 |

분봉은 분 내 high/low/close 집계일 뿐 각 체결의 도착 순서와 호가 잔량을 제공하지 않는다. 한 분 안에서 stop/target 양쪽을 모두 건드린 경우 우선순위를 데이터만으로 정할 수 없으며, 종가만 쓰면 trigger timing/가격 개선을 검증하지 못한다. 분봉에서 더 촘촘한 타임스탬프를 만들어 초봉으로 쪼개는 것은 관측이 아니라 synthetic path 가정이므로 본 연구에서는 금지한다.

## 6. Jev 초단위 의사결정 아키텍처

1. **세션별 market-data collector:** US와 KR timezone/calendar worker 분리. WebSocket 원문 또는 충분한 canonical event를 append-only 보관: source event time, local receive monotonic+UTC time, venue, symbol, trade/quote type, price, size, aggressor/maker indicator, bid/ask levels, sequence/update ID, feed delay. 원문을 보존하고 파싱된 schema version도 기록한다.
2. **정합성/신선도 계층:** reconnect, heartbeat, sequence gap, duplicate, out-of-order, crossed/stale quote 감지. 데이터 age가 기준을 넘으면 신규 action 차단. 실행 가능한 feed coverage를 실제 ACK·수신률로 관리한다.
3. **초단위 로컬 feature:** event-time 기준으로 1s/5s/1m 집계. 가용할 때만 spread, depth imbalance, signed volume delta, realized volatility, trade intensity를 계산한다. 지금 archive에서 만들 수 있는 값은 price-only proxy라고 명명한다.
4. **Jev 호출 분리:** 로컬 규칙이 후보를 좁힌 뒤 snapshot 단위로 typed Choice/Score/Noul 질문을 한 번 호출한다. decision service는 완성 응답 형태이므로 매 tick synchronous blocking을 금지한다. 응답 수신/입력 크기/모델 id/질문 schema/usage/429·529/재시도/latency를 기록한다. 키와 민감계정정보를 state에 넣지 않는다.
5. **로컬 risk/order gate:** Jev 응답은 의견 입력일 뿐 주문 권한이 아니다. 시장 열림·시세 age·한도·가격 tick·거래 가능 수량/현금·short borrow·Rule 201/업틱 필터·중복 주문·기존 미체결·계정 상태를 로컬에서 재검증한다. 해당 gate에서 거부되면 paper 주문도 발행하지 않는다.
6. **paper execution simulator와 broker paper 분리:** 첫 단계는 자체 simulator(quote-side crossing, conservative latency/slippage, partial/no-fill, rejected order, queue loss, halt, timeout). 다음 단계에 한정된 paper account/API 연동. broker paper acceptance/fill과 synthetic replay 결과를 합산하지 않고 각각 보관한다.
7. **킬스위치/재시작 복구:** 단일 writer 또는 durable queue, idempotency key, unresolved order reconciliation, circuit breaker, 일일 손실/노출 한도, 운영자 중지 절차. API timeout 뒤 주문 상태 미확인 시 재주문 금지.

Jev가 매초 한 번 호출되면 초당 60회/분(심볼 수가 늘면 그 배수)의 호출 예산이 필요하지만, TypeSafe 공개 문서에서 현재 수치형 quota를 찾지 못했다. 매 초마다 모델 호출하는 구조는 quota/latency/비용·변동성을 확인하기 전 설계 기준에서 제외한다. 로컬 feature 계산과 hard risk gate는 tick/event-driven으로 하고, Jev는 필요시 비동기 snapshot decision으로 둔다. 시장 급변·통신 지연·429/529가 발생했을 때 안전 기본동작은 `no new order`다.

## 7. 로컬에서 할 수 있는 일과 추가 전제

### 로컬만으로 가능

- 지금: repository/code audit, state machine/strategy/risk gate 단위·속성 테스트, 세션/DST fixture, event-time vs receive-time timestamp schema 테스트, stale-feed·gap·duplicate·out-of-order 시뮬레이션, Jev 응답 fixture 기반 deterministic integration, 비용/호가단위 parameter sweep, 현재 price-only archive에서의 가격 변화 proxy 연구.
- NAS 전체 tick archive는 전수 스캔하지 않았다. 추후에 필요한 범위/기간/종목을 사전 지정해 subset을 읽고 checksum/schema/시간대 coverage를 검사할 수 있다.
- 이 작업에서 broker API나 Jev API를 실제 호출하지 않았고, 키를 찾거나 읽지 않았다.

### 계정/유료 또는 추가 자료가 필요한 것

- KIS paper 계좌/API 권한·approval key, 종목별 실시간 구독 승인/limit, US feed의 지연 여부/모의 계정 호환성/실제 체결·수신 통보 검증.
- 시장별 historical intraday 데이터. 진정한 tick/quote 연구에는 trade prints + NBBO/venue quote 또는 depth + source timestamp/sequence, 정정/취소와 세션 상태가 필요하다. US equity consolidated feed와 한국 KRX/NXT coverage·라이선스/보관 권리·요금은 선택 공급자와 확인해야 한다.
- Jev 계정/API access 및 해당 계정의 현행 rate-limit/quota, 사용 요금, operational SLA/지원정책. 부하 테스트는 낮은 호출량으로 시작하고 provider 정책을 확인한다.
- 실비용 모델: account-specific commission, 환전 spread, SEC/FINRA/거래소 fee, short borrow/recall, KR transaction tax, slippage/impact. 현재 Ochestration의 과거 비용 가정은 seed scenario에만 쓴다.
- stale/out-of-hours/order rejection/partial fill/short unavailable 및 outage를 포함한 multi-week paper run. 확보한 유니버스와 수집 범위의 생존편향도 별도 보고한다.

## 8. 엄격한 paper 검증 프로토콜

### Phase 0 — 사전등록

- 연구 질문/시장/유니버스/거래시간/최대 보유/feature/질문 schema/entry·exit·stop·size·비용·주문유형·latency deadline을 사전에 고정한다. US/KR 별도 프로토콜과 별도 결과를 유지한다.
- 비교군: (A) no-trade, (B) deterministic local-only rule, (C) Jev-augmented rule. 동일 관측·신호 시각·비용·risk gate를 사용한다. Jev 답변만으로 주문하지 않는다.
- 거래비용·slippage·latency stress matrix를 미리 정하고, 결과를 보고 파라미터를 재선택한 데이터는 최종 OOS에서 제외한다.

### Phase 1 — 무주문 feed 검증

- KIS paper feed를 이용해 최소 20거래일 shadow 수집을 목표로 한다(이는 최소 실험 제안이지 통계적 충분성 보장이 아니다). US/KR 각 정규세션 및 개장·종가 주변을 따로 측정한다.
- feed별 subscription ACK, symbol coverage, reconnect 수, 수신 event 수, sequence gap, duplicate, receive lag, provider timestamp가 있으면 source-to-receive delay, 초당 분포를 기록한다. 분모는 거래소 제공 체결/quote 비교 기준 또는 독립 licensed reference feed가 없으면 “측정 불가”로 표시한다.
- tick 저장은 원문+정규화 event-time+collector receive-time을 모두 남긴다. 현행 `now_iso()+price`만 저장하는 형태를 과거 archive와 동일하게 재생산하지 않는다.

### Phase 2 — Jev latency/decision shadow

- 실행 없이 후보 이벤트에서 Jev 호출을 샘플링한다. 요청/응답 monotonic clock, request bytes, input_tokens, output_tokens, model version, market state age, concurrent load, HTTP status, retries, timeout/late answer를 기록한다.
- warm/cold·US/KR 세션·장 초/장 중/급변 구간별 p50/p90/p95/p99/max를 산출하고, deadline 이내 완료율과 no-answer율을 측정한다. 외부 public benchmark나 평균 하나로 대체하지 않는다.
- 선택된 질문/모델 alias를 고정하거나 버전별 결과를 따로 묶는다. rate limit·overload에서 order path가 fail closed인지 검증한다.

### Phase 3 — 이중 paper 체결

- 우선 로컬 simulator에서 quote-crossing, 최소 1 tick adverse execution, 지연 분포를 적용한 다음, 제한된 종목 수의 KIS 모의계좌에서 무위험 주문량으로 주문/취소/체결통보 state machine을 확인한다. KIS paper fills는 real-market fill quality 증거가 아니다.
- 시장가 체결을 mid/last에 자동 가정하지 않는다. 매수는 ask 이상/매도는 bid 이하의 conservative price 또는 calibrated slippage를 쓴다. tick size·price bands·halts·KRVI·SSR·short availability·세션 경계를 반영한다.
- broker simulation과 synthetic fill 결과를 분리 보고한다. 데이터 지연 또는 응답 지연이 정한 deadline을 넘으면 진입 없는 결과로 계산하고 late signal을 소급 실행하지 않는다.

### Phase 4 — OOS 및 통계

- 데이터는 날짜순으로 train/validation/test를 나누고, 최종 test는 한 번만 연다. US와 KR을 합쳐 시장 효과를 숨기지 않는다. DST/휴장·개장·종가, 변동성/유동성 regime별 하위집단을 사전 지정한다.
- 전략 수익뿐 아니라 net PnL, turnover, 비용 비중, fill/partial/no-fill, adverse selection, max drawdown, tail loss, exposure, stale-feed block, late-answer rate, order reject, latency p95/p99를 보고한다.
- 수익성 결론에는 거래수/일수·신뢰구간·multiple testing 보정·시장 benchmark·생존편향 제한을 붙인다. NAS 가격-only 보유기간에 대한 결과는 “초단위 orderflow 성능”이 아니라 “가격-only proxy 재생”으로만 표기한다.
- 최소 안전 체크: 키 노출 0, live endpoint/order route 0, paper flag 강제, 재시작 후 order reconciliation, duplicate signal idempotency, 일일 loss cap, market close handling, stale feed fail-closed, 429/529/timeout fail-closed, 감사 가능한 immutable logs.

## 9. 판정

| 대상 | 지금 가능한 판단 | 결론 |
|---|---|---|
| US equities | KIS API/코드로 제한된 paper feed 실험의 가능성은 있음. archive에 US tick 0, local cache는 일봉. KIS 해외 체결은 API 목록상 지연 체결 명칭. | 과거 초단위 연구는 데이터 확보 전 불가. shadow feed 실측 후에만 paper path 판단 |
| KR equities | KIS 공개체결 구독 코드 및 archive 36일 price-only 있음. 일봉 cache도 존재. | 가격-only 단순 proxy·feed 적재 검증은 가능. 정확한 orderflow/fill replay는 불가 |
| Crypto tick history | Binance trade/mark stream은 코드상 수집하지만 원천 timestamp/size/maker flag를 버리고 archive에 가격만 보관. L2 없음. | 가격기반 이벤트 proxy만 가능. imbalance/volume-delta/queue 연구는 새 원천 수집이 필요 |
| Jev latency | 공식 API는 동기 request/typed response와 429/529를 설명하지만 수치 SLA/latency 한계는 공개하지 않음. | 실제 low-rate shadow workload에서 분포를 측정해야 함. 모델 latency 단독으로 전략 feasibility 판정 불가 |

최종적으로 초단위 paper 보조 의사결정의 프로토타입은 만들 수 있지만, 현재 로컬 자료로 전략 성능을 입증할 수 없다. 첫 완료 기준은 수익 숫자가 아니라 feed/event fidelity, deadline 내 결정 분포, fail-closed, paper order state correctness다. 과거 orderflow 성과 검증을 주장하려면 source timestamp·trade size/side·quote/depth를 보존하는 신규 수집 또는 적법한 historical feed 확보가 선행돼야 한다.

## 출처 (공식 1차 자료)

1. [TypeSafe API reference](https://docs.typesafe.ai/api) — endpoint, request/response schema, usage, HTTP 429/529와 retry handling.
2. [NYSE Trading Information](https://www.nyse.com/trade/trading-information) — 정규장 및 exchange session.
3. [KIS Developers API catalog](https://apiportal.koreainvestment.com/apiservice) — 국내/해외 주문·분봉·실시간 WebSocket 항목.
4. [KRX Guide to Trading in the Korean Stock Market](https://global.krx.co.kr/contents/GLB/01/0109/0109000000/guide_to_trading_in_the_korean_stock_market.pdf) 및 [KRX trading hours](https://global.krx.co.kr/contents/GLB/06/0602/0602010201/GLB0602010201T1.jsp) — 한국 시장 세션.
5. [KRX short-selling restrictions](https://global.krx.co.kr/contents/GLB/06/0602/0602010204/GLB0602010204T5.jsp) — covered short, order verification, uptick rule.
6. [KRX tick sizes](https://global.krx.co.kr/contents/GLB/06/0602/0602010201/GLB0602010201T3.jsp) — KR 주식 호가단위.
7. [SEC Regulation SHO FAQ](https://www.sec.gov/rules-regulations/staff-guidance/trading-markets-frequently-asked-questions-8) 및 [Rule 201 FAQ](https://www.sec.gov/rules-regulations/staff-guidance/trading-markets-frequently-asked-questions-7) — locate/marking/close-out 및 SSR.
8. [SEC Tick Sizes guide](https://www.sec.gov/resources-small-businesses/small-business-compliance-guides/tick-sizes), [SEC 2026-06-11 update](https://www.sec.gov/newsroom/speeches-statements/atkins-statement-minimum-pricing-increments-access-fee-caps-061126) — US Rule 612 increments 및 2026 이행 유예.

현재 facts는 2026-10-16에 확인했다. API 계정별 한도·수수료·개별종목 feed 권리는 변동/계약 조건이므로 계좌 개설 또는 실행 전에 재검증해야 한다.
