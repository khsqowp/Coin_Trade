import pytest
import requests
from exchange import TestnetExchange
from http_client import ThrottledHttp, Signer, ExchangeError
from safety import SafetyError
from test_throttle import Session, Response, Clock


def client(cfg, session):
    clock = Clock()
    return TestnetExchange(
        ThrottledHttp(
            cfg,
            Signer("paper-api", "paper-secret"),
            session=session,
            clock=clock,
            sleep=clock.sleep,
        ),
        False,
    )


def test_ambiguous_order_queries_without_resubmitting(cfg):
    session = Session(
        [
            requests.Timeout(),
            Response(
                200, {"orderId": 7, "clientOrderId": "ags_test", "executedQty": "1"}
            ),
        ]
    )
    exchange = client(cfg, session)
    response = exchange.new_order("BTCUSDT", "BUY", 1, client_order_id="ags_test")
    assert response["orderId"] == 7
    assert [c[0][0] for c in session.calls] == ["POST", "GET"]
    assert session.calls[1][1]["params"]["origClientOrderId"] == "ags_test"


def test_5xx_order_recovered_by_id(cfg):
    session = Session(
        [
            Response(503, {"code": -1000, "msg": "uncertain"}),
            Response(200, {"orderId": 8}),
        ]
    )
    assert client(cfg, session).new_order("BTCUSDT", "BUY", 1)["orderId"] == 8
    assert len(session.calls) == 2


def test_4xx_order_not_retried(cfg):
    session = Session([Response(400, {"code": -2021, "msg": "trigger invalid"})])
    with pytest.raises(ExchangeError):
        client(cfg, session).new_order("BTCUSDT", "SELL", 1, "STOP_MARKET", 100)
    assert len(session.calls) == 1


def test_cancel_only_registered_ids(cfg):
    session = Session(
        [
            Response(
                200,
                [
                    {"orderId": 1, "clientOrderId": "ags_owned"},
                    {"orderId": 2, "clientOrderId": "ags_another_bot"},
                    {"orderId": 3, "clientOrderId": "manual"},
                ],
            ),
            Response(200, {"orderId": 1}),
        ]
    )
    exchange = client(cfg, session)
    assert exchange.cancel_all("BTCUSDT", {1}) == [{"orderId": 1}]
    assert len(session.calls) == 2
    assert session.calls[-1][1]["params"]["orderId"] == 1
    with pytest.raises(SafetyError):
        exchange.cancel_all("BTCUSDT")


def test_stop_reduce_only_and_mark_price(cfg):
    session = Session([Response(200, {"orderId": 1})])
    client(cfg, session).new_order("BTCUSDT", "SELL", 1, "STOP_MARKET", 98)
    params = session.calls[0][1]["params"]
    assert params["reduceOnly"] == "true" and params["workingType"] == "MARK_PRICE"
    assert params["newClientOrderId"].startswith("ags_")
    assert "signature" in params


def test_hedge_mode_refused(cfg):
    with pytest.raises(SafetyError):
        client(
            cfg, Session([Response(200, {"dualSidePosition": True})])
        ).position_mode()
