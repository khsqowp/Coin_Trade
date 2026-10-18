import pytest
from generation import ensure_week_closed, evaluate_week, enforce_daily
from ledger import Ledger
from test_week_boundary import ts


class Marks:
    def premium_index(self):
        return [{"symbol": "BTCUSDT", "markPrice": "100"}]

    def exchange_info(self):
        return {"BTCUSDT": {"stepSize": "0.001", "tickSize": "0.01"}}


def record(ledger, when, equity):
    ledger.store.append(
        "equity.jsonl",
        {"generation": ledger.current["generation"], "ts": when, "equity": equity},
    )


def test_survive_carry_notes(ledger, cfg):
    ledger.store.write_notes(1, "Carry this plan")
    record(ledger, ts("2024-01-08T00:00:00Z"), 1100)
    events = ensure_week_closed(
        ledger.store, Marks(), cfg, ts("2024-01-08T00:00:00Z"), True
    )
    assert events[0]["survived"]
    current = ledger.store.read("current.json")
    assert current["generation"] == 1 and current["week_start_equity"] == 1100
    assert ledger.store.notes(1) == "Carry this plan"
    assert (
        ensure_week_closed(ledger.store, Marks(), cfg, ts("2024-01-08T00:05:00Z"), True)
        == []
    )


def test_retire_archive_wipe_and_flatten(ledger, cfg):
    ledger.store.write_notes(1, "Old notes")
    ledger.simulate_open(
        {
            "symbol": "BTCUSDT",
            "side": "long",
            "size_pct_equity": 10,
            "leverage": 3,
            "stop_loss": 98,
            "rationale": "test",
        },
        100,
        ledger.now,
    )
    record(ledger, ts("2024-01-07T23:59:59Z"), 1099.99)
    events = ensure_week_closed(
        ledger.store, Marks(), cfg, ts("2024-01-08T00:00:00Z"), True
    )
    assert not events[0]["survived"]
    current = ledger.store.read("current.json")
    assert (
        current["generation"] == 2
        and current["positions"] == []
        and current["start_virtual_equity"] == 1000
    )
    assert ledger.store.notes(1) == "" and ledger.store.notes(2) == ""
    archive = ledger.store.dir / "archive/gen_1"
    assert (archive / "final_report.md").exists()
    assert (archive / "notes.md").read_text() == "Old notes"
    assert len(ledger.store.records("fills.jsonl")) == 2
    assert Ledger(ledger.store, cfg).equity() == 1000


def test_multiple_missed_weeks(ledger, cfg):
    record(ledger, ts("2024-01-08T00:00:00Z"), 1100)
    record(ledger, ts("2024-01-15T00:00:00Z"), 1200)
    events = ensure_week_closed(
        ledger.store, Marks(), cfg, ts("2024-01-29T00:00:00Z"), True
    )
    assert [e["survived"] for e in events] == [True, True, False, False]
    assert ledger.store.read("current.json")["generation"] == 3
    assert (
        ensure_week_closed(ledger.store, Marks(), cfg, ts("2024-01-29T00:00:00Z"), True)
        == []
    )
    assert len(ledger.store.read("generations.json")) == 4


def test_midweek_partial(ledger, cfg):
    ledger.current["start_ts"] = ts("2024-01-03T10:00:00Z")
    ledger.save()
    record(ledger, ts("2024-01-08T00:00:00Z"), 1100)
    assert ensure_week_closed(
        ledger.store, Marks(), cfg, ts("2024-01-08T00:00:00Z"), True
    )[0]["partial_week"]


def test_exact_target():
    assert evaluate_week(100, 100)
    assert not evaluate_week(99.99, 100)


def test_daily_flatten_sitout(ledger, cfg):
    ledger.simulate_open(
        {
            "symbol": "BTCUSDT",
            "side": "long",
            "size_pct_equity": 100,
            "leverage": 3,
            "stop_loss": 98,
            "rationale": "test",
        },
        100,
        ledger.now,
    )
    ledger.prices["BTCUSDT"] = 90
    now = ts("2024-01-01T12:00:00Z")
    ledger.now = now
    assert enforce_daily(ledger, None, cfg, now, True)
    assert ledger.positions == []
    assert ledger.current["sit_out_until"] == ts("2024-01-02T00:00:00Z")
    assert enforce_daily(ledger, None, cfg, now + 3600, True)
    assert not enforce_daily(ledger, None, cfg, ts("2024-01-02T00:00:00Z"), True)
    assert ledger.current["day_start_equity"] == ledger.equity()


def test_foreign_prevents_false_retirement(ledger, cfg):
    ledger.simulate_open(
        {
            "symbol": "BTCUSDT",
            "side": "long",
            "size_pct_equity": 10,
            "leverage": 3,
            "stop_loss": 98,
            "rationale": "test",
        },
        100,
        ledger.now,
    )
    ledger.current["foreign_symbols"] = ["BTCUSDT"]
    ledger.save()
    with pytest.raises(RuntimeError):
        ensure_week_closed(ledger.store, Marks(), cfg, ts("2024-01-08T00:00:00Z"), True)
    assert ledger.store.read("current.json")["generation"] == 1
