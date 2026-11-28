# 디렉터리·파일 저장 규칙 (Claude·ChatGPT/Codex 공용, 강제)

## 2026-11-25 절대 강제 데이터 경로

- **실행 전 경로 봉쇄:** 거래·연구 관련 모든 명령, 테스트, 하위 프로세스, 브라우저/데이터 도구와 위임 에이전트는 실행 때마다 정확한 `TRADING_DATA_DIR=/home/noroot/CODE/Coin_Trade/trading_data`를 받아야 한다. 누락·불일치 시 어떤 시장 데이터도 열지 않고 중단한다.
- 홈 디렉터리 기본값, 상대경로, 시스템 임시 폴더 또는 라이브러리 자동 캐시·임시 저장을 연구 경로로 쓰지 않는다. 코드 기본값·fallback과 자식 프로세스 환경까지 추적해 저장소 내부임을 증명할 수 없으면 실행하지 않는다. 실행 후 새 생성물의 위치도 검증한다.
- 위임 작업에는 정규 데이터 경로, 폐기 경로 미접근, 저장소 외부 산출 금지, 실행 전·후 확인 규칙을 명시적으로 전달한다. 에이전트가 이를 보장하지 못하면 위임을 취소한다.
- 모든 거래·연구 파일은 `/home/noroot/CODE/Coin_Trade/` 안에서만 생성·복사·수정한다. 데이터 전용 경로는 `/home/noroot/CODE/Coin_Trade/trading_data/`다.
- `/home/noroot/CODE/trading_data/`는 폐기된 경로다. 읽기·쓰기·다운로드·복사·캐시·로그·임시파일·디렉터리 생성·이동·존재 확인을 전부 금지한다.
- 모든 실행에서 `TRADING_DATA_DIR=/home/noroot/CODE/Coin_Trade/trading_data`를 사용한다. 코드의 기본값도 이 정확한 경로로 한다.
- 이 경계는 주 에이전트와 위임 에이전트, 셸·Python·노트북·브라우저 다운로드, 라이브러리 캐시·임시파일 등 모든 실행 주체에 똑같이 적용한다. 저장소 밖에 기본 저장하는 도구는 출력 위치를 고정할 수 없으면 실행하지 않는다.
- 실행 전에는 환경변수의 정확한 값을 검증하고 코드·설정·인자에 저장소 밖 데이터 경로가 없는지 확인한다. 폐기 경로는 존재 확인도 금지하므로 `ls`, `stat`, `find` 등으로 조회하지 않는다.
- 실행 전 저장소 루트·데이터 루트·코드 기본값/fallback과 하위 프로세스의 환경변수 전달을 확인한다. 출력될 데이터·캐시·로그·임시파일의 실제 경로를 저장소 내부로 증명할 수 없으면 실행하지 않는다. 실행 직후 출력 경로를 재확인한다. 저장소 밖 생성 또는 경로 불확실성이 발견되면 파일을 열거나 옮기거나 삭제하지 말고 추가 작업을 중단해 사용자에게 보고한다.
- 임시 파일·다운로드 조각·캐시·로그도 `/home/noroot/CODE/Coin_Trade/` 안에만 둔다. 외부 경로 생성을 막을 수 없는 도구는 실행하지 말고 저장소 내부 대안을 사용한다.
- 저장소 내부 데이터 폴더는 Git 추적에서 제외한다. 기존 외부 저장 경로 규칙은 이 사용자 지시에 충돌하는 범위에서 폐기한다.

기준일 2026-11-25. 사용자 절대 규칙이다. 위반하면 즉시 멈추고 보고한다.

## 0. 절대 금지

- **`/home/noroot/CODE/` 바로 아래(루트)에 투자·코인·주식·전략·백테스트·시장데이터·공시 관련 새 폴더나 파일을 만들지 않는다.** 이름이 무엇이든(`temp_*`, `*_backup`, `*_merge`, `salvage`, `trading_*`, `research_*` 등) 금지다. 필요한 모든 것은 `Coin_Trade/` 안이나 아래 §2의 지정 위치에 둔다.
- `/home/noroot/CODE/Ochestration/` 에는 거래·연구 파일을 만들지 않는다 (사이트 전용).
- CODE 루트의 새 폴더 생성이 정말 필요해 보이면 만들지 말고 사용자에게 먼저 보고한다.

## 1. 어디에 무엇을 두는가

| 종류 | 위치 | git |
|---|---|---|
| 거래·전략 연구·백테스트·현황판·수집 코드와 문서 | `/home/noroot/CODE/Coin_Trade/` (연구 루프는 `scratchpad/strategy_bt/orderblock_loop/`) | 추적 |
| 대용량 데이터(가격, 공시 PDF, 캐시, 포워드 DB 복사본, 임시 산출물) | `/home/noroot/CODE/Coin_Trade/trading_data/{external,cache,...}` (환경변수 `TRADING_DATA_DIR`) | `.gitignore` 제외 |
| 연구 실행 로그·센티널 | `Coin_Trade/trading_data/cache/orderblock/runs/` | `.gitignore` 제외 |
| 옛 백업·잔재 보관 | `Coin_Trade/_moved_from_CODE_*/` | 비추적(.gitignore) |
| 임시 스크립트·중간 파일 (세션용) | `Coin_Trade/scratchpad/` 안의 지정 하위 폴더 | 저장소 내부 규칙에 따라 보존·정리 |

`Coin_Trade/trading_data` 는 모든 대용량 데이터의 유일한 저장소다. 대용량 파일을 포함해 연구 작업 중 생성·다운로드·캐시·로그·임시 파일을 `/home/noroot/CODE/Coin_Trade/` 바깥에 만들지 않는다. 새 데이터 하위 폴더는 저장소 내부 `trading_data/` 아래에만 만든다. 폐기 경로 `/home/noroot/CODE/trading_data/`는 읽기·쓰기·다운로드·복사·캐시·로그·임시 파일 생성·디렉터리 생성·존재 확인을 포함해 일절 접근하지 않는다. 해당 경로를 참조하는 실행은 시작 전에 중단한다.

## 2. 파일 규칙

1. 데이터 파일(csv/parquet/pdf/db)을 git 저장소에 넣지 않는다. 작은 결과 csv(수 MB)와 장부(`TRAIN_TRIALS.csv`)만 예외다.
2. 비밀값(API 키·비밀번호·토큰)은 코드·로그·문서·커밋에 쓰지 않는다. 환경변수 이름만 적는다.
3. 사용자 지시 없이 파일을 삭제하거나 옮기지 않는다. 허가된 삭제는 목록→검증→삭제 순서를 따르고 `rm -r` 을 넓은 경로에 쓰지 않는다. 저장소 밖의 옛 자료는 임의로 조회·이동·복사하지 않는다.
4. 연구 장부(`TRAIN_TRIALS.csv`)는 수정하지 않고 행을 추가만 한다. 모든 시도는 장부에 남는다.
5. 새 연구 라운드의 코드·사전등록(`PREREG.md`)·보고서(`REPORT_*.md`)는 `scratchpad/strategy_bt/orderblock_loop/` 에 둔다.
6. 사용자가 명시적으로 요청한 경우에만 커밋·푸시한다. Ochestration 에 거래 파일을 커밋하지 않는다.
7. Codex 는 항상 `codex exec -C /home/noroot/CODE/Coin_Trade --add-dir /home/noroot/CODE/Coin_Trade/trading_data` 로 실행한다. 추가 쓰기 경로를 지정하지 않는다. 모든 실행 명령에 `TRADING_DATA_DIR=/home/noroot/CODE/Coin_Trade/trading_data`를 명시하고, 코드 기본값도 이 경로로 둔다. 환경변수로 저장소 밖 경로를 지정하지 않는다.

## 3. 우선순위

연구 속도가 우선이다. 병렬 실행·CPU 사용에는 제한을 두지 않는다. 지키는 것은 연구 방법 규칙(사전등록, 시도 횟수 장부, TEST 분리)과 위 저장 규칙이다.

## 4. 이 문서의 위치

- Codex: `Coin_Trade/AGENTS.md` 와 `~/.codex/AGENTS.md` 가 이 문서를 가리킨다.
- Claude: `~/.claude/rules/coin-trade-only.md`, `Coin_Trade/CLAUDE.md`, `Ochestration/CLAUDE.md` 가 이 문서를 가리킨다.
