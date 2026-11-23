# 한국 상폐·시점별 상장 종목 수집기

수집기는 직접 실행할 때만 `FinanceDataReader`와 `pykrx`를 호출하며 가격 상한은 **2026-05-31**이다. 기본 출력은 `/Users/user/CODE/trading_data/external/kr_pit/`이며 repo에는 데이터를 쓰지 않는다.

## 설치·실행 명령

```sh
python3 -m venv /Users/user/CODE/trading_data/cache/kr_pit/venv
/Users/user/CODE/trading_data/cache/kr_pit/venv/bin/python -m pip install --upgrade pip
/Users/user/CODE/trading_data/cache/kr_pit/venv/bin/python -m pip install pykrx finance-datareader pyarrow pandas
cd /Users/user/CODE/Coin_Trade/data_sources/kr_pit
/Users/user/CODE/trading_data/cache/kr_pit/venv/bin/python -m unittest -v test_collector.py
/Users/user/CODE/trading_data/cache/kr_pit/venv/bin/python collector.py --rate-seconds 0.5
```

## 출력과 한계

- `membership.csv`: R4 헤더 `market,symbol,alive_from,alive_through,source,source_asof`. KOSPI/KOSDAQ 월말 티커 스냅샷에서 각 코드의 첫·마지막 관측일을 만든다. 이는 관측된 구간이며 정확한 IPO·상폐일을 보증하지 않는다. pykrx 목록은 ISIN을 주지 않아 코드를 심볼로 쓴다.
- `snapshots/YYYY-MM-DD_{KOSPI,KOSDAQ}.csv`: 월말 단위 저장·재개용 캐시. 끝난 스냅샷은 재실행에서 건너뛴다.
- `delistings.csv`: FDR `KRX-DELISTING` 응답 중 상폐일이 컷오프 이내인 목록. 재사용 코드는 `코드:상장일`로 분리한다. 상장일 누락 시 `unknown`이라 동일 코드 재사용을 확정 분리할 수 없다.
- `delisted_ohlcv.parquet`: pykrx 일봉, zstd 압축. 종목(코드+상장일)별 최소 2행을 요구하며 빈/짧은 결과는 제외한다. `merger_delisting` 표시로 합병성 상폐를 -100%로 오인하는 처리를 막는다. 완료된 종목은 `delisted_chunks/`에 보존해 재실행에서 재호출하지 않는다.
- `delisted_price_coverage.csv`: 성공/실패 상태와 행 수.
- `MANIFEST_sha256.csv`: 상대경로, 행 수, 바이트, SHA-256.

호출별 0.5초 대기와 4회 재시도(1·2·3초)가 적용된다. 가격 통합 파일은 재실행 때 다시 생성한다. FDR 상폐목록의 역사적 완전성, pykrx 과거 날짜 조회 범위, ISIN 매핑은 보증되지 않으므로 출력만으로 생존편향 제거가 입증되지는 않는다.

## 현황 (2026-11-23 확인)

`collector.py` 실행이 중간에 멈춘 상태로 보인다: `external/kr_pit/delisting_list.csv`(4,229행, FDR KRX-DELISTING)만 있고, `snapshots/*.csv`는 전부 헤더 1행뿐(634개 파일 모두 비어 있음), `membership.csv`/`delisted_ohlcv.parquet`/`MANIFEST_sha256.csv`는 아직 없다.

**중단 원인(2026-11-23 확인, 담당 세션 보고): pykrx가 상폐 종목 과거 일봉 조회에 KRX_ID/KRX_PW 로그인을 요구해 빈 결과를 반환, 그대로 멈췄다.** 해당 환경변수가 없으면 이 경로로는 실행이 안 된다. 재실행하지 않음 — 아래 `build_membership.py` 경량 경로(가격 없이 membership만)로 대체했다.

## build_membership.py — 경량 대안 (membership만, 가격 없음)

위 전체 파이프라인과 별개로, `delisting_list.csv`만 입력으로 받아 R4 membership 형식(`market,symbol,alive_from,alive_through,source,source_asof`)을 즉시 만드는 경량 스크립트다. 상폐 종목의 **일별 가격은 만들지 않는다** — membership(상장상태)만의 PIT이며, 가격 공백은 하류(`search_equities_r4.py`/`search_equities_r5.py`)의 `delisting_gap` 로직이 그대로 집계한다. 출력에는 전 행에 `status=PIT_MEMBERSHIP_ONLY`를 남겨 가격 보증이 아님을 표시한다.

처리 규칙(결과 열람 전 고정):
1. **ListingDate 결측(2026-11-23 확인 기준 25/4,229행, 전부 수익증권·리츠·스팩·우선주·권리상장 "R" 코드 등 특수종목)은 alive_from을 추정하지 않고 membership에서 전부 제외한다.** 제외 코드·개수를 별도 CSV(`excluded_missing_listing_date.csv`)로 남긴다.
2. `delisting_list.csv` 내부에서 동일 `Symbol`이 중복되는 행은 없음을 확인(2026-11-23, 0건)했지만, 코드가 재사용되어 외부 current-listing 입력과 기간이 겹치면 두 레코드 모두 제외하고 보고한다(어느 쪽이 맞는지 추정하지 않음). 겹치지 않으면 `source`를 다르게 달아 별도 레코드로 유지한다.
3. 현재 상장 종목(예: FDR `StockListing('KRX')`)을 `--current-listing` 입력으로 받으면 `alive_through=2026-05-31`(가격 상한과 동일 고정일), `source`는 입력이 명시한 그대로 기록한다. 입력이 없으면 상폐 종목만의 membership을 만들고 그 사실을 콘솔에 출력한다.
4. 출력 경로: `~/CODE/trading_data/cache/orderblock/equity_membership_kr.csv`. repo에는 쓰지 않는다.
5. **(2026-11-23 추가) 현재상장 입력의 `listing_date`가 가격 상한 고정일 `2026-05-31`보다 뒤면 그 행 전체를 membership에서 제외한다.** `alive_from`을 상한일로 당기거나 그 외 추정값으로 바꾸지 않는다(그렇게 하면 `alive_from>alive_through` 역전이 생겨 하류 로더가 `invalid membership interval/source`로 전부 중단됨, 2026-11-23 실제 발생). 제외 코드·개수를 별도 CSV(`excluded_after_cutoff.csv`)로 남기고, 생성 직후 모든 출력 행이 `alive_from<=alive_through`인지 스크립트가 직접 검증해 콘솔에 보고한다.

## 현재 상장 종목 결합 재생성 (2026-11-23)

`~/CODE/trading_data/external/kr_pit/current_listing_for_membership.csv`(FDR KRX-DESC, 2,769행)를 `--current-listing`으로 넣어 재생성했다. 구 파일은 `equity_membership_kr.csv.bak_20261123_pre_current_listing`/`excluded_missing_listing_date.csv.bak_20261123_pre_current_listing`로 보존했다.

- 결과: membership 6,973행(상폐 4,204 + 현재상장 2,769), ListingDate 결측 제외 25건, 중복 Symbol 0건, **겹침 충돌 0건**.
- 현재상장 입력 쪽 ListingDate 결측 109건은 리눅스 투자 세션이 파일 생성 전에 이미 걸러냈다고 보고했다. 이 세션은 그 원본(필터 전) 목록을 받지 못해 109건의 코드 목록을 독립적으로 재현·기록하지 못한다 — 숫자만 전달받은 값이고 검증되지 않았다.
- **market 라벨 불일치 발견**: `equity_membership_kr.csv`의 `market`은 KOSPI/KOSDAQ/KONEX/KOSDAQ GLOBAL이고, `scratchpad/strategy_bt/orderblock_loop/universe/KR.csv`의 `market`은 전부 고정 문자열 `KR`이다. `search_equities_r4.py`/`r5.py`의 `load_membership`은 `(market, symbol)` 튜플로 조회하므로, 이 두 파일을 그대로 넘기면 전부 매칭 실패한다. symbol만으로 매칭하면 558개 전부 일치하지만, 코드 수정(튜플 키를 symbol 단독 또는 market 정규화로 바꾸는 것) 없이는 실행기가 못 쓴다.

### universe/KR.csv 558개 매칭·TRAIN 가격 커버리지 (read-only, TEST 미접근)

- symbol 기준 membership 매칭: 558/558 전부 일치(market 문자열은 위 불일치로 무시하고 symbol만 비교).
- `external/equities/kr/daily_stocks_delisted.parquet`(234만행)에서 공통 TRAIN 경계 `2018-10-26` 이전 행이 있는 심볼: **557/558**. 심볼 `036220`만 TRAIN 구간 가격 행이 0개다.
- TRAIN 구간 보유 557개의 종목별 행수: 최소 527, 중앙값 2,786, 최대 3,000 — 전부 하류 최소 30행 기준을 넉넉히 넘는다.
