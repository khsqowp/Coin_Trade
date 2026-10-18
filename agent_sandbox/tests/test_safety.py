import pytest
from safety import (
    SafetyError,
    assert_testnet_url,
    load_testnet_keys,
    load_env_file,
    redact,
)
from http_client import Signer, ThrottledHttp, ExchangeError
from exchange import TestnetExchange, round_step


@pytest.mark.parametrize(
    "url",
    [
        "https://api.binance.com",
        "https://fapi.binance.com",
        "https://dapi.binance.com",
        "https://www.binance.com",
        "https://testnet.binancefuture.com.evil.com",
        "http://testnet.binancefuture.com",
        "https://evil.com/testnet.binancefuture.com",
        "https://user:pass@testnet.binancefuture.com",
        "https://testnet.binancefuture.com:444",
    ],
)
def test_urls(url):
    with pytest.raises(SafetyError):
        assert_testnet_url(url)


def test_valid_url():
    assert_testnet_url("https://testnet.binancefuture.com/fapi/v1/time")


def test_keys_only():
    env = {"BINANCE_API_KEY": "mainnet-key", "BINANCE_SECRET_KEY": "mainnet-secret"}
    with pytest.raises(SafetyError) as exc:
        load_testnet_keys(env)
    assert "mainnet-key" not in str(exc.value)
    env.update(
        BINANCE_FUTURE_TESTNET_API_KEY="paper-key",
        BINANCE_FUTURE_TESTNET_SECRET_KEY="paper-secret",
    )
    assert load_testnet_keys(env) == ("paper-key", "paper-secret")


def test_env_allowlist(tmp_path):
    path = tmp_path / "credentials.txt"
    path.write_text(
        'BINANCE_API_KEY=main\nOTHER_SECRET=other\nexport BINANCE_FUTURE_TESTNET_API_KEY="paper"\nBINANCE_FUTURE_TESTNET_SECRET_KEY=secret # comment\n'
    )
    env = {"BINANCE_FUTURE_TESTNET_API_KEY": "existing"}
    load_env_file(path, env)
    assert env == {
        "BINANCE_FUTURE_TESTNET_API_KEY": "existing",
        "BINANCE_FUTURE_TESTNET_SECRET_KEY": "secret",
    }


def test_http_refuses_before_send(cfg):
    class Session:
        def request(self, *args, **kw):
            raise AssertionError("must not send")

    with pytest.raises(SafetyError):
        ThrottledHttp(cfg, session=Session()).get(
            "https://fapi.binance.com/fapi/v1/time"
        )


def test_repr_and_exception_redaction(cfg):
    from test_throttle import Session, Response

    signer = Signer("private-api-key", "private-secret")
    client = ThrottledHttp(
        cfg,
        signer,
        session=Session(
            [Response(400, {"code": -1, "msg": "private-secret private-api-key"})]
        ),
    )
    assert "private" not in repr(signer) + repr(client)
    with pytest.raises(ExchangeError) as exc:
        client.get("/x", signed=True)
    assert "private-secret" not in str(exc.value) and "private-api-key" not in str(
        exc.value
    )
    assert redact("abcd abc", ["abc", "abcd"]) == "[REDACTED] [REDACTED]"


@pytest.mark.parametrize(
    "method,args",
    [
        ("set_leverage", ("BTCUSDT", 3)),
        ("new_order", ("BTCUSDT", "BUY", 1)),
        ("cancel_order", ("BTCUSDT", 1)),
        ("cancel_all", ("BTCUSDT",)),
    ],
)
def test_dry_orders_raise(cfg, method, args):
    exchange = TestnetExchange(None, True)
    with pytest.raises(SafetyError):
        getattr(exchange, method)(*args)


def test_rounding():
    assert round_step(1.234, "0.01") == "1.23"
    assert round_step(1.234, "0.01", up=True) == "1.24"
