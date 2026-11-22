# FROZEN_R<n> — 동결 후보 목록

- 라운드: `<n>`
- 시장군: `crypto` 또는 `equities` (시장군당 최대 3개)
- 동결 UTC 시각: `<YYYY-MM-DDTHH:MM:SSZ>`
- 누적 train 시도 수 (`N_train`): `<count>`
- 이번 제출 후보 수: `<count>`
- 제출 후 누적 test 동결 후보 수 (`N_test`): `<count>`
- 동결 전 train cutoff/hash: `<period and SHA-256>`
- test 기간 데이터 미열람 확인자/시각: `<name/UTC time>`

각 후보에 다음을 기록한다. 후보 정의·코드·입력의 SHA-256을 확정하고 이후 변경하지 않는다.

| 순위 | 후보 ID | 가설/전략/시간단위/방향/파라미터 | train 점수·선정 기준 | 설정 SHA-256 | 코드 SHA-256 | 입력 SHA-256 | test 제출 여부 |
|---:|---|---|---:|---|---|---|---|
| 1 |  |  |  |  |  |  | 미제출 |

최대 3행까지 작성한다. `N_test`는 이전 라운드까지 test에 제출한 동결 후보의 누적 수에 이번 문서에서 `test 제출 여부=제출`인 후보 수를 더해 기록한다. 제출 시도 뒤 미실행·실패가 되어도 제출 후보 수에서 빼지 않는다. 각 후보의 Bonferroni/RC/SPA는 이 누적 `N_test`, DSR은 `TRAIN_TRIALS.csv`의 누적 데이터 행 수(`N_train`)만 분모로 쓴다.
