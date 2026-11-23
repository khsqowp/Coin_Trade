# R7 코인 오더블록 사전등록·구현 보고

## 결론

R7 신규 가설 1개를 PREREG addendum에 등록하고 TRAIN 전용 러너와 합성 테스트를 추가했다. 실데이터 실행과 TEST 열람은 하지 않았다. R7은 성과·독립성 미검증이다.

## 등록 내용

- 가설: BTC 4h 종가가 SMA(150) 위이고 SMA(150)가 24개 4h 봉 전보다 높을 때, 알트코인 4h 롱 `bos_origin` 오더블록 첫 재방문만 거래한다.
- 설정: 1개 고정. 48봉 재방문 기한, ATR(14)×0.10 손절 여유, 2R 목표, 48봉 보유, `adverse_only`, TRAIN 전용.
- R3/R4 중복 검토: 같은 심볼/신호봉 중복률, ±1개 4h 봉 진입 근접률 및 일별 순손익 상관을 비교한다. 공통일 60일 미만은 미판정, |상관|≥0.5 또는 신호중복≥50%이면 독립 후보로 세지 않는다.
- 장부 기준은 `csv.field_size_limit(sys.maxsize)`를 설정해 행 수만 센 결과 1,530이었다. R7 계획 1회 포함 N=1,531, Bonferroni 기준 0.0000326584. 실행 전 변경분은 성과 결과를 열기 전에 행 수만으로 갱신한다.
- G의 공통 기준은 그대로 유지하고, 이번 요청대로 R7 기대값은 더 엄격한 ≥30bp를 적용한다. 동결 또는 G 통과로 해석하지 않는다.

## 파일

- `PREREG.md`: R7 가설, 단일 설정, 누적 분모, 판정 및 R3/R4 독립성 검토 계획.
- `search_crypto_r7.py`: R6 러너 구조를 바탕으로 한 BTC 레짐 필터, TRAIN 로더, `heavy_task`, adverse-only 및 `round=R7-coin` 장부 기록.
- `tests/test_search_crypto_r7.py`: 고정 설정, 인과적 SMA, 시각 정렬, 레짐 OFF 필터 합성 테스트.

## 명령

작업 디렉터리에서 합성 단위 테스트 및 전체 테스트:

```sh
/Users/user/CODE/trading_data/cache/orderblock/venv/bin/python -m unittest tests.test_search_crypto_r7 -v
/Users/user/CODE/trading_data/cache/orderblock/venv/bin/python -m unittest discover -s tests -v
```

실데이터 실행 명령은 기록만 하며 이번 작업에서 실행하지 않았다:

```sh
cd /Users/user/CODE/Coin_Trade/scratchpad/strategy_bt/orderblock_loop && /Users/user/CODE/trading_data/cache/orderblock/venv/bin/python search_crypto_r7.py --experiment R7-BTC-REGIME
```

위 실데이터 명령은 TRAIN을 읽고 `TRAIN_TRIALS.csv`에 append하므로 별도 실행 승인과 실행 직전 자원·장부 점검이 필요하다. TEST 경로는 구현하지 않았다.

## 검증 상태

- 실데이터 백테스트: 실행하지 않음.
- TEST/OOS: 열람하지 않음.
- R3/R4 신호 중복·상관: 확인하지 않음. 위 절차는 계획이며 계산 결과가 아니다.
- 합성 테스트: 4개 통과.
- 전체 unittest: 225개 통과 (`Ran 225 tests ... OK`).
- 커밋: 하지 않음.
