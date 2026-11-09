# 독립 검토 보고서 round1 (2026-11-04)

판정: **PASS** (BLOCKER/HIGH 없음, MEDIUM 2 / LOW 4 권고)

## 실행 검증 결과 (구현자 주장 대조)
- Java (JDK21, `mvn -q test`): 269 tests, 실패 2건 = 기존 실패(LinkCollectControllerTest.returnsRawJsonForAllEndpoints, ArchiveMaintenanceServiceTest.mergeIfSameTopic_...)뿐. 신규 실패 없음, BinanceDisplayServiceTest 2건 통과.
- Python(격리 venv, ccxt 4.4.68): 106 passed. pandas_ta 미설치(py3.15 venv)로 test_equity_peer_pairs / test_equity_trx_dca_transfer 수집 오류, test_equity_psar_transfer 1건 실패 -> 전부 변경과 무관한 환경 문제. "111개 통과" 주장은 pandas_ta 포함 환경 기준으로 재현 불가(미확인). 변경 관련(test_resize_positions 등)은 전부 통과.
- 프론트: `npx tsc --noEmit` 오류 없음, `npm run build` 성공, build-info.json 원복 완료.

## 항목별 결과
### A. 거래 로직 (momentum_rotation_exec.py)
- 실행 순서(close -> trim(down) -> 신규 -> top-up(up)) 보존: apply_targets 구조 불변, plans 계산 루프만 SKIP 로그 추가.
- QNT 재현(실제 ccxt 4.4.68 amount_to_precision, 시장 precision 0.1/min 0.1): 0.0567 요청 시 InvalidOrder("must be greater than minimum amount precision")가 실제로 발생 -> 이제 try/except로 흡수. 현재 0.1/목표 $30.24/가격 193: 후보 0.2(=$38.6, 오차 27.6%>15%) -> "표현 불가" 조용한 스킵, errors 비어 있음, 주문 없음. 숏 포지션 동일 결과. 0.5 -> down 0.3, 0.4 -> down 0.2 등 정상 trim 정상. 롱/숏/ reduceOnly 방향 코드 불변.
- down 경로에서 `amount=min(amount, contracts)` 클램프가 삭제됐으나 이후 `amount >= contracts` 스킵 조건과 동치라 결과 동일.
- [LOW] momentum_rotation_exec.py:166-187 (`_plan_resize`) 정상 경로 동작 미세 변경: 이전에는 delta < min_cost면 무조건 스킵, 이제는 step 단위 폴백을 시도해 목표 허용오차 이내로 들어오면 실제 주문. step이 매우 큰 코인에서만 발생 가능하며 최종 min_cost/min_amount 검사 존재. 사양 "정상 리사이즈 불변"과 엄밀히는 다르나 허용오차 개선 방향이라 위험 낮음. 
- [LOW] `_amount_step`(:126-130): precision이 int면 소수자릿수로 해석. TICK_SIZE 모드에서 정수 step(예: 1)이 int로 오면 0.1로 오해 가능. ccxt 4.4.68은 float 반환이라 현재 문제 없음.
- [LOW] `best == current` 분기(:182)는 candidates가 방향 필터를 거쳐 사실상 도달 불가(방어 코드).
- 마진 부족 처리(_exec_resize) 불변.

### B. 마진모드 (:289-295)
- 신규 진입 직전(최소명목/수량 검사 통과 후, set_leverage 직전)에 위치. 보유 유지 종목은 retained라 이 경로에 오지 않음 -> 기존 포지션 마진 변경 호출 없음. 방향 전환 종목은 close 이후라 포지션 없는 상태에서 호출.
- 예외는 전부 try/except 흡수, 진입 계속. ccxt 4.4.68은 -4046(No need...)을 기본 삼킴(throwMarginModeAlreadySet False)이라 이중 방어. -4047/-4048은 경고 로그 후 진입 계속(테스트로 확인).
- 호출 증가: 신규 진입당 1회(weight 1). 레이트리밋 영향 무시 가능. 심볼은 perp_symbol 결과(QNT/USDT:USDT) 그대로 사용.
- [LOW] 포지션 모드(hedge/one-way)는 코드 가정 없음; multi-asset 모드 계정이면 매 진입 경고 로그(-4168 류) -- 무해. 실거래 계정 모드는 미확인.

### C. 동시성 (BinanceDisplayService.java)
- 전역 락 제거 확인. account()/realized()는 캐시 snapshot 반환 + synchronized 짧은 플래그 검사만(I/O 없음). 컨트롤러 /state 경로에 네트워크 호출 없음(파일 읽기만). 싱글턴 HttpClient(connectTimeout 5s), 요청 timeout 8s, 데몬 스레드, 단일 flight(accountFlight/incomeFlight), 실패/타임아웃 60s 백오프, realized 루프 페이지 상한 10 확인.
- 직접 검증(scratchpad): 계속 spin하는 비-인터럽트 fetcher에서도 호출 지연 0ms, flight 해제·60s 백오프 정상.
- [MEDIUM] BinanceDisplayService.java: stale 기준(20s)이 캐시 TTL(20s)과 같고 갱신이 "요청이 TTL 경과 후 들어와야" 시작되며 그 요청은 이전 캐시를 반환. 프론트는 30초 폴링(trading.tsx:545) -> 정상 운영에서도 매 응답이 age>=20s라 accountStale=true. 실측: TTL 21s 후 첫 응답 stale=true, 이후 갱신. 결과적으로 trading.tsx:586 "갱신 지연" 배너가 항상 표시될 가능성 높음(오경보). 권고: stale 임계를 TTL보다 크게(예: TTL*3=60s, income은 2h) 또는 마지막 성공 이후 N회 실패 기준으로 변경, 혹은 주기적 백그라운드 스케줄러로 선갱신.
- [MEDIUM] 코드 가독성: 한 줄 압축 메서드가 많고(예: pollAccount/loadIncome), 테스트가 stale 플래그·타임아웃 watcher cancel·realized 경로를 검증하지 않음. 권고: stale 플래그 테스트, 타임아웃 후 flight 해제 테스트 추가.
- [LOW] 타임아웃 watcher가 별도 스레드를 점유(폴링당 워커 1 + watcher 1), 풀은 unbounded cached. 워커가 인터럽트에 반응 않는 진짜 hang이면 60s 주기로 스레드 1개씩 누수(스핀 fetcher로 확인). 실제 JDK HttpClient.send는 인터럽트/8s timeout에 반응해 현실 위험 낮음. 또한 좀비 워커가 늦게 끝나면 새 flight의 플래그를 false로 덮고 backoff를 0으로 리셋하는 경미한 레이스 존재. 권고: 세대(generation) 토큰 또는 sendAsync+orTimeout, 풀 상한.
- 기준값 144.01/2026-11-02T00:00Z 규칙: 컨트롤러 코드 불변, 캐시 미적재(콜드스타트) 시 transfers 비어 baseline만 표시(현 시점 이후 TRANSFER 없으면 동일).

### D. 위 "실행 검증 결과" 참조.

### E. 범위
- 변경 파일은 요청 범위 내. 전략 파라미터/킬/가드/타이머 변경 없음. 프론트는 stale 배너 1줄 + 타입 필드 추가로 사양(stale/asOf 표시) 범위.
- [LOW] 작업트리 루트의 `Oops.rej` 및 research 산출물은 이번 변경과 무관한 untracked: 커밋에 포함 금지.

### F. 배포
- Python: 새 state 필드/`_DEFAULT_STATE` 변경 없음 -> state 호환 문제 없음. 봇 재시작 자체는 주문을 내지 않음(리밸런스 타이머에 의해서만 실행) -- 코드상 근거, 실제 컨테이너 동작은 미확인.
- 권고 순서: (1) 백엔드(Java) + 프론트 먼저 배포(먹통 재발 방지, 거래와 독립), (2) 봇 컨테이너는 2026-11-05 09:41 UTC 리밸런스 충분히 전(수 시간 이상), 포지션 변경 중이 아닌 시점에 재시작, 재시작 후 로그에서 [RESIZE-SKIP]/set_margin_mode 경고 확인. (3) 가능하면 MEDIUM stale 임계 수정 후 배포.

## 판정: PASS
근거: BLOCKER/HIGH 없음. 거래 로직 회귀 없음(QNT 예외 제거, 순서/방향/reduceOnly 보존), 마진모드 실패가 진입을 막지 않음, Java 신규 테스트 실패 없음, 락 제거 및 요청 경로 논블로킹 확인. 단 stale 배너 상시 표시(MEDIUM)는 배포 전 수정 권장.
미확인: 실제 네트워크 hang 하의 JDK HttpClient 동작, pandas_ta 포함 전체 Python 111개, 실계좌 포지션/멀티에셋 모드, 프론트 실제 렌더링.
