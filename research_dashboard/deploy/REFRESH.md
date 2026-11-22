# 서버 데이터 새로고침 초안 (실행하지 않음)

현황판 갱신용 컨테이너는 저장소의 trading 디렉터리를 읽기 전용으로, forward DB가 든 세 디렉터리를 각각 읽기 전용으로 마운트한다. 별도 출력 디렉터리만 쓰기 가능하게 둔다. 실제 compose 서비스는 아직 추가하지 않는다.

권장 컨테이너 경로:

- 코드: /workspace/trading (읽기 전용)
- 4시간 DB: /data/forward/l5_4h (읽기 전용)
- 12시간 DB: /data/forward/l5_12h (읽기 전용)
- 1시간 DB: /data/forward/jbb_1h (읽기 전용)
- 현황판 dist: /srv/dashboard (data.json 갱신용 쓰기 마운트)

사이드카 스크립트 초안:

~~~sh
#!/bin/sh
set -eu
while :; do
  date -u '+%Y-%m-%dT%H:%M:%SZ' > /data/forward/COPIED_AT.txt
  python /workspace/trading/research_dashboard/build_data.py \
    --root /workspace/trading \
    --out /srv/dashboard/data.json \
    --forward-db-dir /data/forward
  sleep 300
done
~~~

이 초안에서 /data/forward 상위 경로는 컨테이너 자체의 쓰기 가능한 임시 경로이고, 각 프로파일 하위 디렉터리만 호스트에서 읽기 전용으로 마운트한다. SQLite 연결은 코드에서 mode=ro로 연다. DB와 WAL/SHM 파일은 컨테이너에서 절대로 수정하지 않는다. 빌더는 기존 forward_test.status 계산을 사용하므로 동일한 Python 및 의존성 환경이 필요하다. 최초 구성 때는 Python 버전과 의존성 잠금 파일을 별도로 확인하고 고정해야 한다.

매 5분 실행은 data.json을 새로 생성한다. nginx는 이 파일에 Cache-Control: no-store를 적용한다. 데이터베이스 파일을 dist 안에 복사하거나 웹으로 제공하지 않는다.
