"""Exact-host protection and narrowly scoped credential loading."""

import os
from pathlib import Path
from typing import Mapping, MutableMapping, Iterable
from urllib.parse import urlparse

TESTNET_HOST = "testnet.binancefuture.com"
FORBIDDEN_HOSTS = frozenset({"api.binance.com", "fapi.binance.com", "dapi.binance.com"})
KEY_NAMES = ("BINANCE_FUTURE_TESTNET_API_KEY", "BINANCE_FUTURE_TESTNET_SECRET_KEY")


class SafetyError(RuntimeError):
    pass


def assert_testnet_url(url: str) -> None:
    try:
        p = urlparse(url)
        valid = (
            p.scheme == "https"
            and p.hostname == TESTNET_HOST
            and p.port in (None, 443)
            and not p.username
            and not p.password
        )
    except ValueError:
        valid = False
    if not valid:
        raise SafetyError("Only the exact HTTPS futures testnet host is permitted")


def load_testnet_keys(environ: Mapping[str, str] = os.environ) -> tuple[str, str]:
    values = tuple(environ.get(name, "") for name in KEY_NAMES)
    if not all(values):
        raise SafetyError(
            "Both BINANCE_FUTURE_TESTNET_API_KEY and BINANCE_FUTURE_TESTNET_SECRET_KEY are required; use an offline fixture for offline dry-run"
        )
    return values[0], values[1]


def load_env_file(path: str | Path, environ: MutableMapping[str, str]) -> None:
    with Path(path).open() as stream:
        for line in stream:
            name, sep, value = line.strip().removeprefix("export ").partition("=")
            name = name.strip()
            if sep and name in KEY_NAMES and name not in environ:
                value = value.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                    value = value[1:-1]
                else:
                    value = value.split(" #", 1)[0].strip()
                environ[name] = value


def redact(text: str, secrets: Iterable[str]) -> str:
    for secret in sorted((s for s in secrets if s), key=len, reverse=True):
        text = text.replace(secret, "[REDACTED]")
    return text
