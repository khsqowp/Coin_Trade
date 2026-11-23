# R6 코인 사전등록·구현 보고

## 결론

R6-A 8설정과 R6-B 4설정을 성과 결과를 보지 않고 사전등록하고 TRAIN 전용 러너로 구현했다. 전체 unittest 220개가 통과했다. 실데이터 R6 실행은 하지 않았다.

## 등록·trial 분모

- R6 공통 기준은 `bos_origin`, 4시간봉 롱, 48봉 이내 최초 재방문, 목표 2R이다. 불완전 봉은 제외하고 다음 완성봉 시가를 사용한다.
- R6-A는 직전 252개 완성봉의 ATR(14)/종가 경험적 중앙값으로 신호를 낮은/높은 구간으로 분류한다. 손절 여유 0.05/0.20 ATR × 최대 보유 24/48봉, 총 8설정이다.
- R6-B는 재방문 다음 완성 확인봉의 롱 종가 위치 0.60/0.80 × 최대 보유 24/48봉, 총 4설정이다.
- 전체 계획 증가량은 +12회다. 기존 PREREG에 고정된 분모 1,536에 더해 `N_train=1,548`, Bonferroni 단측 기준 `0.05/1548=0.0000322997`로 등록했다. `TRAIN_TRIALS.csv`는 읽거나 고치지 않았으므로 현재 장부 행 수와 실행 직전 실제 분모는 확인하지 않았다. 실행 전에 성과를 열지 않고 실제 누적 시도 수를 확인해 보정해야 한다.
- 두 격자 모두 TRAIN 탐색이다. G 통과·후보 동결·TEST 제출 판정은 하지 않는다.

## 구현 및 경계

- `search_crypto_r6.py`는 `data_access.iter_train_bars`만 사용하고 `resource_guard.heavy_task`로 A와 B를 별도 실행한다. A가 기본값이며 B는 별도 `--experiment R6-B` 인자를 요구한다.
- funding 순서 모호 건은 `adverse_only`를 지정한다. 최소 완성 TRAIN 심볼 수는 30개다. 설정마다 결과를 `round=R6-coin`으로 append한다. 기존 장부 결과 행은 조회하지 않으며, 쓰기 전 CSV 헤더만 스키마 검증에 사용한다.
- 24봉 보유 설정을 위해 `simulate_trade`의 허용 보유기간을 기존 48봉에서 사전등록된 24/48봉으로 확장했다.
- 합성 테스트는 격자 수, ATR 과거표본 경계와 중앙값 동률, 손절·2R 목표, 확인봉 임계값/결측봉, ATR 기준 이력 부족·우측검열 집계, 30심볼 기준, 24봉 시간청산을 검증한다.

## 검증 결과

- R6 합성 단위 테스트: 9개 통과.
- 전체 `tests` unittest: 221개 통과.
- 전체 테스트 중 기존 미국 주식 TRAIN 기준선 테스트가 제한된 실제 TRAIN 표본을 읽어 해시를 대조했다. R6 전략을 실데이터로 실행하지 않았고, TEST 구간과 `TRAIN_TRIALS.csv`를 열지 않았다.
- R6 실제 실행 및 성과: 실행하지 않음. 따라서 수익성·G 기준·데이터 게이트 결과는 확인되지 않았다.

## 정확한 명령

전체 unittest:

```sh
cd /Users/user/CODE/Coin_Trade/scratchpad/strategy_bt/orderblock_loop
/Users/user/CODE/trading_data/cache/orderblock/venv/bin/python -m unittest discover -s tests
```

R6-A 8설정 실행 명령 — 이번 작업에서 실행하지 않음:

```sh
cd /Users/user/CODE/Coin_Trade/scratchpad/strategy_bt/orderblock_loop
nice -n 10 /Users/user/CODE/trading_data/cache/orderblock/venv/bin/python search_crypto_r6.py --experiment R6-A
```

R6-A 장부·완료 확인 뒤 별도 슬롯에서 실행할 R6-B 4설정 명령 — 이번 작업에서 실행하지 않음:

```sh
cd /Users/user/CODE/Coin_Trade/scratchpad/strategy_bt/orderblock_loop
nice -n 10 /Users/user/CODE/trading_data/cache/orderblock/venv/bin/python search_crypto_r6.py --experiment R6-B
```
