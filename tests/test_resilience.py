import json
import sys
from pathlib import Path

import ccxt
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import ccxt_retry
from app import momentum_rotation_loop as m
from app import state_io


# --- retry helper -------------------------------------------------------
def test_retry_succeeds_after_network_errors():
    calls, sleeps = [], []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise ccxt.RequestTimeout("t")
        return "ok"

    assert ccxt_retry.retry_read(flaky, sleep=sleeps.append) == "ok"
    assert len(calls) == 3
    assert sleeps == [1.0, 2.0]


def test_retry_gives_up_after_tries():
    calls = []

    def always():
        calls.append(1)
        raise ccxt.NetworkError("x")

    with pytest.raises(ccxt.NetworkError):
        ccxt_retry.retry_read(always, tries=3, sleep=lambda _: None)
    assert len(calls) == 3


@pytest.mark.parametrize("exc", [ccxt.InsufficientFunds("x"), ccxt.RateLimitExceeded("x"), ValueError("x")])
def test_retry_does_not_retry_other_errors(exc):
    calls = []

    def boom():
        calls.append(1)
        raise exc

    with pytest.raises(type(exc)):
        ccxt_retry.retry_read(boom, sleep=lambda _: None)
    assert len(calls) == 1


# --- partial price guard ------------------------------------------------
def _ranked(n=20):
    return pd.Series(range(n, 0, -1), index=[f"S{i}" for i in range(n)], dtype=float)


def test_gap_guard_blocks_when_held_symbol_missing():
    ranked = _ranked()
    prices = {b: 1.0 for b in ranked.index}
    del prices["S10"]  # 중간 순위지만 보유중
    assert m._price_gap_blocks_rebalance(prices, {"S10": {}}, ranked) == ["S10"]


def test_gap_guard_blocks_when_top_or_bottom_candidate_missing():
    ranked = _ranked()
    prices = {b: 1.0 for b in ranked.index}
    del prices["S0"]
    del prices["S19"]
    assert m._price_gap_blocks_rebalance(prices, {}, ranked) == ["S0", "S19"]


def test_gap_guard_ignores_unheld_mid_rank_gap():
    ranked = _ranked()
    prices = {b: 1.0 for b in ranked.index}
    del prices["S10"]
    assert m._price_gap_blocks_rebalance(prices, {}, ranked) == []


def test_rebalance_live_skips_without_orders_on_price_gap(monkeypatch):
    from app import momentum_rotation_exec as ex

    class Client:
        def __init__(self):
            self.orders = 0

    client = Client()
    monkeypatch.setattr(ex, "exec_client", lambda mode: client)
    monkeypatch.setattr(ex, "account_equity_usdt", lambda c: 1000.0)
    monkeypatch.setattr(ex, "apply_targets", lambda *a, **k: pytest.fail("주문 경로 진입"))
    monkeypatch.setattr(m, "_ranked_momentum", lambda: _ranked())
    prices = {f"S{i}": 1.0 for i in range(20)}
    del prices["S1"]
    state = {"positions": {}, "trade_log": []}
    assert m._rebalance_live(state, prices, 1) is False
    assert "시세 누락" in state["trade_log"][-1]["message"]


# --- consecutive failure counter ---------------------------------------
def test_failure_counter_alerts_and_resets(capsys):
    m._consecutive_cycle_failures = 0
    for _ in range(3):
        m._note_cycle_failure(RuntimeError("net"))
    assert m._consecutive_cycle_failures == 3
    assert "연속 3회 실패" in capsys.readouterr().out
    m._note_cycle_success()
    assert m._consecutive_cycle_failures == 0


# --- compact atomic state write ---------------------------------------
def test_state_write_is_compact_and_roundtrips(tmp_path):
    path = tmp_path / "s.json"
    state = {"a": [1, 2], "msg": "한글"}
    state_io.atomic_write_json(path, state)
    text = path.read_text()
    assert "\n" not in text and ": " not in text
    assert json.loads(text) == state
    assert not path.with_suffix(".tmp").exists()


def test_state_write_failure_removes_tmp_and_keeps_old(tmp_path, monkeypatch):
    path = tmp_path / "s.json"
    path.write_text('{"old":1}')

    def fail(src, dst):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(state_io.os, "replace", fail)
    with pytest.raises(OSError):
        state_io.atomic_write_json(path, {"new": 2})
    assert json.loads(path.read_text()) == {"old": 1}
    assert not path.with_suffix(".tmp").exists()
