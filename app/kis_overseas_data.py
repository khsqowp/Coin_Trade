"""한국투자증권 해외주식(미국) 일봉 시세 조회 (모의투자 도메인, TR HHDFS76240000).

app/kis_data.py의 fetch_ohlcv_kis()와 동일한 DataFrame 계약(Open/High/Low/Close/Volume,
timestamp 인덱스, 오름차순)을 지켜서 기존 backtesting 파이프라인이 그대로 먹게 한다.

한 번 호출에 최대 100건, output2가 최신순으로 내려오므로 가장 오래된 행의 날짜를
BYMD에 넣어 뒤로 페이지네이션한다(재시도 자체는 app/kis_fetch_base.py 공통 구현).
"""
from __future__ import annotations

import datetime as dt
import time

from app.kis_fetch_base import fetch_page_with_retry, normalize_ohlcv_frame

QUOTE_TR_ID = "HHDFS76240000"
PAGE_SLEEP_SECONDS = 0.3
MAX_PAGES = 40

_COLUMN_MAP = {"open": "Open", "high": "High", "low": "Low", "clos": "Close", "tvol": "Volume"}


def _fetch_page(token: str, symbol: str, excd: str, bymd: str, max_retries: int = 4) -> list[dict]:
    params = {"AUTH": "", "EXCD": excd, "SYMB": symbol, "GUBN": "0", "BYMD": bymd, "MODP": "1"}
    return fetch_page_with_retry(
        token, QUOTE_TR_ID, "/uapi/overseas-price/v1/quotations/dailyprice",
        params, symbol, max_retries,
    )


def fetch_ohlcv_kis_overseas(symbol: str, excd: str, token: str, since_iso: str, until_iso: str | None = None):
    since_date = dt.date.fromisoformat(since_iso[:10])
    until_date = dt.date.fromisoformat(until_iso[:10]) if until_iso else dt.date.today()

    rows: list[dict] = []
    bymd = until_date.strftime("%Y%m%d")
    for _ in range(MAX_PAGES):
        page = _fetch_page(token, symbol, excd, bymd)
        page = [r for r in page if r.get("xymd")]
        if not page:
            break
        rows.extend(page)
        earliest = min(dt.date.fromisoformat(r["xymd"][:4] + "-" + r["xymd"][4:6] + "-" + r["xymd"][6:8]) for r in page)
        if earliest <= since_date or len(page) < 100:
            break
        bymd = (earliest - dt.timedelta(days=1)).strftime("%Y%m%d")
        time.sleep(PAGE_SLEEP_SECONDS)

    return normalize_ohlcv_frame(rows, "xymd", _COLUMN_MAP, since_date, until_date)
