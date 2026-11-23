# TRAIN_TRIALS.csv 거래 ID 압축 제안

## 목적

현재 `TRAIN_TRIALS.csv`는 53,803,137바이트(약 53.8 MB, 십진 단위)다. PREREG addendum은 trial metric 안의 긴 거래 ID 목록이 크기 증가 요인이라고 기록한다. 과거 행은 그대로 보존하고, 앞으로 기록하는 행만 `{count, sha256}` 요약으로 저장하는 설계를 제안한다.

## 기존 장부 보존

체인 종료 및 별도 적용 승인 뒤, 기존 CSV를 같은 내용의 gzip 파일 `TRAIN_TRIALS.csv.gz`로 보관한다. 원본 `TRAIN_TRIALS.csv`는 삭제하거나 덮어쓰지 않고 그대로 둔다. gzip 파일 생성 시 행 수와 원본 SHA-256을 매니페스트에 기록하고, 압축 해제 스트림의 행 수와 SHA-256이 원본과 일치하는지 확인한 다음 아카이브를 사용할 수 있다. 이번 작업에서는 압축 파일 생성, 원본 교체, 행 수정은 하지 않았다.

Read-only `gzip -c TRAIN_TRIALS.csv | wc -c` 측정값은 12,799,719바이트(약 12.8 MB)다. 원본 대비 23.8%이며 약 76.2% 감소한다(53,803,137바이트 기준). 측정은 스트림 파이프로 수행되어 gzip 파일을 만들지 않았다. `nice -n 10` 우선순위 변경은 샌드박스에서 거부됐지만 gzip 측정 명령 자체는 완료됐다.

## 요약 CSV 제안

압축 아카이브와 별도로 `TRAIN_TRIALS_SUMMARY.csv`를 생성한다. 행은 기존 trial 한 건당 하나로 유지하되, 원본 ID 리스트는 넣지 않는다. 권장 필드는 다음과 같다.

- 기존 trial 식별 및 재현 필드: `trial_id`, `round`, 설정 식별자, `code_sha256`, `train_input_fingerprint`, 기록 시각, 상태
- 집계 수치: `trade_count`, `scored_trade_count`, `unscorable_trade_count`, 기존 요약 성과 지표와 데이터 품질 집계
- 각 ID 목록 필드별 `*_count`, `*_sha256`: 정렬한 원문 ID를 개행으로 연결해 UTF-8 인코딩한 바이트의 SHA-256

요약 CSV에는 raw `trade_ids`, `unscorable_funding_trade_ids` 또는 그 밖의 ID 목록을 저장하지 않는다. 시도 행 수, `code_sha256`, `train_input_fingerprint`는 기존 값을 유지한다. ID 요약은 원문 복원이 불가능하므로 원본 CSV.gz 아카이브를 감사용으로 보존한다. CSV 요약의 크기는 필드 수와 기존 metric 분포를 측정하지 않았으므로 현재 추정할 수 없다.

## 범위와 적용 순서

이번 변경은 독립 유틸 함수와 합성 단위 테스트만 추가한다. 러너 연결, 기존 ledger 변환, gzip 아카이브 생성은 하지 않았다. 제안된 보존·요약 단계를 실제 적용하기 전에는 체인 종료를 확인하고 별도 변경으로 진행해야 한다.
