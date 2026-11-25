# R33 — 외부 유동성 sweep 뒤 지연 BOS

상태: 실행 전 사전등록. 단일 TRAIN 시도이며, 결과 관찰 후 규칙·기준을 바꾸지 않는다.

## 가설과 탐색 편향 경계

직전 20개 완료 4h봉의 외부 극값을 sweep한 뒤 4–6개 완료 4h봉이 지나 BOS가 형성되는 경우, sweep 이후 가격이 범위 안에 머문 시간이 유동성 흡수/재축적을 나타낼 수 있다. 이 BOS-origin 오더블록의 첫 1h 재방문 반응을 시험한다.

이 가설은 R21의 1–3봉 sweep→BOS 결과와 R26의 사후 깊이 분석을 이미 본 뒤 고안된 같은 계열의 후속이다. 서로 독립된 증거로 세지 않으며 탐색·다중검정 부담에 포함한다. 우호적인 과거 하위집단을 결합해 성능을 만들었다고 주장하지 않는다. R32의 브레이커/강도 필터는 사용하지 않는다.

## 고정 규칙

- **데이터:** `CRYPTO_35.csv`, 고정 cutoff `2023-11-06T16:00:00Z` 이하의 완료 USD-M 4h/1h TRAIN bar만 쓴다. 종목 입력과 기존 cutoff-safe split을 검증하고 30개 미만이면 unscorable. TEST/OOS 및 2026-06-01 이후 입력은 열지 않는다.
- **sweep:** 완료봉 `j`에서 직전 20개 완료봉 `j-20:j`의 최저 저가/최고 고가를 참조한다. 롱 sweep은 `low[j] < prior_min_low AND close[j] > prior_min_low`; 숏은 `high[j] > prior_max_high AND close[j] < prior_max_high`. 경계 동률은 sweep 아님.
- **지연 구간:** BOS 신호 완료봉 `i`와 sweep `j` 사이 `i-j`가 4, 5 또는 6인 경우만 적격. 1–3봉은 제외하고 7봉 이상은 만료다. 후보 sweep이 여러 개면 가장 최근의 sweep 하나만 고른다. 모든 계산은 BOS 시점 이전 완료 데이터만 쓴다. 다른 지연 구간은 검사하지 않는다.
- **OB/진입:** 기존 R14의 `bos_origin` zone 및 4h→1h mapper/single-active-zone을 그대로 사용한다. 활성화 후 24개 완료 1h봉 안의 첫 구역 접촉, 방향으로 중앙값 회복 확인 후 다음 1h 시가 진입. 동일 구역 재진입은 금지.
- **청산/비용:** R14 고정 stop(원거리 경계 ±0.10×BOS 시점 4h ATR14), 0.50R 목표, 최대 24개 1h봉 보유, 시간만료는 다음 완료봉 시가, 같은 봉 손절 우선. 왕복 12bp 및 `adverse_only` funding.
- **분모/지표:** 전체 발행 신호의 M2 및 별도 비중복 M2, funding-scoreable N, Wilson 95% 하한, 승률, EV(bp), PF, Sharpe, 누적 순손익/MDD, 연도·방향 분해, 원시 BOS·적격 sweep·필터 이후 funnel, 만료/중복 수를 기록한다.

## 고정 합격 기준

TRAIN 선별은 scoreable `N≥200`, 전체 M2 `≥75%`, 비용 후 EV `≥+15bp`, PF `≥1.30` 모두 충족해야 한다. 미달·unscorable·실행 실패도 ledger 한 시도로 남기며 R33을 반복하지 않는다. 고정 사용자 코인 G는 OOS M2 `≥80%`, 비중복 OOS N `≥200`, 비용 후 EV `≥+15bp`, PF `≥1.30`, 연환산 Sharpe `≥1`, MDD 제한 및 다중검정·귀무·plateau·2배 비용·1봉 지연·약세장·미사용 코호트·독립 재현·권리/PIT gate 전부다. TRAIN 결과만으로 G 통과 판정을 금지한다.

## 실행 게이트

실행 직전 TRAIN ledger 1,689행, 이 시도 포함 Bonferroni 분모 1,690, R33 기존 행 0, 단일 writer/lock 부재, 디스크 여유 40GB 이상, 고정 split·universe·코드·상세/master prereg hash가 모두 맞아야 한다. 사전등록된 합성 prefix/future-mutation·정확한 3/4/6/7봉 경계·양방향·최신 sweep 선택·실제 R14 종단 경로·비용/funding·append/lock/hash 테스트 및 독립 레드팀 검토를 통과한 뒤 한 번만 실행한다.

## 실패 가능성과 데이터 한계

4–6봉의 지연 창은 표본 N<200으로 줄 수 있고, 지연 자체가 정보를 약화시켜 M2/EV/PF가 기준에 못 미칠 수 있다. R22의 post-BOS 확인 및 R17의 follow-through 실패는 지연 확인이 성과를 보장하지 않는 반례다. 같은 TRAIN에서 아이디어를 만들었으므로 후속 검증으로 OOS를 대체할 수 없다.

USD-M 자료로 2018년 30심볼 역사 유니버스·PIT/상장폐지 완전성 및 파일 취득 당시 이용권을 입증하지 못했다. 최종 G 데이터 게이트는 닫혀 있다. 따라서 결과가 TRAIN 선별선을 통과해도 자동으로 독립·실전 검증 후보가 되거나 TEST 접근이 허용되지 않는다.
