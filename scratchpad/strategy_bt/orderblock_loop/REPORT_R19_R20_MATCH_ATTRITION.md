# R19/R20 — R18 매칭 후보 소멸 진단

## 결론

R18의 0건 매칭은 대부분 유니버스 크기나 252봉 이력 부족만으로 설명되지 않는다. 같은 방향·EMA 추세 상태까지 통과한 후보 중, 사건 feature를 계산할 수 있던 206개 BOS에서 R18의 사전고정 caliper를 통과한 후보쌍이 0개였다. 따라서 고정된 비교 조건에서 공통지지가 없었다. 이는 BOS가 예측력이 없다는 증거도, 전략 성과도 아니다. caliper를 완화하거나 R18을 다시 실행하지 않는다.

## 시도 기록

| 시도 | 상태 | 장부 분모 | 결과 |
|---|---:|---:|---|
| R19-coin | 실패 | 1,676 | 데이터 접근과 funnel 계산 뒤 집계에서 `defaultdict` import 누락(NameError). 성과·funnel 수치 미출력. 실패 행 보존. |
| R20-coin | 완료 | 1,677 | 같은 고정 funnel을 import 복구 후 단 1회 실행. 아래의 attrition 집계만 기록. |

R19 장부 행은 `R19-crypto-391fdb3354ab48549f940082b4b8215f`, status `failed`, failure `NameError`. R20의 ledger `round`는 `R20-coin`, status `completed`지만 trial_id 접두사가 `R19-crypto-`로 잘못 생성됐다: `R19-crypto-a5e38277b3b941a38dddbedcead5e843`. append-only 장부는 수정하지 않았다. R20 행은 round, grid/code/prereg hash, fingerprint로 식별한다. 이 ID 결함은 보고·추적 결함이며, 집계값은 수익 성과가 아니므로 합격 후보 판정에는 영향이 없다.

## R20 고정 funnel 결과

자료: 고정 `CRYPTO_35.csv` 35심볼, 4h TRAIN cutoff `2023-11-06T16:00:00Z`; bar가 존재한 심볼 32개; 46개 연속 segment; 원시 BOS 56,447건. TEST/OOS 및 cutoff 이후 데이터는 열지 않았다.

| 순차 필터 | 후보쌍 수 | 후보가 하나 이상 있는 BOS 사건 |
|---|---:|---:|
| 사건·대조 후보 시점 + 이력 조건 | 8,143,860 | 53,112 |
| 같은 양봉/음봉 방향 | 4,055,049 | 53,099 |
| EMA50/200 추세 상태 완전 일치 | 1,324,415 | 30,355 |
| 후보 및 직전 48봉 BOS 없음 | 333 | 206 |
| 사건·대조 feature 계산 가능 | 333 | 206 |
| R18 caliper 통과 | 0 | 0 |
| 시간창 비중첩·control 재사용 금지 greedy 선택 | 0 | 0 |

사건 이력 252봉 충족은 53,382건, 사건 feature와 EMA 상태가 모두 유효한 BOS는 32,792건이었다. 이 두 수치는 원시 56,447건에서 각각 3,065건의 이력 부족, 20,590건의 사건 feature/EMA 누락과 일치한다. 333개의 후보쌍이 feature 계산 단계까지 남았지만 ATR/종가, 최근 6개 log-return 변동성, 상대 거래량의 로그비율 제한(각 ≤ln(1.25)) 및 몸통/ATR 차(≤0.25)를 모두 통과한 쌍이 하나도 없어 greedy 단계 전에 매칭이 종료됐다. 매칭 가능한 비교군의 공통 지지 부족이 확인된 것이다.

**성과 지표는 해당 없음:** 거래 수, M2, 승률, PF, EV, 수익률, MDD, 샤프, 귀무검정은 계산하지 않았다. 신뢰구간이나 전략 G 판정도 없다.

## 재현·장부 대사

R20 재현 명령:

```sh
env TRADING_DATA_DIR=/Users/user/CODE/trading_data \
  PYTHONPATH=scratchpad/strategy_bt/orderblock_loop \
  PYTHONPYCACHEPREFIX=/tmp/cointrade-pycache \
  /opt/anaconda3/bin/python3 \
  scratchpad/strategy_bt/orderblock_loop/search_crypto_r20_match_attrition_repair.py
```

- R19 fingerprint: `37a793c04061836a8c6635e2f61921a392191aa715bfc8a0315176c1bd7b85df`; code SHA `837f8c62a14d1a88f74d6be2c43eda3a90f84ffb790c5edc40e16874f9190cf7`; grid SHA `f9eb71319c3a51f18c92ab21b86978511b520614afa61d3d367ffd248b2891ca`; prereg SHA `e7d0ab6ba87747a16a3bdf5d4df3af7368e264ebaa3013b293eec98065b297a8`; master SHA `08d44a4b9b9ad069134358a03eeecc15ba378ed8e60ae3abd4e01a1d8cdc91e2`.
- R20 fingerprint (same frozen input): `37a793c04061836a8c6635e2f61921a392191aa715bfc8a0315176c1bd7b85df`; code SHA `2e9ef8c3b7acf26fdbe75d34ece5193db7628fd8ef91fa942846e72394b0e203`; grid SHA `47a1aba2a51dc6ef9414641abd89493808a81852c54d303b16146a2e45b731cb`; prereg SHA `55bd8eb655376ca58b4087c8e0a90bd029923150c7be1e429e29f366a8d7d385`; master SHA `49f5ae31cba33eacc867d9f479d4fbba307b98f238148e0fa74a26f704c759c7`.
- 검증: R19 synthetic tests 13/13 통과; 두 Python runner compile 통과; wrapper 점검에서 `R20-coin`, pre-run rows 1,676, N=1,677, R20 prereg 및 공통 잠금 확인. R20 실행 후 장부 1,677행, R19 failed 1행, R20 completed 1행 확인. 장부 writable handle 없음, 공통 잠금 제거됨, 디스크 여유 51 GiB.

## 해석 및 다음 연구

R18의 matching 접근은 조건을 완화해 살릴 수 있는 후보로 취급하지 않는다. 같은 데이터에서 매칭 결과를 보고 caliper를 넓히면 결과 선택 편향을 만든다. 다음 코인 연구는 R14–R17의 비슷한 retest/confirm 변형과 구조적으로 다른 주문블록 가설로 이동하고, 별도 사전등록·기존 G 기준·TEST 분리를 유지해야 한다. G 후보는 0개다.

국장·미장은 이번 R19/R20에서 성과 실험을 하지 않았다. 현재 작업공간의 기존 시장자료 게이트에서 데이터 적격성 문제가 미해결 상태이므로 이 보고서로 주식 전략 후보를 주장하지 않는다.
