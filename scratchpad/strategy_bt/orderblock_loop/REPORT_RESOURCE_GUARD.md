# Resource guard 변경
- `heavy_task(role, lock_path=None)`의 공유 락, nice 조정, 60분 대기를 제거해 동시 진입을 허용했다.
- 루트 디스크 여유 40 GiB 미만이면 `RuntimeError`를 유지한다.
- 가드 단위 테스트: 2개 통과; 러너 테스트에는 기존 가드 동작 의존 없음.
- 전체 unittest: 225개 실행, 오류 8개, 건너뜀 2개; `pyarrow` 누락으로 전체 통과 확인 불가.
