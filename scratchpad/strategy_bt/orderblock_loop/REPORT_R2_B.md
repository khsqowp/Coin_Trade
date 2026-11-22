# R2 B 코인 오더블록 보고서

## 총괄 실행 명령·예상치

저장소 경로: `/Users/user/CODE/Coin_Trade`. 아래 단일 명령으로 35개 종목을 모두 포함해 72개 사전등록 설정을 실행한다. `--shard 0/1`은 전체 유니버스 단일 샤드다. 이 보고서 작성자는 전략 탐색을 실행하지 않았다.

```bash
cd /Users/user/CODE/Coin_Trade
nice -n 10 /Users/user/CODE/trading_data/cache/orderblock/venv/bin/python /Users/user/CODE/Coin_Trade/scratchpad/strategy_bt/orderblock_loop/search_crypto.py --shard 0/1
```

- 예상 시도 수: 72 (정의 3 × 주기 3 × 방향 2 × 기한 2 × 손익비 2). 완주 시 전부 `TRAIN_TRIALS.csv`에 기록된다.
- 예상 소요시간: 약 2~4시간으로 계획한다. 기존 72개 실행은 mark 누락 심볼 제외 때문에 30심볼 요건을 채우지 못했고 코드 해시도 혼합되어 있어 처리시간 비교 기준으로 신뢰할 수 없다. 따라서 위 시간은 검증된 벤치마크가 아니라 용량 계획용 추정이며 실제 소요시간은 확인 안 됨이다.
- 메모리: 검색기 설정은 3GiB RSS 상한 감시, 순차 단일 프로세스 실행이다. `nice`와 실제 실행 자원 상태는 총괄 실행 환경에서 확인해야 한다.

## Role B 변경 및 확인

- `PREREG.md`에 전략 결과 열람 전 mark 누락 시 동일 timestamp의 일반 1분봉 close 대용 정책과 대용 오차 진단을 고정했다. 공통 train cutoff까지 실제 mark와 1분 close가 모두 있는 91,048개 settlement에서 가격 오차 평균 -0.080592bp, 중앙값 0bp, 절대오차 p95 12.468059bp, 최댓값 311.972938bp였다. Funding 현금흐름 절대오차 평균 0.001437bp, 중앙값 0.000179bp, p95 0.004235bp, 최대 2.825792bp였으며 실제 funding 금액 대비 상대오차 중앙값 0.01917%, p95 0.12468%, 최대 3.11973%였다. 평균 오차는 작지만 최댓값까지 무시할 수 있다고 단정하지 않는다.
- `data_access.py`는 해당 mark가 없을 때 같은 직전 1분 timestamp의 `um_klines_1m` close를 읽는다. mark와 봉 가격이 모두 비면 가격은 결측으로 유지한다.
- `crypto.py`의 `FundingEvent`에 일반 봉 close 대용 여부를 추가했고, `search_crypto.py`가 mark 누락을 이유로 종목 전체를 제외하지 않으며 대용 이벤트 수와 잔여 결측 종목을 기록하게 했다. 실제 보유 중 정산에서 가격을 산출할 수 없는 거래는 기존 미판정 처리로 남는다.
- 테스트: 지정 venv의 `unittest discover` 최종 실행 결과 118개 통과, 실패 0개. `pytest`는 venv에 설치되지 않아 사용하지 않았다.
- 실데이터 전략 탐색, `TRAIN_TRIALS.csv` 추가 기록, 후보 순위·성과 판정: 실행 안 함.

## 코드 SHA-256

전략 실행 전에 아래 다섯 파일을 고정하고, 실행 동안 수정하지 않는다. SHA는 보고서 최종 작성 후 산출한다.

| 파일 | SHA-256 |
|---|---|
| `crypto.py` | `bc87e4c659168f99e62bf5ffb83c4a0aaa6bc4311c2965842b18d1ba4b42474c` |
| `search_crypto.py` | `27bd864372b7f6bb565e5286a784be220faf4dc3fcf6ebd1fa1f64bc4f559587` |
| `data_access.py` | `a08d5a63dfa7c585bc1d4f6ca326962cdac246a5fc87812ab3092b549c9bf6e9` |
| `metrics.py` | `533441debd1873426b168d547703b6964b5c654ac7ae1f63655d44686e05194a` |
| `resource_guard.py` | `9dfc1eaa67cd86d2a43197f3214fa01d3ded93a381095d4d6c15c2e792b43b51` |

## 총괄 독립 감사 — 기존 기록 사용 금지

총괄이 2026-11-23에 `TRAIN_TRIALS.csv`의 기존 crypto/R2 229행을 읽기 전용 재집계했다. 상태는 `failed` 153, `unscorable` 76, `completed` 0이다. failed 153건은 PEPE mark 누락 72, SHIB mark 누락 24, 불완전 봉 배열 48, 정렬·인덱스·중단 등 9건으로 분해된다. unscorable 76행에서는 funding sentinel이 3,263 거래와 겹쳤으나 설정별 중복 집계이며, 3개 종목에는 TRAIN 봉이 없었다. 과거 코드 해시는 8종이고 입력 fingerprint가 없다. v2.1 개정 후 발생한 마지막 4행은 원시 지표가 기록된 진단용·후보 사용 금지 행이다.

따라서 이 229행은 유효한 성과 추정치가 아니며, 과거 행에 지문·수정 상태를 소급 부여하지 않는다. 독립 D가 지적한 P1 두 건은 `data_access.py`와 `search_crypto.py`에서 수정됐고, 전체 단위 테스트 137/137 및 redteam 24/24가 통과했다. D는 코드를 독립 재검토해 두 수정과 회귀 테스트 구조를 확인했고 잔여 P1은 없다고 보고했다. 이 감사에서 회귀 테스트도 직접 재실행했다.

다음 코인 실데이터 run은 v2.1 코드·입력 fingerprint·sentinel 거래/검열 감사가 적용되는 prospective run이어야 한다. 현재 조합 코드 SHA-256은 `ce01e4006e37341353bb2373f2ce9e6ec3999ec2a537f9346ee711791edbac33`이다. 다만 5개 심볼의 mark 가격 6개 지점이 허용된 1분봉 종가 대체 후에도 남아 있어 어떤 grid 설정이 완주 가능한지는 미리 보장할 수 없다. 이 실행은 자원 게이트(swap 사용량 3GiB 미만)를 통과한 뒤에만 한다. 기존 229행을 후보·순위에 넣지 않고, TEST를 열지 않는다.
