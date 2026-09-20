"""한국투자증권 Open API 모의투자 인증 — 토큰 발급/캐시.

모의투자 전용 도메인만 쓴다 (실전 도메인은 모의투자 앱키를 거부한다 — 실측 확인됨).
토큰 발급은 앱키당 분당 1회로 제한되므로(EGW00133) 프로세스 내에서 한 번만 발급해 재사용한다.
"""
from __future__ import annotations

import os
import time

import requests

VTS_BASE_URL = "https://openapivts.koreainvestment.com:29443"

# 모의투자 계좌는 초당 거래건수 제한이 실전 계좌보다 훨씬 빡빡하다(EGW00201/EGW00215) — 한
# 사이클 안에서 잔고조회를 여러 번 연달아 부르기만 해도 걸린다(실측: 해외 잔고조회 2회 + 국내
# 예수금조회 1회를 붙여서 부르면 거의 매번 걸림). 호출 간 최소 간격을 강제하고, 그래도 걸리면
# 백오프 후 재시도해서 한 번의 순간적인 제한 초과로 사이클 전체가 예외로 죽지 않게 한다.
_RATE_LIMIT_MSG_CODES = {"EGW00201", "EGW00215"}
_MIN_REQUEST_INTERVAL_SECONDS = 1.05
_last_request_monotonic = 0.0


def app_credentials() -> tuple[str, str]:
    return os.environ["HANTOO_TEST_KEY"], os.environ["HANTOO_TEST_SECRET"]


def throttled_request(method: str, url: str, max_retries: int = 4, timeout: int = 15, **kwargs) -> requests.Response:
    """KIS 호출 전 최소 간격을 강제하고, 초당 거래건수 제한 응답이면 대기 후 재시도한다.

    모의투자 서버(특히 해외주식 엔드포인트)는 DNS 실패/connect·read 타임아웃이 실측상
    매우 잦다(재시도 없이는 미장 봇이 인셉션 이후 단 한 번도 체결에 성공 못 한 사례 있음).
    requests 예외는 원래 여기서 잡지 않고 그대로 던져 호출부(한 사이클) 전체를 죽였는데,
    순간적인 네트워크 문제일 뿐인 경우가 대부분이라 요율제한 응답과 같은 백오프로 재시도한다.
    """
    global _last_request_monotonic
    last_exc: requests.exceptions.RequestException | None = None
    for attempt in range(max_retries):
        wait = _MIN_REQUEST_INTERVAL_SECONDS - (time.monotonic() - _last_request_monotonic)
        if wait > 0:
            time.sleep(wait)
        try:
            response = requests.request(method, url, timeout=timeout, **kwargs)
        except requests.exceptions.RequestException as exc:
            _last_request_monotonic = time.monotonic()
            last_exc = exc
            if attempt < max_retries - 1:
                time.sleep(2 * (attempt + 1))
                continue
            raise
        _last_request_monotonic = time.monotonic()
        try:
            body = response.json()
        except ValueError:
            return response
        if body.get("msg_cd") in _RATE_LIMIT_MSG_CODES and attempt < max_retries - 1:
            time.sleep(2 * (attempt + 1))
            continue
        return response
    raise last_exc  # type: ignore[misc]


def issue_token(max_retries: int = 5) -> str:
    app_key, app_secret = app_credentials()
    last_error: Exception | None = None
    for attempt in range(max_retries):
        try:
            resp = requests.post(
                f"{VTS_BASE_URL}/oauth2/tokenP",
                json={"grant_type": "client_credentials", "appkey": app_key, "appsecret": app_secret},
                timeout=10,
            )
        except requests.exceptions.RequestException as exc:
            last_error = exc
            time.sleep(3)
            continue
        if resp.status_code == 200:
            return resp.json()["access_token"]
        last_error = RuntimeError(f"token issue failed: {resp.status_code} {resp.text}")
        if "EGW00133" in resp.text:  # 분당 1회 제한 — 대기 후 재시도
            time.sleep(65)
            continue
        time.sleep(3)
    raise last_error  # type: ignore[misc]
