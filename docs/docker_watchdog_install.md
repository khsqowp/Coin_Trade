# Docker watchdog 설치 안내

watchdog은 120초마다 Docker 엔진과 momentum-rotation 상태를 확인한다. 엔진 복구를 고려하려면 30초 timeout의 `docker info` 실패가 3회 이상이고 첫 실패부터 최소 6분이 지나야 한다. 실패 streak가 15분보다 오래되면 만료한다. 직전 실행 간격이 6분을 넘으면 깨우기/부팅 grace로 카운터를 초기화하고 한 주기를 건너뛴다. 봇 중지, heartbeat 누락·지연(600초 이상), OOMKilled, RestartCount 증가는 알림만 내며 Docker를 재시작하지 않는다.

## 설치

1. 템플릿의 `__REPO__`를 레포 절대경로로, `__HOME__`을 홈 절대경로로 치환해 `~/Library/LaunchAgents/com.ochestration.docker-watchdog.plist`에 저장한다.
2. `plutil -lint`로 plist를 확인한 뒤 launchd에 등록한다.

```bash
REPO="$(git rev-parse --show-toplevel)"
mkdir -p "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"
plutil -lint "$HOME/Library/LaunchAgents/com.ochestration.docker-watchdog.plist"
launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/com.ochestration.docker-watchdog.plist"
```

launchd와 스크립트 양쪽에서 제한된 PATH를 설정한다. Docker CLI를 찾지 못하면 `CONFIG ERROR`를 기록하고 Docker Desktop을 건드리지 않는다. `HOME`이 비어 있으면 dscl 및 셸 홈 조회를 시도한 뒤 안전한 임시 위치를 사용한다. dry-run은 별도 임시 상태 디렉터리를 사용하고 실제 카운터를 바꾸지 않으며, 예상 동작 로그를 stderr에 출력한다. 기존 상태를 기준으로 재시작 조건을 미리 보려면 `--dry-run-from-state DIR`을 지정한다. 이 옵션은 상태 파일을 임시 디렉터리로 복사해 판정하며 원본 디렉터리에는 쓰지 않는다.

```bash
REPO="$(git rev-parse --show-toplevel)"
env -i HOME="$HOME" PATH=/usr/bin:/bin:/usr/sbin:/sbin \
  /bin/bash "$REPO/scripts/docker_watchdog.sh" --dry-run --check-once

# 운영 상태를 읽기 전용으로 사용해 재시작 판정 미리보기
/bin/bash "$REPO/scripts/docker_watchdog.sh" \
  --dry-run-from-state "$HOME/Library/Application Support/ochestration-watchdog" --check-once
```

## 일시 중지와 복구 경계

운영 상태 디렉터리는 `~/Library/Application Support/ochestration-watchdog/`다. `PAUSE` 파일이 있으면 Docker 엔진 장애를 알리기만 하고 재시작하지 않는다. Docker Desktop 프로세스가 완전히 없는 경우도 사용자가 앱을 종료한 것으로 보고 자동으로 앱을 열지 않는다.

```bash
mkdir -p "$HOME/Library/Application Support/ochestration-watchdog"
touch "$HOME/Library/Application Support/ochestration-watchdog/PAUSE"
# 유지보수 후 재개
rm "$HOME/Library/Application Support/ochestration-watchdog/PAUSE"
```

`WATCHDOG_STATE_DIR`를 지정했다면 그 디렉터리의 `PAUSE`를 사용한다. 봇 heartbeat가 처음부터 없는 구 이미지에서는 `not-yet-supported` 안내를 한 번 기록하고 오류로 처리하지 않는다. heartbeat가 확인된 뒤 사라지거나 컨테이너 내부 시계 기준 age가 600초 이상이면 알림만 낸다. 호스트와 Docker VM 시계는 비교하지 않는다.

복구 기준을 만족하면 watchdog은 시도 시각과 rolling 24시간 횟수를 tmp 파일에서 원자적으로 갱신한 뒤 `quit`을 요청한다. `pgrep`으로 실제 앱 이름 `Docker Desktop` 또는 `Docker`가 사라지는지 최대 60초 기다린다. 종료 확인에 실패하면 `open -a Docker`를 실행하지 않으며, 해당 시도는 cooldown과 횟수 제한에 포함한다. 종료가 확인된 경우에만 앱을 열고 엔진 복귀를 최대 120초 기다린다. 모든 시도는 30분 cooldown, 24시간 최대 2회 제한을 공유한다.

swap 경고는 전체 swap의 95% 초과와 14 GiB 초과를 동시에 만족할 때만 내며, 같은 경고는 6시간에 한 번 기록한다. 로그 파일은 1 MiB를 넘기면 한 세대 회전한다.

## 상태 및 로그

로그는 기본 `watchdog.log`에 남는다. lock 디렉터리는 PID와 시작 epoch를 기록한다. PID가 살아 있고 lock이 5분 이내면 중복 실행을 건너뛴다. PID가 죽었거나 lock이 5분보다 오래되면 takeover를 로그로 남긴다. lock 정리는 해당 실행이 디렉터리를 직접 만든 뒤에만 활성화되므로, 이미 실행 중인 소유자를 발견해 건너뛴 실행은 기존 lock을 삭제하지 않는다. timeout 명령은 별도 process group에서 실행되며 제한 시간이 끝나면 그룹에 TERM 후 KILL을 보낸다.

```bash
tail -f "$HOME/Library/Application Support/ochestration-watchdog/watchdog.log"
launchctl print "gui/$(id -u)/com.ochestration.docker-watchdog"
launchctl bootout "gui/$(id -u)" "$HOME/Library/LaunchAgents/com.ochestration.docker-watchdog.plist"
```

## 서비스 제한 참고

`docker-compose.trading.yml`에는 아직 메모리/PID 상한이 없는 비활성 profile 서비스가 있다: `trading`, `trading-kr-swing`, `trading-us-swing`, `trading-trx-swing`. 특히 실자금 대상 `trading-trx-swing`을 다시 사용하기 전에 상한을 추가해야 한다.

자동 엔진 복구는 모든 컨테이너를 중단시킬 수 있으며 거래소 stop-loss나 포지션 보호를 보장하지 않는다. 서비스 컨테이너의 Compose 제한은 별도 유지보수 시간에 컨테이너를 재생성해야 적용된다. watchdog은 Compose 명령을 실행하지 않는다.
