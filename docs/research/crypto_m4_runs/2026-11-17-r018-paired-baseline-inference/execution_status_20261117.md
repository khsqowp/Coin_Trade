# R018 execution status — 2026-11-17

## 판정

**R018 paired-inference method gate: REJECT. 시장 outcome/label 개방 금지 유지.**

사전등록한 synthetic equality-null 보정에서 Profile B의 20-calendar-day block이 실패했다. 이 계획은 등록된 equality-null profile/block 중 하나라도 실패하면 방법을 기각하도록 정했다. Profile A/C와 Profile B의 나머지 block이 통과해도 이 실패를 상쇄하지 않는다. 대안·결측 스트레스 및 전략 성과시험은 실행하지 않았다.

## 완료된 셀

세 run은 모두 동일한 코드 SHA-256 `829663f4d197ef19637880acf7b627b33e2b47260d10d5de7b00503fc85a0d99`, 5,000 panel, 1,999 bootstrap draws, seed `20261123`, block lengths `{1,2,5,10,20}`을 썼다. 모든 run은 synthetic-only이며 `market_data_read=false`다. 실패 panel/block cell은 모두 0이다.

| Profile | Block일 | Paired FWER | 95% Wilson 상한 | 전체 claim 적격률 | 셀 판정 |
|---|---:|---:|---:|---:|---|
| A | 1 | 4.42% | 5.03% | 100.00% | PASS |
| A | 2 | 4.34% | 4.94% | 100.00% | PASS |
| A | 5 | 4.26% | 4.86% | 100.00% | PASS |
| A | 10 | 4.24% | 4.83% | 100.00% | PASS |
| A | 20 | 4.34% | 4.94% | 100.00% | PASS |
| B | 1 | 4.96% | 5.60% | 99.96% | PASS |
| B | 2 | 4.94% | 5.58% | 99.96% | PASS |
| B | 5 | 4.96% | 5.60% | 99.96% | PASS |
| B | 10 | 4.80% | 5.43% | 99.96% | PASS |
| B | 20 | **5.40%** | **6.06%** | 99.96% | **REJECT** |
| C | 1 | 5.02% | 5.66% | 100.00% | PASS |
| C | 2 | 5.02% | 5.66% | 100.00% | PASS |
| C | 5 | 5.06% | 5.70% | 100.00% | PASS |
| C | 10 | 4.98% | 5.62% | 100.00% | PASS |
| C | 20 | 5.26% | 5.91% | 100.00% | PASS |

허용 상한은 Wilson 상한 ≤6%다. B/20은 6.0614%로 이를 넘는다. Profile B에서 전체-claim 적격률은 99.96%로 별도 95% 기준을 통과했지만, 이는 FWER 실패를 바꾸지 않는다. A의 joint user-rule false promotion rate는 0.08–0.12%, B는 0.08%, C는 0.02%로 기록됐다. 이 값들은 합성 null의 공동 규칙 진단이며 시장 전략의 정확도나 수익률이 아니다.

## 검증/범위

- A/B/C 각각 5,000 panels 완료. 15 block cells에서 14 PASS, B/20 한 셀 REJECT.
- A/B/C 모두 각 결과 manifest의 source hash가 현재 실행 코드와 일치한다.
- B/C가 바인딩한 A gate 결과 파일 해시는 `1b06923d303a5ff28e8e510719177aa367b51984805b325b718f1cb48ffff1df`다.
- 실행 출력은 각 run 폴더의 `manifest.json`, `results.json`, panel별 checkpoint 5,000개로 보존했다. 원시 checkpoint 15,000개는 `r018-null-panel-checkpoints-20261117.tar.gz`에 무손실 압축 보관했으며 SHA-256은 `d63fbc9cf7bd640d3d2cf918e32977433408aa273a21ba8734216df29773d48a`다. 압축 파일에는 panel JSON만 포함하고 manifest/results는 각 run 디렉터리에 별도 보관한다.
- 해당 실행은 synthetic Bernoulli paired-label inference만 검증했다. OHLC 경로·stop/target 순서·체결 가능성·수수료/슬리피지·funding은 검증하지 않았다.
- 등록된 다음 단계는 위 gate 전체 통과를 요구한다. Profile B/20 실패로 대안 및 결측 보정 셀을 시작하지 않았고, 시장 candle outcome을 읽거나 채점하지 않았다.
- 이 방법을 다시 시도하려면 실패 결과를 보존하고, 변경된 별도 방법/추론 가설을 새 사전등록과 독립 검토에 제출해야 한다. block 길이·임계값을 시장 결과에 맞춰 조정하거나, 유리한 셀만 선택하는 재시도는 허용되지 않는다.

## 저장된 결과

- `profile-A-null-none-vectorized/results.json`
- `profile-B-null-none-vectorized/results.json`
- `profile-C-null-none-vectorized/results.json`

전략 후보의 Monte Carlo 1,000회 P95 MDD, 504/252일 5창 WFA, 인접 파라미터 plateau 검사는 여전히 필수다. 이 R018 방법론 REJECT 때문에 현재는 전략 시장결과 검증 단계에 진입하지 않았다.
