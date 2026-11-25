# R23 사전등록 — R21 고정 거래의 방향·연도 귀속

상태: 단일 진단 실행 전 고정. 이 분해 결과로 필터나 그룹을 고르지 않는다.

## 목적

R21의 단일 TRAIN 결과(EV +50.55bp, PF 1.548, M2 63.27%, 거래 196건)가 한 방향이나 특정 entry year에 집중됐는지 분해한다. R22의 다음봉 BOS 수용 필터는 M2·EV·PF를 개선하지 못했다. R23은 새 성과 전략이 아니라 실패·기여 원인 진단이다.

## 규칙과 분할

- R21과 동일한 고정 35심볼, 완성 4h/1h TRAIN 자료, cutoff `2023-11-06T16:00:00Z`, 사전 BOS 20-bar external sweep, 1–3개 4h봉 내 BOS, 첫 1h 재방문·중앙값 회복 후 next-open 진입, stop/target/time/funding/cost 규칙을 쓴다.
- 거래를 사전 고정 두 축으로 분류한다: 방향(`long`, `short`)과 UTC entry year. 그룹의 경계를 결과에 따라 병합·분할하지 않는다. 그룹을 선택 규칙으로 쓰지 않고 전체 행을 모두 보고한다.
- 모든 trade에서 `direction`, entry timestamp/year, M2 target-first label, funding-scoreability, 비용 후 `net_return`를 보존한다. 그룹별 count, M2 hit/rate/Wilson 95% lower bound, funding-scoreable count, 승률, EV(bp), PF를 산출한다.
- 전체 합계가 기존 R21의 전체 trade 수 196, M2 hit 124, scoreable trade 수, EV, PF와 허용 오차 없이 일치해야 한다. 다르면 `failed/inconsistent`로 기록하고 그룹 결과로 주장을 만들지 않는다. R21의 baseline 행은 재계산하지 않고 기존 report/ledger 값만 대조 대상으로 쓴다.
- 수익/손실이 포함된 그룹 비교는 사후 탐색이다. 그룹 수만큼의 다중비교를 보정하지 않은 p-value를 만들거나 단일 그룹을 새 후보로 승격하지 않는다. 새 가설은 별도 prereg, 새 run, 독립 OOS를 요구한다.

## 고정 경계 및 실행

- 단일 diagnostic trial. 장부 실행 전 행 1,679, 실행 후 1,680이어야 하며 포함 Bonferroni 분모는 N=1,680으로 고정한다. 행 수 mismatch, process/writable FD/lock 발견, code/prereg hash 불일치 때는 가격 자료에 접근하지 않는다.
- 2023-11-06T16:00:00Z 뒤 TEST/OOS 및 2026-06-01 이후 자료를 읽지 않는다. 다른 cutoff·시장·전략 변형을 추가하지 않는다.
- 거래 자료가 unavailable한 상태의 실행/코드 예외는 `failed`로 기록하고 결과를 임의로 보완하지 않는다. 장부 쓰기 불가능 또는 append rollback 실패 시 더 진행하지 않는다.
- 이 결과는 성과 증거를 다시 검증하지 않으며 OOS나 G 통과를 의미하지 않는다. 2018/PIT·상장폐지·데이터 이용권 게이트는 닫힌 상태다.
