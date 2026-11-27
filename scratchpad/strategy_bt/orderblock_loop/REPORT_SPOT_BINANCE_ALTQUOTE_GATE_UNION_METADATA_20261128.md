# Binance 대체 quote + Gate Spot 메타데이터 합집합 결과 — 2026-11-28

## 결론

**고정 29자산 중 단일 venue에서 2018·2022 전체 월 key가 확인된 자산은 합집합 22개다. 25개 source-screen 기준에 3개 미달하므로 현물 전략시험은 시작하지 않았다.** Gate 데이터의 자동 수집·보관·가공 권리도 아직 미해결이라 Gate 자료는 전략 입력으로 승인되지 않았다.

## 사전등록과 계산 범위

- 사전등록: [PREREG_SPOT_BINANCE_ALTQUOTE_GATE_UNION_METADATA_20261128.md](PREREG_SPOT_BINANCE_ALTQUOTE_GATE_UNION_METADATA_20261128.md), 메타데이터 열람 전 SHA-256 `bfc9ea4db4182dc6117c4941afa0089f410e2a4a46ac9515c158c0945db22698`. 사후에는 해당 줄의 Markdown 줄바꿈용 공백만 정리했으며, 현재 파일 SHA-256은 `fde36ca8dca21d4193c630a3f5111c171aba5a200c76ab82753c89de2fcfbf54`다. 규칙·범위·판정기준은 바꾸지 않았다.
- 코호트는 CMC 2018년 고정 상위 30개에서 BTC benchmark를 뺀 29개다. Gate와 Binance의 2018·2022 12/12월 key 존재만 합산하고, 같은 자산을 두 번 세지 않았다.
- Gate 입력은 이미 저장된 `CMC201801_TOP30_MONTH_MATRIX.csv`의 `pair`, `yyyymm`, `status` 필드만 읽었다. OHLCV·체결 행이나 아카이브 본문은 열지 않았다. 새 외부 요청과 파일 다운로드는 없었다.
- Binance 입력은 [고정 대체 quote 결과](REPORT_BINANCE_SPOT_FIXED_QUOTE_FALLBACK_CMC201801_20261128.md)의 완전 pair 20개를 그대로 사용했다. 이 대사는 별도 source-screen이며 기존 Binance·Gate 1h/4h 교차 venue 사전등록의 결과를 수정하지 않는다.

## 대사 결과

Gate 매트릭스에는 2018·2022 모두 12/12로 보이는 pair 문자열이 19개 있었다. 고정 자산과의 명확한 identity가 있고 pair 방향도 유효한 18개는 `ADA`, `BCH`, `BTG`, `BTS`, `DASH`, `EOS`, `ETC`, `ETH`, `IOTA`, `LSK`, `LTC`, `NEO`, `OMG`, `QTUM`, `WAVES`, `XMR`, `XRP`, `ZEC`다. `BTC_USDT`는 CMC 코호트의 USDT 자산을 뜻하는 `USDT_BTC`와 동일 pair라고 입증되지 않아 제외했다. `BCC`는 CMC의 BitConnect와 Gate의 과거 BCH ticker가 충돌하므로 미확정 실패로 남겼다.

Binance 다중 quote 결과에서 같은 2018·2022 월 key가 확인된 고정 자산은 20개다: `ADA`, `BTS`, `DASH`, `EOS`, `ETC`, `ETH`, `IOTA`, `ICX`, `LSK`, `LTC`, `NEO`, `OMG`, `QTUM`, `TRX`, `WAVES`, `XLM`, `XMR`, `XRP`, `XVG`, `ZEC`.

두 집합의 교집합은 16개다: `ADA`, `BTS`, `DASH`, `EOS`, `ETC`, `ETH`, `IOTA`, `LSK`, `LTC`, `NEO`, `OMG`, `QTUM`, `WAVES`, `XMR`, `XRP`, `ZEC`.

따라서 중복 제거 합집합은 `18 + 20 − 16 = 22/29`다. Gate에서만 key가 확인된 자산은 `BCH`, `BTG`; Binance에서만 확인된 자산은 `ICX`, `TRX`, `XLM`, `XVG`다. 기존 source gate 문턱 25/29보다 3개 부족하다.

## 해석 한계와 게이트

- `22/29`는 서로 다른 venue의 월별 객체 이름을 조합한 원천 상한이다. Gate와 Binance 사이의 실제 체결가격·유동성·quote 환산·비용·갭을 동일한 시계열로 합쳤다는 뜻이 아니다. 심볼별로 venue 하나를 고정하더라도 spot 시장 결과는 USDⓈ-M perpetual 주문장·funding·체결을 대체하지 않는다.
- Gate 문서는 정량 백테스트용 역사자료를 제공한다고 하지만, 현재 저장소의 선행 감사는 자동 대량 수집·장기 보관·파생 통계 권리를 확정하지 못했다. 이 보고서는 해당 제한을 해제하지 않는다.
- Binance 객체 key와 checksum sidecar 이름은 파일 본문 무결성, 연속된 캔들, 당시 상장·상폐·최종회수 처리, 장기 학습 데이터 적격성을 증명하지 않는다.
- Kraken의 20개 direct-USD pair 이름 screen은 날짜 범위·2018/2022 월 완전성을 확인한 결과가 아니므로 이 합집합에 더하지 않았다.
- 세 시장 전략 후보 수는 변하지 않는다: 코인 오더블록 0/2, 국장 0/2, 미장 0/2.

## 재현·검증

- 사전등록 뒤 지정 CSV의 세 필드만 읽고 pair별로 2018·2022의 서로 다른 200 월 수를 집계했다. 2018/2022 모두 12개인 Gate pair 문자열 19개를 얻었다. 공식 pair identity 감사에서 모호하거나 방향이 입증되지 않은 1개를 제외해 Gate 고유 자산 18개로 확정했다.
- Binance의 고정 다중 quote 결과 파일에서 완전 자산 20개를 취하고, 고정 ticker identity로 집합 교집합 16개·합집합 22개를 계산했다.
- Python 실행은 `TRADING_DATA_DIR=/Users/user/CODE/Coin_Trade/trading_data`, `PYTHONDONTWRITEBYTECODE=1`, `-B`를 사용했다. 첫 집계 시도는 임시 코드의 예외 집계식 오류로 실패했고, 데이터나 파일에 쓰지 않았다. 수정한 메모리 내 집계는 성공했다.
- `TRAIN_TRIALS.csv` 접근·수정 0건, 가격·체결 행 열람 0건, 네트워크 요청 0건, 다운로드 0건, 데이터·캐시·로그·임시파일 생성 0건이다. 이 메타데이터 대사는 전략 백테스트·통계 검정이 아니다.

## 다음 조치

이 고정 29자산·고정 연도 source screen은 22/29로 실패했으며 Gate 권리도 해소되지 않았다. 이 경로에서 가격 데이터를 받거나 기준을 낮추지 않는다. 다음은 별도 승인 없이 가격자료에 손대지 말고, 사용자가 이미 보유한 적법한 자료 중 PIT·상폐 포함 범위와 내부 백테스트 권리가 문서로 증명되는 경로가 있는지 먼저 대조한다. 그런 경로가 없으면 현물 30자산 코호트는 계속 `DATA_BLOCKED`로 기록한다.
