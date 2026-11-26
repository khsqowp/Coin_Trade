# VOLREG-R1 V1 — TRAIN 결과 보고서

## 판정

**VOLREG-R1은 이 사전등록 robustness battery의 TRAIN 통과를 받지 못했다.** 25개 중 최고 초과수익 셀이 `entry=-1.5, exit=1.0` 격자 가장자리에 있어 평탄도를 판정할 수 없다. 나머지 사전등록 통과선은 통과했지만, 평탄도 미판정은 통과로 간주하지 않는다는 사전 규칙 때문에 전체 판정은 실패다.

평가 범위는 2002-07-30부터 2026-06-01까지 포함이며, cutoff 이후 날짜의 값은 읽지 않았다. 25개 장부 행을 추가해 `TRAIN_TRIALS.csv` 데이터 행은 4,239개가 됐다.

## 전체 25개 셀

같은 셀별 SPY 매수보유 누적수익률은 모두 **1,210.90%**였다. `MDD`는 평가기간 중 고점 대비 최대 하락률이다. 초과수익은 전략 수익률에서 SPY 수익률을 뺀 퍼센트포인트다.

| entry | exit | 전환 | 초과수익 (pp) | 전략 MDD |
|---:|---:|---:|---:|---:|
| -1.0 | -1.0 | 222 | 772.70 | -34.65% |
| -1.0 | -0.5 | 190 | 687.98 | -33.20% |
| -1.0 | 0.0 | 174 | 745.71 | -31.47% |
| -1.0 | 0.5 | 160 | 721.63 | -32.48% |
| -1.0 | 1.0 | 150 | 810.21 | -29.94% |
| -1.5 | -1.0 | 174 | 1,030.93 | -34.10% |
| -1.5 | -0.5 | 158 | 927.05 | -32.64% |
| -1.5 | 0.0 | 148 | 1,115.59 | -29.43% |
| -1.5 | 0.5 | 140 | 1,126.79 | -30.61% |
| **-1.5** | **1.0** | **134** | **1,249.37** | **-29.65%** |
| -2.0 | -1.0 | 132 | 973.78 | -33.86% |
| -2.0 | -0.5 | 124 | 716.67 | -33.36% |
| -2.0 | 0.0 | 118 | 882.93 | -30.79% |
| -2.0 | 0.5 | 112 | 960.46 | -30.61% |
| -2.0 | 1.0 | 110 | 1,064.30 | -29.65% |
| -2.5 | -1.0 | 106 | 1,130.19 | -31.57% |
| -2.5 | -0.5 | 98 | 844.82 | -30.93% |
| -2.5 | 0.0 | 92 | 929.78 | -30.47% |
| -2.5 | 0.5 | 88 | 1,017.40 | -30.47% |
| -2.5 | 1.0 | 88 | 1,146.13 | -30.47% |
| -3.0 | -1.0 | 84 | 946.75 | -31.73% |
| -3.0 | -0.5 | 80 | 728.89 | -31.10% |
| -3.0 | 0.0 | 74 | 787.78 | -30.47% |
| -3.0 | 0.5 | 72 | 992.39 | -30.47% |
| -3.0 | 1.0 | 72 | 1,003.27 | -30.47% |

승자 누적수익률은 **2,460.28%**, SPY는 **1,210.90%**였다. 승자 MDD는 **-29.65%**, SPY MDD는 **-55.19%**로 MDD 개선은 **25.54pp**다.

## 사전등록 robustness battery

| 기준 | 관측 결과 | 판정 |
|---|---|---|
| 다음 세션 체결 시프트 및 미래변형 prefix 불변성 | 25개 셀 모두 두 assert가 `True` | 통과 |
| 평탄도 | 승자 `entry=-1.5, exit=1.0`은 exit 격자 가장자리 | `grid_edge`, 미판정이며 통과 아님 |
| 비용 2배 | 왕복 24bp 초과수익 **+867.40pp** | 통과 |
| 추가 1세션 지연 | 초과수익 **+750.25pp** | 통과 |
| 무작위 전환일 비교 | 200회, seed `20261126`, 승자 **100.0백분위**, 귀무 범위 **-1,147.72~+243.26pp** | 95백분위 기준 통과 |
| 진입·복귀 신호 순환이동 | 1,000회, seed `20261127`, 승자 **97.3백분위**, 귀무 범위 **-1,103.95~+15,757.84pp** | 95백분위 기준 통과 |
| 2018년 전략 대 SPY | 전략 **+7.44%**, SPY **-4.57%**, 상대 **+12.01pp** | 통과 |
| 2022년 전략 대 SPY | 전략 **-17.98%**, SPY **-18.18%**, 상대 **+0.20pp** | 통과 |
| 2008년 정보용 비교 | 전략 **-5.69%**, SPY **-36.80%**, 상대 **+31.11pp** | 정보용, 게이트 아님 |

두 무작위 비교는 사전 기준인 95백분위 이상을 넘었다. 그러나 200회와 1,000회에서 가능한 가장 작은 단측 permutation p값은 각각 `1/201≈0.00498`, `1/1001≈0.000999`다. 이번 장부 반영 뒤 `N_train=4,239`, Bonferroni 참고 경계는 `0.05/4,239=0.000011795235`다. 두 무작위 비교 모두 이 경계보다 거칠며, 100백분위 결과라도 Bonferroni 유의성을 증명할 수 없다. **관측된 증거는 무작위 비교의 95백분위 기준 통과이며, Bonferroni 유의성은 확인되지 않았다.**

## 수익 집중도와 해석 한계

수익 차이는 단일 연도나 반기에만 몰리지 않았다. 연간 전략-SPY 상대수익에서 양수인 연도 기여 중 가장 큰 해는 2008년 **+31.11pp**였고, 전체 양수 연도 상대수익 합계 중 **29.1%**였다. 반기별 상대수익에서는 가장 큰 반기가 2008년 하반기 **+39.83pp**였고, 양수 반기 상대수익 합계 중 **31.8%**였다. 48개 반기 구간에서 양수 반기 상대수익 합계는 **125.22pp**였다. 이 반기·연도별 상대수익은 복리로 누적된 전체 초과수익과 산술 합산해 같아지는 값이 아니다. 따라서 전체 **+1,249.37pp**는 긴 기간의 복리 결과이고, 특정 한 구간이 그 수치 전부를 설명하지 않는다. 다만 2008년 하반기 기여가 가장 큰 단일 구간이라는 사실은 남는다.

25개 임계값 조합은 하나의 CBOE VIX-RV20 신호 계열과 같은 SPY/QQQ/SHY 바스켓을 공유한다. 이는 25개 독립 아이디어가 아니라 한 상관된 베팅 묶음이며, 장부 25행을 독립 증거 25개로 세면 안 된다.

이번 결과는 고정된 robustness battery의 TRAIN 평가뿐이다. TEST는 닫혀 있다. 전체 G 게이트는 완료되지 않았다. Bonferroni/Reality Check/SPA/Deflated Sharpe의 최종 판단에는 동결 TEST 표본과 정의된 시험군 크기가 필요하다. 미사용 종목군, 두 후보 간 상관 검사, 독립 red-team 재구현 항목은 단일 고정 3-ETF 바스켓에 구조적으로 적용할 수 없으므로 **`NOT_APPLICABLE` / `unscored`**다. 이를 통과로 기록하지 않았다.

## 실행·파일 기록

- 생성: `/Users/user/CODE/Coin_Trade/.claude/worktrees/agent-a3703102af0d2ef31/scratchpad/strategy_bt/orderblock_loop/PREREG_VOLREG_R1_V1.md`
- 생성: `/Users/user/CODE/Coin_Trade/.claude/worktrees/agent-a3703102af0d2ef31/scratchpad/strategy_bt/orderblock_loop/search_volreg_r1_prereg.py`
- 수정: `/Users/user/CODE/Coin_Trade/.claude/worktrees/agent-a3703102af0d2ef31/scratchpad/strategy_bt/orderblock_loop/TRAIN_TRIALS.csv` — 기존 행 뒤에 25행 append. 실행 전 diff는 비었고 실행 뒤 diff는 25개 추가 행만 표시했다.
- 생성: `/Users/user/CODE/Coin_Trade/.claude/worktrees/agent-a3703102af0d2ef31/scratchpad/strategy_bt/orderblock_loop/REPORT_VOLREG_R1_PREREG_V1.md`
- 사전 구문 검사 명령: `TRADING_DATA_DIR=/Users/user/CODE/Coin_Trade/trading_data python -c 'import ast,pathlib; p=pathlib.Path("scratchpad/strategy_bt/orderblock_loop/search_volreg_r1_prereg.py"); ast.parse(p.read_text()); print("AST_PARSE_OK")'` — 종료 코드 0.
- runner 실행 명령: `TRADING_DATA_DIR=/Users/user/CODE/Coin_Trade/trading_data python scratchpad/strategy_bt/orderblock_loop/search_volreg_r1_prereg.py` — 실행을 시작했지만 도구가 30초 시점에 세션을 반환했고 최종 stdout 및 종료 코드는 회수되지 않았다. 사후 CSV에는 정확히 25개 새 ID가 순서대로 추가됐고 행 수가 4,214에서 4,239로 늘었다. append 뒤의 종료 코드를 확인했다고 주장하지 않는다.
- 결과 복원·장부 검증 명령은 `TRADING_DATA_DIR=/Users/user/CODE/Coin_Trade/trading_data python -c 'import csv,hashlib,json,sys; from pathlib import Path; base=Path("scratchpad/strategy_bt/orderblock_loop"); p=base/"TRAIN_TRIALS.csv"; csv.field_size_limit(sys.maxsize); f=p.open(newline="",encoding="utf-8"); rows=list(csv.DictReader(f)); selected=[r for r in rows if r["trial_id"].startswith("VOLREG-R1-PREREG-")]; expected=[f"VOLREG-R1-PREREG-{i:02d}" for i in range(1,26)]; assert [r["trial_id"] for r in selected]==expected; dig=hashlib.sha256((base/"search_volreg_r1_prereg.py").read_bytes()).hexdigest(); assert {r["code_sha256"] for r in selected}=={dig}; assert len(rows)==4239; assert all(json.loads(r["metric"])["test_rows_accessed"] is False for r in selected); print("rows=4239; appended_ids=25 ordered; code_sha256_matches=True; test_rows_accessed=false for all")'` — 종료 코드 0.
- 별도 반기 집중도 재계산: 실행한 명령은 `PYTHONDONTWRITEBYTECODE=1 TRADING_DATA_DIR=/Users/user/CODE/Coin_Trade/trading_data python -c '<TRAIN cutoff loader에서 승자 시뮬레이션 곡선을 반기로 나눠 상대수익 집중도를 계산하는 Python 본문>'`이며 종료 코드 0이었다. 실제 Python 본문은 `search_volreg_r1_prereg`의 `read_training`, `indicators`, `make_targets`, `run_one`을 호출해 2002-07-30~2026-06-01 filtered TRAIN 데이터만 사용했다.
- TEST 확인: runner의 ETF 가격 입력은 `date >= 2002-07-30 AND date <= 2026-06-01`, VIX 입력은 `date <= 2026-06-01` 조건을 pyarrow read filter에 넣었고, 각 읽기 직후 최대 날짜가 cutoff 이하인지 assert했다. 25개 metric 모두 `test_rows_accessed=false`다. 이후 보고서 집중도 계산도 동일 필터 함수를 사용했다. cutoff 이후 값·행 수·날짜 범위는 조회하지 않았다.
