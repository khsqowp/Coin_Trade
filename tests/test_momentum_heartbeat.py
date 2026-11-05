import json

from app import momentum_rotation_loop as loop


def test_heartbeat_is_atomically_written(monkeypatch, tmp_path):
    target = tmp_path / "heartbeat.json"
    monkeypatch.setattr(loop, "HEARTBEAT_PATH", str(target))
    monkeypatch.setattr(loop, "_heartbeat_cycle", 0)

    loop._write_heartbeat()

    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["cycle"] == 1
    assert payload["epoch"] > 0
    assert payload["ts_utc"].endswith("+00:00")
    assert not (tmp_path / "heartbeat.json.tmp").exists()


def test_heartbeat_failure_is_swallowed(monkeypatch, tmp_path):
    monkeypatch.setattr(loop, "HEARTBEAT_PATH", str(tmp_path / "missing" / "heartbeat.json"))
    loop._write_heartbeat()
