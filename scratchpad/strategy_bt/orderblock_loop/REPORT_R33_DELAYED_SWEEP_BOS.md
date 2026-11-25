# R33 — 외부 유동성 sweep 뒤 지연 BOS 결과

## 판정

**TRAIN 선별선 미달로 반려한다.** 4–6봉 지연 조건은 표본을 확보했지만 비용 후 기대값은 거의 0이고 M2는 62.50%에 그쳤다. 유의미한 예측력을 보였다고 볼 근거가 없다.

## 사전등록·실행 대사

- 사양: [`PREREG_R33_DELAYED_SWEEP_BOS.md`](PREREG_R33_DELAYED_SWEEP_BOS.md).
- R32 이후 실제 사전 ledger는 4,189행이었다. 결과값을 선택하거나 열지 않고, 새로 추가된 RB 대조 2,500시도 전체를 다중검정 분모에 포함했다. R33 포함 계획 분모는 4,190으로 실행 전 정정했다.
- 사전검사 당시 R33 행 0, 연구 writer/lock 없음, 여유공간 50.44GiB, 코드/상세·master prereg hash 일치, split manifest hash 일치를 확인했다.
- trial ID: `R33-crypto-d7b66cdbc1764d2d84f51dcdea911d95`
- 상태: `completed`, R33 행 1개. 실행 stdout와 ledger 상태·지표·해시가 일치했고 종료 뒤 writer/lock은 보이지 않았다.
- 실행 code SHA-256: `6a666cc8ca75a639bc923081df4e1c6caee7a19e5bef685fe561b8c82baf1606`
- grid SHA-256: `c20a1fab983e6b9c494b1dfc68b68f42e94b82bfe55e919c77cec15830421b12`
- 실행 시 상세 prereg SHA-256: `601daff3d0fbf29c470820bc1a8daedf3d0d41f81865efef359a868b3e2b963b`
- 실행 시 master prereg SHA-256: `ca23fa806a263edd9136233d9f463bd14eb663d339a2ecb79f22e853aa70c4a0`
- TRAIN 입력 fingerprint: `c8876ed7f65d1807304e754aa89f946c7f62faa2630163091b8aec86b770cb39`
- split manifest SHA-256: `5873762fedc42ce05025ea76a91b2b2870a5693a0b5bbdc6dd7f7e571d96b1dd`

## 결과

| 지표 | R33 TRAIN | 고정 기준 | 판정 |
|---|---:|---:|---|
| cutoff-safe 적격 종목 | 32 | ≥30 | 충족 |
| 비용·펀딩 scoreable 거래 | 480 | ≥200 | 충족 |
| 목표 선도달 M2 | 300/480 = **62.50%** | ≥75% | 미달 |
| Wilson 95% 하한 | **58.09%** | 보고 | — |
| 일반 승률 | **64.79%** | 참고 | M2와 구별 |
| 비용 후 기대값 | **+0.73bp/거래** | ≥+15bp | 미달 |
| Profit factor | **1.007** | ≥1.30 | 미달 |
| 연환산 Sharpe | **0.026** | 최종 G ≥1.0 | 미달 |
| 누적 순수익 | **+0.109%** | 양수 | 소폭 양수 |
| 최대 낙폭 | **2.142%** | 순이익 절반 미만 | 미달 |
| funding 미판정 거래 | 0 | 0 | 충족 |
| 비중복 M2 표본 | 480 | ≥200 | 표본만 충족 |

funnel: 원시 BOS 구역 56,447 → 지연 sweep 적격 활성 zone 2,367 → 첫 접촉 520 → 거래 480. 미완료 봉 40개, 누락 gap 봉 1,050개, 4h 정렬 실패 1건을 집계했다. 모든 480 거래가 scoreable이었고 비중복 신호도 480건이었다.

## 기존 결과와 실패 원인

- R21의 1–3봉 sweep→BOS는 TRAIN 196건, M2 63.27%, EV +50.55bp, PF 1.548이었다. R33의 4–6봉은 N이 480으로 늘었지만 M2 62.50%, EV +0.73bp, PF 1.007이었다. **지연 창은 표본 수를 늘렸지만 수익/예측 우위를 재현하지 못했다.**
- R33은 R21/R26 결과를 본 뒤 만든 같은 계열 후속이라 독립 검증이 아니다. 양의 R21 숫자가 시간 지연 전반에 일반화된다는 설명은 이 TRAIN 결과로 지지되지 않았다.
- 일반 승률 64.79%는 목표 선도달 M2 62.50%와 다른 값이다. 시점 만료 등으로 이긴 거래가 있어도 목표가 먼저 닿지 않으면 M2 성공이 아니다.
- 누적 수익은 +0.109%지만 MDD 2.142%가 순이익의 절반을 크게 초과하고 Sharpe도 0.026이다. 수수료와 funding 반영 뒤의 경제적 우위는 확인되지 않았다.
- runner는 연도별·방향별 손익 분해를 저장하지 않았다. 이 값은 **확인 안 됨**이며 사후에 별도 가격행을 재열람해 채우지 않는다.

## 검증·미실행

- R33 합성 테스트 **19/19 통과**: 4·5·6봉 포함 및 3·7봉 배제, timestamp gap fail-closed, 미래봉 불변성, 최신 sweep 선택, 실제 `crypto.r4_zones` BOS 생성→R14 4h/1h mapper→실제 simulator→12bp 비용·adverse-only funding, lock/append/hash/denominator/disk/split fail-closed를 검사했다.
- R31·R32·R14·R21 회귀 및 R24 종단 테스트는 각각 **22/22, 18/18, 10/10, 10/10, 1/1** 통과했다. 이번 확인 합계 **80/80**. Python 3.12/3.13 구문 검사 2/2, 실행 전 source hash 일치 검사 통과.
- 독립 레드팀은 최종 정적 검토에서 R33 실행 코드 차단을 발견하지 않았다. 최초 검토의 3개 차단(실제 BOS 종단 경로, 실행 게이트 테스트, bar gap)을 수정해 재검토받았다.
- 고정 TRAIN 선별 미달이므로 OOS/TEST, walk-forward, Monte Carlo/순환이동 귀무, 2배 비용, 1봉 지연, plateau, Reality Check/SPA, Deflated Sharpe, 독립 재구현, 동결 데이터 검증은 실행하지 않았다.
- USD-M 보유자료의 2018년 30심볼/PIT·상장폐지 이력과 취득 당시 이용권이 해결되지 않아 최종 G 데이터 게이트는 닫혀 있다. 이번 TRAIN 결과는 전략 승인이나 실거래 근거가 아니다.
