# Binance·Kraken 현물 고정 코호트 월별 timestamp 게이트 결과

실행일: 2026-11-28 (Asia/Seoul)
판정: **실패 — 22/29, 25/29 미달. 이 source screen으로 전략시험을 시작하지 않았다.**

## 사전등록과 범위

- 실행 전 고정: [PREREG_SPOT_BINANCE_KRAKEN_MONTH_COVERAGE_20261128.md](PREREG_SPOT_BINANCE_KRAKEN_MONTH_COVERAGE_20261128.md).
- 고정 분모는 CMC 2018 상위 30개 중 BTC benchmark를 제외한 29자산이다. 기존 Binance 대체 quote 월 객체 기준 20/29를 변경하지 않았다.
- Kraken은 이미 저장된 공식 OHLCVT ZIP에서 1시간봉만 읽었다. 자산별 direct USD pair를 먼저, 없으면 direct XBT pair를 선택했다. `BCC` 정체성은 실패로 유지했다.
- ZIP은 수정·추출하지 않았다. 각 CSV 행의 첫 timestamp 필드만 파싱해 2018·2022 월별 존재 bit를 계산했고, 가격·거래량·거래 수는 해석하거나 출력하지 않았다. 2022-12-31 UTC 이후 첫 timestamp에서 member 읽기를 멈췄다.
- 입력: `TRADING_DATA_DIR=/Users/user/CODE/Coin_Trade/trading_data`; 환경변수의 canonical 경로와 ZIP 경로가 그 데이터 루트 아래인지 검증했다. `TRAIN_TRIALS.csv`를 열지 않았다.

## 결과

| 기준 | 자산 수 | 판정 |
|---|---:|---|
| Binance 기존 1h ZIP·checksum 월 key 기준 | 20/29 | 선행 source screen |
| Kraken 1h에서 2018·2022 모두 매월 timestamp 존재 | 9/29 | 새 읽기전용 screen |
| 두 source의 자산 합집합 | 22/29 | **25/29 미달** |

Kraken에서 양 연도 모두 12/12개월이 확인된 자산은 BCH, DASH, ETC, ETH, LTC, USDT, XMR, XRP, ZEC다. Binance 기준과의 합집합은 22개이며 목표 문턱보다 3개 부족하다. Kraken filename만으로 센 기존 20개 후보 중 상당수는 실제 1h 월 timestamp가 2018년에 부족했다. 예: ADA 4/12, XLM 11/12, EOS 11/12, QTUM 4/12. 상장 시점이 늦은 NEO·NANO·TRX·LSK·ICX·OMG·WAVES는 이 화면에서 2018년 0/12였다.

이 합집합은 원천 탐색용이다. Binance 쪽은 선행 보고서의 객체 key 존재, Kraken 쪽은 실제 1h timestamp 존재로 증거 수준이 서로 다르다. 따라서 22/29는 가격 연속성·PIT·상폐 최종가치·정당한 사용권을 증명하지 않으며 전략 성과도 아니다. 이 source gate에서는 다음 전략 실행을 시작하지 않는다.

## 재현·검증

- 실행 코드: [binance_kraken_month_coverage.py](binance_kraken_month_coverage.py). 실행: `TRADING_DATA_DIR=/Users/user/CODE/Coin_Trade/trading_data PYTHONDONTWRITEBYTECODE=1 python3 -B scratchpad/strategy_bt/orderblock_loop/binance_kraken_month_coverage.py`.
- 합성 회귀시험: `TRADING_DATA_DIR=/Users/user/CODE/Coin_Trade/trading_data PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest scratchpad/strategy_bt/orderblock_loop/tests/test_binance_kraken_month_coverage.py -v` — **6/6 통과** (0.001초). 검사 범위는 canonical 데이터 루트 강제, 첫 열만 해석, UTC 월 경계, 동결 기간 밖 정지, 비정렬 timestamp fail-closed, 고정 코호트/분모다.
- 이 결과는 실제 원본의 timestamp 존재만 측정한다. 승률·목표 선도달률·손익비·비용 후 수익률·MDD·Sharpe·OOS 성과는 계산하지 않았다.
- 외부 통신·다운로드 0, ZIP 추출·수정 0, 공용 ledger 접근 0, 저장소 외부 산출물 생성 0.

## 저장 경로 지침 재확인

사용자 지시대로 정규 저장소 및 데이터 경로 강제 규칙은 이미 `AGENTS.md`, `CODEX.md`, `CLAUDE.md`, `docs/STORAGE_RULES.md`에 기록돼 있다. 규칙에 따라 금지된 위치의 존재 확인·검색이나 작성자 추적을 하지 않았다. 내부 증거만으로 작성자를 특정할 수 없는 외부 산출은 누구의 것인지 확인하지 않는다.
