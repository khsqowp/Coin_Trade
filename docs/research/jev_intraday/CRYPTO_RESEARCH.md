# Jev(TypeSafe System One)를 이용한 초단기 크립토 의사결정 연구

작성: 2026-10-16  
상태: 설계·문헌조사만 수행. 수익성 결과가 아니며, 라이브 주문·키 접근·신규 백테스트 실행은 하지 않았다.

## 결론

Jev는 초단기 전략에서 주문 엔진이 아니라, 결정론적 가격/체결 특징으로 사전 필터링한 이벤트에 대해 `진입/대기/취소` 같은 제한된 판단을 반환하는 보조 결정층으로만 평가해야 한다. 현재 자료만으로는 초단위 매매 가능성이나 수익성을 판정할 수 없다.

- 공식 TypeSafe 문서는 `POST /v1/systemone`의 구조화 입력/출력과 저지연 의도를 설명하지만, 문서에서 보장된 수치형 p50/p95 지연시간이나 트레이딩 SLA는 확인하지 못했다.
- 저장소의 Binance crypto collector는 `@trade`, USDⓈ-M `@markPrice@1s`를 구독하는 코드가 있었으나, 로컬 작업 트리에서는 해당 파일이 사용자 변경으로 삭제되어 있다. NAS archive는 제공된 인벤토리상 2026-09-01~10월 중순 spot/perp 일별 파일을 보유하지만 `{symbol, ts, price}`만 저장한다. 따라서 실제 체결 이벤트 순서/거래량/매수·매도 주도권/L2 호가를 재생할 수 없다.
- 로컬 2026-10-13 샘플도 `crypto_spot.jsonl` 1.9MB·25,299행, `crypto_perp.jsonl` 13MB·175,195행이고 각 레코드는 symbol/ts/price다. 매우 촘촘한 수신 timestamp만으로 거래소 event time이나 독립적인 시장 tick을 보증하지 않는다.
- 과거 연구는 주로 일봉 OHLCV 기반이다. 여러 차례의 탐색에도 워크포워드에서 견고한 승자를 선언하기 어렵다는 저장소 연구 요약이 있다. 이 결과는 초단기 edge의 근거가 아니다.
- Jev 응답속도와 거래소 데이터/주문 지연은 별도 구간이다. 최종 손익에는 feed 지연·버퍼링·특징 계산·모델 왕복·위험검사·주문 전송·매칭·취소/체결 지연이 모두 들어간다.

## 범위와 저장소 근거

이번 확인의 저장소는 `/Users/user/Desktop/CODE/Ochestration/trading`이다. 상위/저장소 경로에서 `AGENTS.md`를 찾지 못했다. 작업 트리는 시작 당시 clean이 아니었다: `app/crypto_tick_state.py`, `app/crypto_tick_stream.py` 삭제, `app/momentum_rotation_loop.py` 수정, `.rs_cache/`, `agent_sandbox/` 미추적. 이 항목은 수정하지 않았다.

관련 자료:

- `app/tick_archive.py`: 연/월/일/category JSONL append 구조. 실패 시 실시간 상태 갱신을 막지 않도록 archive 오류를 삼킨다는 설계 설명.
- `app/tick_stream.py`: KIS 공개 실시간 체결 KR `H0STCNT0`, US `HDFSCNT0` 구독 구현. 상태 기반 우선순위와 일일 랭킹으로 종목을 고르며, 실제 구독 성공은 세션 응답으로 기록한다. 코드 주석상 공식 동시구독 상한은 확인하지 못했고 거부 응답을 실측 처리한다.
- `app/crypto_tick_stream.py`는 현재 작업 트리에서 삭제 상태다. 사용자 제공 코드 확인과 저장소 이력에 근거해 Binance spot/perp `@trade`, futures `@markPrice@1s` 구독이 있었고 `_handle_*`가 거래소 `T/E`, trade `q`, maker-side `m`을 버리고 수신시각 `now_iso()`와 price만 archive에 저장했다고 기록한다. 이 collector의 현재 checkout 내 소스는 직접 재검증할 수 없다. 사용자 제공 사실을 저장소 코드 현행으로 오인하지 않는다.
- `app/crypto_technical_ict_research.py`: 45종목 USDⓈ-M 1d OHLCV cached frame, 워밍업, 다음 시가 체결 등의 오프라인 설계. 코드의 fee 가정은 편도 0.04%이며 일봉 데이터다.
- `app/crypto_round16_liquidation_research.py`, `docs/round16-results-2026-10-08.json`, `docs/round16-execution-2026-10-08.log`: 397개 계획 결과를 기록한 연구. 문서 요약상 최종후보 0개이며 청산 근접치는 실제 청산/OI가 아니라 OHLC 스윙 앵커·가정 레버리지의 합성 대리변수다. 로그에는 실행 중 KeyboardInterrupt 흔적도 있어 완료 JSON과 interrupted 실행 흔적을 구별해야 한다.
- `docs/research/strategy_catalog.md`, `docs/전략-백테스트-종합.md`: 기존 결과의 범위와 편향을 정리한다. 장기/일봉 결과, 다중탐색, 생존편향, 수수료·펀딩 처리 차이 때문에 숫자를 초단기 전략에 이식할 수 없다.
- `app/tick_stream.py`의 가격 파서 및 `app/tick_archive.py`: KIS 구독 지원을 보여주지만 실시간 피드 자격 증명/실제 archive 적재를 입증하지 않는다.

### 데이터 인벤토리와 한계

NAS 경로 `/Volumes/HDD2TB/Trade/tick-archive`는 이 세션에서 `du`, 파일명 `find`, 제한 샘플로 직접 확인했다. 약 158GB, 2026-09-01부터 10월 중순까지 crypto_spot/perp 일별 파일 각 43개, `kr.jsonl` 36개, `us.jsonl` 0개다. 전체 archive는 재귀 내용 스캔하지 않았다. 2026-10-13 파일의 크기/행수는 spot 1.9MB·25,299행, perp 13MB·175,195행이었다. 첫/마지막 레코드 timestamp 기준 두 파일 모두 약 2분 41초 구간만 관측되어 온전한 하루라고 볼 수 없다. 이는 그 샘플 파일의 경계 레코드 확인이지 모든 레코드의 순서·연속성을 검증한 결과는 아니다. `crypto_funding.jsonl`은 해당 archive에서 0개 확인했다. 158GB 용량을 전략 검증 가능한 분량으로 해석하면 안 된다. 표본 레코드는 `{symbol, ts, price}`뿐이며, crypto/KR 모두 bid/ask depth, size, aggressor side가 없다.

현 데이터로 검증 가능한 것은 파일별 표본 timestamp의 간격/중복/결측, 가격 변화 기반 짧은 horizon 수익률, price-only 모멘텀·반전 대리신호와 보수적 지연/비용 스트레스다. 다만 2026-10-13 표본은 몇 분 구간에 그치고, archive의 전체 coverage·날짜 연속성·종목별 충분한 표본 수를 측정하지 않았으므로 이 세션에서는 그러한 전략 대리 백테스트도 실행하지 않았다. 수신 timestamp만 보존되고 원본 거래소 event timestamp가 빠져 있어 event-time replay와 feed-to-decision 지연 복원은 불가능하다. 실시간 collector 상태가 바뀌지 않았다는 전제도 둘 수 없다.

불가능하거나 식별되지 않는 항목:

- order-book imbalance, depth slope, queue position, spread의 호가 기반 계산, 숨은 유동성 및 book resilience.
- 거래량 delta/CVD, aggressor-side imbalance, trade intensity. `q`와 `m`이 저장에서 제거됐다.
- 거래소 event-time 기준 정확한 신호 생성시점, trade-to-collector latency. 저장된 `now_iso()`는 로컬 수신시각이다.
- 당시 실제 체결가·maker/taker 체결확률·시장충격·부분체결·취소 성공 시점.
- funding 시점 정렬과 역사적 funding payment를 archive price ticks만으로 재계산하는 것.

추가 L2/체결 collector는 적어도 거래소 event time, 로컬 monotonic receive time, sequence/update ID, bid/ask 가격·수량 delta, trade price·base/quote qty·maker flag, mark/index price, funding rate, reconnect/gap marker를 원형 그대로 기록하고 UTC clock offset을 주기 측정해야 한다. Binance depth는 snapshot+diff sequence로 local book을 재구성하고 gap 시 폐기 후 재동기화해야 한다.

### KR/US 피드 상태를 혼동하지 말 것

`app/tick_stream.py`는 KIS 모의투자 도메인의 KR/US 공개 체결 구독 코드를 갖는다. 이는 현재 두 시장 모두 데이터가 archive에 있다는 뜻이 아니다. 요청자 NAS inventory의 `kr.jsonl` 36개는 일부 역사 구간에 KR price-only 레코드가 있다는 증거이고, `us.jsonl` 0개는 해당 archive 경로에서 보유 파일을 확인하지 못했다는 뜻이다. 0개가 현재 KIS subscription이 실패한다는 증거는 아니다. 반대로 코드에서 구독을 지원한다는 것만으로 오늘 성공적으로 구독 중이라고 할 수 없다. 실제 coverage는 세션 state의 `subscribed.kr/us`, timestamp가 있는 실제 payload, 장 운영시간별 연속성으로 따로 확인해야 한다. `tick_stream.py`는 payload에서 symbol과 price를 뽑고 로컬 `now_iso()`를 붙여 저장하므로 exchange timestamp/체결량 정보가 보전되지 않는다.

저장소 문서/주석은 실시간 tick signal이 실매매 판단으로 연결되지 않았다고 명시한다. 그러므로 현 상태를 자동 실행 전략으로 서술하지 않는다.

## Jev API 및 속도 의미

TypeSafe 공식 문서에서 확인한 사항 (2026-10-16 열람):

- HTTPS `POST https://api.typesafe.ai/v1/systemone`, `Authorization: Bearer …`, `Content-Type: application/json`; body는 `model`, `state`, `questions`. `state`는 text/JSON/문자열 배열이고 질문은 `Choice`, `Score`, `Noul`을 지원한다.
- 응답은 resolved `model`, 질의 ID를 key로 한 `answers`, `usage`를 포함한다. Choice/Score에는 probabilities와 confidence가 있고, Noul에는 0~1의 yes probability가 있다. 출력은 주문을 실행하지 않는다.
- 여러 개의 독립 질문을 한 요청에 넣을 수 있으며 공식 소개는 질문 병렬평가, fast structured decisions라는 제품 설명을 한다. 이는 특정 네트워크 환경에서 초단위 trading SLA나 p95 상한을 뜻하지 않는다.
- 공식 공개 모델 API 설명에서 per-request latency distribution/보장 SLA를 찾지 못했다. 현재 배포 모델/alias·region·요청 크기별 실측은 이 작업에서 하지 않았다. `jev-latest`는 바뀔 수 있으므로 실험은 응답의 resolved model ID와 날짜를 고정/기록해야 한다.
- API rate limit은 공식 공개 문서에서 이번 열람으로 직접 확인하지 못했다. 제3자 Go SDK `kataras/jev`가 TypeSafe 문서를 인용해 1,200 requests/minute 및 250,000 input tokens/second를 기본값으로 기재한다. 이 수치는 공식 페이지 직접 검증이 아니므로 잠정 참고치이며, 실제 조직 quota는 확인되지 않았다. limit은 throughput 정책이지 개별응답 latency 보장이 아니다.
- 공식 API는 동기식 JSON request/response다. 공식 SDK에서 timeout/retry를 설정할 수 있고, 오류·재시도·backoff는 tail latency를 늘린다. 자동주문 안전장치는 모델 재시도를 기다리지 않고 만료 시 `NO_TRADE`여야 한다.

자료에서 API 스키마 설명을 독립적으로 구체화한 jev.pro/SDK 문서는 TypeSafe 공식 문서가 아니다. 본 보고서는 endpoint와 핵심 shape는 TypeSafe 공식 Quick Start를 사용했다. published quota 숫자는 제3자 SDK가 TypeSafe 공식 문서를 인용한 간접 근거라서 불확실성으로 처리한다. 정확한 현재 quota·지원 모델은 console/공식 API에서 키로 확인하지 않았고 키 사용을 피했다.

### 지연시간 분해와 안전 예산

다음 합을 end-to-end `decision_age`로 측정한다. 모델 latency만 측정해 매매 적합성을 주장하지 않는다.

`decision_age = market_event_to_local_receive + feature_and_queue + Jev_HTTP_RTT + policy/risk + order_send_to_ack + ack_to_fill`

`decision_age`는 각 구성 요소의 p50/p95/p99와 timeout/error 비율을 따로 기록한다. Event timestamp가 없는 현재 archive에서는 첫 항목을 신뢰성 있게 복원할 수 없다. 라이브 평가 전에는 별도 shadow collector에서 exchange event time과 local monotonic clock을 동시에 남겨야 한다. 수신 데이터가 stale하거나 clock offset/sequence gap을 알 수 없으면 즉시 no-trade.

Jev는 event burst마다 호출하지 않는다. 저비용 코드가 후보 이벤트를 솎고, 동일 시장/상태 hash의 중복 호출을 합치고, 호출당 3~5개의 독립 질문을 한 번에 묶는다. 응답 만료 deadline은 전략 horizon 및 edge decay보다 짧게 정한다. 첫 프로토콜은 shadow-only이며 `decision_age` p99가 사전 한도를 넘으면 호출 결과를 폐기한다. 250ms/500ms/1s 같은 한도는 검증 파라미터 후보일 뿐 모델 보장치가 아니다.

## 후보 가설 5개 (전부 미검증)

공통: 먼저 후보 이벤트를 코드로 생성하고 Jev는 bounded state와 Choice/Noul 질문으로 상태 분류/행동 선택만 한다. 입력은 정규화 숫자·요약값이고 임의 뉴스 텍스트를 넣지 않는다. 결정론적 하드 가드는 모든 모델 답보다 우선한다. 정확한 orderflow 후보는 L2/trade raw collector가 구축되기 전까지 백테스트 금지이며 아래는 미래 검증 가설이다.

### H1 — 가격 급변 후 짧은 추세 지속

- **촉발:** 완료된 1초 집계 mid/last 가격의 5초 로그수익률이 직전 60초 실현변동성 표준편차의 `z ≥ 2.5` (short는 `z ≤ -2.5`)이고 5초 quote/trade count가 과거 30분 동일 시각대 90백분위 초과. 두 조건 모두 event-time 기준.
- **Jev 입력/질문:** 1/5/15/60초 수익률, 변동성, spread bps, normalized volume, mark/index basis, funding까지의 초, book/trade freshness, BTC 동조도. “다음 10초에서 impulse 지속/횡보/반전 중 무엇인가?”, “현재 진입 우위가 비용 후 양수일 가능성이 있는가?”를 Choice와 Noul로 묻는다.
- **가설 반증:** 테스트 구간 net 10초 markout이 무모델 trigger 및 단순 z-momentum보다 낮거나, 비용 전 우위만 있고 비용 후 0 이하이면 기각.
- **보유/종료:** 5~15초 timeout, 반대 z 신호, hard stop 중 먼저 도달. 손절은 진입 후 adverse 1.0×최근 1초 변동성 또는 계좌위험 한도 중 더 작은 값.

### H2 — 짧은 시간대 가격 반전/과확장

- **촉발:** 3초 누적수익률 `|z| ≥ 3`, 그 다음 1초 수익률이 직전 impulse 방향 반대로 전환, 가격이 5초 VWAP에서 2×1초 변동성 이상 이탈. spread가 10 bps 이내이고 stale feed 아님.
- **Jev 입력/질문:** 1/3/5/30초 path, VWAP gap, 변동성, quote update rate, trade count, 반대방향 가격 변화 지속 여부. `fade / wait / no-trade` 중 선택하고 confidence floor를 shadow calibration으로 정한다.
- **반증:** 5초/15초 net markout이 reversal baseline보다 개선되지 않거나 adverse selection tail이 커지면 폐기.
- **보유/종료:** VWAP 재접근 또는 최대 10초, impulse 재개 시 즉시 종료. stop은 impulse extreme + 0.5×5초 변동성.

### H3 — L2 imbalance와 가격확인의 동행

- **촉발:** 5단계 depth imbalance `I=(Σbid_qty−Σask_qty)/(Σbid_qty+Σask_qty)`가 3회 연속 업데이트에서 0.6 초과(롱) 또는 -0.6 미만(숏)이고, 다음 1초 mid가 같은 방향으로 최소 1 tick 확인.
- **Jev 입력/질문:** 순서가 검증된 L2 snapshot/delta, top-5/10 imbalance, depth slope, spread, quote cancel/update rate, 100/500ms trade flow, 1/3초 mid 변화. “지속/흡수/불충분” 분류와 trade 허용 Noul.
- **반증:** 기록 가능한 L2 보유 후에만 검증. 1/3/5초 mid markout이 spread·수수료 비용 이후 0 이하, 또는 gap/reconnect 구간 제외 후 우위 소멸 시 폐기.
- **보유/종료:** 1~5초; imbalance 반전/가격 confirmation 취소/sequence gap이면 종료. 현재 파일은 imbalance를 재구성할 수 없어서 역사 백테스트 불가.

### H4 — Aggressor flow 고갈 뒤 반전

- **촉발:** rolling 1초 signed quote volume delta가 10초 z-score 3 초과인데 200ms mid return은 더 이상 고점을 갱신하지 않고, 해당 방향 top-of-book depth가 2회 연속 회복(흡수/고갈 후보). 부호는 Binance `m` 또는 검증된 exchange aggressor-side 정의로 계산.
- **Jev 입력/질문:** `q`, `m`, spread, top depth, trade arrival intensity, mid markout, 변동성. `absorption / continuation / ambiguous` 선택. Jev 확률은 실현 1/3/5초 markout으로 calibration 평가.
- **반증:** 가격만 사용한 contrarian baseline보다 net markout/실행 가능성 개선이 없거나 모델 추가가 비용·latency 후 성과를 낮추면 기각.
- **보유/종료:** reversal confirmation 후 1~5초. flow 재가속/극단 adverse move 시 즉시 청산. archive에서 q/m가 버려졌으므로 과거 정확 검증 불가.

### H5 — Funding/mark 급변 시 execution veto (방향 예측 아님)

- **촉발:** 미래 funding settlement까지 60초 이내이고 predicted funding 또는 mark-index basis가 최근 24시간 분포의 99백분위 초과, 또는 mark/last basis가 30초 z-score 3 초과.
- **Jev 입력/질문:** funding rate와 다음 settlement까지 시간, mark/index/last basis, spread/depth, 변동성, 예상 holding horizon, 예정 주문의 side/notional. `allow / delay / reduce / no-trade`를 선택하되 결정론적 risk guard가 leverage/size 상한을 적용.
- **반증:** settlement window와 대조시간 matched sample에서 비용 후 손실 꼬리/체결 품질이 나빠지지 않으면 veto 가치 없음. funding 예측과 실제 수령액을 분리 측정.
- **보유/종료:** 이 후보 자체는 포지션 진입 전략이 아니라 보유·주문 제한 조건이다. funding 지급 직전 신규 포지션을 자동 승인하지 않는다.

## 포지션·비용·위험 규칙 (실행 전 고정할 제안)

- 초기 단계는 shadow-only, 이후 거래소 testnet/demo의 체결 API로 paper execution. API key 없이 public feed만 사용. 계정/키 발급은 본 작업에서 하지 않았다.
- 무레버리지 또는 최대 1x notional, 주문당 stop-distance 기준 equity 위험 2bp, 심볼 단일 총노출 10% equity, 모든 심볼 총 gross 25% equity, 일중 손실 20bp면 정지. 이는 보수적인 실험 상한 제안이지 최적값이나 투자 조언이 아니다.
- 계약 lot/tick/min-notional/position mode는 거래 전 exchangeInfo/contract metadata로 읽어 검증. 수량은 stop loss 금액 기준으로 산정하고, reduce-only exit, 중복 client-order ID, 최대 주문 빈도, kill switch, stale/gap 차단을 구현한다.
- 매매 진입의 왕복 명목 수수료는 maker/taker 실제 tier를 모르는 동안 각각 편도 5bp/10bp 민감도 범위로 스트레스한다. 이는 거래소 확정 수수료가 아니다. 기존 일봉 연구의 편도 4bp 가정을 그대로 사용하지 않는다.
- 슬리피지는 거래소 depth replay가 가능해지면 실제 호가별 VWAP으로 추정한다. 그 전에는 편도 추가 2/5/10bp 스트레스와 latency adverse excursion stress를 별도 보고한다. 미래 최우선호가를 과거 주문 체결가로 쓰면 안 된다.
- funding 비용/수취는 실제 계약의 정산 timestamp 및 역사 funding rate를 별도 자료로 join해 부호와 position을 반영한다. 초단기 보유가 settlement를 넘지 않아도 진입/종료 주변 mark/basis 비용은 별도로 기록한다.
- 한번의 이벤트가 겹치면 symbol당 포지션 1개, 이벤트당 한 주문. 연속 실패/429/529/timeout/unknown response면 진입 금지. 재시도는 새로운 평가일 뿐 자동 주문 재전송을 뜻하지 않는다.

## 비교군과 반증 기준

각 동일 이벤트와 시점에 아래를 paired comparison으로 실행한다:

1. **No-trade**와 무작위 방향/진입 시간(같은 이벤트 군집·시간대 조건).
2. 간단한 결정론적 trigger만 사용 (H1: z-momentum, H2: z-reversal, H3/H4: 사전 등록 후 코드 임계값, H5: funding veto 없음).
3. 같은 feature/질문/decision deadline을 쓴 Jev 게이트. 별도 조건으로 항상 allow, 항상 abstain, confidence 무시, confidence gate를 비교한다.
4. Jev 없이 deterministic 정책만, Jev와 동일한 실측 RTT를 지연 적용한 deterministic 정책. 모델 기여와 단순 지연효과를 구분한다.
5. passive limit / taker market / no-fill을 포함한 체결 모델. mid price markout만으로 실행 수익을 주장하지 않는다.

1차 지표는 fee/funding/slippage 차감 후 net PnL per event 및 거래당 bps, 1/3/5/10초 markout, fill ratio, adverse selection, turnover, max drawdown, 손실 꼬리, 결정 coverage, probability calibration, timeout/stale abstain 비율이다. 후보별 가설·threshold·비용·모델 pin·질문을 사전 등록한다. 하나라도 다중 탐색한 횟수를 보정한다. 채택은 모든 사전 고정 OOS 구간의 net expectancy가 양수이고 비용 상향 스트레스에서도 우위가 baseline을 넘으며 bootstrap 신뢰구간 하한이 0 초과할 때만 고려한다. 유의성만으로 실제 수익성을 선언하지 않는다.

## 현실적인 backtest → paper 프로토콜

1. **데이터 무결성 감사:** NAS 전체가 아닌 manifest/파일 크기/일부 샘플로 시작. 파일별 날짜·symbol coverage, 중복/정렬·누락·점프, local timestamp 간격과 clock offset을 기록. 기존 archive는 price-only 데이터셋으로 별도 라벨. 공급자가 다른 축을 섞지 않는다.
2. **가격 대리시험:** 현재 price-only ticks로 할 수 있는 H1/H2의 제한적 이벤트 분석만 한다. 동일 가격이 반복되는 collector sample을 distinct trade로 오인하지 않는다. 시간 기준은 저장된 local receive timestamp이며 exchange event-time simulation이 아닌 점을 제목과 표에 명시한다. H3/H4/L2 및 실행모델 주장은 금지.
3. **새 raw feed 수집:** Binance public spot+USDⓈ-M trade, mark/index/funding, bookTicker, depth diff를 sequence-safe하게 병행 수집. event time과 monotonic receive time 모두 저장. 한 연결의 stream/update 제한, 24h reconnect, ping/pong, depth snapshot gap 회복을 처리한다. H3/H4 검증에는 100ms L2 및 원체결 `q/m`를 우선 저장. KIS/주식 archive는 별도 시스템이며 코인 검증과 혼합하지 않는다.
4. **사전 정의/분할:** 가장 오래된 구간으로 feature/threshold 개발, 그 다음 기간으로 validation, 마지막 연속 4주 이상 untouched OOS, 이후 새로 수집된 forward 기간으로 확인. 전략 다섯 개/파라미터 전부 탐색 수를 기록하고 purged event split/embargo로 겹치는 label horizon 누수를 방지한다. 가격 regime, symbol, 시간대별도 보고.
5. **비동기적 비용 현실화:** timestamped raw event를 causal replay한다. Jev의 예측을 저장하고 실제 과거 시점의 응답을 재현하려면 당시 API query/response log가 필요하다. 현재 API를 옛 과거 candle에 호출하는 것은 과거 latency/model 상태 재현이 아니므로 historical backtest에서 Jev output을 만들어냈다고 간주하지 않는다. 먼저 live shadow logging으로 같은 모델 버전/질문 response를 모아 이후 OOS 평가에 쓴다.
6. **Shadow 운영:** 최소 2주/1,000개 후보 이벤트 중 더 긴 기간. 주문 없음. feed receive→feature→Jev request/response→policy deadline의 monotonic timestamp, timeout/429/529, resolved model, input/output token, answers/probabilities, no-trade 사유를 저장. p50/p95/p99와 stale rate 측정. 지연 deadline을 넘긴 결과는 늦게 도착해도 버린다.
7. **Paper execution:** shadow 통과 시 Binance demo/testnet paper order adapter에서 주문의 체결/미체결/부분체결/취소를 모사. 실제 queue position이 없으면 optimistic fill 금지; conservative queue haircut와 market impact stress. 최소 4주 paper, 매일 reconciliation. 어떠한 실계좌 주문도 자동 승격하지 않는다.
8. **승격 기준:** 모든 고정 OOS 및 paper 기준 통과, tail loss/kill switch 시험 성공, net edge가 각 비용 스트레스에서 유지, Jev가 deterministic baseline 대비 incremental improvement를 보이고 지연 budget을 만족해야 한다. 그 이후에도 live 주문은 이 연구 범위 밖이며 별도 명시 승인·안전 리뷰가 필요하다.

## 공식 문서와 출처

열람일 2026-10-16. 하위 링크는 문서가 바뀔 수 있으므로 설계에 사용한 구체 기준을 고정 기록한다.

- TypeSafe [Quick start](https://docs.typesafe.ai/introduction/quickstart): endpoint, JSON request/response 예시, request fields, answers/usage.
- TypeSafe [Introduction](https://docs.typesafe.ai/introduction), [System One](https://docs.typesafe.ai/concepts/system-one): typed decisions, parallel independent questions, product positioning. 지연 SLA 수치가 아님.
- TypeSafe [Errors and retries](https://docs.typesafe.ai/api-reference/errors): timeout/error/retry 처리 기준. 재시도는 latency를 늘릴 수 있음.
- TypeSafe [HTTP API reference](https://docs.typesafe.ai/api-reference/http): endpoint/schema 원문.
- TypeSafe 공식 [API reference](https://docs.typesafe.ai/api), [Python SDK retries](https://docs.typesafe.ai/sdk/python/api/retries), [Python SDK constants](https://docs.typesafe.ai/sdk/python/api/constants): API/SDK 계약과 설정을 확인한다. latency percentile/SLA 숫자는 이 문서에서 확인하지 못했다.
- 제3자 Go SDK [`kataras/jev`](https://github.com/kataras/jev): 1,200 RPM / 250,000 input tokens/s를 TypeSafe 문서 인용값으로 소개한다. 공식 원문 quota를 이번 조사에서 직접 재확인하지 못했으므로 보장값으로 취급하지 않는다.
- Binance [Spot WebSocket Streams](https://github.com/binance/binance-spot-api-docs/blob/master/web-socket-streams.md): aggTrade/trade, depth update, event fields, stream limits/reconnect, snapshot+diff sequence.
- Binance [Spot WebSocket API](https://github.com/binance/binance-spot-api-docs/blob/master/web-socket-api.md): request/response, order request/rate-limit 개요. Spot와 futures 규칙을 동일하다고 가정하지 않는다.
- Binance [USDⓈ-M Futures WebSocket Market Streams](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/ws-streams/public): trade/depth/bookTicker/mark stream, sequence fields 및 업데이트 속도. 공식 문서상 depth stream은 100ms/250ms/500ms 선택이 가능하지만 이는 데이터 push 속도이지 end-to-end latency 보장이 아니다.
- Binance [USDⓈ-M Futures New Order](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/trade): order fields/validation.
- Binance [USDⓈ-M Futures exchange information](https://developers.binance.com/en/docs/catalog/derivatives-trading-usds-futures/market-data/rest-api/exchange-information), [funding rate history](https://developers.binance.com/en/docs/catalog/derivatives-trading-usd-s-m-futures/api/rest-api/market-data): tick/step/limit/funding 값은 실행 시점에 공식 API metadata로 확인해야 함.
- Binance [USDⓈ-M Futures limits](https://developers.binance.com/en/docs/products/derivatives-trading-usds-futures/general-info): IP request weight 및 order limits. 가변 값이므로 현재 exchangeInfo/계정 응답으로 확인한다.
- KIS Open API [문서 포털](https://apiportal.koreainvestment.com/): 현재 subscription 구현이 참조하는 KR/US 공개체결 채널. 동시 구독 한도와 실시간 coverage는 API 응답/state 및 archive manifest로 따로 확인.

## 불확실성과 누락

- TypeSafe 공식 docs에서 p50/p95/p99 inference latency/SLA 및 공식 quota 숫자를 이번 조사에서 직접 확인하지 못했다. 제3자 SDK의 quota 인용과 SDK timeout은 이를 대체하지 못한다. 실측 없이는 초단기 응답 가능성 결론 불가.
- Jev 호출 latency를 실제 API에 측정하지 않았다. 키/계정 접근은 하지 않았다.
- Binance 공식 docs 경로는 변경될 수 있다. 개별 endpoint별 weight, order count, position mode, maker/taker fee tier는 paper 전에 현재 계정/제품 기준으로 다시 확인해야 한다.
- NAS 용량·파일명 개수와 일부 샘플은 이 세션에서 직접 확인했지만, 전체 158GB의 내용·coverage·연속성은 스캔하지 않았다. 2026-10-13 crypto sample도 첫/마지막 행 기준 몇 분 구간만 보였다.
- 2026-10-13 로컬 sample은 NAS 전체의 대표성을 보증하지 않는다.
- 현재 dirty worktree에서 crypto stream 구현 파일은 삭제 표시. 사용자 제공 추가 코드 확인을 명시적으로 provenance 처리했다.
- 본 작업은 전략 신호 구현, 백테스트, 수익률 계산, API 호출, paper/live 주문을 수행하지 않았다. **전략 5개는 반증 가능한 연구 가설이며, 수익성 주장이 아니다.**

## 정확한 산출물과 검증

요청한 신규 파일은 아래 두 개뿐이다:

1. `docs/research/jev_intraday/CRYPTO_RESEARCH.md` — 본 보고서.
2. `docs/research/jev_intraday/crypto_plan.json` — 전략 정의, 수수료/리스크 가정, 데이터/latency 한계, 실험 단계와 채택 기준.

현재까지 한 검사: repository/status·코드/문서·저장된 결과 artifact와 제한된 local tick sample 확인, 공식 문서 웹 조회. 전체 NAS 파일 스캔·API latency benchmark·backtest/test/paper/live order는 수행하지 않았다. 파일 생성 후 JSON parser, Markdown 필수 주제, Git diff/status로 산출물을 확인한다.
