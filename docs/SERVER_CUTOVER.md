# 서버 이전 절차: Ochestration/trading -> Coin_Trade (미실행, 사용자 승인 후)

현재(2026-11-22 확인): 거래 컨테이너 약 14개가 linuxserver 의 `~/CODE/Ochestration` 에서
`docker-compose.trading.yml`(compose 프로젝트명 `ochestration-trading`, `build: ./trading`)로 돌고 있다.
실거래 봇(momentum-rotation 등)이 포함되어 있으므로 아래는 **한 단계씩 확인하며** 진행한다. 이 문서의 어떤 명령도 아직 실행하지 않았다.

## 새 구조
- Coin_Trade 가 코드·Dockerfile·compose 를 소유: `docker-compose.yml`(= 구 trading compose, 프로젝트명 `ochestration-trading` 유지, build: .), `docker-compose.crypto-data.yml`.
- 프로젝트명을 바꾸지 않는 이유: external 볼륨(`ochestration_trading_*`)과 사이트 api 의 `:ro` 읽기 연결을 그대로 유지하기 위해. 컨테이너 이름 변경은 별도 단계.
- Ochestration 사이트는 조회/조작 연동만 유지(볼륨 :ro, 필요한 API). 거래 코드·compose 는 없다.

## 서버 선행 점검 (읽기 전용)
1. `docker ps` 로 14개 컨테이너 상태·재시작 횟수 기록. 실거래 봇 포지션 상태 확인(열린 포지션 없을 때 진행 권장).
2. 바인드 마운트 디렉터리 위치 확인: `~/CODE/Ochestration/{trading-forward-test,trading-forward-test-12h,trading-forward-test-jbb-1h,trading-tick-archive,trading-crypto-paper-state,.kis-cache}` 및 `.env`.
3. 백업: 위 상태 디렉터리와 `.env` 를 `~/backup_cutover_<날짜>/` 로 복사 후 크기·행수 확인.

## 이전
1. 서버에 Coin_Trade 체크아웃(`~/CODE/Coin_Trade`). 원격이 공개이므로 `.env` 는 절대 커밋하지 않는다(.gitignore 처리됨).
2. `.env` 와 상태 디렉터리를 Coin_Trade 아래로 `mv`(같은 파일시스템) 또는 compose 의 바인드 경로를 절대경로로 수정.
3. `docker compose -f docker-compose.yml build` 후 프로파일별로 하나씩 `up -d`. 같은 프로젝트명이므로 compose 가 컨테이너를 재생성한다 = 봇 재시작(짧은 중단). 실거래 봇(momentum-rotation)은 마지막, 다른 봇이 정상인 것을 확인한 뒤.
4. 각 봇 로그·하트비트·상태 파일이 이어지는지 확인(`scripts/forward_test_status.sh` 등).
5. 사이트 api 가 볼륨을 계속 읽는지 확인.

## Ochestration 정리 (이전 검증 후)
- `trading/` 디렉터리, `docker-compose.trading.yml`, `docker-compose.crypto-data.yml` 삭제.
- `scripts/linux/auto_deploy.sh` 가 `-f docker-compose.crypto-data.yml` 를 쓰고 `trading/*` 변경을 스킵하는 로직 수정.
- `scripts/linux/nas_backup.sh` 의 ROOT 기반 경로(trading-tick-archive, trading-crypto-paper-state 등) 수정.
- Ochestration/CLAUDE.md 의 trading 설명 갱신.
- 이 정리 커밋을 push 하기 전에 위 수정이 서버에 먼저 적용돼야 한다(자동배포가 ff 병합하며 trading/ 를 지울 수 있음).

## 롤백
이전 직전 백업과 구 Ochestration 체크아웃(삭제 전)이 있으면 같은 프로젝트명으로 구 compose 를 다시 `up -d`.
