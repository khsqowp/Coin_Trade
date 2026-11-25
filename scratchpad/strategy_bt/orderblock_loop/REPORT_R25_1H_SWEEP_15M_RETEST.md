# R25 — 1h pre-BOS sweep + 15m 첫 재방문

## 판정

**반려.** 거래 수는 늘었지만 비용 후 손익과 목표 선도달률이 모두 나빠졌다. 881건에서 M2 53.35%, EV −26.60bp, PF 0.648, Sharpe −1.790, 누적 −7.32%, MDD 7.57%다. 후속 검증 기준 N≥200은 넘겼지만 M2≥75%, EV≥15bp, PF≥1.30를 모두 통과하지 못했다. 코인 G 통과 전략은 0개다.

## 사전등록·실행 대사

- 사전등록: `PREREG_R25_1H_SWEEP_15M_RETEST.md`, master `PREREG.md` §R25
- 코드·테스트: `search_crypto_r25_1h_sweep_15m_retest.py`, `tests/test_search_crypto_r25_1h_sweep_15m_retest.py`
- trial ID: `R25-crypto-ef81d941bade444699880be740ddea6f`
- code SHA-256: `cf5512e801959f59ca5ccd1644e662f754523ad546130e74157bec13215c8c51`
- grid SHA-256: `1e00d3db01ece747ea32dd394a3d0178a0420b5bce8aef24c339bea10f12bf40`
- TRAIN input fingerprint: `c3ebb292c9fb3f05356309e4729792bbdceedf805bb49eb8cc819cee77fa0d57`
- R25/master prereg SHA-256: `c5fba0e7d3729b990f7287c5d54005018916ad199f9f03fe2f3c5f26f97235e0` / `5b785fcb00a363464bd1baf07c45e2db337466e63e3f0bfb8e67dcf7d8901f7d`
- 실행 전 ledger 본문 1,681행, 완료 후 1,682행이며 R25 행은 1개다. stdout와 행의 결과·trial ID·코드/grid/데이터/prereg 지문이 일치했다.
- cutoff는 `2023-11-06T16:00:00Z`이고 유효 심볼 32개. OOS/TEST 및 2026-06-01 이후 자료는 열지 않았다. 실행 전 디스크 51GiB, 러너 writer/lock 부재, 해시 및 ledger 분모를 확인했다. 실행 후 러너 종료와 lock 제거를 확인했다.
- R25 데이터 실행 전 52개 합성·회귀 테스트가 통과했고, 독립 red-team이 현재 로더에서 추가 코드 수준 차단점을 찾지 못했다. 적격 데이터 커버리지·실제 cutoff는 러너의 사전 고정 로더와 입력 검사 결과로 확인했으며, 그 외 PIT/이용권 완전성은 확인되지 않았다.

## 결과

| 항목 | 관측값 |
|---|---:|
| 고정 유니버스 / 유효 심볼 | 35 / **32** |
| 원시 1h BOS 구역 | 216,180 |
| 20-bar sweep 조건 통과 구역 | 3,848 |
| 첫 15m 접촉 / 체결 | 924 / **881** |
| 전체 M2 목표 선도달 | 470/881 = **53.35%** |
| M2 Wilson 95% 하한 | **50.05%** |
| 비중복 M2 | 470/881 = **53.35%** |
| 거래 승률 | **58.46%** |
| 비용 후 EV | **−26.60bp/거래** |
| Profit factor | **0.648** |
| 연환산 Sharpe | **−1.790** |
| 누적 순손익 / MDD | **−7.32% / 7.57%** |
| 만료 / zone 무효화 / 중앙값 실패 | 1,436 / 60 / 43 |
| 중첩 새 zone 폐기 | 1,363 |
| 누락 gap bars / 제외 불완전 봉 | 4,200 / 27 |
| funding 미판정 거래 | 0 |

## 실패 분석 및 다음 가설

R21의 4h 구조와 1h 재방문 조합에서는 같은 20-bar sweep→1~3봉 내 BOS 개념이 196건, M2 63.27%, EV +50.55bp, PF 1.548이었다. R25는 이를 1h/15m으로 단순 이전해 거래를 881건으로 늘렸지만 M2는 9.92%p 낮아지고 EV는 −77.15bp/거래 하락했다. 관측상 낮은 시간축에서는 신호 빈도 증가가 품질 개선으로 이어지지 않았고, 기본 12bp 비용 이후 손실이 됐다. 이는 동일한 sweep 구조가 15m 체결 주기에서 유지되지 않았다는 뜻이지, 모든 단기 전략이 불가능하다는 증명은 아니다.

이 결과를 보고 진입·목표·보유기간을 바꿔 재시험하지 않는다. 다음 단일 가설은 R21의 4h/1h 주기를 유지하고, 기존 20-bar sweep/reclaim 조건에 **sweep 깊이 ≥0.25×ATR14** 하나만 추가한다. 가설은 작은 wick 초과를 실제 외부 유동성 sweep으로 과대계상할 수 있다는 점에서 나온다. 깊이 임계는 실행 전에 고정하고 결과 후 조정하지 않는다. 이 후속도 한 번의 TRAIN 탐색일 뿐, OOS나 G 통과로 세지 않는다.

## 검증 한계

- R25 테스트: `python -m unittest discover -s scratchpad/strategy_bt/orderblock_loop/tests -p 'test_search_crypto_r25_1h_sweep_15m_retest.py' -v` — **13/13 통과**.
- 공통 회귀: R24 단위 9/9, R24 종단간 1/1, R14 10/10, R21 단위 10/10, R21 매퍼 통합 1/1, R22 6/6, R23 2/2. 합계 **52/52 테스트** 통과. 변경된 R25 코드·테스트 `py_compile`도 통과했다.
- 검증하지 않은 항목: OOS/최종 TEST, 비용 2배, 1봉 지연, 무작위 진입 200회, 순환이동 1,000회, plateau, SPA/Reality Check/Deflated Sharpe, 2018·2022 약세장, 독립 재구현, 미사용 심볼군, PIT·상폐 정산·자료 이용권 완전성.
- 기존 2018 futures 30심볼 gate가 닫혀 있어 이 결과는 탐색 TRAIN 전용이다. 이를 성과가 검증된 후보 또는 실매매 근거로 표현하지 않는다.
