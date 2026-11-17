# 사전등록 후보 — 코인 taker-aggressor flow 급등·급락 신호

작성일: 2026-11-17
상태: **아이디어 등록 / 데이터·방법 게이트 미통과 / 성과시험 금지**
범위: 독립 crypto taker-aggressor-flow 연구. 네트워크, 계정, 거래소 주문, 공용 소스 변경은 하지 않았다. 시장 outcome/label을 읽거나 채점하지 않았다.

## 1. 기존 volume/flow 가설 중복 감사

확인한 주 자료는 `docs/chart_predictor/SPEC.md`, `docs/research/round1_candidate_register_20261116.md`, `docs/research/agent_strategy_research_rounds_20261115.md`, `docs/research/round5_continuation_20261117.md`, R018 `plan.md`와 결과/manifest다.

| 선행 가설 | 이미 등록·시험된 구조 | 새 후보와의 중복 판정 |
|---|---|---|
| C-08 volume participation directional efficiency | 4h 코호트 정렬 + 5m quote-volume/캔들 몸통 비율 상위 분위 + 종가 위치 | 거래량 참여도와 방향 종가를 사용한다. 새 후보는 taker 매수/매도 불균형과 가격 비진행의 괴리를 쓰므로 직접 동일하지 않지만, close-location 구성요소는 부분 중복이다. |
| C-10 synchronized wave laggard join | 코호트 breadth/BTC 4h 방향 + 5m 범위 돌파와 시간대별 거래량 | 4h 방향 필터 및 확인 돌파가 겹친다. 코호트 breadth/laggard 순위는 새 후보에 넣지 않는다. |
| round-3 volume climax + failed breakout | 엄격한 20-bar 고저 갱신, 거래량 ≥ 이전 20-bar 중앙값의 3배, 실패 종가 후 반대 진입, ATR stop, 1.5R, 10/20 bar | 고점/저점 실패 뒤 반전이라는 결과 형태가 상당히 가깝다. 새 후보는 단순 고거래량 실패돌파가 아니라 aggressor imbalance가 큰데 가격이 더 진행하지 않는 흡수 괴리를 필수화한다. 여전히 부분 중복이며 사전등록상 신규성은 제한적이다. |
| long-history taker-imbalance breakout | 30m 종가의 직전 20-bar 고저 돌파, taker imbalance ±0.30, 거래량 ≥1.5× median, next open, 1.5 ATR stop, 2R, 10/20 bars | 같은 입력 계열이지만 기존은 flow와 가격이 같은 방향인 추세 돌파다. 새 후보는 flow와 가격의 단기 비진행이 반대인 흡수형 신호다. |
| taker-imbalance multi-timeframe grid | 동일한 방향성 taker imbalance 돌파를 12개 timeframe에서 검사 | 파라미터/timeframe 변형을 추가하는 것은 중복으로 간주한다. 후보는 기존 grid의 승격·재시험이 아니다. |
| liquidation cascade/absorption lead (round5 continuation) | 청산·호가 깊이로 확인되는 cascade/흡수. OHLCV만으로 청산 이벤트나 order-book depth 식별 불가 | 새 후보의 OHLCV proxy는 실제 liquidation/LOB absorption으로 해석하지 않는다. 이 proxy는 “taker-flow/가격 비진행”만 표현한다. 실제 청산 가설로 확장하려면 별도 timestamped liquidation/depth 데이터가 필요하다. |

선행 taker 테스트는 탐색적 개발 데이터에서 성과/80% 기준을 통과하지 못했고 비용·funding·spread의 완전한 검증도 아니다. 이 감사는 가설 중복 분류이며 어떤 새 후보의 성과 근거도 아니다. 이미 노출된 개발 데이터에서 수행하는 후속 결과는 OOS나 독립 확인으로 표기할 수 없다.

## 2. 입력·아카이브 가용성 점검

로컬 파일 `chart_predictor/data/vision_pit_dev_sample.sqlite`는 read-only로 접근했다. SQLite 스키마상 `candles`에 `quote_volume`, `taker_buy_base`, `taker_buy_quote` 열이 존재한다. `archive_manifest`에는 `symbol`, `month`, `sha256`, `rows`, `archive_bytes`, `retrieved_utc` 열이 있다. 이번 점검에서는 OHLCV 값이나 outcome 열을 조회하지 않았다.

`round5_continuation_20261117.md`에 기록된 기존 archive-manifest 집계는 5,522 symbol-month 행, 86개 심볼, 70개월(2021-01~2026-10), 그중 월별 1m 기대 행수가 모두 채워진 심볼 37개다. 같은 기록은 8개 격리 아카이브 및 38개 심볼에 걸친 577,125개 미분류 결측 minute slot을 명시한다. 이는 OHLCV 구조적 가용성이지 point-in-time 계약 유니버스 완전성이나 taker 필드의 비결측 가용성 증명은 아니다.

이번 실행 환경에서 전체 candle 테이블 대상 null 집계는 제한 시간 안에 결과를 반환하지 못했다. 따라서 taker 필드가 각 심볼·월·주기에서 실제로 얼마나 채워져 있는지는 **미확인**이다. 존재하는 열을 전 심볼의 유효 데이터로 간주하지 않는다. 1m가 5m/4h로 올바르게 합산되는지, archive별 checksum/행 격자·중복·누락·NaN·유한성도 아직 후보 입력 기준으로 검증되지 않았다. 일일 metrics의 taker-volume ratio는 OHLCV taker-buy quote와 다른 출처/정의이므로 대체 입력으로 쓰지 않는다.

## 3. 고정 후보 정의 (성과 확인 전 동결)

가칭: **4h regime-gated 5m taker-imbalance absorption-and-confirmation**. 고정된 규칙 하나만 제안한다. 4h는 macro 방향 허용 필터이고, 신호·진입·위험 관리는 5m 기준이다.

### 입력과 계산

- 입력은 확정된 1m OHLCV만 사용한다. UTC 경계에 정렬해 5m와 4h 캔들을 구성한다. 미완성 캔들, 이후 값으로 수정된 피벗, Vision metrics, funding/OI, 청산 피드, order book은 사용하지 않는다.
- 5m quote aggressor imbalance: `I_t = 2 * taker_buy_quote_t / quote_volume_t - 1`. `quote_volume_t <= 0`, null, 비유한 값, 또는 `taker_buy_quote_t`가 `[0, quote_volume_t]` 범위 밖이면 해당 바는 무효다. 유효성 실패를 0 imbalance로 대체하지 않는다. quote 필드가 확인되지 않으면 base 필드로 자동 대체하지 않는다.
- 4h long 허용: 가장 최근 완료 4h close가 EMA50 위이고 EMA50이 4h 전보다 높다. Short 허용은 close가 EMA50 아래이고 EMA50이 4h 전보다 낮은 경우다. 두 조건 모두 아니면 신호 없음.
- 가격 위치는 5m 신호봉에서 `(close-low)/(high-low)`로 정의한다. `high == low`는 무효다. ATR은 완료된 5m 바 기반 Wilder ATR(14)이며, 신호 계산 시점까지 확정된 값만 사용한다.

### 롱 신호

1. 5m 봉 `t` 직전 12개 완료 봉의 최저가보다 `low_t`가 낮거나 같다(동률 포함). 이는 사전 범위 하단에서 공격적 매도 압력이 관측된 상황을 정의한다.
2. `I_t <= -0.35`, `quote_volume_t`는 직전 20개 완료 5m quote-volume 중앙값 이상, 종가 위치는 0.65 이상이어야 한다. 즉 공격적 매도 우위에도 종가가 봉 상단 쪽에 머문다.
3. 다음 완료 5m 봉 `t+1`의 종가가 `high_t`보다 높으면 확인(trigger)이 발생한다. `t+1`에서 조건이 확인되기 전에는 주문/가상 체결을 만들지 않는다.
4. 진입은 확인봉 다음 5m 바의 시가(open)로 정의한다. 그 시가가 신호를 무효화하는 손절가 이하이거나 갭으로 계획 손익비가 1.5 미만이 되면 진입하지 않고 해당 설정을 미체결로 기록한다. 비용을 결과에 맞춰 재진입 가격으로 보정하지 않는다.

### 숏 신호

1. 5m 봉 `t`의 `high_t`가 직전 12개 완료 봉의 최고가보다 높거나 같다.
2. `I_t >= +0.35`, 거래대금은 직전 20개 완료 봉 중앙값 이상, 종가 위치는 0.35 이하여야 한다. 공격적 매수 우위에도 종가가 봉 하단 쪽에 머무는 경우만 허용한다.
3. 다음 완료 5m 봉 `t+1` 종가가 `low_t`보다 낮으면 확인된다.
4. 진입은 확인봉 다음 5m 바 시가다. 시가가 손절가 이상으로 무효화되거나 계획 보상/위험이 1.5 미만이면 미체결 처리한다.

### Stop, target, deadline, 중첩

- 롱 stop: `min(low_t, low_(t+1)) - 0.25 * ATR14_t`. 숏 stop은 두 봉 high의 최댓값에 `0.25 * ATR14_t`를 더한다. 진입가와 stop 간 거리가 0 이하 또는 5m 진입가의 4.5% 초과면 후보에서 제외한다. 이 상한은 사전 제한이며 레버리지/청산 모델이 아니다.
- 목표: 진입가 기준 stop-risk의 1.5배(1.5R). stop과 목표가 한 동일 1m 경로 구간에서 모두 닿으면 stop 우선. 1m가 없거나 경로 순서를 판별할 수 없으면 임의로 성공 라벨을 주지 않고 데이터 미해결로 격리한다.
- 기한은 10개 5m 바와 20개 5m 바를 서로 다른 claim으로 고정한다. 만료 시 목표 미도달은 M2 성공이 아니다. 만기 종가 방향 정확도는 별도 지표로 보고한다.
- 심볼별 동시 보유는 금지한다. 첫 발행 신호부터 등록 기한까지 같은 심볼의 새 신호를 막는다. M2의 all-emitted 분모에는 프로토콜상 발행된 모든 신호를 유지하고, 별도 outcome-blind 비중복 표본은 N/종목수 gate에만 사용한다. 후보 신호에 대한 추가 중복 억제는 성과를 본 뒤 변경하지 않는다.

## 4. 비용·신규성·필요 데이터

- 고정 비용 민감도: 왕복 0.10% base와 0.30% stress를 최소 비교선으로 기록한다(기존 탐색 실험의 가정과 정합). 이는 관측된 수수료·spread·slippage가 아니다. 실제 시점별 수수료 등급, bid/ask 및 체결 가능한 spread, 슬리피지, funding/펀딩 시각과 정확한 체결 모델을 확보하기 전에는 비용 후 성과 판단을 허용하지 않는다. 비용을 못 구하면 `INCONCLUSIVE`, 0 비용 대체 금지.
- 신규성: 같은 taker 데이터 계열은 이미 시험되었으므로 넓은 의미의 신규 전략 주장은 금지한다. 차이는 방향성 breakout이 아닌 extreme에서의 **반대 aggressor 우위 + 종가 비진행 + 다음 바 구조 확인** 조합이다. round-3 실패돌파 가설과 유사하다는 점을 등록된 중복 위험으로 유지한다.
- 필수 데이터: 고정된 심볼 코호트 및 dated contract-incarnation/PIT eligibility; 1m OHLCV의 quote volume/taker-buy quote; checksum·archive manifest·expected grid; 결측/중복/비유한·범위오류 보고; 4h/5m resampling 검증; 1m 실행 경로; 수수료·spread·slippage·funding; 독립된 forward 평가 구간. 1m archive의 checksum만으로 계약 정체성이나 데이터 완전성을 증명하지 않는다.

## 5. 실패 조건과 시험 전 게이트

아래 하나라도 해소되지 않으면 후보를 실행·채점하지 않는다.

1. **R018 synthetic method gate 미완료:** R018 plan은 synthetic paired-baseline inference만 다루며 OHLC barrier path/cost 검증을 별도로 요구한다. profile-A equality-null calibration은 통과 기록이 있지만, profile B/C, alternatives, missingness stress calibration 및 별도 OHLC path method test는 남아 있다. A/null 결과를 전체 gate 통과로 확대 해석하지 않는다. 전체 계획 결과와 독립 검토가 통과하기 전 시장 outcome/label을 열지 않는다.
2. **데이터 필드 게이트:** quote/taker 필드의 심볼×월×기간별 null·범위·합산 정확성, 누락 아카이브와 1m 격자가 사전 고정 기준에 미달하면 해당 심볼·기간을 유효 입력으로 쓰지 않는다. 20개 심볼 이상 유효성과 10/20 deadline별 N 가능성을 outcome 접근 전에 입증하지 못하면 시험 중단이다. 결측을 0 또는 일반 volume으로 채우지 않는다.
3. **결과 규칙:** 시험을 별도로 허가받은 뒤에도 all-emitted M2 target-first 점추정은 각 10/20-bar claim에서 ≥80%여야 한다. deadline-close direction accuracy는 반드시 별도 산출한다. 각 claim의 outcome-blind 비중복 표본 N≥200 및 ≥20 symbols는 별도 eligibility gate이며 M2 분모를 대체하지 않는다.
4. **검증 설계:** 1,000회 Monte Carlo reorder/randomization 진단을 사전 고정하고 결과 선택에 사용하지 않는다. 504/252 calendar-day walk-forward를 각 5개 fold에서 수행하며, 각 fold 경계·purge·embargo·표본 정의를 결과를 보기 전에 동결한다. 10/20-bar claim과 모든 fold를 함께 보고한다. 다섯 fold 중 유리한 것만 뽑지 않는다.
5. **인접 파라미터 안정성:** 사전 정의한 각 핵심 임계값의 바로 인접한 낮음/높음 설정에서, 기준 규칙의 pass/fail 판정이 동일한 비율이 80% 이상이어야 한다. 이 plateau는 사전 고정된 이웃 격자 전부에서 계산하고 좋은 이웃만 선택하지 않는다. 인접 설정에서 성능을 다시 조정하지 않는다.
6. **손실/미해결/비용:** outcome 미해결 비율이 별도 사전 허용 한도를 넘거나 비용 자료가 없고, 실행 경로에서 stop-first를 재현하지 못하거나 positive net expectancy가 입증되지 않으면 통과시키지 않는다. 해당 한도와 동시추론 방식은 성과 접근 전 독립 승인되어야 한다.
7. 기존 개발 기간·결과에 노출된 자료를 사용하면 exploratory로만 분류한다. 미래/forward boundary가 분리되고 읽기 접근 통제·append-only 기록이 증명되지 않으면 OOS 성과 주장을 금지한다.

## 6. 성과시험 허용 후 필요한 unit/invariant tests

테스트 코드를 작성하거나 실행하는 것 자체도 위 R018 전체 method gate와 독립 승인 이후에만 허용한다. 이 절은 향후 체크리스트이며 이번 작업에서 테스트를 수행하지 않았다.

- imbalance: 전부 taker-buy이면 +1, 전부 taker-sell이면 -1, 균형이면 0; null/0 denominator/비유한/범위 위반은 fail-closed.
- 시간 정렬 및 lookahead: UTC 1m→5m/4h 경계·누락 바 처리, 확정봉만 입력; 미래 suffix 변조가 과거 신호/feature를 바꾸지 않는 prefix-invariance.
- macro state: EMA50은 마지막 완료 4h만 사용; 동률/평탄 EMA는 양방향 허용 안 함.
- trigger 대칭성: 가격·imbalance 부호를 반전한 synthetic fixture에서 long/short 조건이 대칭; extreme는 직전 12개만 참조; 볼륨 중앙값은 신호봉 제외.
- 확인/체결 순서: 신호봉, 확인봉, 다음 시가 순서 검증; 미확정 시점 진입 및 확인봉 시가 체결 금지; gap으로 stop 무효/손익비<1.5면 no-entry.
- barrier: stop/target 단일 1m 구간 동시 접촉은 stop-first; 1m 결측/모호한 경로는 unresolved; 10/20 deadline 경계 포함 규칙 고정.
- selector/분모: non-overlap은 시각순 outcome-blind이며 N gate에만 사용; M2는 모든 발행 신호 포함; timeout 실패; 방향 정확도와 M2 분리.
- 비용/재현: base/stress 비용 적용, 수수료·spread·slippage 누락 시 실패 종료; 데이터·코드·설정 fingerprint로 동일 입력 재현.

## 7. 판정

이 문서는 **후보 하나를 사전등록**했을 뿐이며, 후보 성과를 시험하거나 M2 결과를 주장하지 않는다. 지금의 결정은 **HOLD / 시험 금지**다. 근거는 taker 필드 실제 결측률 미확인, R018 전체 synthetic gate 미완료, OHLC barrier/cost method gate 미완료, PIT 계약 유니버스·독립 forward boundary·실제 실행 비용 미확정이다.
