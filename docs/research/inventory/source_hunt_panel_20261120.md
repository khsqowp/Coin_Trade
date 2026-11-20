# 외부 전략 발굴 및 4역할 패널 판정 — 2026-11-20

## 목적과 판정 경계

Phase 9 포트폴리오 결합 전에 기존 레지스트리·TradingView/Pine 자료와 구조적으로 다른 코인 무기한선물 가설을 공개 SNS, TradingView, 공개 커뮤니티, GitHub에서 찾고 4역할로 적대 검토했다. 외부의 수익률 주장은 독립 검증으로 간주하지 않았다. 이 문서는 후보 발굴·자료 적격성 판정이며 백테스트 결과가 아니다.

기존 하드 게이트는 M2 목표 선도달률 80% 이상, 전체 발행신호와 별도 비중복 N≥200, 최소 20개 심볼, 커버리지 10% 이상, 고정 기준선 대비 Wilson 하한 우위, 10bp/30bp 라운드트립 비용과 timestamp-aligned funding 반영 후 양의 순기대값이다. 여기에 walk-forward, 완전히 미사용된 검증/forward 데이터, 민감도, Monte Carlo/블록 부트스트랩 및 독립 원장 재검토가 필요하다. 이 조사에서 어떤 전략도 이 문턱을 통과하지 않았다.

## 조사 설계 및 4역할 검토

네 명의 조사자는 각각 SNS, TradingView/Pine, 공개 커뮤니티, GitHub 전략/스킬 자료를 조사했다. 각자는 기존 레지스트리와 관련 문서를 대조하고, 최대 세 개 후보만 제안했으며, 출처·기계적 규칙·데이터·라이선스·인과성 한계를 기록했다. 이후 Blue Team, Red Team, Methods Evaluator, Chief Judge 역할로 후보 A–G를 교차 심사했다. 네 역할의 판정을 모두 회수했다. 판정은 후보의 검정 자격과 Phase 9 진행 여부에 한정하며, 전략 수익성에 대한 만장일치나 승인을 뜻하지 않는다.

### 후보와 판정

| ID | 가설 | 근거/출처 | 패널 판정 | 핵심 사유 |
|---|---|---|---|---|
| A | 총 청산량의 후속 청산량 지속성 | [Reddit 공개 분석](https://www.reddit.com/r/algotradingcrypto/comments/1xlrrae/liquidations_dont_lead_bitcoins_price_they_mirror/) | **방향 전략 아님** | 원문 주장은 가격 방향이 아니라 후속 청산량의 약한 지속성이다. 이를 롱/숏 신호로 바꾸면 새 가설이 된다. 작성자 단독·짧은 표본·피드 누락 위험. |
| B | 방향별 청산 급증 후 반전 | [Stratmill 전략 설명](https://stratmill.com/research/en/strategies/4e16b871-9fa4-4132-babb-e879b521ed2a) | **데이터 차단** | 제안 규칙은 45일 trailing percentile, 5일 만기, +8%/-5% 장벽이나 방향별 역사 청산 원자료·시점별 이용 가능성을 확인하지 못했다. 가격으로 대체하지 않는다. |
| C | 현물-무기한 베이시스 z-score 수렴 + funding tail | [공개 저장소 설명](https://github.com/swingtradingtank/spot-perp-base-trading-strategy) | **현재 방향성 트랙 차단** | 시장중립 양 레그 전략으로 분류해야 하며 기존 funding-tail과 데이터·신호가 겹친다. 규칙의 horizon/파라미터/라이선스가 불완전하고 양쪽 동시 체결 자료가 필요하다. 기존 funding-tail 단독 결과는 M2 25.04%, 스트레스 비용 후 순기대값 음수였으나 C 자체의 기각 결과로 오인하지 않는다. |
| D | 군중 포지셔닝 극단 + OI 감속 | [저자 공개 문서](https://github.com/MG-Trading-Terminal/trading-strategy/blob/main/strategies/positioning-based-btc.md) | **시점 자료 차단** | 과거 OI·롱숏 비율의 point-in-time vintage, 확정 창, 실제 공개 시각이 검증되지 않았다. 현재 OI QA도 구조적 샘플 무결성과 과거 가용성은 다른 문제라고 판정했다. |
| E | 변동폭 정규화 directional movement 교차(RV) | [TradingView RV Indicator](https://www.tradingview.com/script/WXmHraCk-RV-Indicator/) | **원 규칙 후보 반려** | 특정 스크립트의 정확한 공식·초기화·repaint 동작이 공개 설명만으로 고정되지 않았고 허용 라이선스도 확인되지 않았다. 독립 수식을 새로 만들면 원 스크립트 시험이 아니라 별도 파생 가설이다. |
| F | 15분 경계 첫 10초 주문흐름 불균형 | [Kim & Hansen (2026) 논문](https://arxiv.org/abs/2607.09426) | **현재 수익전략으로 반려** | 논문은 6개 Binance perpetual, aggregate trades 2021-01~2024-10에서 예측 연관을 보고하지만, 경계당 평균 총 예측수익은 약 0.5bp로 taker 비용의 약 1/10이며 논문도 수익 전략으로 제시하지 않는다. 기존 로컬 데이터는 1시간봉이라 재현 불가. |
| G | 100ms LOB + 체결 불균형 | [기술 논문 요약](https://dspace.cuni.cz/handle/20.500.11956/213492?show=full) | **현재 범위에서 실용성 반려** | 100ms에서 예측 설명력은 보고됐지만 30초 이후 경제적으로 의미 있는 이점이 없다는 저자 요약이며, 20단계 order book·세밀한 체결 재구성과 낮은 지연 실행이 필수다. 프로젝트의 시간봉/OOS 자료와 맞지 않는다. |

### 역할별 결론

- **Blue Team:** 미시구조에서 가장 강한 검증 가설은 F의 15분 경계 주문흐름이다. 그러나 예측 신호의 gross 수익이 거래비용보다 작아 현 사양의 수익 전략으로는 승격하지 않는다. B는 방향별 청산 원자료 확보 시에만 검토한다.
- **Red Team:** 2026-06~09 데이터는 mark-price gap 플래그 45건 및 funding metadata 불일치 8건이 있어 원인 해소 전 채점 불가. B/D는 point-in-time 원자료가 없고 E는 규칙 식별/라이선스 문제가 있다. F는 비용 전 근거부터 불리하다.
- **Methods Evaluator (독립 판정):** 현재 전략 채점 가능한 후보는 0개. 36심볼 1시간 USD-M 공통 코호트는 2023-03-23부터 2026-06-01까지 감사되었으나 기존 연구에서 전 구간 노출됐다. 2026-06~09 월별 자료가 로컬에 존재한다는 사실은 OOS 자격을 뜻하지 않는다. 1시간봉으로는 F/G를 채점할 수 없고, B/D 핵심 변수가 없다.
- **Chief Judge:** Phase 9는 계속 차단한다. 현 조사에서 `PROMOTE_TO_PREREG` 후보 0개. A는 방향 전략이 아니며 B/C/D/E는 데이터나 규칙이 막혀 있고 F/G는 경제성·해상도 문제가 있다.

## 조사 순서와 실행 상태

| 순서 | 작업 | 완료 기준 | 상태 |
|---|---|---|---|
| 1 | 출처군별 중복 없는 후보 발굴 | 1차 출처, 규칙, 데이터 요건, 라이선스/누수 위험 확인 | **완료** — 네 출처군 조사. 외부 실적은 미검증으로 분리 |
| 2 | 후보별 Blue/Red/Methods/Judge 심사 | 후보마다 전략성·데이터 자격·비용·독립성 판정 | **완료** — 4역할 모두 최종 의견 회수, 검정 자격 후보 0 |
| 3 | 우선순위 결정 | 실제 데이터가 있고 비용 게이트를 통과할 개연성이 있는 가설만 선정 | **완료** — 아래 데이터 정합성 확인을 가장 먼저 수행. F는 역사 재현/프로토콜 조사에만 제한, 수익 후보로는 보류 |
| 4 | 고정 후보의 성과 검정 | 사전등록, 누출·분할·비용·기준선 통과 | **미실행** — 검정 자격 후보 0개; 성과 숫자 생성 금지 |
| 5 | Phase 9 결합 | 개별 전략 코어 승인 후에만 평가 | **차단** — 승인 코어 없음 |

다음 실행 순서는 ① 현재 연구기간과 겹치지 않는 전진 수집자료의 존재·보존을 확인, ② 보유 아카이브의 mark/funding timestamp 오류 여부를 원본 manifest와 대조, ③ point-in-time OI/청산 자료는 출처·최초 공개 시각까지 별도 검증, ④ 그 뒤에도 비용 후 경제성이 남을 고유 후보만 사전등록, ⑤ 미래 데이터가 쌓이면 단 한 번의 고정 평가, ⑥ 하드 게이트 통과 시에만 WF/민감도/부트스트랩/레드팀 진행한다. 이 순서는 순위가 좋은 과거 수치가 나올 때까지 변형을 반복하는 절차가 아니다.

## 데이터/OOS 경계

- 확인된 `/private/tmp/cointrade-50_50-data`는 1h kline, mark-price, funding 45심볼의 월별 아카이브가 2026-06~2026-09까지 있으나, 메타데이터 감사에서 mark-price 45개 행의 gap 플래그와 funding 8개 행의 interval 불일치가 관측됐다. 원본 파일 내용과 원인에 대한 별도 QA 전에는 전략 평가에 사용하지 않는다.
- 별도 과거 차트 실험은 2026-07-17~2026-10-09 구간을 사용했다. 따라서 2026-06~09 자료는 새 후보의 “미사용 OOS”라고 부르지 않는다.
- `/Volumes/HDD2TB/Trade`는 현재 세션에서 마운트되어 있지 않았다. 해당 경로에서 tick/aggregate-trade 자료를 확인하지 못했다. 이는 NAS에 자료가 없다는 증거가 아니라 현재 접근할 수 없다는 의미다.
- 1h archive는 quarter-hour/100ms 신호의 대용이 될 수 없다. Binance Vision 다운로드는 승인된 역사적 개인·비상업 백테스트 조건 외에 실시간·수동매매 신호 용도로 사용하지 않는다.

## 재현·증거

- 기준 저장소: `/Users/user/Desktop/CODE/trading_bot`, branch `research/bat-harmonic-validation-20261120`, 조사 시작 시 HEAD `92c4563013534e0abbf77a5e3be9e47f38ed1741`, worktree clean.
- 확인 문서: `docs/chart_predictor/SPEC.md`, `docs/chart_predictor/REFERENCES.md`, `docs/chart_predictor/pine/`, `docs/chart_predictor/rounds.md`, `docs/research/registry.jsonl`, `docs/research/inventory/comparable_evaluation_protocol_v1.md`, `docs/research/inventory/PREREG_USDM_1H_SETUP_M2_20261120.md`, `docs/research/inventory/PREREG_CROSS_ASSET_SEESAW_SCREEN_20261120.md`, `docs/research/inventory/PREREG_FUNDING_TAIL_REVERSAL_20261120.md`, `docs/research/inventory/PREREG_USDM_METRICS_SAMPLE_AUDIT_20261120.md`.
- 공개 검색에서 논문 페이지와 공개 출처를 열람했다. SNS/커뮤니티/GitHub의 자체 성과 주장을 독립 재현하지 않았고 외부 코드도 설치·실행하지 않았다.
- 본 라운드 파일 작성 전 저장소 변경은 없었다. 이 문서 자체는 점수·백테스트·전략 승인 기록이 아니다.
