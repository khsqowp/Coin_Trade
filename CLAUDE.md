# Claude 프로젝트 규칙

모든 Coin_Trade 작업에서는 먼저 `AGENTS.md`와 `docs/STORAGE_RULES.md`를 읽고 따른다.

## 절대 저장 경로

- 거래·연구와 관련한 코드, 문서, 원본 데이터, 캐시, 중간 파일과 결과는 예외 없이 `/Users/user/CODE/Coin_Trade/` 안에서만 생성·수정·복사한다.
- `/Users/user/CODE/trading_data/`, `/Users/user/CODE/Ochestration/`, `/Users/user/CODE/` 루트 및 그 밖의 경로에 거래·연구 파일을 만들지 않는다.
- 대용량 자료도 저장소 내 로컬 전용 디렉터리에 두고 Git 추적을 차단한다. 사용자 승인 없이는 외부 저장소 예외를 만들지 않는다.
- 이 규칙은 문서에 남아 있을 수 있는 과거 `trading_data` 경로 안내보다 우선하며, 충돌 발견 시 진행 전에 문서를 정합시킨다.
