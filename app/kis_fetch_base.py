"""KIS 국내/해외 일봉 조회 공통 로직 — kis_data.py와 kis_overseas_data.py가 거의 동일하게
반복하던 'HTTP 재시도 페이지 호출'과 '결과를 OHLCV DataFrame으로 정규화'하는 부분만 뽑았다.
페이지네이션 루프(다음 페이지로 넘어가는 조건)는 국내/해외가 실제로 다르므로(국내는 date1/date2
창을 밀고, 해외는 BYMD 단일값+100건 미만이면 중단) 각 파일에 그대로 남겨둔다.
"""
from __future__ import annotations

import time

import pandas as pd

from app.kis_auth import VTS_BASE_URL, app_credentials, throttled_request

DEFAULT_MAX_RETRIES = 4
DEFAULT_TIMEOUT_SECONDS = 15


def fetch_page_with_retry(
    token: str,
    tr_id: str,
    url_path: str,
    params: dict,
    symbol_label: str,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> list[dict]:
    """지정한 TR로 한 페이지(output2)를 조회하고, 네트워크 오류/실패 응답에 재시도한다."""
    app_key, app_secret = app_credentials()
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "authorization": f"Bearer {token}",
        "appkey": app_key,
        "appsecret": app_secret,
        "tr_id": tr_id,
        "custtype": "P",
    }
    for attempt in range(max_retries):
        try:
            resp = throttled_request(
                "GET", f"{VTS_BASE_URL}{url_path}", headers=headers, params=params, timeout=DEFAULT_TIMEOUT_SECONDS
            )
            body = resp.json()
        except Exception as exc:  # noqa: BLE001 — throttled_request 내부의 requests 예외를 그대로 흡수
            if attempt < max_retries - 1:
                time.sleep(2 * (attempt + 1))
                continue
            raise RuntimeError(f"{symbol_label} 캔들 조회 네트워크 오류: {exc}") from exc
        if body.get("rt_cd") == "0":
            return body.get("output2", [])
        if attempt < max_retries - 1:
            time.sleep(2 * (attempt + 1))
            continue
        raise RuntimeError(f"{symbol_label} 캔들 조회 실패: {body.get('msg_cd')} {body.get('msg1')}")
    return []


def normalize_ohlcv_frame(
    rows: list[dict],
    date_field: str,
    column_map: dict[str, str],
    since_date,
    until_date,
) -> pd.DataFrame:
    """페이지들에서 모은 row를 app/data.py와 동일한 OHLCV DataFrame 계약으로 정규화한다."""
    if not rows:
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])

    frame = pd.DataFrame(rows)
    frame["timestamp"] = pd.to_datetime(frame[date_field], format="%Y%m%d", utc=True)
    frame = frame.rename(columns=column_map)
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    frame = frame.drop_duplicates(subset="timestamp").sort_values("timestamp")
    frame = frame.set_index("timestamp")[["Open", "High", "Low", "Close", "Volume"]]
    return frame[(frame.index.date >= since_date) & (frame.index.date <= until_date)]
