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

## KR 실행 결과 거래종목 5% 원인 진단 (2026-11-23, read-only, TEST 미접근)

리눅스 투자 세션이 실제 KR R4 survivors-only 실행 결과(C1 주봉 최고 85건/28~29종목)가 R2 KR과 동일했던 이상을 보고해, `_daily_bars`/`filter_equity_bars`/`_weekly_bars`를 직접 호출해 단계별로 계측했다(전략 신호 코드는 호출하지 않음, TRAIN 로더만 사용, TEST 미접근).

**결론: 버그는 search_equities_r4.py/r5.py나 data_quality.py에 없다. 원인은 `external/equities/kr/daily_stocks_delisted.parquet`의 가격 데이터 자체에 있는 두 가지 체계적 패턴이, 기존(R2에서 확정된) 품질 임계값(`MAX_BAD_ROW_FRACTION=0.05`, `MAX_CONSECUTIVE_BAD_ROWS=3`)에 걸려 KR 유니버스 558개 중 529개(94.8%)를 `quality_excluded`로 만든다.** 이는 전략 신호 이전 단계에서 결정되며, 신호 조건과 무관하다.

단계별 계측(universe/KR.csv 558행, 신호 코드 미호출):
- 로딩 실패(`other_error`/loader 형식 문제): **0건** — symbol 포맷(알파뉴메릭 코드 포함)이 로더 실패 원인이 아님을 확인(질문 d 답).
- `quality_excluded`: **529/558 (94.8%)** — 압도적 1차 원인(질문 b 답).
- 품질 필터를 통과한 29개 전부 TRAIN 가격을 가졌고 전부 완전 주봉을 형성했다(최소 84개 주봉, 최소 530 일봉). 즉 TRAIN 일봉 보유 종목 수(557/558)와 "품질 필터 통과 후" 종목 수(29) 사이의 528개 차이가 바로 `quality_excluded`다 — 주봉 변환(월~금 완전주 요구) 단계는 29개 생존 종목 전부를 그대로 통과시켰고 탈락을 일으키지 않았다(질문 a 답). 신호 조건(C1 breakout 등)은 이 29개에게만 적용되므로, 85건/28~29종목이 R2와 "거의 같은" 것은 당연한 결과다 — R2/R4가 같은 528개 탈락 종목 집합에서 출발하기 때문이다(질문 e 답: 데이터 단계 탈락, 신호 단계 아님).
- 529개 중 360개는 전체 invalid-OHLC 비율이 5%를 넘었고, 169개는 비율은 5% 미만이지만 연속 3행 이상 불일치 구간이 있어 탈락했다(질문 b 상세).
- 종목당 TRAIN 행수(생존 29개 기준): 최소 530 / 중앙값 1,553 / 최대 2,963 — 이전에 보고한 "전체 558개 중앙값 2,786"보다 낮다. 생존이 "데이터 깨끗함"보다 "TRAIN 구간 전체를 덮지 않는 상장"과도 섞여 있을 수 있다는 뜻으로, 해석에 주의가 필요하다(질문 c 답, 완전한 설명은 아님).

**불일치 행의 실제 내용 (표본 7개 심볼 직접 열람, 가격 자체만 확인, 전략/TEST 무관):**
1. 제로가격 구간(진짜 거래정지로 보임): 예 `000360`은 2012-07-16~2013-01-17 사이에 간헐적으로 OHLC가 전부 0인 행이 있다(해당 심볼 71행). 이는 `filter_equity_bars`가 거래량 0 연속구간(halt)으로 잡는 경로가 아니라 가격 0으로 `invalid_ohlc`에 집계된다 — 분류 라벨은 부정확하지만("halt"가 아니라 "invalid_ohlc"로 찍힘), 심볼을 보수적으로 배제하는 결론 자체는 아마 맞다.
2. **체계적 1원(1 tick) 종가>고가 불일치**: `000360`/`000365`/`000420`/`000425`/`000685`에서 close>high인 비(非)제로 행은 전부 예외 없이 `close - high == 1`(표준편차 0, 여러 심볼 수백 건 표본 전부 동일)이다. close<low 방향 불일치는 같은 심볼에서 0건이었다. 이는 무작위 오염이 아니라 원가/조정가 계산 또는 가격제한(상한가) 라운딩에서 발생하는 **결정론적 1틱 오차**로 보인다. 이 패턴이 360+169개 탈락의 다수를 설명할 가능성이 높다(정확한 분담 비율은 미산출).

**이것을 "버그"로 보고 지금 고칠지는 데이터 소유자/사용자 판단이 필요해 보여 코드 수정은 하지 않았다.** 근거: (i) R2 US에서는 이런 대량 탈락이 없었다(US 487 중 유효 194, empty_train 293 — quality_excluded 사유가 아니었다). 즉 품질 임계값 자체는 US에서 이미 통용되는 값이고, KR 쪽 원본 parquet만 특이하다. (ii) 1틱 close>high 패턴은 전략/실행기 버그가 아니라 `daily_stocks_delisted.parquet` 생성 파이프라인(조정가 라운딩 등)의 문제로 보인다 — 이 세션은 그 파이프라인 코드를 찾지도, 고치지도 않았다. (iii) 품질 임계값을 그냥 완화하면(예: close<=high*1.0001 허용) 진짜 나쁜 데이터(제로가격 장기 정지 구간 등)도 같이 통과시킬 위험이 있어, 결과를 보기 전 사전등록 없이 임의로 느슨하게 바꾸면 안 된다.

제안(결정 필요, 코드 변경 전): (a) 1틱 한도 내 close/high·close/low 불일치만 "참값과 동일"로 간주하는 별도의 사전등록된 허용오차 규칙을 `data_quality.py`에 추가하고 제로가격/큰 불일치는 그대로 배제, 또는 (b) KR 29종목 생존 결과를 일단 "생존편향+데이터편향 이중 경고"로 명시한 채 참고용으로만 쓰고 `daily_stocks_delisted.parquet` 자체를 재생성(원본 소스 재조사)하는 걸 우선하거나, (c) 현재 상태(29종목)로도 TRAIN 탐색은 계속하되 보고서에 "558개 중 29개만 평가됨"을 모든 KR R4/R5 결과에 고정 각주로 남긴다. 이 셋 중 하나를 결정 전 선택해야 PREREG addendum을 쓰고 Codex로 구현할 수 있다.
