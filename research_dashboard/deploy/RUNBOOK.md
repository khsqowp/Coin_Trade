# LAN 현황판 배포 절차 초안 (실행하지 않음)

사전 조건: 이 문서만으로 배포하지 않는다. 사용자의 배포 승인, 실제 소스 전송 확인, compose 패치 검토, 192.168.0.12 인터페이스 확인, 포트 8765 사용 여부, 읽기 전용 DB 마운트와 되돌리기 자료를 확인한 뒤 진행한다.

## 배포 순서

1. linuxserver에서 저장소와 원격 브랜치를 확인한다.
2. 저장소 최상위에서 git pull --ff-only를 실행한다.
3. compose.patch.md의 research-dashboard 서비스만 docker-compose.trading.yml에 적용한다. 다른 서비스는 수정하지 않는다.
4. nginx.conf와 서비스 포트가 192.168.0.12:8765:80인지, 0.0.0.0 바인딩이 없는지 확인한다.
5. 사용자가 별도로 승인한 경우에만 아래 명령을 실행한다.

~~~sh
docker compose -f docker-compose.trading.yml --profile dashboard up -d --build research-dashboard
~~~

6. LAN 주소에서 화면을 열고 GET 응답, 한국어 화면, data.json의 no-store 응답 헤더를 검증한다.

## 되돌리기

1. 사용자가 승인한 경우 현황판 서비스만 중지한다: docker compose -f docker-compose.trading.yml --profile dashboard stop research-dashboard
2. 추가했던 compose 서비스 블록만 제거한다. 다른 서비스와 볼륨은 건드리지 않는다.
3. 변경 커밋을 이미 만든 경우 해당 커밋을 git revert하고 fast-forward로 서버에 반영한다. 강제 초기화나 원격 기록 재작성은 하지 않는다.
4. 현황판 정적 파일과 데이터베이스를 삭제하지 않는다. DB 볼륨을 제거하거나 수정하지 않는다.
5. LAN 포트가 더 이상 열리지 않는지 확인한다. 공개 터널이나 DNS 설정은 만들지 않는다.
