# 전략 연구 진행 기록 — 2026-11-22

## 결론

이번 라운드는 6개 후보 중 검증 합격 0개다. 사전등록된 코인 OB 후보 002의 성과 스크린은 데이터 감사·코드·4인 검토·freeze manifest까지 준비했으나, 실행 직전 macOS 스왑 사용량이 3,432.81 MB로 확인되어 자원 안전 기준(3,000 MB 미만)을 넘었다. 성과 계산은 실행하지 않았다.

## 시장별 후보 상태

| 시장 | 후보 1 | 후보 2 | 검증 상태 |
|---|---|---|---|
| 국장 주식·ETF | KODEX 200 시장가격-iNAV 괴리 회귀 | 공시 시점 기준 실적 서프라이즈 드리프트 | 둘 다 가설 단계. 과거 시점별 iNAV·컨센서스, point-in-time 상장/상폐·기업행위 및 실행가격이 없어 성과 검증 불가. |
| 미장 주식·ETF | 지연 갭 페이드(기존 갭 페이드와 중복 가능성 있어 신규 전략 수에서는 제외) | SPY 변동성 게이트→IEF/SPY 로테이션(기존 ETF 방어 가족과 중복) | 가격 데이터는 staging에서 확인됐지만 현재 생존자 코호트, 기업행위/배당 총수익, 체결 비용 및 sealed OOS 결함으로 합격 검증 불가. |
| 코인 OB | 동일 UTC 5분 구간 현물-퍼페추얼 종가 상대조건 OB 재탈환 | 5분 OB 접촉 뒤 1분 확정 pivot BOS | 후보 001은 이전 개발 스크린에서 M2 31.3869%, 기준선 28.2875%, 비용 후 발행당 평균 손익 -0.0966%/-0.2966%로 반려됨. 후보 002는 규칙 freeze 완료, 이번 자원 차단으로 미실행. 두 후보 모두 OOS/Core 승인 아님. |

정의와 세부 제한은 `strategy_candidate_round_20261122.md`, 후보 002 규칙은 `PREREG_SPOT_PERP_OB_PIVOT_BOS_DEV_20261122.md`에 있다. 아이디어 두 개씩은 확보했지만 “의미 있는 성과”가 입증된 전략 두 개씩을 뜻하지 않는다.

## KR·US 담당자 추가 제안의 중복 검토

- Raman의 월간 저변동성 주식 바스켓은 신규 분류하지 않았다. 기존 Round5 저변동성(realized-volatility) decile과 같은 요인 가족이며, registry 기록상 KR CAGR 5.45% 대 동일 코호트 buy-and-hold 11.95%로 합격선에서 반려됐다. 이번 제안의 리밸런싱·유니버스 세부는 다르지만 과거 결과를 새 전략 수로 재포장하지 않는다.
- Harvey의 SPY 매월 첫 거래일 시가 진입·3거래일째 종가 청산 규칙도 신규 독립 가족으로 세지 않는다. Gen16 preregistration C1이 이미 월 첫 관측 세션 진입 및 초반 세션 청산을 시험했고, 기존 달력 효과 가족과 표본을 공유한다. 새 stop을 붙이는 것은 별도 하위 가설이며 이번 연구에서 그 성과를 생성하거나 기존 OOS를 새로 부르지 않았다.
- 두 담당자의 제안은 데이터 확인 단계에서 규칙 후보로만 기록한다. 새 독립 연구군으로 인정받으려면 사전 trial registry 대조, 구조적 메커니즘 차이, 미사용 OOS와 기준 비용을 먼저 고정해야 한다.

## 코인 후보 002 준비 증거

- 실제 입력 루트 `/Users/user/CODE/trading_data/external/crypto/binance`에서 생성한 funding/mark 감사: `crypto_ob_pivot_bos_cost_input_audit_20261122.json`.
- 감사 결과: funding 파일 800/800, 행 79,902, funding 간격 결함 3건(ENA/POL/TIA 각 1개 예상 4시간 이벤트), mark-price 파일 32/32, 심볼별 하루(1,440분) 결측 32건. 상태 `KNOWN_COST_INPUT_GAPS`.
- 감사 SHA-256: `8f04890b1b52444bec9453f00618dae4bc05fe9173640342306dfad13ee42a1c`. 동일 입력을 재감사했을 때 같은 SHA가 나왔다.
- 가격 입력 fingerprint: `de5c87e883f4c3e00b818c541a0e36d1320f08a2577dc063d2bb9ff519ab9036`.
- funding/mark 결함 때문에 scorer는 funding 비용을 반영하지 않는다. 후보 스크린은 fee-only 과거 개발 진단일 뿐, 완전 순수익·OOS·전향 성과를 주장할 수 없다.
- 독립 검토자 4명(Banach, Raman, Harvey, Singer)이 사전등록·scorer 프로토콜을 승인했다. 이는 코드·절차 승인이지 전략 성과 승인과 다르다.
- 재현성 테스트: `tests/test_spot_perp_ob_pivot_bos.py` 19 passed. `py_compile`, `git diff --check` 통과.
- 코드/감사 커밋: `d806be368a3ea5aa4b2c1e6a74069fce1441d8b1`; 검토자 식별자 수정: `306926212e348e9cf8c3aa8da819b6e3ea1819d9`; freeze manifest 단독 커밋: `a98ea22e37b4e1d968ed2f7d5891e9f2fdf8fd77`. 세 커밋은 요청된 브랜치에 push했고, 마지막 원격 SHA는 로컬 HEAD와 일치했다.

## 실행 직전 자원 게이트와 재개 조건

- `sysctl vm.swapusage`: used `3432.81M`, free `1687.19M`; 임계치인 3000 MB를 초과했다.
- `memory_pressure`: system-wide free percentage 41%; critical 상태 표시는 없었지만 스왑 기준 초과만으로 scorer 실행을 보류했다.
- Scorer 출력 디렉터리는 없었고, 입력·코드 fingerprint는 고정본과 일치하도록 준비됐다. 출력 디렉터리를 만들거나 점수화하지 않았다.
- 재개: 스왑이 3000 MB 미만임을 다시 확인하고, branch/HEAD/clean tree, freeze parent, 입력 fingerprint, output 경로 부재를 재확인한 뒤 고정 scorer를 정확히 한 번 실행한다. 현재 작업에서는 파라미터 탐색이나 반복 scoring 금지.

## 다음 순서

1. 실행 직전 자원 게이트를 재확인하고, 조건을 충족할 때만 코인 후보 002 개발 스크린 1회 실행.
2. 저장된 실제 결과로 gate별 통과/반려 사유를 기록한다. funding 포함 경제성 및 sealed OOS가 없으면 최대 `HOLD_FUNDING_AND_OOS` 상태를 유지한다.
3. 국장·미장 두 후보씩은 새로운 수익률 테스트 전에 PIT/기업행위/체결/비용/독립 OOS 가용성을 각각 검증한다. 불충족이면 가설 후보/데이터 차단으로 기록하고 합격 전략 수로 세지 않는다.
4. 분석 결과에서 확인된 구조적 실패 원인만 새 버전 가설로 바꾸고, 사전등록과 기존 trial-family 연결 후 별도 승인·실험한다. 성과를 본 뒤 기존 규칙을 튜닝하지 않는다.
