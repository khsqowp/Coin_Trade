# Coin_Trade — 거래·전략연구 전용 저장소 (Claude/Codex 필수 규칙)

## 절대 규칙 (사용자가 수십 번 강조함 — 어기면 안 됨)
1. **코인·주식 거래 로직, 전략 연구, 백테스트 하네스, 연구 현황판, 공시/데이터 수집 코드, 거래 봇 컨테이너 정의는 전부 `/Users/user/CODE/Coin_Trade` 에서만 만들고 기록한다.** 이 폴더는 리눅스 서버에도 둔다.
2. **`/Users/user/CODE/Ochestration` 은 사용자의 사이트(보안·사이트 목적) 전용이다.** 거래/연구 파일을 거기에 만들지 않는다. Ochestration 사이트는 거래 상태를 읽어 보여주고(조회) 매도·재진입 같은 조작 요청을 보낼 수는 있지만, 거래 컨테이너는 이 저장소의 별도 compose 프로젝트로 돌며 사이트 재배포와 독립이다.
3. 세션이 시작되면 작업 디렉터리가 Coin_Trade 인지 먼저 확인한다. 경로에 `Ochestration/trading` 이 나오면 즉시 멈추고 사용자에게 보고한다.
4. Codex 는 항상 `-C /Users/user/CODE/Coin_Trade` 로 실행한다. 다른 세션에 작업을 시킬 때도 Coin_Trade 경로만 준다.
5. 대용량 데이터만 저장소 밖 `~/CODE/trading_data/`.
6. 원격(GitHub Coin_Trade)이 공개일 수 있다. push 는 사용자 확인 후.
세부 연구 규칙은 `AGENTS.md`. 서버 이전 절차는 `docs/SERVER_CUTOVER.md`.


## 저장 규칙 (강제)
- `/Users/user/CODE/` 루트에 투자 관련 새 폴더/파일 금지. 디렉터리·파일 저장 규칙 전체는 `docs/STORAGE_RULES.md`. 속도 우선(CPU·동시 실행 제한 없음).
