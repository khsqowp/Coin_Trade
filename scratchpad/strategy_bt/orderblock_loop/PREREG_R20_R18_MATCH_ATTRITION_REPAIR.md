# R20 — R18 matched-candidate attrition audit, repaired execution

상태: 사전등록. R19는 funnel 완료 후 결과 집계에서 코드 NameError로 중단되어 `failed` 1행만 기록됐다. 어떠한 funnel 수치·전략 결과도 출력되거나 읽히지 않았다. R20은 그 기록된 실행 결함을 고친 동일한 설명형 감사의 새 시도다. R19 실패는 분모에 남긴다.

## 고정 내용

- R20은 R19와 동일한 4h `bos_origin` 후보, 동일 고정 35심볼, 동일 cutoff-aware TRAIN, 동일 처리 순서·후보 필터·caliper·greedy 중첩 기준을 사용한다. 어떤 조건도 완화·확대하지 않는다.
- 목표는 원시 BOS 사건에서 각 R18 후보 필터 단계별 후보쌍과 후보 보유 사건 수를 기록하는 것뿐이다. 가격 결과창·승률·M2·손익·수익률·p값은 계산하지 않는다. 후보 전략/G 성공 수를 늘리지 않는다.
- 코드 결함 수정은 집계 딕셔너리 생성에서 빠진 `defaultdict` import 복원뿐이다. R19에서 출력된 성과 수치가 없으므로 성과 기반 수정은 없다. R20은 R19와 독립적인 신규 시도 ID 및 고유 code/grid/prereg hash로 기록한다.
- R19 실패행 반영 후 실행 전 ledger 행수는 1,676이어야 하며, 본 시도 포함 Bonferroni 분모는 N=1,677이다. 불일치 시 TRAIN bar 접근 전에 중단한다.
- R19/R20 공통 배타 실행 잠금 `.ob_attrition_train_trials.lock`으로 두 runner의 동시 실행을 막고, `lsof` writable handle 검사를 실행 시작·append 직전·append 후 적용한다. 같은 심볼의 segment 간 점유집합을 공유하고, 장부 failure row 기록 실패는 결과와 혼동하지 않고 명시적으로 보고한다.
- TRAIN cutoff는 `2023-11-06T16:00:00Z`. TEST/OOS 및 `2026-06-01` 이후 자료는 접근 금지. 데이터 PIT·상폐·이용권 gate는 여전히 닫혀 있다.

## 판정과 종료

R20 결과는 매칭 실패 원인 설명용 기술 진단이다. R18 매칭 조건 변경이나 R18 재실행을 승인하지 않는다. 실행 오류가 다시 나면 해당 실패를 장부에 남기고, 원인 분석 후 별도 새 prereg 없이는 재시도하지 않는다. 상세 알고리즘은 R19 구현 및 R20 wrapper를 해시로 고정한다.
