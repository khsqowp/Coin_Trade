from executor import execute
from test_ledger import open_action


class FakeExchange:
    def __init__(self, fail_stop=False):
        self.calls = []
        self.n = 0
        self.fail_stop = fail_stop

    def set_leverage(self, *args):
        self.calls.append(("leverage", args))

    def new_order(self, symbol, side, quantity, **kw):
        self.calls.append(("order", kw.get("order_type"), kw.get("reduce_only"), side))
        if self.fail_stop and kw.get("order_type") == "STOP_MARKET":
            raise RuntimeError("failed")
        self.n += 1
        return {
            "orderId": self.n,
            "clientOrderId": f"ags_{self.n}",
            "executedQty": quantity,
        }

    def cancel_order(self, *args):
        self.calls.append(("cancel", args))

    def cancel_all(self, *args, **kw):
        self.calls.append(("cancel_all", args))
        return []

    def user_trades(self, *args):
        return []


def test_dry_no_exchange_calls(ledger, cfg):
    class Forbidden:
        def __getattr__(self, name):
            raise AssertionError("dry-run touched exchange order API")

    a = dict(open_action(), type="open")
    execute([a], Forbidden(), ledger, cfg, True)
    execute(
        [{"type": "modify", "symbol": "BTCUSDT", "stop_loss": 99, "rationale": ""}],
        Forbidden(),
        ledger,
        cfg,
        True,
    )
    execute(
        [{"type": "close", "symbol": "BTCUSDT", "rationale": ""}],
        Forbidden(),
        ledger,
        cfg,
        True,
    )
    assert not ledger.positions and len(ledger.store.records("orders.jsonl")) == 3


def test_stop_failure_emergency_close(ledger, cfg):
    exchange = FakeExchange(True)
    out = execute([dict(open_action(), type="open")], exchange, ledger, cfg, False)
    assert out[0]["status"] == "failed"
    assert exchange.calls[-1] == ("order", "MARKET", True, "SELL")
    assert any(
        r.get("level") == "CRITICAL" for r in ledger.store.records("rejections.jsonl")
    )


def test_modify_places_before_cancel(ledger, cfg):
    ledger.simulate_open(open_action(), 100, ledger.now)
    p = ledger.position("BTCUSDT")
    p.update(stop_order_id=10, tp_order_id=11)
    exchange = FakeExchange()
    execute(
        [
            {
                "type": "modify",
                "symbol": "BTCUSDT",
                "stop_loss": 99,
                "take_profit": 105,
                "rationale": "",
            }
        ],
        exchange,
        ledger,
        cfg,
        False,
    )
    assert [c[0] for c in exchange.calls] == ["order", "cancel", "order", "cancel"]
    assert exchange.calls[0][1] == "STOP_MARKET"
    assert exchange.calls[1][1] == ("BTCUSDT", 10)


def test_foreign_no_order(ledger, cfg):
    ledger.current["foreign_symbols"] = ["BTCUSDT"]
    exchange = FakeExchange()
    assert (
        execute([dict(open_action(), type="open")], exchange, ledger, cfg, False)[0][
            "status"
        ]
        == "blocked_foreign"
    )
    assert exchange.calls == []


def test_zero_ack_still_places_stop(ledger, cfg):
    class Delayed(FakeExchange):
        def new_order(self, *args, **kwargs):
            response = super().new_order(*args, **kwargs)
            if kwargs.get("order_type") == "MARKET":
                response["executedQty"] = "0"
            return response

    exchange = Delayed()
    execute([dict(open_action(), type="open")], exchange, ledger, cfg, False)
    assert exchange.calls[2][1] == "STOP_MARKET"
    assert ledger.current["opening_intents"]["BTCUSDT"]["stop_order_id"]


def test_pending_submission_recovery(ledger, cfg):
    from executor import recover_pending_orders

    cid = "ags_pending"
    ledger.current["pending_orders"] = {
        cid: {
            "symbol": "BTCUSDT",
            "clientOrderId": cid,
            "type": "MARKET",
            "side": "BUY",
            "quantity": "1",
            "stopPrice": None,
            "reduceOnly": False,
            "stop": 98,
            "tp": None,
            "decision_id": "decision",
            "rationale": "",
        }
    }
    ledger.save()

    class Recovery:
        def order_by_client(self, symbol, client_id):
            assert client_id == cid
            return {"orderId": 99, "executedQty": "1", "status": "FILLED"}

    recover_pending_orders(Recovery(), ledger)
    assert ledger.current["pending_orders"] == {}
    assert ledger.store.records("orders.jsonl")[-1]["clientOrderId"] == cid


def test_rounding_risk_rechecked(ledger, cfg):
    ledger.symbol_info["BTCUSDT"]["tickSize"] = "10"
    exchange = FakeExchange()
    # Admission risk is 3%, but rounding 99 down to 90 makes it 30%.
    outcomes = execute(
        [dict(open_action(size_pct_equity=100, leverage=3, stop_loss=99), type="open")],
        exchange,
        ledger,
        cfg,
        False,
    )
    assert outcomes[0]["status"] == "risk_rejected" and not exchange.calls


def test_confirmed_flat_cancels_sibling_and_clears_opening(ledger, cfg):
    from executor import cleanup_closed_positions, recover_openings

    ledger.store.append(
        "orders.jsonl",
        {
            "generation": 1,
            "symbol": "BTCUSDT",
            "orderId": 2,
            "clientOrderId": "ags_stop",
        },
    )
    ledger.store.append(
        "orders.jsonl",
        {"generation": 1, "symbol": "BTCUSDT", "orderId": 3, "clientOrderId": "ags_tp"},
    )
    ledger.current["protections"] = {"BTCUSDT": {"stop_order_id": 2, "tp_order_id": 3}}
    ledger.current["opening_intents"] = {
        "BTCUSDT": {
            "action": dict(open_action(), type="open"),
            "entry_client_id": "ags_entry",
            "stop_order_id": 2,
        }
    }
    ledger.apply_fill(
        "BTCUSDT",
        "BUY",
        3,
        100,
        0.15,
        ledger.now,
        "live:entry",
        stop=98,
        decision_id="original",
    )
    ledger.apply_fill("BTCUSDT", "SELL", 3, 98, 0.147, ledger.now + 900, "live:stop")
    assert ledger.current["cleanup_symbols"] == ["BTCUSDT"]

    class Exchange:
        def cancel_all(self, symbol, owned_order_ids):
            assert symbol == "BTCUSDT" and owned_order_ids == {2, 3}
            return [{"orderId": 3}]

    cleanup_closed_positions(Exchange(), ledger)
    recover_openings(Exchange(), ledger)
    assert (
        ledger.current["protections"] == {} and ledger.current["opening_intents"] == {}
    )
    assert ledger.current["cleanup_symbols"] == []
    assert ledger.store.records("orders.jsonl")[-1]["canceled_order_id"] == 3
    assert ledger.store.records("fills.jsonl")[-1]["entry_decision_id"] == "original"


def test_unconfirmed_opening_blocks_without_foreign_label(ledger):
    import pytest
    from executor import resolve_flat_openings

    ledger.current["opening_intents"] = {"BTCUSDT": {"entry_client_id": "ags_entry"}}

    class Exchange:
        def order_by_client(self, *args):
            return {"status": "FILLED", "executedQty": "3"}

    with pytest.raises(RuntimeError):
        resolve_flat_openings(Exchange(), ledger)
    assert not ledger.current["foreign_symbols"]


def test_rejected_unfilled_opening_cleared(ledger):
    from executor import resolve_flat_openings

    ledger.current["opening_intents"] = {"BTCUSDT": {"entry_client_id": "ags_entry"}}

    class Exchange:
        def order_by_client(self, *args):
            return {"status": "EXPIRED", "executedQty": "0"}

    resolve_flat_openings(Exchange(), ledger)
    assert ledger.current["opening_intents"] == {}
