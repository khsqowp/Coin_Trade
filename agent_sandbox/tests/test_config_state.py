import fcntl
import json
import pytest
from config import Config, load_config
from state import StateStore


def test_defaults_and_merge(tmp_path):
    config_file = tmp_path / "config.json"
    config_file.write_text(
        json.dumps({"tick_minutes": 30, "state_dir": str(tmp_path / "state")})
    )
    cfg = load_config(config_file)
    assert cfg.tick_minutes == 30 and cfg.start_equity == 1000
    assert len(cfg.watchlist) == 10 and cfg.core_symbols == ["BTCUSDT", "ETHUSDT"]


@pytest.mark.parametrize(
    "data",
    [
        {"unknown": 1},
        {"max_leverage": True},
        {"start_equity": float("nan")},
        {"state_dir": "/outside-project"},
        {"watchlist": [1]},
    ],
)
def test_invalid_config(tmp_path, data):
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        load_config(config_file)


def test_atomic_json_failure_preserves_prior(tmp_path):
    store = StateStore(tmp_path / "state")
    store.write("data.json", {"value": 1})
    with pytest.raises(ValueError):
        store.write("data.json", {"value": float("nan")})
    assert store.read("data.json") == {"value": 1}
    assert not list(store.dir.glob(".data.json*"))
    store.append("records.jsonl", {"n": 1})
    store.append("records.jsonl", {"n": 2})
    assert store.records("records.jsonl") == [{"n": 1}, {"n": 2}]


def test_run_lock_excludes_second_descriptor(tmp_path):
    store = StateStore(tmp_path / "state")
    with store.lock():
        with (store.dir / ".run.lock").open("a") as second:
            with pytest.raises(BlockingIOError):
                fcntl.flock(second, fcntl.LOCK_EX | fcntl.LOCK_NB)
    with (store.dir / ".run.lock").open("a") as second:
        fcntl.flock(second, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(second, fcntl.LOCK_UN)
