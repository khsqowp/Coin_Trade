import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import momentum_state as state


def test_stale_save_is_refused(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    monkeypatch.setattr(state, "STATE_PATH", path)
    path.write_text(json.dumps({"state_seq": 4, "halted": False}))
    zombie = state.load_state()
    current = state.load_state()
    current["halted"] = True
    state.save_state(current)
    zombie["halted"] = False
    with pytest.raises(state.StaleStateError):
        state.save_state(zombie)
    assert json.loads(path.read_text())["halted"] is True


def test_save_increments_seq_and_does_not_persist_loaded_seq(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    monkeypatch.setattr(state, "STATE_PATH", path)
    st = state.load_state()
    state.save_state(st)
    assert st["state_seq"] == st["_loaded_seq"] == 1
    persisted = json.loads(path.read_text())
    assert persisted["state_seq"] == 1
    assert "_loaded_seq" not in persisted


def test_transfer_cursor_is_defaulted():
    assert "last_transfer_check_ms" in state._DEFAULT_STATE
    assert state._DEFAULT_STATE["last_transfer_check_ms"] is None
