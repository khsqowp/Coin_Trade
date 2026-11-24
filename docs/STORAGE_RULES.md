# 디렉터리·파일 저장 규칙 (Claude·ChatGPT/Codex 공용, 강제)

기준일 2026-11-24. 사용자 절대 규칙이다. 위반하면 즉시 멈추고 보고한다.

## 0. 절대 금지

- **`/Users/user/CODE/` 바로 아래(루트)에 투자·코인·주식·전략·백테스트·시장데이터·공시 관련 새 폴더나 파일을 만들지 않는다.** 이름이 무엇이든(`temp_*`, `*_backup`, `*_merge`, `salvage`, `trading_*`, `research_*` 등) 금지다. 필요한 모든 것은 `Coin_Trade/` 안이나 아래 §2의 지정 위치에 둔다.
- `/Users/user/CODE/Ochestration/` 에는 거래·연구 파일을 만들지 않는다 (사이트 전용).
- CODE 루트의 새 폴더 생성이 정말 필요해 보이면 만들지 말고 사용자에게 먼저 보고한다.

## 1. 어디에 무엇을 두는가

| 종류 | 위치 | git |
|---|---|---|
| 거래·전략 연구·백테스트·현황판·수집 코드와 문서 | `/Users/user/CODE/Coin_Trade/` (연구 루프는 `scratchpad/strategy_bt/orderblock_loop/`) | 추적 |
| 대용량 데이터(가격, 공시 PDF, 캐시, 포워드 DB 복사본, 임시 산출물) | `/Users/user/CODE/trading_data/{external,cache,...}` (환경변수 `TRADING_DATA_DIR`) | 저장소 밖 |
| 연구 실행 로그·센티널 | `trading_data/cache/orderblock/runs/` | 저장소 밖 |
| 옛 백업·잔재 보관 | `Coin_Trade/_moved_from_CODE_*/` | 비추적(.gitignore) |
| 임시 스크립트·중간 파일 (세션용) | 세션 scratchpad 디렉터리 (Claude) / `Coin_Trade/scratchpad/` (Codex) | 세션 종료 시 폐기 또는 정리 |

`trading_data` 는 저장소 밖 단일 데이터 저장소이며 CODE 루트에서 유일하게 허용되는 투자 관련 폴더다. 새 하위 폴더는 그 안에서만 만든다.

## 2. 파일 규칙

1. 데이터 파일(csv/parquet/pdf/db)을 git 저장소에 넣지 않는다. 작은 결과 csv(수 MB)와 장부(`TRAIN_TRIALS.csv`)만 예외다.
2. 비밀값(API 키·비밀번호·토큰)은 코드·로그·문서·커밋에 쓰지 않는다. 환경변수 이름만 적는다.
3. 사용자 지시 없이 파일을 삭제하지 않는다. 지우기 전 목록→검증→삭제 순서를 따르고 `rm -r` 을 넓은 경로에 쓰지 않는다. 옛 파일은 `_moved_from_CODE_*` 로 옮긴다.
4. 연구 장부(`TRAIN_TRIALS.csv`)는 수정하지 않고 행을 추가만 한다. 모든 시도는 장부에 남는다.
5. 새 연구 라운드의 코드·사전등록(`PREREG.md`)·보고서(`REPORT_*.md`)는 `scratchpad/strategy_bt/orderblock_loop/` 에 둔다.
6. 커밋·푸시는 작업 단위마다 자동으로 한다 (Coin_Trade). Ochestration 에는 거래 파일을 커밋하지 않는다.
7. Codex 는 항상 `codex exec -C /Users/user/CODE/Coin_Trade` 로 실행한다. `--add-dir /Users/user/CODE/trading_data` 만 추가로 허용한다.

## 3. 우선순위

연구 속도가 우선이다. 병렬 실행·CPU 사용에는 제한을 두지 않는다. 지키는 것은 연구 방법 규칙(사전등록, 시도 횟수 장부, TEST 분리)과 위 저장 규칙이다.

## 4. 이 문서의 위치

- Codex: `Coin_Trade/AGENTS.md` 와 `~/.codex/AGENTS.md` 가 이 문서를 가리킨다.
- Claude: `~/.claude/rules/coin-trade-only.md`, `Coin_Trade/CLAUDE.md`, `Ochestration/CLAUDE.md` 가 이 문서를 가리킨다.
