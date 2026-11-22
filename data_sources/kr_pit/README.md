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
- `delisted_ohlcv.parquet`: pykrx 일봉, zstd 압축. 조회별 최소 2행을 요구하며 빈/짧은 결과는 제외한다. `merger_delisting` 표시로 합병성 상폐를 -100%로 오인하는 처리를 막는다.
- `delisted_price_coverage.csv`: 성공/실패 상태와 행 수.
- `MANIFEST_sha256.csv`: 상대경로, 행 수, 바이트, SHA-256.

호출별 0.5초 대기와 4회 재시도(1·2·3초)가 적용된다. 가격 통합 파일은 재실행 때 다시 생성한다. FDR 상폐목록의 역사적 완전성, pykrx 과거 날짜 조회 범위, ISIN 매핑은 보증되지 않으므로 출력만으로 생존편향 제거가 입증되지는 않는다.
