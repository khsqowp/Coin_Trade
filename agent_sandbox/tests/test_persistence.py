"""Fault injection at durable state/log transition boundaries."""

import pytest
from ledger import Ledger
from generation import initialize, ensure_week_closed
from safety import SafetyError
from test_generation import Marks, record
from test_week_boundary import ts


@pytest.mark.parametrize("after_append", [False, True])
def test_fill_recovery_exactly_once(ledger, cfg, monkeypatch, after_append):
    original = ledger.store.append

    def interrupted(name, value):
        if name == "fills.jsonl":
            if after_append:
                original(name, value)
            raise OSError("simulated crash")
        original(name, value)

    monkeypatch.setattr(ledger.store, "append", interrupted)
    with pytest.raises(OSError):
        ledger.apply_fill(
            "BTCUSDT", "BUY", 1, 100, 0.05, ledger.now, "durable", stop=98
        )
    monkeypatch.setattr(ledger.store, "append", original)
    recovered = Ledger(ledger.store, cfg)
    assert recovered.equity() == 999.95
    assert len(recovered.store.records("fills.jsonl")) == 1
    assert not recovered.apply_fill(
        "BTCUSDT", "BUY", 1, 100, 0.05, ledger.now, "durable", stop=98
    )
    assert len(recovered.store.records("fills.jsonl")) == 1
    assert recovered.current["pending_fills"] == []


def test_retirement_interrupted_before_commit(ledger, cfg, monkeypatch):
    ledger.store.write_notes(1, "Preserve archived notes")
    record(ledger, ts("2024-01-08T00:00:00Z"), 1099)
    original = ledger.store.write

    def interrupted(name, value):
        if name == "current.json" and value["generation"] == 2:
            raise OSError("interrupted commit")
        original(name, value)

    monkeypatch.setattr(ledger.store, "write", interrupted)
    with pytest.raises(OSError):
        ensure_week_closed(ledger.store, Marks(), cfg, ts("2024-01-08T00:00:00Z"), True)
    assert ledger.store.read("current.json")["generation"] == 1
    monkeypatch.setattr(ledger.store, "write", original)
    ensure_week_closed(ledger.store, Marks(), cfg, ts("2024-01-08T00:00:00Z"), True)
    assert ledger.store.notes(1) == "" and ledger.store.notes(2) == ""
    assert (
        ledger.store.dir / "archive/gen_1/notes.md"
    ).read_text() == "Preserve archived notes"
    assert len(ledger.store.read("generations.json")) == 1


def test_mode_is_persistent_and_carried(ledger, cfg):
    initialize(ledger.store, cfg, ledger.now, True)
    with pytest.raises(SafetyError):
        initialize(ledger.store, cfg, ledger.now, False)
    ensure_week_closed(ledger.store, Marks(), cfg, ts("2024-01-08T00:00:00Z"), True)
    assert ledger.store.read("current.json")["execution_mode"] == "dry-run"
    with pytest.raises(SafetyError):
        initialize(ledger.store, cfg, ledger.now, False)
