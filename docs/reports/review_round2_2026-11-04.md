# 독립 검토 보고서 round2 (2026-11-04)

판정: **PASS** (BLOCKER/HIGH/MEDIUM 없음, 잔여 LOW 3건)

## a. 1차 지적 6건 해소 여부
1. MEDIUM stale 배너 상시 표시 -> **PASS**. BinanceDisplayService.java:37-41 (stale 60s/3h, TTL 20s/1h 분리), :258-270 (stale = 캐시 없음 OR 마지막 성공 후 임계 초과 OR 백오프 중).
   30초 폴링 실시간 시뮬레이션(scratch, 실제 30s sleep): 정상 3회 stale=false 유지 -> 장애 시작 직후 첫 폴링 false(캐시 나이 30s<60s), 이후 true 4회 -> 복구 후 백오프(60s) 때문에 2회 true, 3회째 false. 장애 때만 true, 복구 지연 약 60-90s로 합리적.
   realized 3h: TTL 1h + 백오프 60s 대비 최대 2회 연속 실패까지 허용하는 값으로 정합. 프론트(trading.tsx:586, types.ts:62)는 accountStale/realizedStale/AsOf를 optional로 올바르게 소비, 값 누락 시 falsy로 배너 미표시. 콜드스타트(캐시 없음)에는 stale=true로 첫 로드 전까지 배너가 잠깐 뜸(허용).
2. MEDIUM 가독성/테스트 부족 -> **PASS**. 코드 다중 행 정리, 테스트 7개 추가(정상 폴링, 하드 타임아웃, 늦은 워커, 4개 상한, 실패 백오프, 복구, realized). `mvn test` 274개 중 BinanceDisplayServiceTest 전부 통과.
3. LOW 스레드 누수/레이스 -> **PASS(잔여 한계 있음)**. Flight 객체 동일성 비교(:132,:144,:153,:174)로 늦은 워커 덮어쓰기 차단, ThreadPoolExecutor 최대 4/SynchronousQueue/AbortPolicy(:48-50)로 스레드 상한, 거절 시 백오프(:162-168). 한계는 아래 b.
4. LOW min_cost 정상경로 변경 -> **PASS**. momentum_rotation_exec.py:166-168 `abs(delta) < min_cost`면 step 보정 전에 스킵(원래 동작과 동일).
5. LOW _amount_step int 해석 / 6. LOW 도달불가 best==current 분기 -> 미변경이나 영향 없음(아래 잔여 LOW).

## b. 새 위험
- [LOW] BinanceDisplayService.java:48-50,162-168 워커 4개가 인터럽트 무시로 영구 점유되면 이후 갱신은 매번 거절+60s 백오프 -> 영구 stale. 복구 경로는 점유 워커가 끝나는 것뿐(keepAlive 30s는 유휴 스레드만). 대시보드엔 "갱신 지연 · 계좌 <마지막 시각>" 배너와 마지막 캐시 값이 계속 표시되어 사용자는 인지 가능, 요청 경로는 영향 없음. 실제 JDK HttpClient는 8s 요청 timeout/인터럽트에 반응하므로 현실 가능성 낮음(미확인: 실제 소켓 hang 재현은 하지 않음). 권고: 모니터링/로그 한 줄(포화 시 WARN) 추가 선택.
- 콜드스타트: account/realized 모두 빈 객체 + Stale=true, AsOf=null 반환 -> 컨트롤러가 equity를 state로 폴백, walletBalance/marginBalance null, entryCapital=기준값 144.01. 프론트는 null을 '-'로 처리(trading.tsx 기존 로직). 문제 없음.
- 가시성: accountCache/incomeCache/RetryAt volatile, Flight는 synchronized 내부 접근, worker/timeout volatile. 요청 경로(pollAccount/Income)는 synchronized 안에서 플래그 검사와 submit(비블로킹, SynchronousQueue 거절 즉시)만 수행. 컨트롤러는 파일 읽기 외 블로킹 없음. 실행기는 전부 데몬 스레드(종료 훅 없음, 읽기 전용이라 무방, LOW).
- [LOW] 테스트 타이밍(5~80ms sleep, 2s await) 의존 -> CI에서 드물게 불안정 가능. 이번 실행은 안정적.

## c. Python diff
- momentum_rotation_exec.py:166-168 min_cost 스킵은 `_plan_resize`에서 롱/숏/trim/up 모두 동일하게 적용되며 이전 조건(`abs(delta) < min_cost`)과 동일 -> 정상 리사이즈 불변. 마진모드(:292-297)와 apply_targets 순서 변경 없음(round1과 동일, 신규 진입 직전에만).
- QNT 재현(실제 ccxt 4.4.68): 현재 0.1/목표 $30.24/가격 193 -> InvalidOrder 발생하나 흡수, 롱·숏 모두 "표현 불가" 스킵, errors 없음. 0.5->down 0.3, 0.4->down 0.2 정상.

## d. 테스트 직접 실행
- Python: python3.12 venv + pandas-ta 0.4.71b0 설치하여 `trading/tests` **112 passed** (구현자 주장 재현). 1차의 106 vs 111 차이는 3.15 venv에 pandas_ta 부재 때문.
- Java JDK21: 274 tests, 실패 2건은 기존(LinkCollectControllerTest, ArchiveMaintenanceServiceTest), 오류 0. 구현자가 말한 "샌드박스 네트워크 제한 오류 3건"은 이 환경에서 재현되지 않음(샌드박스 한정 문제로 판단, stash 비교는 불필요해 수행하지 않음 -> 작업트리 변경 없음).
- 프론트: tsc 오류 없음, build 성공(build-info.json 원복).

## e. 범위
- 변경 파일 6개+테스트 1개, round1과 동일. 컨트롤러는 포맷 정리가 대부분(로직 불변: stale 필드 추가 외). 전략 파라미터·킬·가드·타이머 불변. 단 컨트롤러의 대규모 재포맷은 diff 노이즈(LOW, 기능 영향 없음).

## f. 배포 최종안
1. 백엔드+프론트 먼저 배포(거래와 독립, 먹통 재발 방지). 확인: /state 응답 시간, accountStale=false, accountAsOf 갱신, 헬스체크.
2. 봇 재시작은 11-05 09:41 UTC 리밸런스 수 시간 전, 주문 진행 중이 아닐 때. state 스키마 변경 없음.
3. 재시작 후 체크: 봇 정상 기동/킬·가드 상태, 로그에 set_margin_mode 경고 폭주 없는지, 리밸런스 후 [RESIZE-SKIP]·errors(QNT precision 예외 없음)·BCH/XRP 신규 진입 시 cross 확인.

## 판정: PASS
근거: BLOCKER/HIGH/MEDIUM 없음, 1차 지적 전부 해소, 테스트 Python 112/Java 신규 실패 없음/프론트 통과.
미확인: 실제 소켓 hang에서의 JDK HttpClient 거동, 실계좌 포지션·마진 모드, 프론트 실제 화면 렌더링.
