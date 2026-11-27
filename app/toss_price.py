"""토스증권 공식 OpenAPI 시세조회 래퍼 (openapi.tossinvest.com) — 조회만, 주문 엔드포인트 없음.

VOLREG-R1 포워드 가상매매에서 SPY/QQQ 현재가·과거 일봉 조회에 쓴다. 한투(KIS) 모의투자
인증이 계속 막혀서(2026-11-27, 모의투자 신청 상태 문제) 토스로 교체했다 — 가격조회 전용으로
쓰므로 실거래 리스크 없음. OAuth2 client_credentials, 토큰 유효기간 24시간(실측 86399초)이라
KIS(분당 1회 제한)보다 운용이 훨씬 수월해 프로세스 내 캐시만으로 충분하다.
"""
from __future__ import annotations

import os
import time

import requests

BASE_URL = "https://openapi.tossinvest.com"

_token: str | None = None
_token_expires_at = 0.0


def _credentials() -> tuple[str, str]:
    return os.environ["TOSS_API_ID"], os.environ["TOSS_API_SECRET"]


def issue_token(force: bool = False) -> str:
    global _token, _token_expires_at
    if not force and _token and time.monotonic() < _token_expires_at:
        return _token
    client_id, client_secret = _credentials()
    resp = requests.post(
        f"{BASE_URL}/oauth2/token",
        data={"grant_type": "client_credentials", "client_id": client_id, "client_secret": client_secret},
        timeout=10,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"토스 토큰발급 실패: {resp.status_code} {resp.text}")
    body = resp.json()
    _token = body["access_token"]
    # 재발급하면 이전 토큰이 즉시 무효화되므로(토스 OAuth2 특성) 만료 60초 전부터 미리 갱신한다.
    _token_expires_at = time.monotonic() + float(body.get("expires_in", 86399)) - 60
    return _token


def get_prices(symbols: list[str]) -> dict[str, float]:
    """심볼 -> 현재가(USD). 최대 200개, 콤마로 묶어 한 번에 조회."""
    token = issue_token()
    resp = requests.get(
        f"{BASE_URL}/api/v1/prices",
        headers={"Authorization": f"Bearer {token}"},
        params={"symbols": ",".join(symbols)},
        timeout=10,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"토스 현재가 조회 실패: {resp.status_code} {resp.text}")
    return {row["symbol"]: float(row["lastPrice"]) for row in resp.json()["result"]}


def get_daily_closes(symbol: str, since_iso: str, max_pages: int = 5) -> dict[str, float]:
    """날짜("YYYY-MM-DD") -> 일봉 종가(USD). since_iso 이전까지 `before` 커서로 페이지네이션."""
    token = issue_token()
    out: dict[str, float] = {}
    before: str | None = None
    for _ in range(max_pages):
        params: dict[str, object] = {"symbol": symbol, "interval": "1d", "count": 200}
        if before:
            params["before"] = before
        resp = requests.get(
            f"{BASE_URL}/api/v1/candles",
            headers={"Authorization": f"Bearer {token}"},
            params=params,
            timeout=10,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"토스 일봉 조회 실패({symbol}): {resp.status_code} {resp.text}")
        result = resp.json()["result"]
        candles = result.get("candles", [])
        if not candles:
            break
        for candle in candles:
            date_iso = candle["timestamp"].split("T")[0]
            out[date_iso] = float(candle["closePrice"])
        oldest_timestamp = min(c["timestamp"] for c in candles)
        next_before = result.get("nextBefore")
        if oldest_timestamp.split("T")[0] <= since_iso or not next_before:
            break
        before = next_before
    return out
