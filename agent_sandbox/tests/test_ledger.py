import pytest


def open_action(**kw):
    return {
        "symbol": "BTCUSDT",
        "side": "long",
        "size_pct_equity": 10,
        "leverage": 3,
        "stop_loss": 98,
        "take_profit": 104,
        "rationale": "test",
        **kw,
    }


def test_fills_virtual_and_fees(ledger):
    ledger.simulate_open(open_action(), 100, ledger.now)
    assert ledger.position("BTCUSDT")["qty"] == 3
    assert ledger.equity() == 999.85
    ledger.prices["BTCUSDT"] = 110
    assert ledger.equity() == 1029.85
    ledger.simulate_close("BTCUSDT", 110, ledger.now + 1)
    assert ledger.equity() == pytest.approx(1029.685)
    assert ledger.current["realized_pnl"] == 30 and ledger.positions == []
    assert ledger.current["fees"] == pytest.approx(0.315)


@pytest.mark.parametrize(
    "high,low,reason,price",
    [(105, 97, "stop", 98), (105, 99, "take_profit", 104), (101, 97, "stop", 98)],
)
def test_trigger_tie_stop_first(ledger, high, low, reason, price):
    ledger.simulate_open(open_action(), 100, ledger.now)
    ts = ledger.now
    ledger.simulate_triggers(
        {"BTCUSDT": [[ts * 1000, 100, high, low, 100, 1]]}, ts + 901
    )
    assert ledger.positions == []
    fill = ledger.store.records("fills.jsonl")[-1]
    assert fill["price"] == price and fill["reason"] == reason


def test_no_preentry_or_incomplete_trigger(ledger):
    ledger.simulate_open(open_action(), 100, ledger.now + 100)
    ts = ledger.now
    ledger.simulate_triggers({"BTCUSDT": [[ts * 1000, 100, 105, 97, 100, 1]]}, ts + 901)
    assert ledger.positions
    ledger.simulate_triggers(
        {"BTCUSDT": [[(ts + 900) * 1000, 100, 105, 97, 100, 1]]}, ts + 1000
    )
    assert ledger.positions


def test_foreign_detected(ledger):
    ledger.simulate_open(open_action(), 100, ledger.now)
    assert (
        ledger.reconcile(
            [{"symbol": "BTCUSDT", "positionAmt": "3", "entryPrice": "100"}]
        )
        == []
    )
    assert ledger.reconcile([{"symbol": "BTCUSDT", "positionAmt": "4"}]) == ["BTCUSDT"]
    assert len(ledger.store.records("rejections.jsonl")) == 1
    assert ledger.reconcile([{"symbol": "BTCUSDT", "positionAmt": "3"}]) == ["BTCUSDT"]


def test_foreign_manual_symbol(ledger):
    assert ledger.reconcile([{"symbol": "ETHUSDT", "positionAmt": "2"}]) == ["ETHUSDT"]


def test_fill_dedup(ledger):
    assert ledger.apply_fill("BTCUSDT", "BUY", 1, 100, 0.05, ledger.now, "id", stop=98)
    assert not ledger.apply_fill(
        "BTCUSDT", "BUY", 1, 100, 0.05, ledger.now, "id", stop=98
    )
    assert len(ledger.positions) == 1 and ledger.positions[0]["qty"] == 1


def test_real_fills_only_owned_registered(ledger):
    ledger.store.append(
        "orders.jsonl",
        {
            "generation": 1,
            "symbol": "BTCUSDT",
            "orderId": 1,
            "clientOrderId": "ags_a",
            "stop": 98,
        },
    )

    class Exchange:
        def user_trades(self, symbol, start_time, from_id=None):
            return [
                {
                    "orderId": 1,
                    "id": 1,
                    "time": 1704067200000,
                    "side": "BUY",
                    "qty": "1",
                    "price": "100",
                    "commission": "0.05",
                },
                {
                    "orderId": 2,
                    "id": 2,
                    "time": 1704067200000,
                    "side": "BUY",
                    "qty": "5",
                    "price": "100",
                    "commission": "0.25",
                },
            ]

        def order(self, symbol, order_id):
            return {"clientOrderId": "manual"}

    ledger.sync_fills(Exchange(), ["BTCUSDT"], ledger.now)
    ledger.sync_fills(Exchange(), ["BTCUSDT"], ledger.now)
    assert ledger.positions[0]["qty"] == 1 and ledger.equity() == 999.95
