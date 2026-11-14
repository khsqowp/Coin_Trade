# Pine Script / 포트 패턴·피보나치·지지저항 자동 트레이드 플랜 조사

- 조사일: 2026-11-14
- 범위: 패턴(H&S, 더블탑/바텀, 삼각형, 하모닉), 피보나치 골든포켓/익스텐션, 지지저항·추세선 돌파, 캔들 반전, RSI/MACD 다이버전스, 거래량 프로파일, LLM 차트 분석 트레이드 플랜
- 방법: `gh search repos`, `gh search code`(Pine 파일 검색), `gh api repos/...`(메타데이터·라이선스·소스 원문), WebSearch 및 개별 공개 TradingView 스크립트 페이지 WebFetch 몇 건. 로그인, 비공개·보호 스크립트, 접근 우회는 하지 않았다.
- 한계: GitHub 검색 API가 분당 제한에 자주 걸려 Pine 코드 검색은 일부만 수행했다. TradingView 페이지는 소스 코드가 보이지 않는 경우가 많아 규칙은 페이지 설명에서 옮긴 "주장(claimed)" 수준이다. 좋아요·조회수는 라벨 없이 표시되는 경우가 있어 참고용이다.
- 표기: **검증** = 소스 코드를 직접 확인함, **주장** = 페이지/README 설명만 확인함(미검증), **저장** = `chart_predictor/data/pine_refs/pattern/`에 라이선스 파일과 함께 저장함

## 1. 요약 표

| # | 이름 / URL | 작성자 | ★ / 좋아요 | 최종 업데이트 | 라이선스 | 유형 | 진입 | SL | TP | 시장/TF | 주장 성과 | 저장 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | [luckyJeffy/pinescript-harmonic-detector](https://github.com/luckyJeffy/pinescript-harmonic-detector) | luckyJeffy (Jiehui) | ★1 | 2025-04-30 | MIT | indicator (v5) | D점 | D점 ±1% (risk_percent) | TP1 = D±0.382·\|A−D\|, TP2 = D±0.618·\|A−D\| | 범용 / 미명시 | 없음 | 예 |
| 2 | [ggne/harmonic-pattern-pine](https://github.com/ggne/harmonic-pattern-pine) | ggne | ★1 | 2025-09-24 | MIT | indicator (v5) | 없음(D구간 PRZ 박스만) | 없음 | 없음 | 범용 | 없음 | 예 |
| 3 | [djoffrey/HarmonicPatterns](https://github.com/djoffrey/HarmonicPatterns) | Joffrey | ★142 | 2026-06-26 | MIT | Python 라이브러리 | 예측 D점(미완성 패턴) | 코어에서 미확인 | 코어에서 미확인 | 크립토 OHLCV (ccxt 예제) | 없음 | 예 |
| 4 | [sandybradley/HarmonicTrader](https://github.com/sandybradley/HarmonicTrader) | sandybradley | ★10 | 2020-01-20 (오래됨) | MIT | Python | 백테스트 중 (미확인) | 미확인 | 미확인 | Deribit 옵션/선물 | 없음 | 예 |
| 5 | [crypto10kx/harmonic-pattern-detection](https://github.com/crypto10kx/harmonic-pattern-detection) | crypto10kx | ★4 | 2025-09-08 | **NOASSERTION (불명확)** | Python | 패턴 PRZ | `scott_carney_sltp_calculator.py` 등 모듈 존재 | 동일 | 크립토 | README/BACKTEST_RESULTS.md의 수치는 **미검증** | 아니오 (라이선스 불명) |
| 6 | [Blave-TW/blave-agent (stop_loss_take_profit.pine)](https://github.com/Blave-TW/blave-agent/blob/HEAD/examples/exports/pine/stop_loss_take_profit.pine) | Blave-TW | ★346 (레포) | 2026-11-14 (레포) | Apache-2.0 | **strategy** (v6) | SMA 45/100 교차 | 체결가 −2% | 체결가 +4% | 범용 BTC 예 | 없음 | 예 |
| 7 | [qrak/LLM_trader](https://github.com/qrak/LLM_trader) | qrak | ★141 | 2026-11-14 | MIT | Python, LLM | LLM이 OHLCV/차트 기반으로 제시 | LLM 제시 | LLM 제시 | 크립토 | `claims.json` 등 자체 주장 (**미검증**) | 아니오(링크만) |
| 8 | [raghavan/SnapScalp](https://github.com/raghavan/SnapScalp) | raghavan | ★23 | 2025-09-28 | MIT | Electron + LLM | 스크린샷 → LLM | LLM 제시 | LLM 제시 | 인트라데이 | 없음 | 아니오 |
| 9 | [MiteshSharma/tradingai](https://github.com/MiteshSharma/tradingai) | MiteshSharma | ★3 | 2025-02-22 | MIT | FastAPI + GPT-4 | TA+LLM | 기능 목록에 SL 계산 언급 | 미확인 | 미명시 | 없음 | 아니오 |
| 10 | [bluepeter/alphagroove](https://github.com/bluepeter/alphagroove) | bluepeter | ★1 | 2025-10-07 | AGPL-3.0 | TypeScript + LLM | LLM 신호 | LLM 제시 | LLM 제시 | 주식 (Polygon) | 없음 | 아니오 (AGPL) |
| 11 | [BennyThadikaran/stock-pattern](https://github.com/BennyThadikaran/stock-pattern) | BennyThadikaran | ★421 | 2025-12-02 | GPL-3.0 | Python CLI | 패턴 스캔 (H&S, 더블탑, 삼각형 등), 백테스트 모듈 존재 | 확인 필요 | 확인 필요 | 주식 | 없음 | 아니오 (GPL, 로컬 연구만) |
| 12 | [Daz92/stock-pattern](https://github.com/Daz92/stock-pattern) | Daz92 | ★0 | 2024-06-29 | GPL-3.0 | Python | 패턴 스캔 + backtest.py | 확인 필요 | 확인 필요 | 주식 | 없음 | 아니오 |
| 13 | [zeta-zetra/chart_patterns](https://github.com/zeta-zetra/chart_patterns) | zeta-zetra | ★129 | 2024-07-08 | 없음 (명시 안 됨) | Python | H&S/역H&S/삼각형 감지 | 없음 | 없음 | 주식 | 없음 | 아니오 (라이선스 없음) |
| 14 | [keithorange/PatternPy](https://github.com/keithorange/PatternPy) | keithorange | ★481 | 2024-02-27 | NOASSERTION (불명확) | Python | 패턴 감지 (OHLCV DataFrame) | 없음 | 없음 | 주식 | 없음 | 아니오 |
| 15 | [ArunKBhaskar/PineScript](https://github.com/ArunKBhaskar/PineScript) | ArunKBhaskar | ★602 | 2025-03-30 | MPL-2.0 | Pine 모음 (ICT 중심) | 레포 설명 수준 | 확인 필요 | 확인 필요 | 다수 | 없음 | 아니오(링크만) |
| 16 | [FaustoS88/Pydantic-AI-Pinescript-Expert](https://github.com/FaustoS88/Pydantic-AI-Pinescript-Expert) | FaustoS88 | ★70 | 2026-11-04 | MIT | RAG 에이전트 (Pine 생성 보조) | 해당 없음 | - | - | - | - | 아니오 |
| 17 | [pAulseperformance/awesome-pinescript](https://github.com/pAulseperformance/awesome-pinescript) | pAulse | ★1960 | 2026-02-28 | MIT | 큐레이션 목록 | - | - | - | - | - | 아니오(인덱스) |
| 18 | [everget/tradingview-pinescript-indicators](https://github.com/everget/tradingview-pinescript-indicators) | everget | ★965 | 2026-10-19 | GPL-3.0 | 지표 모음 (패턴 아님) | - | - | - | - | - | 아니오 |
| 19 | [hasnocool/tradingview-pine-scripts](https://github.com/hasnocool/tradingview-pine-scripts) | hasnocool | ★107 | 2024-09-18 | GPL-3.0 | Pine strategy 모음 (ATR Exit, Fib+RSI, BB Fib 등) | 파일별 상이 | ATR Exit 등 | 파일별 상이 | 주식 | 미확인 | 아니오 (GPL) |
| 20 | [capissimo/Pinescript-Laboratory](https://github.com/capissimo/Pinescript-Laboratory) | capissimo | ★114 | 2024-11-08 | 없음 | Pine 모음 (피보나치 비율 BB 등) | 파일별 상이 | 파일별 상이 | 파일별 상이 | - | 없음 | 아니오 |
| 21 | [dizpatek/mexc-ultimate-trading-bot](https://github.com/dizpatek/mexc-ultimate-trading-bot) | dizpatek | ★0 | 2026-04-22 | 없음 | Pine TSL 익절 전략 + 봇 | 파일별 상이 | 트레일링 SL | 파일별 상이 | 크립토 MEXC | 없음 | 아니오 |
| 22 | [turkogluc/forex-pattern](https://github.com/turkogluc/forex-pattern) | turkogluc | ★8 | 2019-03-15 | MIT | Java | 하모닉 감지 | 미확인 | 미확인 | 외환 | 없음 | 아니오 |
| 23 | [alexvin8/metatrader4-harm_pets](https://github.com/alexvin8/metatrader4-harm_pets) | alexvin8 | ★12 | 2019-11-19 | Apache-2.0 | MQL4 (Pine 아님) | 하모닉 PRZ 수동 지정 후 자동 감지 | 미확인 | 미확인 | 외환 | 없음 | 아니오 (Pine 아님) |
| 24 | [Samson5000/Harmonic-Patterns](https://github.com/Samson5000/Harmonic-Patterns) | Samson5000 | ★0 | 2020-01-12 | CC0-1.0 | TradingView 스크립트 모음 (내용 미확인) | 확인 필요 | 확인 필요 | 확인 필요 | - | 없음 | 아니오 (내용 미확인) |
| 26 | [UAlgo Auto Harmonic Pattern Recognition](https://www.tradingview.com/script/Alg2Vb8K-Auto-Harmonic-Pattern-Recognition-UAlgo/) | UAlgo | 확인 불가 | 확인 불가 | open-source (MPL 계열 추정, **미확인**) | indicator (추정) | ZigZag 피벗 후 XABCD 완성 | 극점 바깥 | AD 확장 0.786 / 1.272 / 1.618 기준 3개 목표 | 다수 | 주장 (미검증) | 아니오 |
| 27 | [MSX Harmonic Pro](https://www.tradingview.com/script/Ww3aoTN9-MSX-Harmonic-Pro/) | 확인 불가 | 확인 불가 | 확인 불가 | open-source (페이지 표기) | 확인 필요 | XABCD 비율 점수 기반 진입 | 미확인 | 3단계 목표 | 다수 | 없음 | 아니오 |
| 28 | Harmonic Assistant (XABCD) (TradingView) | 확인 불가 | 확인 불가 | 확인 불가 | open-source | indicator (추정) | PRZ 박스 | SL 라인 | TP1/TP2 | 다수 | 없음 | 아니오 |
| 29 | [Fibonacci Trading Strategy (Auto Levels)](https://in.tradingview.com/script/4FLMhdD4-Fibonacci-Trading-Strategy-Auto-Levels) | riszmufc | 좋아요 99 (주장) | 2025-01-06 (표시 날짜) | open-source (표기) | 유형 미확인 | 되돌림 50%~61.8% 풀백 | 78.6% 되돌림 | 확장 127.2 / 161.8 / 200 / 261.8 / 361.8 | 미명시 | 없음 | 아니오 |
| 30 | [AB=CD Fibonacci Strategy (One Trade at a Time)](https://in.tradingview.com/script/g1QEIDEt-AB-CD-Fibonacci-Strategy-One-Trade-at-a-Time) | julioperez75955 | 좋아요 58 (주장) | 2025-11-30 (발행일) | open-source (표기) | strategy (페이지 표기) | D점 터치 시 진입 | 리스크 대비 보상 배수 (값 미명시) | 리스크 대비 보상 배수 | 미명시 | 없음 | 아니오 |
| 31 | [RSI + MACD Long-Only Strategy](https://www.tradingview.com/script/m99D8MgQ-RSI-MACD-Long-Only-Strategy/) | agrothe | 좋아요 55 (주장) | 2025-08-08 (표시 날짜) | open-source (표기) | strategy (페이지 표기) | RSI 50 상향 돌파 + MACD 강세 또는 MACD 시그널 교차 + RSI≥50 | 진입가 대비 −1.5% (기본) | 진입가 대비 +3.0% (기본) | 미명시 | 없음 | 아니오 |
| 32 | [AliferCryptoStrategy RSI Divergence](https://www.tradingview.com/scripts/alifer) | AliferCryptoStrategy | 확인 불가 | 확인 불가 | open-source (표기 추정) | strategy (추정) | 정규 강세/약세 RSI 다이버전스 | 스윙 고저 또는 ATR 배수 | RR 비율 | 크립토 | 없음 | 아니오 |
| 33 | [AI Fib Strategy (Full Trade Plan)](https://in.tradingview.com/script/d1R85osc-AI-Fib-Strategy-Full-Trade-Plan) | 확인 불가 | 확인 불가 | 확인 불가 | open-source | **indicator** (백테스트 불가 표기) | 골든존 61.8~65% (4H 캔들 바디) | 확인 필요 | TP1~TP3 익스텐션 | 4H | 없음 | 아니오 |
| 34 | [Fibonacci Swing Trading Bot](https://www.tradingview.com/script/dzhi1xb7-Fibonacci-Swing-Trading-Bot) | 확인 불가 | 확인 불가 | 확인 불가 | open-source | 확인 필요 | 피보나치 스윙 | 고정 | 손절폭 기준 2:1 | 다수 | 없음 | 아니오 |
| 35 | [Fibonacci Extension Strt Strategy](https://www.tradingview.com/script/6Rp6JEb5-Fibonacci-Extension-Strt-Strategy/) | 확인 불가 | 확인 불가 | 확인 불가 | open-source | 확인 필요 | 돌파 캔들 기준 | 돌파 캔들 꼬리 아래 | 0.5 / 0.236 부분 청산 + 트레일링 | 다수 | 없음 | 아니오 |
| 36 | [Fibonacci-Only Strategy](https://id.tradingview.com/script/V6eviGjR-Fibonacci-Only-Strategy) | 확인 불가 | 확인 불가 | 확인 불가 | open-source | strategy (추정) | 피보나치 레벨 | 고정 % 또는 ATR | 다중 TP | 다수 | 없음 | 아니오 |
| 37 | [Extended Chart Patterns Detector](https://www.tradingview.com/script/btDQDnDb-Extended-Chart-Patterns-Detector) | 확인 불가 | 확인 불가 | 확인 불가 | open-source | indicator (추정) | 패턴 감지 | 확인 필요 | 확인 필요 | 다수 | 없음 | 아니오 |
| 38 | [Harmonic Patterns (DaviddTech)](https://in.tradingview.com/script/4aK8i3pp-Harmonic-Patterns-DaviddTech) | DaviddTech | 확인 불가 | 확인 불가 | open-source | indicator (추정) | 하모닉 PRZ | 확인 필요 | 확인 필요 | 다수 | 없음 | 아니오 |
| 39 | Fikira Harmonic Patterns Gartley / IKODO Harmonic Patterns | - | - | - | **Protected (비공개 소스)** | - | - | - | - | - | - | **제외** (보호 스크립트라 확인 불가) |

- `확인 필요` = 검색 스니펫이나 페이지에서 규칙을 확인하지 못함. 추측하지 않음.
- 행 24 Samson5000은 레포 설명만 확인했고 스크립트 내용은 열어보지 않았다.

## 2. 저장한 파일 (`chart_predictor/data/pine_refs/pattern/`)

각 파일 상단에 출처 URL, 작성자, 라이선스 표기를 넣었고, 폴더마다 원본 `LICENSE`를 함께 두었다. 원본 소스는 수정하지 않았다.

| 폴더 | 파일 | 라이선스 | 비고 |
|---|---|---|---|
| `luckyjeffy-harmonic-detector/` | `harmonic_patterns.pine` | MIT | 하모닉 감지 + D점 진입 / SL / TP 계산 함수 포함 |
| `ggne-harmonic-pattern-pine/` | `harmonic-pattern-v5.pine` | MIT | XABCD 스캐너, D구간 PRZ 박스만 있음 (SL/TP 없음) |
| `blave-agent-sltp/` | `stop_loss_take_profit.pine` | Apache-2.0 | 패턴 없음. 진입 후 SL/TP 브래킷 `strategy.exit` 참조용 |
| `djoffrey-harmonic-patterns/` | `harmonic_patterns.py`, `harmonic_functions.py` | MIT | 9개 하모닉 패턴 감지, 미완성 패턴 D점 예측 |
| `sandybradley-harmonictrader/` | `harmonic_functions.py`, `deribit_harmonics.py` | MIT | 하모닉 백테스트 참조용. 2020년 이후 업데이트 없음 |

GPL, AGPL, 라이선스 없음, 불명확(NOASSERTION) 항목(BennyThadikaran, Daz92, hasnocool, alphagroove, zeta-zetra, PatternPy, crypto10kx)은 저장하지 않았다. 링크와 요약만 남겼다.

## 3. 스크립트별 메모

- **luckyJeffy (1번).** 하모닉 XABCD를 감지한 뒤 D점을 진입가로 둔다. SL은 D점에서 1% 반대 방향(`risk_percent=0.01`)이다. TP1은 D에서 A 방향으로 |A−D|의 0.382, TP2는 0.618이다. 손익비도 계산한다. 자동 주문은 없다. 소스 직접 확인함(검증).
- **ggne (2번).** XABCD 패턴 감지와 D구간 PRZ 박스 표시만 한다. 진입·SL·TP는 계산하지 않는다. 검증됨. 참고용으로 패턴 감지 부분만 쓸 만하다.
- **djoffrey (3번).** 9개 하모닉 패턴을 감지하고, 아직 완성되지 않은 패턴은 예측 D점을 낸다. 허용 오차(`error_allowed=0.05`) 파라미터가 있다. 소스에서 확인함. SL/TP 계산은 코어 모듈에서 찾지 못했다. 예제 스크립트에 있을 수 있어 확인이 필요하다.
- **sandybradley (4번).** Deribit 데이터로 하모닉을 감지하고 백테스트하는 구조다. 2020년 이후 업데이트가 없다. 지금 쓸 만한 수준인지 불확실하다.
- **crypto10kx (5번).** SL/TP 모듈(`scott_carney_sltp_calculator.py`, `pattern_specific_sltp.py`, `dynamic_risk_manager.py`)과 백테스트가 많다. 다만 라이선스가 명확하지 않고 `BACKTEST_RESULTS.md` 성과는 미검증이다. 재구현 참고 가치는 높지만 복사는 하지 않는다.
- **Blave (6번).** 패턴 기능은 없다. SMA 교차 진입 후 체결가 기준 −2% SL, +4% TP를 `strategy.exit`으로 건다. 체결 후 평균단가로 매 봉 다시 걸어주는 구조다. 저장된 파일 기준으로 검증함. 보호 브래킷 로직 참고용이다.
- **qrak/LLM_trader (7번).** LLM이 OHLCV 데이터를 보고 SL/TP를 제안한다. 페이퍼 트레이딩과 주문 실행을 분리해 두었다. 레포 자체도 "research-grade"라고 밝힌다. `claims.json`과 `results/` 성과는 미검증이다.
- **SnapScalp (8번).** 화면을 캡처해서 LLM에게 진입·청산 가격을 받는다. 이미지에서 가격축을 읽는 정확도 문제를 레포 설명에서도 언급한다.
- **TradingView 항목 (26~38번).** 소스 코드를 열지 못해 규칙은 페이지 설명을 옮긴 것이다. 좋아요·조회수 라벨이 불분명하다. riszmufc, julioperez, agrothe 항목에는 "주장" 표시를 달았다. Fikira·IKODO는 보호 스크립트라 열지 않았다.

## 4. 재구현 우선순위 Top 5 (백테스트 기준 규칙 명확성)

1. **luckyJeffy harmonic_patterns.pine (MIT, 저장됨, 검증됨).** 하모닉 완성 후 D점에서 진입하고 SL은 D에서 1% 반대 방향에 둔다. TP1·TP2는 D에서 A 방향으로 0.382·0.618 되돌림 거리에 둔다.
2. **Fibonacci Trading Strategy (Auto Levels), riszmufc (주장, 미검증).** 50~61.8% 풀백 구간에서 진입하고 SL은 78.6% 되돌림 밖에 둔다. TP는 127.2, 161.8, 200, 261.8, 361.8% 익스텐션에 둔다.
3. **RSI + MACD Long-Only Strategy, agrothe (주장, 미검증).** RSI가 50을 상향 돌파하고 MACD가 강세일 때 또는 MACD가 시그널을 상향 교차하고 RSI가 50 이상일 때 롱 진입한다. SL은 진입가 −1.5%, TP는 진입가 +3.0%로 둔다(기본값).
4. **stop_loss_take_profit.pine, Blave-TW (Apache-2.0, 저장됨, 검증됨).** 진입 봉의 체결가를 기준으로 SL을 −2%, TP를 +4%에 `strategy.exit` 브래킷으로 건다. 체결 후 평균단가로 매 봉 다시 건다. 패턴 로직은 없으니 진입 신호만 바꿔 끼우면 된다.
5. **AB=CD Fibonacci Strategy, julioperez75955 (주장, 미검증).** 가격이 D점을 터치하면 진입하고, C점이 되돌림 50~78.6%이고 CD 길이가 AB와 같을 때 유효한 것으로 본다. SL과 TP는 리스크 대비 보상 배수로 정하지만 기본 배수 값은 페이지에 없어서 백테스트 시 값을 직접 정해야 한다.
