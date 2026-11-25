# R28 사전등록 — BOS 봉 종가 위치 필터

상태: 결과 열람 전 단일 TRAIN 탐색으로 사전등록. 실데이터 실행 전 코드·합성 종단 테스트·독립 레드팀 및 장부/잠금 게이트를 다시 확인한다.

## 가설

R14의 4시간 BOS-origin 구역은 1시간 첫 재방문 중앙값 회복 후 진입했지만, TRAIN 7,729건에서 M2 60.89%, 비용 후 기대값 -20.88bp, PF 0.826이었다. R27은 BOS봉의 방향 일치 FVG를 요구했으나 M2 60.34%, EV -13.71bp, PF 0.883으로 개선되지 않았다. R22는 다음 4시간 확인봉을 기다리는 방식이 기회를 줄이고 M2·EV를 악화시켰다. R28은 추가 확인봉 대신 이미 완료된 BOS 봉 자체의 종가 위치를 측정한다. 롱 BOS가 봉 범위 상단 25%에서, 숏 BOS가 하단 25%에서 마감한 경우는 반대꼬리 돌파보다 방향성 있는 경매 수용을 나타내어 첫 재방문 목표 선도달과 비용 후 손익을 개선할 수 있다는 가설이다.

## 고정 규칙

- **데이터·유니버스:** 고정 `universe/CRYPTO_35.csv`; cutoff-aware 완료 Binance USDⓈ-M TRAIN 4h/1h bars; 신호 4h봉 마감 cutoff `2023-11-06T16:00:00Z` 이하. OOS/TEST와 2026-06-01 이후 데이터는 열지 않는다. 두 시간축 사용 가능 심볼이 30개 미만이면 `unscorable`로 기록한다.
- **구역:** 기존 R14 `bos_origin`만 사용한다. 완료된 BOS 봉의 range를 `high-low`로 계산한다. 롱은 `(close-low)/(high-low) >= 0.75`, 숏은 `(close-low)/(high-low) <= 0.25`일 때만 통과한다. 경계 0.75/0.25는 통과한다. 방향 외 별도 body·ATR·volume·FVG·추세 조건은 추가하지 않는다. range가 0 이하이거나 OHLC 값이 유한하지 않거나 `low ≤ min(open,close) ≤ max(open,close) ≤ high`를 위반한 입력은 전략 필터 탈락으로 세지 않는다. R14 BOS 엔진의 입력 무결성 검증에서 예외로 fail-closed 처리하고 해당 단일 시도는 데이터/실행 실패로 기록한다. 이는 OHLC 불량 신호를 임의로 걸러 성과를 바꾸지 않기 위한 처리다.
- **인과성·수명주기:** 분류에는 해당 완료 BOS봉까지의 값만 쓴다. BOS봉 종가 확정 뒤 구역을 R14와 같은 시각으로 매핑한다. 필터 통과 구역만 활성 구역 엔진에 전달하며, 거부 구역은 기존 활성 구역을 대체하지 않는다. 겹침·정렬·무효화·첫 접촉·만료·검열은 R14 규칙 그대로 둔다. 미래 봉은 필터 및 구역 선택에 사용하지 않는다.
- **진입·청산:** 첫 1h 재방문에서 중앙값 회복을 확인한 뒤 다음 1h 시가에 진입한다. distal 경계 바깥 BOS ATR14의 0.10배를 손절로, 고정 0.50R을 목표로, 최대 24개 1h봉을 보유한다. 동일 봉 손절/목표 동시 접촉은 손절 우선, 왕복 비용 12bp, `adverse_only` funding과 R14 시간청산·gap·불완전봉·censor 처리를 그대로 적용한다.
- **독립성:** R27과 달리 FVG를 사용하지 않는다. R11의 목표거리 0.25/0.50/0.75/1.00R 탐색을 반복하지 않는다. R22의 다음 봉 확인을 반복하지 않는다. 이 시험은 BOS봉 종가 위치라는 단일 사전 신호 필터다.

## 사전 고정 판정

- 최종 G는 변경하지 않는다: OOS M2 ≥80%, 비중복 OOS N ≥200, 비용 후 EV ≥+15bp, PF ≥1.30 및 Bonferroni/Reality Check·SPA/Deflated Sharpe, 무작위 귀무, 민감도·평탄도, 레짐·비용·지연·미사용 종목, 데이터 PIT·이용권 gate를 모두 통과해야 한다. TRAIN은 G 통과가 될 수 없다.
- TRAIN 후속 선별선은 R27과 같은 `N≥200, M2≥75%, EV≥+15bp, PF≥1.30` 네 항목 모두다. 표본 미달 또는 어느 한 항목이라도 미달이면 반려한다.
- 전체 및 비중복 M2·Wilson 95%, 승률·손익비, EV·PF·Sharpe·누적손익·MDD, 방향·진입연도별 귀속, 필터 funnel, funding/gap/불완전 봉 수를 모두 기록한다. 기준을 결과 뒤에 바꾸지 않는다.

## 실행 전 게이트와 시도 분모

- 사전등록 시점 장부는 헤더 제외 1,684행으로 확인했다. 이번 한 시도를 포함하는 계획 분모는 `N=1,685`다. 실행 직전 장부 행수와 스키마, R28 중복, 상세·master 사전등록 hash, runner 의존 코드 hash, cutoff, 30개 이상 심볼, 데이터 fingerprint 형식을 재확인한다. 행수 불일치 시 입력 가격행을 열기 전에 중단하며 분모를 실제 선행행수+1로 고정한다.
- 데이터 접근 전에 `TRADING_DATA_DIR/cache/orderblock/crypto_splits_close_boundary.json`의 cutoff 고정 split 메타데이터가 현재 1h·4h 입력 파일 전체에 존재하고 고정 경계와 일치하는지 읽기 전용으로 검증한다. 누락·불일치 시 TRAIN 가격 파일을 열지 않고 실패행만 기록한다. 따라서 `data_access.load_bars`가 split 캐시를 생성·갱신할 상황에서는 실행하지 않는다. 실행 전후 split manifest SHA-256과 mtime을 비교해 변경이 없음을 확인한다. 허용되는 영구 쓰기는 append-only `TRAIN_TRIALS.csv` 한 행뿐이다.
- 두 배타 잠금 `.cointrade_train_trials.lock` 및 `.ob_attrition_train_trials.lock`을 획득하고, 프로세스 목록과 `lsof`로 다른 writer/연구 실행 부재를 확인한 후 한 번만 실행한다. 안전한 단일 append를 보장할 수 없으면 실행하지 않는다. write/fsync/close 결과가 불확실할 때 재시도·truncate하지 않고 장부 tail 확인 절차로 멈춘다.
- 사전등록 hash·코드 hash·데이터 cutoff·필수 합성 테스트·독립 레드팀 중 하나라도 실패하면 TRAIN 가격 데이터를 열지 않는다. 본 시험은 한 번의 설정이며 파라미터 격자나 사후 재실행은 없다.

## 필수 합성 검증

1. 롱/숏 종가 위치 대칭, 정확한 0.75/0.25 경계, 바로 밖 값, range=0, 전체 OHLC 유한성 및 `low≤min(open,close)≤max(open,close)≤high`, 비완료·잘못된 index를 검사한다. 잘못된 OHLC가 실제 R14 detector에 도달하면 전체 시도를 fail-closed 하는지도 검사한다.
2. BOS봉 이후 값을 변조해도 이미 확정된 분류 결과가 바뀌지 않는 prefix/future-mutation 검사를 수행한다.
3. 실제 `crypto.r4_zones`가 검출한 BOS→종가 위치 필터→R14 매퍼·활성 구역·첫 접촉·setup·공통 simulator에서 실제 거래까지 이어지는 단일 경로를 검증한다. 별도 합성 경로로 후속 거부 zone이 앞서 활성화된 통과 zone을 대체하지 않는지 확인한다.
4. 필터 funnel 원시 BOS→origin zone→종가 위치 통과/거부→매핑→활성화→첫 접촉→거래를 합성 입력에서 대사한다.
5. 장부 중복/행수·append 오류/불확실성·부분 잠금 회수와 cutoff 고정 split cache 완전성·불변성을 검증한다. 이 테스트는 tempfile만 쓰고 실데이터를 열지 않는다.

## 결과 기록

단일 cutoff-safe TRAIN 실행·장부/stdout/hash 대사와 실패 원인을 `REPORT_R28_BOS_CLOSE_LOCATION.md`에 기록한다. 성공 기준 미달도 시도 1건으로 보존한다. 이 사전등록은 OOS 접근, 실거래·서버 변경, 포워드 승격 또는 데이터 적격성 승인을 뜻하지 않는다.
