# 셋업 파인더(Setup finder) 참고 자료 조사

- 조사일: 2026-11-14
- 목적: 크립토 단기 매매에서 진입 구간(entry zone), 손절(stop-loss), 익절(take-profit)을 출력하는 셋업 탐지 로직의 공개 레퍼런스 수집 및 평가
- 원칙: 코드를 클론하거나 실행하지 않았음. README와 일부 소스 파일을 `gh api`로 읽고 로직을 요약함. 코드를 이 문서나 프로젝트에 복사하지 않음. 라이선스는 GitHub API가 보고한 값을 기록함 (`NONE`은 라이선스 파일이 없다는 뜻이며, 사용 권한이 없다고 보아야 함).
- 재구현 원칙: 아래 로직은 모두 요약 설명이며, 우리 백테스트에는 직접 구현함.

## 0. 조사 방법과 한계

- `gh search repos` / `gh search code`를 먼저 사용함. 검색 API가 중간에 레이트 리밋(403)에 걸려 여러 키워드 검색이 실패함. 이후 확보한 후보는 `gh api repos/...`로 메타데이터와 README를 직접 조회함.
- 검색이 막힌 뒤 WebSearch를 2회 사용함 (AI 차트 분석 도구, RSI/MACD 다이버전스 레포).
- 한계: 골든 포켓(golden pocket), 거래량 프로파일 기반 셋업, 지지/저항 리테스트 키워드 검색은 결과가 거의 없었음. 해당 항목은 "신뢰 가능한 공개 구현 없음"으로 기록함. 검색 결과에 0~1 스타짜리 저품질 레포가 많아 제외함.
- 평가한 레포 중 실제 README 또는 소스를 읽은 것은 본문에 "읽음"으로 표시함. 메타데이터만 확인한 것은 "미확인"으로 표시함.

## 1. 후보 목록 요약 (스타/갱신/라이선스)

| # | 프로젝트 (URL) | 스타 | 마지막 push | 라이선스 | 언어 | 셋업 계열 | 검증 수준 |
|---|---|---|---|---|---|---|---|
| 1 | [joshyattridge/smart-money-concepts](https://github.com/joshyattridge/smart-money-concepts) | 2222 | 2026-04-03 | MIT | Python | SMC (FVG, OB, BOS/CHoCH, 유동성) | 지표 라이브러리, 백테스트 없음 (읽음) |
| 2 | [Prasad1612/smart-money-concept](https://github.com/Prasad1612/smart-money-concept) | 54 | 2025-09-19 | 없음 | Python | SMC | 미확인 (메타데이터만) |
| 3 | [kxngHADES/SMC-Marking](https://github.com/kxngHADES/SMC-Marking) | 45 | 2026-11-10 | NOASSERTION | Pine v6 | SMC 표시 | 미확인 |
| 4 | [neurotrader888/TrendlineBreakoutMetaLabel](https://github.com/neurotrader888/TrendlineBreakoutMetaLabel) | 121 | 2023-06-14 | MIT | Python | 추세선 돌파 + ATR 브래킷 + 메타 라벨 | 워크포워드 코드 있음 (읽음) |
| 5 | [hackingthemarkets/supertrend-crypto-bot](https://github.com/hackingthemarkets/supertrend-crypto-bot) | 416 | 2023-01-17 | 없음 | Python | SuperTrend 실시간 봇 | 백테스트 없음 (읽음) |
| 6 | [kuncle/supertrend-trading](https://github.com/kuncle/supertrend-trading) | 75 | 2025-12-22 | MIT | Python | SuperTrend + RSI/EMA/MACD/거래량 필터, OI 신호 | 자체 백테스트 주장 (읽음, 검증 약함) |
| 7 | [freqtrade/freqtrade-strategies](https://github.com/freqtrade/freqtrade-strategies) `Supertrend.py` | 5653 (repo) | 2026-09-08 | GPL-3.0 | Python | 3중 SuperTrend 합의 | 하이퍼옵트 결과 있음, 소스 읽음. 주석에 "미검증" 명시 |
| 8 | [i1ya/freqtrade-strategies](https://github.com/i1ya/freqtrade-strategies) | 248 | 2021-07-11 | 없음 | Python | 개인 freqtrade 전략 모음 | 미확인 (파일 목록만) |
| 9 | [stockalgo/stolgo](https://github.com/stockalgo/stolgo) | 365 | 2026-11-03 | MIT | Python | 가격행동(price action): 돌파, 리테스트, 프리셋 | 백테스터 + 프리셋 (읽음) |
| 10 | [Ashwani219/sats-dynamic-swing-backtester](https://github.com/Ashwani219/sats-dynamic-swing-backtester) | 0 | 2026-08-28 | 없음 | Python | SATS(SuperTrend 변형) + 앵커드 VWAP + 스윙 구조 | 진입/청산 규칙 명시 (읽음), 결과 미확인 |
| 11 | [SpiralDevelopment/RSI-divergence-detector](https://github.com/SpiralDevelopment/RSI-divergence-detector) | 115 | 2023-06-07 | MIT | Python | RSI 정규/히든 다이버전스 탐지 | 탐지만, 백테스트 없음 (읽음) |
| 12 | [GZotin/RSI_MACD_strategy](https://github.com/GZotin/RSI_MACD_strategy) | 23 | 2023-03-05 | MIT | Python | RSI + MACD 4단계 규칙 | 교육용 명시 (읽음) |
| 13 | [SpiralDevelopment/candlestick-patterns](https://github.com/SpiralDevelopment/candlestick-patterns) | 539 | 2020-07-23 | MIT | Python | 캔들 패턴 탐지 | 미확인 (메타데이터만), 오래됨 |
| 14 | [hackingthemarkets/candlestick-screener](https://github.com/hackingthemarkets/candlestick-screener) | 682 | 2023-04-07 | 없음 | Python (TA-Lib, Flask) | 캔들 패턴 스크리너 | 스크리너, 백테스트 없음 (README 읽음) |
| 15 | [TA-Lib/ta-lib](https://github.com/TA-Lib/ta-lib) | 1737 | 2026-11-13 | BSD-3-Clause | C (Python 바인딩 있음) | 캔들 패턴 함수 61종 등 지표 라이브러리 | 라이브러리 (권장 의존성) |
| 16 | [xgboosted/pandas-ta-classic](https://github.com/xgboosted/pandas-ta-classic) | 490 | 2026-11-13 | MIT | Python | 지표 라이브러리 (Supertrend, VWAP 등) | 라이브러리, 메타데이터만 확인 |
| 17 | [bfolkens/py-market-profile](https://github.com/bfolkens/py-market-profile) | 412 | 2026-11-07 | NOASSERTION | Python | 마켓 프로파일 / 볼륨 프로파일 계산 | 미확인 (라이선스 파일 직접 확인 필요) |
| 18 | [je-suis-tm/quant-trading](https://github.com/je-suis-tm/quant-trading) | 11254 | 2026-06-20 | Apache-2.0 | Python | 런던 브레이크아웃, RSI/볼린저 패턴 등 | README 읽음. 마찰 없음(수수료/슬리피지 없음) 가정 명시 |
| 19 | [kernc/backtesting.py](https://github.com/kernc/backtesting.py) | 9236 | 2026-08-05 | AGPL-3.0 | Python | 백테스트 프레임워크 | 프레임워크 참고용. AGPL이므로 코드 재사용 주의 |
| 20 | [polakowo/vectorbt](https://github.com/polakowo/vectorbt) | 9841 | 2026-11-11 | NOASSERTION | Python | 벡터화 백테스트 엔진 | 프레임워크 참고용. 라이선스 파일 직접 확인 필요 |
| 21 | [everget/tradingview-pinescript-indicators](https://github.com/everget/tradingview-pinescript-indicators) | 965 | 2026-10-19 | GPL-3.0 | Pine | 다수 지표 모음 | GPL, 재사용 금지 (아이디어만 참고) |
| 22 | [TradersPost/pinescript-agents](https://github.com/TradersPost/pinescript-agents) | 241 | 2026-07-23 | 없음 | Python (Claude Code 툴킷) | Pine 스크립트 생성 보조 | 차트 분석 도구 아님 |
| 23 | [bigmacman1129/crypto-ai-trading-bot](https://github.com/bigmacman1129/crypto-ai-trading-bot) | 201 | 2026-08-25 | GPL-3.0 (README) | JavaScript | 호가창 유동성 기반 마켓메이킹 봇 | 셋업 파인더 아님. 유사 설명의 레포가 다수 존재해 마케팅성 복제로 보임. 제외 |

후보로 검토했지만 제외한 것: `aitradingbotspro/crypto-liquidity-ai-trading-bot` (23번과 동일 설명의 복제본), `maxgfr/ai-strategy-backtester` (스타 0, 라이선스 없음), `Steinwealth/EasyTrendline` (스타 7, 라이선스 없음, XAU 대상 설명), `ZiadFrancis/BreakOutLiquiditySweep` (노트북만, README 없음, 라이선스 없음, 스타 44. 셋업 규칙 확인용 참고 정도).

## 2. 계열별 상세 평가

표기: "진입/손절/익절"은 README 또는 소스에서 읽은 규칙을 한국어로 요약한 것.

### 2-1. Smart Money Concepts (FVG, Order Block, BOS/CHoCH, 유동성 스윕)

**[1] joshyattridge/smart-money-concepts (Python, MIT, 2222 stars, 2026-04-03)**
- 신호: 스윙 고저(swing_length 기준), FVG, BOS/CHoCH, 오더블록, 유동성 풀, 이전 고저, 세션, 리트레이스먼트 비율을 계산하는 지표 패키지. `pip install smartmoneyconcepts`.
- 진입/손절/익절: 패키지는 구조 지표만 제공하며 진입, 손절, 익절 규칙을 정의하지 않음. 따라서 셋업 파인더가 아니라 재료 공급 도구임.
- 타임프레임: 제한 없음 (OHLC 입력).
- 성과 근거: 없음. README에 백테스트나 수익 수치 없음.
- 신뢰도: 구현 설명은 명확하고 라이선스도 MIT임. 다만 ICT 개념을 수치화한 것이라 "오더블록" 정의가 제작자 임의 정의이며 객관적 검증 대상이 아님.
- 판정: 재구현 가치 있음. 우리 쪽에서 FVG/스윙/BOS 정의를 직접 구현하고 파라미터를 고정해 검증할 때 정의 비교용으로 사용. 패키지를 그대로 쓰기보다 정의 규칙만 참고.

**[2] Prasad1612/smart-money-concept (Python, 라이선스 없음, 54 stars)**
- 미확인 (메타데이터만). 라이선스 없음이므로 코드 참고도 자제하고, 필요 시 우리 정의로 독자 구현.

**[3] kxngHADES/SMC-Marking (Pine v6, NOASSERTION, 45 stars)**
- 미확인. TradingView 표시용 지표로 보임. 백테스트 근거 없을 가능성 높음.

**SMC 계열 종합 판정**: 공개 레포 대부분이 "표시(시각화)" 도구이며 진입/손절/익절을 수치로 검증한 사례가 확인되지 않음. 셋업 규칙을 백테스트하려면 우리가 정의를 고정해야 함. 우선순위는 중간 이하(4순위 권장)이며, 유동성 스윕 + CHoCH 조건을 명시적으로 정의해 검증하는 것이 필요함.

### 2-2. 추세선 돌파 (Trendline / Channel Breakout)

**[4] neurotrader888/TrendlineBreakoutMetaLabel (Python, MIT, 121 stars, 2023-06-14)**
- 신호: 최근 `lookback`개 종가에 대해 저항선과 지지선을 피팅하고(잔차 기반), 종가가 투영된 저항선을 상향 돌파하면 롱 진입 후보로 기록함. 이후 메타 라벨(Random Forest) 모델이 각 진입 후보의 승률 확률을 예측해 거래 필터로 사용함.
- 진입: 종가가 저항선 위로 돌파한 바의 다음 처리(코드 기준 해당 바 종가 진입).
- 손절/익절 (소스 `trendline_break_dataset.py` 읽음): 진입가 기준 `SL = entry − 3 × ATR`, `TP = entry + 3 × ATR`, 보유 기간 12바. 세 조건 중 먼저 충족되는 것으로 청산. ATR 룩백 168. 라벨은 수익 > 0.
- 타임프레임: 샘플 데이터 BTCUSDT 1시간(`BTCUSDT3600.csv`).
- 성과 근거: 정식 리포트는 없음. `walkforward.py`에 워크포워드 학습(`train_size`, `step_size` 롤링, 각 구간은 이전 구간 거래로만 학습)이 구현되어 있음. 이는 아웃 오브 샘플 평가 구조로 긍정적임. 다만 수수료와 슬리피지 처리는 코드에서 확인되지 않음 (grep 결과 없음). 샘플 데이터 기간과 결과 수치는 README에 없음.
- 신뢰도: 워크포워드 구조는 평가 방식 면에서 가장 신뢰할 만한 편. 그러나 README에 결과가 없고, 수수료 미반영이 확인됨. 우리가 재검증해야 함.
- 판정: 재구현 가치 높음. 추세선 피팅 방법, ATR 기반 3:3 브래킷, 워크포워드 평가 틀을 우리 방식으로 다시 짜 볼 것. 메타 라벨 부분은 2차 단계로 미룸.

**[5] varshithsai17-boop/trendline-breakout-backtester (Python, 스타 1, 라이선스 없음)**
- EMA50/200 + 윌리엄스 프랙탈 기반 추세선 돌파 이벤트 백테스터. 스타 1이고 근거 부족. 참고만.

### 2-3. 지지/저항 + 돌파/리테스트 (Support/Resistance Breakout and Retest)

**[6] stockalgo/stolgo (Python, MIT, 365 stars, 2026-11-03)**
- 신호: 가격행동 DSL. 예: `pa.crosses_above(pa.resistance(21))`. 프리셋으로 `consolidation_breakout`(박스 돌파), `breakout_intraday`(일봉 S/R 돌파 + 인트라데이 트리거), `failed_break_intraday`(실패 돌파 역방향), `scalp_green_fade`, `parabolic_short`이 있음.
- 진입/손절/익절 (README 읽음): `trade.long(ctx, rr=(1, 2), stop="candle_low")`는 손절을 신호 캔들의 저점, 목표를 리스크의 2배로 둠. 숏은 `stop="candle_high"`, `rr=(1,3)`.
- 타임프레임: 일봉 레벨 + 인트라데이 트리거 등 다중 타임프레임 지원.
- 성과 근거: README는 "look-ahead 없음", 수수료/슬리피지 설정(`commission`, `slippage`), 샤프/드로다운 리포트를 기능으로 설명함. 그러나 프리셋의 실제 백테스트 결과 수치는 README에 없음. "battle-tested"라는 표현은 근거 없는 마케팅 문구로 봄.
- 신뢰도: 엔진 설계(다음 바 시가 체결 옵션, 룩어헤드 방지 주장)는 좋음. 성과 주장은 미검증.
- 판정: 재구현 가치 있음. 특히 "손절 = 신호 캔들 저점, 목표 = 2R" 규칙은 간단해 우리 백테스트의 기본 기준선으로 쓸 만함. 엔진 자체는 MIT라 아이디어 참고 가능하나 코드 복사 금지.

### 2-4. 슈퍼트렌드 / EMA 리본 + ATR 손절

**[7] freqtrade/freqtrade-strategies `Supertrend.py` (repo GPL-3.0, 5653 stars, 2026-09-08)**
- 소스 읽음. 신호: 서로 다른 (배수, 기간) 조합의 SuperTrend 3개가 모두 상승이면 매수, 3개가 모두 하락이면 매도. 파라미터는 하이퍼옵트로 얻은 값(buy_m1/p1 등 IntParameter).
- 진입/손절/익절: 진입은 3개 방향 합의 시점. 손절 고정값 -26.5%, 트레일링 스톱 양수 임계(5%, 오프셋 14.4%), ROI 테이블(0분 8.7%, 372분 5.8%, 861분 2.9%, 이후 0). 즉 목표는 시간 기반으로 줄어드는 ROI 테이블.
- 타임프레임: 1시간봉.
- 성과 근거: 전략 파일 주석에 "구현이 논문과 일치한다고 검증되지 않았다"고 명시되어 있음. 하이퍼옵트는 특정 기간(2021~)에 맞춘 값이므로 과최적화 위험이 큼. 샘플 외 검증 근거 없음.
- 신뢰도: 낮음~중간. 정직한 주석이 있으나 손절 -26.5%는 크립토 단기 매매 기준으로 과도함.
- 판정: 재구현 가치 있음. "SuperTrend 방향 전환 + ATR 기반 트레일링"이라는 구조만 가져오고, 파라미터는 우리가 워크포워드로 다시 찾을 것. 상위 계열로 1순위 후보.

**[8] hackingthemarkets/supertrend-crypto-bot (Python, 라이선스 없음, 416 stars, 2023-01-17)**
- 소스 `supertrend.py` 일부 확인: 기간 7, 배수 3 기본값. 상단/하단 밴드는 HL2 ± 배수×ATR. 매수/매도는 ccxt로 시장가 주문을 내는 실거래 봇 구조. 주문 규모는 고정 수량 0.05 ETH.
- 진입/손절/익절: 밴드 전환 시 시장가 진입/청산. 손절과 익절 규칙은 별도로 없음 (반전 신호가 곧 청산).
- 성과 근거: README에 유튜브 링크만 있고 백테스트 없음.
- 판정: 재구현 가치는 낮음. 라이선스가 없고 로직이 단순해 우리 쪽에서 직접 구현하는 편이 빠름. 실주문 코드는 참고하지 말 것.

**[9] kuncle/supertrend-trading (Python, MIT, 75 stars, 2025-12-22)**
- 소스가 아닌 README 읽음 (중국어). SuperTrend(ATR 14, 배수 3.0, 일봉)에 RSI(<70 매수), EMA 정렬, MACD 히스토그램, 거래량(평균 이상) 필터를 붙임. 별도로 OI(미결제약정)와 자금조달률 기반 5분봉 "SAFE/DANGER" 신호가 있음.
- 진입/손절/익절: SuperTrend 방향 전환 + 필터 통과 시 진입. OI 신호는 가격 임계 0.1%. 손절은 README 예시에서 "3%"로 언급되나 백테스트 엔진에 명시 규칙이 있는지는 확인 못함.
- 타임프레임: 일봉(SuperTrend), 5분봉(OI).
- 성과 근거 (주장): 일봉 SuperTrend 조합 전략 승률 71%, 누적 수익 +141%, 최대 낙폭 21.2%, 샤프 1.06 (2.7년). 5분봉 OI 신호 승률 71%, 표본 21건, 테스트 데이터 1.7일, 연환산 "~480%"는 이론값.
- 신뢰도: 낮음. (a) 파라미터를 "회테스트 최적"이라고 명시 (샘플 내 최적화), (b) 샘플 외 구간 없음, (c) 수수료/슬리피지 미반영을 README가 스스로 인정, (d) 5분봉 신호의 표본 21건과 1.7일 기간으로 연환산 수치를 낸 것은 근거 부족. 일봉 조합 7회 거래도 통계적으로 매우 작음. 마케팅성 수치로 분류.
- 판정: 로직 아이디어(SuperTrend + 거래량/모멘텀 필터)만 참고. 수치는 신뢰하지 말 것.

**[10] Dodo33/gekko-supertrend-strategy (JavaScript, MIT, 83 stars, 2018-03-07)**
- 2018년 Gekko 전략. 갱신이 중단된 지 오래되어 참고 가치 낮음. 제외.

**[11] Ashwani219/sats-dynamic-swing-backtester (Python, 라이선스 없음, 스타 0, 2026-08-28)**
- README 읽음. 신호: SATS(적응형 SuperTrend + 추세 품질 지수 TQI)의 매수/매도 플립과 동적 스윙 구조(HH/HL/LH/LL, 전방 확정, 룩어헤드 없음 주장)를 결합.
- 진입: 롱은 새 HL(저점 상승) 확정 후 SATS 매수 플립이 나오면 다음 바 시가 진입. 숏은 대칭.
- 청산: 롱은 새 HH 확정 시점에 청산하고, SATS 추세가 하락이면 숏 전환. 손절은 README 일부만 읽어서 확인 못함.
- 성과 근거: README에 수치 없음 (BTC 15분봉 대상으로 설계). 스타 0, 라이선스 없음.
- 판정: 규칙 구조(구조 확정 + 지표 플립 + 앵커드 VWAP)는 참고할 가치 있음. 저품질 레포이므로 구현은 우리 쪽에서 정의를 직접 만들 것.

### 2-5. VWAP / 거래량 급증 / 볼륨 프로파일

**[12] xgboosted/pandas-ta-classic (Python, MIT, 490 stars, 2026-11-13)**
- 지표 라이브러리 (VWAP, 앵커드 VWAP, SuperTrend, 볼륨 지표 포함으로 알려짐. 메타데이터만 확인). 셋업 로직 없음. 지표 계산 용도로 적합.

**[13] bfolkens/py-market-profile (Python, NOASSERTION, 412 stars, 2026-11-07)**
- 마켓 프로파일(볼륨 프로파일) 계산 라이브러리. POC, 가치 영역(Value Area) 계산용. 셋업 규칙은 없음. 라이선스 파일을 직접 확인해야 함 (NOASSERTION).
- 판정: 볼륨 프로파일 계산 검증용으로 참고 가능. 셋업 로직은 우리가 정의.

**[10 재참고] SATS + 앵커드 VWAP 백테스터**: 위 2-4의 11번 참조. VWAP 계열은 공개 셋업 레포가 사실상 이것 하나뿐이며, 결과 근거 없음.

**VWAP/볼륨 계열 종합**: 거래량 급증이나 VWAP 눌림목을 "진입 셋업"으로 완결한 신뢰할 만한 오픈소스 백테스트는 찾지 못함. 계산 라이브러리 위주. 우리가 직접 정의해야 함.

### 2-6. 피보나치 되돌림 (골든 포켓)

**[14] panzmoravylab/Fibonacci_Pro (Pine v6, 스타 20, 라이선스 없음 (README 배지는 MIT라고 주장), 2025-09-11)**
- 신호: ZigZag 피벗으로 자동 피보나치 레벨 생성. 0.618 또는 0.786 레벨을 가격이 상향 돌파하고 상승 캔들 + 거래량 조건이 맞으면 매수 신호.
- 진입/손절/익절: 매수 신호 시점 진입. 손절/익절은 README에 "적절한 손절 설정" 외에 구체 규칙 없음.
- 성과 근거: 없음.
- 판정: 재구현 가치 낮음. 라이선스 표기가 충돌함(배지 MIT, API 없음). 골든 포켓 정의(0.618~0.65 등)를 우리가 직접 고정하는 것이 더 나음.

**골든 포켓 종합**: "golden pocket" 키워드 검색 결과는 대부분 스타 0의 짧은 레포였고, 신뢰할 만한 백테스트 구현을 찾지 못함. 계열 자체는 정의 문제(어느 스윙을 기준으로 할지)가 커서 우리 정의가 필요함.

### 2-7. 캔들 패턴 반전 (Candlestick Reversal)

**[15] TA-Lib/ta-lib (C, BSD-3-Clause, 1737 stars, 2026-11-13)**
- 캔들 패턴 함수(망치형, 장악형 등)를 제공하는 표준 라이브러리. 라이선스 BSD-3로 가장 안전함. 셋업 규칙은 없음.
- 판정: 패턴 탐지 기반으로 채택 권장. 라이브러리 의존성으로 사용.

**[16] hackingthemarkets/candlestick-screener (Python, 라이선스 없음, 682 stars, 2023-04-07)**
- README 읽음. TA-Lib 패턴을 웹 스크리너로 보여주는 도구. 진입/손절/익절 규칙이나 백테스트 없음. 판정: 참고만.

**[17] SpiralDevelopment/candlestick-patterns (Python, MIT, 539 stars, 2020-07-23)**
- 캔들 패턴 탐지기. 미확인 (메타데이터만). 오래되었음. 판정: 패턴 정의 비교용.

**캔들 계열 종합**: 패턴 탐지는 충분히 많음. 그러나 "패턴 + 레벨 근접 + 확인 캔들"을 하나의 셋업으로 묶어 백테스트 결과를 공개한 레포는 확인되지 않음.

### 2-8. 다이버전스 (RSI / MACD)

**[18] SpiralDevelopment/RSI-divergence-detector (Python, MIT, 115 stars, 2023-06-07)**
- 신호: RSI의 정규/히든 강세·약세 다이버전스 탐지. TA-Lib 사용. BTCUSDT 일봉 2020-11~2022-03 구간 시각화 결과 제시.
- 진입/손절/익절: 정의 없음 (탐지 후 시각화만). 텔레그램 알림 샘플 있음.
- 성과 근거: 없음 (시각화만).
- 판정: 피벗 기반 다이버전스 탐지 로직의 정의 비교용으로 참고. 셋업 완결 규칙은 우리가 정의.

**[19] GZotin/RSI_MACD_strategy (Python, MIT, 23 stars, 2023-03-05)**
- 신호: RSI가 매수 구간에서 신호를 내고 MACD가 확인하는 4단계 규칙(RSI 매수 신호 → MACD 확인 → RSI 매도 신호 → MACD 확인). 원 기사는 4시간봉. 저자는 1시간봉으로 시험.
- 진입/손절/익절: 손절/익절 규칙 없이 RSI/MACD 교차 시 청산. 리스크 관리 부재.
- 성과 근거: README는 "교육용 전용"이라고 명시하며 수익 수치 근거는 없음 (기사 기반).
- 판정: 재구현 가치 낮음. 우리 다이버전스 셋업의 대조군(baseline) 정도로만 가치.

**다이버전스 계열 종합**: 탐지기는 있으나, 다이버전스 + 손절/익절 + 수수료 반영까지 포함한 백테스트 공개 레포는 확인하지 못함. WebSearch의 DEV 글(다중 타임프레임 RSI/MACD, "승률 42%→61%")은 방법론이 없어 검증 불가로 분류.

### 2-9. AI 차트 분석 도구 (gptchart.ai 유형)

- gptchart.ai 자체의 오픈소스 레포는 찾지 못함. WebSearch 결과는 제작자 본인이 쓴 것으로 보이는 홍보성 글뿐이며, 진입/손절/익절을 차트에서 제안한다고만 설명함. 독립 검증 없음. 이 도구의 수치는 검증 불가로 분류.
- 관련 오픈소스: [TradersPost/pinescript-agents](https://github.com/TradersPost/pinescript-agents) (241 stars, 라이선스 없음)는 Claude Code 기반 Pine 스크립트 생성 도구이며 차트 이미지 분석 도구가 아님. 제외.
- 판정: 이 계열은 셋업 로직의 근거로 쓰지 않음. LLM 판단은 백테스트 가능한 규칙으로 바꿀 수 없으므로 우리 파이프라인에서 제외 권장. 필요하면 "LLM이 규칙을 제안하고 우리 백테스트가 검증"하는 구조만 고려.

## 3. 라이선스 주의 목록

| 구분 | 프로젝트 | 라이선스 | 처리 |
|---|---|---|---|
| 강한 카피레프트 | kernc/backtesting.py | AGPL-3.0 | 코드 재사용 금지. 개념만 참고 |
| 카피레프트 | freqtrade/freqtrade-strategies, freqtrade/freqtrade | GPL-3.0 | 코드 재사용 금지. 아이디어만 참고 |
| 카피레프트 | everget/tradingview-pinescript-indicators | GPL-3.0 | 코드 재사용 금지 |
| 카피레프트 | bigmacman1129/crypto-ai-trading-bot | GPL-3.0 (README) | 사용 대상 아님 |
| 라이선스 불명 (NOASSERTION) | bfolkens/py-market-profile, polakowo/vectorbt, kxngHADES/SMC-Marking, LouisLetcher/quant-pine | GitHub 자동 판독 실패 | LICENSE 파일 직접 확인 전까지 코드 사용 금지 |
| 라이선스 없음 (NONE) | hackingthemarkets/supertrend-crypto-bot, Prasad1612/smart-money-concept, i1ya/freqtrade-strategies, Ashwani219/sats-dynamic-swing-backtester, panzmoravylab/Fibonacci_Pro (README는 MIT 주장), hackingthemarkets/candlestick-screener, ZiadFrancis/BreakOutLiquiditySweep | 없음 | 저작권 기본 보호. 코드 참고 금지, 로직은 우리가 독자 정의 |
| 허용적 (MIT/Apache/BSD) | joshyattridge/smart-money-concepts, neurotrader888/TrendlineBreakoutMetaLabel, kuncle/supertrend-trading, stockalgo/stolgo, SpiralDevelopment/RSI-divergence-detector, GZotin/RSI_MACD_strategy, SpiralDevelopment/candlestick-patterns, xgboosted/pandas-ta-classic, je-suis-tm/quant-trading (Apache-2.0), TA-Lib/ta-lib (BSD-3) | MIT / Apache-2.0 / BSD-3 | 아이디어 재구현 허용. 코드 복사 시 라이선스 고지 필요 (우리 방침상 복사 안 함) |

## 4. 우선순위와 판정 요약

| 순위 | 계열 | 대표 레포 | 근거 강도 | 판정 |
|---|---|---|---|---|
| 1 | SuperTrend 방향 전환 + ATR 트레일링 | freqtrade Supertrend (GPL, 아이디어만), kuncle (MIT, 수치 신뢰 낮음) | 낮음~중간 (미검증 주석 있음) | 재구현, 워크포워드로 파라미터 재탐색 |
| 2 | 추세선 돌파 + ATR 브래킷(3:3) + 워크포워드 | neurotrader888 (MIT, 워크포워드 구조) | 중간 (구조는 좋음, 수수료 미반영) | 재구현, 수수료/슬리피지 추가 |
| 3 | S/R 돌파 + 리테스트 (2R 목표, 신호봉 저점 손절) | stolgo (MIT, 프리셋 + 엔진) | 낮음 (성과 수치 없음, 엔진 설계는 양호) | 재구현, 기준선(baseline)으로 사용 |
| 4 | SMC: 유동성 스윕 + CHoCH + 오더블록/FVG 리테스트 | joshyattridge (MIT, 지표만) | 없음 (정의만 존재) | 정의를 명시적으로 고정해 검증 |
| 5 | 앵커드 VWAP 눌림목 (스윙 구조 확정 후) | Ashwani219 (라이선스 없음, 규칙 설명 명확) | 없음 | 규칙 참고 후 독자 구현 |
| 6 | RSI 정규 다이버전스 (피벗 확정 후) | SpiralDevelopment (MIT, 탐지만) | 없음 | 탐지 정의 참고 후 손절/익절 직접 설계 |
| 7 | 캔들 반전 패턴 (레벨 근접 + 확인) | TA-Lib (BSD-3) | 없음 (패턴 라이브러리만) | 라이브러리 사용 + 독자 규칙 |
| 8 | 피보나치 골든 포켓 (0.618~0.786 리트레이스 + 확인봉) | panzmoravylab (라이선스 불명, 근거 없음) | 없음 | 우리 정의로 구현, 최하위 우선 |

AI 차트 분석 도구(gptchart 유형): 검증 불가, 제외.

## 5. 최종 권고: 먼저 백테스트할 8개 셋업 계열 (순위별)

모든 규칙은 "신호 확정 후 다음 바 시가 체결, 수수료 0.05~0.1%/편도, 슬리피지 반영, 워크포워드 샘플 외 검증"을 기본 조건으로 함.

1. **SuperTrend 방향 전환**: SuperTrend(ATR 기간 14, 배수 3 기준값) 방향이 하락에서 상승으로 바뀌면 다음 바 시가에 롱 진입한다. 손절은 진입 시점의 SuperTrend 밴드선(또는 진입가 − 2×ATR 중 더 가까운 쪽)에 두고, 익절은 SuperTrend가 반대로 전환될 때 청산하는 트레일링 방식으로 둔다.
2. **추세선 돌파 + ATR 브래킷**: 최근 N개 고점/저점으로 추세선을 피팅하고, 종가가 추세선을 상향 돌파하면 다음 바 시가에 롱 진입한다. 손절은 진입가 − 3×ATR, 익절은 진입가 + 3×ATR로 두고, 12바 안에 어느 쪽도 안 닿으면 시간 청산한다.
3. **지지/저항 돌파 후 리테스트**: 저항선을 종가로 돌파한 뒤, 가격이 그 레벨까지 되돌아와 지지받고 상승 캔들이 나오면 다음 바 시가에 롱 진입한다. 손절은 신호 캔들 저점 아래, 익절은 리스크의 2배(1:2)로 둔다.
4. **유동성 스윕 + CHoCH + 리테스트**: 직전 스윙 저점 아래로 꼬리만 내려갔다가 종가가 다시 올라오고(스윕), 이후 직전 하락 구조의 고점을 종가로 돌파(CHoCH)하면 그 구간의 오더블록(또는 FVG) 되돌림에서 롱 진입한다. 손절은 스윕 꼬리 저점 아래, 익절은 반대편 유동성(직전 스윙 고점)으로 둔다.
5. **앵커드 VWAP 눌림목**: 상승 구조(HL 확정)가 나온 뒤 가격이 앵커드 VWAP 근처까지 눌리고 상승 전환 캔들이 나오면 롱 진입한다. 손절은 직전 스윙 저점 아래, 익절은 직전 스윙 고점(HH 확정) 또는 리스크 2배 중 먼저 닿는 쪽으로 둔다.
6. **RSI 정규 다이버전스**: 가격은 저점을 낮추는데 RSI는 저점을 높이는 강세 다이버전스가 피벗 확정 후 나오면, 확정 캔들 다음 바 시가에 롱 진입한다. 손절은 가격 피벗 저점 아래, 익절은 RSI 50 회귀 또는 2R 중 먼저 닿는 쪽으로 둔다.
7. **레벨 위의 캔들 반전 패턴**: 지지 레벨(또는 VWAP, 이전 고점) 근처에서 TA-Lib의 강세 장악형 또는 망치형 패턴이 나오고 다음 캔들이 그 고점을 넘기면 진입한다. 손절은 패턴 최저점 아래, 익절은 1.5R~2R로 둔다.
8. **피보나치 골든 포켓 되돌림**: 직전 상승 스윙(저점→고점)을 기준으로 0.618~0.786 구간까지 되돌림이 나오고 그 안에서 상승 확인 캔들이 나오면 롱 진입한다. 손절은 0.886 레벨 또는 스윙 저점 아래, 익절은 스윙 고점(1.0) 또는 1.272 확장으로 둔다.

## 6. 참고: 제외 또는 보류한 항목

- `aitradingbotspro/crypto-liquidity-ai-trading-bot`: 23번 레포와 같은 설명의 복제본. 마케팅성 레포로 판단하여 제외.
- `Steinwealth/EasyTrendline`: 스타 7, 라이선스 없음, XAUUSD 대상. 제외.
- `ming86/trendline-breakouts`: 2014년 MT4 EA. 오래됨. 제외.
- MQL5 기반 SMC EA들(KVignesh122, carlosrod723, foeed 등): 메타데이터만 확인했고 대부분 XAUUSD/MT5 대상이며 라이선스가 불명확하거나 없음. 크립토 단기 매매 목적과 맞지 않아 제외.
- 조사 공백: 검색 레이트 리밋으로 "volume spike", "support resistance retest", "golden pocket" 키워드의 추가 검색이 실패함. 필요 시 조사를 이어서 할 수 있음.

## 에이전트/스킬/MCP 런타임 후보 검토 (2026-11-14, `gh`로 사실 재확인)

| 저장소 | 실제 별 수 | 라이선스 | 최근 갱신 | 언어 |
|---|---:|---|---|---|
| Jakeschincariol/day-trader-skill | 7,657 | MIT | 2026-10-20 | Python |
| TauricResearch/TradingAgents | 122,488 | Apache-2.0 | 2026-11-04 | Python |
| tradesdontlie/tradingview-mcp | 7,181 | MIT(LICENSE 파일 원문 확인, `gh` 메타데이터 표시는 틀림) | 2026-10-21 | JS |
| matulessy/tradingview-mcp-jackson | 1 | 불명확("other") | 2026-05-26(6개월 정체) | JS |

**① day-trader-skill — 우리 알림 시스템과 구조가 가장 비슷하다.**
`trader-scanner`(종목 스캔) → `trader-entry`/`trader-exit`(진입·손절·목표 플랜) → `trader-timemachine`(같은 규칙을 과거 60일 전 구간에 10,000회 몬테카를로 + 실제 과거 발동 사례로 재현해 목표/손절/무승부 확률 산출) → `trader-risk`/`trader-budget` → `trader-broker`(실주문은 **3중 승인**: 당일 리스크 통과 + 사용자가 그 주문에 "yes"라고 명시 + Claude 자체 Allow 카드 재확인). 미국 주식/Alpaca 대상이라 코인 선물로는 이식 필요하지만, **승인 게이트 패턴과 "시뮬레이션이지 예측 아님"을 매번 명시하는 태도**는 그대로 가져올 가치가 있다. MIT라 코드 재사용 가능.

**② TradingAgents — 무겁다. "튜닝 끝난 뒤 API 켠다" 단계의 후보지, 지금은 아니다.**
애널리스트/불-베어 리서치팀/트레이더/리스크팀/포트폴리오매니저로 역할을 나눈 멀티에이전트 토론 프레임워크. 결정마다 LLM 호출이 여러 번 겹쳐 비용·지연이 크고, 기본 대상도 미국주식/일봉 스윙이라 분봉 단타와 안 맞는다. Apache-2.0이라 재사용엔 문제없다. 지금 단계(규칙+임계값 검증 중)에는 과하다 — API 키 사용 승인 이후 "판단 레이어" 후보로만 남겨둔다.

**③ tradingview-mcp — linuxserver에서는 못 쓴다.**
TradingView **데스크톱 앱(GUI, 유료 구독 필요)**이 실제로 켜져 있어야 하고 그 Electron 디버그 포트(CDP)에 붙는 방식이다. 리눅스 서버는 헤드리스라 이 방식이 안 맞는다. 맥에서 사람이 직접 차트 보며 쓰는 보조 도구로는 쓸 수 있어도, 24시간 자동 알림 엔진 쪽에는 맞지 않는다.

**④ tradingview-mcp-jackson — 보류.** 별 1개, 6개월째 업데이트 없음, 라이선스 불명확. 지금은 채택하지 않는다.

**결론**: 런타임(openclaw/Hermes/자체구축)은 여전히 미정이지만, **어느 쪽으로 가든 day-trader-skill의 스캔→플랜→시뮬레이션→승인게이트 구조를 참고 설계로 쓰는 게 맞다.** 아무것도 설치/실행하지 않았다 — 승인 받고 진행한다.
