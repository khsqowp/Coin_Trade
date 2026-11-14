# TradingView Pine Script / 포트 수집 인덱스: 추세·모멘텀·돌파·변동성 (trend / momentum / breakout / volatility)

- 작성일: 2026-11-14
- 목적: 진입가를 자동으로 정하고 손절(SL)·익절(TP) 박스/라인을 그리는 스크립트 수집 (포지션 툴 스타일)
- 저장 경로: `/Users/user/CODE/Coin_Trade/chart_predictor/data/pine_refs/trend/` (gitignore 대상 `data/`; 라이선스 허용 14개 파일 + 라이선스 원문)

## 0. 수집 방법과 한계

- **GitHub**: `gh search code ... extension:pine`(확장자 필터가 있어야 결과가 나옴), `gh search repos`, 레포별 `gh api`로 파일과 라이선스 직접 확인. 검색 API 한도(분당 30회)에 걸려 여러 번 대기 후 재시도.
- **TradingView**: WebSearch로 목록을 얻고, 공개 스크립트 페이지 12개를 한 페이지씩 읽음(WebFetch, 페이지 텍스트 기준, 그중 2개는 404). 스크립트 소스 코드는 페이지에서 보이지 않는 경우가 대부분이라 **TradingView 항목의 규칙은 작성자 설명 기준**이며 코드 검증이 아님.
- **보호/초대 전용 스크립트는 열지 않음**: `Supertrend Strategy With Multi-TP/TSL` (PROTECTED SOURCE), `ORB Fusion Adaptive` (INVITE-ONLY) 제외.
- **404 응답**: `Squeeze Breakout Strategy [KedArc Quant]`, `EMA 12/21 Crossover with ATR-based SL/TP`는 페이지 조회 실패. 검색 목록 설명만 기재하고 "목록 정보"로 표시.
- **TradingView 라이선스**: 요청서의 "기본 MPL-2.0"은 확인되지 않음. 읽은 페이지 대부분은 "OPEN-SOURCE SCRIPT" 표시만 있고 라이선스 본문이 없음. 따라서 TradingView 스크립트는 **원문을 저장하지 않고 링크와 요약만 기재**.
- **좋아요 수**: 페이지 숫자가 라벨 없이 표시되어 대부분 "미확인". 확실한 경우에만 기재.
- **성과 수치**: 대부분 "미기재". 작성자 주장은 모두 **미검증**으로 표시.

### 라이선스 분류 (저장 기준)

| 라이선스 | 처리 |
|---|---|
| MIT / Apache-2.0 / MPL-2.0 | 원문과 라이선스 문구를 함께 저장 |
| GPL-3.0 | 로컬 학습용으로만 저장, 라이선스 원문 포함 |
| 없음 (NONE) / CC-BY-NC-SA / AGPL-3.0 / NOASSERTION | 링크와 요약만 기재, 저장하지 않음 |

---

## 1. 요약 표 A: TradingView 공개(OPEN-SOURCE) 스크립트

| # | 이름 | 작성자 | 출처 URL | 좋아요 | 게시/갱신 | 라이선스 표시 | 타입 | 진입 | SL | TP | 저장 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| T1 | SuperTrade ST1 Strategy | SupertradeOfficial | https://www.tradingview.com/script/AyY3vB17-SuperTrade-ST1-Strategy/ | 미확인 | 2025-05-09 / 갱신 미기재 | OPEN-SOURCE (본문 없음) | strategy (목록) | SuperTrend 음→양 전환 + 종가 > ST + 종가 > EMA200 | 진입가 − 1×ATR | 진입가 + 4×ATR (1:4) | 링크만 |
| T2 | Open Range Breakout Strategy With Multi TakeProfit | Milvetti | https://www.tradingview.com/script/Tr0vgxkq-Open-Range-Breakout-Strategy-With-Multi-TakeProfit | 미확인 | 2025-08-13 / 미기재 | OPEN-SOURCE | strategy (보고서 탭) | 오프닝 레인지 상/하단 돌파 (세션 창) | 레인지 중간 또는 레인지 반대편 바깥 (선택) | RR 기반 2개 목표, 수량 분할 | 링크만 |
| T3 | IU Opening range Breakout Strategy | Shivam_Mandrai | https://www.tradingview.com/script/JnOdejSN-IU-Opening-range-Breakout-Strategy | 미확인 | 2024-12-12 / 미기재 | OPEN-SOURCE | strategy (보고서 탭) | 종가가 레인지 고점 상향 / 저점 하향 돌파, 포지션 없을 때만 | 직전 봉 저점(롱) / 고점(숏) | RR 2:1 기본 | 링크만 |
| T4 | Squeeze Breakout Strategy [KedArc Quant] | 미확인 | https://www.tradingview.com/script/v7qmcxJZ-Squeeze-Breakout-Strategy-KedArc-Quant | 미확인 | 미확인 (404) | OPEN-SOURCE (목록) | strategy (목록) | BB가 KC 안에 들어간 뒤 모멘텀 필터 방향으로 확장 돌파 (목록 설명) | ATR 스톱 (목록) | 1R 부분익절 + Chandelier 트레일 (목록) | 링크만 |
| T5 | BB Breakout + Momentum Squeeze [Strategy] | WunderTrading | https://www.tradingview.com/script/LYoe08Gn-BB-Breakout-Momentum-Squeeze-Strategy | 미확인 | 2025-04-08 / 미기재 | OPEN-SOURCE | strategy (라벨) | Bull/Bear Power 선이 50선 상/하 돌파 + TTM 스퀴즈 녹색 점 | 롱: 하단 ATR 밴드 / 숏: 상단 ATR 밴드. 절반 목표 도달 시 본전 이동 | RR 1:1.5 | 링크만 |
| T6 | Casper SMC: 5m ORB + Retest | hoosn1ck | https://www.tradingview.com/script/muLbjEdA-Casper-SMC-5m-ORB-Retest/ | 미확인 | 연도 미표시 Feb 23 / 갱신 Mar 3 | OPEN-SOURCE | strategy (보고서 탭) | NY 09:30–09:35 레인지 돌파 후 심지 되돌림 + 몸통 유지 재진입 (리테스트) | 초기: ORB 중간값. 부분익절 후 나머지는 ORB 경계로 이동 | 고정 RR. 옵션: 50% @1R + 잔량 2–2.5R (예시) | 링크만 |
| T7 | NeuraEdge ORB Opening Range Breakout Indicator | Darkmatter513 | https://www.tradingview.com/script/Sb0YgLYU-NeuraEdge-ORB-Opening-Range-Breakout-Indicator/ | 미확인 (138 라벨 불명) | 연도 미표시 Jan 11 / 갱신 Mar 5 | OPEN-SOURCE (교육용 명시) | indicator (작성자 설명) | 돌파 확정 또는 리테스트 모드 (기본 리테스트). 필터: 거래량 1.2×, EMA, VWAP | 레인지 반대편 / 중간 / 1.5×ATR 중 선택 | 진입 − 손절 거리 × RR (1.0–5.0, 기본 1.5). 80봉 후 자동 청산 | 링크만 |
| T8 | Volume Momentum Breakout + TP/SL | Uncle_the_shooter | https://www.tradingview.com/script/hNqs0Z2D-Volume-Momentum-Breakout-TP-SL/ | 미확인 (1.3K 라벨 불명) | 연도 미표시 Mar 6 | OPEN-SOURCE | indicator (작성자 설명) | 피벗 돌파 또는 OB/OS 크로스 봉 위에 박스, 박스 밖 종가 돌파 | ATR 1.5× 또는 % | RR 3단계 (기본값 미기재) | 링크만 |
| T9 | Donchian Breakout Strategy | millerrh | https://www.tradingview.com/script/hyYvFjux-Donchian-Breakout-Strategy | 미확인 (1.4K 라벨 불명) | 2020-01-01 / 2023-08-23 | OPEN-SOURCE | strategy (보고서 탭) | 돈치안 상단 돌파 (선택: MA 필터) | 하단 돈치안 채널 트레일 (선택: 초기 좁은 채널) | 미기재 | 링크만 |
| T10 | 3 EMA Pullback Strategy with ATR | SPLpulse | https://in.tradingview.com/script/LofwH6lh-3-EMA-Pullback-Strategy-with-ATR | 19 (추정) | 2025-07-28 / 미기재 | OPEN-SOURCE | 제목상 indicator, 설명상 strategy | 미기재 | 미기재 | 미기재 | 링크만 (정보 부족) |
| T11 | VWAP Reclaim (Retest) | samjNQ | https://jp.tradingview.com/script/glll4xvz-VWAP-Reclaim/ | 미확인 | 6월 9일 (연도 미표시) | OPEN-SOURCE | indicator ("does not place trades") | 일봉 앵커 VWAP 재탈환 → VWAP 리테스트 → 리테스트 봉 고점 돌파 | 리테스트 스윙 밖 + 0.5 ATR 버퍼 | R×1.5 (표시용, 하드 청산 아님) | 링크만 |
| T12 | EMA 12/21 Crossover with ATR-based SL/TP | 미확인 | https://tw.tradingview.com/script/wrMWMOyF-EMA-12-21-Crossover-with-ATR-based-SL-TP | 미확인 | 미확인 (404) | OPEN-SOURCE (목록) | 미확인 | EMA 12/21 크로스 (목록) | 1.5×ATR (목록) | 2×ATR (목록) | 링크만 |
| T13 | Quantum Ribbon Lite | 미확인 | https://in.tradingview.com/script/49ak1Mix-Quantum-Ribbon-Lite | 미확인 | 미확인 | OPEN-SOURCE (목록) | 미확인 | 5층 EMA 리본 기반 (목록) | ATR 적응형 (목록) | R배수 (2R 설정 예시, 목록) | 링크만 |
| T14 | Gradient Ribbon / EMA Ribbon Slope-Acceleration System | 미확인 | https://in.tradingview.com/script/X0F9OE4L-Gradient-Ribbon-EMA-Ribbon-Slope-Acceleration-System/ | 미확인 | 미확인 | OPEN-SOURCE (목록) | 미확인 | EMA 리본 + 기울기/가속도 확인 (목록) | ATR 스톱 (목록) | 고정 R배수 (목록) | 링크만 |
| T15 | Chandelier Exit Strategy | 미확인 | https://vn.tradingview.com/script/yca6gmSk-Chandelier-Exit-Strategy | 미확인 | 미확인 | OPEN-SOURCE (목록) | strategy (목록) | 롱/숏 설정 (목록, 구체 규칙 미확인) | Chandelier 트레일 (목록) | TP 비율 설정 (목록) | 링크만 |
| T16 | Larry Williams Donchian Breakout Strategy | 미확인 | https://www.tradingview.com/script/72LSDcg6-Larry-Williams-Donchian-Breakout-Strategy | 미확인 | 미확인 | OPEN-SOURCE (목록) | strategy (목록) | 돈치안 돌파 (목록) | 돈치안 중간선 기준 + 오프셋 (ATR 아님, 목록) | 롱/숏 별도 RR (목록) | 링크만 |
| T17 | Volume Spike & RSI Scalping (Session Restricted) | 미확인 | https://in.tradingview.com/script/57HJx9Nl-Volume-Spike-RSI-Scalping-Session-Restricted | 미확인 | 미확인 | OPEN-SOURCE (목록) | strategy v6 (목록) | 거래량 급증 + RSI + 캔들 방향 (목록) | low − ATR (목록, 코드 일부 인용) | close + (close − SL) × RR (목록, 코드 일부 인용) | 링크만 |
| T18 | Institutional VWAP Bands [JOAT] | JOAT (표기) | https://www.tradingview.com/script/HBa1RdfD-Institutional-VWAP-Bands-JOAT/ | 미확인 | 미확인 | OPEN-SOURCE (목록) | indicator (목록) | VWAP 밴드 신호 (목록) | ATR 스톱, 빨간 리스크 박스 (목록) | 3단계 R배수 목표, 초록 리워드 박스 (목록) | 링크만 |
| T19 | Squeeze Breakout Pro [WillyAlgoTrader] | WillyAlgoTrader (표기) | https://id.tradingview.com/script/9bwEi6EK-squeeze-breakout-pro-willyalgotrader/ | 미확인 | 미확인 | OPEN-SOURCE (목록) | 미확인 | 스퀴즈 후 돌파 (목록) | 범위 저점 아래 / 고점 위 (목록) | 레인지 폭 배수 3단계 (목록) | 링크만 |
| T20 | Anchored Chandelier Exit (indicator) | 미확인 | https://in.tradingview.com/script/h8tRixQX-Anchored-Chandelier-Exit | 미확인 | 미확인 | OPEN-SOURCE (목록) | indicator (목록) | 해당 없음 (스톱 지표) | 최고가 − ATR×3 (기본 배수, 목록) | 해당 없음 | 링크만 |
| T21 | SuperTrend Multi Time Frame Long and Short Trading Strategy | 미확인 | https://in.tradingview.com/script/nXIb4hOt-SuperTrend-Multi-Time-Frame-Long-and-Short-Trading-Strategy | 미확인 | 미확인 | OPEN-SOURCE (목록) | strategy (목록) | 다중 TF SuperTrend 방향 (목록) | 퍼센트 기반 (ATR 아님, 목록) | TP + 트레일 (목록) | 링크만 |

> 제외: `Supertrend Strategy With Multi-TP/TSL` (PROTECTED SOURCE), `ORB Fusion Adaptive` (INVITE-ONLY). 열지 않음.

### TradingView 항목 짧은 메모

- **T1 SuperTrade**: 페이지에 0.1% 수수료, 1틱 슬리피지, 계정 $10,000, 리스크 2%가 적혀 있으나 **백테스트 결과는 없음**. 가장 규칙이 명확하지만 성과 근거 없음.
- **T2 / T3 ORB**: 레인지 정의와 손절 위치는 명확. 기간, 심볼, 수수료 기재 없음. 성과 근거 없음.
- **T5 BB + Squeeze**: 진입 조건이 두 개의 오실레이터 교차로 이루어져 복잡. 재현 시 지표 정의 확인 필요.
- **T6 Casper ORB**: 규칙이 가장 세밀함(리테스트 심지 깊이 범위, 컷오프 시각, 부분익절 후 SL 이동). 옵션 필터(ATR 레인지, ADX 25, 4H VWAP 편향)도 있음. 성과 없음, 페이지에는 "forward-test 권장".
- **T7 NeuraEdge**: 손절 3종 선택과 RR 공식이 명확. 실시간 승률 대시보드만 있고 과거 백테스트는 없음. 지표라서 strategy 백테스트를 하려면 재작성 필요.
- **T11 VWAP Reclaim**: 재탈환 → 리테스트 → 돌파의 3단계 진입 규칙이 명확. 작성자가 "forward-test 30–50 신호 후 사이즈 증액" 권고.
- **T9 Donchian**: 익절 규칙 없음. 트레일링 스톱만. 작성자 주장("결과가 더 좋아 보임")은 수치 없음.
- **T10 3 EMA Pullback**: 규칙이 공개되어 있지 않아 정보 가치 낮음.

---

## 2. 요약 표 B: GitHub 레포 (코드 확인)

| # | 레포 / 파일 | 라이선스 | 별 | 최종 push | 타입 | 진입 | SL | TP | 저장 |
|---|---|---|---|---|---|---|---|---|---|
| G1 | everget/tradingview-pinescript-indicators: `trailing_stops/supertrend.pine` | GPL-3.0 | 965 | 2026-10-19 | indicator (v6) | ATR(22)×3 SuperTrend 방향 전환 (wicks 옵션) | SuperTrend 라인 (트레일) | 없음 (지표) | 저장 (GPL, 학습용) |
| G2 | everget/... : `trailing_stops/chandelier_exit.pine` | GPL-3.0 | 965 | 2026-10-19 | indicator (v6) | 미확인 (본문 미열람, 헤더만 확인) | 미확인 (본문 미열람) | 없음 | 저장 (GPL, 학습용) |
| G3 | freqtrade/freqtrade-strategies: `user_data/strategies/Supertrend.py` | GPL-3.0 | 5,653 | 2026-09-08 | freqtrade (Python) | 3개 SuperTrend 그룹 모두 'up' (하이퍼옵트 파라미터), 1h | 고정 −26.5% + 트레일 (+5%, 오프셋 14.4%) | ROI 테이블 (0.087→0.058→0.029→0) | 저장 (GPL, 학습용) |
| G4 | freqtrade-strategies: `user_data/strategies/futures/FSupertrendStrategy.py` | GPL-3.0 | 5,653 | 2026-09-08 | freqtrade (Python) | G3와 같은 계열 | −26.5% + 트레일 (오프셋 10%) | ROI 테이블 (0.1→0.75→0.05→0.025) | 저장 (GPL, 학습용) |
| G5 | nateemma/strategies: `SimpleStrategies/DCBreakout.py` | GPL-3.0 | 442 | 2026-10-27 | freqtrade (Python) | 종가가 N봉 최고가 상향 돌파 (N = 6–96, 기본 24) | 상위 클래스 SimpleStrategy에 위임 (파일 미포함) | 종가가 하단 돌파 시 청산 (신호 기반) | 저장 (GPL, 학습용) |
| G6 | nateemma/strategies: `NNNC/_atr14_take_profit.py` | GPL-3.0 | 442 | 2026-10-27 | freqtrade mixin | 해당 없음 (익절 리졸버) | 해당 없음 | TP = k × ATR(14)/종가 (신호 봉 기준, 클램프 없음) | 링크만 (내부 Framework 의존) |
| G7 | LePotoRico2105/pine-script-strategies: `strategies/bollinger_squeeze.pine` | MIT | 4 | 2026-04-03 | strategy (v5) | 스퀴즈 (BB 폭 < 평균 × 0.75) 후 20봉 내 BB 상/하단 돌파 (close[1] 기준) | BB 중간선 (SMA20) | 진입가 ± 거리 × 2 | 저장 (MIT) |
| G8 | yawningmonsoon/cubicle-sdk: `examples/strategies/opening-range-breakout.pine` | MIT | 1 | 2026-11-07 | strategy (v5) | 09:30–09:45 레인지 밖 종가 돌파 (세션 밖) | 레인지 반대편 | hi + (hi − lo) (레인지 폭 1배 투사) | 저장 (MIT) |
| G9 | F0rger123/ultimate-claude-trading-skill: `pine/mnq_opening_range_915_930.pine` | MIT | 1 | 2026-11-13 | strategy (v6) | 09:15 15분봉 레인지, 이후 완료된 15분봉 종가가 레인지 밖 → 다음 봉 시가 체결 | 돌파 봉의 반대쪽 극단 (롱: 저점) | 체결가 ± targetR(0.5/0.75/1.0) × 실제 리스크 | 저장 (MIT) |
| G10 | trugurpala/pinescriptv6: `global-markets/15_es_opening_range.pine` | MIT | 4 | 2026-11-01 | strategy (v6) | 첫 30분 고저 돌파 (종가 crossover/crossunder), RTH | 진입가 ∓ 1.5 × ATR(14) | RR 2.0 (기본) | 저장 (MIT) |
| G11 | dcaoyuan/vibetrader: `public/indicators/supertrend.pine` | Apache-2.0 | 55 | 2026-04-21 | indicator (title "Supertrend Strategy") | ta.supertrend(3, 10) 방향 + EMA200 표시 | 없음 | 없음 | 저장 (Apache) |
| G12 | mihakralj/pinescript: `indicators/oscillators/squeeze.pine` | MIT | 49 | 2026-03-01 | indicator (v6) | BB가 KC 안으로 들어가면 스퀴즈 ON, 해제 시 돌파 가능성 | 없음 | 없음 | 저장 (MIT) |
| G13 | mihakralj/pinescript: `indicators/channels/atrbands.pine` | MIT | 49 | 2026-03-01 | indicator (v6) | 해당 없음 | ATR 밴드 기준 스톱 값 제공 | ATR 밴드 기준 목표 값 제공 | 저장 (MIT) |
| G14 | ArunKBhaskar/PineScript: `Trend Following Setup - Sideways Market Skipper` | MPL-2.0 | 602 | 2025-03-30 | indicator (v5) | Supertrend(ATR10, factor 3) 방향 전환, 변동성 레인지 필터로 횡보장 스킵 (부분 확인) | 레인지 기반 (ATR14 × 1.5 또는 고정 포인트, 부분 확인) | 미확인 (부분 확인) | 저장 (MPL-2.0) |
| G15 | ArunKBhaskar/PineScript: `Momentum Setup - RSI Directional Momentum` | MPL-2.0 | 602 | 2025-03-30 | indicator (v6) | RSI 60/40 기준 연속 돌파, 피보 리트레이스, 플립, 다이버전스 스캐너 (부분 확인) | 미확인 | 미확인 | 저장 (MPL-2.0) |

### GitHub 항목 짧은 메모

- **G1 (everget SuperTrend)**: 원문을 전부 읽음. GPL-3.0이므로 학습용. 전략이 아니므로 TP 규칙 없음. **G2 (chandelier)**: 헤더만 확인했고 본문은 읽지 않음. 재구현 전에 열어야 함.
- **G3 / G4 (freqtrade)**: 하이퍼옵트 파라미터가 파일에 박혀 있음. 파일 docstring에 "검증되지 않음, 논문 결과와 불일치 가능"이라고 명시. 손절이 −26.5%로 ATR 기반이 아님. 성과 수치는 없음.
- **G5 (DCBreakout)**: 돌파 진입과 하단 돌파 청산만 있음. SL/TP 수치는 상위 클래스에 있어 파일만으로는 확인 불가.
- **G7 (LePotoRico)**: README 성격의 헤더에 "Backtrex로 10년 M1 데이터 테스트" 주장. 수수료, 기간, 심볼 세부 정보 없음 → **미검증**. 코드가 짧아 재현은 쉬움.
- **G8 (cubicle)**: 작성자가 "읽기용 예제, 추천 아님"으로 명시. 규칙은 명확.
- **G9 (MNQ ORB)**: 코드 헤더에 "RESEARCH HYPOTHESIS, paper only", "TradingView에서 아직 컴파일/실행 안 됨"이라고 명시. 수수료 $0.62/계약, 슬리피지 1틱을 포함. 0.5R 목표에서 손익분기 승률 66.7% (비용 전)이라고 기재. Python 패리티 파일(`research/mnq_opening_range.py`)이 같은 저장소에 있다고 적혀 있으나 이번에 열지 않음.
- **G10 (ES ORB)**: 수수료 $4/계약, 슬리피지 1틱 설정. 백테스트 수치 주장은 없음. 규칙이 코드로 명확함.
- **G12 / G13 (mihakralj)**: 지표 구현. 스퀴즈 판정식과 ATR 밴드 공식이 명확해 SL/TP 계산의 기초로 사용 가능.
- **G14 / G15 (ArunKBhaskar)**: 파일 일부만 읽음. MPL-2.0 헤더 확인. 자세한 SL/TP 규칙은 파일 내 나머지 부분을 읽어야 확정 가능.

---

## 3. 요약 표 C: 링크만 (저장하지 않음)

| # | 레포 / 항목 | 라이선스 | 별 | 최종 push | 내용 | 저장 불가 이유 / 메모 |
|---|---|---|---|---|---|---|
| L1 | Alorse/pinescript-strategies (https://github.com/Alorse/pinescript-strategies) | 없음 (NONE) | 360 | 2026-08-25 | Supertrend 계열 (`Supertrend + EMA rebound`, `Supertrend + RSI`, `Double Supertrend`), TTM Squeeze EMA 등 | 라이선스 없음. 대신 **백테스트 공개** (`BACKTEST.md`, PineTS, BTCUSDT 1D, 2022–24 / 2025–26 두 구간). 대부분 Sharpe 음수. 예: Supertrend + EMA rebound: 2025–26 Sharpe −0.227, Net −4.75%, MaxDD 7.06%. 수수료 명시 없음. 부정적 근거로 가치 있음 |
| L2 | AlbertoCuadra/algo_trading_weighted_strategy (https://github.com/AlbertoCuadra/algo_trading_weighted_strategy) | CC BY-NC-SA 4.0 | 324 | 2022-11-04 | 가중 전략 (`weighted_strategy.pine`) | 비상업 조건 (NC), 저장 제외 |
| L3 | trustdan/trend-following-backtesting-strategies (https://github.com/trustdan/trend-following-backtesting-strategies) | 없음 (NONE) | 17 | 2025-11-04 | SPY 기반 40개 Pine 전략 (파일명에 PF 표기), README에 "293 backtests / 21종목" 주장. Alt10 = 3N–6N–9N 익절, Alt26 = fractional pyramid | 라이선스 없음. PF(예: alt10 1.232, alt26 1.388)는 파일명 표기이며 **OOS/수수료 여부 미기재, 미검증**. 샘플 기간은 SPY 중심 |
| L4 | hasnocool/tradingview-pine-scripts (https://github.com/hasnocool/tradingview-pine-scripts) | GPL-3.0 (레포 기준) | 107 | 2024-09-18 | 대규모 혼합 모음. Donchian (`Donchian Channel Strategy`, `Donchian Trend V1`), ORB (`Pro Trading Art Open Range Breakout Strategy`, `Open Drive`), Squeeze (`BB Keltner Squeeze Strategy`, `Squeeze Momentum Strategy [LazyBear] Buy Sell TP SL Alerts`), VWAP (`VWAP Trendfollow Strategy [wbburgin]`) | 개별 스크립트의 원저작자 라이선스가 다를 수 있어 파일 단위 저장 안 함 |
| L5 | TradersPost/pinescript-agents (`templates/strategies/breakout.pine`, `momentum.pine`) (https://github.com/TradersPost/pinescript-agents) | 없음 (NONE) | 241 | 2026-07-23 | Claude Code용 Pine 툴셋. breakout/momentum 템플릿 | 라이선스 없음 |
| L6 | judder659/Forven `docs/pine/simple_donchian_breakout_demo.pine` (https://github.com/judder659/Forven) | AGPL-3.0 | 364 | 2026-11-11 | Donchian 돌파 데모 | AGPL, 저장 제외 |
| L7 | geraked/tradingview `strategies/*.pine` (https://github.com/geraked/tradingview) | MIT | 105 | 2023-10-29 | 3MAF, ABSAR, BBRSI, CEZLSMA, CP1, DHLAOS, LRCUTB, MLCEL_MACD, NWERSIASF | **미검토**. MIT이므로 후속 검토 시 저장 후보 |
| L8 | raybird/pine-trading-strategies (`strategies/tn_opening_range_magnet_v6.pine`) | 없음 | 1 | 2026-08-15 | ORB + 레인지 마그넷 (파일명 기준) | 라이선스 없음, 미검토 |
| L9 | saeed1004/tradingview-opening-range-breakout (`OpeningRangeBreakout.pine`) | 없음 | 0 | 2026-10-31 | ORB | 라이선스 없음, 미검토 |
| L10 | MorSof/tradingview-pine-scripts (`Strategies/5m_opening_range.pine`) | 없음 | 0 | 2025-07-12 | 5분 ORB | 라이선스 없음, 미검토 |
| L11 | Zettt/pinescripts (`Super SuperTrend.pine`, `Modified Donchian.pine`, `Peak Reversal.pine`) | 없음 | 43 | 2025-09-23 | Supertrend / Donchian 변형 | 라이선스 없음 |
| L12 | capissimo/Pinescript-Laboratory (`scripts/013-Squeeze-Momentum-Indicator-(v3).pine`, `014-Momentum-Strategy-(v2).pine`) | 없음 | 114 | 2024-11-08 | 스퀴즈 지표, 모멘텀 전략 | 라이선스 없음 |
| L13 | freqtrade/freqtrade-strategies 외 werkkrew/freqtrade-strategies `archived/Supertrend.py` | 없음 | 324 | 2021-06-04 | Supertrend 보관본 | 라이선스 없음, 2021 이후 미갱신 |
| L14 | mementum/backtrader (https://github.com/mementum/backtrader) | GPL-3.0 | 23,737 | 2024-08-19 | Python 백테스트 프레임워크. bracket 주문(진입+SL+TP) 지원, ATR 지표 (`backtrader/indicators/atr.py`) | 프레임워크. 전략 자체는 아님 |
| L15 | kernc/backtesting.py (https://github.com/kernc/backtesting.py) | AGPL-3.0 | 9,236 | 2026-08-05 | Python 백테스트 라이브러리 (SL/TP, 트레일 주문 지원) | AGPL, 링크만 |
| L16 | LuxAlgo/PineTS (https://github.com/LuxAlgo/PineTS) | AGPL-3.0 | 951 | 2026-11-13 | Pine v5/v6 런타임을 JS/TS로 구현. Alorse 백테스트에 사용됨 | AGPL, 링크만 (포트 참고용) |
| L17 | QuantConnect/Lean (https://github.com/QuantConnect/Lean) | Apache-2.0 | 22,521 | 2026-11-14 | 대형 엔진 (ATR 스톱, 알고리즘 프레임워크) | 전략 파일이 아니라 엔진. 필요 시 참고 |
| L18 | freqtrade/freqtrade (https://github.com/freqtrade/freqtrade) | GPL-3.0 | - | - | custom stoploss, trailing, ROI 등 SL/TP API | 엔진 참고용 |
| L19 | pAulseperformance/awesome-pinescript (https://github.com/pAulseperformance/awesome-pinescript) | MIT | 1,960 | 2026-02-28 | Pine 자료 모음 (목록) | 목록 자체 |

---

## 4. 성과 주장 정리 (credibility 메모)

| 항목 | 주장 | 검증 상태 |
|---|---|---|
| L1 Alorse BACKTEST.md | 여러 전략 백테스트 (PineTS, BTCUSDT 1D, 두 구간) | 부분 검증 가능 (구간 분리, 수수료 미기재). 대부분 음수 |
| L3 trustdan README / 파일명 PF | 293 백테스트, SPY 기준 PF 1.232–1.474 등 | **미검증**. 수수료/OOS 미기재 |
| G7 LePotoRico 헤더 | Backtrex 10년 M1 테스트 | **미검증**. 수수료 미기재 |
| G9 F0rger123 헤더 | 0.5R 손익분기 승률 66.7% (비용 전) | 계산식 수준. 실측 아님, 실행 전 상태 명시 |
| T1 SuperTrade 페이지 | 수수료 0.1%, 1틱 슬리피지 설정 | 설정 값만 있음. 결과 없음 |
| T11 VWAP Reclaim 가이드 | 30–50 신호 선행 포워드 테스트 권고 | 권고만 있음 |
| T12 EMA 12/21 (목록) | 승률 50%, PF 1.5 | 작성자 주장, 페이지 조회 실패. **미검증** |
| G3 / G4 freqtrade | 파일 docstring: 검증 안 됨 | 작성자 자기 평가 |

---

## 5. 재구현 우선순위 메모 (규칙 명확도 기준, 상위 5개는 맨 끝)

- 명확한 "진입 / SL / TP" 규칙이 코드로 있는 것을 우선.
- 라이선스가 있어 원문을 로컬에서 바로 열 수 있는 것을 우선.
- 수수료와 슬리피지 설정이 같이 있는 것을 가산.

---

## 6. 백테스트용 재구현 TOP 5 (규칙 수준)

1. **G9 F0rger123 MNQ ORB 9:15–9:30 (MIT, `pine_refs/trend/F0rger123-ultimate-claude-trading-skill/mnq_opening_range_915_930.pine`)**: 09:15 15분봉 고저를 레인지로 잡고, 이후 완료된 15분봉 종가가 레인지를 벗어나면 다음 봉 시가에 진입한다. 손절은 돌파 봉의 반대쪽 극단이고, 목표는 실제 체결가 기준 0.5~1.0R이며, 15:45 청산과 세션당 1회 진입을 두고 수수료(계약당 $0.62)와 1틱 슬리피지를 함께 반영한다.

2. **G10 trugurpala ES ORB (MIT, `pine_refs/trend/trugurpala-pinescriptv6/15_es_opening_range.pine`)**: 첫 30분 고저를 레인지로 잡고 종가가 레인지 고점을 상향 돌파(또는 저점 하향 돌파)하면 진입한다. 손절은 진입가에서 1.5×ATR(14) 떨어진 곳이고 목표는 RR 2.0이며, RTH 종료 시 전량 청산한다.

3. **G7 LePotoRico Bollinger Squeeze Breakout (MIT, `pine_refs/trend/LePotoRico2105-pine-script-strategies/bollinger_squeeze.pine`)**: BB 폭이 평균의 0.75배 아래로 떨어진 스퀴즈가 최근 5봉 안에 있었고 종가가 BB 상단(롱) 또는 하단(숏)을 넘어서면 진입한다. 손절은 SMA20 중간선, 목표는 진입가와 중간선 사이 거리의 2배이며, 백테스트 주장은 미검증이다.

4. **G1 everget SuperTrend (GPL-3.0 학습용, `pine_refs/trend/everget-tradingview-pinescript-indicators/supertrend.pine`)**: ATR(22)×3 기반 SuperTrend의 방향이 음에서 양으로 바뀌면 롱 진입, 반대 방향이면 숏 진입으로 본다. 손절(트레일)은 SuperTrend 라인이며 원본에는 익절이 없으므로 우리 규칙에서 ATR 배수 또는 RR로 익절을 따로 정의해야 한다.

5. **G8 cubicle-sdk Opening Range Breakout (MIT, `pine_refs/trend/yawningmonsoon-cubicle-sdk/opening-range-breakout.pine`)**: 09:30–09:45 레인지 밖에서 종가가 돌파하면 진입하고, 손절은 레인지 반대편이다. 목표는 레인지 폭만큼 투사한 지점(hi + (hi − lo))이며, 작성자가 "읽기용 예제, 추천 아님"이라고 명시했으므로 규칙만 참고한다.

---

## 7. 참고 사항

- 요청한 "25개 이상" 수집: TradingView 21개 (표 A), GitHub 15개 (표 B), 링크만 19개 (표 C). 합 55개.
- 저장한 파일 14개 (라이선스 원문 포함, 폴더마다 `LICENSE.txt`): `pine_refs/trend/` 하위 10개 폴더.
- 아직 확인되지 않은 항목: TradingView 페이지 대부분의 원문 코드, G14/G15 파일의 나머지 SL/TP 규칙, L7 geraked 전략 전체.
- 다음 단계 제안: L7(MIT) 전략 원문을 열어 추가 저장 후보로 검토, 그리고 G14 파일 나머지 부분에서 SL/TP 규칙 확정.
