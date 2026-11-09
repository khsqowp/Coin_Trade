# Docker 장애 예방 변경 보고 — 2026-11-05

## 범위와 상태

- 적용 범위: Ochestration, trading, crypto-data, shadow-predictor, ScopeSentry, dolphin_ai, ARTEx의 Compose 7개 파일과 이 보고서의 현재 제한값 표.
- 제한 규칙: 각 컨테이너의 `mem_limit`과 `memswap_limit`은 같고, 알려진 현재 관측 사용량 또는 제공된 peak의 1.5배 이상으로 올림했다. 소형 컨테이너의 기본 하한은 128 MiB다. API/MySQL/n8n의 PID 제한은 review2에 따라 256/192/96으로 조정했다.
- 완충은 `oom_score_adj` 우선순위, PID 제한, 기존의 완화된 healthcheck 간격으로 둔다. API의 `JAVA_TOOL_OPTIONS=-Xmx1536m` 및 다른 애플리케이션 설정은 보존했다.
- 제한 변경은 컨테이너 재생성 전까지 실행 중 환경에 반영되지 않는다. NAS 백업 파일은 수정하지 않았다.
- commit/push/build/deploy/restart/Compose up·down은 수행하지 않았다.

## 예산 요약

단위는 MiB다. lab 합계는 `oom_score_adj: 500`으로 표시되는 main lab/security/shadow/games/n8n/db-backup/ARTEx/dolphin 서비스의 제한 합계다. trading 합계는 trading 및 crypto-data Compose의 제한된 컨테이너다. 기타 main 보호 서비스(API, MySQL, web, cloudflared)는 전체 합계에는 포함했다.

| 구분 | 제한 합계 | 설명 |
|---|---:|---|
| lab (+500) | 7,424 MiB (7.25 GiB) | n8n 1536 MiB 반영. 컨테이너 ceiling 합계, 예약량이 아님 |
| trading 보호 서비스 | 4,736 MiB | trading 4,352 + crypto-data 384 |
| 기타 main 보호 서비스 | 4,096 MiB | API 2,560 + MySQL 1,280 + web 128 + cloudflared 128 |
| **모든 설정 상한** | **16,256 MiB** | **VM 11,950 MiB (11.67 GiB) 대비 4,306 MiB 초과** |
| 현재 관측 사용량 | 사용자 제시 근사 약 6 GiB; 나열된 현재값 단순 합계 7,374 MiB (약 7.2 GiB) | Docker stats 목록의 합과 요청에 기재된 근사치가 일치하지 않음. API/n8n peak는 현재값에 더하지 않음 |

상한은 동시에 전부 사용되는 예약량이 아니므로 총합이 VM 메모리보다 크다는 사실만으로 초과 사용을 뜻하지 않는다. 반대로 VM에 전부 수용된다는 보장도 아니다. 관측 합계로 제공된 약 6 GiB는 항목별 현재값을 합한 7,374 MiB와 차이가 있어, 합산값은 나열된 항목을 단순 합산한 값으로 구분해 기록했다. 설정 상한 합계와 관측값은 서로 다른 지표다.

## Compose별 최종 제한표

모든 메모리 값은 MiB이며 각 행의 `mem_limit=memswap_limit`이다. 관측치는 사용자가 제공한 현재값이며 API/n8n은 알려진 peak를 병기했다. `+500` 서비스는 OOM 우선순위가 낮은 lab·보조 서비스다.

| Compose / 서비스 | 관측 MiB (PIDs) | 메모리/swap MiB | PID 제한 | oom_score_adj |
|---|---:|---:|---:|---:|
| main / mysql | 601 (46) | 1280 | 192 | -300 |
| main / db-backup | 1.3 (2) | 128 | 32 | +500 |
| main / api | 1263, peak 1.4 GiB (56) | 2560 | 256 | -300 |
| main / games | 64 (11) | 128 | 32 | +500 |
| main / web | 10 (12) | 128 | 32 | -300 |
| main / cloudflared | 56 (16) | 128 | 32 | -300 |
| main / n8n | 399, peak 1.10 GiB (20) | 1536 | 96 | +500 |
| trading / trading-paper-funding-arb | 328 (1) | 768 | 32 | -300 |
| trading / trading-kr-rotation | 288 (11) | 640 | 32 | -300 |
| trading / trading-us-rotation | 163 (11) | 384 | 32 | -300 |
| trading / trading-coin-swing6 | 367 (11) | 768 | 32 | -300 |
| trading / trading-momentum-rotation | 449 (12) | 1024 | 64 | -500 |
| trading / trading-kr-opening-scan | 21 (1) | 256 | 32 | -300 |
| trading / trading-tick-stream | 142 (12) | 512 | 32 | -300 |
| crypto-data / crypto-tick-stream | 172 (14) | 384 | 32 | -300 |
| shadow / crypto-shadow-predictor | 404 (22) | 768 | 48 | +500 |
| ScopeSentry / mongodb | 313 (45) | 512 | 256 | +500 |
| ScopeSentry / redis | 22 (5) | 128 | 16 | +500 |
| ScopeSentry / scope-sentry | 97 (15) | 256 | 48 | +500 |
| ScopeSentry / scopesentry-scan | 454 (15) | 768 | 1024 | +500 |
| ARTEx / postgres | 67 (10) | 128 | 24 | +500 |
| ARTEx / artex | 59 (12) | 128 | 24 | +500 |
| dolphin / qdrant | 310 (44) | 512 | 96 | +500 |
| dolphin / postgres | 26 (7) | 128 | 16 | +500 |
| dolphin / pipeline | 159 (16) | 256 | 48 | +500 |
| dolphin / chat | 1139 (27) | 2048 | 64 | +500 |

거래 Compose의 제한은 관측값의 1.5배 이상이다. 미관측 profile 서비스(`trading`, `trading-kr-swing`, `trading-us-swing`, `trading-trx-swing`)는 현재 메모리/PID 제한이 없다. 특히 `trading-trx-swing`은 실자금 대상으로 분류되어 재사용 전에 상한 설정이 필요하다.

## 보호 설정과 변경 경계

- API는 `JAVA_TOOL_OPTIONS=-Xmx1536m`와 2,560 MiB 제한을 유지한다.
- API/MySQL/n8n의 PID 상한은 각각 256/192/96으로 설정했다. 다른 `pids_limit` 및 `oom_score_adj` 값은 위 표와 같이 유지했다. 이들은 메모리 부족 상황에서 lab 서비스를 trading/API보다 먼저 희생시키고 과도한 프로세스 생성을 제한한다.
- main MySQL healthcheck의 기존 interval 30초와 start period 30초 설정을 유지했다.
- Compose 설정은 컨테이너 재생성 시 적용된다. 실제 런타임 적용 여부는 재생성 후 별도 확인이 필요하다.

## 검증

- Review2 후속 수정: n8n memory/swap 상한 1536 MiB, API/MySQL/n8n PID 상한 256/192/96. 설정 ceiling은 lab 7,424 MiB, 전체 16,256 MiB이며 VM 11,950 MiB보다 4,306 MiB 높다.
- Watchdog review2 항목: `Docker Desktop`/`Docker` 프로세스를 제한 대기하고 종료 확인 후에만 재개방한다. 30초 engine timeout, 3회 및 최소 6분 streak, 15분 만료, 6분 wake grace skip을 구현했다. PAUSE와 앱 프로세스 부재는 alert-only이며 재시작 시도/쿨다운은 quit 전에 원자 기록한다. swap 경고는 전체의 95% 초과 및 14 GiB 초과 조건과 6시간 rate limit를 적용했다. HOME fallback, dry-run 출력, 1 MiB 단일 세대 로그 회전, 대기 중 lock 갱신을 추가했다. `docker inspect`는 `--format`으로 필요한 세 필드만 읽는다.
- `/opt/anaconda3/bin/python3 -m pytest tests -q` (`trading/`): 7개 모듈 collection 오류 후 중단. `/opt/anaconda3/lib/python3.13/site-packages/pandas_ta/utils/_math.py`의 Numba `fibonacci` 캐시 초기화가 `no locator available`을 냈다. 전체 테스트 본문은 실행되지 않았다.
- `/opt/anaconda3/bin/python3 -m pytest tests/test_docker_watchdog.py -q`: 12 passed.
- `bash -n scripts/docker_watchdog.sh`: exit 0.
- 치환한 plist 임시 사본에 `plutil -lint`: OK.
- `docker compose -f <file> config -q`: Ochestration main, crypto-data, trading (전체 profiles 지정), shadow, dolphin_ai, ScopeSentry, ARTEx artex-docker 총 7개 모두 exit 0. dolphin_ai와 ScopeSentry에서 기존 `version` obsolete 경고만 표시됐다.
- 이 세션에서 `ps -ax -o comm`은 OS 권한 오류, `osascript` System Events 조회는 자동화 오류로 차단됐다. 따라서 프로세스 실측은 하지 않았으며 review2의 호스트 기록과 요구된 이름을 기준으로 처리했다.
- Docker build, restart, deploy 및 Compose up/down은 실행하지 않았다.
