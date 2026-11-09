from pathlib import Path
import json
from datetime import datetime, timezone
import pytest
import requests
from run_tick import main
from run_week_close import main as close_main
from state import StateStore


def inputs(tmp_path, symbol="BTCUSDT"):
    now = datetime(2024, 1, 1, 12, tzinfo=timezone.utc).timestamp()
    bars = [[(now - 900 * (250 - i)) * 1000, 100, 101, 99, 100, 10] for i in range(250)]
    fixture = {
        "account": {"equity": 900000, "positions": []},
        "premium_index": [
            {"symbol": symbol, "markPrice": "100", "lastFundingRate": "0.001"}
        ],
        "symbol_info": {
            symbol: {
                "stepSize": "0.001",
                "tickSize": "0.01",
                "minQty": 0.001,
                "minNotional": 5,
            }
        },
        "candles": {symbol: {interval: bars for interval in ("15m", "1h", "4h", "1d")}},
    }
    fixture_file = tmp_path / "fixture.json"
    fixture_file.write_text(json.dumps(fixture))
    decision_file = tmp_path / "decision.json"
    decision_file.write_text(
        json.dumps(
            {
                "actions": [
                    {
                        "type": "open",
                        "symbol": symbol,
                        "side": "long",
                        "size_pct_equity": 10,
                        "leverage": 3,
                        "stop_loss": 98,
                        "take_profit": 104,
                        "rationale": "test",
                    }
                ],
                "notes": "persist",
            }
        )
    )
    config_file = tmp_path / "config.json"
    config_file.write_text(
        json.dumps(
            {
                "state_dir": str(tmp_path / "state"),
                "watchlist": [symbol],
                "core_symbols": [symbol],
                "random_benchmark_runs": 3,
            }
        )
    )
    return fixture_file, decision_file, config_file, fixture


def test_pipeline_no_network(tmp_path, monkeypatch, capsys):
    def forbidden(*a, **kw):
        raise AssertionError("real network invoked")

    monkeypatch.setattr(requests.sessions.Session, "request", forbidden)
    monkeypatch.setattr("subprocess.run", forbidden)
    fixture, decision, config, data = inputs(tmp_path)
    args = [
        "--offline-fixture",
        str(fixture),
        "--fake-llm",
        str(decision),
        "--config",
        str(config),
        "--now",
        "2024-01-01T12:00:00Z",
    ]
    assert main(args) == 0
    store = StateStore(tmp_path / "state")
    assert store.read("current.json")["positions"][0]["qty"] == 3
    assert store.read("current.json")["fees"] == 0.15
    assert store.notes(1) == "persist"
    for name in ("ticks", "decisions", "orders", "fills", "equity"):
        assert store.records(name + ".jsonl")
    assert store.read("current.json")["start_virtual_equity"] == 1000
    # A later closed 15m candle hits both triggers; the stop must win.
    timestamp = datetime(2024, 1, 1, 12, tzinfo=timezone.utc).timestamp()
    data["candles"]["BTCUSDT"]["15m"].append([timestamp * 1000, 100, 105, 97, 100, 10])
    fixture.write_text(json.dumps(data))
    decision.write_text('{"actions":[],"notes":"new"}')
    args[-1] = "2024-01-01T13:00:00Z"
    assert main(args) == 0
    assert store.read("current.json")["positions"] == []
    assert store.records("fills.jsonl")[-1]["reason"] == "stop"
    assert store.read("current.json")["realized_pnl"] == -6
    assert "secret" not in capsys.readouterr().out


def test_malformed_decision_no_action(tmp_path):
    fixture, decision, config, _ = inputs(tmp_path)
    decision.write_text('{"actions":[{"type":"open"}],"notes":""}')
    assert (
        main(
            [
                "--offline-fixture",
                str(fixture),
                "--fake-llm",
                str(decision),
                "--config",
                str(config),
                "--now",
                "2024-01-01T12:00:00Z",
            ]
        )
        == 0
    )
    store = StateStore(tmp_path / "state")
    assert not store.read("current.json")["positions"]
    assert store.records("rejections.jsonl")


def test_week_close_offline_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(
        requests.sessions.Session, "request", lambda *a, **kw: pytest.fail("network")
    )
    fixture, decision, config, _ = inputs(tmp_path)
    decision.write_text('{"actions":[],"notes":"plan"}')
    assert (
        main(
            [
                "--offline-fixture",
                str(fixture),
                "--fake-llm",
                str(decision),
                "--config",
                str(config),
                "--now",
                "2024-01-01T12:00:00Z",
            ]
        )
        == 0
    )
    args = [
        "--offline-fixture",
        str(fixture),
        "--config",
        str(config),
        "--now",
        "2024-01-08T00:05:00Z",
    ]
    assert close_main(args) == 0
    store = StateStore(tmp_path / "state")
    assert store.read("current.json")["generation"] == 2
    assert store.read("generations.json")[0]["benchmarks_complete"]
    assert list((store.dir / "reports").glob("*.md"))
    assert close_main(args) == 0 and len(store.read("generations.json")) == 1


def test_fixture_cannot_place_real_orders(tmp_path):
    fixture, decision, config, _ = inputs(tmp_path)
    assert (
        main(
            [
                "--testnet-orders",
                "--offline-fixture",
                str(fixture),
                "--config",
                str(config),
            ]
        )
        == 2
    )


def test_mode_change_rejected_before_network(tmp_path, monkeypatch):
    fixture, decision, config, _ = inputs(tmp_path)
    decision.write_text('{"actions":[],"notes":""}')
    assert (
        main(
            [
                "--offline-fixture",
                str(fixture),
                "--fake-llm",
                str(decision),
                "--config",
                str(config),
                "--now",
                "2024-01-01T12:00:00Z",
            ]
        )
        == 0
    )
    monkeypatch.setattr(
        requests.sessions.Session,
        "request",
        lambda *a, **kw: pytest.fail("mode switch sent network"),
    )
    assert (
        main(
            [
                "--testnet-orders",
                "--config",
                str(config),
                "--now",
                "2024-01-01T13:00:00Z",
            ]
        )
        == 2
    )


def test_daily_loss_skips_llm_and_flattens(tmp_path):
    fixture, decision, config, data = inputs(tmp_path)
    d = json.loads(decision.read_text())
    d["actions"][0].update(size_pct_equity=100, leverage=3, stop_loss=99)
    decision.write_text(json.dumps(d))
    args = [
        "--offline-fixture",
        str(fixture),
        "--fake-llm",
        str(decision),
        "--config",
        str(config),
        "--now",
        "2024-01-01T12:00:00Z",
    ]
    assert main(args) == 0
    data["premium_index"][0]["markPrice"] = "90"
    fixture.write_text(json.dumps(data))
    # This path does not exist: the daily guard must skip even reading the fake LLM.
    args[3] = str(tmp_path / "must-not-read.json")
    args[-1] = "2024-01-01T13:00:00Z"
    assert main(args) == 0
    store = StateStore(tmp_path / "state")
    assert store.read("current.json")["positions"] == []
    assert (
        store.read("current.json")["sit_out_until"]
        == datetime(2024, 1, 2, tzinfo=timezone.utc).timestamp()
    )
    assert store.records("decisions.jsonl")[-1]["skipped"]


def test_stale_server_clock_rejects_open(tmp_path):
    fixture, decision, config, data = inputs(tmp_path)
    data["server_time"] = (
        datetime(2024, 1, 1, 12, tzinfo=timezone.utc).timestamp() - 301
    ) * 1000
    fixture.write_text(json.dumps(data))
    assert (
        main(
            [
                "--offline-fixture",
                str(fixture),
                "--fake-llm",
                str(decision),
                "--config",
                str(config),
                "--now",
                "2024-01-01T12:00:00Z",
            ]
        )
        == 0
    )
    store = StateStore(tmp_path / "state")
    assert store.read("current.json")["positions"] == []
    assert store.records("rejections.jsonl")[-1]["reason"] == "Market data is stale"
