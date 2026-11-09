"""Single transport with persisted throttle, bans, and secret-safe errors."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlencode
import hashlib
import hmac
import re
import time
import requests
from config import Config
from safety import TESTNET_HOST, assert_testnet_url, redact
from state import StateStore


class BanError(RuntimeError):
    def __init__(self, until: float):
        self.until = until
        super().__init__(f"Testnet requests banned until epoch {until:.0f}")


class ExchangeError(RuntimeError):
    def __init__(self, code: Any, msg: str, status: int | None = None):
        self.code, self.msg, self.status = code, msg, status
        super().__init__(f"Exchange error {code}: {msg}")


@dataclass(repr=False)
class Signer:
    api_key: str = field(repr=False)
    secret: str = field(repr=False)

    def __repr__(self) -> str:
        return "Signer(credentials=[REDACTED])"

    def sign(self, params: dict[str, Any], timestamp: int) -> dict[str, Any]:
        signed = dict(params, timestamp=timestamp, recvWindow=5000)
        signed["signature"] = hmac.new(
            self.secret.encode(), urlencode(signed).encode(), hashlib.sha256
        ).hexdigest()
        return signed


class ThrottledHttp:
    def __init__(
        self,
        config: Config,
        signer: Signer | None = None,
        session: Any = None,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], None] = time.sleep,
        fs: StateStore | None = None,
    ):
        self.config, self.signer = config, signer
        self.session = session or requests.Session()
        self.clock, self.sleep = clock, sleep
        self.store = fs or StateStore(config.state_dir)
        self.base_url = f"https://{TESTNET_HOST}"

    def __repr__(self) -> str:
        return "ThrottledHttp(testnet-only)"

    def check_ban(self) -> None:
        ban = self.store.read("ban.json", {})
        if float(ban.get("until_epoch_s", 0)) > self.clock():
            raise BanError(float(ban["until_epoch_s"]))

    def _slot(self) -> None:
        while True:
            with self.store.lock(".throttle.lock"):
                self.check_ban()
                now = self.clock()
                times = [
                    t for t in self.store.read("throttle.json", []) if t > now - 60
                ]
                if len(times) < self.config.throttle_per_minute:
                    self.store.write("throttle.json", times + [now])
                    return
                delay = max(0.001, min(times) + 60 - now)
            self.sleep(delay)

    def request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        signed: bool = False,
        retry: bool = True,
    ) -> Any:
        url = path if "://" in path else self.base_url + path
        assert_testnet_url(url)
        secrets = [self.signer.api_key, self.signer.secret] if self.signer else []
        attempts = 3 if retry else 1
        for attempt in range(attempts):
            self._slot()
            payload = dict(params or {})
            headers = {}
            if signed:
                if not self.signer:
                    raise ExchangeError("AUTH", "Testnet signer is required")
                payload = self.signer.sign(payload, int(self.clock() * 1000))
                headers["X-MBX-APIKEY"] = self.signer.api_key
            try:
                response = self.session.request(
                    method,
                    url,
                    params=payload,
                    headers=headers,
                    timeout=30,
                    allow_redirects=False,
                )
            except (requests.Timeout, requests.ConnectionError):
                if attempt == attempts - 1:
                    raise ExchangeError(
                        "NETWORK",
                        "Testnet transport failed; order execution may be uncertain",
                    ) from None
                self.sleep(2**attempt)
                continue
            try:
                body = response.json()
            except ValueError:
                body = {}
            status = response.status_code
            if status in (418, 429):
                until = self.clock() + 60
                msg = str(body.get("msg", "")) if isinstance(body, dict) else ""
                match = re.search(r"banned until\s+(\d+)", msg, re.I)
                if match:
                    until = max(until, int(match.group(1)) / 1000)
                retry = response.headers.get("Retry-After")
                if retry:
                    try:
                        until = max(self.clock(), self.clock() + float(retry))
                        if match:
                            until = max(until, int(match.group(1)) / 1000)
                    except ValueError:
                        pass
                with self.store.lock(".throttle.lock"):
                    previous = self.store.read("ban.json", {})
                    until = max(until, previous.get("until_epoch_s", 0))
                    self.store.write(
                        "ban.json",
                        {"until_epoch_s": until, "status": status, "ts": self.clock()},
                    )
                raise BanError(until)
            if 500 <= status < 600 and attempt < attempts - 1:
                self.sleep(2**attempt)
                continue
            if not 200 <= status < 300:
                code = body.get("code", status) if isinstance(body, dict) else status
                msg = (
                    body.get("msg", "Testnet request failed")
                    if isinstance(body, dict)
                    else "Testnet request failed"
                )
                raise ExchangeError(
                    redact(str(code), secrets), redact(str(msg), secrets), status
                )
            if not isinstance(body, (dict, list)):
                raise ExchangeError("JSON", "Unexpected testnet response")
            return body
        raise ExchangeError("NETWORK", "No response")

    def get(
        self, path: str, params: dict[str, Any] | None = None, signed: bool = False
    ) -> Any:
        return self.request("GET", path, params, signed)

    def post(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        signed: bool = False,
        retry: bool = True,
    ) -> Any:
        return self.request("POST", path, params, signed, retry)

    def delete(
        self, path: str, params: dict[str, Any] | None = None, signed: bool = False
    ) -> Any:
        return self.request("DELETE", path, params, signed)
