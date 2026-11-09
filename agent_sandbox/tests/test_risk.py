import pytest
from config import Config
from risk import RiskEngine


def action(**kw):
    return {
        "type": "open",
        "symbol": "BTCUSDT",
        "side": "long",
        "size_pct_equity": 10,
        "leverage": 3,
        "stop_loss": 98,
        "rationale": "test",
        **kw,
    }


def context(**kw):
    return {
        "equity": 1000,
        "positions": [],
        "prices": {"BTCUSDT": 100, "ETHUSDT": 100},
        "allowed_symbols": ["BTCUSDT", "ETHUSDT"],
        "data_age_seconds": 0,
        "sit_out_until": None,
        "symbol_info": {"BTCUSDT": {"minNotional": 5}},
        **kw,
    }


def held(symbol="ETHUSDT", **kw):
    return {
        "symbol": symbol,
        "side": "long",
        "qty": 1,
        "entry": 100,
        "stop": 98,
        "tp": None,
        "notional": 100,
        **kw,
    }


@pytest.mark.parametrize(
    "a,c,expected",
    [
        (action(), context(), True),
        (action(leverage=11), context(), False),
        (action(stop_loss=None), context(), False),
        (action(stop_loss=100), context(), False),
        (action(side="short", stop_loss=98), context(), False),
        (action(side="short", stop_loss=102), context(), True),
        (action(take_profit=99), context(), False),
        (action(side="short", stop_loss=102, take_profit=101), context(), False),
        (action(size_pct_equity=100, leverage=3, stop_loss=98), context(), False),
        (action(size_pct_equity=100, leverage=4, stop_loss=99), context(), False),
        (action(), context(data_age_seconds=301), False),
        (action(), context(data_age_seconds=300), True),
        (action(), context(sit_out_until=123), False),
        (action(), context(allowed_symbols=[]), False),
        (action(), context(positions=[held("BTCUSDT")]), False),
        (action(size_pct_equity=0.01), context(), False),
        (action(), context(symbol_info={"BTCUSDT": {"minQty": 4}}), False),
        (action(), context(foreign_symbols=["BTCUSDT"]), False),
        ({"type": "close", "symbol": "BTCUSDT"}, context(), False),
        (
            {"type": "close", "symbol": "BTCUSDT"},
            context(
                positions=[held("BTCUSDT")], data_age_seconds=999, allowed_symbols=[]
            ),
            True,
        ),
        (
            {"type": "modify", "symbol": "BTCUSDT", "stop_loss": 90},
            context(positions=[held("BTCUSDT")]),
            True,
        ),
        (
            {"type": "modify", "symbol": "BTCUSDT", "stop_loss": 40},
            context(positions=[held("BTCUSDT")]),
            False,
        ),
        (
            {"type": "modify", "symbol": "BTCUSDT", "stop_loss": 101},
            context(positions=[held("BTCUSDT")]),
            False,
        ),
        (
            {"type": "modify", "symbol": "BTCUSDT", "take_profit": 120},
            context(positions=[held("BTCUSDT")]),
            True,
        ),
        ({"type": "modify", "symbol": "BTCUSDT", "stop_loss": 99}, context(), False),
        (
            {"type": "modify", "symbol": "BTCUSDT", "stop_loss": 99},
            context(positions=[held("BTCUSDT")], data_age_seconds=301),
            False,
        ),
    ],
)
def test_rules(a, c, expected):
    _, ok, reason = RiskEngine(Config()).evaluate([a], c)[0]
    assert ok is expected and reason


def test_max_positions_and_sequential():
    cfg = Config(max_positions=1)
    engine = RiskEngine(cfg)
    assert not engine.evaluate([action()], context(positions=[held()]))[0][1]
    outcomes = engine.evaluate([action(), action(symbol="ETHUSDT")], context())
    assert [r[1] for r in outcomes] == [True, False]
    assert [r[1] for r in engine.evaluate([action(), action()], context())] == [
        True,
        False,
    ]
    assert all(
        r[1]
        for r in engine.evaluate(
            [{"type": "close", "symbol": "ETHUSDT"}, action()],
            context(positions=[held()]),
        )
    )


def test_exact_risk_and_gross():
    e = RiskEngine(Config())
    assert e.evaluate(
        [action(size_pct_equity=100, leverage=1, stop_loss=95)], context()
    )[0][1]
    assert e.evaluate(
        [action(size_pct_equity=100, leverage=3, stop_loss=99)], context()
    )[0][1]
    assert not e.evaluate(
        [action(size_pct_equity=100, leverage=3, stop_loss=99)],
        context(positions=[held()]),
    )[0][1]
    assert [
        r[1]
        for r in e.evaluate(
            [
                action(size_pct_equity=60, leverage=3, stop_loss=99),
                action(symbol="ETHUSDT", size_pct_equity=60, leverage=3, stop_loss=99),
            ],
            context(),
        )
    ] == [True, False]


def test_daily():
    e = RiskEngine(Config())
    assert e.daily_loss_breached(850, 1000)
    assert not e.daily_loss_breached(850.01, 1000)
    assert not e.daily_loss_breached(0, 0)
