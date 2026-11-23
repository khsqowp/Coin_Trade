# R5 equities strategy implementation report

## 결론

R5 E3-J 시장별 동일비중 일별 포트폴리오 곡선을 추가했다. 변경 전 지정 가상환경 전체 테스트는 160개 통과/0개 실패, 변경 후에는 162개 통과/0개 실패다. 실데이터 검색과 TEST 데이터 접근은 없었다.

## 사전등록 범위

- R5 사전등록의 E3-A Supertrend, E3-B Ichimoku, E3-C Keltner squeeze, E3-D RSI4+EMA100, E3-E CCI+MFI, E3-F Williams %R+SMA200, E3-G RSI 상승 다이버전스, E3-H ADX+EMA20 되돌림, E3-I Turnaround Monday, E3-J 6개월 계절성을 구현했다.
- US/KR 각 한 개 고정 규칙, 총 20개 설정이다. 튜닝 격자는 추가하지 않았다.
- 완료 봉 신호와 다음 실제 거래일 시가 체결을 쓴다. 청산 신호는 다음 시가, 정해진 보유기간은 거래일 수로 처리하며 손절과 같은 봉의 기타 청산 조건이 겹치면 손절을 먼저 처리한다.
- 비용은 기존 `equities.py` 산식 그대로 적용한다. US 왕복 20bp, KR 왕복 31bp다.
- R4와 같은 `market,symbol,alive_from,alive_through,source,source_asof` membership 검사, 신호일 생존 판단, `alive_through` 뒤 가격 배제, 거래 종료 시점 생존 누락의 `delisting_gap` 제외를 적용했다. 별도 PIT membership이 없으면 실행이 실패한다.
- TRAIN loader는 R3의 공통 주식 split loader를 호출하고 `2018-10-26T23:59:00Z` 경계를 고정한다. 검색기에는 TEST loader가 없다.
- 공용 `TRAIN_TRIALS.csv` 11열 형식, R5 라운드 표기, PREREG SHA와 관련 코드 파일 묶음의 SHA-256 fingerprint를 기록하는 함수를 구현했다. 이번 테스트는 임시 CSV만 사용했다.

## 구현과 검증

- `search_equities_r5.py`에 CLI(`--universe`, `--membership`, `--split-file`, `--survivors-only`), R4식 membership 로더·생존편향 차단, E3-A~J 신호·거래 시뮬레이션, 비용·지표·장부 기록을 구현했다. E3-J에는 시장별 동일비중 일별 종가 곡선, 최대낙폭, 연환산 Sharpe, 포함 종목·진입 수, `delisting_gap` 집계를 추가했다.
- 합성 검증은 기존 10개 규칙 신호와 비용·PIT·장부 검증에 더해, E3-J 곡선의 손계산 최대낙폭·Sharpe 및 PIT 비적격·`delisting_gap` 종목 제외를 확인한다.
- 지정 전체 명령 결과: 변경 전 **160개 통과, 0개 실패**; 변경 후 **162개 통과, 0개 실패**.

```sh
cd /Users/user/CODE/Coin_Trade/scratchpad/strategy_bt/orderblock_loop
PYTHONPATH=. TRADING_DATA_DIR=/Users/user/CODE/trading_data /Users/user/CODE/trading_data/cache/orderblock/venv/bin/python -m unittest discover -s tests -v
```

## 남은 작업

1. 실데이터 검색은 0회다. 공식 PIT membership의 출처·완전성, OHLC 품질, 상폐 정산가격은 확인하지 않았다. R5 결과는 전부 미판정이며 G 통과나 후보 동결 근거가 아니다.
2. 보수적 구현 해석을 고정했다. E3-G의 두 저점 비교는 최근 20거래일을 앞 10일/뒤 10일로 나눠 가격 저점과 RSI 저점을 비교한다. E3-H는 신호 다음 거래일 고가가 전일 고가를 넘는 것을 종가로 확인한 뒤 그 다음 거래일 시가에 진입한다. 이 해석은 같은 봉 체결과 미래정보 사용을 피한다.
3. E3-J 종목별 행은 유지한다. 별도 `E3-J-portfolio` 행은 시장 공통 11월 첫 관측 거래일 기준으로 종목을 동일비중 편입하고, 다음 거래일 시가부터 5월 첫 관측 거래일까지 종가로 일별 평가한다. 청산 시점까지 membership과 가격을 확인할 수 없는 종목은 곡선에서 제외하고 `delisting_gap`에 센다. 곡선의 MDD와 표본 표준편차(ddof=1)를 쓴 연환산 Sharpe를 계산한다.
4. E3-E는 MFI 계산에 실제 거래량 열이 필요하다. 거래량 열이 없으면 대체값을 만들지 않고 실행을 중단한다.
5. 구현 파일의 독립 `py_compile`은 시스템 Python으로 실행했을 때 캐시 경로 쓰기 권한 오류가 났다. 지정 가상환경의 전체 unittest는 해당 모듈을 import해 실행했고 변경 후 162개 전부 통과했다.
6. 실행 중 공유 `TRAIN_TRIALS.csv`에 본 R5 테스트와 무관한 R3-coin 행 48개 추가 diff가 관찰됐다. 내용을 복원하거나 수정하지 않았다. 추가 주체는 이 세션에서 확인되지 않았다.

## 정확한 실행 명령

합성·회귀 테스트에 실제 사용한 명령은 아래와 같다. US/KR 실데이터 명령은 실행하지 않았다.

```sh
cd /Users/user/CODE/Coin_Trade/scratchpad/strategy_bt/orderblock_loop
PYTHONPATH=. TRADING_DATA_DIR=/Users/user/CODE/trading_data /Users/user/CODE/trading_data/cache/orderblock/venv/bin/python -m unittest discover -s tests -v
```

**2026-11-23 수정**: 위 US/KR 명령에 쓰려던 `equity_membership_r4.csv`/`equity_splits_r4.json`은 존재하지 않는다(생성된 적 없음, R2/R3 선례처럼 `--split-file`은 처음 실행 시 새로 만들어지는 캐시 경로일 뿐 사전 준비 파일이 아니다). 미국은 아직 membership 파일이 없어 실행 불가다. 한국만, R4/R5 KR market 라벨 정규화(PREREG addendum, 2026-11-23) 적용 후 실제로 쓸 명령은:

```sh
cd /Users/user/CODE/Coin_Trade/scratchpad/strategy_bt/orderblock_loop
PYTHONPATH=. TRADING_DATA_DIR=/Users/user/CODE/trading_data /Users/user/CODE/trading_data/cache/orderblock/venv/bin/python search_equities_r5.py --universe universe/KR.csv --membership /Users/user/CODE/trading_data/cache/orderblock/equity_membership_kr.csv --split-file /Users/user/CODE/trading_data/cache/orderblock/equity_splits_r5.json --survivors-only
```

(R4의 동일 KR 명령은 `search_equities_r4.py`로, 같은 `--membership`/신규 `--split-file`을 쓴다.) 이 명령은 이번 세션에서 실행하지 않았다; 실행은 별도 자원 게이트(단일 heavy slot, nice -n 10)를 쥔 쪽이 한다.

## 소요시간 추정 (실측 아님)

R2 US TRAIN 실측값(STATUS.md, 2026-11-22T15:14Z)을 기준으로 외삽했다: 68개 설정 × 유효 194종목 ≈ 13,192 설정×종목 단위가 약 9분 걸렸다(≈0.041초/단위, nice -n 10 조건 포함). R5 KR은 10개 설정 × 557종목 ≈ 5,570단위로, 같은 처리율이면 **약 3.8분**이다. 다만 R5 지표(Ichimoku/Supertrend/CCI+MFI/divergence 등)는 R2의 단순 lookback/retest보다 봉당 계산량이 많고, KR 종목당 TRAIN 행수(중앙값 2,786)가 R2 당시 US 유효종목 평균보다 많을 수 있어, 실제로는 **약 4~10분** 범위로 본다. 선형 외삽이며 실측 벤치마크는 아니다.

`search_equities_r5.py --survivors-only` already uses the same `survivorship_biased=true` and `status=TRAIN_ONLY_NOT_G` labeled-fallback convention as R4 (R4b), so no second flag was needed. The US/KR commands above are documented only and were not executed.

## E3-J 감사 (2026-11-23, read-only, 코드 수정 없음, TEST 미접근)

피어 세션 요청으로 `TRAIN_TRIALS.csv`에 이미 기록된 KR E3-J 최신 행(timestamp 2026-11-23T01:58:20Z, PF=1.73, expectancy_net_bps=+1069.25, trades=4446, quality_excl=43/558)을 대상으로 룩어헤드·포트폴리오 집계·비용 차감·생존편향을 코드 레벨로 점검했다. 결과 열람은 이 숫자뿐이며 신규 실행·TEST 접근 없음.

1. **룩어헤드 — 문제 없음.** `_signal`의 E3-J 진입조건(`search_equities_r5.py:289`)은 당일 봉 자체의 월(11월)만 보고, 전일 봉이 11월이 아니었는지로 "그 달 첫 거래일"을 판정한다. 둘 다 해당 봉 종가 시점에 이미 알 수 있는 정보다. `simulate_e3`(269행대)에서 신호 봉 i의 다음 봉(entry_i=i+1) 시가로 진입한다. 청산도 `bars[j]`를 스캔해 "익년 5월 첫주(day<=7)"인 거래일을 찾은 뒤(342~351행) 그 다음 거래일(exit_signal+1) 시가로 체결한다. 신호→진입, 신호→청산 모두 next-bar-open 규칙(PREREG §2)을 지키고 있어 미래가격 참조 없음.

2. **비용 차감 — 불일치 발견 (중간 심각도).** 종목별 거래 성과(`_metrics`, PF 1.73·+1069bp가 나오는 경로)는 `simulate_e3` 396~399행에서 `net = gross - cost/10_000`으로 `preregistered_costs(market)` 기반 비용을 매 거래마다 뺀다 — 이 숫자는 비용 포함 net이 맞다. 그런데 **`E3-J-portfolio` 행(동일비중 Sharpe/MDD, 413~480행)은 비용을 전혀 반영하지 않는다** — `_e3j_portfolio_metrics` 안에 `cost` 관련 연산이 없다. 종목 단위 PF/expectancy는 net인데 포트폴리오 단위 Sharpe/MDD는 gross라서, 같은 전략의 두 지표 집합이 비용 처리 기준이 다르다. 포트폴리오 Sharpe는 실제보다 높게, MDD는 실제보다 얕게 나올 것으로 추정한다 (연 2회 리밸런싱이라 절대 영향은 크지 않겠지만 숫자 불일치 자체가 문제).

3. **생존편향 — 프로젝트 기존 관행과 동일, 신규 결함 아님.** `survivorship_safe_trades`(73~85행, 종목별)와 `_e3j_portfolio_metrics`의 코호트 선정(437~446행, 포트폴리오)은 둘 다 "진입일+청산일 모두 alive"를 요구하고, 청산일에 생존 확인이 안 되면 거래/코호트를 완전히 제외하며 `delisting_gap`에만 센다. 상폐 중 정산가로 마킹하지 않고 통째로 빼는 방식은 R2~R4에서도 동일하게 쓰인 프로젝트 전역 관행(PREREG §2 fail-closed 원칙)이라 E3-J만의 결함은 아니다. 다만 이 관행 때문에 포트폴리오 MDD는 보유기간 중 상장폐지로 인한 꼬리 손실을 전혀 반영하지 못한다는 한계는 이 숫자에도 그대로 적용된다는 점을 기록해둔다.

4. **평가 구간 1영업일 불일치 (경미).** 종목별 거래는 "5월 첫주 신호일+1 거래일 시가"에 실제로 청산 체결한다(351행). 그런데 포트폴리오 곡선(453행 `market_days[entry_pos:may_pos+1]`)은 신호일(may_pos) 당일 **종가**까지만 평가하고 멈춘다 — 그 다음 거래일 체결가까지 곡선을 끌고 가지 않는다. 즉 종목별 "실제 청산 체결일"과 포트폴리오 곡선의 "마지막 마킹일"이 하루 어긋난다. 미래정보 사용은 아니지만(둘 다 알 수 있는 날의 가격만 사용), 두 보고 숫자가 서로 다른 날짜 기준이라는 점은 명확히 할 필요가 있다.

**결론**: PF 1.73 / +1069bp(종목별 net 지표)는 신호·진입·청산 타이밍과 비용 처리 모두 문제없이 재현 가능한 숫자로 판단한다. 다만 같은 E3-J-portfolio 행의 Sharpe/MDD는 비용 미반영으로 종목별 지표와 기준이 다르므로 **그 두 숫자만 따로 떼어 비교·인용하지 않을 것**을 권고한다. 코드 수정은 하지 않았다(감사 요청 범위가 점검이었고, 수정이 필요하면 PREREG 선등록 후 별도 승인 라운드에서 진행).
