# 다음 사전등록 실행 명령 (가격 품질 addendum 적용 후)

실행 위치는 `/Users/user/CODE/Coin_Trade/scratchpad/strategy_bt/orderblock_loop`이며, 지정 Python은 `/Users/user/CODE/trading_data/cache/orderblock/venv/bin/python`이다. 아래 명령은 총괄 전용 실데이터 실행 안내다. 이 변경 세션에서는 실행하지 않는다.

```sh
TRADING_DATA_DIR=/Users/user/CODE/trading_data PYTHONPATH=. /Users/user/CODE/trading_data/cache/orderblock/venv/bin/python search_equities.py --universe universe/US.csv --splits /Users/user/CODE/trading_data/cache/orderblock/equity_splits_r2.json
TRADING_DATA_DIR=/Users/user/CODE/trading_data PYTHONPATH=. /Users/user/CODE/trading_data/cache/orderblock/venv/bin/python search_equities.py --universe universe/KR.csv --splits /Users/user/CODE/trading_data/cache/orderblock/equity_splits_r2.json
TRADING_DATA_DIR=/Users/user/CODE/trading_data PYTHONPATH=. /Users/user/CODE/trading_data/cache/orderblock/venv/bin/python search_equities_r3.py --universe universe/US.csv --split-file /Users/user/CODE/trading_data/cache/orderblock/equity_splits_r3.json
TRADING_DATA_DIR=/Users/user/CODE/trading_data PYTHONPATH=. /Users/user/CODE/trading_data/cache/orderblock/venv/bin/python search_equities_r3.py --universe universe/KR.csv --split-file /Users/user/CODE/trading_data/cache/orderblock/equity_splits_r3.json
```

예상 장부 시도는 R2 68×2=136회, R3 24×2=48회, 합계 184회다. 전체 예상 소요시간은 계획치 5~15분이며 데이터 읽기 속도에 따라 달라진다. 실측 실행시간·품질 제외 종목 수·시장별 잔여 종목 수는 총괄 실행 전까지 확인 안 됨이다.

# R2 Role C — 미국·한국 주식 TRAIN 결과

## 1. 결론

**훈련 탐색은 완료했지만 후보 동결·TEST 제출은 할 수 없다. TEST 제출 후보는 0개다.** 최신 기록은 시장별 68개 설정이다. 숫자는 TRAIN 관찰치이며, 상폐·PIT 결손과 OHLC 오류 때문에 시장 전체 성과로 해석하면 안 된다.

## 2. 생존편향·데이터 품질 — 모든 표보다 먼저 확인

- **생존편향: 두 시장 모두 PRESENT/UNKNOWN.** 고정 유니버스는 공식 시점별 전체 구성종목을 보장하지 않는다.
- **KR:** 4,229개 상폐 중 3,039개(71.86%, 약 71.9%)에 가격자료가 없다. 입력 가격이 있는 558개도 각 설정에서 `data_errors=553`을 기록했다. 실행 중 관측된 오류는 `bar OHLC values are inconsistent`였다. 따라서 상위 KR 지표는 시장 전체를 대표하지 않는다.
- **US:** 고정 심볼 487개 중 293개는 2018-10-26까지 훈련 가격이 없어 `empty train window`로 오류 처리됐다. 194개만 신호 계산에 들어갔다. 미국 목록도 공식 PIT 구성 및 상폐 가격 완전성이 확인된 유니버스가 아니다.
- 오류 종목의 가격을 보정하거나 성공 행으로 바꾸지 않았다. 오류는 각 설정의 장부에 남겼다.

## 3. 실행 범위·장부

| 구분 | US | KR | 합계 |
|---|---:|---:|---:|
| 고정 유니버스 | 487 | 558 | 1,045 |
| 최신 코드 기록 TRAIN 격자 | 68 | 68 | 136 |
| R2 주식 시도 행 누적 | 204 | 136 | 340 |
| 설정당 데이터 오류 | 293 | 553 | — |
| TEST 제출 후보 | 0 | 0 | 0 |

- 공통 훈련 경계는 **2018-10-26 포함**이다. 최종 실행은 `end_ms=EQUITY_COMMON_SPLIT_MS`를 로더에 넘겨 Parquet 읽기 조건 자체를 경계에서 자른다. 최종 136행은 TEST 기간 자료를 요청하지 않았다.
- 최종 장부 시각: US `2026-11-22T14:18:52.869470+00:00`, KR `2026-11-22T14:19:11.797079+00:00`. 장부에 기록된 소스 해시는 `94b54512aa6e3075720ecb2237c4d9927c01f23bab8997e3a6a1069034159e9b`다.
- 현재 파일 해시는 `87003fd34f53c4be7f101fff12a800fdd582a63b14bc4efa22e2100dca9f9273`로 장부 실행 해시와 다르다. 실행 당시 소스 스냅샷을 보관하지 못해 **정확한 소스 재현 가능성은 확인 안 됨**이다. 아래 수치는 최신 `TRAIN_TRIALS.csv`에 직접 기록된 실측 행이다. 소스 해시 차이도 후보 동결을 막는 사유다.
- 전체 `TRAIN_TRIALS.csv`에는 data 행 493개가 있다. 기존 코인 실패 153행과 주식 시도 340행을 모두 보존했다. 누적 `N_train=493`이며 실패·무효 기록도 시도 수에서 제외하지 않았다.
- 무효 실행 136행(US 68, KR 68; `2026-11-22T13:57:45Z`~`13:58:04Z`)은 로더가 TEST 행을 내부에서 먼저 읽은 뒤 TRAIN만 반환했다. 해당 결과는 장부에서 삭제하지 않고 후보 선정·성과 표에서 제외했다. `ERRATA.md`에 이유를 적었다.
- 그 뒤 US만 실행한 구버전 MDD 68행도 장부에 남겼다. 표는 최신 동일 해시 실행 136행만 사용했다.
- 공유 heavy lock은 생성 후 제거했다. `os.nice(10)`은 `PermissionError: Operation not permitted`, `RLIMIT_AS`는 `ValueError: current limit exceeds maximum limit`로 설정되지 않았다. 스크립트의 종목 단위 3GiB RSS 검사로 진행했고 초과 중단은 없었다. 실제 최대 RSS 값은 출력하지 않아 **확인 안 됨**이다.

## 4. 시장별 상위 10개 TRAIN 행

비용 차감 거래별 승률과 Wilson 95% 하한을 표시했다. MDD는 최신 검색기의 일일 평가손익 기준이다. 훈련 상위 순위는 G 통과나 미래 성과를 뜻하지 않는다.

### 미국

|순위|설정|거래수|승률|Wilson 95% 하한|손익비|PF|기대값 bp|MDD %|
|---:|---|---:|---:|---:|---:|---:|---:|---:|
|1|C1 weekly · lookback 10 · retest 20 · R 3 · 보유 40|3702|36.63%|35.09%|2.69|1.55|268.4|5.16%|
|2|C1 weekly · lookback 10 · retest 10 · R 3 · 보유 40|3922|35.90%|34.41%|2.74|1.54|256.2|4.80%|
|3|C1 weekly · lookback 10 · retest 20 · R 3 · 보유 20|3791|39.12%|37.58%|2.27|1.46|201.7|4.90%|
|4|C1 weekly · lookback 20 · retest 10 · R 3 · 보유 40|2987|33.65%|31.97%|2.73|1.38|184.4|3.68%|
|5|C1 weekly · lookback 10 · retest 10 · R 3 · 보유 20|4031|38.28%|36.79%|2.29|1.42|183.0|5.00%|
|6|C1 weekly · lookback 20 · retest 20 · R 3 · 보유 40|2834|33.94%|32.22%|2.66|1.37|180.3|3.92%|
|7|C1 weekly · lookback 10 · retest 20 · R 2 · 보유 40|3898|42.12%|40.58%|1.90|1.39|171.8|4.79%|
|8|C1 weekly · lookback 10 · retest 10 · R 2 · 보유 40|4149|41.29%|39.80%|1.92|1.35|154.4|4.94%|
|9|C1 weekly · lookback 10 · retest 20 · R 2 · 보유 20|3953|43.08%|41.54%|1.75|1.32|135.1|4.73%|
|10|C1 weekly · lookback 10 · retest 10 · R 2 · 보유 20|4202|42.15%|40.66%|1.77|1.29|121.0|4.83%|

### 한국

|순위|설정|거래수|승률|Wilson 95% 하한|손익비|PF|기대값 bp|MDD %|
|---:|---|---:|---:|---:|---:|---:|---:|---:|
|1|C1 weekly · lookback 10 · retest 20 · R 3 · 보유 20|22|40.91%|23.26%|2.60|1.80|567.9|0.14%|
|2|C1 weekly · lookback 10 · retest 10 · R 3 · 보유 20|23|39.13%|22.16%|2.65|1.71|504.3|0.12%|
|3|C1 weekly · lookback 10 · retest 10 · R 3 · 보유 40|23|39.13%|22.16%|2.51|1.61|463.9|0.12%|
|4|C1 weekly · lookback 10 · retest 20 · R 3 · 보유 40|22|40.91%|23.26%|2.23|1.55|449.7|0.16%|
|5|C3 daily · lookback 126 · stop ATR 3 · R 3 · 보유 40|57|43.86%|31.77%|1.91|1.49|402.2|0.19%|
|6|C1 weekly · lookback 10 · retest 20 · R 2 · 보유 20|22|50.00%|30.72%|1.60|1.60|391.2|0.13%|
|7|C1 weekly · lookback 10 · retest 10 · R 2 · 보유 20|23|47.83%|29.24%|1.65|1.51|335.2|0.12%|
|8|C1 weekly · lookback 10 · retest 10 · R 2 · 보유 40|23|47.83%|29.24%|1.65|1.51|335.2|0.12%|
|9|C1 weekly · lookback 10 · retest 20 · R 2 · 보유 40|22|50.00%|30.72%|1.44|1.44|315.2|0.13%|
|10|C1 weekly · lookback 20 · retest 20 · R 2 · 보유 20|8|50.00%|21.52%|1.44|1.44|292.1|0.08%|

## 5. 동결·검증 상태

- `FROZEN_R2.md`에는 시장별 상위 최대 3개를 **동결 제안**이라고 명시했다. 정식 동결은 0건이다.
- `N_test=0`, TEST 채점 0회다. 무작위 진입, 순환이동, 다중검정 보정, Reality Check/SPA, Deflated Sharpe, plateau, 약세장, 비용 2배, 1봉 지연, 수익 집중도, 레드팀 독립 검증을 이번 역할에서 하지 않았다. 모두 **확인 안 됨**이며 G 통과가 아니다.
- 2026-06-01 이후 데이터는 최종 TRAIN 읽기 상한에서 제외했다. 별도 접근 로그는 **확인 안 됨**이다.
- 지정한 Python 실행 파일만 사용했다. 전체 테스트 85개는 이번 작업에서 재실행하지 않았다. 코드 변경 후 통과 여부는 **확인 안 됨**이다.

## 6. 변경 파일

- `search_equities.py`: 시장별 실행은 해당 시장의 68행만 기록하고, TRAIN 읽기 상한을 2018-10-26으로 제한한다. 기록 행 수 반환도 시장별 호출 수에 맞춘다.
- R2/R3 split cache는 저장소 외부 `/Users/user/CODE/trading_data/cache/orderblock/`에 분리 저장한다. 두 실행기의 기본값은 각각 `equity_splits_r2.json`, `equity_splits_r3.json`이며 `TRADING_DATA_DIR`로 기준 경로를 바꿀 수 있다. R2는 TRAIN 원행 fingerprint 및 invalid/empty/error 심볼 accounting을 metric에 기록하고, optional `complete`를 보존해 trailing incomplete 행을 주봉 형성 전에 제외한다. 이 문서 갱신은 이전 장부를 수정하거나 실데이터 재실행을 뜻하지 않는다.
- `TRAIN_TRIALS.csv`: 과거 행을 보존하고 주식 탐색 340행을 누적했다.
- `REPORT_R2_C.md`, `ERRATA.md`, `FROZEN_R2.md`, `STATUS.md`: 실측치, 데이터 결함, 무효 실행, 제안 후보 및 미확인 항목을 기록했다.
- Python 경로: `/Users/user/CODE/trading_data/cache/orderblock/venv/bin/python`. 테스트 실행: 안 함.

## 7. 2026-11-22 미국 R2 실측 추가 — TRAIN 전용, 현재 후보 아님

미국 R2의 등록된 68개 설정을 실제로 실행해 `TRAIN_TRIALS.csv`에 68행을 추가했다. 실행 약 9분, 그 시점 누적 `N_train=637`이다. 68행은 모두 market=US/R2이며 코드 해시 하나와 TRAIN 데이터 fingerprint 하나로 일치한다.

| 항목 | 실제 값 |
|---|---:|
| 유니버스 입력 / TRAIN 유효 | 487 / 194 종목 |
| TRAIN 비어 있음 / 품질 제외 / 로더 오류 / 처리 오류 | 293 / 0 / 0 / 0 종목 |
| 0 거래량 구간 제거 행 | 2,145 |
| 최고 TRAIN 탐색 설정 | C1 주간, lookback 10, retest 20, 목표 3R, 최대보유 40주 |
| 최고 TRAIN 거래 수 / 승률 / PF | 3,700 / 36.62% / 1.554 |
| 최고 TRAIN 거래당 순기대값 / 일간 mark-to-market MDD | +268.03bp / 5.17% |
| 실행 code SHA-256 / TRAIN fingerprint | `805b0a4e0d885a3c7952c236de85cbb863e9129bf732d0d160cb44fd51a7a691` / `8b06d17801ba9d3ed0bb3dd5eccd691a13b5eea3aa9ddb90783d6a3c4507afa1` |

이 값은 TRAIN에서 68개를 탐색한 상위 셀이다. 사전등록 G의 최소 OOS 표본, 워크포워드, 다중검정, 비용 스트레스, 파라미터 평탄도, 독립 레드팀 성과 재현을 통과하지 않았으므로 전략 후보 승인이나 시장 엣지 증거가 아니다. 생존편향도 해결되지 않았다. 유효 TRAIN 종목은 입력 487개 중 194개이며 293개는 공통 2018-10-26 경계 이전 가격 행이 없어 빈 TRAIN으로 기록됐다.

실행 후 레드팀이 코인 경계 2개 P1을 찾아 모두 수정했다(훈련 컷오프 이후 월 파일을 읽지 않음, missing-funding sentinel과 겹치는 우측 검열 setup의 fail-closed 판정). 수정된 현재 주식 source SHA-256은 `a837496623bbf3c8fe09a1911575615e28fc2b510a7b10ece027c7ac523d5616`로 위 실행 SHA와 다르다. 수정 내용은 주식 실험의 계산 경로에는 해당하지 않지만, 정확한 코드 해시 일치와 시장 간 비교를 보장하기 위해 US R2를 현재 동일 코드 버전에서 재실행하고 KR R2도 같은 버전으로 실행할 예정이다. 과거 행은 삭제·수정하지 않는다.

추가 실데이터 작업 전 자원 게이트에서 macOS swap 사용량 `5,225.38 MiB`가 최대 허용 `3 GiB`를 넘었다. 공유 heavy lock은 해제됐고 `/` 여유는 89 GiB였지만 swap 조건 때문에 다음 실데이터 실행은 시작하지 않았다. 전체 단위 테스트 137/137 및 레드팀 24/24가 통과했고, 독립 레드팀은 두 수정이 코드에 반영됐음을 확인했다. OOS는 열지 않았다.

### TRAIN 내 가족별 탐색 폭 (동일 68행)

| 가족 | 양(+) 기대값 설정 | PF≥1.3 설정 | PF 최소/중앙/최대 | 최고 설정 기대값 / PF / 거래수 |
|---|---:|---:|---:|---|
| C1 OB 재방문 | 26/32 | 9/32 | 0.966 / 1.131 / 1.554 | +268.03bp / 1.554 / 3,700 |
| C2 갭 되돌림 | 0/4 | 0/4 | 0.777 / 0.813 / 0.890 | -14.56bp / 0.890 / 2,517 |
| C3 추세 눌림 | 14/16 | 0/16 | 0.997 / 1.084 / 1.213 | +70.13bp / 1.212 / 15,783 |
| C4 수요구간 재방문 | 8/16 | 0/16 | 0.890 / 1.002 / 1.127 | +24.81bp / 1.127 / 34,191 |

C1 주간 16설정 중 16개가 TRAIN 기대값 양수(77.23–268.03bp)였고 9개가 PF 1.3 이상이었다. 최고 설정의 직접 이웃 4개(한 파라미터만 변경)도 모두 양수(171.64–255.46bp, PF 1.369–1.535)였다. 이는 TRAIN 안의 주변 설정 일관성만 보인 탐색 단서다. 사후 선택된 표본이고 고정 G의 plateau/워크포워드/OOS 검증이 아니므로 통과 증거가 아니다. 다음 연구 우선순위는 C1의 주간 메커니즘을 별도 사전등록하고, point-in-time/상폐 데이터 결함이 해결되기 전에는 OOS 후보를 동결하지 않는 것이다.
