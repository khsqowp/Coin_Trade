# R37 — BOS 후 4시간 이내 신선한 오더블록 재방문

## 가설·중복 경계

R14는 4h BOS 이후 24개 1h봉 이내 첫 재방문을 모두 허용한다. **BOS 확정 후 한 개 상위 4h 주기, 즉 최대 4개 완료 1h봉 안에 첫 재방문한 구역은 아직 새로운 관심·잔여 주문이 집중된 상태여서 늦게 재방문한 구역보다 반응 품질이 높을 수 있다.**

R21–R36에서 pre-BOS sweep·confirmation·funding·가격 위치·확인봉 꼬리 등은 시험했지만, 확인된 문서 검색 범위에서는 “4h BOS close 이후 첫 OB touch까지의 경과시간 1–4개의 1h봉” 필터를 찾지 못했다. 이는 저장소 범위에 대한 중복 판단이며, R14 종속 시간 하위집단이지 독립 전략 증거가 아니다.

## 고정 규칙

- **기본 흐름:** R14 고정 4h `bos_origin` → 1h 첫 구역 접촉·중앙값 방향 회복 → 다음 1h 시가 진입.
- **활성·경과 정의:** 4h BOS 확인 시각에 맞춘 1h `signal_index`에서 zone age 0으로 활성화한다. 확인봉 `confirmation_index`의 정수 경과봉은 `age = confirmation_index - zone.signal_index`다. age 1·2·3·4만 허용하고 age 0 및 age 5 이상은 거래하지 않는다. 4개 1h봉은 BOS 확정 뒤 한 개 4h 주기 안의 완료 확인봉이다.
- **만료/소진:** 1~4봉 안에서 첫 접촉이 없으면 age 5 첫 기회에서 거부되어 zone은 R14와 동일하게 소진된다. 먼저 무효화되거나 새 zone에 의해 대체되는 규칙은 R14 그대로다. 지연 재접촉이나 같은 zone 재진입은 없다.
- **기타:** R14 distal `0.10×4h BOS ATR14` stop, `0.50R` target, 최대 24개 1h봉, 동시 장벽 stop 우선, 왕복 12bp, `adverse_only` funding, 고정 35심볼·TRAIN cutoff `2023-11-06T16:00:00Z`를 유지한다. wick, funding polarity, range location, FVG, sweep 조건을 추가하지 않는다.

## 자료·실행 게이트

- 기존 Binance USD-M 로컬 TRAIN bars만 사용한다. OOS/TEST, 2026-06-01 이후 데이터, 새 다운로드, 네트워크, 실주문은 금지한다.
- R36 포함 후 사전 장부는 4,193행, 계획 이번 포함 분모는 4,194다. 중복 R37·전역 writer·lock·코드/상세/master prereg hash·split cutoff·30개 미만 cutoff-safe symbols·40GiB 미만 여유공간이면 시장 행을 열기 전에 중단한다.
- 단일 설정 1회다. 실패·성공 모두 재실행/시간창 조정/사후 하위집단 선택은 금지한다. append가 불확실하면 장부 대사 전 재시도하지 않는다.

## 판정선

- TRAIN 선별선은 scoreable 신호 N≥200, 전체 발행 신호 M2≥75%, 비용 후 EV≥+15bp, PF≥1.30 모두 충족이다. 하나라도 미달이면 반려한다.
- 최종 G는 OOS M2≥80%, 비중복 OOS N≥200, 비용 후 EV≥+15bp, PF≥1.30, annualized Sharpe≥1.0, MDD < 양의 OOS 수익 절반, Bonferroni·Reality Check/SPA·Deflated Sharpe, 무작위 진입·순환이동 귀무, 2배 비용·1봉 지연·plateau·약세장·미사용 심볼군·PIT·데이터 권리 게이트를 모두 유지한다.
- 2018 USD-M 30심볼/PIT·상폐·취득권 게이트는 닫혀 있어 TRAIN 결과는 코어/포워드 승인 근거가 아니다.

## 예상 실패·필수 검증

- 예상 실패는 빠른 접촉이 정보 우위가 아니거나, 표본만 줄이고 M2/EV/PF를 개선하지 못하는 것이다. R14/R35/R36의 이전 aggregate를 보고 만든 탐색 아이디어이므로 다중검정 부담에 포함한다.
- 합성 검증은 age 1·4 허용, age0·5 거부 경계, 실제 BOS zone 생성→R14 1h mapper→setup/simulator 체결, 늦은 첫 접촉 소진·재진입 금지, 미래봉 변조 불변성, stop/target·12bp·funding 보존, R14 함수 monkeypatch 복구, append/hash/denominator/lock/disk fail-closed를 포함한다. 독립 red-team 승인 전 TRAIN 입력에 접근하지 않는다.
