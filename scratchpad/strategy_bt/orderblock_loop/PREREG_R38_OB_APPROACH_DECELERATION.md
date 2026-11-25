# R38 — 첫 오더블록 재방문 전 방향성 3봉·몸통 비증가 필터

## 상태·가설·연구 한계

**상태: 실행 전 고정.** 이 실험은 R14의 첫 재방문 거래에서 접촉 직전의 짧은 가격경로 필터가 결과를 구분하는지 보는 한 번의 TRAIN 탐색이다. R37의 나이 범위를 다시 고르지 않는다. 롱은 접촉 전 세 완료봉 종가가 차례로 낮아지고 절대 몸통이 커지지 않는 경우, 숏은 대칭 경로일 때만 첫 유효 재방문을 거래한다.

이 규칙은 봉 사이 가격 이동량의 속도, 주문장 흡수, 매수·매도 체결량을 직접 계산하지 않는다. 따라서 이를 실제 “감속” 또는 기관의 흡수로 해석하지 않는다. 정확한 실험명은 **방향성 종가 연속 + 절대 몸통 비증가**다. 작은 몸통의 의미는 검증 전 가설일 뿐이다.

R1–R37 저장소 사전등록·보고서 검색에서는 이 정확한 조합이 보이지 않았다. R6-B는 접촉 뒤 확인봉, R17은 접촉·회복 후 추종, R30은 접촉봉 체결흐름, R35는 BOS 전 range 내 위치, R36은 접촉봉 꼬리, R37은 zone age를 다룬다. R10은 부모 4h 오더블록 재방문 이후 자식 1h 오더블록을 요구하는 연쇄로, R38은 자식 zone을 만들지 않고 부모 zone의 첫 접촉 직전 1h 경로를 필터링한다. 이 중복 검토는 저장소 기록 범위에 한정된다.

R38은 R14와 R37을 포함해 이미 본 TRAIN 결과를 바탕으로 나온 적응형 후속 가설이다. **새롭고 독립적인 검증 표본이 아니며, TRAIN에서 나와도 독립 성과 증거 또는 승인 후보로 세지 않는다.** 2018 파생 데이터, point-in-time 상장 유니버스, 취득권 게이트도 닫혀 있으므로 이 한 번의 실행은 G를 열 수 없다.

## 기계 규칙 — 단일 설정

- 기반은 R14의 고정 4h `bos_origin` zone, 1h mapping, 단일 활성 zone, 첫 유효 접촉, 접촉봉 중앙값 방향 종가 회복, 다음 1h 시가 진입이다.
- R14의 활성 `signal_index`는 해당 4h BOS가 완료된 시각으로 매핑된다. 활성봉(age 0)은 건너뛴다. 접촉 확인 index `i`에 대해 `i-signal_index`는 R14 deadline 이내여야 하며, R14가 정의한 첫 접촉 하나만 평가한다.
- 접근창은 `i-3, i-2, i-1`이고 접촉·확인봉 `i`는 연속성만 확인한다. 네 봉 모두 완료·유효 OHLC여야 하고 각 인접 timestamp 차는 정확히 3,600,000ms여야 한다. 누락·중복·역순·시간 불연속·잘못된 OHLC는 거부한다. 세 접근봉의 첫 index `i-3`은 `zone.signal_index` 이상이어야 한다.
- 롱: 세 접근봉 모두 `low > zone.high`; 종가는 `close[i-3] > close[i-2] > close[i-1]`; 절대 몸통은 시간순으로 `body[i-3] >= body[i-2] >= body[i-1]`.
- 숏: 세 접근봉 모두 `high < zone.low`; 종가는 `close[i-3] < close[i-2] < close[i-1]`; 절대 몸통은 시간순 비증가.
- 종가 동률은 거부, 몸통 동률은 허용한다. 접촉 전에 zone을 건드리거나 zone과 겹친 접근봉은 거부한다. 조건에 실패한 첫 접촉은 R14처럼 해당 zone을 소진하며 재접촉을 기다리지 않는다. 별도 필터 거부는 거래/예측 신호가 아니다.
- R14 우선순위를 그대로 쓴다: zone 무효화는 접촉 판정보다 먼저, 더 새로운 zone은 기존 활성 zone을 대체하지 않고 R14 규칙대로 누락, age deadline을 넘기면 만료, 첫 접촉에서 setup 생성 실패·필터 거부 시 zone 소진, 성공 시 한 거래 종료 후 zone 소진. 시간창 끝에 필요한 다음 봉/거래 종료가 없으면 right-censored로 세고 성공/실패 신호에 포함하지 않는다.
- 손절은 zone distal 바깥 `0.10×4h ATR14`, 목표 `0.50R`, 최대 보유 24개 완료 1h봉, 같은 봉에서 stop/target 양쪽 터치는 stop 우선, 왕복 비용 12bp, `adverse_only` funding을 그대로 적용한다. R14 체결 simulator와 비용·funding 계산을 바꾸지 않는다.

## 지표와 분모의 사전 정의

- **발행 신호와 M2 분모:** 실제 진입이 만들어진 R38 거래만 신호로 센다. R14 setup 중 R38 필터 거부, setup 미생성, 신호 없는 zone, 미완료/right-censored 거래는 신호 분모에 넣지 않고 각각 별도 계수한다. 거래 진입 뒤 목표 선도달만 성공이며 손절·시간 만료는 실패다. funding 누락 여부와 무관하게 완결된 경로의 M2는 기록하되, funding을 포함한 순손익을 계산할 수 없는 거래는 `funding_unscorable`로 별도 표시한다.
- **scoreable N, EV, PF, Sharpe, 누적수익·MDD:** 유효 funding 및 순손익을 계산할 수 있는 거래만 동일한 scoreable 집합으로 사용한다. scoreable N은 `trades - funding_unscorable_trades`와 대사한다. 기한 만료는 0 수익이 아니라 실제 R14 거래 순손익을 반영하되 M2에서는 실패다. 모든 지표의 표본·정의 차이를 결과표에서 밝힌다.
- M2 Wilson 95% 신뢰구간, 비중복 거래 N·성공률, 거래 수, 필터 통과/거부, right-censored, funding unscorable 개수를 함께 기록한다. 비중복은 같은 심볼의 이전 거래 종료 시각 이후에 시작한 거래만 남기는 R14 규칙을 따른다.

## 데이터·장부·재현 고정

- 고정 `CRYPTO_35.csv`, 현행 공통 TRAIN split, 각 완료봉의 close가 `2023-11-06T16:00:00Z` 이하인 데이터만 허용한다. 1h·4h 각 bar open timestamp에 timeframe 길이를 더해 close를 검사한다. 사전등록된 fixed split manifest SHA-256은 `5873762fedc42ce05025ea76a91b2b2870a5693a0b5bbdc6dd7f7e571d96b1dd`다. 바뀌거나 읽지 못하면 가격행 전에 중단한다. OOS/TEST 및 2026-06-01 이후 데이터, 네트워크·다운로드는 열거나 사용하지 않는다.
- 고정 사전 장부 행수는 4,194, 이번 포함 Bonferroni 분모는 4,195다. 이는 **공유 장부에 등록된 시도 행에 대한 분모**이며, 장부 밖의 사전 조사·가설 생성까지 완전하게 계수했다는 증거가 아니다. R38은 앞선 결과를 본 뒤 설계된 적응형 가설이므로 4,195를 독립성·전체 데이터 탐색 보정·통계적 유의성의 증명으로 해석하지 않는다. R38 단일 결과에서 Reality Check/SPA/Deflated Sharpe를 실행하지 않으며, 새 OOS/G 검증 없이 유의한 전략으로 판정하지 않는다.
- **가격행 접근 전:** writer 부재, 장부 행수·R38 중복·schema, 상세/master prereg SHA, 전체 source SHA, split manifest SHA, 40GiB 여유를 확인한다. 고정 35심볼의 1h·4h 파일에서 Parquet projection으로 `open_time`과 `complete` **두 필드만** 읽고, 조건 `open_time <= cutoff - timeframe_duration`을 적용한다. `complete=True` 행이 하나 이상인 심볼만 해당 시간단위 후보로 인정한다. `open`, `high`, `low`, `close`, volume 등 가격 필드는 이 사전검사에서 요청하지 않는다. 1h·4h 공통 후보가 30 미만이면 가격행을 열지 않고 중단한다. 이 검사는 데이터의 품질·연속성을 증명하지 않으므로 실제 로드 뒤에도 각 완료봉 close cutoff와 실제 공통 usable 심볼 30개를 재검사한다. 실로드 뒤 30개 미만이면 점수 계산은 하지 않고 `unscorable` 행으로만 기록한다. 분모는 결과 후 바꾸지 않는다.
- `data_access.iter_train_bars`의 고정 common split 및 `load_bars` close-aligned predicate를 사용한다. Parquet footer 통과만으로 시장행을 읽지 않으며, 실행 직전 예상 split SHA가 다르거나 이 구현 계약을 확인할 수 없으면 OHLCV 접근을 중단한다.
- 데이터 접근 전 합성테스트와 별도 적대적 검토가 모두 승인되어야 한다. 테스트 실패, 검토 미승인, writer/잠금 불확실, 파일 hash drift는 실데이터·장부 쓰기 전에 종료 조건이다. 실행 중 R38 source·두 prereg·split manifest가 바뀌면 성공 결과로 해석하지 않는다. execution-stage failure가 발생했을 때만 단 한 개 실패 행을 남기며, split/source/prereg preflight 실패는 시장행을 읽거나 장부에 시도 행을 쓰지 않고 멈춘다.
- 1회만 실행한다. result를 본 뒤 규칙 수정·하위집단 선택·재실행은 금지한다. append가 불확실하면 재시도하지 말고 writer 종료 뒤 trial ID/행수로 먼저 대사한다.
- 실행 시 코드 파일별 SHA-256과 aggregate code SHA, grid, 상세/master prereg, split manifest, TRAIN data fingerprint를 남긴다. 결과를 추가한 뒤에는 결과행 외에 실행 source snapshot과 같은지 파일별 hash로 대사한다. 대사되지 않으면 “현재 파일로 전체 재현 확인 안 됨”으로 남긴다.

## 판정선과 예상 실패

- 단일 TRAIN 선별 기준: scoreable 거래 `N≥200`, 전체 발행 거래 신호 M2 `≥75%`, 비용·funding 반영 EV `≥+15bp/거래`, PF `≥1.30`. 모두 만족해야 다음 검토 단계로 제안할 뿐 승인하지 않는다. 미달/표본 부족은 반려 또는 검증불가다.
- 최종 G는 별도 미사용 OOS에서 M2 `≥80%`, 비중복 `N≥200`, 비용 후 수익 양수, PF·EV·Sharpe·MDD, Bonferroni/Reality Check·SPA/Deflated Sharpe, 무작위 진입 및 순환이동 귀무, 2배 비용·1봉 지연·민감도 고원, 약세장·미사용 심볼군·수익 집중도·독립 재구현·PIT·데이터 취득권을 모두 요구한다. R38은 적응형 TRAIN 탐색이므로 새 미사용 OOS 없이는 이 항목들을 통과했다고 말하지 않는다.
- 예상 실패는 엄격한 3봉 방향 조건으로 유효 setup이 줄어 N<200이 되는 경우, 또는 몸통 축소가 매수·매도 압력 완화가 아니라 단순 정체여서 목표 적중·순기대값이 개선되지 않는 경우다. 지표가 나쁘면 원인을 기록하되 R38 규칙은 다시 맞추지 않는다. 다음 라운드는 별도 사전등록 가설로 진행한다.

## 사전 실행 검증 항목

합성 입력으로 롱·숏 대칭, strict zone 외부·close 이동, 몸통 동률/증가, 활성 경계, 불완전·불량 OHLC, 시간 gap을 확인한다. 실제 합성 4h BOS → R14 1h mapper → first-touch/setup → R38 filter → 다음 봉 entry → R14 simulator 경로, 거부 zone 소진, 미래 1h/4h 변조 불변성, 비용/funding 전달 및 patch 복원도 검사한다. 실행 전 fail-closed 테스트는 데이터 접근 없이 행수·중복·prereg/source/split hash·disk·writer·비가격 시간/완전성 projection 기반 최소 심볼 수·lock을 각각 위반시켜 loader와 append가 호출되지 않는지 검증한다. projection 테스트는 합성 입력으로 OHLCV 컬럼을 읽지 않는 것을 확인한다. 별도 합성 경로는 실제 로드 후 usable 심볼 미달 시 거래 채점을 건너뛰는지 확인한다. 장부 임시파일에서 성공 append 및 부분 write/fsync/close 불확실 결과도 검사한다.
