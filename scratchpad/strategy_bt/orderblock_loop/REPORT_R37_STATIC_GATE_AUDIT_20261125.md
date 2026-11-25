# R37 정적·합성 게이트 감사 — 2026-11-25

## 판정

R37은 R14 기반 첫 오더블록 재방문 시간 필터의 **단일 TRAIN 선별 실험 후보**다. 최신 고정 테스트 스냅샷은 15/15 통과했지만, 사전검사 실패 기록과 모든 실행 전 게이트의 순서 검증은 완전하지 않아 실데이터 TRAIN 게이트는 아직 열지 않았다. 독립 검토자가 더 오래된 스냅샷에서 테스트 파일 부재를 지적했으나 현 checkout에는 파일이 있다.

## 고정 가설

- R14의 4h `bos_origin` 구역을 유지하고, BOS와 일치하는 1h 활성 인덱스 이후 1~4개의 완료 1h봉 안에 발생한 첫 접촉만 허용한다. age 0 또는 age 5 이상은 거부한다.
- age 5에서 첫 접촉한 구역은 한 번 소진되며, 같은 구역에 나중에 재진입하지 않는다. R14의 다음 1h 시가 진입·손절·목표·보유시간·비용·펀딩은 그대로다.
- R37은 R14에 종속된 하위집단 진단이다. 독립 전략 증거나 확정 후보로 세지 않는다.

## 현재 실행 전 증거

- 현재 상세 사전등록 SHA-256: `940c0232fdbcdec212e8281746f74ae4db00f031e8f9e31c4e0971046a71e050`.
- 현재 runner SHA-256: `d581e5e8ff94eed61df6d68cf5f1d8b09a31d78ad86c6fc066cac0ada7624ba1`.
- test 보강 직전 snapshot SHA-256: `9302e7576bd2d0548c0accead60fcd30c6a900c96c3ba43aa46303d073f70a01`.
- test 보강 후 현재 합성 테스트 SHA-256: `e5ff48f00166c85751e8290632e8148b812e66bd26676e13f33097ad9a9d3ffa`.
- 보강된 파일 조합의 현재 R37 `_code_hash()` (상세·master prereg, runner, tests 포함): `94fc95f43d06c70b70690f9b9cf338831f256b4a86f1e2621367e9cf63b624d9`.
- 현재 checkout 장부는 앞선 writer 검사 통과 후 읽은 상태에서 4,193행이고, R37 라운드는 없었다. 따라서 사전등록의 계획 분모는 4,194다. 이 기록 시점 이후 장부가 바뀔 수 있으므로 실행 직전 다시 확인해야 한다.
- R37 runner·사전등록·테스트는 미추적/uncommitted 파일이다. `PREREG.md`에는 R37 설명이 이미 추가돼 있다. 이 감사에서는 어떤 R37 소스나 사전등록도 수정하지 않았다.

## 합성 테스트 결과

최근 실행 명령: `/Users/user/CODE/Coin_Trade/trading_data/cache/orderblock/venv/bin/python -m unittest discover -s tests -p 'test_search_crypto_r37_fresh_ob_retest.py' -v` (작업 위치: `scratchpad/strategy_bt/orderblock_loop`). test SHA와 runner의 종합 `_code_hash()`를 실행 전후 비교했고 값이 바뀌지 않았다. 최신 결과: **15 tests, OK**.

현 테스트는 age 0·1·4·5 경계, age 5 첫 접촉 소진, 미래 1h·4h 봉 변조 불변성, R14 simulator 연결, 정확한 다음 봉 `entry_index`·`entry_price`, 왕복 12bp 및 age 4 fixture의 adverse funding 음수 손익, monkeypatch 복구, 중복 라운드·행수·prereg hash·저장공간 사전검사, 두 잠금 경합, 성공 append, 짧은 append, `fsync` 실패, `close` 실패 시 단일 write와 불확실 오류를 다룬다.

같은 테스트를 앞서 실행했을 때 age 5 소진 검사가 한 차례 실패했다. 곧바로 동일한 합성 fixture를 따로 실행했을 때 age count `{"5": 1}`이 나왔고, 뒤이어 test 파일이 갱신됐다. 파일 SHA가 조사 중 바뀌어 첫 실행의 정확한 코드·테스트 쌍은 보존하지 못했다. 따라서 중간 실패를 최신 test snapshot의 회귀로 단정하지 않으며 당시 실행 기록으로만 남긴다. 이후 안정된 snapshot의 11/11, 그리고 보강 후 stable hash의 15/15가 각각 통과했다.

## 남은 게이트 결함·검증 공백

1. **실행 전 게이트 범위:** 행수·상세 prereg hash·disk gate는 데이터 접근 전에 멈추는 픽스처가 있다. writer 부재 검사 오류, master hash, code hash, split manifest/cutoff, 최소 유효 심볼 수의 fail-closed 동작은 직접 검증하지 않았다.
2. **실패 원인 보존:** 위 preflight 오류는 `_run_locked()`의 데이터 실행 `try`보다 앞에서 발생하고 `_acquire_locks()`도 `run()`의 `try/finally` 밖이다. 따라서 실패 정보를 저장하지 않고 종료할 수 있다. 원시 장부에 쓰기 어려운 writer 동시성 오류와 일반적인 고정 사전검사 실패를 분리해 안전하게 남기는 규칙이 필요하다. 이 동작은 현재 runner와 tests에 구현되지 않았다.
3. **독립 검토:** 이 감사는 한 차례 독립 read-only 검토를 추가했으나, 남은 preflight·실패 보존 공백을 닫은 뒤의 최종 독립 승인은 아니다.

## 허용되는 다음 작업

사전등록된 age 경계는 변경하지 않는다. master/code/split/cutoff/최소심볼 검증과 preflight 실패 정보 보존 규칙을 완성하고, 수정된 상세/master prereg·runner·tests hash를 고정한다. 독립 red-team 재검토 및 실행 직전 장부·writer·lock·cutoff·심볼·disk 대사를 모두 통과한 뒤에만 한 번의 TRAIN 실행을 검토할 수 있다. 이 조건이 충족되기 전에는 R37을 실행하거나 숫자로 평가하지 않는다.

R37 TRAIN 통과도 OOS/G 후보 확정을 의미하지 않는다. 코인 오더블록 2개, 한국 주식 2개, 미국 주식 2개 목표는 현재 **0/6**이다.

## 사후 실행 대사 및 해석 정정 — 2026-11-25

이 절은 기존 사전 실행 감사 내용을 덮어쓰지 않고, 이후 공유 체크아웃에 나타난 R37 결과를 별도로 기록한다. 현재 R37 결과 보고서는 1회 실행 및 TRAIN 선별 탈락을 기록한다. 보고서와 장부를 읽기 전 `r19._assert_no_ledger_writer()`가 통과했다. CSV 스트리밍 대사 결과 데이터 행은 4,194개였고, trial ID `R37-crypto-39cf547ee8b04c87ae10bc8d38d00dd8` 한 행이 확인됐다. 장부의 `metric` 필드에는 보고서와 일치하는 고정 지문, 4,361 거래, M2 2,657/4,361 (60.9264%), EV −23.8141bp, PF 0.8066, Sharpe −2.0918, 누적 −32.4542%, MDD 32.9346%가 기록돼 있다. 기준 미달이므로 R37은 실패이며 0/6 후보 수를 바꾸지 않는다.

장부 행에 저장된 실행 code SHA는 `d50fdaab511b05b3c0623b5e18c70ea20353eb1a3b1c7bdc59c30b2f3b93c6c0`이다. 현재 R37 모듈이 계산하는 composite code hash는 `fbc440e3c5dbce77e73f1ad6a9049f2983045177bd674a7b63fcdbb536b1d386`으로 다르다. 현재 상세 prereg SHA는 `940c0232fdbcdec212e8281746f74ae4db00f031e8f9e31c4e0971046a71e050`이며 장부에 기록된 상세 prereg SHA와 일치한다. 테스트 SHA는 `e5ff48f00166c85751e8290632e8148b812e66bd26676e13f33097ad9a9d3ffa`이다. 실행 당시의 전체 파일 스냅샷은 보존되지 않아 현재 코드로 완전 재현됐다고 볼 수 없다.

독립 red-team의 시간 해석 지적도 남긴다. R14의 활성 `signal_index`는 4h BOS 완료 시각에 해당하는 1h 인덱스에 놓이며 simulator는 age 0봉을 건너뛴다. 그러므로 사전등록된 index 차이 1–4는 “첫 네 개의 R14 진입 가능 봉”을 뜻한다. H1 확인봉의 완료 시각을 BOS 완료 이후 경과 시간으로 표현하면 2–5시간 범위가 될 수 있어, 보고서의 “1–4개 1h봉 안”은 문자 그대로 “BOS 후 4시간 이내 확인”과 동일하지 않다. 사전등록 index 규칙과 실행 결과는 사후에 바꾸지 않으며 age 경계 재시험도 하지 않는다. R37은 이미 실패했고 더 이상 실행 대상이 아니다.

R11에 대해서는 사용자가 전달한 사후 감사 상태를 반영한다. 목표거리 0.25R EV 구간 표기는 `−36.00~−19.25bp`로 정정됐고, R11 48행 표·신뢰구간 재계산 대사 및 단위 테스트 43/43 통과, no-index diff check와 trailing-whitespace 점검 통과가 보고됐다. R12 초안은 prereg와 runner만 있으며 hash 고정·테스트·실행·장부 기록은 없는 상태다. 이 감사에서는 R11 테스트를 재실행하거나 R12를 실행하지 않았다.
