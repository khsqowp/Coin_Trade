# R4 Strategy Design — build status

## 결론

R4 실행기 구현은 완료됐고, 실데이터 검색은 0회다. runner는 C1 32개(시장×16)와 E2 12개(시장×6) 설정을 계산하고 설정별 공용 장부 행을 기록한다. 코인 변형 3개는 본 주식 검색기 범위 밖이다. TEST는 미열람이다.

## 사전등록 범위

- C1 주봉: US/KR 각각 lookback 2 × retest 2 × 목표 2 × 보유 2, 총 16 설정/시장, 32 설정 합계.
- 신규 아카이브 파생 가설: Donchian 돌파 2종, 모멘텀 1종, Bollinger 평균회귀 1종, 주봉 SMA 되돌림 1종, 변동성 수축 돌파 1종. US/KR 각 6개, 12 설정.
- ERRATA 파생 코인 아이디어: 변위봉/OB 경계 분리, BOS 기원 블록만 사용, 거래량 확인 변위와 결측 funding fail-closed. 코인 자료 접근 및 실행은 이 산출물 범위가 아니다.
- 사전등록 계획 총량은 44개 설정이다. 실패·미산출도 실제 검색 시도 장부에서 빼지 않는다.

## 생존편향·PIT 정책

R4 membership CSV는 `market,symbol,alive_from,alive_through,source,source_asof`를 요구한다. alive 날짜 양끝을 포함해 신호일 자격을 판단하고, 거래 종료가 상폐/거래 종료일 뒤로 넘어가며 공식 청산가격이 확인되지 않으면 `delisting_gap`으로 세어 성과에서 제외하도록 합성 단위 경계를 구현했다. 상폐 뒤 가격 사용은 금지한다. 기존 US/KR proxy universe에는 공식 시점별 편입/상장 상태가 없으며, 실제 PIT 자료의 가용성·완전성은 확인하지 않았다. 따라서 해당 파일만으로는 검색 실행이 정당화되지 않는다.

현재 실행기 입력 형식 검사에는 공식 출처의 진위를 판정하는 기계적 증거가 없다. 파일의 `source` 텍스트만으로 PIT가 증명되지 않는다. 검색 전에 담당자가 출처와 커버리지를 검증하고 데이터 무결성 hash를 고정해야 한다.

## 구현과 검증

- `search_equities_r4.py`: 16셀 C1 grid, E2-A~F 규칙, 다음 거래일 시가 체결, US/KR 비용, PIT membership 필수 검사, TRAIN 전용 cutoff loader, 11열 공용 장부와 코드 SHA 기록.
- E2-A 시간 청산은 20일차 종가 확정 뒤 다음 거래일 시가로 체결한다. 장벽이 같은 봉에서 겹치면 stop 우선이다.
- `tests/test_search_equities_r4.py`: 여섯 E2 후보 합성 입력, C1 grid, membership schema/기간, delisting-gap 경계를 검증.
- 지정 venv 전체 unittest 명령 결과: 테스트 147개 통과, 실패 0개.
- 최종 코드 변경 후 전체 테스트 재실행: 테스트 147개 통과, 실패 0개. 임시 CSV로 공용 11열 schema와 코드 SHA 기록도 검증했다.
- 최초 테스트 호출은 `PYTHONPATH` 누락으로 import 오류 1건. 수정된 명령은 정상 통과했다.
- 실데이터 검색, TEST 접근, 코인 검색: 실행 안 함.

## 남은 작업·제한

1. PIT 출처 검증, 등록상태 데이터 완전성, 상폐 청산가/가격 공백의 실제 감사는 확인 안 됨이다. 공식 PIT 자료 검증 전 실검색은 정당화되지 않는다.
2. `--survivors-only`는 필수 PIT membership 실행에 생존 종목만의 비교 결과를 추가한다. 비교 결과는 `survivorship_biased=true`로 표시되며 G에 쓰면 안 된다.
3. 전체 G 검정, 무작위 귀무, plateau, 스트레스, 레드팀 및 동결은 실행하지 않았다.
4. `source` 문자열과 `source_asof`는 공식 원천의 진위를 증명하지 못한다. 별도 출처·커버리지 확인이 필요하다.

## 정확한 실행 명령 (준비 후 TRAIN 전용)

첫 명령은 이번 구현 검증에서 실제 실행했다. US/KR 명령은 공식 PIT membership 및 입력 검증 뒤에만 실행할 수 있으며 이번 세션에서는 실행하지 않았다. 코인은 포함하지 않는다.

```sh
cd /Users/user/CODE/Coin_Trade/scratchpad/strategy_bt/orderblock_loop
PYTHONPATH=. TRADING_DATA_DIR=/Users/user/CODE/trading_data /Users/user/CODE/trading_data/cache/orderblock/venv/bin/python -m unittest discover -s tests -v
PYTHONPATH=. TRADING_DATA_DIR=/Users/user/CODE/trading_data /Users/user/CODE/trading_data/cache/orderblock/venv/bin/python search_equities_r4.py --universe universe/US.csv --membership /Users/user/CODE/trading_data/cache/orderblock/equity_membership_r4.csv --split-file /Users/user/CODE/trading_data/cache/orderblock/equity_splits_r4.json --survivors-only
PYTHONPATH=. TRADING_DATA_DIR=/Users/user/CODE/trading_data /Users/user/CODE/trading_data/cache/orderblock/venv/bin/python search_equities_r4.py --universe universe/KR.csv --membership /Users/user/CODE/trading_data/cache/orderblock/equity_membership_r4.csv --split-file /Users/user/CODE/trading_data/cache/orderblock/equity_splits_r4.json --survivors-only
```

위 US/KR 명령은 실행되지 않았다. 완료 범위는 규칙 구현, 장부 기록 코드, 합성 테스트와 전체 테스트다. `TRAIN_TRIALS.csv`에는 실제 R4 실행행을 추가하지 않았다. survivors-only 결과는 보조 표기이며 G 수치로 사용하지 않는다.
