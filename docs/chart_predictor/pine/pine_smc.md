# TradingView Pine Script / 포트 수집: SMC·ICT 진입·SL·TP 로직

- 작성일: 2026-11-14
- 범위: 자동으로 진입가를 정하고 SL/TP 박스·라인을 그리는 스크립트 (OB, FVG, 유동성 스윕, BOS/CHoCH, 프리미엄/디스카운트, 킬존)
- 저장 위치: `/Users/user/CODE/Coin_Trade/chart_predictor/data/pine_refs/smc/` (라이선스 허용 14개 파일 + LICENSE 본문)

## 수집 방법과 한계

- **GitHub 저장소 검색**: `gh search repos`로 SMC/ICT/pinescript/freqtrade 관련 저장소를 검색했다. 주제 검색과 여러 키워드 검색 결과를 합쳐 약 60개 저장소의 별점, 최종 push, 라이선스를 확인했다.
- **GitHub 코드 검색**: `language:pine`은 422 오류가 나서 `extension:pine` 한정자로 바꿨다. `order block extension:pine`로 30개 결과를 얻었지만, `strategy.exit`·`liquidity sweep` 등 전략 특화 질의는 보조 rate limit에 걸려 완료하지 못했다. 따라서 Pine `strategy()` 계열 커버리지는 불완전하다.
- **freqtrade**: `freqtrade` 키워드 저장소 검색(fair value gap, order block, smart money, liquidity sweep)은 결과가 0건이었다. freqtrade 쪽 SMC 전략은 찾지 못했다.
- **TradingView**: 웹검색으로 후보 URL을 얻은 뒤 공개 스크립트 페이지 6개를 한 페이지씩 읽었다(로그인·비공개·유료 스크립트 미접근). 대량 수집은 하지 않았다. 좋아요·조회 수는 라벨 없이 두 숫자만 표시되는 경우가 많아 대부분 "미확인"으로 표기했다.
- **코드 확인 수준**: TradingView 페이지는 소스가 접혀 있어 설명문 기준이다. GitHub 파일은 실제 코드를 읽었다(단, 표시한 부분만).
- **라이선스 주의**: `qe_fvg`(Ahmed-GoCode) 헤더는 "Inversion Fair Value Gaps [TradingFinder]" 제목을 쓴다. 저장소는 MPL-2.0이지만 원작자가 TradingFinder일 가능성이 있다. 재배포 전 원작자 확인이 필요하다.

---

## 1. TradingView 공개 스크립트 (페이지 직접 확인)

| # | 이름 (Name) | 작성자 | 종류 | 라이선스 표기 | 좋아요/조회 | 최종 게시 | 진입 | SL | TP | 시장/TF | 성과 주장 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| T1 | [Professional SMC & OB Strategy](https://www.tradingview.com/script/lLuNTkn5-Professional-SMC-OB-Strategy/) | X_MiraNI_313 | 제목 Strategy, 설명은 "Indicator" (코드 미확인) | OPEN-SOURCE 표시, 본문 없음 | 미확인 (392 / 1,175) | "Jun 26" (연도 없음) | 4H FVG 진입 후 OB 신호(파란 다이아몬드) | OB 구조 고/저 또는 FVG 외곽 바로 너머 | 다음 반대편 유동성 스윕 또는 최소 2R | 4H FVG, 200/50 EMA 필터, 시장 미지정 | 정량 없음 ("consistent results" 등 정성 표현) |
| T2 | [Smart Money Concepts Pro – OB, FVG, Liquidity + Trade Setups](https://www.tradingview.com/script/bYblTTqo/) | Kammi07 | indicator (설명 기준) | OPEN-SOURCE 표시, 본문 없음 | 미확인 (1.6K / 1) | Oct 20, 2025 | OB 리테스트 + 추세 필터 | 반대편 OB 경계 | 기본 2R (R:R 설정) | 코인/FX/지수/주식, 스캘프·인트라데이·스윙 프리셋 | 정량 없음 |
| T3 | [SMC Analytics Pro](https://www.tradingview.com/script/ev3ivqZm-SMC-Analytics-Pro/) | sunya | indicator, Pine v5 | OPEN-SOURCE 표시, 본문 없음 | 미확인 (3952 / 6198) | Aug 11 (연도 없음) | 재시험 시 미완화 Bullish OB 복귀 후 저TF iBOS/CHoCH 확인 (재량) | 명시 없음 | 명시 없음 | 멀티 TF·멀티 마켓 | 정량 없음; 차트 "100% accurate" 표현 |
| T4 | [Smart Money Concept [martineye15]](https://www.tradingview.com/script/4U8Xgv0C-Smart-Money-Concept-martineye15/) | martineye15 | indicator ("주문 없음" 명시) | OPEN-SOURCE 표시 | 201 추정 (6193 조회 추정) | Jul 6 (연도 없음) | 신호 봉 종가 시장가 또는 OB 중간 지정가 | OB/스윙/ATR 기반 + ATR 버퍼 | TP1~TP4, 사용자 지정 R 배수 | 옵션 트레이드 셋업 | 없음, 비금융 자문 고지 |
| T5 | [Smart Money Tracker [JOAT]](https://www.tradingview.com/script/RIFflvzg-Smart-Money-Tracker-JOAT/) | officialjackofalltrades | indicator (선언 미확인) | OPEN-SOURCE 표시 | 205 / 5997 (라벨 없음) | Feb 18 (연도 없음) | OB 복귀 대기 (규칙 명시 약함) | 명시 없음 | FVG를 목표·이익실현 구역으로 사용 | 미지정 | 저자 소개 "highest win rate" (근거 없음) |
| T6 | [SMC Pro: Strategy & Liquidity](https://www.tradingview.com/script/6iAh8TWT-SMC-Pro-Strategy-Liquidity/) | MntDude65 | indicator ("주문 미생성") | OPEN-SOURCE 표시 | 미확인 (5122 / 7424) | Aug 19 (연도 없음) | 없음 (재량, 확인 이벤트 표시만) | 없음 | 없음 | 미지정 | 없음; 면책 고지 |

확인 못 한 검색 결과 (페이지 미확인): "Order Block Volumatic FVG Strategy" (BigBeluga 계열 FVG를 전략화했다는 검색 설명), "ICT KillZones Hunt [TradingFinder]" (4세션 킬존 + OB + FVG 알림).

## 2. GitHub Pine 스크립트 (파일 확인)

| # | 저장소 (Repo) | 작성자 | 종류 | 라이선스 | 별점 | 최종 push | 파일 | 진입 / SL / TP | 저장 여부 |
|---|---|---|---|---|---|---|---|---|---|
| G1 | [TradingSignalBot/tradingview-strategies](https://github.com/TradingSignalBot/tradingview-strategies) | TradingSignalBot | indicator, Pine v6 (alert JSON 포함) | MIT | 25 | 2026-11-03 | `indicators/liquidity-sweep.pine` | 전일 고/저 스윕 후 종가 복귀 / 스윕 극단 ± 0.1×ATR(14) / 1R·2R·3R | **저장** |
| G2 | [quantumalgo-official/smart-money-concepts-indicator](https://github.com/quantumalgo-official/smart-money-concepts-indicator) | Quant Algo | indicator, Pine v6 | MIT | 23 | 2026-10-06 | `smart-money-concepts.pine` | 없음 (SMC 감지 엔진: OB, FVG, 스윕, BOS/CHoCH) | **저장** |
| G3 | [VolodymyrFilias/feels-indicators](https://github.com/VolodymyrFilias/feels-indicators) | FEELS | indicator, Pine v6 | MIT | 15 | 2026-06-11 | `liquidity-magnet.pine`, `power-of-three.pine` | 없음 (유동성 목표 확률 존, PO3) | **저장** |
| G4 | [Ahmed-GoCode/Quant-Edge-Indicators](https://github.com/Ahmed-GoCode/Quant-Edge-Indicators) | Ahmed (Quant-Edge) | indicator | MPL-2.0 | 57 | 2026-08-17 | `Smart Money & Liquidity/MSS + CHoCH + BOS.pinescript`, `FVG.pinescript`, `Trio Liquidity.pinescript` | 없음 (구조·스윕 신호). 헤더에 TradingFinder 명시 (원작자 확인 필요) | **저장** (3개) |
| G5 | [samuelharting/bandz-po3-stdv-cisd](https://github.com/samuelharting/bandz-po3-stdv-cisd) | samuelharting (© Bandz-ICT) | indicator, 2,238행 | MPL-2.0 | 6 | 2026-10-06 | `Bandz-STDV-Flow.pine` | 프로젝션 목표 (STDV −2.0, −3.5 배수 터치 여부 추적), CISD 확인 | **저장** |
| G6 | [rockon8765/smc-trading-strategy](https://github.com/rockon8765/smc-trading-strategy) | rockon8765 | 백테스트 (Python, 암호화폐) | MIT | 1 | 2025-11-20 | `strategy.py`, `smc_indicators.py` | 아래 상세 | **저장** |
| G7 | [fredlines/Backtest-project](https://github.com/fredlines/Backtest-project) | fredlines | 백테스트 (Python, US30/NAS) | MIT | 0 | 2026-10-08 | `strategies/fvg_cascade.py`, `fvg_detector.py` | 아래 상세 | **저장** |
| G8 | [joshyattridge/smart-money-concepts](https://github.com/joshyattridge/smart-money-concepts) | Josh Attridge | 라이브러리 (Python, indicators) | MIT | 2,222 | 2026-04-03 | `smartmoneyconcepts/smc.py` | 없음 (FVG, swing, OB, BOS/CHoCH, 유동성, 프리/디스카운트 계산) | **저장** |
| G9 | [KVignesh122/MT5-SMC-trading-bot](https://github.com/KVignesh122/MT5-SMC-trading-bot) | KVignesh122 | EA (MQL5) | Apache-2.0 | 95 | 2026-07-15 | `EA_Script.mq5` | 아래 상세 (SL/TP 확인, 진입 세부 미확인) | **저장** |
| G10 | [rabichawila/smart-money-py](https://github.com/rabichawila/smart-money-py) | rabichawila | 지표 (Python) | GPL-3.0 | 18 | 2024-01-07 | `smart_money.py` | 확인 안 함 (SL/TP 키워드 29건) | 링크만 (GPL, 파일 미저장) |
| G11 | [ivala2081/Helix](https://github.com/ivala2081/Helix) | ivala2081 | BTC FVG 백테스트 (Python) | MIT | 8 | 2026-11-05 | `backtester.py` 외 | 확인 안 함 (SL/TP 키워드 많음, 시간 부족) | 링크만 |
| G12 | [foeed/FvgGold-EA](https://github.com/foeed/FvgGold-EA) | foeed | EA (MQL5, XAUUSD FVG) | MIT | 54 | 2026-09-17 | `FvgGold.mq5` (952행) | 확인 안 함 (SL/TP 키워드 53건) | 링크만 |
| G13 | [yanstd888/institutional-smc-scalper-mt5](https://github.com/yanstd888/institutional-smc-scalper-mt5) | yanstd888 | EA (MQL5, XAUUSD 스캘프) | MIT | 38 | 2026-10-25 | 테스트/도구 중심 | 확인 안 함 | 링크만 |
| G14 | [carlosrod723/MQL5-Trading-Bot](https://github.com/carlosrod723/MQL5-Trading-Bot) | carlosrod723 | EA (MQL5) + ML | MIT | 83 | 2025-11-19 | `MyTradingBot.mq5` (1,104행), `OrderBlock.mq5` | 확인 안 함 (SL/TP 키워드 142건) | 링크만 |
| G15 | [SiyabongaDlamini/SmartMoney.MQ5](https://github.com/SiyabongaDlamini/SmartMoney.MQ5) | SiyabongaDlamini | EA (MQL5, MTF SMC) | Apache-2.0 | 16 | 2026-05-11 | `SmartMoney_MTF_EA_v2.mq5` | 확인 안 함 (SL/TP 키워드 213건) | 링크만 (미저장) |
| G16 | [rpanchyk/mt5-liquidity-sweep-ind](https://github.com/rpanchyk/mt5-liquidity-sweep-ind) | rpanchyk | 지표 (MQL5) | MIT | 17 | 2024-10-25 | `LiquiditySweep.mq5` | 확인 안 함 | 링크만 |
| G17 | [Velmolk/Smart-Money-Concepts-indicator-MT5](https://github.com/Velmolk/Smart-Money-Concepts-indicator-MT5) | Velmolk | 지표 (C#) | MIT | 11 | 2026-04-08 | — | 없음 (유동성, OB, BOS) | 링크만 |
| G18 | [GeneralTradingSarl/Smart-Money-Concepts](https://github.com/GeneralTradingSarl/Smart-Money-Concepts) | GeneralTradingSarl | 지표 (MQL5, LuxAlgo SMC 포트) | 기타 (Other) | 33 | 2026-11-14 | — | 없음 (작성자 주장: TradingView와 동일) | 링크만 (라이선스 불명) |
| G19 | [kxngHADES/SMC-Marking](https://github.com/kxngHADES/SMC-Marking) | kxngHADES | 지표 (Pine v6, 용어 표시) | NOASSERTION (자체 라이선스) | 45 | 2026-11-10 | `SMC_Terminology_marks.pine` | 없음 | 링크만 (자체 라이선스 문구 확인 필요) |
| G20 | [jayadevrana/free-pine-script-indicators](https://github.com/jayadevrana/free-pine-script-indicators) | jayadevrana | 지표/전략 모음 (Pine) | MPL-2.0 | 7 | 2026-10-26 | `scripts/*.pine.txt` | SMC 관련 파일은 확인 안 함 (`complete-system` 지표형) | 링크만 |
| G21 | [ArunKBhaskar/PineScript](https://github.com/ArunKBhaskar/PineScript) | ArunKBhaskar | ICT 지표 모음 (.txt) | MPL-2.0 | 602 | 2025-03-30 | ICT FVG, 유동성, MSS 스캐너 등 | 지표/스캐너 위주 (전략 없음) | 링크만 |
| G22 | [TradersPost/pinescript-agents](https://github.com/TradersPost/pinescript-agents) | TradersPost | 예제 (Pine, 에이전트용) | **라이선스 없음** | 241 | 2026-07-23 | `examples/simple/order-blocks-simple.pine` | 미확인 | 링크만 (라이선스 없음 = 복사 금지) |
| G23 | [LuxAlgo/PineTS](https://github.com/LuxAlgo/PineTS) | LuxAlgo | Pine 실행기 (TypeScript) | AGPL-3.0 | 951 | 2026-11-13 | — | 도구 (Pine을 Node에서 실행) | 링크만 (AGPL 주의) |
| G24 | [PyneSys/pynecore](https://github.com/PyneSys/pynecore) | PyneSys | Pine 호환 Python 런타임 | Apache-2.0 | 265 | 2026-11-13 | — | 도구 (Pine 전략을 Python 백테스트로) | 링크만 |
| G25 | [pAulseperformance/awesome-pinescript](https://github.com/pAulseperformance/awesome-pinescript) | pAulse | 큐레이션 목록 | MIT | 1,960 | 2026-02-28 | — | 목록 | 링크만 |
| G26 | [SrsBlack/ict-knowledge-library](https://github.com/SrsBlack/ict-knowledge-library) | SrsBlack | ICT 지식 베이스 (Python 폴더) | **라이선스 없음** | 82 | 2026-11-09 | — | 지식 자료 (코드 전략 아님) | 링크만 |
| G27 | [everget/tradingview-pinescript-indicators](https://github.com/everget/tradingview-pinescript-indicators) | everget | 일반 지표 모음 | GPL-3.0 | 965 | 2026-10-19 | — | SMC 아님 (참고용) | 링크만 |
| G28 | [geraked/tradingview](https://github.com/geraked/tradingview) | geraked | 전략 백테스트 모음 (`strategy()`) | MIT | 105 | 2023-10-29 | `strategies/*.pine` | SMC 아님. `CP1.pine`은 캔들 패턴 스캘프 전략 (SL/TP 확인) | 링크만 (SMC 아님) |
| G29 | [OpenMobius-skill](https://github.com/MobiusQuant/OpenMobius-skill) | MobiusQuant | ICT/SMC 지식 스킬 (에이전트용) | Apache-2.0 | 726 | 2026-11-12 | — | 지식 자료 | 링크만 |

## 3. 파이썬·MQL5 포트 상세 (코드 확인)

- **rockon8765 `strategy.py`** (MIT): 불리시 OB 신호와 종가 > EMA200 추세 필터, 거래량 > 1.5×평균 조건이 맞으면 OB 상단에 지정가 매수. 손절은 직전 스윙 저점, 조건을 못 맞추면 진입가의 1% 아래. 목표는 `entry + RR×risk` (기본 RR 1.5). 숏은 대칭. OB/EMA 계산은 `smc_indicators.py`에 있다(이번에는 미검증).
- **fredlines `fvg_cascade.py`** (MIT): 4H FVG 존 → 가격 복귀 시 engaged → 같은 방향 15분 FVG가 같은 존과 겹치면 그 FVG 경계에 지정가. 손절은 15분 FVG 첫 캔들의 고/저(`stop_ref`), 목표는 `rr_target`=2.0. 세션 07:00–10:00 GMT, 주문은 10:00에 만료. 존은 48시간 후 또는 종가가 존을 완전히 통과하면 무효화.
- **KVignesh `EA_Script.mq5`** (Apache-2.0): 진입 후 SL은 진입가 ∓1.5×ATR(14), TP는 ±2.5×ATR(14)이다. ATR 필터를 끄면 고정 350/750 포인트 거리. 브로커 최소 STOP 거리에 맞춰 보정. 진입 트리거(displacement 2-of-3 점수 + OB/FVG/BOS)는 이번에 읽은 범위 밖이라 세부 확인 필요. 포지션 크기는 잔고 1,000당 0.02랏, 자산 8% 수익 시 전체 청산.
- **joshyattridge `smc.py`** (MIT): 라이브러리. FVG, 스윙 고/저, OB, BOS/CHoCH, 유동성, 프리미엄/디스카운트 계산 함수. 진입·SL·TP 로직은 없음. 감지 계층으로 쓰기 좋다.

## 4. 참고 메모

- 검색으로 본 SMC 스크립트 대부분은 **indicator** (`indicator()`)이다. 진입·SL·TP를 자동 계산하는 `strategy()`는 드물다. 재구현 후보로 쓸 만한 것은 G1, G6, G7, G9 정도다.
- TradingView 공개 스크립트의 "승률", "고정밀" 같은 문구는 모두 근거가 없다. 성과 수치는 전부 미검증 주장으로 취급한다.
- 라이선스가 없는 저장소(G22, G26)는 코드를 저장하지 않았다.
- 다음 단계 제안: 코드 검색 rate limit이 풀리면 `strategy.exit order block extension:pine`, `fair value gap strategy.entry extension:pine`, `breaker block extension:pine` 질의로 strategy() 계열을 더 찾는다.

## 5. 재구현 후보 TOP 5 (백테스트용 규칙 정리)

1. **TSB Liquidity Sweep (G1, MIT)**: 전일 고/저점을 03:00–12:00 NY 사이 돌파한 15분봉이 나온 뒤 4봉 안에 레벨 안쪽으로 종가 복귀하면, 그 봉 종가에 진입한다(고점 스윕 → 매도, 저점 스윕 → 매수). 손절은 스윕 최극단 가격에서 0.1×ATR(14) 바깥이고, 목표는 손절 거리의 1R·2R·3R이다.

2. **FVG Cascade, fredlines (G7, MIT)**: 4H FVG 존으로 가격이 되돌아와 engaged 상태가 된 뒤, 07:00–10:00 GMT 안에 같은 방향 15분 FVG가 같은 존과 겹치면 그 FVG 경계(롱은 상단, 숏은 하단)에 지정가를 건다. 손절은 해당 15분 FVG 첫 캔들의 고/저이고, 목표는 RR 2.0이며 주문은 10:00에 만료된다.

3. **SMC Strategy, rockon8765 (G6, MIT)**: 불리시 OB 신호가 나오고 종가가 EMA200 위이며 거래량이 평균의 1.5배를 넘으면, OB 상단에 지정가 매수를 건다. 손절은 직전 스윙 저점(없으면 진입가의 1% 아래), 목표는 위험의 1.5배다(숏은 대칭).

4. **MT5 SMC Bot, KVignesh122 (G9, Apache-2.0)**: OB/FVG/BOS 신호와 displacement 필터가 맞으면 진입한다(진입 세부 조건은 추가 확인 필요). 손절은 진입가에서 1.5×ATR(14), 목표는 2.5×ATR(14) 거리다(SL/TP는 코드 확인, 진입은 부분 확인).

5. **Professional SMC & OB Strategy, X_MiraNI_313 (T1, 설명문 기준, 코드 미확인)**: 4H FVG에 진입한 뒤 OB 신호(파란 다이아몬드)가 뜨면 진입한다. 손절은 OB 구조의 고/저 또는 FVG 외곽 바로 너머이고, 목표는 다음 반대편 유동성 스윕이나 최소 2R이다(설명문 기준이라 재구현 전 실제 로직 확인 필요).
