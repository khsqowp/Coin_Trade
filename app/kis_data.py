"""한국투자증권 국내주식 일봉 시세 조회 (모의투자 도메인, TR FHKST03010100).

app/data.py의 fetch_ohlcv()와 동일한 DataFrame 계약(Open/High/Low/Close/Volume,
timestamp 인덱스, 오름차순)을 지켜서 기존 backtesting 파이프라인이 그대로 먹게 한다.

한 번 호출에 최대 100건만 나오므로 날짜창을 뒤로 밀어가며 페이지네이션한다.
모의투자 게이트웨이가 간헐적으로 EGW00300(라우팅 오류)을 뱉는 걸 실측 확인했으므로
각 페이지 호출에 재시도를 둔다(재시도 자체는 app/kis_fetch_base.py 공통 구현).
"""
from __future__ import annotations

import datetime as dt
import time

from app.kis_fetch_base import fetch_page_with_retry, normalize_ohlcv_frame

QUOTE_TR_ID = "FHKST03010100"
PAGE_SLEEP_SECONDS = 0.3
MAX_PAGES = 40  # 100일/페이지 * 40 ≈ 15년치, 충분한 상한

_COLUMN_MAP = {
    "stck_oprc": "Open", "stck_hgpr": "High", "stck_lwpr": "Low",
    "stck_clpr": "Close", "acml_vol": "Volume",
}


def _fetch_page(token: str, symbol: str, date1: str, date2: str, max_retries: int = 4) -> list[dict]:
    params = {
        "FID_COND_MRKT_DIV_CODE": "J",
        "FID_INPUT_ISCD": symbol,
        "FID_INPUT_DATE_1": date1,
        "FID_INPUT_DATE_2": date2,
        "FID_PERIOD_DIV_CODE": "D",
        "FID_ORG_ADJ_PRC": "0",
    }
    return fetch_page_with_retry(
        token, QUOTE_TR_ID, "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice",
        params, symbol, max_retries,
    )


def fetch_ohlcv_kis(symbol: str, token: str, since_iso: str, until_iso: str | None = None):
    since_date = dt.date.fromisoformat(since_iso[:10])
    until_date = dt.date.fromisoformat(until_iso[:10]) if until_iso else dt.date.today()

    rows: list[dict] = []
    window_end = until_date
    for _ in range(MAX_PAGES):
        page = _fetch_page(token, symbol, since_date.strftime("%Y%m%d"), window_end.strftime("%Y%m%d"))
        if not page:
            break
        rows.extend(page)
        earliest = min(dt.date.fromisoformat(r["stck_bsop_date"][:4] + "-" + r["stck_bsop_date"][4:6] + "-" + r["stck_bsop_date"][6:8]) for r in page)
        if earliest <= since_date:
            break
        window_end = earliest - dt.timedelta(days=1)
        time.sleep(PAGE_SLEEP_SECONDS)

    return normalize_ohlcv_frame(rows, "stck_bsop_date", _COLUMN_MAP, since_date, until_date)
