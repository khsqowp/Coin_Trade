# oracle_server — 작업 가이드

이 디렉터리는 **Ochestration/linuxserver 스택과 무관한 별개 인프라**를 다루는 로컬 작업 폴더다. 같은 사람이 운영한다는 것 말고는 공유하는 게 없음 — 같은 Docker 네트워크도, 같은 인증도 아니다. 전체 그림은 `/Users/user/CODE/Ochestration/CLAUDE.md`에 있고, 거기서도 이 문서를 가리킨다.

## 이 서버는 뭔가

원격 **Oracle Cloud(OCI) 무료 티어 VPS** 한 대. 코드/스크립트는 여기 로컬 폴더에 쌓아두고, 실제 서비스는 SSH로 들어가서 그 서버 위에서 돈다. 이 폴더 자체는 Git 저장소 아님(별도 `.git` 없음), 그냥 작업 스테이징 공간.

**스펙(2026-10-25 기준 대화 기록 — 재검증 전까지는 참고용으로만 취급)**: ARM64, 2 OCPU, RAM 약 10~11GB, 디스크 173GB, Oracle Linux 9.8 aarch64.

## 접속

- SSH 유저: `opc` (주의: `ocp`로 틀리게 치면 `Permission denied (publickey)` 남)
- 호스트: `152.67.206.89` (2026-10-25 시점 기록 — OCI 프리티어는 재부팅 시 IP 바뀔 수 있어서 최신 IP인지 확인 필요)
- 키 파일: 이 디렉터리의 `ssh-key-2026-10-24.key` (권한 600이어야 함, `.pub`도 같이 있음)
- `~/.ssh/config`에 별도 alias 없음(`linuxserver`처럼 등록 안 돼 있음) — 접속은 매번:
  ```
  ssh -i /Users/user/CODE/oracle_server/ssh-key-2026-10-24.key opc@152.67.206.89
  ```

## 용도

Hermes라는 이름의 트레이딩 리서치 멀티에이전트 파이프라인. 코인(Binance) + 미국주식 + 한국주식 세 트랙. **실거래 금지가 명시적 전제** — Freqtrade는 dry-run, 가상 1,000 USDT로만 테스트. 원격 서버의 `~/trading/` 아래 파이프라인(`~/trading/pipeline/driver.py`)이 있고 구조는:

```
데이터 수집(Binance 공개 시세, KIS 모의) → Agent A(시장분석/가설) → Agent B(전략코드/실행) → Agent C(독립검증/반증) → 백테스트·통계 판정
```

Researcher / Engineer / Auditor / 비-LLM Risk Engine 역할 분리, future-leak(미래 참조) 오류 탐지, 재현성 테스트까지 구성돼 있다고 기록됨.

**80/443 포트는 의도적으로 열어둔 상태 유지** — 사용자가 "웹 사용 예정"이라 명시, 임의로 막지 말 것.

## 미해결 보안 후속조치 (중요)

2026-10-25 작업 중 `.env` 점검 명령이 `KEY: value` 형식 줄 때문에 **Telegram 봇 토큰 값이 로그/에이전트 세션 출력에 노출**된 사고가 있었다. 당시 `~/trading/.env`, `pipeline/secrets/kis.env`, `pipeline/secrets/llm.env` 권한은 600으로 맞췄다고 기록돼 있지만, **토큰 자체를 회전(재발급)했는지는 끝까지 확인되지 않았다.** 이 서버를 다시 만질 일 있으면 먼저 이것부터 확인할 것 — 회전 안 됐으면 지금이라도 해야 함.

또한 `/home/opc/trading/.env`에 Binance, KIS 모의, **TOSS 실거래 키**가 들어있다고 기록됨 — 실거래는 금지 상태이므로 이 키가 실제로 호출되는 경로 없는지도 재확인 대상.

## 이 로컬 폴더에 있는 파일들

분석/백테스트 산출물 — 원격 서버에 자동 배포되는 게 아니라 로컬 분석용:
- `cointrade_us_reconciliation_audit.md`, `append_backtest_baselines.py`, `ma40_weekly_backtest.py`, `source_collector_backtest.py`, `us_cointrade_independent.py`
- `Source_Collector_latest/`, `source_collector_backtest_results/`, `My_Archive_LinkCollect/`
- `대화기록_Oracle_Hermes_트레이딩_2026-10-25.md` — 위 내용 전부의 원 출처. 이 문서의 모든 "기록됨" 표현은 이 파일에 근거하며, 원격 서버 상태를 다시 접속해 확인한 게 아니라는 점이 그 문서 안에도 명시돼 있다.

## Ochestration/linuxserver와의 관계

없음. 같은 Cloudflare 계정(`khsqowp1.my`)을 쓸 수는 있지만 이 서버용 터널/라우트는 별도로 설정해야 하며, 현재 Ochestration 터널(Tunnel ID `cc985378-...`)에는 이 서버가 연결돼 있지 않다. 인증 쿠키(`orchestration_session`)도 공유 안 됨.
